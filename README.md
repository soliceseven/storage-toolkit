# Storage Toolkit

Python scripts for enterprise storage operations: S3-compatible object storage (Cleversafe/IBM COS, Cloudian, AWS S3), the NetApp ONTAP REST API, capacity forecasting, and backup verification.

## Scripts

| Script | What it does |
|--------|--------------|
| `s3_compat_ops.py` | Works with Cleversafe, Cloudian, AWS S3, and MinIO |
| `ontap_volume_report.py` | Gets NetApp ONTAP volume inventory through the REST API and writes `ontap_volumes.csv` |
| `ontap_snapshot_audit.py` | Reports ONTAP snapshot age and space use, and flags snapshots older than a configurable age |
| `fc_zoning_audit.py` | Checks Brocade and Cisco FC switch zoning over SSH |
| `capacity_forecast.py` | Forecasts storage capacity from usage trends with a simple linear model |
| `infinidat_infinibox_report.py` | Gets INFINIDAT InfiniBox volume and capacity data through the REST API and writes `infinidat_volumes.csv` |
| `pure_flasharray_report.py` | Gets Pure Storage FlashArray volume and capacity data through the Purity REST API and writes `pure_volumes.csv` |

## Setup

```bash
pip install boto3 requests paramiko
```

The REST API reports authenticate with ONTAP basic authentication (`ONTAP_USER`, default `admin`, and `ONTAP_PASSWORD`), InfiniBox username and password (`INFINIDAT_USER`, default `admin`, and `INFINIDAT_PASSWORD`), or a Pure API token (`PURE_API_TOKEN`). The ONTAP volume, InfiniBox, and Pure reports write CSV files; pass `--output` to change their output paths. The ONTAP snapshot audit prints its report in the terminal.

The REST scripts connect over HTTPS and verify TLS certificates. If your environment uses a private or custom certificate authority, configure it through Requests' standard CA-bundle settings.

For S3-compatible endpoints (non-AWS), set:
```bash
export S3_ENDPOINT_URL=https://cos.example.com
```

For the FC zoning audit, set `SW_PASSWORD` (or the variable named with `--password-env`).

Example ONTAP volume report (the user defaults to `admin`):
```bash
python ontap_volume_report.py --cluster CLUSTER
```

## Why this exists

I spent 14 years working in storage, including IBM Lab Services, Cleversafe object storage, and S3 at AWS. These operational scripts check encryption, snapshot age, capacity, and other storage health signals.
