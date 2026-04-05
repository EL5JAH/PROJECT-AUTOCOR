#!/usr/bin/env python3
"""Baseline validator for the AUTOCOR IOS XE expanded lab.

Run from the automation-host or any box that can reach the lab networks.

Usage:
  pip install netmiko pyyaml
  python baseline_validate.py
"""
from __future__ import annotations

import logging
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

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "expected_state.yaml"
DEFAULT_LOG_DIR = BASE_DIR / "logs"


@dataclass
class TestResult:
    name: str
    passed: bool
    details: str = ""


LOGGER = logging.getLogger("baseline_validate")


def banner(title: str) -> None:
    line = "=" * 76
    LOGGER.info("\n%s\n%s\n%s", line, title, line)


def show(result: TestResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    LOGGER.info("[%s] %s", status, result.name)
    if result.details:
        LOGGER.info("       %s", result.details)


def load_state() -> Dict[str, Any]:
    with STATE_FILE.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_log_path(state: Dict[str, Any]) -> Path:
    logging_state = state.get("logging", {})
    directory = logging_state.get("directory", "logs")
    directory_path = Path(directory)
    if not directory_path.is_absolute():
        directory_path = BASE_DIR / directory_path

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = logging_state.get("filename_prefix", "baseline_validate")
    return directory_path / f"{prefix}-{timestamp}.log"


def setup_logging(state: Dict[str, Any]) -> Path:
    logging_state = state.get("logging", {})
    log_level_name = str(logging_state.get("level", "INFO")).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    log_path = resolve_log_path(state)
    log_path.parent.mkdir(parents=True, exist_ok=True)

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
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)

    LOGGER.info("Logging initialized.")
    LOGGER.info("State file: %s", STATE_FILE)
    LOGGER.info("Log file  : %s", log_path)
    return log_path


def local_ping(ip: str, count: int = 2, timeout: int = 2) -> bool:
    system = platform.system().lower()
    cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), ip] if system == "windows" else ["ping", "-c", str(count), "-W", str(timeout), ip]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            LOGGER.debug("Local ping to %s failed. stdout=%r stderr=%r", ip, proc.stdout, proc.stderr)
        return proc.returncode == 0
    except Exception as exc:
        LOGGER.exception("Local ping execution failed for %s: %s", ip, exc)
        return False


def connect(host: str, device_type: str, username: str, password: str, secret: str) -> Tuple[Optional[Any], Optional[str]]:
    try:
        conn = ConnectHandler(device_type=device_type, host=host, username=username, password=password, secret=secret, fast_cli=False)
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
    hostname = getattr(conn, "host", "unknown")
    LOGGER.debug("Running on %s: %s", hostname, command)
    output = conn.send_command(command, read_timeout=45)
    LOGGER.debug("Completed on %s: %s", hostname, command)
    return output


def parse_ip_int_brief(output: str) -> Dict[str, Tuple[str, str]]:
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
                entry = trunks.setdefault(port, {"vlans_allowed": set(), "vlans_active": set(), "vlans_forwarding": set()})
                entry["vlans_allowed"] = expand_vlan_text(vlan_text)
        elif current_section in {"vlans_active", "vlans_forwarding"}:
            if len(parts) >= 2:
                port = parts[0]
                vlan_text = parts[-1]
                entry = trunks.setdefault(port, {"vlans_allowed": set(), "vlans_active": set(), "vlans_forwarding": set()})
                entry[current_section] = expand_vlan_text(vlan_text)

    return trunks


def parse_show_interface_vlan(output: str) -> Tuple[Optional[str], Optional[str]]:
    for raw in output.splitlines():
        line = raw.strip()
        m = re.search(r"Vlan\d+\s+is\s+([^,]+),\s+line protocol is\s+(.+)", line, re.I)
        if m:
            return m.group(1).strip().lower(), m.group(2).strip().lower()
    return None, None

def parse_full_ospf(output: str) -> int:
    return sum(1 for line in output.splitlines() if "FULL" in line.upper())


def ping_success(output: str, minimum: int) -> bool:
    m = re.search(r"Success +rate +is +(\d+) +percent", output, re.I)
    return bool(m and int(m.group(1)) >= minimum)


def expand_vlan_text(text: str) -> Set[int]:
    result: Set[int] = set()
    for piece in text.split(','):
        piece = piece.strip()
        if not piece:
            continue
        if '-' in piece:
            a, b = piece.split('-', 1)
            if a.isdigit() and b.isdigit():
                result.update(range(int(a), int(b) + 1))
        elif piece.isdigit():
            result.add(int(piece))
    return result


def get_run_interface(conn: Any, interface: str) -> str:
    return cmd(conn, f"show running-config interface {interface}")


def parse_allowed_vlans(run_int: str) -> Optional[Set[int]]:
    m = re.search(r"switchport trunk allowed vlan\s+(.+)", run_int, re.I)
    return expand_vlan_text(m.group(1).strip()) if m else None


def parse_access_vlan(run_int: str) -> int:
    m = re.search(r"switchport access vlan\s+(\d+)", run_int, re.I)
    return int(m.group(1)) if m else 1


def is_trunk(run_int: str) -> bool:
    return bool(re.search(r"switchport mode trunk", run_int, re.I))


def is_access(run_int: str) -> bool:
    return bool(re.search(r"switchport mode access", run_int, re.I))


def route_present(output: str, prefix: str) -> bool:
    return prefix in output


def acl_line_present(output: str, line: str) -> bool:
    return line.lower() in output.lower()


def collect_results(results: List[TestResult]) -> Tuple[int, int]:
    passed = sum(1 for r in results if r.passed)
    return passed, len(results) - passed


def test_local_ping_targets(state: Dict[str, Any]) -> List[TestResult]:
    results = []
    for target in state.get("local_ping_targets", []):
        ok = local_ping(target["ip"])
        results.append(TestResult(f"Local ping to {target['name']} ({target['ip']})", ok, "" if ok else "No ICMP response."))
    return results


def login_all(state: Dict[str, Any]) -> Tuple[Dict[str, Any], List[TestResult]]:
    creds = state["credentials"]
    sessions: Dict[str, Any] = {}
    results: List[TestResult] = []
    for name, device in state["devices"].items():
        conn, err = connect(device["host"], device["device_type"], creds["username"], creds["password"], creds.get("secret", ""))
        if conn:
            sessions[name] = conn
            results.append(TestResult(f"SSH login to {name} ({device['host']})", True))
        else:
            sessions[name] = None
            results.append(TestResult(f"SSH login to {name} ({device['host']})", False, err or "unknown failure"))
    return sessions, results


def test_interfaces(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    results: List[TestResult] = []
    for name, device in state["devices"].items():
        conn = sessions.get(name)
        if not conn:
            results.append(TestResult(f"{name} interface state", False, "Skipped because SSH login failed."))
            continue
        output = cmd(conn, "show ip interface brief")
        parsed = parse_ip_int_brief(output)
        missing, down = [], []
        for interface in device.get("expected_up_interfaces", []):
            if interface not in parsed:
                missing.append(interface)
                continue
            status, protocol = parsed[interface]
            if status != "up" or protocol != "up":
                down.append(f"{interface}={status}/{protocol}")
        ok = not missing and not down
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if down:
            details.append("not up/up: " + ", ".join(down))
        results.append(TestResult(f"{name} expected interfaces are up/up", ok, "; ".join(details)))
    return results


def test_ospf(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    results: List[TestResult] = []
    for name, device in state["devices"].items():
        expected = device.get("expected_full_ospf_neighbors")
        if expected is None:
            continue
        conn = sessions.get(name)
        if not conn:
            results.append(TestResult(f"{name} OSPF neighbors", False, "Skipped because SSH login failed."))
            continue
        output = cmd(conn, "show ip ospf neighbor")
        found = parse_full_ospf(output)
        results.append(TestResult(f"{name} has {expected} FULL OSPF neighbor(s)", found == expected, f"Found {found}."))
    return results


def test_routes(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    results: List[TestResult] = []
    for name, device in state["devices"].items():
        routes = device.get("expected_routes", [])
        if not routes:
            continue
        conn = sessions.get(name)
        if not conn:
            results.append(TestResult(f"{name} expected routes", False, "Skipped because SSH login failed."))
            continue
        output = cmd(conn, "show ip route")
        missing = [r for r in routes if not route_present(output, r)]
        results.append(TestResult(f"{name} expected routes present", not missing, "Missing: " + ", ".join(missing) if missing else ""))
    return results


def test_switching(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    results: List[TestResult] = []
    for name, device in state["devices"].items():
        if device.get("role") != "switch":
            continue
        conn = sessions.get(name)
        if not conn:
            results.append(TestResult(f"{name} switching checks", False, "Skipped because SSH login failed."))
            continue

        vlan_out = cmd(conn, "show vlan brief")
        trunk_out = cmd(conn, "show interfaces trunk")
        ip_brief_out = cmd(conn, "show ip interface brief")
        parsed_ip_brief = parse_ip_int_brief(ip_brief_out)
        parsed_trunks = parse_show_interfaces_trunk(trunk_out)

        for vlan in device.get("required_vlans", []):
            ok = re.search(rf"^\s*{vlan}\s+\S+\s+active\b", vlan_out, re.I | re.M) is not None
            results.append(TestResult(f"{name} VLAN {vlan} exists", ok))

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
                    f"Found state {status}/{protocol}." if status or protocol else "SVI not found in show ip interface brief.",
                )
            )
            results.append(
                TestResult(
                    f"{name} {svi_name} operational state is known",
                    oper_known,
                    f"Found {oper_status}/{oper_protocol}." if oper_known else "Could not parse show interface output.",
                )
            )

        for trunk in device.get("trunk_ports", []):
            int_out = get_run_interface(conn, trunk["name"])
            req = set(trunk["allowed_vlans"])
            ok_mode = is_trunk(int_out)
            actual = parsed_trunks.get(trunk["name"], {})
            allowed = actual.get("vlans_allowed", set())
            active = actual.get("vlans_active", set())
            forwarding = actual.get("vlans_forwarding", set())
            ok_allowed = req.issubset(allowed)
            ok_active = req.issubset(active) if active else False
            results.append(TestResult(f"{name} {trunk['name']} is trunk", ok_mode))
            results.append(
                TestResult(
                    f"{name} {trunk['name']} allows VLANs {sorted(req)}",
                    ok_allowed,
                    f"Allowed on trunk: {sorted(allowed)}" if allowed else "Interface not present in show interfaces trunk allowed list.",
                )
            )
            results.append(
                TestResult(
                    f"{name} {trunk['name']} has VLANs {sorted(req)} active on trunk",
                    ok_active,
                    f"Allowed+active: {sorted(active)}; forwarding: {sorted(forwarding)}",
                )
            )

        for access in device.get("access_ports", []):
            int_out = get_run_interface(conn, access["name"])
            vlan = parse_access_vlan(int_out)
            ok_mode = is_access(int_out)
            ok_vlan = vlan == access["access_vlan"]
            results.append(TestResult(f"{name} {access['name']} is access", ok_mode))
            results.append(TestResult(f"{name} {access['name']} access VLAN is {access['access_vlan']}", ok_vlan, f"Found VLAN {vlan}."))
    return results

def test_device_pings(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    results: List[TestResult] = []
    for test in state.get("device_ping_tests", []):
        conn = sessions.get(test["device"])
        if not conn:
            results.append(TestResult(test["name"], False, f"Skipped because SSH login to {test['device']} failed."))
            continue
        repeat = int(test.get("repeat", 3))
        min_success = int(test.get("min_success", 100))
        if test.get("source_ip"):
            command = f"ping {test['target_ip']} source {test['source_ip']} repeat {repeat}"
        else:
            command = f"ping {test['target_ip']} repeat {repeat}"
        out = cmd(conn, command)
        ok = ping_success(out, min_success)
        results.append(TestResult(test["name"], ok, "" if ok else f"Ping to {test['target_ip']} did not meet {min_success}% success."))
    return results


def test_acl(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    results: List[TestResult] = []
    device = state["devices"].get("cat8k-2")
    if not device:
        return results
    conn = sessions.get("cat8k-2")
    if not conn:
        return [TestResult("cat8k-2 ACL checks", False, "Skipped because SSH login failed.")]
    for acl in device.get("required_acls", []):
        out = cmd(conn, f"show access-lists {acl['name']}")
        results.append(TestResult(f"ACL {acl['name']} exists on cat8k-2", acl["name"].lower() in out.lower()))
        for line in acl.get("lines", []):
            results.append(TestResult(f"ACL {acl['name']} contains: {line}", acl_line_present(out, line)))
    run_int = get_run_interface(conn, "GigabitEthernet3.20")
    applied = re.search(r"ip access-group VLAN20_TO_SERVER in", run_int, re.I) is not None
    results.append(TestResult("ACL VLAN20_TO_SERVER applied inbound on GigabitEthernet3.20", applied))
    return results


def test_vlan99_policy(state: Dict[str, Any], sessions: Dict[str, Any]) -> List[TestResult]:
    results: List[TestResult] = []
    policy = state.get("vlan99_policy", {})

    for name, rule in policy.get("must_exist_on", {}).items():
        conn = sessions.get(rule["device"])
        if not conn:
            results.append(TestResult(f"VLAN99 policy {name}", False, f"Skipped because SSH login to {rule['device']} failed."))
            continue
        int_out = get_run_interface(conn, rule["interface"])
        ok = True
        details: List[str] = []
        if rule.get("mode") == "trunk":
            ok = ok and is_trunk(int_out)
            allowed = parse_allowed_vlans(int_out) or set()
            req = int(rule["allowed_vlan_must_include"])
            if req not in allowed:
                ok = False
                details.append(f"allowed VLANs {sorted(allowed)} do not include {req}")
        if rule.get("mode") == "access":
            ok = ok and is_access(int_out)
            found = parse_access_vlan(int_out)
            req = int(rule["access_vlan"])
            if found != req:
                ok = False
                details.append(f"access VLAN is {found}, expected {req}")
        if rule.get("ip") and rule["ip"] not in int_out:
            ok = False
            details.append(f"expected IP {rule['ip']} not found")
        results.append(TestResult(f"VLAN99 required placement: {name}", ok, "; ".join(details)))

    for name, rule in policy.get("must_not_be_used_on", {}).items():
        conn = sessions.get(rule["device"])
        if not conn:
            results.append(TestResult(f"VLAN99 exclusion policy {name}", False, f"Skipped because SSH login to {rule['device']} failed."))
            continue
        int_out = get_run_interface(conn, rule["interface"])
        found = parse_access_vlan(int_out)
        forbidden = int(rule["access_vlan_must_not_be"])
        ok = found != forbidden
        results.append(TestResult(f"VLAN99 not used on {name}", ok, f"Found access VLAN {found}."))
    return results


def close_all(sessions: Dict[str, Any]) -> None:
    for conn in sessions.values():
        if conn:
            try:
                conn.disconnect()
            except Exception:
                LOGGER.exception("Error while disconnecting session.")


def main() -> int:
    state = load_state()
    log_path = setup_logging(state)
    all_results: List[TestResult] = []

    banner("STEP 1 - LOCAL PING TESTS")
    for r in test_local_ping_targets(state):
        all_results.append(r)
        show(r)

    banner("STEP 2 - SSH LOGIN TESTS")
    sessions, login_results = login_all(state)
    for r in login_results:
        all_results.append(r)
        show(r)

    banner("STEP 3 - INTERFACE STATE")
    for r in test_interfaces(state, sessions):
        all_results.append(r)
        show(r)

    banner("STEP 4 - OSPF NEIGHBORS")
    for r in test_ospf(state, sessions):
        all_results.append(r)
        show(r)

    banner("STEP 5 - ROUTES")
    for r in test_routes(state, sessions):
        all_results.append(r)
        show(r)

    banner("STEP 6 - SWITCHING AND VLAN CHECKS")
    for r in test_switching(state, sessions):
        all_results.append(r)
        show(r)

    banner("STEP 7 - END-TO-END DEVICE PINGS")
    for r in test_device_pings(state, sessions):
        all_results.append(r)
        show(r)

    banner("STEP 8 - ACL CHECKS")
    for r in test_acl(state, sessions):
        all_results.append(r)
        show(r)

    banner("STEP 9 - VLAN 99 POLICY CHECKS")
    for r in test_vlan99_policy(state, sessions):
        all_results.append(r)
        show(r)

    close_all(sessions)

    passed, failed = collect_results(all_results)
    banner("SUMMARY")
    LOGGER.info("Total tests : %s", len(all_results))
    LOGGER.info("Passed      : %s", passed)
    LOGGER.info("Failed      : %s", failed)
    LOGGER.info("Validation log saved to %s", log_path)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())