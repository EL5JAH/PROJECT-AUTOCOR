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