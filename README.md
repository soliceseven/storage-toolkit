# Storage Toolkit

Python scripts for enterprise storage operations — S3-compatible object storage (Cleversafe/IBM COS, Cloudian, AWS S3), NetApp ONTAP REST API, capacity forecasting, and backup verification.

## Scripts

| Script | What it does |
|--------|--------------|
| `s3_compat_ops.py` | S3-compatible storage ops — works against Cleversafe, Cloudian, AWS S3, MinIO |
| `ontap_volume_report.py` | NetApp ONTAP volume inventory via REST API |
| `ontap_snapshot_audit.py` | ONTAP snapshot compliance — retention, age, space |
| `fc_zoning_audit.py` | Brocade/Cisco FC switch zoning audit via SSH |
| `capacity_forecast.py` | Storage capacity trending with simple linear forecast |
| `infinidat_infinibox_report.py` | INFINIDAT InfiniBox volume/capacity via REST API |
| `pure_flasharray_report.py` | Pure Storage FlashArray volume/capacity via Purity REST |

## Setup

```bash
pip install boto3 requests
```

For S3-compatible endpoints (non-AWS), set:
```bash
export S3_ENDPOINT_URL=https://cos.example.com
```

## Why this exists

Storage is where I spent 14 years — IBM Lab Services, Cleversafe object storage, S3 at AWS. These are the operational scripts that keep storage honest: is it encrypted, is it backed up, is it about to fill up.
