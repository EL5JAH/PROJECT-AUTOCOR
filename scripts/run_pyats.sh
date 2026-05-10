#!/usr/bin/env bash
set -euo pipefail

###############################################################
# run-pyats
#
# Purpose:
# - Run Cisco pyATS from a Docker container
# - Keep pyATS isolated from the host Python environment
# - Store pyATS artifacts in timestamped run directories
# - Use a persistent writable workspace mounted at /pyats
#
# Usage:
#   run-pyats
#   run-pyats pyats version check
#   run-pyats bash
###############################################################

PYATS_IMAGE="ciscotestautomation/pyats:latest"
REPO_DIR="/opt/labrepo"
PYATS_WORKSPACE="${REPO_DIR}/pyats"
PYATS_RUNS_DIR="${REPO_DIR}/artifacts/pyats-runs"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="${PYATS_RUNS_DIR}/${RUN_ID}"

mkdir -p "${PYATS_WORKSPACE}"
mkdir -p "${RUN_DIR}"

if [[ ! -w "${PYATS_WORKSPACE}" ]]; then
    echo "ERROR: pyATS workspace is not writable: ${PYATS_WORKSPACE}"
    echo
    echo "Fix with:"
    echo "  sudo chown -R cisco:cisco ${PYATS_WORKSPACE}"
    exit 1
fi

if [[ ! -w "${PYATS_RUNS_DIR}" ]]; then
    echo "ERROR: pyATS artifact directory is not writable: ${PYATS_RUNS_DIR}"
    echo
    echo "Fix with:"
    echo "  sudo chown -R cisco:cisco ${PYATS_RUNS_DIR}"
    exit 1
fi

echo "Starting pyATS container..."
echo "Image:      ${PYATS_IMAGE}"
echo "Workspace:  ${PYATS_WORKSPACE} -> /pyats"
echo "Artifacts:  ${RUN_DIR} -> /artifacts"
echo "Repo:       ${REPO_DIR} -> /workspace"
echo

if [[ $# -gt 0 ]]; then
    docker run --rm -it \
        -v "${PYATS_WORKSPACE}:/pyats" \
        -v "${RUN_DIR}:/artifacts" \
        -v "${REPO_DIR}:/workspace" \
        -w /workspace \
        "${PYATS_IMAGE}" \
        "$@"
else
    docker run --rm -it \
        -v "${PYATS_WORKSPACE}:/pyats" \
        -v "${RUN_DIR}:/artifacts" \
        -v "${REPO_DIR}:/workspace" \
        -w /workspace \
        "${PYATS_IMAGE}" \
        pyats version check
fi

echo
echo "pyATS run complete."
echo "Artifacts saved to: ${RUN_DIR}"