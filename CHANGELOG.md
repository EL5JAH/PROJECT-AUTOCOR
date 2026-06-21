# Changelog

All notable changes to this project will be documented in this file.

## [0.8.3] - Documentation Overhaul and Bootstrap Instrumentation - 2026-06-21

### Documentation

- Rewrote README to reflect current platform architecture
- Added docs/QUICKSTART.md
- Added docs/ARCHITECTURE.md
- Documented automation host, Ansible, pyATS, artifacts, and topology

### Bootstrap

- Added section_start/section_end timing to pyATS Docker installation
- Improved bootstrap execution visibility
- Improved section-level performance tracking

## [0.8.2] - pyATS Runtime Permission Hardening - 2026-05-10

### Added

- Added persistent `/opt/labrepo/pyats` workspace creation during bootstrap
- Added pyATS artifact directory initialization under `/opt/labrepo/artifacts/pyats-runs`
- Added ownership and permission enforcement for pyATS runtime directories
- Added writable directory validation checks to the `run-pyats` wrapper
- Added improved pyATS runtime logging for workspace, artifact, and repository mount visibility
- Added automatic timestamped pyATS run directory creation

### Changed

- Updated `run-pyats` to use structured Docker bind mounts for:
  - persistent pyATS workspace storage
  - timestamped artifact collection
  - repository workspace access
- Hardened pyATS container initialization against permission-related failures caused by root-owned bind mount paths

## [0.8.1] - Bootstrap Section Timing Instrumentation - 2026-05-10

### Added

- Added `section_start` timestamp logging to major bootstrap workflow sections
- Added `section_end` timestamp logging to major bootstrap workflow sections
- Added standardized runtime instrumentation for bootstrap phase duration tracking
- Improved bootstrap observability for provisioning performance analysis and troubleshooting
- Prepared bootstrap workflow for future optimization benchmarking and timing comparisons

## [0.8.0] - pyATS Container Runtime & Repository Platform Structure - 2026-05-09

### Added

- Added containerized pyATS runtime support to automation-host bootstrap
- Added automatic Cisco pyATS Docker image pull during provisioning
- Added pyATS runtime directories for testbeds, jobs, tests, and reports
- Added dedicated pyATS platform structure:
  - `pyats/docker/`
  - `pyats/jobs/`
  - `pyats/testbeds/`
  - `pyats/tests/`
- Added pyATS Docker build and compose definitions
- Added pyATS baseline validation job
- Added initial pyATS validation test suite:
  - `test_connectivity.py`
  - `test_interfaces.py`
  - `test_ospf.py`
  - `test_vlan.py`
- Added pyATS testbed definitions for:
  - `sandbox.yml`
  - `homelab.yml`
- Added timestamped pyATS artifact directory structure under:
  - `artifacts/pyats-runs/`
- Added `run_pyats.sh` wrapper for repeatable pyATS validation execution
- Added `run-pyats` command for launching pyATS validation workflows
- Added `pyats-shell` alias for interactive pyATS container access
- Added pyATS operations section to the automation-host MOTD
- Added platform components section documenting:
  - Docker
  - GitLab
  - Ansible
  - pyATS
  - Cisco CML integration

### Changed

- Updated MOTD layout for a more uniform and professional structure
- Improved bootstrap script permission handling by automatically applying executable permissions to all `.sh` files under:
  - `/opt/labrepo/scripts`
- Kept pyATS isolated from the host Python virtual environment by using Docker as the runtime boundary
- Added dedicated `gitlab/local/scripts/` structure for local GitLab deployment tooling
- Reorganized GitLab helper scripts into the GitLab platform directory
- Moved:
  - `setup_gitlab_container.sh`
  - `setup_gitlab_ssh.sh`
  - `validate_gitlab_lab.sh`
  - `docker-compose.yaml`

### Improved

- Improved portability of validation workflows across local lab, CML, and future CI/CD execution
- Improved operator experience with simplified pyATS helper commands
- Improved artifact organization for pyATS validation runs
- Improved repository scalability for future validation expansion
- Improved repository organization by separating platform-specific tooling from generic utility scripts
- Prepared repository layout for:
  - future GitLab CI/CD runners
  - containerized validation pipelines
  - pyATS scaling
  - automated regression testing
  - multi-environment validation workflows

## [0.7.4] - Configurable Git Platform Modes - 2026-05-09

### Added

- Added external bootstrap configuration loading from `/opt/bootstrap/bootstrap.env`
- Added configurable bootstrap entrypoint for user-defined runtime variables
- Added support for configurable hosted Git remotes using `GIT_REMOTE_URL`
- Added optional local GitLab CE deployment toggle using `INSTALL_GITLAB`
- Added bootstrap configuration banner and runtime config loading validation
- Added reusable cloud-init bootstrap configuration pattern using separate `.env` and bootstrap script files
- Added hosted Git workflow support for GitLab.com and GitHub-based lab deployments

### Changed

- Refactored GitLab bootstrap logic to support conditional local GitLab deployment
- Changed local GitLab CE installation from mandatory to optional
- Updated bootstrap architecture to separate user configuration from bootstrap logic
- Improved portability for public repo consumers by removing hardcoded Git remote assumptions
- Updated MOTD guidance to better distinguish optional local GitLab operations

## [0.7.3] - Bootstrap Service Optimization - 2026-05-08

### Fixed

- Added early cloud-init masking for Ubuntu package/update helper services before bootstrap execution.
- Prevented PackageKit from restarting through socket and DBus activation during first boot.
- Removed invalid cloud-init `runcmd` chmod reference to `${REPO_DIR}` before repository clone.

### Changed

- Retained bootstrap-level service optimization as final idempotent enforcement after early cloud-init prevention.
- Improved first-boot package installation reliability by reducing apt/dpkg lock contention.

## [0.7.2] - Bootstrap Workflow Refactor and Repository Validation Hardening - 2026-05-08

### Changed

- Reordered bootstrap workflow to clone and validate the automation repository before invoking repo-based scripts
- Added centralized repository validation for `.git`, `scripts/`, and `requirements.txt`
- Added explicit Git branch checkout validation during bootstrap
- Added automatic execute permission handling for repo shell scripts
- Improved bootstrap failure handling with persistent status tracking for repo and GitLab validation failures
- Reorganized bootstrap sections with standardized operational banners and helper summaries
- Moved Python virtual environment creation and dependency installation ahead of Docker and GitLab provisioning
- Added validation for required GitLab helper scripts before execution
- Added bootstrap prerequisite validation for the `cisco` user
- Improved helper command and MOTD documentation for operational usability

### Fixed

- Fixed bootstrap failures caused by GitLab setup executing before repository clone completion
- Fixed ambiguous chmod failures by validating required script paths before execution
- Fixed stale Docker placement documentation after bootstrap workflow restructuring

## [0.7.1] - Operator environment UX and validation helpers - 2026-05-07

### Added

- Added `/etc/profile.d/labenv.sh` to provide shell-function based `enter-lab` and `exit-lab` helpers
- Added visible lab prompt format showing active environment and Git branch, such as `(labenv:<branch>)`
- Added root-user guardrails to prevent activating the lab environment as `root`
- Added Docker access visibility during lab environment activation
- Added `lab-check` helper for validating Python, Ansible, Docker, Docker permissions, and Ansible functionality
- Added `lab` CLI entrypoint with `help`, `check`, `run`, `logs`, and `last` operations
- Added MOTD guidance for lab environment usage, platform operations, validation commands, and bootstrap recovery

### Changed

- Replaced executable `enter-lab` and `exit-lab` scripts with shell functions so virtual environment activation persists in the current shell
- Updated operator workflow to use `enter-lab`, `lab check`, `lab run`, `lab logs`, and `exit-lab`
- Improved failure messaging for missing playbooks, missing virtual environment, Docker permission issues, and unavailable automation tools

### Removed

- Removed standalone `/usr/local/bin/enter-lab` and `/usr/local/bin/exit-lab` executable helpers because they cannot persist virtual environment activation in the parent shell

## [0.7.0] - Portable GitLab CE DevOps lab integration - 2026-05-06

### Added

- Added self-hosted GitLab CE deployment using Docker Compose
- Added automated GitLab container provisioning during automation-host bootstrap
- Added persistent GitLab data, config, and log volume configuration under `/srv/gitlab`
- Added GitLab web service exposure on port `8080`
- Added GitLab SSH service exposure on port `2222`
- Added automated lab SSH key generation for GitLab authentication
- Added GitLab SSH client configuration and known_hosts registration
- Added GitLab validation helper script for container, web, SSH, and key verification
- Added bootstrap integration for GitLab setup and validation helper installation
- Added portable DevOps lab MOTD guidance and validation commands

### Changed

- Expanded automation-host bootstrap to support portable DevOps lab provisioning workflows
- Extended Docker-based lab architecture to support self-hosted CI/CD platform services

## [0.6.0] - Docker integration and automation-host runtime validation hardening - 2026-04-26

### Added

- Added Docker Engine installation during automation-host bootstrap using Docker’s official Ubuntu repository
- Added Docker GPG key and apt source configuration for managed Docker package installation
- Added automatic Docker service enable/start handling during bootstrap
- Added automatic `cisco` user membership in the `docker` group for non-sudo Docker usage
- Added Docker post-install validation for:
  - Docker service state
  - Docker daemon connectivity
  - `cisco` docker group membership
- Added MOTD runtime guidance for validating Docker access and daemon connectivity after login

## [0.5.1] - Fix credential prompt handling for reliable secret input - 2026-04-17

### Fixed

- Fixed interactive credential prompt handling in `setup_local_secrets.sh`
- Eliminated subshell usage from command substitution during secret input
- Corrected pass-by-name prompt helper functions for proper variable assignment
- Resolved prompt hangs and inconsistent input behavior during execution
- Fixed leading newline (`\n`) injection in credential values
- Restored reliable generation of `iosxe.yml` for Ansible authentication

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
