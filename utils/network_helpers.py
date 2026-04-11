
"""
network_helpers.py

Purpose
-------
This module owns:
- device connectivity (Netmiko sessions)
- command execution
- parsing raw CLI output into structured Python data
- reusable validation checks that baseline_validate.py can call

Design goal
-----------
Keep SSH / CLI handling and parsing logic OUT of the main validator.
That lets the validator stay focused on orchestration, reporting, and artifacts.

Notes
-----
- This module is intentionally verbose and heavily commented so it doubles
  as both working code and a study reference.
- The helpers are written for Cisco IOS / IOS XE style output.
"""

from __future__ import annotations

import logging
import platform
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException


# -------------------------------------------------------------------------
# Result model
# -------------------------------------------------------------------------
@dataclass
class TestResult:
    """
    Simple, reusable container for a single validation result.

    Fields
    ------
    name:
        Human-readable test name.
    passed:
        True when the test succeeded, False when it failed.
    details:
        Optional extra context that explains what was found.
    """
    name: str
    passed: bool
    details: str = ""


# -------------------------------------------------------------------------
# Connectivity helpers
# -------------------------------------------------------------------------
def local_ping(ip: str, count: int = 2, timeout: int = 2, logger: Optional[logging.Logger] = None) -> bool:
    """
    Ping an IP from the machine running the validator.

    Why this matters
    ----------------
    This validates reachability from the automation host itself before
    attempting deeper checks such as SSH, routing, ACLs, or end-to-end traffic.

    Cross-platform behavior
    -----------------------
    Windows and Linux/macOS use different ping flags, so this helper adapts
    automatically based on the local operating system.
    """
    system = platform.system().lower()
    cmd = (
        ["ping", "-n", str(count), "-w", str(timeout * 1000), ip]
        if system == "windows"
        else ["ping", "-c", str(count), "-W", str(timeout), ip]
    )

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0 and logger:
            logger.debug("Local ping failed for %s. stdout=%r stderr=%r", ip, proc.stdout, proc.stderr)
        return proc.returncode == 0
    except Exception as exc:
        if logger:
            logger.exception("Local ping execution failed for %s: %s", ip, exc)
        return False


def connect_device(
    host: str,
    device_type: str,
    username: str,
    password: str,
    secret: str = "",
    logger: Optional[logging.Logger] = None,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Open a Netmiko session to a device.

    Returns
    -------
    (connection, error_message)

    Why tuple return?
    -----------------
    Returning both the connection and an error string lets the caller record
    a precise PASS/FAIL result without raising an exception that stops the run.
    """
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

        if logger:
            logger.debug("Connected to %s (%s)", host, device_type)

        return conn, None

    except NetmikoTimeoutException:
        return None, "connection timeout"
    except NetmikoAuthenticationException:
        return None, "authentication failed"
    except Exception as exc:
        if logger:
            logger.exception("Unexpected connection failure to %s", host)
        return None, str(exc)


def run_command(conn: Any, command: str, read_timeout: int = 45, logger: Optional[logging.Logger] = None) -> str:
    """
    Run a CLI command on a live device and return raw text output.
    """
    hostname = getattr(conn, "host", "unknown")
    if logger:
        logger.debug("Running on %s: %s", hostname, command)
    output = conn.send_command(command, read_timeout=read_timeout)
    if logger:
        logger.debug("Completed on %s: %s", hostname, command)
    return output


def close_connections(sessions: Dict[str, Any], logger: Optional[logging.Logger] = None) -> None:
    """
    Gracefully disconnect every open Netmiko session in the sessions dict.
    """
    for name, conn in sessions.items():
        if conn:
            try:
                conn.disconnect()
            except Exception:
                if logger:
                    logger.exception("Error disconnecting session for %s", name)


def get_run_interface(conn: Any, interface: str, logger: Optional[logging.Logger] = None) -> str:
    """
    Convenience helper for reading the running config of a single interface.
    """
    return run_command(conn, f"show running-config interface {interface}", logger=logger)


# -------------------------------------------------------------------------
# Parsing helpers
# -------------------------------------------------------------------------
def expand_vlan_text(text: str) -> Set[int]:
    """
    Expand Cisco VLAN strings into a set of integers.

    Example
    -------
    "10,20,30-32" -> {10, 20, 30, 31, 32}
    """
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


def parse_ip_int_brief(output: str) -> Dict[str, Tuple[str, str]]:
    """
    Parse 'show ip interface brief' into:
        {interface: (status, protocol)}

    Example
    -------
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
    """
    Parse 'show interfaces trunk' into structured VLAN data.

    Returned structure
    ------------------
    {
        "GigabitEthernet0/0": {
            "vlans_allowed": {10, 20, 30, 99},
            "vlans_active": {10, 20, 30, 99},
            "vlans_forwarding": {10, 20, 30, 99},
        }
    }
    """
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
        if len(parts) < 2:
            continue

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

        if current_section == "vlans_allowed":
            entry["vlans_allowed"] = expand_vlan_text(vlan_text)
        elif current_section == "vlans_active":
            entry["vlans_active"] = expand_vlan_text(vlan_text)
        elif current_section == "vlans_forwarding":
            entry["vlans_forwarding"] = expand_vlan_text(vlan_text)

    return trunks


def parse_show_interface_vlan(output: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse 'show interface vlan X' into:
        (admin/oper status, line protocol)
    """
    for raw in output.splitlines():
        line = raw.strip()
        match = re.search(r"Vlan\d+\s+is\s+([^,]+),\s+line protocol is\s+(.+)", line, re.I)
        if match:
            return match.group(1).strip().lower(), match.group(2).strip().lower()
    return None, None


def parse_full_ospf(output: str) -> int:
    """
    Count how many OSPF neighbors are currently in FULL state.
    """
    return sum(1 for line in output.splitlines() if "FULL" in line.upper())


def ping_success(output: str, minimum: int) -> bool:
    """
    Return True when device ping output meets the required success percentage.
    """
    match = re.search(r"Success +rate +is +(\d+) +percent", output, re.I)
    return bool(match and int(match.group(1)) >= minimum)


def parse_allowed_vlans(run_int: str) -> Optional[Set[int]]:
    """
    Extract allowed VLANs from an interface's running config.
    """
    match = re.search(r"switchport trunk allowed vlan\s+(.+)", run_int, re.I)
    return expand_vlan_text(match.group(1).strip()) if match else None


def parse_access_vlan(run_int: str) -> int:
    """
    Extract the configured access VLAN from interface config.

    Cisco defaults an access port to VLAN 1 if no explicit access VLAN is set.
    """
    match = re.search(r"switchport access vlan\s+(\d+)", run_int, re.I)
    return int(match.group(1)) if match else 1


def is_trunk(run_int: str) -> bool:
    """
    Return True when the interface is explicitly configured as a trunk.
    """
    return bool(re.search(r"switchport mode trunk", run_int, re.I))


def is_access(run_int: str) -> bool:
    """
    Return True when the interface is explicitly configured as an access port.
    """
    return bool(re.search(r"switchport mode access", run_int, re.I))


def route_present(output: str, prefix: str) -> bool:
    """
    Simple route presence check against 'show ip route' output.
    """
    return prefix in output


def acl_line_present(output: str, line: str) -> bool:
    """
    Case-insensitive check that a required ACL line exists.
    """
    return line.lower() in output.lower()


# -------------------------------------------------------------------------
# Reusable validation checks
# -------------------------------------------------------------------------
def test_local_ping_targets(state: Dict[str, Any], logger: Optional[logging.Logger] = None) -> List[TestResult]:
    """
    Validate automation-host reachability to key IP targets.
    """
    results: List[TestResult] = []
    for target in state.get("local_ping_targets", []):
        ok = local_ping(target["ip"], logger=logger)
        results.append(
            TestResult(
                f"Local ping to {target['name']} ({target['ip']})",
                ok,
                "" if ok else "No ICMP response.",
            )
        )
    return results


def login_all(state: Dict[str, Any], logger: Optional[logging.Logger] = None) -> Tuple[Dict[str, Any], List[TestResult]]:
    """
    Attempt SSH login to every device defined in expected_state.yaml.
    """
    creds = state["credentials"]
    sessions: Dict[str, Any] = {}
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        conn, err = connect_device(
            host=device["host"],
            device_type=device["device_type"],
            username=creds["username"],
            password=creds["password"],
            secret=creds.get("secret", ""),
            logger=logger,
        )

        if conn:
            sessions[name] = conn
            results.append(TestResult(f"SSH login to {name} ({device['host']})", True))
        else:
            sessions[name] = None
            results.append(TestResult(f"SSH login to {name} ({device['host']})", False, err or "unknown failure"))

    return sessions, results


def test_interfaces(state: Dict[str, Any], sessions: Dict[str, Any], logger: Optional[logging.Logger] = None) -> List[TestResult]:
    """
    Verify interfaces that are expected to be up/up actually are.
    """
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        conn = sessions.get(name)
        if not conn:
            results.append(TestResult(f"{name} interface state", False, "Skipped because SSH login failed."))
            continue

        output = run_command(conn, "show ip interface brief", logger=logger)
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

        results.append(TestResult(f"{name} expected interfaces are up/up", ok, "; ".join(details)))

    return results


def test_ospf(state: Dict[str, Any], sessions: Dict[str, Any], logger: Optional[logging.Logger] = None) -> List[TestResult]:
    """
    Verify each device has the expected number of FULL OSPF neighbors.
    """
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        expected = device.get("expected_full_ospf_neighbors")
        if expected is None:
            continue

        conn = sessions.get(name)
        if not conn:
            results.append(TestResult(f"{name} OSPF neighbors", False, "Skipped because SSH login failed."))
            continue

        output = run_command(conn, "show ip ospf neighbor", logger=logger)
        found = parse_full_ospf(output)

        results.append(
            TestResult(
                f"{name} has {expected} FULL OSPF neighbor(s)",
                found == expected,
                f"Found {found}.",
            )
        )

    return results


def test_routes(state: Dict[str, Any], sessions: Dict[str, Any], logger: Optional[logging.Logger] = None) -> List[TestResult]:
    """
    Verify each device has all expected routes present.
    """
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        routes = device.get("expected_routes", [])
        if not routes:
            continue

        conn = sessions.get(name)
        if not conn:
            results.append(TestResult(f"{name} expected routes", False, "Skipped because SSH login failed."))
            continue

        output = run_command(conn, "show ip route", logger=logger)
        missing = [route for route in routes if not route_present(output, route)]

        results.append(
            TestResult(
                f"{name} expected routes present",
                not missing,
                "Missing: " + ", ".join(missing) if missing else "",
            )
        )

    return results


def test_switching(state: Dict[str, Any], sessions: Dict[str, Any], logger: Optional[logging.Logger] = None) -> List[TestResult]:
    """
    Run switch-specific VLAN / SVI / trunk / access checks.
    """
    results: List[TestResult] = []

    for name, device in state["devices"].items():
        if device.get("role") != "switch":
            continue

        conn = sessions.get(name)
        if not conn:
            results.append(TestResult(f"{name} switching checks", False, "Skipped because SSH login failed."))
            continue

        vlan_out = run_command(conn, "show vlan brief", logger=logger)
        trunk_out = run_command(conn, "show interfaces trunk", logger=logger)
        ip_brief_out = run_command(conn, "show ip interface brief", logger=logger)

        parsed_ip_brief = parse_ip_int_brief(ip_brief_out)
        parsed_trunks = parse_show_interfaces_trunk(trunk_out)

        for vlan in device.get("required_vlans", []):
            ok = re.search(rf"^\s*{vlan}\s+\S+\s+active\b", vlan_out, re.I | re.M) is not None
            results.append(TestResult(f"{name} VLAN {vlan} exists", ok))

        for svi in device.get("required_svis", []):
            svi_name = svi["name"]
            int_out = get_run_interface(conn, svi_name, logger=logger)
            ok_ip = svi["ip"] in int_out

            status, protocol = parsed_ip_brief.get(svi_name, (None, None))
            not_admin_down = status is not None and status != "administratively"

            svi_oper_out = run_command(conn, f"show interface {svi_name.lower()}", logger=logger)
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

        for trunk in device.get("trunk_ports", []):
            int_out = get_run_interface(conn, trunk["name"], logger=logger)
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

        for access in device.get("access_ports", []):
            int_out = get_run_interface(conn, access["name"], logger=logger)
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


def test_device_pings(state: Dict[str, Any], sessions: Dict[str, Any], logger: Optional[logging.Logger] = None) -> List[TestResult]:
    """
    Run end-to-end ping tests from the devices themselves.
    """
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

        out = run_command(conn, command, logger=logger)
        ok = ping_success(out, min_success)

        results.append(
            TestResult(
                test["name"],
                ok,
                "" if ok else f"Ping to {test['target_ip']} did not meet {min_success}% success.",
            )
        )

    return results


def test_acl(state: Dict[str, Any], sessions: Dict[str, Any], logger: Optional[logging.Logger] = None) -> List[TestResult]:
    """
    Validate required ACL existence, line content, and attachment point.
    """
    results: List[TestResult] = []

    device = state["devices"].get("cat8k-2")
    if not device:
        return results

    conn = sessions.get("cat8k-2")
    if not conn:
        return [TestResult("cat8k-2 ACL checks", False, "Skipped because SSH login failed.")]

    for acl in device.get("required_acls", []):
        out = run_command(conn, f"show access-lists {acl['name']}", logger=logger)

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

    run_int = get_run_interface(conn, "GigabitEthernet3.20", logger=logger)
    applied = re.search(r"ip access-group VLAN20_TO_SERVER in", run_int, re.I) is not None

    results.append(
        TestResult(
            "ACL VLAN20_TO_SERVER applied inbound on GigabitEthernet3.20",
            applied,
        )
    )

    return results


def test_vlan99_policy(state: Dict[str, Any], sessions: Dict[str, Any], logger: Optional[logging.Logger] = None) -> List[TestResult]:
    """
    Validate where VLAN 99 must exist and where it must not be used.
    """
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

        int_out = get_run_interface(conn, rule["interface"], logger=logger)
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

        int_out = get_run_interface(conn, rule["interface"], logger=logger)
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


def collect_results(results: List[TestResult]) -> Tuple[int, int]:
    """
    Return:
        (passed_count, failed_count)
    """
    passed = sum(1 for result in results if result.passed)
    return passed, len(results) - passed
