"""Chart de U6 (Paso 6; NFR-U6-02, 11, 20; P-U6-02, 04; INF-U6-01, 02): render por perfil, `kubeconform` con el CRD de KServe v0.21.0
y las politicas de `model-serving/policies/conftest/`. Cada `# regla: <id>` tiene aqui un caso que falla con una mutacion del render
(`CASES`) y el render sin tocar pasa. Necesita `platform/install-tools.sh`."""

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from chart_helpers import (
    FIXTURES,
    POLICY,
    ROOT,
    Doc,
    edit,
    failures,
    helm,
    isvcs,
    of_kind,
    passes,
    render,
    render_profile,
    tool,
)

CRDS = FIXTURES / "crds"


def one(docs: list[Doc]) -> Doc:
    (isvc,) = isvcs(docs)
    return isvc


def spec(docs: list[Doc], component: str = "predictor") -> Doc:
    return one(docs)["spec"][component]  # type: ignore[no-any-return]


def container(docs: list[Doc], component: str = "predictor") -> Doc:
    return spec(docs, component)["containers"][0]  # type: ignore[no-any-return]


def mutation(change: Callable[[list[Doc]], None]) -> Callable[[list[Doc]], None]:
    return change


def _rename(docs: list[Doc]) -> None:
    one(docs)["metadata"]["name"] = "isvc-deadbeef"


def _uppercase_name(docs: list[Doc]) -> None:
    one(docs)["metadata"]["name"] = "isvc-ABCDEF12"
    one(docs)["metadata"]["annotations"]["vectra.io/model-version-id"] = "mv-2026-01-01-ABCDEF12"
    for component in ("predictor", "explainer"):
        spec(docs, component)["annotations"]["vectra.io/model-version-id"] = "mv-2026-01-01-ABCDEF12"


def _explainer_version(docs: list[Doc]) -> None:
    spec(docs, "explainer")["annotations"]["vectra.io/model-version-id"] = "mv-2026-01-01-ffffffff"


def _explainer_uri(docs: list[Doc]) -> None:
    other = "s3://model-store/mv-2026-01-01-ffffffff/"
    spec(docs, "explainer")["annotations"]["internal.serving.kserve.io/storage-initializer-sourceuri"] = other
    container(docs, "explainer")["env"][-1]["value"] = other


def _env_uri(docs: list[Doc]) -> None:
    container(docs)["env"][-1]["value"] = "s3://model-store/otra/"


def _adversarial(docs: list[Doc]) -> None:
    uri = "s3://model-store/adversarial/rt3-a/"
    for component in ("predictor", "explainer"):
        spec(docs, component)["annotations"]["internal.serving.kserve.io/storage-initializer-sourceuri"] = uri
        container(docs, component)["env"][-1]["value"] = uri


def _set(component: str, key: str, value: Any) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        spec(docs, component)[key] = value

    return change


def _metric(change: Callable[[Doc], None]) -> Callable[[list[Doc]], None]:
    def apply(docs: list[Doc]) -> None:
        change(spec(docs)["autoScaling"])

    return apply


def _drop_spread(docs: list[Doc]) -> None:
    del spec(docs, "explainer")["topologySpreadConstraints"]


def _del_annotation(key: str) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        del one(docs)["metadata"]["annotations"][key]

    return change


def _add_annotation(key: str, value: str) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        one(docs)["metadata"]["annotations"][key] = value

    return change


def _inactive_autoscaling(docs: list[Doc]) -> None:
    spec(docs)["autoScaling"] = {"metrics": []}


def _drop_pod_state(docs: list[Doc]) -> None:
    del spec(docs)["labels"]["vectra.io/serving-state"]


def _staging_explainer(docs: list[Doc]) -> None:
    one(docs)["spec"]["explainer"] = spec(docs)


def _predictor_cpu_limit(docs: list[Doc]) -> None:
    container(docs)["resources"]["limits"]["cpu"] = "2"


def _staging_memory(docs: list[Doc]) -> None:
    container(docs)["resources"]["requests"]["memory"] = "512Mi"


def _label(key: str, value: str) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        spec(docs)["labels"][key] = value

    return change


def _probe(name: str, key: str, value: int) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        container(docs)[name][key] = value

    return change


def _volume(docs: list[Doc]) -> None:
    spec(docs)["volumes"][0]["emptyDir"]["sizeLimit"] = "2Gi"


def _tag_image(docs: list[Doc]) -> None:
    container(docs)["image"] = "kind-registry:5000/vectra/model-predictor:dev"


def _rw_rootfs(docs: list[Doc]) -> None:
    container(docs)["securityContext"]["readOnlyRootFilesystem"] = False


def _del(component: str, *path: str) -> Callable[[list[Doc]], None]:
    def change(docs: list[Doc]) -> None:
        node: Any = spec(docs, component)
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return change


def _no_security_context(docs: list[Doc]) -> None:
    del container(docs)["securityContext"]


def _no_storage_env(docs: list[Doc]) -> None:
    container(docs)["env"] = [e for e in container(docs)["env"] if e["name"] != "STORAGE_URI"]


def _add_secret(docs: list[Doc]) -> None:
    docs.append(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "minio-kserve", "namespace": "vectra-serving"},
        }
    )


def _repeat(docs: list[Doc]) -> None:
    docs.append(docs[0])


def _no_credential(docs: list[Doc]) -> None:
    for account in of_kind(docs, "ServiceAccount"):
        if account["metadata"]["namespace"] == "vectra-staging":
            del account["secrets"]


def _drop_budgets(docs: list[Doc]) -> None:
    docs[:] = [d for d in docs if d["kind"] != "PodDisruptionBudget"]


def _budget_on_inactive(docs: list[Doc]) -> None:
    docs.append(
        {
            "apiVersion": "policy/v1",
            "kind": "PodDisruptionBudget",
            "metadata": {"name": "isvc-26300247-predictor", "namespace": "vectra-serving"},
            "spec": {
                "minAvailable": 1,
                "selector": {"matchLabels": {"app.kubernetes.io/name": "isvc-26300247-predictor"}},
            },
        }
    )


# (regla, perfil del render, mutacion). Cada regla `# regla: <id>` de las politicas tiene al menos un caso.
CASES: list[tuple[str, str, Callable[[list[Doc]], None]]] = [
    ("name-from-version", "prod", _rename),
    ("name-from-version", "prod", _uppercase_name),
    ("version-annotation-equal", "prod", _explainer_version),
    ("storage-uri-equal", "prod", _explainer_uri),
    ("storage-uri-equal", "prod", _env_uri),
    ("no-adversarial-in-serving", "prod", _adversarial),
    ("no-adversarial-in-serving", "inactive", _adversarial),
    ("active-min-replicas", "prod", _set("predictor", "minReplicas", 1)),
    ("active-min-replicas", "prod", _set("explainer", "minReplicas", 1)),
    ("active-scaling", "prod", _set("predictor", "maxReplicas", 5)),
    ("active-scaling", "prod", _set("explainer", "maxReplicas", 4)),
    ("active-scaling", "prod", _metric(lambda a: a["metrics"][0]["resource"].update(name="memory"))),
    (
        "active-scaling",
        "prod",
        _metric(lambda a: a["metrics"][0]["resource"]["target"].update(averageUtilization=70)),
    ),
    (
        "active-scaling",
        "prod",
        _metric(lambda a: a["behavior"]["scaleDown"].update(stabilizationWindowSeconds=60)),
    ),
    ("active-spread", "prod", _drop_spread),
    ("priority-by-profile", "prod", _set("predictor", "priorityClassName", "vectra-normal")),
    ("priority-by-profile", "inactive", _set("explainer", "priorityClassName", "vectra-high")),
    ("priority-by-profile", "staging", _set("predictor", "priorityClassName", "vectra-normal")),
    ("inactive-contract", "inactive", _set("predictor", "minReplicas", 2)),
    ("inactive-contract", "inactive", _del_annotation("vectra.io/hpa-exempt")),
    ("inactive-contract", "inactive", _inactive_autoscaling),
    ("inactive-contract", "inactive", _drop_pod_state),
    ("inactive-contract", "inactive", _del_annotation("serving.kserve.io/autoscalerClass")),
    ("inactive-contract", "staging", _del_annotation("serving.kserve.io/autoscalerClass")),
    ("active-no-exemption", "prod", _add_annotation("vectra.io/hpa-exempt", "true")),
    ("staging-contract", "staging", _staging_explainer),
    ("staging-contract", "staging", _set("predictor", "minReplicas", 2)),
    ("resources-by-profile", "prod", _predictor_cpu_limit),
    ("resources-by-profile", "staging", _staging_memory),
    ("component-identity", "prod", _label("vectra.io/component", "explainer")),
    ("component-identity", "prod", _set("predictor", "serviceAccountName", "default")),
    ("component-identity", "prod", _label("app.kubernetes.io/name", "otro")),
    ("probes-and-volume", "prod", _probe("startupProbe", "failureThreshold", 10)),
    ("probes-and-volume", "prod", _probe("livenessProbe", "periodSeconds", 30)),
    ("probes-and-volume", "prod", _volume),
    ("container-security", "prod", _tag_image),
    ("container-security", "prod", _rw_rootfs),
    ("version-annotation-equal", "prod", _del("explainer", "annotations", "vectra.io/model-version-id")),
    ("storage-uri-equal", "prod", _no_storage_env),
    (
        "storage-uri-equal",
        "prod",
        _del("predictor", "annotations", "internal.serving.kserve.io/storage-initializer-sourceuri"),
    ),
    ("priority-by-profile", "prod", _del("predictor", "priorityClassName")),
    ("component-identity", "prod", _del("predictor", "labels", "vectra.io/component")),
    ("component-identity", "prod", _del("predictor", "serviceAccountName")),
    ("container-security", "prod", _no_security_context),
    ("no-secrets", "prod", _add_secret),
    ("no-repeated-documents", "prod", _repeat),
    ("service-account-credential", "prod", _no_credential),
    ("active-pdb", "prod", _drop_budgets),
    ("inactive-no-pdb", "inactive", _budget_on_inactive),
]


@pytest.mark.parametrize("profile", ["prod", "inactive", "staging"])
def test_el_render_de_cada_perfil_pasa_kubeconform_y_las_dos_pasadas_de_conftest(profile: str) -> None:
    docs = render_profile(profile)
    assert passes(docs), failures(docs)
    rendered = subprocess.run(  # noqa: S603
        [
            tool("helm"),
            "template",
            "ms",
            str(ROOT / "model-serving" / "chart"),
            "-f",
            str(FIXTURES / f"values-{profile}.yaml"),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    result = subprocess.run(  # noqa: S603
        [
            tool("kubeconform"),
            "-strict",
            "-summary",
            "-schema-location",
            "default",
            "-schema-location",
            f"{CRDS}/{{{{.ResourceKind}}}}.json",
            "-",
        ],
        input=rendered,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Invalid: 0, Errors: 0, Skipped: 0" in result.stdout


def test_kubeconform_rechaza_un_campo_que_el_crd_no_declara() -> None:
    rendered = helm(FIXTURES / "values-prod.yaml").stdout.replace("priorityClassName:", "priorityClassNme:")
    result = subprocess.run(  # noqa: S603
        [
            tool("kubeconform"),
            "-strict",
            "-schema-location",
            "default",
            "-schema-location",
            f"{CRDS}/{{{{.ResourceKind}}}}.json",
            "-",
        ],
        input=rendered,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "priorityClassNme" in result.stdout


def test_cada_perfil_cumple_el_diseno() -> None:
    prod = render_profile("prod")
    assert (
        one(prod)["metadata"]["name"] == "isvc-26300247"
        and one(prod)["metadata"]["namespace"] == "vectra-serving"
    )
    assert [spec(prod, c)[k] for c in ("predictor", "explainer") for k in ("minReplicas", "maxReplicas")] == [
        2,
        4,
        2,
        6,
    ]
    assert {d["metadata"]["name"] for d in of_kind(prod, "PodDisruptionBudget")} == {
        "isvc-26300247-predictor",
        "isvc-26300247-explainer",
    }
    inactive = render_profile("inactive")
    meta = one(inactive)["metadata"]
    assert (
        meta["labels"]["vectra.io/serving-state"] == "inactivo"
        and meta["annotations"]["vectra.io/hpa-exempt"]
    )
    assert of_kind(inactive, "PodDisruptionBudget") == []
    staging = render_profile("staging")
    assert one(staging)["metadata"]["namespace"] == "vectra-staging" and set(one(staging)["spec"]) == {
        "predictor"
    }
    assert container(staging)["resources"]["requests"] == {"cpu": "250m", "memory": "256Mi"}


def test_el_render_sin_inferenceservices_solo_trae_la_serviceaccount_con_la_credencial() -> None:
    docs = render()
    assert {(d["kind"], d["metadata"]["namespace"]) for d in docs} == {
        ("ServiceAccount", "vectra-serving"),
        ("ServiceAccount", "vectra-staging"),
    }
    assert all(
        d["secrets"] == [{"name": "minio-kserve"}] and d["metadata"]["name"] == "kserve-model" for d in docs
    )
    assert passes(docs)


def test_imagenes_por_digest_con_el_registro_de_entorno() -> None:
    docs = render(FIXTURES / "values-prod.yaml", "--set", "imageRegistry=registro.banco.internal/vectra")
    assert re.fullmatch(
        r"registro\.banco\.internal/vectra/model-predictor@sha256:[0-9a-f]{64}", container(docs)["image"]
    )
    assert re.fullmatch(
        r"registro\.banco\.internal/vectra/model-explainer@sha256:[0-9a-f]{64}",
        container(docs, "explainer")["image"],
    )
    docs = render(FIXTURES / "values-prod.yaml", "--set", "imageRegistry=kind-registry:5000")
    assert container(docs)["image"].startswith("kind-registry:5000/vectra/model-predictor@sha256:")


def test_sin_digest_no_se_renderiza() -> None:
    result = helm(FIXTURES / "values-prod.yaml", "--set", "images.predictor.digest=")
    assert result.returncode != 0


def test_una_version_repetida_en_el_mismo_namespace_no_se_renderiza() -> None:
    result = helm(FIXTURES / "values-repeated.yaml")
    assert result.returncode != 0 and "repetido" in result.stderr


def test_adversarial_solo_se_admite_en_staging() -> None:
    assert helm(FIXTURES / "values-adversarial-prod.yaml").returncode != 0
    assert helm(FIXTURES / "values-adversarial-staging.yaml").returncode == 0


def test_los_valores_de_entorno_de_argo_cd_no_rompen_el_esquema() -> None:
    result = helm(
        None,
        "--set",
        "storageClass=standard,mockEnabled=true,verificationOperator=true,imageRegistry=kind-registry:5000",
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("rule", "profile", "change"), CASES, ids=[f"{r}-{i}" for i, (r, _, _) in enumerate(CASES)]
)
def test_cada_mutacion_hace_fallar_su_regla(
    rule: str, profile: str, change: Callable[[list[Doc]], None]
) -> None:
    docs = render_profile(profile)
    assert passes(docs), failures(docs)
    output = failures(edit(docs, change))
    assert f"{rule}:" in output, output


def test_todas_las_reglas_de_las_politicas_tienen_caso() -> None:
    declared = {
        m
        for f in POLICY.glob("*.rego")
        for m in re.findall(r"# regla: ([\w-]+)", f.read_text(encoding="utf-8"))
    }
    assert declared == {rule for rule, _, _ in CASES}


def _kyverno_bounds(docs: list[Doc], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    resource = tmp_path / "render.yaml"
    resource.write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
    policy = ROOT / "platform" / "policies" / "kyverno" / "require-hpa-bounds.yaml"
    return subprocess.run(
        [tool("kyverno"), "apply", str(policy), "--resource", str(resource)],
        capture_output=True,
        text=True,
        check=False,
    )  # noqa: S603


@pytest.mark.parametrize("profile", ["prod", "inactive"])
def test_la_politica_de_u1_admite_el_activo_y_el_inactivo(profile: str, tmp_path: Path) -> None:
    result = _kyverno_bounds(render_profile(profile), tmp_path)
    assert "pass: 1, fail: 0, warn: 0, error: 0" in result.stdout, result.stdout


def test_la_politica_de_u1_rechaza_al_activo_con_una_replica_y_al_inactivo_sin_exencion(
    tmp_path: Path,
) -> None:
    active = _kyverno_bounds(
        edit(render_profile("prod"), lambda d: _set("predictor", "minReplicas", 1)(d)), tmp_path
    )
    assert "fail: 1" in active.stdout and "active-inference-service-needs-two-replicas" in active.stdout
    inactive = _kyverno_bounds(
        edit(render_profile("inactive"), _del_annotation("vectra.io/hpa-exempt")), tmp_path
    )
    assert "fail: 1" in inactive.stdout and "inactive-inference-service-needs-exemption" in inactive.stdout
