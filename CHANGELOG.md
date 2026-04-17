# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] - Zero-touch automation-host provisioning and secret management hardening - 2026-04-17

### Added

- Extended `scripts/setup_local_secrets.sh` to provision local `ansible/group_vars/iosxe.yml` for device authentication
- Added secure prompts for device username, login password, and enable password
- Added creation of local-only IOS XE Ansible credential vars outside tracked repo content
- Added validation guidance in the script success output for checking resolved inventory variables
- Added vault environment auto-loading in `run_ansible.sh` from `~/.ansible/.vault_env`
- Added early validation for `ANSIBLE_VAULT_PASSWORD` so Ansible runs fail fast with a clear message before vault helper execution
- Added automatic execute-permission handling for repo shell scripts during bootstrap to reduce post-build manual setup

### Changed

- Updated the local secret setup success message to report both `.vault_env` and `iosxe.yml`
- Improved local secret setup flow to better support zero-touch Ansible runs on freshly bootstrapped automation hosts
- Updated bootstrap cloning flow to run repository operations as the `cisco` user instead of root
- Updated virtual environment creation and related repo operations to preserve consistent `cisco` ownership
- Improved bootstrap reliability by adding retry logic and fail-fast handling for `apt-get update`

### Fixed

- Resolved Ansible authentication failures caused by missing local `group_vars/iosxe.yml` on hosts cloned from the public repo
- Clarified the separation between vault password loading and device credential provisioning in the local secret workflow
- Fixed bootstrap permission issues that led to Git ownership and virtual environment access problems
- Fixed bootstrap script execution readiness so `/scripts` content no longer requires manual `chmod`
- Fixed a bootstrap syntax error caused by a missing `fi` in the script-permissions block

## [0.4.0] - Security & Execution Model Overhaul - 2026-04-14

### Added

- Added `scripts/setup_local_secrets.sh` for secure, one-time vault password initialization
- Added dynamic vault password helper (`get_vault_pass.sh`) for runtime retrieval
- Added optional local environment file (`~/.ansible/.vault_env`) for zero-touch execution
- Added automatic environment variable loading in `run_ansible.sh`
- Added validation checks for vault helper presence and required environment variables
- Added vault source tracking (`pre-set` vs `loaded_from_file`) in run metadata
- Added bootstrap provisioning of `.ansible` directory with secure permissions

### Changed

- Refactored vault handling to use runtime environment variables instead of static password files
- Updated `ansible.cfg` to use executable vault helper script
- Updated `run_ansible.sh`:
  - Correct repo root resolution from `scripts/`
  - Proper `ansible.cfg` discovery
  - Improved error handling and execution flow
- Standardized execution path: `./scripts/run_ansible.sh`
- Removed dependency on `~/.ansible/.vault_pass.txt`

### Security

- Eliminated plaintext vault password file storage
- Ensured vault password is never exposed in logs or console output
- Enforced strict permissions:
  - `.ansible/` → `700`
  - Helper scripts → `700`
- Updated `.gitignore` to exclude all local secret artifacts

### ⚠️ Important Changes

- Vault password must now be provided via environment variable:
  - ANSIBLE_VAULT_PASSWORD
- For automated runs, the variable can be sourced from:
  - ~/.ansible/.vault_env
- Ansible retrieves the vault password via an executable helper script at runtime, which must output only the password

## [0.3.0] - Automation maturity milestone: secure credentials, execution wrapper, and SSH compatibility - 2026-04-13

### Added

- Added `run_ansible.sh` wrapper to standardize Ansible execution across the project
- Implemented timestamped artifact directories under `artifacts/ansible-runs/` for each run
- Added persistent logging (`console.log`) and execution metadata (`run_meta.txt`) for traceability
- Enabled support for both playbook execution and ad-hoc Ansible commands via a unified interface
- Added secure credential storage using Ansible Vault (`group_vars/iosxe.yml`).
- Added automated vault password handling via `~/.ansible/.vault_pass`.
- Enabled non-interactive Ansible runs with `vault_password_file` configuration.
- Added scoped SSH compatibility settings for legacy IOSv devices.

### Changed

- Centralized Ansible execution through `run_ansible.sh` to ensure consistent use of `ansible.cfg` and inventory
- Improved reproducibility and portability of automation workflows by eliminating dependency on user execution context
- Moved credentials from inventory into `group_vars` for proper variable resolution.
- Updated `ansible.cfg` with standardized defaults for inventory, vault handling, and connection behavior.
- Enabled SSH pipelining to improve execution performance.

### Fixed

- Fixed missing credential issue where Ansible was not authenticating to devices.
- Restored SSH connectivity to legacy IOSv devices by enabling compatible key exchange and RSA algorithms.
- Prevented global weakening of SSH security by scoping legacy crypto settings to specific hosts only.

### Security

- Ensured vault integration remains transparent during automated runs by leveraging configured `vault_password_file`
- Removed plaintext credentials from repository-tracked files.
- Encrypted all sensitive variables using Ansible Vault.
- Restricted vault password file permissions (`chmod 600`).

## [0.2.0] - Foundation milestone: CML lab, bootstrap, ansible baseline - 2026-04-13

### Added

- Automation host bootstrapping via `bootstrap.sh` and `automation-bootstrap.service`
- Baseline `ansible.cfg` for standardized automation behavior
- Ansible dependencies added to `requirements.txt`
- `run_ansible.sh` wrapper for timestamped execution and structured logging

- Introduced environment-specific lab directories:
  - `cml/labs/homelab`
  - `cml/labs/sandbox`

### Changed

- Converted distribution switches from iosvl2 to iosv to enable Layer 3 functionality
- Updated routing configuration to support multilayer switching design
- Standardized automation-host networking with static IP addressing

- Refactored validation framework:
  - Extracted network logic into `network_helpers.py`
  - Centralized file/artifact handling in `file_helpers.py`
  - Simplified `baseline_validate.py` into orchestration layer
- Reorganized lab structure by moving base lab to `cml/labs/`

### Fixed

- Corrected `.gitignore` to properly exclude sensitive files while tracking inventory structure
  - allow `hosts.yml` for reproducibility
  - ignore `group_vars` and `host_vars`
  - enforce vault file exclusion
  - ignore local virtual environments

- Resolved CML sandbox import failures by removing unsupported YAML fields:
  - `mac_address`
  - `annotations`
  - `smart_annotations`
- Normalized YAML formatting using block-style (`|`) for device configs

## [0.1.0] - Initial Foundation

### Added

- Base CML lab topology
- Baseline validation script
- Expected state definition
- Artifact logging structure
- Version tracking (VERSION)
- Metadata tracking (meta.txt)
