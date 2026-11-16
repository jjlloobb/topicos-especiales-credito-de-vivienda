"""U01-T16: la siembra recupera del cluster lo que la boveda ya no tiene (un reinicio de la maquina la deja vacia), informa sin secretos y refresca los ExternalSecret de `identity/`.

Nada toca un cluster: `kubectl` es un ejecutor falso (`FakeCluster`) y la boveda un diccionario. Todos los valores son de mentira.
"""

import base64
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_paths as vp  # noqa: E402
from test_identity_seed import CA_PEM, FakeVault  # noqa: E402

SEED_VAULT = Path(os.environ.get("SEED_VAULT_SCRIPT", HERE / "seed-vault.sh"))
REAL_CLUSTER_SECRETS = vp.ClusterSecrets
#: Valores de mentira, en constantes y no como literales junto a `["password"]` (la regla S105 de ruff).
FAKE_ONE = "clave-de-mentira"
FAKE_SAME = "valor-de-mentira"
FAKE_THREE = "glsa-de-mentira"
LITERAL = re.compile(r"^\s*\{\{\s*\.(\w+)\s*\}\}\s*$")


def ok(stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


class FakeCluster:
    """`kubectl get externalsecrets -A -o json` y `kubectl get secret <n> -n <ns> -o json`, sobre diccionarios. Anota cada orden."""

    def __init__(self, external_secrets: list[dict], secrets: dict[tuple[str, str], dict[str, str]]) -> None:
        self.external_secrets = external_secrets
        self.secrets = secrets
        self.calls: list[list[str]] = []

    def run(self, command: list[str], stdin: str | None) -> SimpleNamespace:
        self.calls.append(command)
        assert command[:4] == ["kubectl", "--context", "kind-vectra", "get"], command
        if "externalsecrets.external-secrets.io" in command:
            return ok(json.dumps({"items": self.external_secrets}))
        name, namespace = command[command.index("secret") + 1], command[command.index("-n") + 1]
        found = self.secrets.get((namespace, name))
        if found is None:
            return SimpleNamespace(returncode=1, stdout="", stderr=f'Error from server (NotFound): secrets "{name}" not found')
        return ok(json.dumps({"data": {key: base64.b64encode(value.encode()).decode() for key, value in found.items()}}))

    def recoverer(self) -> "vp.Recoverer":
        return vp.Recoverer(vp.ClusterSecrets("kind-vectra", self.run))


def external_secret(namespace: str, name: str, items: list[tuple[str, str, str]], template: dict | None = None) -> dict:
    """items: (secretKey, ruta en la boveda, propiedad)."""
    target: dict = {"name": name}
    if template is not None:
        target["template"] = template
    data = [{"secretKey": key, "remoteRef": {"key": path, "property": prop}} for key, path, prop in items]
    return {"apiVersion": "external-secrets.io/v1", "kind": "ExternalSecret", "metadata": {"name": name, "namespace": namespace}, "spec": {"target": target, "data": data}}


def cluster_of(documents: list[dict], values: dict[tuple[str, str], str]) -> FakeCluster:
    """Los Secret que ESO habria dejado para esos ExternalSecret: copia literal, o texto compuesto si el valor pasa por una plantilla."""
    secrets: dict[tuple[str, str], dict[str, str]] = {}
    for document in documents:
        target = document["spec"]["target"]
        namespace, name = document["metadata"]["namespace"], target.get("name") or document["metadata"]["name"]
        template_data = (target.get("template") or {}).get("data") or {}
        content = secrets.setdefault((namespace, name), {})
        by_key = {item["secretKey"]: values[(item["remoteRef"]["key"], item["remoteRef"]["property"])] for item in document["spec"]["data"]}
        if not template_data:
            content.update(by_key)
            continue
        for key, text in template_data.items():
            match = LITERAL.match(text)
            content[key] = by_key[match.group(1)] if match else "compuesto-" + "-".join(by_key.values())
    return FakeCluster(documents, secrets)


# --- CA-1: recuperar antes de generar ---------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def platform_documents() -> list[dict]:
    return vp.platform_external_secrets()


def fake_value(path: str, prop: str, users: dict[str, str]) -> str:
    fixed = vp.fixed_value(path, prop, users)
    return fixed if fixed is not None else f"valor-de-mentira/{path}/{prop}"


def test_recover_with_an_empty_vault_gives_back_every_value_and_generates_none(platform_documents, monkeypatch):
    """El caso real: boveda vacia y los Secret presentes. Lo sembrado es lo que habia; nada se genera al azar."""
    users = vp.minio_users(platform_documents)
    refs = vp.collect(platform_documents)
    values = {(path, prop): fake_value(path, prop, users) for path, props in refs.items() for prop in props}
    cluster = cluster_of(platform_documents, values)
    monkeypatch.setattr(vp.secrets, "token_hex", lambda *_: pytest.fail("se genero un valor al azar"))
    report = vp.Report()
    planned = vp.plan(refs, users, lambda _path: {}, cluster.recoverer(), report)
    assert planned == {path: {prop: values[(path, prop)] for prop in props} for path, props in refs.items()}
    assert [path for path, line in report.paths.items() if line.generated] == []
    assert sum(line.recovered for line in report.paths.values()) > 20


def test_recover_property_without_a_secret_is_generated_and_reported():
    refs = {"minio/root": {"accessKey", "password"}}
    documents = [external_secret("vectra-data", "minio-root", [("rootUser", "minio/root", "accessKey")])]
    cluster = cluster_of(documents, {("minio/root", "accessKey"): "usuario-de-mentira"})
    report = vp.Report()
    planned = vp.plan(refs, {}, lambda _path: {}, cluster.recoverer(), report)
    assert planned["minio/root"]["accessKey"] == "usuario-de-mentira"
    assert len(planned["minio/root"]["password"]) == 48  # token_hex(24): nuevo
    line = report.paths["minio/root"]
    assert (line.kept, line.recovered, line.generated) == (0, 1, ["password"])


def test_recover_a_secret_that_exists_without_the_key_does_not_count_as_a_source():
    refs = {"grafana/admin": {"password"}}
    documents = [external_secret("vectra-observability", "grafana-admin", [("admin-password", "grafana/admin", "password")])]
    cluster = FakeCluster(documents, {("vectra-observability", "grafana-admin"): {"otra-clave": "x"}})
    report = vp.Report()
    vp.plan(refs, {}, lambda _path: {}, cluster.recoverer(), report)
    assert report.paths["grafana/admin"].generated == ["password"]


def test_recover_does_not_copy_a_value_that_goes_through_a_template_and_says_so():
    """Una DSN, un archivo: el valor del Secret no es el de la boveda. Solo la copia literal (`{{ .x }}` entera) se recupera."""
    refs = {"edge/valkey": {"exporter", "ratelimit"}}
    template = {"data": {"users.acl": "user ratelimit on >{{ .ratelimit }} ~*\n", "exporter-password": "{{ .exporter }}"}}
    documents = [external_secret("vectra-edge", "valkey-acl", [("ratelimit", "edge/valkey", "ratelimit"), ("exporter", "edge/valkey", "exporter")], template)]
    cluster = cluster_of(documents, {("edge/valkey", "ratelimit"): "clave-de-mentira-1", ("edge/valkey", "exporter"): "clave-de-mentira-2"})
    report = vp.Report()
    planned = vp.plan(refs, {}, lambda _path: {}, cluster.recoverer(), report)
    assert planned["edge/valkey"]["exporter"] == "clave-de-mentira-2"  # copia literal en otra clave del Secret
    assert planned["edge/valkey"]["ratelimit"] != "clave-de-mentira-1" and "clave-de-mentira-1" not in planned["edge/valkey"]["ratelimit"]
    line = report.paths["edge/valkey"]
    assert line.generated == ["ratelimit"] and line.templated == {"ratelimit": ["vectra-edge/valkey-acl"]}
    assert line.recovered == 1


def test_recover_a_template_that_only_sets_the_type_is_still_a_literal_copy():
    refs = {"postgres/roles/app": {"password"}}
    documents = [external_secret("vectra-data", "pg-role-app", [("password", "postgres/roles/app", "password")], {"type": "kubernetes.io/basic-auth"})]
    planned = vp.plan(refs, {}, lambda _path: {}, cluster_of(documents, {("postgres/roles/app", "password"): FAKE_ONE}).recoverer(), vp.Report())
    assert planned["postgres/roles/app"]["password"] == FAKE_ONE


def test_recover_two_secrets_with_different_values_stop_the_seed_without_choosing():
    refs = {"minio/root": {"password"}}
    documents = [
        external_secret("vectra-data", "minio-root", [("rootPassword", "minio/root", "password")]),
        external_secret("vectra-app", "minio-root-copia", [("clave", "minio/root", "password")]),
    ]
    cluster = FakeCluster(documents, {("vectra-data", "minio-root"): {"rootPassword": "valor-de-mentira-A"}, ("vectra-app", "minio-root-copia"): {"clave": "valor-de-mentira-B"}})
    with pytest.raises(vp.RecoveryConflict) as raised:
        vp.plan(refs, {}, lambda _path: {}, cluster.recoverer(), vp.Report())
    message = str(raised.value)
    assert "minio/root" in message and "password" in message and "vectra-data/minio-root" in message and "vectra-app/minio-root-copia" in message
    assert "valor-de-mentira" not in message  # el mensaje dice donde, nunca el valor


def test_recover_two_secrets_with_the_same_value_are_not_a_conflict():
    refs = {"minio/root": {"password"}}
    documents = [
        external_secret("vectra-data", "minio-root", [("rootPassword", "minio/root", "password")]),
        external_secret("vectra-app", "minio-root-copia", [("clave", "minio/root", "password")]),
    ]
    cluster = FakeCluster(documents, {("vectra-data", "minio-root"): {"rootPassword": FAKE_SAME}, ("vectra-app", "minio-root-copia"): {"clave": FAKE_SAME}})
    assert vp.plan(refs, {}, lambda _path: {}, cluster.recoverer(), vp.Report())["minio/root"]["password"] == FAKE_SAME


def test_recover_keeps_what_the_vault_has_and_reads_the_cluster_only_when_something_is_missing():
    refs = {"minio/root": {"password"}}
    cluster = FakeCluster([], {})
    report = vp.Report()
    planned = vp.plan(refs, {}, lambda _path: {"password": "valor-de-la-boveda"}, cluster.recoverer(), report)
    assert planned["minio/root"] == {"password": "valor-de-la-boveda"} and cluster.calls == []
    assert (report.paths["minio/root"].kept, report.paths["minio/root"].recovered) == (1, 0)


def test_recover_fixed_values_are_not_taken_from_the_cluster():
    refs = {"postgres/roles/app": {"username"}}
    documents = [external_secret("vectra-data", "pg-role-app", [("username", "postgres/roles/app", "username")])]
    cluster = cluster_of(documents, {("postgres/roles/app", "username"): "otro-nombre"})
    report = vp.Report()
    assert vp.plan(refs, {}, lambda _path: {}, cluster.recoverer(), report)["postgres/roles/app"]["username"] == "app"
    assert report.paths["postgres/roles/app"].fixed == 1


def test_recover_the_grafana_token_comes_from_the_secret_and_the_placeholder_stays_without_it():
    refs = {"grafana/folder-permissions": {"token"}}
    documents = [external_secret("vectra-observability", "grafana-folder-permissions-token", [("GRAFANA_TOKEN", "grafana/folder-permissions", "token")])]
    with_token = cluster_of(documents, {("grafana/folder-permissions", "token"): FAKE_THREE})
    assert vp.plan(refs, {}, lambda _path: {}, with_token.recoverer(), vp.Report())["grafana/folder-permissions"]["token"] == FAKE_THREE
    report = vp.Report()
    without = FakeCluster(documents, {})
    assert vp.plan(refs, {}, lambda _path: {}, without.recoverer(), report)["grafana/folder-permissions"]["token"] == vp.TOKEN_PENDING
    assert report.paths["grafana/folder-permissions"].generated == ["token"]


def test_recover_a_failing_kubectl_stops_but_a_cluster_without_the_crd_just_has_nothing_to_recover():
    broken = SimpleNamespace(returncode=1, stdout="", stderr="Unable to connect to the server")
    with pytest.raises(RuntimeError, match="Unable to connect"):
        vp.Recoverer(vp.ClusterSecrets("kind-vectra", lambda *_: broken)).find("minio/root", "password")
    no_crd = SimpleNamespace(returncode=1, stdout="", stderr="error: the server doesn't have a resource type \"externalsecrets\"")
    assert vp.Recoverer(vp.ClusterSecrets("kind-vectra", lambda *_: no_crd)).find("minio/root", "password") is None


# --- CA-1: U2 (identity), el flujo completo y los pares de llaves -------------------------------------------------------------


VECTRA = HERE.parents[1]
CHART_VALUES = ("bias-monitoring", "case-management", "governance", "product-metrics", "scoring-explainability")


def declared_clients() -> set[str]:
    """Los clientes de U3 a U11 que un chart declara con su `ExternalSecret` de `private-key` (`clientId:` o `vaultKey: identity/clients/<id>` en sus `values.yaml`), sacados del repositorio."""
    found: set[str] = set()
    for chart in CHART_VALUES:
        text = (VECTRA / chart / "chart/values.yaml").read_text(encoding="utf-8")
        found |= set(re.findall(r"clientId:\s*([a-z][a-z-]+)", text)) | set(re.findall(r"vaultKey:\s*identity/clients/([a-z][a-z-]+)", text))
    return found


#: Clientes con cuenta de servicio cuya privada ningun `Secret` guarda: `identity-edge` solo declara `keycloak-config-cli` y `keycloak-reader`, y los charts los de arriba (F-01).
NEVER_IN_A_SECRET = {"channel", "channel-simulator", "verification-reader"}


def identity_cluster(old: FakeVault) -> FakeCluster:
    """Los ExternalSecret reales de U2 mas los `*-client` que los charts de U3 a U11 declaran de verdad (uno en `vectra-app` por cliente declarado), con los Secret que dejaron."""
    values = {(path, prop): value for path, data in old.store.items() for prop, value in data.items()}
    documents = vp.identity_external_secrets()
    for client in sorted(declared_clients() & set(vp.service_account_clients())):
        path = f"{vp.CLIENTS_PREFIX}{client}"
        documents.append(external_secret("vectra-app", f"{client}-client", [("private-key", path, "private-key")]))
    return cluster_of(documents, values)


def test_recover_the_clients_without_a_secret_are_exactly_the_three_the_charts_never_declare():
    """F-01: la prueba no inventa un `*-client` por cliente: los que ningun chart ni identity-edge declaran se quedan sin Secret."""
    in_identity_edge = {
        item["remoteRef"]["key"].removeprefix(vp.CLIENTS_PREFIX)
        for document in vp.identity_external_secrets()
        for item in document["spec"]["data"]
        if item["remoteRef"]["key"].startswith(vp.CLIENTS_PREFIX) and item["remoteRef"]["property"] == "private-key"
    }
    with_secret = declared_clients() | in_identity_edge
    assert set(vp.service_account_clients()) - with_secret == NEVER_IN_A_SECRET


def run_identity(vault: FakeVault, cluster: FakeCluster, keys_dir: Path, report: "vp.Report | None" = None) -> list[str]:
    written, _ = vp.seed_identity(vault, lambda: CA_PEM, keys_dir, cluster.recoverer(), report)
    return written


def test_recover_identity_with_an_empty_vault_gives_back_the_same_pairs_and_secrets(tmp_path):
    old = FakeVault()
    run_identity(old, FakeCluster([], {}), tmp_path / "antes")
    cluster = identity_cluster(old)
    new, report = FakeVault(), vp.Report()
    run_identity(new, cluster, tmp_path / "despues", report)
    for path, data in old.store.items():
        for prop, value in data.items():
            if (path, prop) in {("identity/clients/grafana", "jwks"), ("identity/break-glass", "BREAK_GLASS_PASSWORD")} or path.removeprefix(vp.CLIENTS_PREFIX) in NEVER_IN_A_SECRET:
                continue  # el primero solo vive dentro de una plantilla (`| toJson`); el segundo no lo lee ningun ExternalSecret: se generan y se informan, abajo
            if path == "edge/valkey" and prop not in {"exporter", "sentinel-ratelimit"}:
                continue  # solo viven dentro de archivos compuestos
            assert new.store[path][prop] == value, (path, prop)
    generated = {path: line.generated for path, line in report.paths.items() if line.generated}
    assert generated == {
        "identity/break-glass": ["BREAK_GLASS_PASSWORD"],
        "identity/clients/channel": ["jwks", "private-key"],
        "identity/clients/channel-simulator": ["jwks", "private-key"],
        "identity/clients/grafana": ["jwks"],
        "identity/clients/verification-reader": ["jwks", "private-key"],
        "edge/valkey": ["ratelimit", "replication", "sentinel", "sentinel-peer"],
    }  # las seis rutas que el operador debe esperar


def test_recover_identity_the_private_key_and_its_jwks_stay_the_same_pair(tmp_path):
    old = FakeVault()
    run_identity(old, FakeCluster([], {}), tmp_path / "antes")
    new = FakeVault()
    run_identity(new, identity_cluster(old), tmp_path / "despues")
    for client in vp.service_account_clients():
        data = new.store[f"{vp.CLIENTS_PREFIX}{client}"]
        assert json.loads(data["jwks"]) == json.loads(vp.jwks_text(vp.load_private(data["private-key"])))
        if client not in NEVER_IN_A_SECRET:  # esos tres no tienen Secret: par nuevo, pero entero (arriba)
            assert data == old.store[f"{vp.CLIENTS_PREFIX}{client}"]


def test_recover_identity_a_client_without_its_private_key_gets_a_whole_new_pair_and_it_is_reported(tmp_path):
    """Si la privada no esta en ningun Secret, no se rescata el `jwks` suelto (la privada nueva no le correspondería): par nuevo, y se dice."""
    old = FakeVault()
    run_identity(old, FakeCluster([], {}), tmp_path / "antes")
    cluster = identity_cluster(old)
    assert ("vectra-app", "channel-client") not in cluster.secrets  # ningun chart lo declara (F-01)
    new, report = FakeVault(), vp.Report()
    run_identity(new, cluster, tmp_path / "despues", report)
    path = "identity/clients/channel"
    assert new.store[path]["private-key"] != old.store[path]["private-key"]
    assert json.loads(new.store[path]["jwks"]) == json.loads(vp.jwks_text(vp.load_private(new.store[path]["private-key"])))
    assert report.paths[path].generated == ["jwks", "private-key"]


def test_recover_identity_a_jwks_that_does_not_match_the_recovered_private_key_stops(tmp_path):
    old = FakeVault()
    run_identity(old, FakeCluster([], {}), tmp_path / "antes")
    other = vp.jwks_text(vp.load_private(old.store["identity/clients/case-service"]["private-key"]))
    documents = [
        external_secret("vectra-app", "channel-client", [("private-key", "identity/clients/channel", "private-key")]),
        external_secret("vectra-identity", "jwks-channel", [("jwks", "identity/clients/channel", "jwks")]),
    ]
    cluster = FakeCluster(documents, {("vectra-app", "channel-client"): {"private-key": old.store["identity/clients/channel"]["private-key"]}, ("vectra-identity", "jwks-channel"): {"jwks": other}})
    refs = {"identity/clients/channel": {"jwks", "private-key"}}
    with pytest.raises(RuntimeError, match="no corresponde"):
        vp.plan_identity(refs, lambda _path: {}, lambda: CA_PEM, cluster.recoverer(), vp.Report())


def test_recover_identity_a_vault_with_everything_reads_nothing_from_the_cluster(tmp_path):
    seeded = FakeVault()
    run_identity(seeded, FakeCluster([], {}), tmp_path / "a")
    cluster = FakeCluster([], {})
    assert run_identity(seeded, cluster, tmp_path / "b") == [] and cluster.calls == []


# --- CA-2: el informe, sin secretos ------------------------------------------------------------------------------------------


#: Nombres y direcciones fijas (`case_app`, `admin`, la URL del relay): no son secretos.
NOT_SECRET = {"username", "user", "accessKey", "access_key_id", "url"}


def secrets_of(vault: FakeVault) -> set[str]:
    return {value for data in vault.store.values() for prop, value in data.items() if len(value) >= 8 and prop not in NOT_SECRET}


def test_report_says_per_path_what_was_kept_recovered_and_generated_and_never_a_value(platform_documents, monkeypatch, capsys):
    users = vp.minio_users(platform_documents)
    refs = vp.collect(platform_documents)
    values = {(path, prop): fake_value(path, prop, users) for path, props in refs.items() for prop in props}
    cluster = cluster_of(platform_documents, values)
    for document in platform_documents:  # `minio/governance` sin Secret: se genera
        if any(item["remoteRef"]["key"] == "minio/governance" for item in document["spec"]["data"]):
            cluster.secrets.pop((document["metadata"]["namespace"], document["spec"]["target"]["name"]), None)
    vault = FakeVault({"minio/root": {"password": "valor-ya-en-la-boveda"}})
    monkeypatch.setattr(vp, "Vault", lambda *_: vault)
    monkeypatch.setattr(vp, "ClusterSecrets", lambda context: REAL_CLUSTER_SECRETS(context, cluster.run))
    assert vp.main(["vault_paths.py", "seed", "kind-vectra", "root"]) == 0
    out = capsys.readouterr()
    text = out.out + out.err
    assert "minio/root: conservadas 1, recuperadas 1, generadas 0" in text, text
    assert "minio/governance: conservadas 0, recuperadas 0, generadas 1 (secretKey), fijas 1" in text, text
    assert any(vault.store[p].get("password") for p in vault.store) and secrets_of(vault)
    for value in secrets_of(vault) | {"valor-ya-en-la-boveda"}:
        assert value not in text


def test_report_of_identity_lists_the_generated_names_and_no_value(tmp_path, monkeypatch, capsys):
    old = FakeVault()
    run_identity(old, FakeCluster([], {}), tmp_path / "antes")
    cluster = identity_cluster(old)
    new = FakeVault()
    monkeypatch.setattr(vp, "Vault", lambda *_: new)
    monkeypatch.setattr(vp, "ClusterSecrets", lambda context: REAL_CLUSTER_SECRETS(context, cluster.run))
    monkeypatch.setattr(vp, "ca_from_cluster", lambda *_: lambda: CA_PEM)
    assert vp.main(["vault_paths.py", "seed-identity", "kind-vectra", "root", str(tmp_path / "llaves")]) == 0
    out = capsys.readouterr()
    text = out.out + out.err
    assert "identity/clients/grafana: conservadas 0, recuperadas 0, generadas 1 (jwks)" in text
    assert re.search(r"edge/valkey: conservadas 0, recuperadas 2, generadas 4 \(ratelimit, replication, sentinel, sentinel-peer\)", text), text
    assert "plantilla" in text  # dice por que no se recuperaron
    for value in secrets_of(new) | secrets_of(old):
        assert value not in text
    assert "BEGIN" not in text


def test_report_when_everything_is_recovered_says_there_is_nothing_to_realign():
    report = vp.Report()
    report.path("a/b").recovered = 2
    assert any("nada que realinear" in line for line in report.lines())
    report.path("a/c").generated.append("clave")
    assert not any("nada que realinear" in line for line in report.lines())
    assert any("a/c" in line and "(clave)" in line for line in report.lines())


# --- CA-3: los namespaces que leen `identity/` --------------------------------------------------------------------------------


def live_external_secrets() -> list[dict]:
    paths = vp.identity_refs(vp.identity_external_secrets())
    documents = list(vp.identity_external_secrets())
    for namespace in ("vectra-app", "vectra-staging", "vectra-mock"):
        documents.append(external_secret(namespace, "scoring-service-client", [("private-key", "identity/clients/scoring-service", "private-key")]))
    documents.append(external_secret("vectra-data", "minio-root", [("rootPassword", "minio/root", "password")]))  # no lee identity/
    assert paths
    return documents


def test_namespaces_are_the_ones_whose_external_secrets_read_identity_paths():
    cluster = FakeCluster(live_external_secrets(), {})
    namespaces = cluster.recoverer().identity_namespaces(set(vp.identity_refs(vp.identity_external_secrets())))
    assert namespaces == sorted({"vectra-identity", "vectra-edge", "envoy-gateway-system", "vectra-app", "vectra-staging", "vectra-mock"})
    assert "vectra-data" not in namespaces


def test_namespaces_the_script_annotates_each_one_and_only_those(tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "kubectl").write_text(FAKE_KUBECTL, encoding="utf-8")
    (fake / "kubectl").chmod(0o755)
    (tmp_path / "ca.pem").write_text(CA_PEM, encoding="utf-8")
    (tmp_path / "externalsecrets.json").write_text(json.dumps({"items": live_external_secrets()}), encoding="utf-8")
    uv = shutil.which("uv")
    assert uv
    env = {**os.environ, "PATH": f"{fake}:{Path(uv).parent}:/usr/bin:/bin", "FAKE_DIR": str(tmp_path), "VECTRA_E2E_KEYS_DIR": str(tmp_path / "llaves")}
    result = subprocess.run([str(SEED_VAULT), "identity"], env=env, capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "kubectl.log").read_text(encoding="utf-8").splitlines()
    annotated = sorted(re.search(r"-n (\S+)", line).group(1) for line in log if "annotate" in line)  # type: ignore[union-attr]
    assert annotated == sorted({"vectra-identity", "vectra-edge", "envoy-gateway-system", "vectra-app", "vectra-staging", "vectra-mock"})
    assert all("--all" in line and "force-sync=" in line for line in log if "annotate" in line)
    assert "conservadas" in result.stdout  # el informe llega al operador por el guion


FAKE_KUBECTL = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_DIR/kubectl.log"
all="$*"
case "$all" in
  *"get crd"*) exit 0 ;;
  *"get externalsecrets"*) if [ -f "$FAKE_DIR/es-falla" ]; then echo "Unable to connect to the server" >&2; exit 1; fi; cat "$FAKE_DIR/externalsecrets.json" ;;
  *"get secret vectra-internal-ca"*) base64 -w0 < "$FAKE_DIR/ca.pem" ;;
  *"get secret "*) echo 'Error from server (NotFound): secrets not found' >&2; exit 1 ;;
  *"kv get"*)
    path="${all##*secret/}"
    file="$FAKE_DIR/vault/$path.json"
    if [ -f "$file" ]; then printf '{"data":{"data":%s}}' "$(cat "$file")"; else exit 2; fi ;;
  *"kv put"*)
    path="${all##*secret/}"; path="${path% -}"
    mkdir -p "$(dirname "$FAKE_DIR/vault/$path")"
    cat > "$FAKE_DIR/vault/$path.json" ;;
esac
"""


def test_namespaces_do_not_come_from_a_hand_written_list_in_the_script():
    text = SEED_VAULT.read_text(encoding="utf-8")
    assert "vectra-identity vectra-edge envoy-gateway-system" not in text and "identity-namespaces" in text


# --- ronda 2 ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["{{ .pw }}\n", "  {{ .pw }}", "{{ .pw }} ", "x{{ .pw }}", "{{ .pw }}{{ .pw }}", "{{ .pw | toJson }}"])
def test_recover_a_template_with_anything_around_the_value_is_not_a_literal_copy(text):
    """F-02: ESO conserva el texto que rodea a `{{ }}`: el valor del Secret no seria el de la boveda. Solo `{{ .clave }}` exacto es copia."""
    refs = {"minio/root": {"password"}}
    documents = [external_secret("vectra-data", "minio-root", [("pw", "minio/root", "password")], {"data": {"CLAVE": text}})]
    cluster = FakeCluster(documents, {("vectra-data", "minio-root"): {"CLAVE": "VALOR-" + text}})
    assert cluster.recoverer().find("minio/root", "password") is None
    report = vp.Report()
    vp.plan(refs, {}, lambda _path: {}, cluster.recoverer(), report)
    assert report.paths["minio/root"].generated == ["password"] and report.paths["minio/root"].templated


def test_recover_a_template_with_only_the_value_inside_the_braces_is_a_literal_copy():
    documents = [external_secret("vectra-data", "minio-root", [("pw", "minio/root", "password")], {"data": {"CLAVE": "{{ .pw }}"}})]
    assert FakeCluster(documents, {("vectra-data", "minio-root"): {"CLAVE": FAKE_SAME}}).recoverer().find("minio/root", "password") == FAKE_SAME


def test_recover_a_secret_that_is_not_utf8_stops_with_a_message_that_quotes_no_byte():
    """F-05: el error nombra el Secret y la clave, nunca un byte del valor."""
    documents = [external_secret("vectra-data", "minio-root", [("pw", "minio/root", "password")])]
    cluster = FakeCluster(documents, {})

    def run(command, stdin):
        if "externalsecrets.external-secrets.io" in command:
            return ok(json.dumps({"items": documents}))
        return ok(json.dumps({"data": {"pw": base64.b64encode(b"\xff\xfe0x41").decode()}}))

    with pytest.raises(RuntimeError) as raised:
        vp.Recoverer(vp.ClusterSecrets("kind-vectra", run)).find("minio/root", "password")
    message = str(raised.value)
    assert "vectra-data/minio-root" in message and "pw" in message and "UTF-8" in message
    assert "0xff" not in message and "byte" not in message.replace("bytes de", "") and raised.value.__cause__ is None and cluster.calls == []


def test_report_a_generated_path_nobody_reads_does_not_stop_the_closing_from_saying_nothing_to_realign():
    """F-05: `identity/break-glass` no lo lee ningun ExternalSecret (el realm de kind no lo usa): se informa, pero no hay nada que realinear."""
    report = vp.Report()
    report.path("a/b").recovered = 1
    line = report.path("identity/break-glass")
    line.generated.append("BREAK_GLASS_PASSWORD")
    line.unread = True
    lines = report.lines()
    assert any("identity/break-glass" in text and "nadie la lee" in text for text in lines)
    assert any("nada que realinear" in text for text in lines) and not any("Se generaron valores nuevos" in text for text in lines)


def test_report_identity_counts_the_five_paths_that_something_reads_and_not_break_glass(tmp_path, monkeypatch, capsys):
    old = FakeVault()
    run_identity(old, FakeCluster([], {}), tmp_path / "antes")
    cluster = identity_cluster(old)
    monkeypatch.setattr(vp, "Vault", lambda *_: FakeVault())
    monkeypatch.setattr(vp, "ClusterSecrets", lambda context: REAL_CLUSTER_SECRETS(context, cluster.run))
    monkeypatch.setattr(vp, "ca_from_cluster", lambda *_: lambda: CA_PEM)
    assert vp.main(["vault_paths.py", "seed-identity", "kind-vectra", "root", str(tmp_path / "llaves")]) == 0
    text = capsys.readouterr().out
    assert "Se generaron valores nuevos en 5 ruta(s)" in text, text
    for path in ("identity/clients/channel", "identity/clients/channel-simulator", "identity/clients/verification-reader"):
        assert f"{path}: conservadas 0, recuperadas 0, generadas 2 (jwks, private-key)" in text


def test_namespaces_a_failure_listing_them_fails_the_script_instead_of_refreshing_nothing(tmp_path: Path):
    """F-03: si `identity-namespaces` falla, `identity` no termina en 0 con cero namespaces refrescados."""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "kubectl").write_text(FAKE_KUBECTL, encoding="utf-8")
    (fake / "kubectl").chmod(0o755)
    (tmp_path / "ca.pem").write_text(CA_PEM, encoding="utf-8")
    (tmp_path / "externalsecrets.json").write_text(json.dumps({"items": live_external_secrets()}), encoding="utf-8")
    uv = shutil.which("uv")
    assert uv
    env = {**os.environ, "PATH": f"{fake}:{Path(uv).parent}:/usr/bin:/bin", "FAKE_DIR": str(tmp_path), "VECTRA_E2E_KEYS_DIR": str(tmp_path / "llaves")}
    assert subprocess.run([str(SEED_VAULT), "identity"], env=env, capture_output=True, text=True, timeout=180, check=False).returncode == 0
    (tmp_path / "kubectl.log").unlink()
    (tmp_path / "es-falla").write_text("", encoding="utf-8")  # ahora la boveda esta completa (no lee el clúster) pero listar los ExternalSecret falla
    result = subprocess.run([str(SEED_VAULT), "identity"], env=env, capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode != 0 and "Unable to connect" in result.stderr
    assert not [line for line in (tmp_path / "kubectl.log").read_text(encoding="utf-8").splitlines() if "annotate" in line]
