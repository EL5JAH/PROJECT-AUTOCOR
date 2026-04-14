#!/usr/bin/env bash
set -euo pipefail

###############################################################
# run_ansible.sh
#
# Purpose:
# Standardized wrapper for running Ansible playbooks from this repo.
#
# What it does:
# - Resolves the repo root automatically
# - Forces use of this project's ansible.cfg
# - Creates a timestamped run directory for logs/artifacts
# - Saves full console output for later review
# - Accepts either a playbook path or ad-hoc ansible arguments
#
# Examples:
#   ./ansible/run_ansible.sh playbooks/playbook1.yaml
#   ./ansible/run_ansible.sh playbooks/playbook1.yaml -l cat8k-1
#   ./ansible/run_ansible.sh playbooks/playbook1.yaml -t validate
#   ./ansible/run_ansible.sh --adhoc iosxe -m ansible.netcommon.cli_command -a "command=show version"
###############################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="${SCRIPT_DIR}"
REPO_ROOT="$(cd "${ANSIBLE_DIR}/.." && pwd)"

# Project config and inventory paths
ANSIBLE_CONFIG_FILE="${ANSIBLE_DIR}/ansible.cfg"
INVENTORY_FILE="${ANSIBLE_DIR}/inventory/hosts.yml"

# Timestamped artifact directory for this execution
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RUNS_DIR="${REPO_ROOT}/artifacts/ansible-runs"
RUN_DIR="${RUNS_DIR}/${TIMESTAMP}"
LOG_FILE="${RUN_DIR}/console.log"
META_FILE="${RUN_DIR}/run_meta.txt"

mkdir -p "${RUN_DIR}"

###############################################################
# Export project-local Ansible config
#
# This ensures Ansible uses the repo's ansible.cfg even if the
# user launches the script from another directory.
###############################################################
export ANSIBLE_CONFIG="${ANSIBLE_CONFIG_FILE}"

###############################################################
# NEW: Vault helper and optional environment file paths
#
# Purpose:
# - Validate that the executable vault helper created by bootstrap
#   exists before Ansible is launched
# - Optionally auto-load ANSIBLE_VAULT_PASSWORD from a local file
#   that is NOT stored in the repo
#
# Notes:
# - VAULT_HELPER should match the path configured in ansible.cfg
# - VAULT_ENV_FILE is optional and intended for lab convenience
# - The env file should contain a line like:
#     export ANSIBLE_VAULT_PASSWORD='your-password'
###############################################################
VAULT_HELPER="/home/cisco/.ansible/get_vault_pass.sh"
VAULT_ENV_FILE="/home/cisco/.ansible/.vault_env"

###############################################################
# Basic validation
###############################################################
if [[ ! -f "${ANSIBLE_CONFIG_FILE}" ]]; then
  echo "ERROR: ansible.cfg not found at ${ANSIBLE_CONFIG_FILE}" >&2
  exit 1
fi

if [[ ! -f "${INVENTORY_FILE}" ]]; then
  echo "ERROR: inventory file not found at ${INVENTORY_FILE}" >&2
  exit 1
fi

###############################################################
# NEW: Validate vault helper script exists
#
# Why this check exists:
# - ansible.cfg now points vault_password_file to an executable
#   helper script instead of a plaintext password file
# - If bootstrap did not create the helper, Ansible would fail later
# - This fails early with a clearer message
###############################################################
if [[ ! -f "${VAULT_HELPER}" ]]; then
  echo "ERROR: vault helper script not found at ${VAULT_HELPER}" >&2
  echo "ERROR: bootstrap is incomplete or the helper path is incorrect." >&2
  exit 1
fi

###############################################################
# NEW: Auto-load ANSIBLE_VAULT_PASSWORD if not already set
#
# Load order:
# 1) If ANSIBLE_VAULT_PASSWORD is already exported in the shell,
#    leave it alone
# 2) Otherwise, if /home/cisco/.ansible/.vault_env exists, source it
# 3) If the variable is still missing, fail with a clear message
#
# Why source a file:
# - This avoids hardcoding the password in the repo
# - This avoids requiring the user to export it manually every time
# - The file remains outside the repo and can be ignored by Git
#
# Important:
# - The env file should be readable only by the cisco user
# - The env file should not be echoed or logged
###############################################################
VAULT_ENV_SOURCE="pre-set"

if [[ -z "${ANSIBLE_VAULT_PASSWORD:-}" ]]; then
  if [[ -f "${VAULT_ENV_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${VAULT_ENV_FILE}"
    VAULT_ENV_SOURCE="loaded_from_file"
  else
    VAULT_ENV_SOURCE="missing"
  fi
fi

###############################################################
# NEW: Fail clearly if the vault password is still unavailable
#
# This check protects the helper script path from failing later with
# a less obvious error. The runner explains exactly what is missing.
###############################################################
if [[ -z "${ANSIBLE_VAULT_PASSWORD:-}" ]]; then
  echo "ERROR: ANSIBLE_VAULT_PASSWORD is not set." >&2
  echo "ERROR: Export it in your shell or create ${VAULT_ENV_FILE}." >&2
  echo "ERROR: Example content for ${VAULT_ENV_FILE}:" >&2
  echo "ERROR:   export ANSIBLE_VAULT_PASSWORD='your-password'" >&2
  exit 1
fi

if [[ $# -lt 1 ]]; then
  cat <<'EOF'
Usage:
  ./ansible/run_ansible.sh <playbook_path> [additional ansible-playbook args...]
  ./ansible/run_ansible.sh --adhoc <pattern> [ansible args...]

Examples:
  ./ansible/run_ansible.sh playbooks/playbook1.yaml
  ./ansible/run_ansible.sh playbooks/playbook1.yaml -l cat8k-1
  ./ansible/run_ansible.sh playbooks/playbook1.yaml -t validate
  ./ansible/run_ansible.sh --adhoc iosxe -m ansible.netcommon.cli_command -a "command=show ip int brief"
EOF
  exit 1
fi

###############################################################
# Record metadata for traceability
###############################################################
{
  echo "timestamp=${TIMESTAMP}"
  echo "repo_root=${REPO_ROOT}"
  echo "ansible_dir=${ANSIBLE_DIR}"
  echo "ansible_config=${ANSIBLE_CONFIG_FILE}"
  echo "inventory=${INVENTORY_FILE}"
  echo "vault_helper=${VAULT_HELPER}"
  echo "vault_env_file=${VAULT_ENV_FILE}"
  echo "vault_env_source=${VAULT_ENV_SOURCE}"
  echo "cwd=$(pwd)"
  echo "user=$(whoami)"
  echo "command=$*"
} > "${META_FILE}"

###############################################################
# Show a concise execution banner to the terminal
###############################################################
echo "============================================================"
echo "Ansible run starting"
echo "Config    : ${ANSIBLE_CONFIG_FILE}"
echo "Inventory : ${INVENTORY_FILE}"
echo "Run dir   : ${RUN_DIR}"
echo "Log file  : ${LOG_FILE}"
echo "Vault src : ${VAULT_ENV_SOURCE}"
echo "============================================================"

###############################################################
# Support two modes:
#
# 1) Playbook mode
#    ./run_ansible.sh playbooks/site.yaml -l cat8k-1
#
# 2) Ad-hoc mode
#    ./run_ansible.sh --adhoc iosxe -m ping
###############################################################
if [[ "${1}" == "--adhoc" ]]; then
  shift

  if [[ $# -lt 1 ]]; then
    echo "ERROR: --adhoc requires a host pattern." >&2
    exit 1
  fi

  HOST_PATTERN="$1"
  shift

  set +e
  ansible "${HOST_PATTERN}" -i "${INVENTORY_FILE}" "$@" 2>&1 | tee "${LOG_FILE}"
  RC=${PIPESTATUS[0]}
  set -e
else
  PLAYBOOK_INPUT="$1"
  shift

  # Allow either:
  # - relative to ansible/ directory, e.g. playbooks/playbook1.yaml
  # - absolute path
  if [[ "${PLAYBOOK_INPUT}" = /* ]]; then
    PLAYBOOK_FILE="${PLAYBOOK_INPUT}"
  else
    PLAYBOOK_FILE="${ANSIBLE_DIR}/${PLAYBOOK_INPUT}"
  fi

  if [[ ! -f "${PLAYBOOK_FILE}" ]]; then
    echo "ERROR: playbook not found at ${PLAYBOOK_FILE}" >&2
    exit 1
  fi

  set +e
  ansible-playbook -i "${INVENTORY_FILE}" "${PLAYBOOK_FILE}" "$@" 2>&1 | tee "${LOG_FILE}"
  RC=${PIPESTATUS[0]}
  set -e
fi

###############################################################
# Persist exit code and finish cleanly
###############################################################
echo "exit_code=${RC}" >> "${META_FILE}"

if [[ ${RC} -eq 0 ]]; then
  echo "Run completed successfully."
else
  echo "Run failed with exit code ${RC}."
fi

exit "${RC}"