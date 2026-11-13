"""Render y politicas de los CronJobs de identidad (U02-T08, CA-4): `helm template`, `conftest` y los documentos esperados.

Los valores del diseno salen de `jobs_design`; lo que solo fija el chart (etiquetas, `securityContext`, plazos, nombres de
volumenes) se compara con el render versionado en `identity-edge/jobs/rendered/`, que a su vez es el de ahora.
"""

import copy
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import jobs_design as design
import yaml

_ROOT = Path(__file__).resolve().parents[3]
EDGE = _ROOT / "identity-edge"
JOBS = EDGE / "jobs"
POLICY = JOBS / "policy"
RENDERED = JOBS / "rendered"
CHART = JOBS / "chart"
REALM_DIR = EDGE / "keycloak" / "realm"
HELM = _ROOT / "platform" / ".tools" / "bin" / "helm"
CONFTEST = _ROOT / "platform" / ".tools" / "bin" / "conftest"
ENVS = ("kind", "staging", "prod")
NAMESPACE = "vectra-identity"
Docs = list[dict[str, Any]]


def issuer(env: str) -> str:
    """El emisor que Keycloak publica en `env`: su `KC_HOSTNAME` (render versionado) + el realm. Es la `aud` de la aserción (U00-T04)."""
    text = (EDGE / "keycloak" / "rendered" / env / "keycloak.yaml").read_text(encoding="utf-8")
    match = re.search(r"name: KC_HOSTNAME\n\s+value: (\S+)", text)
    assert match, f"{env}: el render de Keycloak no fija KC_HOSTNAME"
    return match.group(1).rstrip("/") + "/realms/vectra"


def values_file(env: str) -> Path:
    return JOBS / "values" / f"{env}.yaml"


def realm_file(env: str) -> Path:
    return REALM_DIR / f"realm.{env}.yaml"


def render(env: str, *extra: str, realm: bool = True) -> subprocess.CompletedProcess[str]:
    command = [
        str(HELM),
        "template",
        "identity-jobs",
        str(CHART),
        "--namespace",
        NAMESPACE,
        "-f",
        str(values_file(env)),
    ]
    if realm:
        command += ["--set-file", f"realm={realm_file(env)}"]
    return subprocess.run([*command, *extra], capture_output=True, text=True, check=False)  # noqa: S603


def load(text: str) -> Docs:
    return [d for d in yaml.safe_load_all(text) if d]


# Los archivos del render de cada entorno (T1): el ConfigMap del realm va aparte, para poder omitirlo del escaneo de Trivy.
FILES = {
    "identity-jobs.yaml": "templates/identity-jobs.yaml",
    "realm-configmap.yaml": "templates/realm-configmap.yaml",
}


def render_file(env: str, name: str) -> subprocess.CompletedProcess[str]:
    return render(env, "--show-only", FILES[name])


def versioned(env: str) -> Docs:
    """Todos los documentos del render versionado de `env`, de sus dos archivos."""
    assert sorted(p.name for p in (RENDERED / env).iterdir()) == sorted(FILES)
    docs: Docs = []
    for name in sorted(FILES):
        docs += load((RENDERED / env / name).read_text(encoding="utf-8"))
    return docs


def find(docs: Docs, kind: str, name: str) -> dict[str, Any]:
    (found,) = [d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name]
    return found


def conftest(docs: Docs, *, combine: bool = False) -> subprocess.CompletedProcess[str]:
    """Las reglas de `identity-edge/jobs/policy/` sobre `docs` (una por una, o juntas con `--combine`)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "identity-jobs.yaml"
        path.write_text(yaml.safe_dump_all(copy.deepcopy(docs)), encoding="utf-8")
        args = ["--combine", "--namespace", "jobs_set"] if combine else []
        return subprocess.run(  # noqa: S603
            [str(CONFTEST), "test", *args, "--policy", str(POLICY), str(path), "--output", "json"],
            capture_output=True,
            text=True,
            check=False,
        )


def rego_rules() -> set[str]:
    rules: set[str] = set()
    for path in sorted(POLICY.glob("*.rego")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# regla: "):
                rules.add(line.removeprefix("# regla: ").strip())
    return rules


# --- documentos esperados, completos ----------------------------------------------------------------


def _env_list(common: dict[str, str], extra: dict[str, str]) -> list[dict[str, str]]:
    return [{"name": k, "value": v} for k, v in {**common, **extra}.items()]


def expected_documents(env: str, image: str) -> Docs:
    """Los cinco documentos del render de `env`, completos. Lo que fija el diseno viene de `jobs_design`."""
    realm_text = realm_file(env).read_text(encoding="utf-8")
    common_env = {
        "VECTRA_CLIENT_ID": "keycloak-reader",
        "VECTRA_TOKEN_URL": design.token_url(),
        "VECTRA_ASSERTION_AUDIENCE": issuer(env),
        "VECTRA_CLIENT_KEY_PATH": "/etc/vectra/reader/private-key",
        "VECTRA_CA_BUNDLE": "/etc/vectra/ca/ca.crt",
        "KEYCLOAK_ADMIN_URL": design.admin_url(),
        "PUSHGATEWAY_URL": design.pushgateway_url(),
    }
    schedules = design.schedules()
    deadlines = {"realm-drift": 900, "signing-key-age": 300}
    scripts = {"realm-drift": "/app/realm_drift.py", "signing-key-age": "/app/signing_key_age.py"}

    def cronjob(name: str) -> dict[str, Any]:
        has_realm = name == "realm-drift"
        volumes: list[dict[str, Any]] = [
            {
                "name": "reader-key",
                "secret": {
                    "secretName": "keycloak-reader-client",
                    "defaultMode": 288,
                    "items": [{"key": "private-key", "path": "private-key"}],
                },
            },
            {
                "name": "identity-ca",
                "secret": {
                    "secretName": "identity-ca",
                    "defaultMode": 288,
                    "items": [{"key": "ca.crt", "path": "ca.crt"}],
                },
            },
        ]
        mounts = [
            {"name": "reader-key", "mountPath": "/etc/vectra/reader", "readOnly": True},
            {"name": "identity-ca", "mountPath": "/etc/vectra/ca", "readOnly": True},
        ]
        env_extra = {}
        if has_realm:
            volumes.append(
                {
                    "name": "realm",
                    "configMap": {
                        "name": "realm-drift-realm",
                        "items": [{"key": "realm.yaml", "path": "realm.yaml"}],
                    },
                }
            )
            mounts.append({"name": "realm", "mountPath": "/etc/vectra/realm", "readOnly": True})
            env_extra["REALM_FILE"] = "/etc/vectra/realm/realm.yaml"
        return {
            "apiVersion": "batch/v1",
            "kind": "CronJob",
            "metadata": {
                "name": name,
                "namespace": NAMESPACE,
                "labels": {
                    "app.kubernetes.io/name": name,
                    "app.kubernetes.io/part-of": "identity-edge",
                    "vectra.io/criticality": "medium",
                },
            },
            "spec": {
                "schedule": schedules[name],
                "concurrencyPolicy": design.concurrency_policy(),
                "jobTemplate": {
                    "spec": {
                        "backoffLimit": 0,
                        "activeDeadlineSeconds": deadlines[name],
                        "template": {
                            "metadata": {
                                "labels": {
                                    "app.kubernetes.io/name": name,
                                    "app.kubernetes.io/part-of": "identity-edge",
                                },
                                "annotations": {
                                    "config.alpha.linkerd.io/proxy-enable-native-sidecar": "true"
                                },
                            },
                            "spec": {
                                "serviceAccountName": name,
                                "priorityClassName": design.priority_class(),
                                "restartPolicy": "Never",
                                "securityContext": {
                                    "runAsNonRoot": True,
                                    "runAsUser": 65532,
                                    "runAsGroup": 65532,
                                    "fsGroup": 65532,
                                    "seccompProfile": {"type": "RuntimeDefault"},
                                },
                                "containers": [
                                    {
                                        "name": name,
                                        "image": image,
                                        "imagePullPolicy": "IfNotPresent",
                                        "command": ["python", scripts[name]],
                                        "env": _env_list(
                                            {**common_env, **env_extra}, {"PYTHONDONTWRITEBYTECODE": "1"}
                                        ),
                                        "securityContext": {
                                            "allowPrivilegeEscalation": False,
                                            "readOnlyRootFilesystem": True,
                                            "capabilities": {"drop": ["ALL"]},
                                        },
                                        "resources": design.resources(),
                                        "volumeMounts": mounts,
                                    }
                                ],
                                "volumes": volumes,
                            },
                        },
                    }
                },
            },
        }

    def service_account(name: str) -> dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": name,
                "namespace": NAMESPACE,
                "labels": {"app.kubernetes.io/name": name, "app.kubernetes.io/part-of": "identity-edge"},
            },
        }

    config_map = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "realm-drift-realm",
            "namespace": NAMESPACE,
            "labels": {
                "app.kubernetes.io/name": "realm-drift",
                "app.kubernetes.io/part-of": "identity-edge",
                "vectra.io/criticality": "medium",
            },
        },
        "data": {"realm.yaml": realm_text},
    }
    return [
        config_map,
        service_account("realm-drift"),
        service_account("signing-key-age"),
        cronjob("realm-drift"),
        cronjob("signing-key-age"),
    ]
