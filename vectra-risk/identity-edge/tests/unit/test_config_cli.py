"""`keycloak-config-cli` y el administrador de arranque, solo en kind (U02-T19, B-1; INF-U2-05a, «Excepción solo en kind»).

Cada regla de `keycloak/policy/config_cli.rego` (y `bootstrap-admin` y `config-cli-only-kind`, de las otras dos) tiene su caso que falla
sobre un render alterado. Lo que el Job necesita sale del realm de kind y de `platform/network/flows.yaml`, no de constantes.
"""

import copy
import re
from collections.abc import Callable
from typing import Any

import keycloak_deploy_checks as kd
import pytest
import yaml

Docs = list[dict[str, Any]]
JOB = "keycloak-config-cli"
REALM_TEXT = kd.REALM_KIND.read_text(encoding="utf-8")
REALM = yaml.safe_load(REALM_TEXT)
FLOWS = yaml.safe_load((kd._ROOT / "platform" / "network" / "flows.yaml").read_text(encoding="utf-8"))  # noqa: SLF001
# La linea 3 del realm cita `$(env:NOMBRE)` en un comentario; el Job define NOMBRE para que la sustitucion no falle (CANDIDATAS.md).
COMMENT_PLACEHOLDERS = {"NOMBRE"}


def job(docs: Docs) -> dict[str, Any]:
    return kd.find(docs, "Job", JOB)


def pod(docs: Docs) -> dict[str, Any]:
    return job(docs)["spec"]["template"]["spec"]


def main(docs: Docs) -> dict[str, Any]:
    return pod(docs)["containers"][0]


def env_of(docs: Docs, name: str) -> dict[str, Any]:
    (found,) = [e for e in main(docs)["env"] if e["name"] == name]
    return found


def mutation(fn: Callable[[Docs], None]) -> Callable[[Docs], None]:
    return fn


def set_env(name: str, value: str) -> Callable[[Docs], None]:
    def apply(docs: Docs) -> None:
        env_of(docs, name).pop("valueFrom", None)
        env_of(docs, name)["value"] = value

    return apply


def drop_env(name: str) -> Callable[[Docs], None]:
    def apply(docs: Docs) -> None:
        main(docs)["env"].remove(env_of(docs, name))

    return apply


def set_path(kind: str, name: str, path: list[str | int], value: Any) -> Callable[[Docs], None]:
    def apply(docs: Docs) -> None:
        node: Any = kd.find(docs, kind, name)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return apply


def del_path(kind: str, name: str, path: list[str | int]) -> Callable[[Docs], None]:
    def apply(docs: Docs) -> None:
        node: Any = kd.find(docs, kind, name)
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return apply


def drop_doc(kind: str, name: str) -> Callable[[Docs], None]:
    def apply(docs: Docs) -> None:
        docs.remove(kd.find(docs, kind, name))

    return apply


def sts_env_drop(name: str) -> Callable[[Docs], None]:
    def apply(docs: Docs) -> None:
        env = kd.statefulset(docs)["spec"]["template"]["spec"]["containers"][0]["env"]
        env[:] = [e for e in env if e["name"] != name]

    return apply


def sts_env_plain(name: str) -> Callable[[Docs], None]:
    def apply(docs: Docs) -> None:
        env = kd.statefulset(docs)["spec"]["template"]["spec"]["containers"][0]["env"]
        for e in env:
            if e["name"] == name:
                e.pop("valueFrom")
                e["value"] = "admin"

    return apply


def jwks_item(docs: Docs) -> dict[str, Any]:
    return kd.find(docs, "ExternalSecret", "keycloak-realm-clients-jwks")["spec"]["data"][0]


def job_container_all(docs: Docs) -> list[dict[str, Any]]:
    return [*pod(docs)["initContainers"], *pod(docs)["containers"]]


def each(fn: Callable[[dict[str, Any]], None]) -> Callable[[Docs], None]:
    def apply(docs: Docs) -> None:
        fn(main(docs))

    return apply


KIND_MUTATIONS: list[tuple[str, str, Callable[[Docs], None]]] = [
    ("bootstrap-admin", "el StatefulSet sin KC_BOOTSTRAP_ADMIN_PASSWORD", sts_env_drop("KC_BOOTSTRAP_ADMIN_PASSWORD")),
    ("bootstrap-admin", "usuario de arranque en claro", sts_env_plain("KC_BOOTSTRAP_ADMIN_USERNAME")),
    ("config-cli-hook", "sin anotaciones", del_path("Job", JOB, ["metadata", "annotations"])),
    ("config-cli-hook", "hook Sync", set_path("Job", JOB, ["metadata", "annotations", "argocd.argoproj.io/hook"], "Sync")),
    ("config-cli-hook", "sin BeforeHookCreation", set_path("Job", JOB, ["metadata", "annotations", "argocd.argoproj.io/hook-delete-policy"], "HookSucceeded")),
    ("config-cli-image", "etiqueta en vez de digest", set_path("Job", JOB, ["spec", "template", "spec", "containers", 0, "image"], "kind-registry:5000/vectra/keycloak-config-cli:6.5.1-26.5.5")),
    ("config-cli-image", "digest de ceros", set_path("Job", JOB, ["spec", "template", "spec", "containers", 0, "image"], "kind-registry:5000/vectra/keycloak-config-cli@sha256:" + "0" * 64)),
    ("config-cli-image", "otro registro", set_path("Job", JOB, ["spec", "template", "spec", "initContainers", 0, "image"], "docker.io/adorsys/keycloak-config-cli@sha256:" + "a" * 64)),
    ("config-cli-varsubst", "sustitucion apagada", set_env("IMPORT_VARSUBSTITUTION_ENABLED", "false")),
    ("config-cli-varsubst", "sin la variable de sustitucion", drop_env("IMPORT_VARSUBSTITUTION_ENABLED")),
    ("config-cli-varsubst", "variable indefinida sin error", set_env("IMPORT_VARSUBSTITUTION_UNDEFINEDISERROR", "false")),
    ("config-cli-connection", "otra URL de Keycloak", set_env("KEYCLOAK_URL", "https://vectra.localtest.me/auth")),
    ("config-cli-connection", "sin verificar TLS", set_env("KEYCLOAK_SSLVERIFY", "false")),
    ("config-cli-connection", "otro archivo de realm", set_env("IMPORT_FILES_LOCATIONS", "file:/config/realm.staging.yaml")),
    ("config-cli-connection", "sin el volumen de la CA", set_path("Job", JOB, ["spec", "template", "spec", "volumes", 0, "secret", "secretName"], "otra-ca")),
    ("config-cli-connection", "sin el ConfigMap del realm", set_path("Job", JOB, ["spec", "template", "spec", "volumes", 1, "configMap", "name"], "otro")),
    ("config-cli-credentials", "contrasena en claro", set_env("KEYCLOAK_PASSWORD", "admin")),
    ("config-cli-credentials", "usuario de otro Secret", set_path("Job", JOB, ["spec", "template", "spec", "containers", 0, "env", 2, "valueFrom", "secretKeyRef", "name"], "otro")),
    ("config-cli-credentials", "sin el envFrom de los usuarios", set_path("Job", JOB, ["spec", "template", "spec", "containers", 0, "envFrom"], [{"secretRef": {"name": "keycloak-realm-clients-jwks"}}])),
    ("config-cli-security", "como root", set_path("Job", JOB, ["spec", "template", "spec", "securityContext", "runAsNonRoot"], False)),
    ("config-cli-security", "raiz de escritura", set_path("Job", JOB, ["spec", "template", "spec", "containers", 0, "securityContext", "readOnlyRootFilesystem"], False)),
    ("config-cli-security", "init container con privilegios", set_path("Job", JOB, ["spec", "template", "spec", "initContainers", 0, "securityContext", "allowPrivilegeEscalation"], True)),
    ("config-cli-security", "sin limites", del_path("Job", JOB, ["spec", "template", "spec", "containers", 0, "resources", "limits"])),
    ("config-cli-security", "limite de memoria de 1Gi (ronda 1)", set_path("Job", JOB, ["spec", "template", "spec", "containers", 0, "resources", "limits", "memory"], "1Gi")),
    ("config-cli-security", "prioridad vectra-low (ronda 1)", set_path("Job", JOB, ["spec", "template", "spec", "priorityClassName"], "vectra-low")),
    ("config-cli-security", "recursos del truststore de mas", set_path("Job", JOB, ["spec", "template", "spec", "initContainers", 0, "resources", "limits", "memory"], "512Mi")),
    ("config-cli-security", "otra prioridad", set_path("Job", JOB, ["spec", "template", "spec", "priorityClassName"], "vectra-high")),
    ("config-cli-security", "otra cuenta de servicio", set_path("Job", JOB, ["spec", "template", "spec", "serviceAccountName"], "default")),
    ("config-cli-security", "otra etiqueta de pod (F94)", set_path("Job", JOB, ["spec", "template", "metadata", "labels", "app.kubernetes.io/name"], "otro")),
    ("config-cli-security", "sin sidecar nativo", del_path("Job", JOB, ["spec", "template", "metadata", "annotations"])),
    ("config-cli-security", "sin criticidad", del_path("Job", JOB, ["metadata", "labels", "vectra.io/criticality"])),
    ("config-cli-security", "reinicio OnFailure", set_path("Job", JOB, ["spec", "template", "spec", "restartPolicy"], "OnFailure")),
    ("config-cli-external-secrets", "otra clave del administrador", set_path("ExternalSecret", "keycloak-bootstrap-admin", ["spec", "data", 0, "remoteRef", "key"], "identity/otra")),
    ("config-cli-external-secrets", "dataFrom en el administrador", set_path("ExternalSecret", "keycloak-bootstrap-admin", ["spec", "dataFrom"], [{"extract": {"key": "identity"}}])),
    ("config-cli-external-secrets", "JWKS de otro cliente", set_path("ExternalSecret", "keycloak-realm-clients-jwks", ["spec", "data", 0, "remoteRef", "key"], "identity/clients/otro")),
    ("config-cli-external-secrets", "propiedad private-key en el JWKS", set_path("ExternalSecret", "keycloak-realm-clients-jwks", ["spec", "data", 0, "remoteRef", "property"], "private-key")),
    ("config-cli-external-secrets", "JWKS sin toJson", set_path("ExternalSecret", "keycloak-realm-clients-jwks", ["spec", "target", "template", "data", "CLIENT_BIAS_MONITORING_JOB_JWKS"], "{{ .bias_monitoring_job }}")),
    ("config-cli-external-secrets", "usuario sintetico con otra propiedad", set_path("ExternalSecret", "keycloak-realm-synthetic-users", ["spec", "data", 0, "remoteRef", "property"], "otra")),
    ("config-cli-external-secrets", "usuarios con template", set_path("ExternalSecret", "keycloak-realm-synthetic-users", ["spec", "target", "template"], {"data": {}})),
    ("config-cli-realm", "clave de realm distinta", set_path("ConfigMap", "keycloak-config-cli-realm", ["data"], {"realm.yaml": "# x"})),
    ("config-cli-realm", "realm que no es el de Git", set_path("ConfigMap", "keycloak-config-cli-realm", ["data", "realm.kind.yaml"], "realm: vectra")),
    ("config-cli-only-kind", "kind sin el Job", drop_doc("Job", JOB)),
    ("config-cli-only-kind", "kind sin el administrador de arranque", drop_doc("ExternalSecret", "keycloak-bootstrap-admin")),
    ("config-cli-only-kind", "kind sin la cuenta de servicio", drop_doc("ServiceAccount", JOB)),
]  # fmt: skip


@pytest.fixture(scope="module")
def kind_docs() -> Docs:
    return kd.load("kind")


def test_kind_meets_the_policies_with_the_job(kind_docs):
    code, output = kd.conftest(kind_docs)
    assert code == 0, output
    assert job(kind_docs)["metadata"]["annotations"]["argocd.argoproj.io/hook"] == "PostSync"


@pytest.mark.parametrize(("rule", "case", "apply"), KIND_MUTATIONS, ids=[f"{r}-{c}" for r, c, _ in KIND_MUTATIONS])
def test_rule_fails_on_an_altered_kind_render(rule, case, apply, kind_docs):
    docs = copy.deepcopy(kind_docs)
    apply(docs)
    code, output = kd.conftest(docs)
    assert code != 0, f"{rule}/{case}: conftest no fallo"
    assert f"{rule}: " in output, f"{rule}/{case}: la salida no nombra la regla\n{output}"


# --- solo kind -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_the_bank_environments_render_nothing_of_the_exception(env):
    text = (kd.RENDERED / env / "keycloak.yaml").read_text(encoding="utf-8")
    # `keycloak-config-cli-client` y `identity/clients/keycloak-config-cli` son de INF-U2-01 y siguen en los tres entornos.
    for needle in (r"(name|serviceAccountName): keycloak-config-cli\s*$", r"^kind: Job", "KC_BOOTSTRAP_ADMIN", "keycloak-bootstrap-admin", "keycloak-realm-", "PostSync"):
        assert not re.search(needle, text, re.MULTILINE), f"{env}: {needle}"
    assert not [d for d in kd.load(env) if d["kind"] in {"Job", "ConfigMap"}]


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_the_bank_values_do_not_enable_the_exception(env):
    common = yaml.safe_load((kd.VALUES / "common.yaml").read_text(encoding="utf-8"))
    own = yaml.safe_load((kd.VALUES / f"{env}.yaml").read_text(encoding="utf-8"))
    assert common["vectra"]["configCli"]["enabled"] is False
    assert not own.get("vectra", {}).get("configCli")


def test_kind_values_enable_the_exception_with_a_pinned_image():
    own = yaml.safe_load((kd.VALUES / "kind.yaml").read_text(encoding="utf-8"))["vectra"]["configCli"]
    assert own["enabled"] is True
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", own["image"]["digest"]) and set(own["image"]["digest"][7:]) != {"0"}


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_the_job_in_a_bank_render_fails_the_policy(env):
    docs = kd.load(env)
    docs.append(copy.deepcopy(job(kd.load("kind"))))
    code, output = kd.conftest(docs)
    assert code != 0 and "config-cli-only-kind: " in output


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_the_bootstrap_admin_in_a_bank_render_fails_the_policy(env):
    docs = kd.load(env)
    env_list = kd.statefulset(docs)["spec"]["template"]["spec"]["containers"][0]["env"]
    env_list.append({"name": "KC_BOOTSTRAP_ADMIN_USERNAME", "valueFrom": {"secretKeyRef": {"name": "keycloak-bootstrap-admin", "key": "username"}}})
    code, output = kd.conftest(docs)
    assert code != 0 and "bootstrap-admin: " in output


def test_enabling_the_exception_without_a_digest_or_realm_does_not_render():
    base = kd.render("staging", "--set", "vectra.configCli.enabled=true")
    assert base.returncode != 0 and "vectra.configCli.image.digest" in base.stderr
    no_realm = kd.helm_command("kind")
    no_realm = no_realm[: no_realm.index("--set-file")] + no_realm[no_realm.index("--set-file") + 2 :]
    import subprocess

    run = subprocess.run(no_realm, capture_output=True, text=True, check=False)  # noqa: S603
    assert run.returncode != 0 and "vectra.configCli.realm" in run.stderr


# --- lo que el Job necesita sale del realm ------------------------------------------------------------------------


def realm_variables() -> set[str]:
    return set(re.findall(r"\$\(env:([A-Z0-9_]+)\)", REALM_TEXT))


def job_variables(docs: Docs) -> set[str]:
    provided = {e["name"] for e in main(docs)["env"]}
    for ref in main(docs)["envFrom"]:
        secret = ref["secretRef"]["name"]
        es = kd.find(docs, "ExternalSecret", secret)
        template = es["spec"]["target"].get("template", {}).get("data")
        provided |= set(template) if template else {item["secretKey"] for item in es["spec"]["data"]}
    return provided


def test_every_variable_of_the_realm_has_a_value_in_the_job(kind_docs):
    missing = realm_variables() - job_variables(kind_docs)
    assert not missing, sorted(missing)


def test_the_only_placeholder_in_a_comment_is_the_known_one():
    """`NOMBRE` solo aparece en una linea de comentario del realm; el Job la define y `CANDIDATAS.md` la registra."""
    in_comments = {m for line in REALM_TEXT.splitlines() if line.lstrip().startswith("#") for m in re.findall(r"\$\(env:([A-Z0-9_]+)\)", line)}
    in_data = {m for line in REALM_TEXT.splitlines() if not line.lstrip().startswith("#") for m in re.findall(r"\$\(env:([A-Z0-9_]+)\)", line)}
    assert in_comments == COMMENT_PLACEHOLDERS and not in_comments & in_data


def test_the_job_defines_no_variable_the_realm_does_not_use(kind_docs):
    plain = {e["name"] for e in main(kind_docs)["env"] if "value" in e}
    configuration = {"KEYCLOAK_URL", "KEYCLOAK_SSLVERIFY", "KEYCLOAK_AVAILABILITYCHECK_ENABLED", "KEYCLOAK_AVAILABILITYCHECK_TIMEOUT", "IMPORT_FILES_LOCATIONS", "IMPORT_VARSUBSTITUTION_ENABLED", "IMPORT_VARSUBSTITUTION_UNDEFINEDISERROR", "JAVA_OPTS"}
    assert plain - configuration == {"PUBLIC_HOSTNAME", *COMMENT_PLACEHOLDERS}


def test_the_jwks_clients_are_the_realm_clients_with_client_jwt(kind_docs):
    wanted = {c["clientId"] for c in REALM["clients"] if "$(env:CLIENT_" in str(c.get("attributes", {}).get("jwks.string", ""))}
    es = kd.find(kind_docs, "ExternalSecret", "keycloak-realm-clients-jwks")
    assert {i["remoteRef"]["key"].removeprefix("identity/clients/") for i in es["spec"]["data"]} == wanted
    assert len(wanted) == 15


def test_the_synthetic_users_are_the_realm_users(kind_docs):
    wanted = {u["username"] for u in REALM["users"] if "$(env:SYNTH_" in str(u)}
    es = kd.find(kind_docs, "ExternalSecret", "keycloak-realm-synthetic-users")
    users = {i["secretKey"].removeprefix("SYNTH_").rsplit("_", 1)[0].lower().replace("_", "-") for i in es["spec"]["data"] if i["secretKey"].endswith("_PASSWORD")}
    assert users == wanted and len(es["spec"]["data"]) == 2 * len(wanted)


def test_the_realm_configmap_is_the_realm_of_git_untouched(kind_docs):
    data = kd.find(kind_docs, "ConfigMap", "keycloak-config-cli-realm")["data"]["realm.kind.yaml"]
    assert data.strip() == REALM_TEXT.strip()


def test_the_truststore_the_init_container_builds_is_the_one_java_reads(kind_docs):
    options = env_of(kind_docs, "JAVA_OPTS")["value"]
    init = pod(kind_docs)["initContainers"][0]
    assert "-Djavax.net.ssl.trustStore=/trust/truststore.p12" in options
    assert "/trust/truststore.p12" in init["args"] and "/etc/vectra/ca/ca.crt" in init["args"]
    assert {"name": "trust", "mountPath": "/trust", "readOnly": True} in main(kind_docs)["volumeMounts"]


# --- red: F94 cubre al Job con sus etiquetas reales -------------------------------------------------------------


def test_flow_f94_covers_the_job_with_its_real_labels_and_identity(kind_docs):
    workload = FLOWS["workloads"]["keycloak-config-cli"]
    assert workload == {"ns": "vectra-identity", "sa": JOB, "name": JOB}
    assert job(kind_docs)["metadata"]["namespace"] == workload["ns"]
    assert pod(kind_docs)["serviceAccountName"] == workload["sa"]
    assert job(kind_docs)["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/name"] == workload["name"]
    f94 = next(f for f in FLOWS["flows"] if f["id"] == "F94")
    assert JOB in f94["from"] and f94["to"] == ["keycloak"] and f94["port"] == 8443
    assert kd.find(kind_docs, "ServiceAccount", workload["sa"])["automountServiceAccountToken"] is False


def test_the_generated_network_policy_selects_the_job_pod(kind_docs):
    path = kd._ROOT / "platform" / "network" / "generated" / "kind" / "vectra-identity.yaml"  # noqa: SLF001
    policies = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d and d["kind"] == "NetworkPolicy"]
    egress = next(p for p in policies if p["metadata"]["name"] == "allow-f94-keycloak-config-cli-to-keycloak-egress")
    assert egress["spec"]["podSelector"]["matchLabels"] == {"app.kubernetes.io/name": JOB}
    assert egress["spec"]["egress"][0]["ports"] == [{"port": 8443, "protocol": "TCP"}]
    assert env_of(kind_docs, "KEYCLOAK_URL")["value"].endswith(":8443/auth")


# --- U1: las politicas estaticas ven al Job -------------------------------------------------------------------------


def test_the_u1_kyverno_policies_pass_on_kind_including_the_job(kind_docs):
    ok, output = kd.kyverno(kind_docs)
    assert ok, output


def test_the_u1_kyverno_policies_fail_on_a_job_with_a_latest_image(kind_docs):
    docs = copy.deepcopy(kind_docs)
    set_path("Job", JOB, ["spec", "template", "spec", "containers", 0, "image"], "kind-registry:5000/vectra/keycloak-config-cli:latest")(docs)
    ok, _ = kd.kyverno(docs)
    assert not ok


# --- KSV-0109: el ConfigMap del realm de kind va en su propio archivo (PR 85) ------------------------------------------


def test_the_realm_configmap_of_kind_is_alone_in_its_own_file():
    in_main = [d["kind"] for d in yaml.safe_load_all((kd.RENDERED / "kind" / "keycloak.yaml").read_text(encoding="utf-8")) if d]
    assert "ConfigMap" not in in_main and "Job" in in_main
    alone = [d for d in yaml.safe_load_all((kd.RENDERED / "kind" / "config-cli-realm.yaml").read_text(encoding="utf-8")) if d]
    assert [(d["kind"], d["metadata"]["name"]) for d in alone] == [("ConfigMap", "keycloak-config-cli-realm")]
    assert sorted(p.name for p in (kd.RENDERED / "kind").iterdir()) == ["config-cli-realm.yaml", "keycloak.yaml"]


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_the_bank_environments_have_no_realm_file(env):
    assert [p.name for p in (kd.RENDERED / env).iterdir()] == ["keycloak.yaml"]


def test_the_split_loses_nothing_and_needs_exactly_one_realm_configmap():
    full = kd.render("kind")
    assert full.returncode == 0, full.stderr
    main, realm = kd.split_realm(full.stdout)

    def key(d):
        return (d["kind"], d["metadata"]["name"])

    assert sorted(key(d) for d in yaml.safe_load_all(main + "\n---\n" + realm) if d) == sorted(key(d) for d in yaml.safe_load_all(full.stdout) if d)
    with pytest.raises(SystemExit):
        kd.split_realm(main)


def test_trivy_skips_only_the_new_file_and_the_decision_is_recorded():
    root = kd._ROOT  # noqa: SLF001
    workflow = (root.parent / ".github" / "workflows" / "supply-chain.yml").read_text(encoding="utf-8")
    skip = [s.strip() for s in next(line for line in workflow.splitlines() if line.strip().startswith("skip-files:")).split(":", 1)[1].split(",")]
    assert "vectra-risk/identity-edge/keycloak/rendered/kind/config-cli-realm.yaml" in skip
    assert not [s for s in skip if s.endswith("rendered/kind/keycloak.yaml") or "keycloak/rendered/staging" in s or "keycloak/rendered/prod" in s]
    ignore = (root / ".trivyignore").read_text(encoding="utf-8")
    assert "config-cli-realm.yaml" in ignore and "2026-11-09" in ignore and "PR 85" in ignore and "T1" in ignore


def test_the_job_parameters_come_from_the_values_not_from_the_template():
    """F-02: `backoffLimit`, el plazo, la espera de disponibilidad, los recursos y el rodeo `NOMBRE` salen de `vectra.configCli.*`."""
    own = yaml.safe_load((kd.VALUES / "common.yaml").read_text(encoding="utf-8"))["vectra"]["configCli"]
    template = (kd.VALUES / "common.yaml").read_text(encoding="utf-8")
    block = template[template.index("kind: Job") :]
    for literal in ("backoffLimit: 3", "activeDeadlineSeconds: 900", "value: 300s", "memory: 512Mi", "memory: 256Mi", "name: NOMBRE", "vectra-normal"):
        assert literal not in block, literal
    docs = kd.render("kind", "--set", "vectra.configCli.backoffLimit=7", "--set", "vectra.configCli.availabilityTimeout=42s")
    assert docs.returncode == 0, docs.stderr
    job_doc = next(d for d in yaml.safe_load_all(docs.stdout) if d and d["kind"] == "Job")
    assert job_doc["spec"]["backoffLimit"] == 7
    assert {"name": "KEYCLOAK_AVAILABILITYCHECK_TIMEOUT", "value": "42s"} in job_doc["spec"]["template"]["spec"]["containers"][0]["env"]
    assert own["resources"] == {"requests": {"cpu": "100m", "memory": "256Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}}  # INF-U2-06
