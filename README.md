# Storage Toolkit

Python scripts for enterprise storage operations — S3-compatible object storage (Cleversafe/IBM COS, Cloudian, AWS S3), NetApp ONTAP REST API, capacity forecasting, and backup verification.

## Scripts

| Script | What it does |
|--------|--------------|
| `s3_compat_ops.py` | S3-compatible storage ops — works against Cleversafe, Cloudian, AWS S3, MinIO |
| `ontap_volume_report.py` | NetApp ONTAP volume inventory via REST API; writes `ontap_volumes.csv` |
| `ontap_snapshot_audit.py` | ONTAP snapshot age and space report (flags snapshots older than a configurable age) |
| `fc_zoning_audit.py` | Brocade/Cisco FC switch zoning audit via SSH |
| `capacity_forecast.py` | Storage capacity trending with simple linear forecast |
| `infinidat_infinibox_report.py` | INFINIDAT InfiniBox volume/capacity via REST API; writes `infinidat_volumes.csv` |
| `pure_flasharray_report.py` | Pure Storage FlashArray volume/capacity via Purity REST; writes `pure_volumes.csv` |

## Setup

```bash
pip install boto3 requests paramiko
```

The REST API reports use ONTAP basic authentication (`ONTAP_USER`, default `admin`, and `ONTAP_PASSWORD`), InfiniBox username/password (`INFINIDAT_USER`, default `admin`, and `INFINIDAT_PASSWORD`), or a Pure API token (`PURE_API_TOKEN`). ONTAP volume, InfiniBox, and Pure reports write CSV files; their output paths can be changed with `--output`. The ONTAP snapshot audit prints its report to the terminal.

The REST scripts connect over HTTPS with TLS certificate verification enabled. Requests' standard CA-bundle configuration is supported for environments using a private or custom certificate authority.

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

Storage is where I spent 14 years — IBM Lab Services, Cleversafe object storage, S3 at AWS. These are operational scripts for checking encryption, snapshot age, capacity, and other storage health signals.
