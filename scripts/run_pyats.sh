#!/usr/bin/env bash

###############################################################
# Execute pyATS validation workflow
#
# Purpose:
# - Launch pyATS inside the containerized runtime
# - Execute validation jobs against the lab testbed
# - Persist logs and execution artifacts
# - Provide portable and repeatable test execution
#
# Features:
# - Timestamped artifact directories
# - Repo-mounted container execution
# - Non-root container runtime
# - CI/CD-ready workflow support
#
# Outputs:
# - artifacts/pyats-runs/<timestamp>/
###############################################################

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RUN_ID="$(date +%Y%m%d-%H%M%S)"

RUN_DIR="${REPO_ROOT}/artifacts/pyats-runs/${RUN_ID}"

mkdir -p "${RUN_DIR}"

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${REPO_ROOT}:/workspace" \
  -w /workspace \
  ciscotestautomation/pyats:latest \
  pyats run job pyats/jobs/baseline_job.py \
    --testbed-file pyats/testbeds/lab-testbed.yaml \
    | tee "${RUN_DIR}/console.log"