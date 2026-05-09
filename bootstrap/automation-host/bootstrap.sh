#!/usr/bin/env bash
set -euo pipefail

###############################################################
# Initialize bootstrap environment
#
# Purpose:
# - Configure bootstrap runtime variables and logging
# - Initialize persistent bootstrap status tracking
# - Prevent repeated bootstrap execution after success
# - Validate required bootstrap prerequisites
#
# Components:
# - Bootstrap log file
# - Bootstrap status file
# - Bootstrap completion marker
# - Repository configuration variables
# - Required user validation
#
# Important:
# - bootstrap.sh runs as a systemd service during first boot
# - All stdout/stderr is redirected into the bootstrap log
# - set -euo pipefail is enabled for strict error handling
###############################################################

LOG_FILE="/var/log/automation-bootstrap.log"
STATUS_FILE="/var/log/automation-bootstrap.status"
MARKER_FILE="/opt/bootstrap/.bootstrapped"
REPO_DIR="/opt/labrepo"
REPO_URL="https://github.com/EL5JAH/PROJECT-AUTOCOR.git"
REPO_BRANCH="test-baseline_validate"
BOOT_DELAY_SECONDS=60
BOOTSTRAP_START_EPOCH=$(date +%s)

exec > >(tee -a "$LOG_FILE") 2>&1

section_start() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

section_end() {
  echo
  echo "Completed: $1"
}

echo "BOOTSTRAP_STATE=starting" > "$STATUS_FILE"
echo "BOOTSTRAP_STARTED_AT=$(date -Iseconds)" >> "$STATUS_FILE"

if [[ -f "$MARKER_FILE" ]]; then
    echo "Bootstrap already completed. Exiting."
    echo "BOOTSTRAP_STATE=already_completed" > "$STATUS_FILE"
    echo "BOOTSTRAP_COMPLETED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 0
fi

export DEBIAN_FRONTEND=noninteractive

###############################################################
# Load bootstrap configuration
#
# Purpose:
# - Allow user customization before bootstrap execution
# - Support portable GitLab/GitHub remote configuration
# - Allow optional local GitLab CE deployment
# - Provide reusable bootstrap customization entrypoint
#
# Config File:
# - /opt/bootstrap/bootstrap.env
#
# Supported Variables:
# - INSTALL_GITLAB
# - GIT_REMOTE_URL
#
# Important:
# - Values loaded here override bootstrap defaults
# - Missing config file is non-fatal
###############################################################

BOOTSTRAP_CONFIG="/opt/bootstrap/bootstrap.env"

if [[ -f "${BOOTSTRAP_CONFIG}" ]]; then
    echo "Loading bootstrap configuration: ${BOOTSTRAP_CONFIG}"

    # shellcheck disable=SC1090
    source "${BOOTSTRAP_CONFIG}"
else
    echo "No bootstrap configuration file found."
    echo "Using built-in bootstrap defaults."
fi

if ! id cisco >/dev/null 2>&1; then
    echo "Bootstrap failed: cisco user does not exist."
    echo "BOOTSTRAP_STATE=failed_missing_cisco_user" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

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

###############################################################
# Optimize Ubuntu service footprint
#
# Purpose:
# - Reduce bootstrap-time background contention
# - Prevent package/update helpers from competing with apt
# - Disable unnecessary firmware/update telemetry services
# - Keep automation-host lean for Docker, GitLab, Ansible, and pyATS
#
# Safe for:
# - Ubuntu Server
# - CML automation hosts
# - Disposable lab environments
# - Infrastructure automation workloads
#
# Important:
# - Do NOT disable networking, SSH, time sync, logging,
#   Docker, containerd, or cloud-init related services
###############################################################

echo
echo "============================================================"
echo "Optimizing Ubuntu service footprint"
echo "============================================================"

SERVICES_DISABLED=0

disable_service() {
    local UNIT="$1"

    if systemctl list-unit-files --type=service --type=socket --type=timer --all \
    --no-legend | awk '{print $1}' | grep -Fxq "${UNIT}"; then
        systemctl disable --now "$UNIT" 2>/dev/null || true
        systemctl mask "$UNIT" 2>/dev/null || true
        echo "Disabled: ${UNIT}"
        SERVICES_DISABLED=$((SERVICES_DISABLED + 1))
    else
        echo "Not present: ${UNIT}"
    fi
}

###############################################################
# Disable unattended apt timers
###############################################################

disable_service apt-daily.service
disable_service apt-daily.timer
disable_service apt-daily-upgrade.service
disable_service apt-daily-upgrade.timer

###############################################################
# Disable unnecessary package/update helpers
###############################################################

disable_service packagekit.service
disable_service packagekit.socket
disable_service dbus-org.freedesktop.PackageKit.service
disable_service update-notifier-download.service
disable_service update-notifier-download.timer

###############################################################
# Disable firmware update services
###############################################################

disable_service fwupd.service
disable_service fwupd-refresh.service
disable_service fwupd-refresh.timer

###############################################################
# Disable Ubuntu Pro / apt news helpers
###############################################################

disable_service apt-news.service
disable_service esm-cache.service

###############################################################
# Disable sysstat performance collection
###############################################################

disable_service sysstat.service
disable_service sysstat-collect.timer
disable_service sysstat-summary.timer

echo
echo "Service optimization complete"
echo "Services disabled/masked: ${SERVICES_DISABLED}"

###############################################################
# Validate optimized service state
###############################################################

echo
echo "============================================================"
echo "Validating optimized service state"
echo "============================================================"

validate_disabled() {
    local UNIT="$1"

    if systemctl is-enabled "$UNIT" >/dev/null 2>&1; then
        echo "WARNING: ${UNIT} still enabled"
    else
        echo "OK: ${UNIT} disabled"
    fi
}

validate_disabled packagekit.service
validate_disabled packagekit.socket
validate_disabled dbus-org.freedesktop.PackageKit.service
validate_disabled update-notifier-download.service
validate_disabled update-notifier-download.timer
validate_disabled fwupd.service
validate_disabled fwupd-refresh.timer
validate_disabled apt-news.service
validate_disabled esm-cache.service
validate_disabled sysstat.service

echo
echo "Checking for failed systemd units..."

if systemctl --failed --no-legend | grep -q .; then
    systemctl --failed
else
    echo "OK: no failed systemd units detected"
fi

echo
echo "Ubuntu service footprint optimization complete"

###############################################################
# Install base packages
###############################################################

echo
echo "============================================================"
echo "Installing base packages"
echo "============================================================"

apt-get install -y --no-install-recommends --fix-missing \
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

###############################################################
# Clone automation repository
#
# Purpose:
# - Prepare /opt/labrepo before any repo-based scripts run
# - Ensure bootstrap has access to scripts, requirements, and lab files
# - Clone as the cisco user so repo ownership is correct
###############################################################

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

###############################################################
# Validate automation repository
#
# Purpose:
# - Fail early if the repository did not clone correctly
# - Confirm required repo directories exist before later stages
# - Check out the target bootstrap branch
# - Ensure required bootstrap files are present
###############################################################

if [[ ! -d "${REPO_DIR}/.git" ]]; then
    echo "Bootstrap failed: repository missing or invalid: ${REPO_DIR}"
    echo "BOOTSTRAP_STATE=failed_repo_missing" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

cd "${REPO_DIR}"

echo "Checking out repository branch: ${REPO_BRANCH}"
if ! sudo -u cisco git checkout "${REPO_BRANCH}"; then
    echo "Bootstrap failed: unable to checkout branch ${REPO_BRANCH}."
    echo "BOOTSTRAP_STATE=failed_git_checkout" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

sudo -u cisco git status

if [[ ! -d "${REPO_DIR}/scripts" ]]; then
    echo "Bootstrap failed: repository scripts directory missing: ${REPO_DIR}/scripts"
    echo "BOOTSTRAP_STATE=failed_repo_scripts_missing" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

if [[ ! -f "${REPO_DIR}/requirements.txt" ]]; then
    echo "Bootstrap failed: requirements.txt missing: ${REPO_DIR}/requirements.txt"
    echo "BOOTSTRAP_STATE=failed_requirements_missing" > "$STATUS_FILE"
    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
    exit 1
fi

###############################################################
# Set repository script permissions
#
# Purpose:
# - Ensure repo shell scripts are executable after clone
# - Prevent manual chmod steps after bootstrap
# - Prepare repo scripts for later bootstrap stages
#
# Scope:
# - Applies execute permissions to all .sh files under:
#     /opt/labrepo/scripts
###############################################################

echo "Setting execute permissions on repo scripts..."
find "${REPO_DIR}/scripts" -type f -name "*.sh" -exec chmod 755 {} \;

###############################################################
# Create Python virtual environment
#
# Purpose:
# - Create an isolated Python environment for automation tooling
# - Install repo-defined Python dependencies from requirements.txt
# - Keep lab automation dependencies separate from system Python
###############################################################

echo "Creating Python virtual environment..."
sudo -u cisco python3 -m venv .venv

echo "Installing Python requirements..."
sudo -u cisco bash -c "
cd '${REPO_DIR}' &&
source .venv/bin/activate &&
pip install --upgrade pip &&
pip install -r requirements.txt"

###############################################################
# Install Docker Engine
#
# Purpose:
# - Install Docker from Docker's official Ubuntu repository
# - Allow the cisco user to run docker commands without sudo
#
# Placement:
# - Run after base packages are installed
# - Run after repo clone / venv setup
# - Run before GitLab setup because GitLab depends on Docker
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

apt-get clean
rm -rf /var/lib/apt/lists/*

for i in 1 2 3; do
  apt-get update -y && break
  echo "apt-get update failed after adding Docker repo, retrying in 10 seconds..."
  sleep 10
done

apt-get install -y --no-install-recommends --fix-missing \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

echo "Adding cisco user to docker group..."
usermod -aG docker cisco
echo "NOTE: Docker group membership for 'cisco' will apply on next login session."

echo "Enabling and starting Docker service..."
systemctl enable --now docker

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
# Configure Git platform mode
#
# Purpose:
# - Use GitLab.com by default for faster bootstrap builds
# - Avoid pulling/initializing the large local GitLab CE container
# - Optionally deploy a portable self-hosted GitLab CE lab
#
# Modes:
# - INSTALL_GITLAB=false  Use GitLab.com/GitHub remote workflow
# - INSTALL_GITLAB=true   Install local GitLab CE Docker lab
###############################################################

section_start "Configure Git platform mode"

INSTALL_GITLAB="${INSTALL_GITLAB:-false}"
GIT_REMOTE_URL="${GIT_REMOTE_URL:-}"

echo "GitLab local install requested: ${INSTALL_GITLAB}"

if [[ "${INSTALL_GITLAB}" == "true" ]]; then

    GITLAB_SCRIPTS=(
      "/opt/labrepo/scripts/setup_gitlab_container.sh"
      "/opt/labrepo/scripts/setup_gitlab_ssh.sh"
      "/opt/labrepo/scripts/validate_gitlab_lab.sh"
    )

    echo "Validating GitLab helper scripts..."

    for script in "${GITLAB_SCRIPTS[@]}"; do
      if [[ ! -f "$script" ]]; then
        echo "Bootstrap failed: Required GitLab helper script missing: $script"
        echo "BOOTSTRAP_STATE=failed_gitlab_script_missing" > "$STATUS_FILE"
        echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
        exit 1
      fi
    done

    chmod +x "${GITLAB_SCRIPTS[@]}"

    echo "Running GitLab container setup..."
    /opt/labrepo/scripts/setup_gitlab_container.sh

    echo "Running GitLab SSH setup..."
    /opt/labrepo/scripts/setup_gitlab_ssh.sh

    ln -sf /opt/labrepo/scripts/validate_gitlab_lab.sh \
      /usr/local/bin/validate-gitlab-lab

    echo "Local GitLab portable DevOps lab setup complete."

else

    echo "Skipping local GitLab CE install."
    echo "Using hosted Git workflow for faster bootstrap."

    if [[ -n "${GIT_REMOTE_URL}" ]]; then

        echo "Configuring Git remote origin..."

        cd "${REPO_DIR}"

        if git remote get-url origin >/dev/null 2>&1; then
            git remote set-url origin "${GIT_REMOTE_URL}"
        else
            git remote add origin "${GIT_REMOTE_URL}"
        fi

        echo "Configured Git remote:"
        git remote -v

    else
        echo "No GIT_REMOTE_URL provided."
        echo "Leaving existing Git remote unchanged."
    fi

fi

section_end "Configure Git platform mode"

###############################################################
# Create Helper Commands and User Environment Utilities
#
# Purpose:
# - Install operational helper commands for troubleshooting
# - Provide a reusable lab environment activation workflow
# - Improve usability for repeatable automation tasks
# - Configure persistent shell functions for the cisco user
#
# Components:
# - bootstrap-status : View bootstrap logs and status
# - enter-lab        : Activate the PROJECT AUTOCOR lab environment
# - exit-lab         : Exit the active lab environment
# - /etc/motd        : Display platform usage guidance on login
###############################################################

echo "Creating helper commands..."

###############################################################
# Create bootstrap-status helper
#
# Purpose:
# - Provide quick visibility into bootstrap state
# - Show recent bootstrap log output for troubleshooting
###############################################################

cat >/usr/local/bin/bootstrap-status <<'EOF'
#!/usr/bin/env bash
echo "===== BOOTSTRAP STATUS ====="
cat /var/log/automation-bootstrap.status 2>/dev/null || echo "No status file found."
echo
echo "===== LAST 40 LOG LINES ====="
tail -n 40 /var/log/automation-bootstrap.log 2>/dev/null || echo "No log file found."
EOF
chmod +x /usr/local/bin/bootstrap-status

###############################################################
# Create persistent lab environment shell functions
#
# Purpose:
# - Allow users to quickly enter the automation workspace
# - Automatically activate the Python virtual environment
# - Provide a custom shell prompt for lab sessions
# - Validate Docker access and repo availability
#
# Location:
# - /etc/profile.d/labenv.sh
#
# Behavior:
# - Functions automatically become available on login
# - enter-lab activates the environment
# - exit-lab restores the default shell state
###############################################################

sudo tee /etc/profile.d/labenv.sh >/dev/null <<'EOF'
# ============================================================
# Lab Environment Functions
# ============================================================

enter-lab() {

  # Prevent root usage
  if [[ "$EUID" -eq 0 ]]; then
    echo "❌ Do not run enter-lab as root."
    echo "👉 Use the cisco user instead."
    return 1
  fi

  local LAB_DIR="/opt/labrepo"

  # Validate repo path
  if [[ ! -d "$LAB_DIR" ]]; then
    echo "❌ Lab directory not found:"
    echo "   $LAB_DIR"
    return 1
  fi

  cd "$LAB_DIR" || {
    echo "❌ Failed to enter $LAB_DIR"
    return 1
  }

  # Validate venv exists
  if [[ ! -f ".venv/bin/activate" ]]; then
    echo "❌ Virtual environment missing:"
    echo "   $LAB_DIR/.venv"
    return 1
  fi

  # Activate venv
  source .venv/bin/activate

  # Detect git branch
  local BRANCH="no-git"

  if command -v git &>/dev/null &&
     git rev-parse --is-inside-work-tree &>/dev/null; then

    BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  fi

  # Custom prompt
  export LAB_ENV_NAME="labenv:${BRANCH}"
  export PS1="(${LAB_ENV_NAME}) \u@\h:\w\$ "

  echo "✅ Lab environment activated"
  echo "   Env: $LAB_ENV_NAME"
  echo "   Python: $(which python)"
  echo "   Ansible: $(which ansible)"

  # Docker permission validation
  if docker ps &>/dev/null; then
    echo "   Docker: ✅ access OK"
  else
    echo "   Docker: ❌ permission issue"
    echo "   👉 Ensure user is in docker group"
  fi

  echo ""
  echo "👉 Available commands:"
  echo "   lab help"
  echo "   lab check"
  echo "   exit-lab"
}

# ============================================================
# Exit lab environment
# ============================================================

exit-lab() {

  deactivate 2>/dev/null || true

  unset LAB_ENV_NAME

  export PS1="\u@\h:\w\$ "

  cd ~ || return 1

  echo "Exited lab environment"
}
EOF

chmod 644 /etc/profile.d/labenv.sh

###############################################################
# Configure login MOTD
#
# Purpose:
# - Display operational guidance after login
# - Provide quick-reference platform commands
# - Improve usability for new lab users
###############################################################

cat >/etc/motd <<'EOF'
============================================================
      PROJECT AUTOCOR - Automation Host
============================================================

Lab Environment
------------------------------
  enter-lab              Activate lab environment
  exit-lab               Exit lab environment

Platform Operations
------------------------------
  lab help               Show available lab commands
  lab check              Validate environment health
  lab run <playbook>     Run Ansible playbook
  lab logs               Show recent automation runs
  lab last               Show latest run directory

Validation
------------------------------
  docker version         Check Docker daemon connectivity
  docker ps              Verify Docker access (no sudo)
  ansible --version      Verify Ansible environment

Optional Local GitLab
------------------------------
  validate-gitlab-lab    Validate local GitLab container if installed
  docker logs gitlab     View local GitLab startup logs if installed

Bootstrap / Recovery
------------------------------
  bootstrap-status       View bootstrap logs and status

Environment Notes
------------------------------
  - Use enter-lab before running automation commands
  - Docker runs without sudo for cisco user
  - Artifacts stored under:
      /opt/labrepo/artifacts/

============================================================
EOF

###############################################################
# Finalize bootstrap state
#
# Purpose:
# - Mark bootstrap completion
# - Persist successful bootstrap state
# - Prevent bootstrap reruns on future boots
###############################################################

touch "${MARKER_FILE}"

BOOTSTRAP_END_EPOCH=$(date +%s)
BOOTSTRAP_DURATION=$((BOOTSTRAP_END_EPOCH - BOOTSTRAP_START_EPOCH))

echo "BOOTSTRAP_STATE=completed" > "$STATUS_FILE"
echo "BOOTSTRAP_COMPLETED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
echo "BOOTSTRAP_DURATION_SECONDS=${BOOTSTRAP_DURATION}" >> "$STATUS_FILE"

echo "Bootstrap complete."
echo
echo "Bootstrap completed in ${BOOTSTRAP_DURATION} seconds."