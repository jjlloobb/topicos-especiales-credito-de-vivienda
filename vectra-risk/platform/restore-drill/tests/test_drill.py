"""P-U1-05, NFR-U1-07."""

import json
import os
import subprocess
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tests"))
from drill import INTERNAL_CA, DrillResult, KubectlCommands, main, metrics_body, run_drill  # noqa: E402
from pg_hba_rules import assert_postgres_requires_tls  # noqa: E402


class Fake:
    def __init__(self, verdict="integra", violations=0, fail_on=None, destroy_fails=()):
        self.verdict, self.violations, self.fail_on, self.destroy_fails, self.log = verdict, violations, fail_on, destroy_fails, []

    def create_cluster(self, name, source):
        self.log.append(("create", name, source))
        if self.fail_on == name:
            raise RuntimeError("fallo")

    def destroy_cluster(self, name):
        self.log.append(("destroy", name))
        if name in self.destroy_fails:
            raise RuntimeError("no se pudo destruir")

    def verify_chain(self, cluster):
        if self.fail_on == "verify":
            raise FileNotFoundError("vectra-registry")
        return self.verdict

    def run_case_retention(self, cluster):
        if self.fail_on == "retention":
            raise ValueError("salida no numerica")
        return self.violations

    def reached_lsn(self, cluster):
        return 7


def test_success_requires_integra_and_zero_violations():
    fake = Fake()
    result = run_drill(fake, clock=iter([0.0, 12.0]).__next__)
    assert result == DrillResult(True, 12.0, 0, 7)
    assert fake.log == [
        ("destroy", "restore-case"),
        ("destroy", "restore-registry"),
        ("create", "restore-registry", "registry-db"),
        ("create", "restore-case", "case-db"),
        ("destroy", "restore-case"),
        ("destroy", "restore-registry"),
    ]


def test_chain_not_intact_fails():
    assert not run_drill(Fake(verdict="inconsistente")).success


def test_retention_violations_fail_and_are_reported():
    result = run_drill(Fake(violations=3))
    assert not result.success and result.retention_violations == 3
    assert b"vectra_restore_drill_retention_violations 3\n" in metrics_body(result)


@pytest.mark.parametrize("step", ["restore-registry", "verify", "restore-case", "retention"])
def test_any_exception_is_a_failed_drill_and_destroys_what_was_created(step):
    fake = Fake(fail_on=step)
    result = run_drill(fake)
    assert not result.success
    assert fake.log[-1] == ("destroy", "restore-registry")


def test_cluster_that_timed_out_while_being_created_is_destroyed():
    fake = Fake(fail_on="restore-case")
    run_drill(fake)
    creation = fake.log.index(("create", "restore-case", "case-db"))
    assert ("destroy", "restore-case") in fake.log[creation:]


def test_leftovers_are_destroyed_before_creating():
    fake = Fake()
    run_drill(fake)
    assert fake.log[:2] == [("destroy", "restore-case"), ("destroy", "restore-registry")]


def test_leftovers_that_cannot_be_destroyed_fail_without_creating():
    fake = Fake(destroy_fails=("restore-case",))
    assert not run_drill(fake).success
    assert not [entry for entry in fake.log if entry[0] == "create"]


def test_final_destroy_failure_fails_the_drill_and_tries_the_rest():
    class FailsOnlyAtTheEnd(Fake):
        def destroy_cluster(self, name):
            self.destroy_fails = ("restore-case",) if any(e[0] == "create" for e in self.log) else ()
            super().destroy_cluster(name)

    fake = FailsOnlyAtTheEnd()
    assert not run_drill(fake).success
    assert fake.log[-1] == ("destroy", "restore-registry")


@pytest.fixture
def pushgateway():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_PUT(self):
            received.append((self.path, self.rfile.read(int(self.headers["Content-Length"])).decode()))
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield received, f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_main_pushes_success_and_exits_zero(pushgateway, monkeypatch):
    received, url = pushgateway
    monkeypatch.setenv("PUSHGATEWAY_URL", url)
    assert main(Fake()) == 0
    assert received[0][0] == "/metrics/job/restore-drill"
    assert "vectra_restore_drill_success 1\n" in received[0][1]


def test_main_pushes_failure_and_exits_one_on_any_exception(pushgateway, monkeypatch):
    received, url = pushgateway
    monkeypatch.setenv("PUSHGATEWAY_URL", url)
    assert main(Fake(fail_on="verify")) == 1
    assert "vectra_restore_drill_success 0\n" in received[0][1]


def test_main_exits_one_when_the_push_fails(monkeypatch):
    monkeypatch.setenv("PUSHGATEWAY_URL", "http://127.0.0.1:9")
    assert main(Fake()) == 1


def test_main_exits_one_without_pushgateway_url(monkeypatch):
    monkeypatch.delenv("PUSHGATEWAY_URL", raising=False)
    assert main(Fake()) == 1


def fake_kubectl(tmp_path, monkeypatch, script):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    tool = bin_dir / "kubectl"
    tool.write_text(f"#!/usr/bin/env bash\necho \"$*\" >> {tmp_path}/calls\n{script}\n", encoding="utf-8")
    tool.chmod(0o755)
    if not (bin_dir / "restore-cluster.sh").exists():
        (bin_dir / "restore-cluster.sh").symlink_to(HERE / "restore-cluster.sh")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("RESTORE_IMAGE", "registro.vectra.internal/postgresql@sha256:abc")
    monkeypatch.setenv("BACKUP_DESTINATION", "s3://vectra-backups")
    monkeypatch.setenv("BACKUP_ENDPOINT", "http://minio.vectra-data.svc:9000")
    return tmp_path / "calls"


def test_lsn_is_read_over_f114_with_the_verifier_role(monkeypatch):
    seen = {}

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, query):
            seen["query"] = query

        def fetchone(self):
            return (1234,)

    class Connection(Cursor):
        def cursor(self):
            return Cursor()

    def connect(**kwargs):
        seen.update(kwargs)
        return Connection()

    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=connect))
    monkeypatch.setenv("LSN_USER", "registry_verifier")
    monkeypatch.setenv("LSN_PASSWORD", "x")
    assert KubectlCommands().reached_lsn("restore-registry") == 1234
    assert seen["host"] == "restore-registry-rw.vectra-restore-drill.svc" and seen["dbname"] == "registry"
    assert seen["user"] == "registry_verifier" and seen["sslmode"] == "verify-full"
    assert seen["sslrootcert"] == INTERNAL_CA
    assert "COALESCE(pg_last_wal_replay_lsn(), pg_current_wal_lsn())" in seen["query"]


def test_the_drill_role_cannot_exec_or_read_pods():
    documents = list(yaml.safe_load_all((HERE / "cronjob.yaml").read_text(encoding="utf-8")))
    role = next(d for d in documents if d and d["kind"] == "Role")
    resources = {r for rule in role["rules"] for r in rule["resources"]}
    assert "pods/exec" not in resources and "pods" not in resources


def test_the_lsn_secret_is_delivered_to_the_namespace_of_the_drill():
    values = yaml.safe_load((HERE.parent / "data/chart/values.yaml").read_text(encoding="utf-8"))
    assert "vectra-restore-drill" in values["roleConsumers"]["registry_verifier"]
    assert "pg-role-registry-verifier" in (HERE / "cronjob.yaml").read_text(encoding="utf-8")


def manifest(tmp_path, monkeypatch, *extra):
    """El Cluster que el script enviaria a `kubectl create -f -`."""
    calls = fake_kubectl(tmp_path, monkeypatch, f'[ "$1" = create ] && cat > {tmp_path}/manifest; true')
    subprocess.run([str(HERE / "restore-cluster.sh"), "create", *extra], check=True)
    assert "wait clusters.postgresql.cnpg.io" in calls.read_text(encoding="utf-8")
    return yaml.safe_load((tmp_path / "manifest").read_text(encoding="utf-8"))


def test_restore_cluster_uses_the_image_labels_and_annotations_from_its_contract(tmp_path, monkeypatch):
    spec = manifest(tmp_path, monkeypatch, "restore-registry", "registry-db")["spec"]
    assert spec["imageName"] == "registro.vectra.internal/postgresql@sha256:abc"
    assert spec["inheritedMetadata"]["labels"]["app.kubernetes.io/name"] == "restore-cluster"
    assert spec["inheritedMetadata"]["annotations"]["config.linkerd.io/skip-inbound-ports"] == "8000"
    external = spec["externalClusters"][0]["barmanObjectStore"]
    assert external["destinationPath"] == "s3://vectra-backups/registry-db"
    assert external["endpointURL"] == "http://minio.vectra-data.svc:9000"


@pytest.mark.parametrize(("source", "size"), [("registry-db", "100Gi"), ("case-db", "50Gi")])
def test_storage_size_depends_on_the_source(tmp_path, monkeypatch, source, size):
    monkeypatch.delenv("RESTORE_STORAGE_SIZE", raising=False)
    assert manifest(tmp_path, monkeypatch, "c", source)["spec"]["storage"]["size"] == size


def test_storage_size_from_environment_then_argument(tmp_path, monkeypatch):
    monkeypatch.setenv("RESTORE_STORAGE_SIZE", "2Gi")
    assert manifest(tmp_path, monkeypatch, "c", "registry-db")["spec"]["storage"]["size"] == "2Gi"
    assert manifest(tmp_path, monkeypatch, "c", "registry-db", "3Gi")["spec"]["storage"]["size"] == "3Gi"


def test_unknown_source_without_size_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("RESTORE_STORAGE_SIZE", raising=False)
    fake_kubectl(tmp_path, monkeypatch, "true")
    assert subprocess.run([str(HERE / "restore-cluster.sh"), "create", "c", "otra-db"], check=False, capture_output=True).returncode != 0


def test_f75_policy_lists_only_on_buckets_and_reads_only_objects():
    policy = json.loads((HERE / "bucket-policy-f75.json").read_text(encoding="utf-8"))
    for statement in policy["Statement"]:
        assert statement["Effect"] == "Allow"
        if statement["Action"] == ["s3:ListBucket"]:
            assert all("/" not in r.removeprefix("arn:aws:s3:::") for r in statement["Resource"])
            assert statement["Condition"]
        else:
            assert statement["Action"] == ["s3:GetObject"]
            assert all("/" in r.removeprefix("arn:aws:s3:::") for r in statement["Resource"])
    assert "vectra-wal" not in json.dumps(policy)


def test_metrics_names():
    body = metrics_body(DrillResult(True, 1.5, 0, 9)).decode()
    assert "vectra_restore_drill_success 1" in body and "vectra_restore_drill_duration_seconds 1.500" in body and "vectra_restore_drill_lsn 9" in body


def test_the_drill_mounts_the_internal_ca_and_the_ephemeral_cluster_serves_a_cert_signed_by_it():
    documents = [d for d in yaml.safe_load_all((HERE / "cronjob.yaml").read_text(encoding="utf-8")) if d]
    pod = next(d for d in documents if d["kind"] == "CronJob")["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    volume = next(v for v in pod["volumes"] if v["name"] == "internal-ca")
    assert volume["configMap"]["name"] == "vectra-internal-ca"
    mount = next(m for m in pod["containers"][0]["volumeMounts"] if m["name"] == "internal-ca")
    assert mount["readOnly"] is True
    bundles = yaml.safe_load_all((HERE.parent / "mesh/certificates.yaml").read_text(encoding="utf-8"))
    bundle = next(d for d in bundles if d and d["kind"] == "Bundle" and d["metadata"]["name"] == "vectra-internal-ca")
    assert f"{mount['mountPath']}/{bundle['spec']['target']['configMap']['key']}" == INTERNAL_CA
    certificate = next(d for d in documents if d["kind"] == "Certificate")
    assert certificate["spec"]["issuerRef"] == {"name": "vectra-internal-ca", "kind": "ClusterIssuer"}
    assert certificate["metadata"]["namespace"] == "vectra-restore-drill"
    assert "*.vectra-restore-drill.svc" in certificate["spec"]["dnsNames"]
    script = (HERE / "restore-cluster.sh").read_text(encoding="utf-8")
    assert f"serverTLSSecret: {certificate['spec']['secretName']}" in script
    assert f"serverCASecret: {certificate['spec']['secretName']}" in script


def test_the_ephemeral_cluster_rejects_plain_text_connections(tmp_path, monkeypatch):
    for name, source in (("restore-registry", "registry-db"), ("restore-case", "case-db")):
        assert_postgres_requires_tls(manifest(tmp_path, monkeypatch, name, source), name)
