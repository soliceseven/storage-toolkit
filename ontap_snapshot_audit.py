#!/usr/bin/env python3
"""
ONTAP Snapshot Audit — check snapshot retention, age, and space consumption.

Usage:
    python ontap_snapshot_audit.py --cluster CLUSTER [--password-env ONTAP_PASSWORD]
"""

import argparse
import os
import sys
from datetime import datetime, timezone

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="NetApp ONTAP snapshot audit")
    p.add_argument("--cluster", default=os.environ.get("ONTAP_CLUSTER"))
    p.add_argument("--user", default=os.environ.get("ONTAP_USER", "admin"))
    p.add_argument("--password-env", default="ONTAP_PASSWORD")
    p.add_argument(
        "--max-age-days", type=int, default=30, help="Flag snapshots older than this"
    )
    args = p.parse_args()

    if not args.cluster:
        print("--cluster or ONTAP_CLUSTER required", file=sys.stderr)
        sys.exit(1)
    password = os.environ.get(args.password_env)
    if not password:
        print(f"{args.password_env} not set", file=sys.stderr)
        sys.exit(1)

    base = f"https://{args.cluster}/api"
    auth = HTTPBasicAuth(args.user, password)

    r = requests.get(
        base + "/storage/volumes/snapshots",
        auth=auth,
        verify=True,
        timeout=30,
        params={"fields": "name,volume.name,svm.name,create_time,space"},
    )
    r.raise_for_status()
    snaps = r.json().get("records", [])

    now = datetime.now(timezone.utc)
    stale, total_space = [], 0
    for s in snaps:
        create_time = s.get("create_time", "")
        try:
            ct = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
            age_days = (now - ct).days
        except Exception:
            age_days = -1
        space = (s.get("space") or {}).get("total", 0) or 0
        total_space += space
        if age_days > args.max_age_days:
            stale.append(
                (
                    s.get("svm", {}).get("name", ""),
                    (s.get("volume") or {}).get("name", ""),
                    s.get("name", ""),
                    age_days,
                )
            )

    print(f"{len(snaps)} snapshots, {total_space / 1e9:.1f} GB total")
    print(f"{len(stale)} older than {args.max_age_days} days:")
    for svm, vol, name, age in sorted(stale, key=lambda x: x[3], reverse=True)[:20]:
        print(f"  {svm}/{vol}/{name}: {age}d old")


if __name__ == "__main__":
    main()
