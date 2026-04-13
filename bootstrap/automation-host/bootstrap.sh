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
                apt-get update -y
                apt-get install -y \
                    git \
                    python3 \
                    python3-pip \
                    python3-venv \
                    curl \
                    jq \
                    net-tools \
                    iputils-ping \
                    traceroute

                mkdir -p /opt/bootstrap
                mkdir -p /opt

                echo "Preparing repo directory..."

                if [[ -d "${REPO_DIR}" ]]; then
                    echo "Removing existing repo directory..."
                    rm -rf "${REPO_DIR}"
                fi

                echo "Cloning repo from ${REPO_URL} ..."
                if ! git clone "${REPO_URL}" "${REPO_DIR}"; then
                    echo "Bootstrap failed: git clone failed."
                    echo "BOOTSTRAP_STATE=failed_git_clone" > "$STATUS_FILE"
                    echo "BOOTSTRAP_FAILED_AT=$(date -Iseconds)" >> "$STATUS_FILE"
                    exit 1
                fi

                cd "${REPO_DIR}"
                git checkout test-baseline_validate
                git status

                echo "Creating Python virtual environment..."
                python3 -m venv .venv

                echo "Installing Python requirements..."
                source .venv/bin/activate
                pip install --upgrade pip
                pip install -r requirements.txt

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

                Useful commands:
                  bootstrap-status   Show bootstrap status and recent log lines
                  labenv             Enter /opt/labrepo with the Python venv activated

                Log files:
                  /var/log/automation-bootstrap.log
                  /var/log/automation-bootstrap.status
                EOF

                echo "Bootstrap complete."