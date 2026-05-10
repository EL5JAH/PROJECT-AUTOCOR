#!/usr/bin/env bash
set -euo pipefail

GITLAB_DIR="/opt/labrepo/gitlab"
GITLAB_HOME="/srv/gitlab"
GITLAB_HOSTNAME="${GITLAB_HOSTNAME:-$(hostname -I | awk '{print $1}')}"

echo "Preparing GitLab persistent directories..."
sudo mkdir -p "$GITLAB_HOME/config" "$GITLAB_HOME/logs" "$GITLAB_HOME/data"

echo "Writing GitLab environment file..."
cat > "$GITLAB_DIR/.env" <<EOF
GITLAB_HOSTNAME=$GITLAB_HOSTNAME
EOF

echo "Starting GitLab CE container..."
cd "$GITLAB_DIR"
sudo docker compose up -d

echo "GitLab container started."
echo "Web URL: http://${GITLAB_HOSTNAME}:8080"
echo "SSH URL format: ssh://git@${GITLAB_HOSTNAME}:2222/root/project.git"