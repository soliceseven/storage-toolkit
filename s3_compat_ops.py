#!/usr/bin/env python3
"""
S3-Compatible Storage Ops — list, upload, and audit buckets on any S3 API endpoint.

Works against: IBM Cloud Object Storage (Cleversafe), Cloudian HyperStore,
AWS S3, MinIO, Wasabi, and any S3-compatible target.

Usage:
    python s3_compat_ops.py --action list [--endpoint URL] [--profile NAME]
    python s3_compat_ops.py --action audit --bucket my-bucket [--endpoint URL]
"""

import argparse
import boto3
import os
import sys
from botocore.config import Config


def get_client(profile, endpoint, region="us-east-1"):
    session = boto3.Session(profile_name=profile)
    kw = {"region_name": region, "config": Config(signature_version="s3v4")}
    if endpoint or os.environ.get("S3_ENDPOINT_URL"):
        kw["endpoint_url"] = endpoint or os.environ["S3_ENDPOINT_URL"]
    return session.client("s3", **kw)


def action_list(s3):
    buckets = s3.list_buckets()["Buckets"]
    total_objects = 0
    for b in buckets:
        name = b["Name"]
        try:
            paginator = s3.get_paginator("list_objects_v2")
            count, size = 0, 0
            for page in paginator.paginate(Bucket=name):
                for obj in page.get("Contents", []):
                    count += 1
                    size += obj["Size"]
            total_objects += count
            print(f"  {name:40s} {count:>8,} objects  {size/1e9:>10.2f} GB")
        except Exception as e:
            print(f"  {name:40s} error: {e}")
    print(f"\n{len(buckets)} buckets, {total_objects:,} total objects")


def action_audit(s3, bucket):
    print(f"Auditing s3://{bucket}")
    issues = []
    try:
        s3.get_bucket_encryption(Bucket=bucket)
        print("  encryption: ENABLED")
    except Exception:
        print("  encryption: DISABLED")
        issues.append("no-encryption")
    try:
        v = s3.get_bucket_versioning(Bucket=bucket).get("Status", "Suspended")
        print(f"  versioning: {v}")
        if v != "Enabled":
            issues.append("versioning-off")
    except Exception as e:
        print(f"  versioning: unknown ({e})")
    try:
        s3.get_bucket_lifecycle_configuration(Bucket=bucket)
        print("  lifecycle: CONFIGURED")
    except Exception:
        print("  lifecycle: NONE")
        issues.append("no-lifecycle")
    if issues:
        print(f"\nFindings: {', '.join(issues)}")
    else:
        print("\nNo findings.")


def main():
    p = argparse.ArgumentParser(description="S3-compatible storage operations")
    p.add_argument("--action", required=True, choices=["list", "audit"])
    p.add_argument("--bucket", default=None)
    p.add_argument("--endpoint", default=None, help="S3-compatible endpoint URL")
    p.add_argument("--profile", default=None)
    p.add_argument("--region", default="us-east-1")
    args = p.parse_args()

    s3 = get_client(args.profile, args.endpoint, args.region)
    if args.action == "list":
        action_list(s3)
    elif args.action == "audit":
        if not args.bucket:
            print("--bucket required for audit", file=sys.stderr)
            sys.exit(1)
        action_audit(s3, args.bucket)


if __name__ == "__main__":
    main()
