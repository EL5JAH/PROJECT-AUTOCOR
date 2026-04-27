#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/var/log/automation-bootstrap.log"
STATUS_FILE="/var/log/automation-bootstrap.status"
MARKER_FILE="/opt/bootstrap/.bootstrapped"
REPO_DIR="/opt/labrepo"
REPO_URL="https://github.com/EL5JAH/PROJECT-AUTOCOR.git"
BOOT_DELAY_SECONDS=180

exec > >(tee -a "$LOG_FILE") 2>&1

echo "BOOTSTRAP_STATE=starting" > "$STATUS_FILE"
echo "BOOTSTRAP_STARTED_AT=$(date -Iseconds)" >> "$STATUS_FILE"

if [[ -f "$MARKER_FILE" ]]; then
    echo "Bootstrap already completed. Exiting."
    echo "BOOTSTRAP_STATE=already_completed" > "$STATUS_FILE"
    echo "BOOTSTRAP_COMPLETED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 0
fi

export DEBIAN_FRONTEND=noninteractive

echo "Waiting ${BOOT_DELAY_SECONDS}s to allow lab devices to finish booting..."
sleep "${BOOT_DELAY_SECONDS}"

echo "Checking internet reachability before continuing..."
for _ in $(seq 1 30); do
    if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
        echo "Internet reachability confirmed."
        break
    fi
    echo "Internet not reachable yet. Retrying in 10 seconds..."
    sleep 10
done

if ! ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    echo "Bootstrap failed: internet never became reachable."
    echo "BOOTSTRAP_STATE=failed_no_internet" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

echo "Installing required packages..."
for i in 1 2 3; do
  apt-get update -y && break
  echo "apt-get update failed, retrying in 10 seconds..."
  sleep 10
done
apt-get install -y --fix-missing \
    git \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    jq \
    net-tools \
    iputils-ping \
    traceroute

###############################################################
# Install Docker Engine
#
# Purpose:
# - Install Docker from Docker's official Ubuntu repository
# - Allow the cisco user to run docker commands without sudo
#
# Placement:
# - Run after base packages are installed
# - Run before repo clone / venv setup in case future tooling
#   depends on Docker being available
#
# Important:
# - newgrp docker is intentionally NOT used here because bootstrap
#   runs non-interactively as a service
# - The docker group membership applies after the cisco user starts
#   a new login session
###############################################################

echo "Installing Docker Engine..."

install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

chmod a+r /etc/apt/keyrings/docker.asc

cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

for i in 1 2 3; do
  apt-get update -y && break
  echo "apt-get update failed after adding Docker repo, retrying in 10 seconds..."
  sleep 10
done

apt-get install -y --fix-missing \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

echo "Adding cisco user to docker group..."
usermod -aG docker cisco
echo "NOTE: Docker group membership for 'cisco' will apply on next login session."

echo "Enabling and starting Docker service..."
systemctl enable docker
systemctl start docker

echo "Docker installation complete."

###############################################################
# Validate Docker installation
#
# Purpose:
# - Confirm Docker service is installed and running
# - Confirm the cisco user has docker group membership configured
#
# Note:
# - We do NOT run `docker` as cisco here because group membership
#   may not apply until the next login session.
###############################################################

echo "Validating Docker installation..."

if ! systemctl is-active --quiet docker; then
    echo "Bootstrap failed: Docker service is not running."
    echo "BOOTSTRAP_STATE=failed_docker_service" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

if ! docker version >/dev/null 2>&1; then
    echo "Bootstrap failed: Docker CLI cannot communicate with Docker daemon."
    echo "BOOTSTRAP_STATE=failed_docker_cli" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

if ! id -nG cisco | grep -qw docker; then
    echo "Bootstrap failed: cisco user is not in the docker group."
    echo "BOOTSTRAP_STATE=failed_docker_group" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

echo "Docker validation passed."
echo "NOTE: cisco may need a new login session before running docker without sudo."

###############################################################
# Configure Ansible vault password helper
#
# Purpose:
# - Create the cisco user's .ansible directory
# - Install an executable helper script that Ansible can call
#   whenever it needs the vault password
#
# Why this change was made:
# - The previous design expected a plaintext vault password file
#   at ~/.ansible/.vault_pass.txt
# - Fresh builds failed because that file did not exist
# - This new design avoids storing a permanent plaintext password
#   file on disk
#
# How this works:
# - ansible.cfg points vault_password_file to:
#     /home/cisco/.ansible/get_vault_pass.sh
# - When Ansible needs the vault password, it executes that script
# - The script reads the password from the environment variable:
#     ANSIBLE_VAULT_PASSWORD
#
# Important:
# - This block does NOT hardcode the password
# - This block does NOT print the password
# - The password must be supplied externally at runtime
###############################################################

echo "Configuring Ansible vault password helper..."

CISCO_USER="cisco"
CISCO_HOME="/home/${CISCO_USER}"
ANSIBLE_DIR="${CISCO_HOME}/.ansible"
VAULT_HELPER="${ANSIBLE_DIR}/get_vault_pass.sh"

# Create the .ansible directory with secure permissions.
# 700 means only the owner can access the directory.
# install is used instead of mkdir/chown/chmod separately so the
# directory is created with the intended ownership and mode in one step.
install -d -m 700 -o "${CISCO_USER}" -g "${CISCO_USER}" "${ANSIBLE_DIR}"

# Create the vault helper script that Ansible will execute.
#
# Important behavior:
# - The script must print ONLY the vault password to stdout
# - The script must not print debug/status text to stdout
# - The script fails immediately if ANSIBLE_VAULT_PASSWORD is unset
cat > "${VAULT_HELPER}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

###############################################################
# get_vault_pass.sh
#
# Purpose:
# - Provide the Ansible Vault password at runtime
# - Avoid storing the vault password in the repo
# - Avoid using a permanent plaintext password file
#
# How it works:
# - Ansible executes this script because ansible.cfg points
#   vault_password_file to this path
# - The script reads the password from:
#     ANSIBLE_VAULT_PASSWORD
# - The script prints ONLY the password to stdout
#
# Important:
# - Do not add debug echo statements here
# - Do not hardcode the password here
# - Do not print anything except the password
###############################################################

# Fail immediately if the required environment variable is not set.
: "${ANSIBLE_VAULT_PASSWORD:?ANSIBLE_VAULT_PASSWORD is not set}"

# Print only the vault password for Ansible to consume.
printf '%s\n' "${ANSIBLE_VAULT_PASSWORD}"
EOF

# Ensure the helper script is owned by the cisco user even if
# bootstrap.sh is running as root.
chown "${CISCO_USER}:${CISCO_USER}" "${VAULT_HELPER}"

# 700 means only the owner can read/write/execute the helper.
chmod 700 "${VAULT_HELPER}"

# Validate that the helper script now exists.
if [[ ! -f "${VAULT_HELPER}" ]]; then
    echo "Bootstrap failed: vault helper script was not created."
    echo "BOOTSTRAP_STATE=failed_vault_helper" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

echo "Ansible vault password helper created successfully."

mkdir -p /opt/bootstrap
mkdir -p /opt
chown cisco:cisco /opt      # Give cisco ownership so it can create labrepo

echo "Preparing repo directory..."

if [[ -d "${REPO_DIR}" ]]; then
    echo "Removing existing repo directory..."
    rm -rf "${REPO_DIR}"
fi

echo "Cloning repo from ${REPO_URL} ..."
if ! sudo -u cisco git clone "${REPO_URL}" "${REPO_DIR}"; then
    echo "Bootstrap failed: git clone failed."
    echo "BOOTSTRAP_STATE=failed_git_clone" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

cd "${REPO_DIR}"
sudo -u cisco git checkout test-baseline_validate
sudo -u cisco git status

echo "Creating Python virtual environment..."
sudo -u cisco python3 -m venv .venv

echo "Installing Python requirements..."
sudo -u cisco bash -c "
source .venv/bin/activate &&
pip install --upgrade pip &&
pip install -r requirements.txt"

# Ensure repo scripts are executable by the owner/group/others as appropriate.
# This prevents needing to manually chmod scripts after bootstrap.
if [[ -d "${REPO_DIR}/scripts" ]]; then
    echo "Setting execute permissions on repo scripts..."
    find "${REPO_DIR}/scripts" -type f -name "*.sh" -exec chmod 755 {} \;
fi

echo "Creating helper commands..."
cat >/usr/local/bin/labenv <<'EOF'
#!/usr/bin/env bash
cd /opt/labrepo
source .venv/bin/activate
exec bash
EOF
chmod +x /usr/local/bin/labenv

cat >/usr/local/bin/bootstrap-status <<'EOF'
#!/usr/bin/env bash
echo "===== BOOTSTRAP STATUS ====="
cat /var/log/automation-bootstrap.status 2>/dev/null || echo "No status file found."
echo
echo "===== LAST 40 LOG LINES ====="
tail -n 40 /var/log/automation-bootstrap.log 2>/dev/null || echo "No log file found."
EOF
chmod +x /usr/local/bin/bootstrap-status

touch "${MARKER_FILE}"

echo "BOOTSTRAP_STATE=completed" > "$STATUS_FILE"
echo "BOOTSTRAP_COMPLETED_AT=$(date -Iseconds)" >> "$STATUS_FILE"

cat >/etc/motd <<'EOF'
Automation host is ready.

Core commands:
  bootstrap-status   Show bootstrap status and logs
  labenv             Enter lab environment (venv activated)

Validation:
  docker version     Check Docker daemon connectivity
  docker ps          Verify Docker access (no sudo)
  ansible --version  Verify Ansible environment

Notes:
  Docker group membership applies after login
  Export ANSIBLE_VAULT_PASSWORD before running Ansible

Logs:
  /var/log/automation-bootstrap.log
EOF

echo "Bootstrap complete."