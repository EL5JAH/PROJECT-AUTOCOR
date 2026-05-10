#!/usr/bin/env bash
set -euo pipefail

LAB_USER="${LAB_USER:-cisco}"
SSH_DIR="/home/${LAB_USER}/.ssh"
KEY_PATH="${SSH_DIR}/gitlab_lab_ed25519"
GITLAB_HOST="${GITLAB_HOST:-$(hostname -I | awk '{print $1}')}"
GITLAB_SSH_PORT="${GITLAB_SSH_PORT:-2222}"

echo "Preparing SSH directory..."
sudo install -d -m 700 -o "$LAB_USER" -g "$LAB_USER" "$SSH_DIR"

if [ ! -f "$KEY_PATH" ]; then
  echo "Generating GitLab lab SSH key..."
  sudo -u "$LAB_USER" ssh-keygen -t ed25519 -N "" \
    -C "${LAB_USER}@portable-devops-lab" \
    -f "$KEY_PATH"
else
  echo "GitLab lab SSH key already exists."
fi

echo "Adding GitLab SSH endpoint to known_hosts..."
sudo -u "$LAB_USER" ssh-keyscan -p "$GITLAB_SSH_PORT" "$GITLAB_HOST" \
  >> "${SSH_DIR}/known_hosts" 2>/dev/null || true

sudo chown "$LAB_USER:$LAB_USER" "${SSH_DIR}/known_hosts"
sudo chmod 644 "${SSH_DIR}/known_hosts"

cat > /tmp/gitlab_ssh_config <<EOF
Host gitlab-lab
  HostName ${GITLAB_HOST}
  Port ${GITLAB_SSH_PORT}
  User git
  IdentityFile ~/.ssh/gitlab_lab_ed25519
  IdentitiesOnly yes
  StrictHostKeyChecking yes
EOF

sudo install -m 600 -o "$LAB_USER" -g "$LAB_USER" /tmp/gitlab_ssh_config "${SSH_DIR}/config"
rm -f /tmp/gitlab_ssh_config

echo "GitLab SSH key generated:"
sudo cat "${KEY_PATH}.pub"