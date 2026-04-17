#!/usr/bin/env bash
set -euo pipefail

###############################################################
# setup_local_secrets.sh
#
# Purpose:
# - Create the local, untracked secret file used by the Ansible
#   runner and vault helper
# - Prompt the operator securely for the Ansible Vault password
# - Store the password outside the repo with restrictive permissions
#
# What this script creates:
# - /home/cisco/.ansible/.vault_env
#
# Why this exists:
# - bootstrap installs the vault helper mechanism
# - this script injects the actual local secret value afterward
# - the secret is never stored in the repo
#
# When to run:
# - once per automation host
# - after bootstrap
# - before the first Ansible run
#
# Example:
#   cd /opt/labrepo
#   ./scripts/setup_local_secrets.sh
###############################################################

# Directory and file used by the local vault environment.
ANSIBLE_LOCAL_DIR="/home/cisco/.ansible"
VAULT_ENV_FILE="${ANSIBLE_LOCAL_DIR}/.vault_env"
# Resolve repo root dynamically
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

###############################################################
# Basic sanity checks
###############################################################

# This script is intended to be run as the cisco user on the
# automation host. Failing early here avoids creating files
# under the wrong account.
if [[ "$(whoami)" != "cisco" ]]; then
  echo "ERROR: run this script as the cisco user." >&2
  exit 1
fi

###############################################################
# Create the local .ansible directory if needed
###############################################################
mkdir -p "${ANSIBLE_LOCAL_DIR}"

# Restrict directory access so only the cisco user can access it.
chmod 700 "${ANSIBLE_LOCAL_DIR}"

###############################################################
# Handle existing secret file
###############################################################
if [[ -f "${VAULT_ENV_FILE}" ]]; then
  echo "A local vault environment file already exists:"
  echo "  ${VAULT_ENV_FILE}"
  echo

  read -r -p "Overwrite it? [y/N]: " OVERWRITE_REPLY

  case "${OVERWRITE_REPLY}" in
    y|Y|yes|YES)
      ;;
    *)
      echo "No changes made."
      exit 0
      ;;
  esac
fi

###############################################################
# Prompt securely for the vault password
#
# - -s prevents the password from being echoed to the terminal
# - We ask twice to prevent accidental typos
###############################################################
read -r -s -p "Enter Ansible Vault password: " VAULT_PASSWORD_1
echo
read -r -s -p "Confirm Ansible Vault password: " VAULT_PASSWORD_2
echo

###############################################################
# Validate the entered values
###############################################################
if [[ -z "${VAULT_PASSWORD_1}" ]]; then
  echo "ERROR: vault password cannot be empty." >&2
  exit 1
fi

if [[ "${VAULT_PASSWORD_1}" != "${VAULT_PASSWORD_2}" ]]; then
  echo "ERROR: passwords did not match." >&2
  exit 1
fi

###############################################################
# Write the local environment file
#
# Important:
# - Use printf instead of echo for predictable output
# - Quote the value so the runner can safely source the file
# - Do not print the password to the terminal
###############################################################
cat > "${VAULT_ENV_FILE}" <<EOF
export ANSIBLE_VAULT_PASSWORD='${VAULT_PASSWORD_1}'
EOF

# Restrict file access to the cisco user only.
chmod 600 "${VAULT_ENV_FILE}"

###############################################################
# Clear sensitive variables from the current shell process
#
# This does not scrub memory perfectly, but it prevents accidental
# reuse later in the script and is still good hygiene.
###############################################################
unset VAULT_PASSWORD_1
unset VAULT_PASSWORD_2

###############################################################
# Create local iosxe group_vars (device credentials)
###############################################################

GROUP_VARS_DIR="${REPO_ROOT}/ansible/inventory/group_vars"
IOSXE_VARS_FILE="${GROUP_VARS_DIR}/iosxe.yml"
# Track whether we created/overwrote the file
IOSXE_CREATED=false

mkdir -p "${GROUP_VARS_DIR}"
chmod 700 "${GROUP_VARS_DIR}"

confirm_overwrite() {
    local target_file="$1"

    if [[ -e "${target_file}" ]]; then
        read -r -p "File exists: ${target_file}. Overwrite? [y/N]: " reply
        case "${reply}" in
            y|Y|yes|YES) ;;
            *) 
                echo "Skipping iosxe.yml creation."
                return 1
                ;;
        esac
    fi
    return 0
}

prompt_secret() {
    local prompt_text="$1"
    local val1=""
    local val2=""

    while true; do
        read -r -s -p "${prompt_text}: " val1
        echo
        read -r -s -p "Confirm ${prompt_text}: " val2
        echo

        if [[ "${val1}" != "${val2}" ]]; then
            echo "Values did not match. Try again."
            continue
        fi

        [[ -z "${val1}" ]] && echo "Value cannot be empty." && continue

        printf '%s' "${val1}"
        return 0
    done
}

prompt_value() {
    local prompt_text="$1"
    local val=""

    while true; do
        read -r -p "${prompt_text}: " val
        [[ -z "${val}" ]] && echo "Value cannot be empty." && continue
        printf '%s' "${val}"
        return 0
    done
}

echo
echo "Setting up local iosxe credentials..."

DEVICE_USERNAME="$(prompt_value "Device username")"
DEVICE_PASSWORD="$(prompt_secret "Device login password")"
ENABLE_PASSWORD="$(prompt_secret "Device enable password")"

if confirm_overwrite "${IOSXE_VARS_FILE}"; then
    cat > "${IOSXE_VARS_FILE}" <<EOF
---
ansible_user: '${DEVICE_USERNAME}'
ansible_password: '${DEVICE_PASSWORD}'
ansible_become_password: '${ENABLE_PASSWORD}'
EOF

    chmod 600 "${IOSXE_VARS_FILE}"
    IOSXE_CREATED=true
    echo "Created ${IOSXE_VARS_FILE}"
fi

###############################################################
# Final success message
###############################################################
echo "Local secrets configured successfully:"
echo
echo "Vault environment file:"
echo "  ${VAULT_ENV_FILE}"
echo
echo "IOSXE group vars file:"
if [[ "${IOSXE_CREATED}" == true ]]; then
  echo "  ${IOSXE_VARS_FILE}"
else
  echo "  (unchanged)"
fi
echo
echo "Permissions set:"
echo "  directory: ${ANSIBLE_LOCAL_DIR} (700)"
echo "  vault env: ${VAULT_ENV_FILE} (600)"
echo "  group vars: ${IOSXE_VARS_FILE} (600)"
echo
echo "Validation steps:"
echo "  source ${VAULT_ENV_FILE}"
echo "  ANSIBLE_CONFIG=${REPO_ROOT}/ansible/ansible.cfg \\"
echo "  ansible-inventory -i ${REPO_ROOT}/ansible/inventory/hosts.yaml --host cat8k-1"
echo
echo "You can now run Ansible normally, for example:"
echo "  ./scripts/run_ansible.sh playbooks/playbook1.yaml -t validate"