#!/usr/bin/env python3
"""
NetApp ONTAP Volume Report — inventory via the ONTAP REST API.

Usage:
    python ontap_volume_report.py --cluster CLUSTER --user USER [--password-env ONTAP_PASSWORD]
    # Or: export ONTAP_CLUSTER, ONTAP_USER, ONTAP_PASSWORD
"""

import argparse
import csv
import os
import sys

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

# Suppress self-signed cert warnings (lab/cluster certs are commonly self-signed)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Ontap:
    def __init__(self, cluster, user, password):
        self.base = f"https://{cluster}/api"
        self.auth = HTTPBasicAuth(user, password)

    def get(self, path, params=None):
        r = requests.get(self.base + path, auth=self.auth,
                         params=params or {}, verify=False, timeout=30)
        r.raise_for_status()
        return r.json()


def main():
    p = argparse.ArgumentParser(description="NetApp ONTAP volume report")
    p.add_argument("--cluster", default=os.environ.get("ONTAP_CLUSTER"))
    p.add_argument("--user", default=os.environ.get("ONTAP_USER", "admin"))
    p.add_argument("--password-env", default="ONTAP_PASSWORD")
    p.add_argument("--output", default="ontap_volumes.csv")
    args = p.parse_args()

    if not args.cluster:
        print("--cluster or ONTAP_CLUSTER required", file=sys.stderr)
        sys.exit(1)
    password = os.environ.get(args.password_env)
    if not password:
        print(f"{args.password_env} not set", file=sys.stderr)
        sys.exit(1)

    api = Ontap(args.cluster, args.user, password)
    vols = api.get("/storage/volumes",
                   {"fields": "name,svm.name,size,space,state,type"})

    rows = []
    for v in vols.get("records", []):
        space = v.get("space", {})
        size = v.get("size", 0) or 0
        used = space.get("used", 0) or 0
        pct = (used / size * 100) if size else 0
        rows.append({
            "svm": v.get("svm", {}).get("name", ""),
            "volume": v.get("name", ""),
            "type": v.get("type", ""),
            "state": v.get("state", ""),
            "size_gb": f"{size/1e9:.1f}",
            "used_gb": f"{used/1e9:.1f}",
            "used_pct": f"{pct:.1f}",
        })

    with open(args.output, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["svm", "volume", "type", "state",
                                          "size_gb", "used_gb", "used_pct"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: float(r["used_pct"]), reverse=True))

    hot = [r for r in rows if float(r["used_pct"]) >= 85]
    print(f"Wrote {args.output}: {len(rows)} volumes, {len(hot)} over 85% used")
    for r in hot[:10]:
        print(f"  {r['svm']}/{r['volume']}: {r['used_pct']}% used")


if __name__ == "__main__":
    main()
