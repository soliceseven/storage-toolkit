import contextlib
import csv
import importlib.util
import io
import os
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def local_test_path(test_case, filename):
    path = ROOT / "tests" / filename
    path.unlink(missing_ok=True)
    test_case.addCleanup(lambda: path.unlink(missing_ok=True))
    return path


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_optional_import_stubs():
    if importlib.util.find_spec("paramiko") is None:
        sys.modules["paramiko"] = types.ModuleType("paramiko")
    if importlib.util.find_spec("boto3") is None:
        sys.modules["boto3"] = types.ModuleType("boto3")
    if importlib.util.find_spec("botocore") is None:
        botocore = types.ModuleType("botocore")
        botocore.__path__ = []
        config = types.ModuleType("botocore.config")
        config.Config = lambda **kwargs: kwargs
        exceptions = types.ModuleType("botocore.exceptions")

        class ClientError(Exception):
            def __init__(self, error_response, operation_name):
                super().__init__(operation_name)
                self.response = error_response

        exceptions.ClientError = ClientError
        botocore.config = config
        botocore.exceptions = exceptions
        sys.modules["botocore"] = botocore
        sys.modules["botocore.config"] = config
        sys.modules["botocore.exceptions"] = exceptions


install_optional_import_stubs()
capacity = load_script("capacity_forecast")
fc = load_script("fc_zoning_audit")
infinidat = load_script("infinidat_infinibox_report")
snapshot = load_script("ontap_snapshot_audit")
ontap = load_script("ontap_volume_report")
pure = load_script("pure_flasharray_report")
s3 = load_script("s3_compat_ops")


class CapacityForecastTests(unittest.TestCase):
    def test_sorts_samples_skips_bad_rows_and_prints_expected_forecast(self):
        input_path = local_test_path(self, ".capacity_samples.csv")
        input_path.write_text(
            "date,used_gb\n"
            "2026-01-11,60\n"
            "not-a-date,invalid\n"
            "2026-01-01,40\n"
        )
        output = io.StringIO()
        errors = io.StringIO()
        with patch.object(
            sys,
            "argv",
            ["capacity_forecast.py", "--input", str(input_path), "--capacity-gb", "100"],
        ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            capacity.main()

        self.assertEqual(
            output.getvalue(),
            "Latest: 2026-01-11 — 60 GB (60.0% of 100 GB)\n"
            "Growth rate: 2.0 GB/day\n"
            "\nHits 85% (85 GB) in ~12 days (2026-01-23)\n"
            "Hits 100% in ~20 days (2026-01-31)\n",
        )
        self.assertIn("Skipping bad row", errors.getvalue())

    def test_nonpositive_growth_does_not_project_exhaustion(self):
        input_path = local_test_path(self, ".capacity_shrinking_samples.csv")
        input_path.write_text("date,used_gb\n2026-01-01,40\n2026-01-11,30\n")
        output = io.StringIO()
        with patch.object(
            sys,
            "argv",
            ["capacity_forecast.py", "--input", str(input_path), "--capacity-gb", "100"],
        ), contextlib.redirect_stdout(output):
            capacity.main()

        self.assertIn("Growth rate: -1.0 GB/day", output.getvalue())
        self.assertIn("Usage is flat or shrinking — no exhaustion projected.", output.getvalue())
        self.assertNotIn("Hits 100%", output.getvalue())


class FibreChannelAuditTests(unittest.TestCase):
    def test_parsers_and_audit_report_zone_hygiene_findings(self):
        brocade = fc.parse_brocade_zoneshow(
            "zone: app\n  10:00:00:00:00:00:00:01;50:00:00:00:00:00:00:01\n"
            "zone: empty\n"
        )
        cisco = fc.parse_cisco_zoneset(
            "zone name shared vsan 10\n"
            "  member pwwn 10:00:00:00:00:00:00:01\n"
            "  member pwwn 20:00:00:00:00:00:00:02\n"
            "zone name storage vsan 10\n"
            "  member pwwn 50:00:00:00:00:00:00:03\n"
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            fc.audit({**brocade, **cisco})

        self.assertEqual(
            brocade,
            {
                "app": [
                    "10:00:00:00:00:00:00:01",
                    "50:00:00:00:00:00:00:01",
                ],
                "empty": [],
            },
        )
        self.assertEqual(len(cisco["shared"]), 2)
        self.assertIn("4 zones found", output.getvalue())
        self.assertIn("Empty zones (1):\n  empty", output.getvalue())
        self.assertIn("Zones with multiple initiators (1):\n  shared: 2 initiators", output.getvalue())


class OntapVolumeReportTests(unittest.TestCase):
    def test_main_writes_sorted_volume_csv_and_reports_threshold(self):
        class FakeOntap:
            def __init__(self, cluster, user, password):
                self.request = (cluster, user, password)

            def get(self, path, params):
                self.path = path
                self.params = params
                return {
                    "records": [
                        {
                            "svm": {"name": "=SV"},
                            "name": "+VOL",
                            "type": "-rw",
                            "state": "@online",
                            "size": 10_000_000_000,
                            "space": {"used": 2_000_000_000},
                        },
                        {
                            "svm": {"name": "svm-b"},
                            "name": "hot",
                            "type": "rw",
                            "state": "online",
                            "size": 10_000_000_000,
                            "space": {"used": 9_000_000_000},
                        },
                        {
                            "svm": {"name": "svm-c"},
                            "name": "zero-size",
                            "type": "dp",
                            "state": "offline",
                            "size": 0,
                            "space": {"used": 1},
                        },
                    ]
                }

        output_path = local_test_path(self, ".ontap_volume_report.csv")
        output = io.StringIO()
        with (
            patch.object(ontap, "Ontap", FakeOntap),
            patch.object(
                sys,
                "argv",
                [
                    "ontap_volume_report.py",
                    "--cluster",
                    "offline.example",
                    "--output",
                    str(output_path),
                ],
            ),
            patch.dict(os.environ, {"ONTAP_PASSWORD": "not-a-real-secret"}),
            contextlib.redirect_stdout(output),
        ):
            ontap.main()

        with output_path.open(newline="") as report:
            rows = list(csv.DictReader(report))

        self.assertEqual(
            list(rows[0]),
            ["svm", "volume", "type", "state", "size_gb", "used_gb", "used_pct"],
        )
        self.assertEqual([row["volume"] for row in rows], ["hot", "'+VOL", "zero-size"])
        self.assertEqual(rows[0]["used_pct"], "90.0")
        self.assertEqual(
            [rows[1][field] for field in ("svm", "volume", "type", "state")],
            ["'=SV", "'+VOL", "'-rw", "'@online"],
        )
        self.assertEqual(rows[2]["used_pct"], "0.0")
        self.assertEqual(
            output.getvalue(),
            f"Wrote {output_path}: 3 volumes, 1 over 85% used\n"
            "  svm-b/hot: 90.0% used\n",
        )


class SnapshotAuditTests(unittest.TestCase):
    def test_snapshot_age_and_space_are_reported_deterministically(self):
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 23, tzinfo=tz)

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "records": [
                        {
                            "svm": {"name": "svm1"},
                            "volume": {"name": "vol1"},
                            "name": "old",
                            "create_time": "2026-09-01T00:00:00Z",
                            "space": {"total": 1_500_000_000},
                        },
                        {
                            "svm": {"name": "svm2"},
                            "volume": {"name": "vol2"},
                            "name": "recent",
                            "create_time": "2026-10-01T00:00:00Z",
                            "space": {"total": 1_000_000_000},
                        },
                    ]
                }

        output = io.StringIO()
        with (
            patch.object(snapshot, "datetime", FixedDateTime),
            patch.object(snapshot.requests, "get", return_value=FakeResponse()) as request,
            patch.object(
                sys,
                "argv",
                [
                    "ontap_snapshot_audit.py",
                    "--cluster",
                    "offline.example",
                    "--max-age-days",
                    "30",
                ],
            ),
            patch.dict(os.environ, {"ONTAP_PASSWORD": "not-a-real-secret"}),
            contextlib.redirect_stdout(output),
        ):
            snapshot.main()

        self.assertEqual(
            output.getvalue(),
            "2 snapshots, 2.5 GB total\n"
            "1 older than 30 days:\n"
            "  svm1/vol1/old: 52d old\n",
        )
        self.assertEqual(
            request.call_args.args[0],
            "https://offline.example/api/storage/volumes/snapshots",
        )
        self.assertIs(request.call_args.kwargs["verify"], True)


class InfiniBoxReportTests(unittest.TestCase):
    def test_main_writes_volume_rows_and_pool_utilization(self):
        class FakeInfiniBox:
            logged_out = False

            def __init__(self, host, user, password):
                self.host = host

            def get(self, path, params):
                if path == "/volumes":
                    return [
                        {
                            "name": "zeta",
                            "size": 2_000_000_000,
                            "pool": {"id": "p1"},
                            "mapped": False,
                        },
                        {
                            "name": "@vol",
                            "size": 1_000_000_000,
                            "pool": {"id": "p1"},
                            "provtype": " \t=thin",
                            "mapped": True,
                        },
                    ]
                return [
                    {
                        "id": "p1",
                        "name": " +pool",
                        "size": 1_000_000_000_000,
                        "free": 250_000_000_000,
                    }
                ]

            def logout(self):
                type(self).logged_out = True

        output_path = local_test_path(self, ".infinibox_report.csv")
        output = io.StringIO()
        with (
            patch.object(infinidat, "InfiniBox", FakeInfiniBox),
            patch.object(
                sys,
                "argv",
                [
                    "infinidat_infinibox_report.py",
                    "--host",
                    "offline.example",
                    "--output",
                    str(output_path),
                ],
            ),
            patch.dict(os.environ, {"INFINIDAT_PASSWORD": "not-a-real-secret"}),
            contextlib.redirect_stdout(output),
        ):
            infinidat.main()

        with output_path.open(newline="") as report:
            rows = list(csv.DictReader(report))

        self.assertEqual([row["volume"] for row in rows], ["'@vol", "zeta"])
        self.assertEqual(rows[0], {
            "volume": "'@vol",
            "pool": "' +pool",
            "size_gb": "1.0",
            "provtype": "' \t=thin",
            "mapped": "yes",
        })
        self.assertEqual(rows[0]["pool"], "' +pool")
        self.assertIn("1.0TB total, 75.0% used", output.getvalue())
        self.assertIn(f"Wrote {output_path}: 2 volumes", output.getvalue())
        self.assertTrue(FakeInfiniBox.logged_out)

    def test_rest_calls_require_verified_tls(self):
        class Response:
            def __init__(self, body):
                self.body = body

            def raise_for_status(self):
                pass

            def json(self):
                return self.body

        with (
            patch.object(
                infinidat.requests,
                "post",
                side_effect=[
                    Response({"result": {"auth_token": "offline-token"}}),
                    Response({}),
                ],
            ) as post,
            patch.object(
                infinidat.requests,
                "get",
                return_value=Response({"result": []}),
            ) as get,
        ):
            client = infinidat.InfiniBox("offline.example", "user", "password")
            self.assertEqual(client.get("/volumes"), [])
            client.logout()

        self.assertEqual([call.kwargs["verify"] for call in post.call_args_list], [True, True])
        self.assertIs(get.call_args.kwargs["verify"], True)


class FlashArrayReportTests(unittest.TestCase):
    def test_main_writes_volume_inventory_and_logs_out(self):
        class FakeFlashArray:
            logged_out = False

            def __init__(self, array, api_token):
                self.array = array

            def get(self, path, params=None):
                if path == "/arrays":
                    return {
                        "items": [
                            {
                                "name": "array-a",
                                "space": {
                                    "total_physical": 2_000_000_000_000,
                                    "total_used": 500_000_000_000,
                                    "data_reduction": 3.2,
                                },
                            }
                        ]
                    }
                if path == "/volumes":
                    return {
                        "items": [
                            {
                                "name": "-volume",
                                "provisioned": 2_000_000_000,
                                "space": {"total_used": 1_000_000_000},
                                "serial": "\r=SERIAL",
                            },
                            {
                                "name": "alpha",
                                "provisioned": 0,
                                "space": {"total_used": 0},
                                "serial": "S1",
                            },
                        ]
                    }
                return {"items": [{"name": "pg-a"}]}

            def logout(self):
                type(self).logged_out = True

        output_path = local_test_path(self, ".flasharray_report.csv")
        output = io.StringIO()
        with (
            patch.object(pure, "FlashArray", FakeFlashArray),
            patch.object(
                sys,
                "argv",
                [
                    "pure_flasharray_report.py",
                    "--array",
                    "offline.example",
                    "--output",
                    str(output_path),
                ],
            ),
            patch.dict(os.environ, {"PURE_API_TOKEN": "not-a-real-secret"}),
            contextlib.redirect_stdout(output),
        ):
            pure.main()

        with output_path.open(newline="") as report:
            rows = list(csv.DictReader(report))

        self.assertEqual([row["volume"] for row in rows], ["'-volume", "alpha"])
        self.assertEqual(rows[0], {
            "volume": "'-volume",
            "size_gb": "2.0",
            "used_gb": "1.0",
            "serial": "'\r=SERIAL",
        })
        self.assertIn("array-a: 2.0TB total, 25.0% used, 3.2:1 data reduction", output.getvalue())
        self.assertIn("1 protection groups configured", output.getvalue())
        self.assertTrue(FakeFlashArray.logged_out)

    def test_rest_calls_require_verified_tls(self):
        class Response:
            def __init__(self, body):
                self.body = body

            def raise_for_status(self):
                pass

            def json(self):
                return self.body

        with (
            patch.object(
                pure.requests,
                "post",
                side_effect=[
                    Response({"access_token": "offline-token"}),
                    Response({}),
                ],
            ) as post,
            patch.object(
                pure.requests,
                "get",
                return_value=Response({"items": []}),
            ) as get,
        ):
            client = pure.FlashArray("offline.example", "not-a-real-token")
            self.assertEqual(client.get("/volumes"), {"items": []})
            client.logout()

        self.assertEqual([call.kwargs["verify"] for call in post.call_args_list], [True, True])
        self.assertIs(get.call_args.kwargs["verify"], True)


class SecureTransportTests(unittest.TestCase):
    def test_ontap_rest_get_requires_verified_tls(self):
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"records": []}

        with patch.object(ontap.requests, "get", return_value=Response()) as request:
            self.assertEqual(ontap.Ontap("offline.example", "user", "password").get("/storage/volumes"), {
                "records": [],
            })

        self.assertIs(request.call_args.kwargs["verify"], True)

    def test_ssh_rejects_unknown_host_keys(self):
        class FakeStdout:
            def read(self):
                return b"offline output"

        class FakeSSHClient:
            def __init__(self):
                self.loaded_system_keys = False
                self.policy = None
                self.closed = False

            def load_system_host_keys(self):
                self.loaded_system_keys = True

            def set_missing_host_key_policy(self, policy):
                self.policy = policy

            def connect(self, *args, **kwargs):
                pass

            def exec_command(self, command):
                return None, FakeStdout(), None

            def close(self):
                self.closed = True

        client = FakeSSHClient()
        rejecting_policy = object()
        with (
            patch.object(fc.paramiko, "SSHClient", return_value=client, create=True),
            patch.object(
                fc.paramiko,
                "RejectPolicy",
                return_value=rejecting_policy,
                create=True,
            ),
        ):
            result = fc.ssh_run("offline.example", "user", "password", "show status")

        self.assertEqual(result, "offline output")
        self.assertTrue(client.loaded_system_keys)
        self.assertIs(client.policy, rejecting_policy)
        self.assertTrue(client.closed)


class S3OperationsTests(unittest.TestCase):
    def test_audit_reports_encryption_versioning_and_lifecycle_findings(self):
        class FakeS3:
            def get_bucket_encryption(self, **kwargs):
                raise s3.ClientError(
                    {"Error": {"Code": "ServerSideEncryptionConfigurationNotFoundError"}},
                    "GetBucketEncryption",
                )

            def get_bucket_versioning(self, **kwargs):
                return {"Status": "Suspended"}

            def get_bucket_lifecycle_configuration(self, **kwargs):
                raise s3.ClientError(
                    {"Error": {"Code": "NoSuchLifecycleConfiguration"}},
                    "GetBucketLifecycleConfiguration",
                )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            s3.action_audit(FakeS3(), "example")

        self.assertEqual(
            output.getvalue(),
            "Auditing s3://example\n"
            "  encryption: DISABLED\n"
            "  versioning: Suspended\n"
            "  lifecycle: NONE\n"
            "\nFindings: no-encryption, versioning-off, no-lifecycle\n",
        )

    def test_unexpected_api_failures_mark_audit_incomplete(self):
        class FakeS3:
            def get_bucket_encryption(self, **kwargs):
                raise s3.ClientError(
                    {"Error": {"Code": "AccessDenied"}},
                    "GetBucketEncryption",
                )

            def get_bucket_versioning(self, **kwargs):
                raise RuntimeError("offline")

            def get_bucket_lifecycle_configuration(self, **kwargs):
                raise s3.ClientError(
                    {"Error": {"Code": "InternalError"}},
                    "GetBucketLifecycleConfiguration",
                )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            s3.action_audit(FakeS3(), "example")

        self.assertEqual(
            output.getvalue(),
            "Auditing s3://example\n"
            "  encryption: unknown (AccessDenied)\n"
            "  versioning: unknown (offline)\n"
            "  lifecycle: unknown (InternalError)\n"
            "\nAudit incomplete; unknown checks: encryption, versioning, lifecycle\n",
        )
        self.assertNotIn("No findings.", output.getvalue())

    def test_list_aggregates_object_counts_and_sizes(self):
        class FakePaginator:
            def paginate(self, Bucket):
                self.bucket = Bucket
                return [
                    {"Contents": [{"Size": 1_000_000_000}, {"Size": 500_000_000}]},
                    {"Contents": [{"Size": 500_000_000}]},
                ]

        class FakeS3:
            def list_buckets(self):
                return {"Buckets": [{"Name": "bucket-a"}]}

            def get_paginator(self, operation):
                self.operation = operation
                return FakePaginator()

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            s3.action_list(FakeS3())

        self.assertIn("bucket-a", output.getvalue())
        self.assertIn("3 objects", output.getvalue())
        self.assertIn("2.00 GB", output.getvalue())
        self.assertIn("1 buckets, 3 total objects", output.getvalue())


if __name__ == "__main__":
    unittest.main()
