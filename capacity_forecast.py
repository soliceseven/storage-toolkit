#!/usr/bin/env python3
"""
Project storage capacity from CSV samples using a simple linear trend.

Reads a CSV of (date, used_gb) samples and projects when capacity runs out.

Usage:
    python capacity_forecast.py --input samples.csv --capacity-gb 100000
    # samples.csv: date,used_gb  (e.g. 2026-01-01,45200)
"""

import argparse
import csv
import math
import sys
from datetime import datetime, timedelta


def main():
    p = argparse.ArgumentParser(description="Storage capacity forecast")
    p.add_argument("--input", required=True, help="CSV with date,used_gb columns")
    p.add_argument("--capacity-gb", type=float, required=True)
    p.add_argument("--warn-pct", type=float, default=85)
    args = p.parse_args()

    if not math.isfinite(args.capacity_gb) or args.capacity_gb <= 0:
        p.error("--capacity-gb must be a finite positive number")
    if not math.isfinite(args.warn_pct) or not 0 <= args.warn_pct <= 100:
        p.error("--warn-pct must be between 0 and 100")

    samples = []
    with open(args.input) as f:
        for row in csv.DictReader(f):
            try:
                d = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
                samples.append((d, float(row["used_gb"])))
            except (KeyError, ValueError) as e:
                print(f"Skipping bad row {row}: {e}", file=sys.stderr)
    samples.sort()

    if len(samples) < 2:
        print("Need at least 2 samples", file=sys.stderr)
        sys.exit(1)

    # Calculate the linear rate in GB per day.
    (d0, u0), (d1, u1) = samples[0], samples[-1]
    days = (d1 - d0).days or 1
    rate = (u1 - u0) / days

    latest_date, latest_used = samples[-1]
    pct_now = latest_used / args.capacity_gb * 100
    print(
        f"Latest: {latest_date} — {latest_used:,.0f} GB ({pct_now:.1f}% of {args.capacity_gb:,.0f} GB)"
    )
    print(f"Growth rate: {rate:,.1f} GB/day")

    if rate <= 0:
        print("Usage is flat or shrinking — no exhaustion projected.")
        return

    warn_gb = args.capacity_gb * args.warn_pct / 100
    days_to_warn = max(0, (warn_gb - latest_used) / rate)
    days_to_full = max(0, (args.capacity_gb - latest_used) / rate)

    print(
        f"\nHits {args.warn_pct:.0f}% ({warn_gb:,.0f} GB) in ~{days_to_warn:.0f} days "
        f"({(latest_date + timedelta(days=days_to_warn)).isoformat()})"
    )
    print(
        f"Hits 100% in ~{days_to_full:.0f} days "
        f"({(latest_date + timedelta(days=days_to_full)).isoformat()})"
    )


if __name__ == "__main__":
    main()
