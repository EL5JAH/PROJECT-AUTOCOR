# Changelog

All notable changes to this project will be documented in this file.

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
