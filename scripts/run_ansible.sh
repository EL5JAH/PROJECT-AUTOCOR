#!/usr/bin/env bash

# Exit immediately if:
# - any command fails (-e)
# - an undefined variable is used (-u)
# - any command in a pipeline fails (-o pipefail)
# This ensures the script fails fast and avoids silent errors.
set -euo pipefail

# ---------------------------------------------------------
# Resolve repository root directory
# ---------------------------------------------------------
# This dynamically determines the repo root regardless of
# where the script is executed from.
#
# BASH_SOURCE[0] -> current script path
# dirname         -> directory of the script
# /..             -> move one level up (repo root)
# pwd             -> resolve absolute path
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------------------------------------------------------
# Generate timestamp for this run
# ---------------------------------------------------------
# Format: YYYYMMDD-HHMMSS (sortable and unique)
# Used to create isolated run directories for logs/artifacts
TIMESTAMP="$(date +"%Y%m%d-%H%M%S")"

# ---------------------------------------------------------
# Define run-specific directories
# ---------------------------------------------------------
# Each execution gets its own directory to:
# - prevent log overwrites
# - support debugging and auditing
# - allow historical comparisons between runs
RUN_DIR="${REPO_ROOT}/artifacts/runs/${TIMESTAMP}"
LOG_DIR="${RUN_DIR}/logs"

# Create directory structure if it does not exist
mkdir -p "${LOG_DIR}"

# ---------------------------------------------------------
# Configure Ansible logging
# ---------------------------------------------------------
# ANSIBLE_LOG_PATH directs Ansible to write logs to a file
# instead of only stdout.
#
# This is critical for:
# - CI/CD pipelines
# - troubleshooting failed runs
# - preserving execution history
export ANSIBLE_LOG_PATH="${LOG_DIR}/ansible.log"

# ---------------------------------------------------------
# Execute Ansible Playbook
# ---------------------------------------------------------
# -i : Inventory file defining managed hosts
# baseline.yml : Playbook to apply baseline configuration
#
# Paths are constructed dynamically using REPO_ROOT to ensure
# portability across environments (local, CI runner, etc.)
ansible-playbook \
  -i "${REPO_ROOT}/ansible/inventory/hosts.yml" \
  "${REPO_ROOT}/ansible/playbooks/baseline.yml"