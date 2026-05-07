#!/usr/bin/env bash
set -euo pipefail

GITLAB_HOST="${GITLAB_HOST:-$(hostname -I | awk '{print $1}')}"
GITLAB_WEB_PORT="${GITLAB_WEB_PORT:-8080}"
GITLAB_SSH_PORT="${GITLAB_SSH_PORT:-2222}"
LAB_USER="${LAB_USER:-cisco}"

echo "Validating portable DevOps lab..."

failures=0

check() {
  local name="$1"
  shift

  if "$@"; then
    echo "✅ $name"
  else
    echo "❌ $name"
    failures=$((failures + 1))
  fi
}

check "Docker is available" docker version
check "GitLab container exists" docker ps --format '{{.Names}}' | grep -q '^gitlab$'
check "GitLab web port is listening" bash -c "curl -fsS http://${GITLAB_HOST}:${GITLAB_WEB_PORT}/-/health >/dev/null"
check "GitLab SSH port is listening" bash -c "nc -z ${GITLAB_HOST} ${GITLAB_SSH_PORT}"
check "Lab SSH private key exists" test -f "/home/${LAB_USER}/.ssh/gitlab_lab_ed25519"
check "Lab SSH public key exists" test -f "/home/${LAB_USER}/.ssh/gitlab_lab_ed25519.pub"

echo
echo "GitLab URL:"
echo "  http://${GITLAB_HOST}:${GITLAB_WEB_PORT}"
echo
echo "Git SSH alias:"
echo "  gitlab-lab"
echo
echo "Public key to add to GitLab:"
cat "/home/${LAB_USER}/.ssh/gitlab_lab_ed25519.pub"

if [ "$failures" -gt 0 ]; then
  echo
  echo "Validation completed with ${failures} issue(s)."
  exit 1
fi

echo
echo "✅ GitLab lab validation passed."