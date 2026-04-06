#!/usr/bin/env python3
from __future__ import annotations
"""Baseline validator for the AUTOCOR IOS XE expanded lab.

Run from the automation-host or any box that can reach the lab networks.

Usage:
  pip install netmiko pyyaml
  python baseline_validate.py
"""

import logging
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

# ---------------------------------------------------------------------------
# Paths and artifact layout
# ---------------------------------------------------------------------------
# BASE_DIR is the folder where this script lives. Keeping paths relative to the
# script makes the validator portable whether you run it locally, in WSL, or in CI.
BASE_DIR = Path(__file__).resolve().parent

# expected_state.yaml remains next to the script so the validator can always find
# its source of truth without needing an absolute path.
STATE_FILE = BASE_DIR / "expected_state.yaml"

# Create one timestamp per execution so every run gets its own isolated artifact
# directory. This prevents logs from being overwritten and makes troubleshooting
# easier because each run is self-contained.
RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# Standard artifact layout:
# artifacts/
#   runs/
#     <timestamp>/
#       logs/
ARTIFACTS_DIR = BASE_DIR / "artifacts"
RUNS_DIR = ARTIFACTS_DIR / "runs"
RUN_DIR = RUNS_DIR / RUN_TIMESTAMP
LOG_DIR = RUN_DIR / "logs"

# Full path to the log file for this specific validator run.
LOG_FILE = LOG_DIR / f"baseline_validate_{RUN_TIMESTAMP}.log"


@dataclass
class TestResult:
    """Represents the outcome of a single validation test."""
    name: str
    passed: bool
    details: str = ""


# Use a named logger instead of the root logger so this script controls exactly
# where its messages go and how they are formatted.
LOGGER = logging.getLogger("baseline_validate")


def banner(title: str) -> None:
    """Write a clear section divider into the logs and console output."""
    line = "=" * 76
    LOGGER.info("\n%s\n%s\n%s", line, title, line)


def show(result: TestResult) -> None:
    """Log a test result in a consistent PASS/FAIL format."""
    status = "PASS" if result.passed else "FAIL"
    LOGGER.info("[%s] %s", status, result.name)
    if result.details:
        LOGGER.info("       %s", result.details)


def load_state() -> Dict[str, Any]:
    """Load the desired lab state from expected_state.yaml."""
    with STATE_FILE.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
    

def get_git_commit() -> str:
    """Return short git commit hash, or 'unknown' if unavailable."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def get_project_version(version_file: Path = BASE_DIR / "VERSION") -> str:
    """Read project version from VERSION file."""
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0"


def create_meta_file(log_path: Path) -> Path:
    """Create meta.txt inside the run directory."""
    meta_path = RUN_DIR / "meta.txt"

    meta = {
        "timestamp": RUN_TIMESTAMP,
        "version": get_project_version(),
        "git_commit": get_git_commit(),
        "run_directory": str(RUN_DIR),
        "log_file": str(log_path),
        "state_file": str(STATE_FILE),
        "script": "baseline_validate.py",
    }

    with meta_path.open("w", encoding="utf-8") as f:
        for k, v in meta.items():
            f.write(f"{k}: {v}\n")

    return meta_path


def setup_logging(state: Dict[str, Any]) -> Path:
    """Configure console and file logging for this run.

    Behavior:
    - Reads optional logging settings from expected_state.yaml
    - Creates the timestamped run directory
    - Sends logs to both stdout and a timestamped file by default
    """
    logging_state = state.get("logging", {})
    log_level_name = str(logging_state.get("level", "INFO")).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Build the run-specific artifact directory before any handlers are attached.
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s")

    # Clear existing handlers so reruns in interactive environments do not
    # duplicate output.
    LOGGER.setLevel(log_level)
    LOGGER.handlers.clear()
    LOGGER.propagate = False

    # Console logging is helpful for local runs and CI job output.
    if logging_state.get("console", True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        LOGGER.addHandler(console_handler)

    # File logging is the persistent artifact you can review after the run.
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


def local_ping(ip: str, count: int = 2, timeout: int = 2) -> bool:
    """Ping an IP from the machine running the validator.

    This is useful for validating the automation host itself can reach a target
    before attempting device SSH or deeper protocol checks.
    """
    system = platform.system().lower()

    # Windows and Linux/macOS use different ping flags.
    cmd = (
        ["ping", "-n", str(count), "-w", str(timeout * 1000), ip]
        if system == "windows"
        else ["ping", "-c", str(count), "-W", str(timeout), ip]
    )

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            LOGGER.debug(
                "Local ping to %s failed. stdout=%r stderr=%r",
                ip,
                proc.stdout,
                proc.stderr,
            )
        return proc.returncode == 0
    except Exception as exc:
        LOGGER.exception("Local ping execution failed for %s: %s", ip, exc)
        return False


def connect(
    host: str,
    device_type: str,
    username: str,
    password: str,
    secret: str,
) -> Tuple[Optional[Any], Optional[str]]:
    """Open a Netmiko session to a device and enter enable mode when needed."""
    try:
        conn = ConnectHandler(
            device_type=device_type,
            host=host,
            username=username,
            password=password,
            secret=secret,
            fast_cli=False,
        )
        if secret:
            conn.enable()
        LOGGER.debug("Connected to %s (%s)", host, device_type)
        return conn, None
    except NetmikoTimeoutException:
        return None, "connection timeout"
    except NetmikoAuthenticationException:
        return None, "authentication failed"
    except Exception as exc:
        LOGGER.exception("Unexpected connection failure to %s", host)
        return None, str(exc)


def cmd(conn: Any, command: str) -> str:
    """Run a show/ping command on a live device and return raw output."""
    hostname = getattr(conn, "host", "unknown")
    LOGGER.debug("Running on %s: %s", hostname, command)
    output = conn.send_command(command, read_timeout=45)
    LOGGER.debug("Completed on %s: %s", hostname, command)
    return output


def parse_ip_int_brief(output: str) -> Dict[str, Tuple[str, str]]:
    """Parse 'show ip interface brief' into {interface: (status, protocol)}.

    Example:
      {
        "GigabitEthernet1": ("up", "up"),
        "Vlan99": ("administratively", "down"),
      }
    """
    data: Dict[str, Tuple[str, str]] = {}
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("interface"):
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 6:
            continue
        data[parts[0]] = (parts[-2].lower(), parts[-1].lower())
    return data


def parse_show_interfaces_trunk(output: str) -> Dict[str, Dict[str, Set[int]]]:
    """Parse 'show interfaces trunk' into allowed/active/forwarding VLAN sets."""
    trunks: Dict[str, Dict[str, Set[int]]] = {}
    current_section: Optional[str] = None
    headers = {
        "Port        Mode": "vlans_allowed",
        "Port        Vlans allowed on trunk": "vlans_allowed",
        "Port        Vlans allowed and active in management domain": "vlans_active",
        "Port        Vlans in spanning tree forwarding state and not pruned": "vlans_forwarding",
    }

    for raw in output.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue

        matched_header = False
        for header, section in headers.items():
            if stripped.startswith(header.strip()):
                current_section = section
                matched_header = True
                break

        if matched_header or stripped.startswith("----"):
            continue

        parts = re.split(r"\s+", stripped)
        if current_section == "vlans_allowed":
            if len(parts) >= 2:
                port = parts[0]
                vlan_text = parts[-1]
                entry = trunks.setdefault(
                    port,
                    {
                        "vlans_allowed": set(),
                        "vlans_active": set(),
                        "vlans_forwarding": set(),
                    },
                )
                entry["vlans_allowed"] = expand_vlan_text(vlan_text)
        elif current_section in {"vlans_active", "vlans_forwarding"}:
            if len(parts) >= 2:
                port = parts[0]
                vlan_text = parts[-1]
                entry = trunks.setdefault(
                    port,
                    {
                        "vlans_allowed": set(),
                        "vlans_active": set(),
                        "vlans_forwarding": set(),
                    },
                )
                entry[current_section] = expand_vlan_text(vlan_text)

    return trunks


def parse_show_interface_vlan(output: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse 'show interface vlan X' into (status, line_protocol)."""
    for raw in output.splitlines():
        line = raw.strip()
        match = re.search(
            r"Vlan\d+\s+is\s+([^,]+),\s+line protocol is\s+(.+)",
            line,
            re.I,
        )
        if match:
            return match.group(1).strip().lower(), match.group(2).strip().lower()
    return None, None


def parse_full_ospf(output: str) -> int:
    """Count the number of OSPF neighbors currently in FULL state."""
    return sum(1 for line in output.splitlines() if "FULL" in line.upper())


def ping_success(output: str, minimum: int) -> bool:
    """Return True when device ping output meets the required success rate."""
    match = re.search(r"Success +rate +is +(\d+) +percent", output, re.I)
    return bool(match and int(match.group(1)) >= minimum)


def expand_vlan_text(text: str) -> Set[int]:
    """Expand VLAN strings like '10,20,30-32' into a set of integers."""
    result: Set[int] = set()
    for piece in text.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "-" in piece:
            start, end = piece.split("-", 1)
            if start.isdigit() and end.isdigit():
                result.update(range(int(start), int(end) + 1))
        elif piece.isdigit():
            result.add(int(piece))
    return result


def get_run_interface(conn: Any, interface: str) -> str:
    """Shortcut for reading the running config of a single interface."""
    return cmd(conn, f"show running-config interface {interface}")


def parse_allowed_vlans(run_int: str) -> Optional[Set[int]]:
    """Extract allowed VLANs from a trunk interface running config."""
    match = re.search(r"switchport trunk allowed vlan\s+(.+)", run_int, re.I)
    return expand_vlan_text(match.group(1).strip()) if match else None


def parse_access_vlan(run_int: str) -> int:
    """Extract the configured access VLAN from an interface config.

    Cisco defaults an access port to VLAN 1 if no explicit access VLAN is set.
    """
    match = re.search(r"switchport access vlan\s+(\d+)", run_int, re.I)
    return int(match.group(1)) if match else 1


def is_trunk(run_int: str) -> bool:
    """Return True when an interface is explicitly configured as a trunk."""
    return bool(re.search(r"switchport mode trunk", run_int, re.I))


def is_access(run_int: str) -> bool:
    """Return True when an interface is explicitly configured as an access port."""
    return bool(re.search(r"switchport mode access", run_int, re.I))


def route_present(output: str, prefix: str) -> bool:
    """Simple presence check for a route prefix in 'show ip route' output."""
    return prefix in output


def acl_line_present(output: str, line: str) -> bool:
    """Case-insensitive check for a required ACL line."""
    return line.lower() in output.lower()


def collect_results(results: List[TestResult]) -> Tuple[int, int]:
    """Return a summary count of passed and failed tests."""
    passed = sum(1 for result in results if result.passed)
    return passed, len(results) - passed


def test_local_ping_targets(state: Dict[str, Any]) -> List[TestResult]:
    """Validate basic IP reachability from the automation host."""
    results = []
    for target in state.get("local_ping_targets", []):
        ok = local_ping(target["ip"])
        results.append(
            TestResult(
                f"Local ping to {target['name']} ({target['ip']})",
                ok,
                "" if ok else "No ICMP response.",
            )
        )
    return results


def login_all(state: Dict[str, Any]) -> Tuple[Dict[str, Any], List[TestResult]]:
    """Attempt SSH login to all devices defined in expected_state.yaml."""
    creds = state["credentials"]
    sessions: Dict[str, Any] = {}
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        conn, err = connect(
            device["host"],
            device["device_type"],
            creds["username"],
            creds["password"],
            creds.get("secret", ""),
        )
        if conn:
            sessions[name] = conn
            results.append(TestResult(f"SSH login to {name} ({device['host']})", True))
        else:
            sessions[name] = None
            results.append(
                TestResult(
                    f"SSH login to {name} ({device['host']})",
                    False,
                    err or "unknown failure",
                )
            )

    return sessions, results


def test_interfaces(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    """Verify that expected interfaces exist and are up/up."""
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        conn = sessions.get(name)
        if not conn:
            results.append(
                TestResult(
                    f"{name} interface state",
                    False,
                    "Skipped because SSH login failed.",
                )
            )
            continue

        output = cmd(conn, "show ip interface brief")
        parsed = parse_ip_int_brief(output)

        missing: List[str] = []
        down: List[str] = []

        for interface in device.get("expected_up_interfaces", []):
            if interface not in parsed:
                missing.append(interface)
                continue
            status, protocol = parsed[interface]
            if status != "up" or protocol != "up":
                down.append(f"{interface}={status}/{protocol}")

        ok = not missing and not down
        details: List[str] = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if down:
            details.append("not up/up: " + ", ".join(down))

        results.append(
            TestResult(
                f"{name} expected interfaces are up/up",
                ok,
                "; ".join(details),
            )
        )

    return results


def test_ospf(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    """Verify each device has the expected number of FULL OSPF neighbors."""
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        expected = device.get("expected_full_ospf_neighbors")
        if expected is None:
            continue

        conn = sessions.get(name)
        if not conn:
            results.append(
                TestResult(
                    f"{name} OSPF neighbors",
                    False,
                    "Skipped because SSH login failed.",
                )
            )
            continue

        output = cmd(conn, "show ip ospf neighbor")
        found = parse_full_ospf(output)
        results.append(
            TestResult(
                f"{name} has {expected} FULL OSPF neighbor(s)",
                found == expected,
                f"Found {found}.",
            )
        )

    return results


def test_routes(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    """Verify each device has all required routes present in its routing table."""
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        routes = device.get("expected_routes", [])
        if not routes:
            continue

        conn = sessions.get(name)
        if not conn:
            results.append(
                TestResult(
                    f"{name} expected routes",
                    False,
                    "Skipped because SSH login failed.",
                )
            )
            continue

        output = cmd(conn, "show ip route")
        missing = [route for route in routes if not route_present(output, route)]
        results.append(
            TestResult(
                f"{name} expected routes present",
                not missing,
                "Missing: " + ", ".join(missing) if missing else "",
            )
        )

    return results


def test_switching(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    """Run VLAN, SVI, trunk, and access-port checks on switch devices."""
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        if device.get("role") != "switch":
            continue

        conn = sessions.get(name)
        if not conn:
            results.append(
                TestResult(
                    f"{name} switching checks",
                    False,
                    "Skipped because SSH login failed.",
                )
            )
            continue

        vlan_out = cmd(conn, "show vlan brief")
        trunk_out = cmd(conn, "show interfaces trunk")
        ip_brief_out = cmd(conn, "show ip interface brief")

        parsed_ip_brief = parse_ip_int_brief(ip_brief_out)
        parsed_trunks = parse_show_interfaces_trunk(trunk_out)

        # Confirm required VLANs exist and are active.
        for vlan in device.get("required_vlans", []):
            ok = re.search(rf"^\s*{vlan}\s+\S+\s+active\b", vlan_out, re.I | re.M) is not None
            results.append(TestResult(f"{name} VLAN {vlan} exists", ok))

        # Validate SVI presence, addressing, and operational state.
        for svi in device.get("required_svis", []):
            svi_name = svi["name"]
            int_out = get_run_interface(conn, svi_name)
            ok_ip = svi["ip"] in int_out

            status, protocol = parsed_ip_brief.get(svi_name, (None, None))
            not_admin_down = status is not None and status != "administratively"

            svi_oper_out = cmd(conn, f"show interface {svi_name.lower()}")
            oper_status, oper_protocol = parse_show_interface_vlan(svi_oper_out)
            oper_known = oper_status is not None and oper_protocol is not None

            results.append(TestResult(f"{name} {svi_name} has expected IP {svi['ip']}", ok_ip))
            results.append(
                TestResult(
                    f"{name} {svi_name} is not administratively down",
                    not_admin_down,
                    (
                        f"Found state {status}/{protocol}."
                        if status or protocol
                        else "SVI not found in show ip interface brief."
                    ),
                )
            )
            results.append(
                TestResult(
                    f"{name} {svi_name} operational state is known",
                    oper_known,
                    (
                        f"Found {oper_status}/{oper_protocol}."
                        if oper_known
                        else "Could not parse show interface output."
                    ),
                )
            )

        # Validate trunk port mode and VLAN carriage.
        for trunk in device.get("trunk_ports", []):
            int_out = get_run_interface(conn, trunk["name"])
            required_vlans = set(trunk["allowed_vlans"])

            ok_mode = is_trunk(int_out)
            actual = parsed_trunks.get(trunk["name"], {})
            allowed = actual.get("vlans_allowed", set())
            active = actual.get("vlans_active", set())
            forwarding = actual.get("vlans_forwarding", set())

            ok_allowed = required_vlans.issubset(allowed)
            ok_active = required_vlans.issubset(active) if active else False

            results.append(TestResult(f"{name} {trunk['name']} is trunk", ok_mode))
            results.append(
                TestResult(
                    f"{name} {trunk['name']} allows VLANs {sorted(required_vlans)}",
                    ok_allowed,
                    (
                        f"Allowed on trunk: {sorted(allowed)}"
                        if allowed
                        else "Interface not present in show interfaces trunk allowed list."
                    ),
                )
            )
            results.append(
                TestResult(
                    f"{name} {trunk['name']} has VLANs {sorted(required_vlans)} active on trunk",
                    ok_active,
                    f"Allowed+active: {sorted(active)}; forwarding: {sorted(forwarding)}",
                )
            )

        # Validate access port mode and VLAN assignment.
        for access in device.get("access_ports", []):
            int_out = get_run_interface(conn, access["name"])
            vlan = parse_access_vlan(int_out)
            ok_mode = is_access(int_out)
            ok_vlan = vlan == access["access_vlan"]

            results.append(TestResult(f"{name} {access['name']} is access", ok_mode))
            results.append(
                TestResult(
                    f"{name} {access['name']} access VLAN is {access['access_vlan']}",
                    ok_vlan,
                    f"Found VLAN {vlan}.",
                )
            )

    return results


def test_device_pings(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    """Run ping tests from devices themselves for end-to-end validation."""
    results: List[TestResult] = []

    for test in state.get("device_ping_tests", []):
        conn = sessions.get(test["device"])
        if not conn:
            results.append(
                TestResult(
                    test["name"],
                    False,
                    f"Skipped because SSH login to {test['device']} failed.",
                )
            )
            continue

        repeat = int(test.get("repeat", 3))
        min_success = int(test.get("min_success", 100))

        if test.get("source_ip"):
            command = f"ping {test['target_ip']} source {test['source_ip']} repeat {repeat}"
        else:
            command = f"ping {test['target_ip']} repeat {repeat}"

        out = cmd(conn, command)
        ok = ping_success(out, min_success)
        results.append(
            TestResult(
                test["name"],
                ok,
                (
                    ""
                    if ok
                    else f"Ping to {test['target_ip']} did not meet {min_success}% success."
                ),
            )
        )

    return results


def test_acl(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    """Validate required ACLs and interface ACL attachment points."""
    results: List[TestResult] = []

    device = state["devices"].get("cat8k-2")
    if not device:
        return results

    conn = sessions.get("cat8k-2")
    if not conn:
        return [TestResult("cat8k-2 ACL checks", False, "Skipped because SSH login failed.")]

    for acl in device.get("required_acls", []):
        out = cmd(conn, f"show access-lists {acl['name']}")
        results.append(
            TestResult(
                f"ACL {acl['name']} exists on cat8k-2",
                acl["name"].lower() in out.lower(),
            )
        )
        for line in acl.get("lines", []):
            results.append(
                TestResult(
                    f"ACL {acl['name']} contains: {line}",
                    acl_line_present(out, line),
                )
            )

    run_int = get_run_interface(conn, "GigabitEthernet3.20")
    applied = re.search(r"ip access-group VLAN20_TO_SERVER in", run_int, re.I) is not None
    results.append(
        TestResult(
            "ACL VLAN20_TO_SERVER applied inbound on GigabitEthernet3.20",
            applied,
        )
    )
    return results


def test_vlan99_policy(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    """Validate where VLAN 99 must exist and where it must not be used."""
    results: List[TestResult] = []
    policy = state.get("vlan99_policy", {})

    for name, rule in policy.get("must_exist_on", {}).items():
        conn = sessions.get(rule["device"])
        if not conn:
            results.append(
                TestResult(
                    f"VLAN99 policy {name}",
                    False,
                    f"Skipped because SSH login to {rule['device']} failed.",
                )
            )
            continue

        int_out = get_run_interface(conn, rule["interface"])
        ok = True
        details: List[str] = []

        if rule.get("mode") == "trunk":
            ok = ok and is_trunk(int_out)
            allowed = parse_allowed_vlans(int_out) or set()
            required_vlan = int(rule["allowed_vlan_must_include"])
            if required_vlan not in allowed:
                ok = False
                details.append(f"allowed VLANs {sorted(allowed)} do not include {required_vlan}")

        if rule.get("mode") == "access":
            ok = ok and is_access(int_out)
            found = parse_access_vlan(int_out)
            required_vlan = int(rule["access_vlan"])
            if found != required_vlan:
                ok = False
                details.append(f"access VLAN is {found}, expected {required_vlan}")

        if rule.get("ip") and rule["ip"] not in int_out:
            ok = False
            details.append(f"expected IP {rule['ip']} not found")

        results.append(TestResult(f"VLAN99 required placement: {name}", ok, "; ".join(details)))

    for name, rule in policy.get("must_not_be_used_on", {}).items():
        conn = sessions.get(rule["device"])
        if not conn:
            results.append(
                TestResult(
                    f"VLAN99 exclusion policy {name}",
                    False,
                    f"Skipped because SSH login to {rule['device']} failed.",
                )
            )
            continue

        int_out = get_run_interface(conn, rule["interface"])
        found = parse_access_vlan(int_out)
        forbidden = int(rule["access_vlan_must_not_be"])
        ok = found != forbidden
        results.append(
            TestResult(
                f"VLAN99 not used on {name}",
                ok,
                f"Found access VLAN {found}.",
            )
        )

    return results


def close_all(sessions: Dict[str, Any]) -> None:
    """Gracefully disconnect all open Netmiko sessions."""
    for conn in sessions.values():
        if conn:
            try:
                conn.disconnect()
            except Exception:
                LOGGER.exception("Error while disconnecting session.")


def main() -> int:
    """Run the full baseline validation workflow.

    Order matters:
    1. Load state
    2. Start logging
    3. Run tests from basic reachability to deeper policy validation
    4. Close sessions
    5. Return proper exit code for CI pipelines
    """
    state = load_state()
    log_path = setup_logging(state)

#   Create meta file AFTER logging is initialized
    meta_path = create_meta_file(log_path)
    LOGGER.info("Meta file  : %s", meta_path)
    all_results: List[TestResult] = []

    banner("STEP 1 - LOCAL PING TESTS")
    for result in test_local_ping_targets(state):
        all_results.append(result)
        show(result)

    banner("STEP 2 - SSH LOGIN TESTS")
    sessions, login_results = login_all(state)
    for result in login_results:
        all_results.append(result)
        show(result)

    banner("STEP 3 - INTERFACE STATE")
    for result in test_interfaces(state, sessions):
        all_results.append(result)
        show(result)

    banner("STEP 4 - OSPF NEIGHBORS")
    for result in test_ospf(state, sessions):
        all_results.append(result)
        show(result)

    banner("STEP 5 - ROUTES")
    for result in test_routes(state, sessions):
        all_results.append(result)
        show(result)

    banner("STEP 6 - SWITCHING AND VLAN CHECKS")
    for result in test_switching(state, sessions):
        all_results.append(result)
        show(result)

    banner("STEP 7 - END-TO-END DEVICE PINGS")
    for result in test_device_pings(state, sessions):
        all_results.append(result)
        show(result)

    banner("STEP 8 - ACL CHECKS")
    for result in test_acl(state, sessions):
        all_results.append(result)
        show(result)

    banner("STEP 9 - VLAN 99 POLICY CHECKS")
    for result in test_vlan99_policy(state, sessions):
        all_results.append(result)
        show(result)

    close_all(sessions)

    passed, failed = collect_results(all_results)
    banner("SUMMARY")
    LOGGER.info("Total tests : %s", len(all_results))
    LOGGER.info("Passed      : %s", passed)
    LOGGER.info("Failed      : %s", failed)
    LOGGER.info("Validation log saved to %s", log_path)

    # Exit code is pipeline-friendly:
    # 0 = success
    # 1 = one or more tests failed
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
