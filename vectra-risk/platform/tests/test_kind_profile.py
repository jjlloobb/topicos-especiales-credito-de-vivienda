"""El perfil liviano de kind cabe en una maquina de 14 GiB, y conserva lo que los simulacros necesitan."""

import tempfile
from pathlib import Path

import integration
import yaml

PLATFORM = Path(__file__).resolve().parents[1]
#: Memoria pedida por todos los pods de kind, proxies incluidos. Es lo que el planificador reserva, no el uso real.
# Provisional (decisión del usuario, 2026-11-08, U02-T17): U1 + U2 piden 5,47 GiB. Se revisa con la medición del Paso 16 de U2
# (DD-3 y T6 de `aidlc-docs/construction/plans/demo-kind-alcance.md`).
# Subido a 6,1, provisional (decisión del usuario, 2026-11-09, arbitraje de U03-T05): U1 + U2 + U3 piden 6,01 GiB. Sigue
# provisional hasta la medición de DD-3 con el Paso 16 de U2.
# Subido a 8,5 (decisión del usuario, 2026-11-09, opción (c) de DECISIONES-LOOP.md §7, U06-T03): U1 + U2 + U3 + U6 piden 8,4375 GiB en el peor
# momento que kind declara para U6 (la promoción: M1 y M2 en `prod` y el predictor de staging, a 256 MiB por pod; con 512 MiB serían ≈ 10,4).
# Se vuelve a revisar con cada unidad nueva.
# Subido a 9,0 en U04-T06 (misma regla de DECISIONES-LOOP.md §7, «se vuelve a revisar con cada unidad nueva»): `governance-service` suma 2 replicas
# x (256 Mi + 20 Mi de proxy) = 0,5391 GiB y el total pasa a 8,9766 GiB, redondeado hacia arriba a 0,1 GiB. El tope de parada era 9,2 GiB.
# Subido a 9,3 en U09-T04 (misma regla de DECISIONES-LOOP.md §7): `bias-monitoring-service` suma 2 replicas x (128 Mi + 20 Mi de proxy) = 0,2891 GiB y el
# total pasa a 9,2656 GiB, redondeado hacia arriba a 0,1 GiB. El CronJob no cuenta (`requested_gib()` suma Deployment y StatefulSet). El tope de parada era 9,49 GiB.
# Subido a 10,4 en U07-T04 (misma regla de DECISIONES-LOOP.md §7): `scoring-service` y `explainability-service` suman 2 servicios x 2 replicas x (256 Mi + 20 Mi
# de proxy) = 1,0781 GiB y el total pasa a 10,3438 GiB, redondeado hacia arriba a 0,1 GiB. El tope de parada era 10,58 GiB (9,3 + 1,08 + 0,2).
# Subido a 10,7 en U11-T03 (misma regla de DECISIONES-LOOP.md §7; P-1 = (b), decision del usuario 2026-11-12): `product-metrics` suma 2 replicas x (128 Mi + 20 Mi de
# proxy) = 0,2891 GiB y el total pasa a 10,6328 GiB (medido antes y despues de agregar la Application), redondeado hacia arriba a 0,1 GiB. El request de kind es de
# 128 MiB y no de los 256 MiB de INF-U11-01: se aparta de «kind igual a staging» (deployment-architecture.md) solo en este request. Con U8 y U10 la proyeccion es ≈ 12,5 GiB.
BUDGET_GIB = 10.7
PROXY_GIB = 20 / 1024
MESHED = {
    "vectra-edge", "vectra-app", "vectra-serving", "vectra-staging", "vectra-data", "vectra-identity", "vectra-mock",
    "vectra-observability", "vectra-restore-drill",
}  # fmt: skip
UNITS = {"Ki": 1 / 1024**2, "Mi": 1 / 1024, "Gi": 1}


def gib(value: object) -> float:
    text = str(value)
    for suffix, factor in UNITS.items():
        if text.endswith(suffix):
            return float(text.removesuffix(suffix)) * factor
    return float(text) / 1024**3 if text.isdigit() else 0.0


def pod_memory(spec: dict) -> float:
    return sum(
        gib(c.get("resources", {}).get("requests", {}).get("memory", 0)) for c in spec.get("containers", [])
    )


def rendered() -> list[dict]:
    return [d for _, group in integration.render_env("kind") for d in group]


GITOPS = PLATFORM.parent / "vectra-risk-gitops"
SERVING_CHART = PLATFORM.parent / "model-serving/chart"
KIND_SERVING_VALUES = GITOPS / "values/kind/model-serving.yaml"
#: El peor momento que el perfil de kind declara para U6 (DECISIONES-LOOP §7): la promocion, con M1 y M2 en `prod` (2 + 2 pods cada una) y el
#: predictor de staging. Los PR de `promotion-tool` aun no lo agregan a los values de kind, asi que el presupuesto lo proyecta aqui.
PEAK_INFERENCE_SERVICES = [
    {"modelVersionId": "mv-2026-01-01-26300247", "storageUri": "s3://model-store/mv-2026-01-01-26300247/", "profile": "prod"},
    {"modelVersionId": "mv-2026-02-01-a1b2c3d4", "storageUri": "s3://model-store/mv-2026-02-01-a1b2c3d4/", "profile": "prod"},
    {"modelVersionId": "mv-2026-02-01-a1b2c3d4", "storageUri": "s3://model-store/mv-2026-02-01-a1b2c3d4/", "profile": "staging"},
]  # fmt: skip


def declared_inference_services() -> list[dict]:
    return yaml.safe_load(KIND_SERVING_VALUES.read_text(encoding="utf-8")).get("inferenceServices") or []


def inference_services(services: list[dict] | None = None) -> list[dict]:
    """Los `InferenceService` que el chart de U6 rinde en kind con esos `inferenceServices` (por omision, los declarados en kind)."""
    services = declared_inference_services() if services is None else services
    with tempfile.TemporaryDirectory() as folder:
        overlay = Path(folder) / "inference-services.yaml"
        overlay.write_text(yaml.safe_dump({"inferenceServices": services}), encoding="utf-8")
        values = [GITOPS / "envs/kind/values.yaml", KIND_SERVING_VALUES, overlay]
        documents = integration.helm("model-serving", SERVING_CHART, "vectra-serving", values)
    return [d for d in documents if d["kind"] == "InferenceService"]


def inference_service_gib(document: dict) -> float:
    """Replicas minimas de cada componente por (requests del contenedor + proxy): lo que el planificador reserva en reposo."""
    total = 0.0
    for component in document["spec"].values():
        containers = {"containers": component.get("containers", [])}
        total += component["minReplicas"] * (pod_memory(containers) + PROXY_GIB)
    return total


def requested_gib(services: list[dict] | None = None) -> float:
    total = 0.0
    for document in rendered():
        namespace = document["metadata"].get("namespace", "")
        proxy = PROXY_GIB if namespace in MESHED else 0.0
        kind = document["kind"]
        if kind in {"Deployment", "StatefulSet"}:
            total += document["spec"].get("replicas", 1) * (
                pod_memory(document["spec"]["template"]["spec"]) + proxy
            )
        elif kind == "DaemonSet":
            total += 2 * (pod_memory(document["spec"]["template"]["spec"]) + proxy)  # dos nodos de trabajo
        elif kind == "Cluster":
            memory = gib(document["spec"]["resources"]["requests"]["memory"])
            total += document["spec"]["instances"] * (memory + proxy)
        elif kind in {"Prometheus", "Alertmanager"}:
            memory = gib(document["spec"]["resources"]["requests"]["memory"])
            total += document["spec"].get("replicas", 1) * (memory + proxy)
    return total + sum(inference_service_gib(d) for d in inference_services(services))


def test_the_profile_requests_fit_the_budget():
    peak = requested_gib([*declared_inference_services(), *PEAK_INFERENCE_SERVICES])
    assert peak <= BUDGET_GIB, peak


def test_inference_services_in_kind_values_are_counted():
    """Rojo de U06-T03: un `InferenceService` en los values de kind no cambiaba `requested_gib()`."""
    base = requested_gib([])
    one = requested_gib(PEAK_INFERENCE_SERVICES[:1])
    # prod: 2 + 2 pods de (256 Mi + proxy)
    assert one - base == 4 * (256 / 1024 + PROXY_GIB)
    staging = requested_gib(PEAK_INFERENCE_SERVICES[2:])
    assert staging - base == 1 * (256 / 1024 + PROXY_GIB)


def test_kind_serving_halves_memory_requests_and_staging_and_prod_keep_inf_u6_01():
    """Decision 7 de DECISIONES-LOOP: 256 Mi por pod solo en kind, sin tocar replicas; chart/values.yaml (staging y prod) sigue en INF-U6-01."""
    chart = yaml.safe_load((SERVING_CHART / "values.yaml").read_text(encoding="utf-8"))["profiles"]
    assert chart["prod"]["predictor"]["resources"]["requests"]["memory"] == "512Mi"
    assert chart["prod"]["explainer"]["resources"]["requests"]["memory"] == "512Mi"
    assert chart["inactive"]["predictor"]["resources"]["requests"]["memory"] == "512Mi"
    assert chart["staging"]["predictor"]["resources"]["requests"]["memory"] == "256Mi"
    for env in ("staging", "prod"):
        text = (GITOPS / f"values/{env}/model-serving.yaml").read_text(encoding="utf-8")
        assert "profiles" not in yaml.safe_load(text) and "profiles" not in (
            yaml.safe_load((GITOPS / f"envs/{env}/values.yaml").read_text()) or {}
        )
    kind = yaml.safe_load(KIND_SERVING_VALUES.read_text(encoding="utf-8"))["profiles"]
    for profile, components in {
        "prod": ("predictor", "explainer"),
        "inactive": ("predictor", "explainer"),
        "staging": ("predictor",),
    }.items():
        for component in components:
            assert kind[profile][component]["resources"]["requests"]["memory"] == "256Mi"
            assert not {"minReplicas", "maxReplicas", "replicas"} & kind[profile][component].keys()
    rendered_prod = inference_services(PEAK_INFERENCE_SERVICES[:1])[0]["spec"]
    assert rendered_prod["predictor"]["minReplicas"] == rendered_prod["explainer"]["minReplicas"] == 2


def test_kind_has_no_synchronous_replica_but_production_does():
    clusters = {
        e: [d for d in integration.render_env(e) for d in d[1] if d["kind"] == "Cluster"]
        for e in ("kind", "prod")
    }
    assert all(c["spec"]["instances"] == 1 and "minSyncReplicas" not in c["spec"] for c in clusters["kind"])
    assert all(c["spec"]["instances"] == 3 and c["spec"]["minSyncReplicas"] == 1 for c in clusters["prod"])


def test_minio_keeps_several_drives_for_object_lock():
    values = yaml.safe_load((PLATFORM / "data/minio/values-kind.yaml").read_text(encoding="utf-8"))
    assert values["replicas"] == 1 and values["drivesPerNode"] >= 4


def test_linkerd_loses_ha_only_in_kind():
    assert (
        yaml.safe_load((PLATFORM / "mesh/linkerd-kind.yaml").read_text(encoding="utf-8"))[
            "controllerReplicas"
        ]
        == 1
    )
    assert (
        yaml.safe_load((PLATFORM / "mesh/linkerd-values.yaml").read_text(encoding="utf-8"))[
            "controllerReplicas"
        ]
        == 3
    )
