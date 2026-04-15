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
# Final success message
###############################################################
echo "Local vault environment file created successfully:"
echo "  ${VAULT_ENV_FILE}"
echo
echo "Permissions set:"
echo "  directory: ${ANSIBLE_LOCAL_DIR} (700)"
echo "  file     : ${VAULT_ENV_FILE} (600)"
echo
echo "You can now run Ansible normally, for example:"
echo "  ./scripts/run_ansible.sh playbooks/playbook1.yaml -t validate"