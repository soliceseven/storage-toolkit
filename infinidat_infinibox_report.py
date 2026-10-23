#!/usr/bin/env python3
"""
Report INFINIDAT InfiniBox volume inventory and capacity through the REST API.

Uses the InfiniBox REST API (https://<box>/api/rest/).
Authenticate with a username and password to obtain a session token.

Usage:
    python infinidat_infinibox_report.py --host BOX [--password-env INFINIDAT_PASSWORD]
    # Or: export INFINIDAT_HOST, INFINIDAT_USER, INFINIDAT_PASSWORD
"""

import argparse
import csv
import os
import sys

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)


class InfiniBox:
    def __init__(self, host, user, password):
        self.base = f"https://{host}/api/rest"
        r = requests.post(
            f"{self.base}/users/login",
            json={"user": user, "password": password},
            verify=True,
            timeout=30,
        )
        r.raise_for_status()
        self.token = r.json()["result"]["auth_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def get(self, path, params=None):
        r = requests.get(
            self.base + path,
            headers=self.headers,
            params=params or {},
            verify=True,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["result"]

    def logout(self):
        try:
            requests.post(
                f"{self.base}/users/logout",
                headers=self.headers,
                verify=True,
                timeout=10,
            )
        except Exception:
            pass


def csv_safe(value):
    if isinstance(value, str) and (
        value[:1] in {"=", "+", "-", "@", "\t", "\r", "\n"}
        or value.lstrip(" \t\r\n")[:1] in {"=", "+", "-", "@"}
    ):
        return "'" + value
    return value


def main():
    p = argparse.ArgumentParser(description="INFINIDAT InfiniBox volume report")
    p.add_argument("--host", default=os.environ.get("INFINIDAT_HOST"))
    p.add_argument("--user", default=os.environ.get("INFINIDAT_USER", "admin"))
    p.add_argument("--password-env", default="INFINIDAT_PASSWORD")
    p.add_argument("--output", default="infinidat_volumes.csv")
    args = p.parse_args()

    if not args.host:
        print("--host or INFINIDAT_HOST required", file=sys.stderr)
        sys.exit(1)
    password = os.environ.get(args.password_env)
    if not password:
        print(f"{args.password_env} not set", file=sys.stderr)
        sys.exit(1)

    box = InfiniBox(args.host, args.user, password)
    try:
        vols = box.get("/volumes", {"fields": "name,size,pool,provtype,mapped"})
        pools = {
            pl["id"]: pl
            for pl in box.get("/pools", {"fields": "id,name,size,free"})
        }

        rows = []
        for v in vols:
            pool = pools.get(v.get("pool", {}).get("id", ""), {})
            size = v.get("size", 0) or 0
            rows.append(
                {
                    "volume": csv_safe(v.get("name", "")),
                    "pool": csv_safe(pool.get("name", "")),
                    "size_gb": f"{size / 1e9:.1f}",
                    "provtype": csv_safe(v.get("provtype", "")),
                    "mapped": "yes" if v.get("mapped") else "no",
                }
            )

        with open(args.output, "w", newline="") as f:
            w = csv.DictWriter(
                f, fieldnames=["volume", "pool", "size_gb", "provtype", "mapped"]
            )
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: r["volume"]))

        print("\nPools:")
        for pl in pools.values():
            size, free = pl.get("size", 0) or 0, pl.get("free", 0) or 0
            pct = (1 - free / size) * 100 if size else 0
            print(f"  {pl.get('name')}: {size / 1e12:.1f}TB total, {pct:.1f}% used")

        print(f"\nWrote {args.output}: {len(rows)} volumes")
    finally:
        box.logout()


if __name__ == "__main__":
    main()
