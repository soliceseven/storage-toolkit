#!/usr/bin/env python3
"""
Pure Storage FlashArray Report — volume inventory and array capacity via REST.

Uses the Purity REST API v2 (https://<array>/api/2.x/).
Auth: API token -> access token.

Usage:
    python pure_flasharray_report.py --array ARRAY [--token-env PURE_API_TOKEN]
    # Or: export PURE_ARRAY, PURE_API_TOKEN

    # Generate an API token on the array first:
    #   pureadmin create --api-token -u <username>
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

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class FlashArray:
    def __init__(self, array, api_token, api_version="2.30"):
        self.base = f"https://{array}/api/{api_version}"
        r = requests.post(f"{self.base}/login", json={"api_token": api_token},
                          verify=False, timeout=30)
        r.raise_for_status()
        self.token = r.json()["access_token"]
        self.headers = {"x-auth-token": self.token}

    def get(self, path, params=None):
        r = requests.get(self.base + path, headers=self.headers,
                         params=params or {}, verify=False, timeout=30)
        r.raise_for_status()
        return r.json()

    def logout(self):
        try:
            requests.post(f"{self.base}/logout", headers=self.headers,
                          verify=False, timeout=10)
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser(description="Pure Storage FlashArray report")
    p.add_argument("--array", default=os.environ.get("PURE_ARRAY"))
    p.add_argument("--token-env", default="PURE_API_TOKEN")
    p.add_argument("--output", default="pure_volumes.csv")
    args = p.parse_args()

    if not args.array:
        print("--array or PURE_ARRAY required", file=sys.stderr)
        sys.exit(1)
    api_token = os.environ.get(args.token_env)
    if not api_token:
        print(f"{args.token_env} not set", file=sys.stderr)
        sys.exit(1)

    fa = FlashArray(args.array, api_token)
    try:
        # Array capacity
        arrays = fa.get("/arrays", {"space": "true"})["items"]
        print("Array capacity:")
        for a in arrays:
            sp = a.get("space", {})
            total = sp.get("total_physical", 0) or 0
            used = sp.get("total_used", 0) or 0
            drr = sp.get("data_reduction", 0) or 0
            pct = (used/total*100) if total else 0
            print(f"  {a.get('name')}: {total/1e12:.1f}TB total, "
                  f"{pct:.1f}% used, {drr:.1f}:1 data reduction")

        # Volumes
        vols = fa.get("/volumes", {"space": "true"})["items"]
        rows = []
        for v in vols:
            sp = v.get("space", {})
            size = v.get("provisioned", 0) or 0
            used = (sp.get("total_used", 0) or 0)
            rows.append({
                "volume": v.get("name", ""),
                "size_gb": f"{size/1e9:.1f}",
                "used_gb": f"{used/1e9:.1f}",
                "serial": v.get("serial", ""),
            })

        with open(args.output, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["volume", "size_gb", "used_gb", "serial"])
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: r["volume"]))

        print(f"\nWrote {args.output}: {len(rows)} volumes")

        # Protection groups
        pgs = fa.get("/protection-groups")["items"]
        print(f"{len(pgs)} protection groups configured")
    finally:
        fa.logout()


if __name__ == "__main__":
    main()
