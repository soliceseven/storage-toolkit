# Storage Toolkit

Python scripts for enterprise storage operations: S3-compatible object storage (Cleversafe/IBM COS, Cloudian, AWS S3), the NetApp ONTAP REST API, capacity forecasting, and backup verification. They are for storage engineers and anyone running storage health reviews.

## Overview

Each script is standalone: no framework, no configuration file, no shared state. Pick one and run it from the command line. The REST reports print a summary and write a CSV; the snapshot audit and the FC zoning audit print their reports in the terminal.

Credentials come from environment variables, never from arguments on the command line (except `--user`, which defaults to `admin` where it exists). The REST scripts connect over HTTPS and verify TLS certificates. The FC zoning audit connects over SSH and rejects unknown host keys.

## Scripts

| Script | What it does |
|--------|--------------|
| `s3_compat_ops.py` | Lists buckets and audits S3-compatible object storage (Cleversafe/IBM COS, Cloudian, AWS S3, MinIO): bucket inventory with object counts and sizes, and an audit of encryption, versioning, and lifecycle settings |
| `ontap_volume_report.py` | Gets NetApp ONTAP volume inventory through the REST API and writes `ontap_volumes.csv` |
| `ontap_snapshot_audit.py` | Reports ONTAP snapshot age and space use, and flags snapshots older than a configurable age |
| `fc_zoning_audit.py` | Checks Brocade and Cisco FC switch zoning over SSH |
| `capacity_forecast.py` | Forecasts storage capacity from usage trends with a simple linear model |
| `infinidat_infinibox_report.py` | Gets INFINIDAT InfiniBox volume and capacity data through the REST API and writes `infinidat_volumes.csv` |
| `pure_flasharray_report.py` | Gets Pure Storage FlashArray volume and capacity data through the Purity REST API and writes `pure_volumes.csv` |

## Installation

### Prerequisites

- Python 3
- `boto3` (S3-compatible operations only)
- `requests` (ONTAP, InfiniBox, and Pure REST reports)
- `paramiko` (FC zoning audit)
- For S3-compatible endpoints outside AWS, an endpoint URL (flag or environment variable, below)

### Quick Install

```bash
git clone https://github.com/soliceseven/storage-toolkit.git
cd storage-toolkit
pip install boto3 requests paramiko
```

### Verification

```bash
python3 ontap_volume_report.py --help
# Expected output:
# usage: ontap_volume_report.py [-h] [--cluster CLUSTER] [--user USER]
#                                [--password-env PASSWORD_ENV] [--output OUTPUT]
```

## Quick Start

```bash
# Volume inventory for an ONTAP cluster (user defaults to admin)
python3 ontap_volume_report.py --cluster my-cluster

# Wrote ontap_volumes.csv
```

Open `ontap_volumes.csv` to see the cluster's volumes. The InfiniBox and Pure reports work the same way and write `infinidat_volumes.csv` and `pure_volumes.csv`.

## Usage

### Credentials

Passwords and tokens are read from the environment variable named by each script's `--password-env` / `--token-env` flag, or from the defaults below. They are never passed as command-line arguments.

| Script | Host / cluster | User | Password or token |
|--------|---------------|------|-------------------|
| `ontap_volume_report.py`, `ontap_snapshot_audit.py` | `--cluster` or `ONTAP_CLUSTER` | `--user` or `ONTAP_USER` (default `admin`) | `--password-env` (default `ONTAP_PASSWORD`) |
| `infinidat_infinibox_report.py` | `--host` or `INFINIDAT_HOST` | `--user` or `INFINIDAT_USER` (default `admin`) | `--password-env` (default `INFINIDAT_PASSWORD`) |
| `pure_flasharray_report.py` | `--array` or `PURE_ARRAY` | — | `--token-env` (default `PURE_API_TOKEN`) |
| `fc_zoning_audit.py` | `--host` (required) | `--user` (default `admin`) | `--password-env` (default `SW_PASSWORD`) |

If your environment uses a private or custom certificate authority, configure it through Requests' standard CA-bundle settings. The REST scripts verify TLS certificates and will not connect over unverified HTTPS.

### Common flags

- `--output PATH`: output CSV path (`ontap_volume_report.py`, `infinidat_infinibox_report.py`, `pure_flasharray_report.py`). Defaults to `<name>.csv` as listed in the Scripts table.
- `--cluster` / `--host` / `--array`: the target system. Each script also reads its environment variable from the table above when the flag is omitted.
- `--password-env NAME` / `--token-env NAME`: the environment variable holding the password or token. Defaults are in the table above.

The snapshot audit, the FC zoning audit, and the capacity forecast print their reports in the terminal and take no `--output` flag. Run any script with `--help` for its full flag list.

### Examples

```bash
# Audit S3-compatible buckets for encryption, versioning, and lifecycle risk
python3 s3_compat_ops.py --action audit --bucket my-bucket --profile my-aws-profile

# Same, against a non-AWS endpoint (flag wins; S3_ENDPOINT_URL is the fallback)
python3 s3_compat_ops.py --action list --endpoint https://cos.example.com

# Flag ONTAP snapshots older than 30 days (default); raise the threshold with --max-age-days
python3 ontap_snapshot_audit.py --cluster my-cluster --max-age-days 60

# Check FC zoning on a Brocade switch (default vendor); use --vendor cisco for Cisco
python3 fc_zoning_audit.py --host switch1 --vendor brocade

# Forecast capacity from a CSV of date,used_gb rows; warn when projected use passes 85%
python3 capacity_forecast.py --input usage.csv --capacity-gb 10000 --warn-pct 85
```

## Testing

```bash
python3 -m unittest discover -s tests
```

The test suite uses `unittest` with mocked APIs, SSH, and REST calls, so it runs without real credentials, storage systems, or network access.

## Why this exists

I spent 14 years working in storage, including IBM Lab Services, Cleversafe object storage, and S3 at AWS. These operational scripts check encryption, snapshot age, capacity, and other storage health signals.
