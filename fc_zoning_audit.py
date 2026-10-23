#!/usr/bin/env python3
"""
Check Brocade and Cisco FC switch zoning over SSH.

Connects over SSH, runs zoneshow (Brocade) or show zoneset (Cisco MDS),
and reports on zone hygiene: empty zones, single-initiator violations, etc.

Usage:
    python fc_zoning_audit.py --host SWITCH --user admin [--password-env SW_PASSWORD]
    python fc_zoning_audit.py --host SWITCH --vendor cisco --user admin

Requires: pip install paramiko
"""

import argparse
import os
import re
import sys

try:
    import paramiko
except ImportError:
    print("pip install paramiko", file=sys.stderr)
    sys.exit(1)


def ssh_run(host, user, password, command):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(host, username=user, password=password, timeout=15)
    _, stdout, _ = client.exec_command(command)
    out = stdout.read().decode(errors="replace")
    client.close()
    return out


def parse_brocade_zoneshow(output):
    """Parse `zoneshow` into {zone_name: [members]}."""
    zones, current = {}, None
    for line in output.splitlines():
        m = re.match(r"^\s*zone:\s+(\S+)", line)
        if m:
            current = m.group(1)
            zones[current] = []
            continue
        if current and re.match(r"^\s+[0-9a-fA-F:,;]+", line):
            members = re.split(r"[;\s]+", line.strip())
            zones[current].extend([x for x in members if x])
    return zones


def parse_cisco_zoneset(output):
    """Parse `show zoneset active` into {zone_name: [members]}."""
    zones, current = {}, None
    for line in output.splitlines():
        m = re.match(r"^\s*zone\s+name\s+(\S+)", line)
        if m:
            current = m.group(1)
            zones[current] = []
            continue
        if current:
            members = re.findall(r"pwwn\s+([0-9a-fA-F:]+)", line)
            zones[current].extend(members)
    return zones


def audit(zones):
    print(f"\n{len(zones)} zones found\n")
    empty = [z for z, m in zones.items() if not m]
    if empty:
        print(f"Empty zones ({len(empty)}):")
        for z in empty[:10]:
            print(f"  {z}")

    # Flag zones with multiple pWWNs starting with 10:00 or 20:00 (host HBAs),
    # which violates the single-initiator zoning best practice.
    multi_init = []
    for z, members in zones.items():
        initiators = [m for m in members if re.match(r"^(10|20):00", m, re.IGNORECASE)]
        if len(initiators) > 1:
            multi_init.append((z, len(initiators)))
    if multi_init:
        print(f"\nZones with multiple initiators ({len(multi_init)}):")
        for z, n in multi_init[:10]:
            print(f"  {z}: {n} initiators")

    if not empty and not multi_init:
        print("No zoning hygiene issues found.")


def main():
    p = argparse.ArgumentParser(description="FC switch zoning audit")
    p.add_argument("--host", required=True)
    p.add_argument("--user", default="admin")
    p.add_argument("--password-env", default="SW_PASSWORD")
    p.add_argument("--vendor", choices=["brocade", "cisco"], default="brocade")
    args = p.parse_args()

    password = os.environ.get(args.password_env)
    if not password:
        print(f"{args.password_env} not set", file=sys.stderr)
        sys.exit(1)

    cmd = "zoneshow" if args.vendor == "brocade" else "show zoneset active"
    print(f"Querying {args.host} ({args.vendor})...")
    output = ssh_run(args.host, args.user, password, cmd)

    if args.vendor == "brocade":
        zones = parse_brocade_zoneshow(output)
    else:
        zones = parse_cisco_zoneset(output)
    audit(zones)


if __name__ == "__main__":
    main()
