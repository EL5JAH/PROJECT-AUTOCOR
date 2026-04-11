
#!/usr/bin/env python3
from __future__ import annotations

"""
baseline_validate.py

Purpose
-------
Main orchestration script for validating the AUTOCOR IOS XE lab.

What this script owns
---------------------
- loading the source-of-truth YAML file
- building artifact directories for each run
- configuring logging
- calling reusable connectivity / parsing / validation helpers
- saving run summaries and metadata

What this script does NOT own
-----------------------------
- low-level SSH session behavior
- CLI parsing logic
- deep validation helper logic

Those belong in utils/network_helpers.py.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from utils.file_helpers import build_run_dir, load_yaml, save_json, write_text
from utils.network_helpers import (
    TestResult,
    close_connections,
    collect_results,
    login_all,
    test_acl,
    test_device_pings,
    test_interfaces,
    test_local_ping_targets,
    test_ospf,
    test_routes,
    test_switching,
    test_vlan99_policy,
)


# -------------------------------------------------------------------------
# Paths and artifact layout
# -------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "expected_state.yaml"

RUN_DIR = Path(build_run_dir(str(BASE_DIR / "artifacts" / "runs")))
LOG_DIR = RUN_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "baseline_validate.log"

LOGGER = logging.getLogger("baseline_validate")


# -------------------------------------------------------------------------
# Small utility helpers
# -------------------------------------------------------------------------
def banner(title: str) -> None:
    """
    Write a clear section divider into both console and log output.
    """
    line = "=" * 76
    LOGGER.info("\n%s\n%s\n%s", line, title, line)


def show(result: TestResult) -> None:
    """
    Log a single test result in a consistent PASS/FAIL format.
    """
    status = "PASS" if result.passed else "FAIL"
    LOGGER.info("[%s] %s", status, result.name)
    if result.details:
        LOGGER.info("       %s", result.details)


def load_state() -> Dict[str, Any]:
    """
    Load the lab's source-of-truth state file using file_helpers.
    """
    return load_yaml(str(STATE_FILE))


def get_git_commit() -> str:
    """
    Return the short git commit hash for traceability.
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def get_project_version(version_file: Path = BASE_DIR / "VERSION") -> str:
    """
    Read the project version from a VERSION file.
    """
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0"


def create_meta_file(log_path: Path) -> Path:
    """
    Create a meta.txt artifact for this run.
    """
    meta_path = RUN_DIR / "meta.txt"

    meta = {
        "version": get_project_version(),
        "git_commit": get_git_commit(),
        "run_directory": str(RUN_DIR),
        "log_file": str(log_path),
        "state_file": str(STATE_FILE),
        "script": "baseline_validate.py",
    }

    write_text(str(meta_path), "\n".join(f"{k}: {v}" for k, v in meta.items()))
    return meta_path


def setup_logging(state: Dict[str, Any]) -> Path:
    """
    Configure console and file logging for this run.
    """
    logging_state = state.get("logging", {})
    log_level_name = str(logging_state.get("level", "INFO")).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    formatter = logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s")

    LOGGER.setLevel(log_level)
    LOGGER.handlers.clear()
    LOGGER.propagate = False

    if logging_state.get("console", True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        LOGGER.addHandler(console_handler)

    if logging_state.get("file", True):
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)

    LOGGER.info("Logging initialized.")
    LOGGER.info("State file : %s", STATE_FILE)
    LOGGER.info("Run dir    : %s", RUN_DIR)
    LOGGER.info("Log file   : %s", LOG_FILE)
    return LOG_FILE


def save_run_summary(all_results: List[TestResult], passed: int, failed: int) -> None:
    """
    Persist structured and human-readable summaries for the validation run.
    """
    summary = {
        "run_directory": str(RUN_DIR),
        "total_tests": len(all_results),
        "passed": passed,
        "failed": failed,
        "results": [
            {
                "name": result.name,
                "passed": result.passed,
                "details": result.details,
            }
            for result in all_results
        ],
    }

    save_json(summary, str(RUN_DIR / "summary.json"))

    lines = [
        "Baseline Validation Summary",
        f"Run Directory: {RUN_DIR}",
        f"Total Tests: {len(all_results)}",
        f"Passed: {passed}",
        f"Failed: {failed}",
        "",
    ]

    for result in all_results:
        status = "PASS" if result.passed else "FAIL"
        line = f"[{status}] {result.name}"
        if result.details:
            line += f" | {result.details}"
        lines.append(line)

    write_text(str(RUN_DIR / "summary.txt"), "\n".join(lines))


def main() -> int:
    """
    Run the full baseline validation workflow.
    """
    state = load_state()
    log_path = setup_logging(state)

    meta_path = create_meta_file(log_path)
    LOGGER.info("Meta file  : %s", meta_path)

    all_results: List[TestResult] = []

    banner("STEP 1 - LOCAL PING TESTS")
    for result in test_local_ping_targets(state, logger=LOGGER):
        all_results.append(result)
        show(result)

    banner("STEP 2 - SSH LOGIN TESTS")
    sessions, login_results = login_all(state, logger=LOGGER)
    for result in login_results:
        all_results.append(result)
        show(result)

    banner("STEP 3 - INTERFACE STATE")
    for result in test_interfaces(state, sessions, logger=LOGGER):
        all_results.append(result)
        show(result)

    banner("STEP 4 - OSPF NEIGHBORS")
    for result in test_ospf(state, sessions, logger=LOGGER):
        all_results.append(result)
        show(result)

    banner("STEP 5 - ROUTES")
    for result in test_routes(state, sessions, logger=LOGGER):
        all_results.append(result)
        show(result)

    banner("STEP 6 - SWITCHING AND VLAN CHECKS")
    for result in test_switching(state, sessions, logger=LOGGER):
        all_results.append(result)
        show(result)

    banner("STEP 7 - END-TO-END DEVICE PINGS")
    for result in test_device_pings(state, sessions, logger=LOGGER):
        all_results.append(result)
        show(result)

    banner("STEP 8 - ACL CHECKS")
    for result in test_acl(state, sessions, logger=LOGGER):
        all_results.append(result)
        show(result)

    banner("STEP 9 - VLAN 99 POLICY CHECKS")
    for result in test_vlan99_policy(state, sessions, logger=LOGGER):
        all_results.append(result)
        show(result)

    close_connections(sessions, logger=LOGGER)

    passed, failed = collect_results(all_results)

    banner("SUMMARY")
    LOGGER.info("Total tests : %s", len(all_results))
    LOGGER.info("Passed      : %s", passed)
    LOGGER.info("Failed      : %s", failed)

    save_run_summary(all_results, passed, failed)
    LOGGER.info("Summary JSON: %s", RUN_DIR / "summary.json")
    LOGGER.info("Summary TXT : %s", RUN_DIR / "summary.txt")
    LOGGER.info("Validation log saved to %s", log_path)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
