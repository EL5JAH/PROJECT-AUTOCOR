# Project Conventions

## Directory Rules

- scripts/ → automation logic
- lab/ → topology
- expected_state/ → desired state
- artifacts/ → runtime output (ignored in git)
- docs/ → documentation

## Naming

- snake_case for scripts
- lowercase directories

## Logging

artifacts/runs/YYYYMMDD-HHMMSS/

## Validation

- No hardcoding
- Use expected_state.yaml

## Versioning

- MAJOR → breaking
- MINOR → features
- PATCH → fixes

## Commit Types

### feat

Use for new functionality or meaningful new capabilities.

Examples:

- feat: add baseline validator for lab connectivity
- feat(validation): add ACL and VLAN policy checks

### fix

Use for bug fixes or corrections to existing behavior.

Examples:

- fix: correct VLAN 99 validation logic
- fix(utils): handle missing version file gracefully

### refactor

Use for code restructuring that improves design without introducing new behavior.

Examples:

- refactor: extract network_helpers and modularize baseline validation
- refactor(utils): move file operations into file_helpers

### docs

Use for documentation updates such as README, comments, and usage guides.

Examples:

- docs: add commit and versioning conventions
- docs(readme): document validator workflow

### test

Use for adding or updating tests, mock data, or validation coverage.

Examples:

- test: add parsing coverage for trunk output
- test(validation): add expected state cases for ACL checks

### chore

Use for maintenance tasks, housekeeping, or version bumps.

Examples:

- chore: update gitignore for run artifacts
- chore(version): bump version to 0.2.0

### build

Use for dependency management or build system changes.

Examples:

- build: add netmiko to requirements
- build: pin pyyaml version

### ci

Use for CI/CD pipeline configuration and automation changes.

Examples:

- ci: add github actions validation workflow
- ci: publish validation artifacts in pipeline
