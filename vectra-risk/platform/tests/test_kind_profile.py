"""El perfil liviano de kind: lo que pide el planificador en el pico de D2, contado completo, y lo que conserva para los simulacros."""

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from functools import cache
from pathlib import Path

import integration
import pytest
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
# Subido a 11,1 en U10-T05 (misma regla de DECISIONES-LOOP.md §7; P-1 = (b), decision del usuario 2026-11-13): `console-bff` y `console-spa` suman 2 replicas x (128 Mi + 20 Mi de proxy)
# + 2 replicas x (32 Mi + 20 Mi de proxy) = 0,3906 GiB y el total pasa a 11,0234 GiB (medido antes y despues de agregar las dos Applications: 10,6328 y 11,0234), redondeado hacia arriba
# a 0,1 GiB. El request del BFF en kind es de 128 MiB y no de los 256 MiB de INF-U10-01: se aparta de «kind igual a staging» (deployment-architecture.md) solo en ese request. Con U8 la proyeccion es ≈ 11,77 GiB.
# Subido a 11,8 en U08-T05 (misma regla de DECISIONES-LOOP.md §7; P-1 = (b), decision del usuario, 2026-11-12): `case-service` y `case-worker` piden 128 Mi solo en kind
# (`case-management/chart/values-kind.yaml`; INF-U8-04 dice 256 Mi) y el mock 64 Mi: 2 x (128 + 20) + 2 x (128 + 20) + 2 x (64 + 20) Mi = 760 Mi = 0,7422 GiB. La rama midio 10,3438 -> 11,0859 GiB
# sobre una base sin U11 ni U10; al fusionar con las dos (11,0234 GiB) el total pasa a 11,7656 GiB, redondeado hacia arriba a 0,1 GiB. Con 256 Mi (opcion a) habria sido 1,2422 GiB.
# Con esto estan todas las unidades de aplicacion menos U12 (tope de parada, 13,0).
# Subido a 13,4 en U01-T10 (cifra medida, no una decision de recorte): el total pasa de 11,7656 a 13,3672 GiB, redondeado hacia arriba a 0,1 GiB. Suma
# 1,6016 GiB: la 2.a instancia de `registry-db` (256 Mi + 20 Mi de proxy = 0,2695), la 2.a replica de Keycloak que pide su HPA y el StatefulSet no declaraba
# (1.000 Mi + 20 Mi = 1,0195; antes contaba 1), metrics-server (64 Mi, kube-system sin proxy = 0,0625) y la boveda de kind (256 Mi = 0,25). 13,4 supera el tope
# de parada de 13,0 que se habia fijado para U12: los recortes de memoria de kind son otra tarea; ver la bitacora de U01-T10.
# Cambia en U01-T11 a 13,9 (cifra medida, no una decision de recorte): (1) F-03 de la revision de U01-T10: la prueba ahora cuenta lo que el planificador reserva y `render_env` no
# renderiza, leido de sus archivos de origen (`runtime_documents()`): data plane de Envoy 0,6016, controlador de Envoy Gateway 0,25, `envoy-ratelimit` 0,125 y controlador de KServe
# 0,5859 GiB; la cuenta de U01-T10 (13,3672) pasa a 14,9297. (2) Sin Loki, Tempo ni Alloy en kind (decision del usuario 2026-11-14): -0,4336 -0,4102 -0,2266 = -1,0703 GiB. Total 13,8594
# GiB, redondeado hacia arriba a 0,1. Sigue sin contar los Jobs (`model-validation-job` 1 GiB de request en D2, config-cli 0,25, `minio-post-job` 0,375) ni `kube-system`.
# Cambia en U01-T12 a 15,1 (cifra medida con todo contado, no una decision de recorte; F-01, F-03 y el punto 3 de la revision de U01-T11): (1) la cuenta suma los sidecars nativos
# (`linkerd-proxy` de `linkerd-destination` y `linkerd-proxy-injector`, +40 Mi) y sigue la regla max(init, contenedores); (2) serving cuenta `maxReplicas` (en kind igual a `minReplicas`, ver
# `values/kind/model-serving.yaml`: sin ese cambio la cuenta seria 18,29); (3) el Job de validacion (1 Gi + proxy 20 Mi, leido de `k8s_jobs.py`) y `kube-system` (`KUBE_SYSTEM`: CoreDNS, 0,1368;
# calico-node no pide memoria). Total 15,0547 GiB con Keycloak en 2 replicas (14,0352 con 1: U02-T23). La maquina de la demo tiene 15 GiB (MACHINE_GIB): con Keycloak en 2 faltan 0,06 GiB
# y no cabe; con 1 sobran 0,96. Es un presupuesto de requests, no de uso real (plataforma sola ~7,6 GiB reales).
BUDGET_GIB = 15.1
MACHINE_GIB = 15.0
PROXY_GIB = 20 / 1024
#: CPU pedida por todos los pods de kind en el pico de D2, con proxies (20m, sidecars nativos incluidos), el Job de validacion, `kube-system` (calico-node, CoreDNS) y serving a `maxReplicas`: 11,465
#: con Keycloak en 2 replicas, redondeado hacia arriba a 0,5 (U01-T12; antes 10,5 con una cuenta que no veia los sidecars nativos). OJO (F-05): los tres nodos de kind comparten los 8 nucleos
#: FISICOS del host, aunque cada worker anuncie 8; un request de CPU solo reparte pesos entre pods y no reserva nucleos, asi que 11,5 sobre 8 no es un fallo. El tope solo evita pods en `Pending`
#: (REQUESTABLE_CPU: lo que los dos workers aceptan en `kubectl describe node`); no es capacidad de computo.
CPU_BUDGET = 11.5
PHYSICAL_CORES = 8.0
REQUESTABLE_CPU = 16.0
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


def cores(value: object) -> float:
    text = str(value)
    return float(text.removesuffix("m")) / 1000 if text.endswith("m") else float(text)


def effective_request(spec: dict, resource: str, convert) -> float:
    """El request de un pod segun la regla de Kubernetes (U01-T12 F-01).

    Los `initContainers` con `restartPolicy: Always` (sidecars nativos, como el `linkerd-proxy` de `linkerd-destination`) corren junto a los contenedores y se
    suman. Los demas init containers corren antes y solos (con los sidecars que ya arrancaron): el pod pide el maximo entre el mayor de ellos y la suma de
    sidecars y contenedores.
    """

    def request(container: dict) -> float:
        return convert(container.get("resources", {}).get("requests", {}).get(resource, 0))

    sidecars = 0.0
    init_peak = 0.0
    for container in spec.get("initContainers", []):
        if container.get("restartPolicy") == "Always":
            sidecars += request(container)
        else:
            init_peak = max(init_peak, sidecars + request(container))
    return max(init_peak, sidecars + sum(request(c) for c in spec.get("containers", [])))


def pod_memory(spec: dict) -> float:
    return effective_request(spec, "memory", gib)


def pod_cpu(spec: dict) -> float:
    return effective_request(spec, "cpu", cores)


def proxy_cpu() -> float:
    """El request de CPU del proxy de Linkerd: el de staging y prod (`linkerd-values.yaml`) con lo que kind le sobrescribe (`linkerd-kind.yaml`)."""
    request = yaml.safe_load((PLATFORM / "mesh/linkerd-values.yaml").read_text(encoding="utf-8"))["proxy"]["resources"]["cpu"]["request"]
    kind = yaml.safe_load((PLATFORM / "mesh/linkerd-kind.yaml").read_text(encoding="utf-8"))
    return cores(kind.get("proxy", {}).get("resources", {}).get("cpu", {}).get("request", request))


def deployment(name: str, namespace: str, replicas: int, *containers: dict) -> dict:
    return {
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {"replicas": replicas, "template": {"spec": {"containers": [{"resources": {"requests": c["requests"]}} for c in containers]}}},
    }


@cache
def runtime_documents() -> tuple[dict, ...]:
    """U01-T10 F-03: lo que el planificador reserva y `render_env` no ve, leido de los archivos de origen (si cambian, cambia la cuenta).

    Los charts OCI (controlador de Envoy Gateway, controlador de KServe) se renderizan con sus values; el data plane de Envoy (lo crea el
    controlador a partir del `EnvoyProxy` de kind) y `envoy-ratelimit` (lo crea el controlador desde `rateLimitDeployment`) se arman con los
    requests y las replicas que esos archivos declaran. Quedan fuera los Jobs y CronJobs: ver `UNCOUNTED_CPU` y la bitacora de U01-T11.
    """
    documents: list[dict] = []
    for component in integration.CONFIG["components"]:
        if "kind" in component.get("envs", ("kind", "staging", "prod")) and "chart" in component and not integration.is_chart(component):
            files = [integration.ROOT / f for f in [*component.get("values", []), *component.get("kind_values", [])]]
            chart = integration.CHARTS / component["name"] / component["chart"]
            documents += integration.helm(component["name"], chart, component["namespace"], files)
    for proxy in yaml.safe_load_all((PLATFORM.parent / "identity-edge/gateway/generated/kind/envoyproxies.yaml").read_text(encoding="utf-8")):
        if proxy and proxy["kind"] == "EnvoyProxy":
            provider = proxy["spec"]["provider"]["kubernetes"]
            envoy = provider["envoyDeployment"]
            sidecars = envoy["patch"]["value"]["spec"]["template"]["spec"]["containers"]
            documents.append(
                deployment(
                    f"{proxy['metadata']['name']}-data-plane",
                    proxy["metadata"]["namespace"],
                    max(provider["envoyHpa"]["minReplicas"], envoy["replicas"]),
                    envoy["container"]["resources"],
                    *(c["resources"] for c in sidecars),
                )
            )
    gateway = yaml.safe_load((PLATFORM / "operators/envoy-gateway.yaml").read_text(encoding="utf-8"))
    ratelimit = gateway["config"]["envoyGateway"]["provider"]["kubernetes"]["rateLimitDeployment"]
    documents.append(deployment("envoy-ratelimit", "envoy-gateway-system", ratelimit["replicas"], ratelimit["container"]["resources"]))
    return tuple(documents)


def rendered() -> list[dict]:
    return [*(d for _, group in integration.render_env("kind") for d in group), *runtime_documents()]


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
    """Replicas MAXIMAS de cada componente por (requests del contenedor + proxy) (U01-T12 F-03): el HPA de serving sube a `maxReplicas` con poca carga."""
    total = 0.0
    for component in document["spec"].values():
        containers = {"containers": component.get("containers", [])}
        total += component["maxReplicas"] * (pod_memory(containers) + PROXY_GIB)
    return total


def inference_service_cpu(document: dict) -> float:
    total = 0.0
    for component in document["spec"].values():
        containers = {"containers": component.get("containers", [])}
        total += component["maxReplicas"] * (pod_cpu(containers) + proxy_cpu())
    return total


def hpa_minimums() -> dict[tuple[str, str], int]:
    """`minReplicas` de cada HPA por (tipo, nombre) de lo que escala. Sin HPA que lo suba, el workload cuenta sus `replicas`."""
    result: dict[tuple[str, str], int] = {}
    for document in rendered():
        if document["kind"] == "HorizontalPodAutoscaler":
            target = document["spec"]["scaleTargetRef"]
            result[(target["kind"], target["name"])] = int(document["spec"].get("minReplicas", 1))
    return result


def workload_replicas(document: dict, minimums: dict[tuple[str, str], int]) -> int:
    declared = document["spec"].get("replicas", 1)
    return max(declared, minimums.get((document["kind"], document["metadata"]["name"]), 0))


def requested(pod_value, proxy: float, cluster_request, services: list[dict] | None, isv_value) -> float:
    """Lo que el planificador reserva por replica minima: workloads, un pod por nodo de trabajo de los DaemonSet, instancias de CNPG, Prometheus y Alertmanager."""
    total = 0.0
    minimums = hpa_minimums()
    for document in rendered():
        namespace = document["metadata"].get("namespace", "")
        proxied = proxy if namespace in MESHED else 0.0
        kind = document["kind"]
        if kind in {"Deployment", "StatefulSet"}:
            total += workload_replicas(document, minimums) * (pod_value(document["spec"]["template"]["spec"]) + proxied)
        elif kind == "DaemonSet":
            total += 2 * (pod_value(document["spec"]["template"]["spec"]) + proxied)  # dos nodos de trabajo
        elif kind == "Cluster":
            total += document["spec"]["instances"] * (cluster_request(document["spec"]["resources"]["requests"]) + proxied)
        elif kind in {"Prometheus", "Alertmanager"}:
            total += document["spec"].get("replicas", 1) * (cluster_request(document["spec"]["resources"]["requests"]) + proxied)
    return total + sum(isv_value(d) for d in inference_services(services))


def job_resources() -> dict:
    """Los requests del Job de validacion, leidos de `governance/src/vectra_governance/k8s_jobs.py` (`JOB_RESOURCES`), no copiados."""
    source = (PLATFORM.parent / "governance/src/vectra_governance/k8s_jobs.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "JOB_RESOURCES":
            return ast.literal_eval(node.value)["requests"]
    raise AssertionError("JOB_RESOURCES no esta en k8s_jobs.py")


def validation_job_pod() -> dict:
    """`governance-service` crea el Job en `vectra-staging` (mallado): el contenedor y el proxy como sidecar nativo."""
    request = job_resources()
    return {"containers": [{"resources": {"requests": request}}], "initContainers": [{"restartPolicy": "Always", "resources": {"requests": {"cpu": proxy_cpu(), "memory": "20Mi"}}}]}


#: Lo de `kube-system` que `render_env` no ve y tiene cifra conocida. NO medido en kind: son los requests de los manifiestos upstream, que `kubectl describe node` confirma.
#: Calico v3.33.0 (`kubectl apply -f .../calico/v3.33.0/manifests/calico.yaml`, install.md paso 3): `calico-node` es un DaemonSet con 250m de CPU y sin request de memoria, y corre en los
#: tres nodos (tolera el taint del plano de control). CoreDNS de kubeadm (Kubernetes 1.37): 2 replicas de 100m de CPU y 70Mi. Ninguno lleva proxy (kube-system no esta mallado).
KUBE_SYSTEM = {
    "calico-node": {"pods": 3, "cpu": 0.25, "memory_gib": 0.0},
    "coredns": {"pods": 2, "cpu": 0.1, "memory_gib": 70 / 1024},
}
#: Lo que el planificador reserva y la prueba sigue sin contar (estimado). Los pods estaticos del plano de control de kubeadm (apiserver 250m, controller-manager 200m, scheduler
#: 100m, etcd 100m = 0,65 de CPU y 100Mi de memoria) corren en el nodo `control-plane`, que no programa cargas, y los Jobs de instalacion y migracion (minio-post-job 0,15, config-cli 0,1,
#: tres migraciones 0,3) terminan y dejan de reservar. Suma 1,2.
CONTROL_PLANE_CPU = 0.65
INSTALL_JOBS_CPU = 0.55
UNCOUNTED_CPU = CONTROL_PLANE_CPU + INSTALL_JOBS_CPU


def kube_system_gib() -> float:
    return sum(c["pods"] * c["memory_gib"] for c in KUBE_SYSTEM.values())


def kube_system_cpu() -> float:
    return sum(c["pods"] * c["cpu"] for c in KUBE_SYSTEM.values())


def requested_breakdown(resource: str, services: list[dict] | None = None) -> dict[str, float]:
    """Lo pedido en el pico de D2, por origen: lo renderizado (con los `InferenceService` a `maxReplicas`), el Job de validacion y `kube-system`."""
    if resource == "memory":
        render = requested(pod_memory, PROXY_GIB, lambda r: gib(r["memory"]), services, inference_service_gib)
        job = pod_memory(validation_job_pod())
        system = kube_system_gib()
    else:
        render = requested(pod_cpu, proxy_cpu(), lambda r: cores(r["cpu"]), services, inference_service_cpu)
        job = pod_cpu(validation_job_pod())
        system = kube_system_cpu()
    return {"render": render, "validation-job": job, "kube-system": system}


def requested_gib(services: list[dict] | None = None) -> float:
    return sum(requested_breakdown("memory", services).values())


def requested_cpu(services: list[dict] | None = None) -> float:
    return sum(requested_breakdown("cpu", services).values())


def _requests(cpu: str, memory: str, **extra: object) -> dict:
    return {"resources": {"requests": {"cpu": cpu, "memory": memory}}, **extra}


def test_budget_counts_native_sidecars_and_the_init_container_rule():
    """U01-T12 F-01: un `initContainer` con `restartPolicy: Always` es un sidecar y se suma; los demas init containers cuentan por el maximo."""
    sidecar = _requests("20m", "20Mi", restartPolicy="Always")
    spec = {"initContainers": [_requests("30m", "30Mi"), sidecar], "containers": [_requests("100m", "100Mi")]}
    assert pod_cpu(spec) == pytest.approx(0.12) and pod_memory(spec) == pytest.approx(120 / 1024)  # 20 + 100; el init de 30 no pesa mas
    big_init = {"initContainers": [sidecar, _requests("500m", "500Mi")], "containers": [_requests("100m", "100Mi")]}
    assert pod_cpu(big_init) == pytest.approx(0.52) and pod_memory(big_init) == pytest.approx(520 / 1024)  # el sidecar ya corre cuando arranca el init
    plain = {"initContainers": [_requests("500m", "500Mi")], "containers": [_requests("100m", "100Mi")]}
    assert pod_cpu(plain) == 0.5 and pod_memory(plain) == 500 / 1024
    destination = next(d for d in rendered() if d["kind"] == "Deployment" and d["metadata"]["name"] == "linkerd-destination")
    spec = destination["spec"]["template"]["spec"]
    proxy = next(c for c in spec["initContainers"] if c["name"] == "linkerd-proxy")
    assert proxy["restartPolicy"] == "Always"
    assert pod_cpu(spec) >= sum(cores(c.get("resources", {}).get("requests", {}).get("cpu", 0)) for c in spec["containers"]) + cores(proxy["resources"]["requests"]["cpu"])


def test_budget_counts_the_minimum_replicas_of_statefulset_hpas():
    """U01-T10: el HPA de Keycloak fija las replicas minimas y el StatefulSet declara 1; el planificador reserva las del HPA (`replicas` lo fija el HPA, no el chart).

    El minimo se lee del render de `identity-edge` (2 hasta U02-T23, 1 despues): ninguna cifra de Keycloak va fija aqui.
    """
    minimums = hpa_minimums()
    keycloak = next(d for d in rendered() if d["kind"] == "StatefulSet" and d["metadata"]["name"] == "keycloak")
    hpa = next(d for d in rendered() if d["kind"] == "HorizontalPodAutoscaler" and d["spec"]["scaleTargetRef"]["name"] == "keycloak")
    assert keycloak["spec"].get("replicas", 1) == 1
    assert minimums[("StatefulSet", "keycloak")] == hpa["spec"]["minReplicas"] >= 1
    assert workload_replicas(keycloak, minimums) == hpa["spec"]["minReplicas"]
    plain = next(d for d in rendered() if d["kind"] == "StatefulSet" and ("StatefulSet", d["metadata"]["name"]) not in minimums)
    assert workload_replicas(plain, minimums) == plain["spec"].get("replicas", 1)


def test_budget_counts_envoy_data_plane_envoy_gateway_ratelimit_and_kserve():
    """U01-T10 F-03: lo que el planificador reserva y `render_env` no renderiza (runtime y charts OCI) entra en la cuenta, leido de sus archivos de origen."""
    by_name = {d["metadata"]["name"]: d for d in runtime_documents() if d["kind"] == "Deployment"}
    assert {"api-gateway-data-plane", "envoy-gateway", "envoy-ratelimit", "kserve-controller-manager"} <= by_name.keys()
    assert by_name["api-gateway-data-plane"]["spec"]["replicas"] == 2 and len(by_name["api-gateway-data-plane"]["spec"]["template"]["spec"]["containers"]) == 2
    assert by_name["envoy-ratelimit"]["spec"]["replicas"] == 2
    extra = {
        name: workload_replicas(d, {}) * (pod_memory(d["spec"]["template"]["spec"]) + (PROXY_GIB if d["metadata"]["namespace"] in MESHED else 0.0))
        for name, d in by_name.items()
    }
    assert extra["api-gateway-data-plane"] == 2 * ((256 + 32) / 1024 + PROXY_GIB)  # envoy + shutdown-manager + proxy, vectra-edge esta mallado
    assert extra["envoy-gateway"] == 2 * 128 / 1024 and extra["envoy-ratelimit"] == 2 * 64 / 1024  # envoy-gateway-system no lleva proxy
    assert sum(extra.values()) > 1.5
    # y la cuenta total los incluye
    assert requested_gib([]) >= sum(extra.values())


def test_kind_serving_cannot_scale_beyond_what_the_budget_counts():
    """U01-T12 F-03: con 100m de request el HPA al 60 % escala a `maxReplicas` con casi cualquier trafico; en kind `maxReplicas` = `minReplicas`, y el presupuesto suma `maxReplicas`."""
    base = requested_gib([])
    for services in (PEAK_INFERENCE_SERVICES[:1], PEAK_INFERENCE_SERVICES[2:]):
        for isvc in inference_services(services):
            for name, component in isvc["spec"].items():
                assert component["maxReplicas"] == component["minReplicas"] == (2 if isvc["metadata"]["namespace"] == "vectra-serving" else 1), (name, component)
    prod = inference_services(PEAK_INFERENCE_SERVICES[:1])[0]
    pod = (256 + 20) / 1024  # request de memoria del contenedor mas el proxy
    assert inference_service_gib(prod) == pytest.approx(sum(c["maxReplicas"] for c in prod["spec"].values()) * pod)
    assert requested_gib(PEAK_INFERENCE_SERVICES[:1]) - base == pytest.approx(4 * pod)
    # y el presupuesto de verdad cuenta el maximo: con el del chart (4 y 6) la cuenta subiria 3,23 GiB y 1,44 CPU por cada InferenceService de prod
    chart = yaml.safe_load((SERVING_CHART / "values.yaml").read_text(encoding="utf-8"))["profiles"]["prod"]
    assert (chart["predictor"]["maxReplicas"], chart["explainer"]["maxReplicas"]) == (4, 6)


def test_kind_serving_render_passes_the_kyverno_hpa_bounds_policy():
    """La forma elegida (`maxReplicas` = 2) no relaja nada: `require-hpa-bounds` evalua el InferenceService de prod con los values de kind y no falla."""
    with tempfile.TemporaryDirectory() as folder:
        resource = Path(folder) / "inference-services.yaml"
        resource.write_text(yaml.safe_dump_all(inference_services(PEAK_INFERENCE_SERVICES)), encoding="utf-8")
        policy = PLATFORM / "policies/kyverno/require-hpa-bounds.yaml"
        kyverno = shutil.which("kyverno") or str(PLATFORM / ".tools/bin/kyverno")
        result = subprocess.run([kyverno, "apply", str(policy), "--resource", str(resource)], capture_output=True, text=True, check=False)  # noqa: S603
    assert "fail: 0, warn: 0, error: 0" in result.stdout + result.stderr, result.stdout + result.stderr


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
            assert not {"minReplicas", "replicas"} & kind[profile][component].keys()
            # U01-T12: solo el perfil `prod` (el unico con HPA) fija `maxReplicas`, en 2: serving no escala en kind
            assert ("maxReplicas" in kind[profile][component]) == (profile == "prod"), (profile, component)
            if profile == "prod":
                assert kind[profile][component]["maxReplicas"] == chart["prod"][component]["minReplicas"] == 2
    rendered_prod = inference_services(PEAK_INFERENCE_SERVICES[:1])[0]["spec"]
    assert rendered_prod["predictor"]["minReplicas"] == rendered_prod["explainer"]["minReplicas"] == 2


def clusters_of(env: str) -> dict[str, dict]:
    return {
        d["metadata"]["name"]: d["spec"]
        for _, group in integration.render_env(env)
        for d in group
        if d["kind"] == "Cluster"
    }


def test_only_registry_db_has_a_synchronous_replica_in_kind():
    """U01-T10: el /readyz del registro exige un standby sincrono y `registry-db-ro` lee de una replica; los otros tres siguen en 1."""
    kind = clusters_of("kind")
    assert set(kind) == {"registry-db", "case-db", "governance-db", "keycloak-db"}
    assert kind["registry-db"]["instances"] == 2 and kind["registry-db"]["minSyncReplicas"] == 1
    # CloudNativePG exige maxSyncReplicas < instances: con 2 instancias, 1.
    assert kind["registry-db"]["maxSyncReplicas"] == 1
    for name in ("case-db", "governance-db", "keycloak-db"):
        assert kind[name]["instances"] == 1 and "minSyncReplicas" not in kind[name], name
        assert "maxSyncReplicas" not in kind[name], name


def test_staging_and_production_keep_three_instances_with_one_synchronous_replica():
    for env in ("staging", "prod"):
        clusters = clusters_of(env)
        assert len(clusters) == 4
        for name, spec in clusters.items():
            assert spec["instances"] == 3 and spec["minSyncReplicas"] == 1 and spec["maxSyncReplicas"] == 2, (env, name)


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


def test_linkerd_cpu_request_drops_only_in_kind():
    """U01-T11: 100m por pod en unos 48 pods son 4,8 nucleos de reserva; el limit (500m) no baja y staging y prod siguen en 100m."""
    kind = yaml.safe_load((PLATFORM / "mesh/linkerd-kind.yaml").read_text(encoding="utf-8"))["proxy"]["resources"]
    assert cores(kind["cpu"]["request"]) <= 0.02, kind
    assert "limit" not in kind["cpu"] and "memory" not in kind, "kind solo baja el request de CPU: el limit y la memoria no cambian"
    staging = yaml.safe_load((PLATFORM / "mesh/linkerd-values.yaml").read_text(encoding="utf-8"))["proxy"]["resources"]
    assert staging == {"cpu": {"request": "100m", "limit": "500m"}, "memory": {"request": "20Mi", "limit": "128Mi"}}
    assert proxy_cpu() == cores(kind["cpu"]["request"])


def test_kind_serving_cpu_requests_are_100m_and_staging_and_prod_keep_inf_u6_01():
    """U01-T11: 500m (250m el predictor de staging) por pod de serving reservan casi la mitad de la CPU del pico de D2; los limits no bajan."""
    chart = yaml.safe_load((SERVING_CHART / "values.yaml").read_text(encoding="utf-8"))["profiles"]
    assert chart["prod"]["predictor"]["resources"]["requests"]["cpu"] == "500m"
    assert chart["prod"]["explainer"]["resources"]["requests"]["cpu"] == "500m"
    assert chart["inactive"]["predictor"]["resources"]["requests"]["cpu"] == "500m"
    assert chart["staging"]["predictor"]["resources"]["requests"]["cpu"] == "250m"
    kind = yaml.safe_load(KIND_SERVING_VALUES.read_text(encoding="utf-8"))["profiles"]
    for profile, components in {"prod": ("predictor", "explainer"), "inactive": ("predictor", "explainer"), "staging": ("predictor",)}.items():
        for component in components:
            resources = kind[profile][component]["resources"]
            assert resources["requests"]["cpu"] == "100m", (profile, component)
            assert "limits" not in resources, (profile, component)
    for isvc in inference_services(PEAK_INFERENCE_SERVICES):
        for component in isvc["spec"].values():
            for container in component["containers"]:
                assert container["resources"]["requests"]["cpu"] == "100m"
                assert cores(container["resources"]["limits"]["cpu"]) >= 1


def test_the_profile_cpu_requests_fit_the_budget_at_the_d2_peak():
    """U01-T11: dos InferenceService en `vectra-serving`, uno en `vectra-staging` y el Job de validacion, con las replicas minimas de los HPA."""
    peak = requested_cpu([*declared_inference_services(), *PEAK_INFERENCE_SERVICES])
    assert peak <= CPU_BUDGET, peak


def test_the_cpu_budget_leaves_room_for_what_the_render_does_not_count():
    """El tope evita pods en `Pending` y nada mas: lo que la prueba no ve (UNCOUNTED_CPU) tambien cabe en lo que los dos workers aceptan (2 x 8, que no son nucleos reales; F-05 de U01-T11)."""
    assert CPU_BUDGET + UNCOUNTED_CPU <= REQUESTABLE_CPU
    assert REQUESTABLE_CPU == 2 * PHYSICAL_CORES, "cada worker anuncia los 8 nucleos del host: los tres nodos comparten los mismos 8"


# ---- U01-T11: sin Loki, Tempo ni Alloy en kind, y nada en kind los referencia ----------------------------------------------------------------
#: Decision del usuario (2026-11-14): kind no instala estos tres. Ninguna demo ni U12 los lee (bitacoras/U01-T11.md).
REMOVED_FROM_KIND = {"loki", "tempo", "alloy"}
REMOVED_NAME = re.compile(r"\b(" + "|".join(sorted(REMOVED_FROM_KIND)) + r")\b")


def components_not_in_kind() -> set[str]:
    return {c["name"] for c in integration.CONFIG["components"] if "kind" not in c.get("envs", ("kind", "staging", "prod"))}


def kind_services() -> set[tuple[str, str]]:
    return {(d["metadata"]["namespace"], d["metadata"]["name"]) for d in rendered() if d["kind"] == "Service"}


def service_of(url: str) -> tuple[str, str] | None:
    """`(namespace, servicio)` de una URL o un `host:puerto` de la forma `<servicio>.<namespace>[.svc...]`."""
    match = re.match(r"^(?:[a-z]+://)?([a-z0-9-]+)\.([a-z0-9-]+)(?:\.svc[a-z.]*)?(?::\d+)?(?:/.*)?$", url)
    return (match.group(2), match.group(1)) if match else None


def kind_configmap(name: str, key: str) -> dict:
    document = next(d for d in rendered() if d["kind"] == "ConfigMap" and d["metadata"]["name"] == name)
    return yaml.safe_load(document["data"][key])


def test_kind_does_not_install_loki_tempo_or_alloy_and_staging_and_prod_do():
    assert REMOVED_FROM_KIND <= components_not_in_kind()
    for env in ("staging", "prod"):
        assert all((GITOPS / f"apps/{env}/{name}.yaml").is_file() for name in REMOVED_FROM_KIND), env
    assert not any((GITOPS / f"apps/kind/{name}.yaml").exists() for name in REMOVED_FROM_KIND)


def test_kind_grafana_datasources_point_only_to_services_kind_installs():
    """Una fuente de datos que apunta a un Service que kind no rinde deja el panel en rojo."""
    datasources = kind_configmap("kube-prometheus-stack-grafana-datasource", "datasource.yaml")["datasources"]
    assert datasources, "Grafana sin Prometheus"
    services = kind_services()
    for datasource in datasources:
        assert service_of(datasource["url"]) in services, (datasource["name"], datasource["url"])
        assert datasource["type"] not in {"loki", "tempo"}, datasource["name"]


def test_kind_otel_collector_exports_only_to_services_kind_installs():
    relay = kind_configmap("otel-collector", "relay")
    services = kind_services()
    used = {e for pipeline in relay["service"]["pipelines"].values() for e in pipeline["exporters"]}
    assert used, "un pipeline sin exportadores no arranca"
    for name in used:
        endpoint = relay["exporters"].get(name, {}).get("endpoint")
        if endpoint:
            assert service_of(endpoint) in services, (name, endpoint)
    for pipeline_name, pipeline in relay["service"]["pipelines"].items():
        assert pipeline["exporters"], pipeline_name


def test_kind_network_flows_do_not_mention_removed_components():
    """F62, F63, F65 a F67, F120, F121 y K13 siguen en staging y prod; en kind ni una NetworkPolicy ni una autorizacion de Linkerd nombran a esos pods."""
    for path in sorted((PLATFORM / "network/generated/kind").glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        assert not REMOVED_NAME.search(text), (path.name, REMOVED_NAME.findall(text)[:3])
    # Grafana sigue llegando a Prometheus, y solo al 9090: los 3100 y 3200 eran de Loki y Tempo.
    observability = (PLATFORM / "network/generated/kind/vectra-observability.yaml").read_text(encoding="utf-8")
    ingress = [d for d in yaml.safe_load_all(observability) if d and d["metadata"]["name"] == "allow-f65-to-prometheus-ingress"]
    assert len(ingress) == 1 and [p["port"] for p in ingress[0]["spec"]["ingress"][0]["ports"]] == [9090]


def test_kind_secrets_and_minio_have_nothing_left_for_loki_or_tempo():
    names = {d["metadata"]["name"] for d in rendered() if d["kind"] == "ExternalSecret"}
    assert not {n for n in names if REMOVED_NAME.search(n) or n.endswith(("-loki", "-tempo", "loki-s3", "tempo-s3"))}, names
    values = (PLATFORM / "data/minio/values-kind.yaml").read_text(encoding="utf-8")
    assert not re.search(r"\b(loki|tempo)\b", re.sub(r"^\s*#.*$", "", values, flags=re.M)), "buckets, politicas, usuarios o comandos de Loki o Tempo en MinIO de kind"


def test_the_failover_drill_override_gives_three_instances_to_the_four_clusters():
    """U01-T10 F-02: `values-kind.yaml` fija `instances` por cluster y este gana sobre el global, asi que el override del simulacro (Paso 20) tiene que ser por cluster."""
    override = PLATFORM / "kind/postgres-failover.yaml"
    values = [GITOPS / "envs/kind/values.yaml", PLATFORM / "data/chart/values-kind.yaml", override]
    clusters = {d["metadata"]["name"]: d["spec"] for d in integration.helm("data", PLATFORM / "data/chart", "vectra-data", values) if d["kind"] == "Cluster"}
    assert set(clusters) == {"registry-db", "case-db", "governance-db", "keycloak-db"}
    for name, spec in clusters.items():
        assert spec["instances"] == 3 and spec["minSyncReplicas"] == 1 and spec["maxSyncReplicas"] == 2, name
    # sin el override, kind sigue liviano
    base = {d["metadata"]["name"]: d["spec"]["instances"] for d in integration.helm("data", PLATFORM / "data/chart", "vectra-data", values[:2]) if d["kind"] == "Cluster"}
    assert base == {"registry-db": 2, "case-db": 1, "governance-db": 1, "keycloak-db": 1}


INSTALL_RUNBOOK = PLATFORM / "runbooks/install.md"
FAILOVER_BLOCK = re.compile(r"```bash\n# simulacro-failover: (aplicar|deshacer)\n(.*?)```", re.S)


def failover_procedure() -> dict[str, str]:
    """Los dos bloques del procedimiento del simulacro (Paso 20) tal como los escribe `install.md`."""
    return {name: body for name, body in FAILOVER_BLOCK.findall(INSTALL_RUNBOOK.read_text(encoding="utf-8"))}


def run_in(folder: Path, script: str) -> subprocess.CompletedProcess[str]:
    """Corre el bloque con `bash -e` desde la carpeta `vectra-risk/` de una copia; `python3` es el interprete de las pruebas (tiene PyYAML)."""
    return subprocess.run(["bash", "-ec", script.replace("python3 ", f"{sys.executable} ")], cwd=folder, capture_output=True, text=True, check=False)  # noqa: S603, S607


def application_value_files(folder: Path, name: str) -> list[Path]:
    """Los `valueFiles` de la Application de kind, resueltos como los resuelve Argo CD: relativos a la raiz del repositorio (`/vectra-risk/...`)."""
    application = yaml.safe_load((folder / f"vectra-risk-gitops/apps/kind/{name}.yaml").read_text(encoding="utf-8"))
    files = application["spec"]["source"]["helm"]["valueFiles"]
    return [folder / f.removeprefix("/vectra-risk/") if f.startswith("/vectra-risk/vectra-risk-gitops/") else PLATFORM.parent / f.removeprefix("/vectra-risk/") for f in files]


def test_the_failover_drill_procedure_as_written_gives_three_instances_in_the_four_clusters(tmp_path):
    """U01-T12 F-02: copiar el archivo no basta («Argo CD lo agrega solo» era falso: `valueFiles` sale de `generate.py`); el procedimiento de `install.md` se ejecuta tal cual en una copia."""
    steps = failover_procedure()
    assert steps.keys() == {"aplicar", "deshacer"}, "install.md debe traer los bloques `# simulacro-failover: aplicar` y `deshacer`"
    work = tmp_path / "vectra-risk"
    shutil.copytree(GITOPS, work / "vectra-risk-gitops", ignore=shutil.ignore_patterns("__pycache__"))
    (work / "platform/kind").mkdir(parents=True)
    shutil.copy(PLATFORM / "kind/postgres-failover.yaml", work / "platform/kind/postgres-failover.yaml")
    check = ["vectra-risk-gitops/generate.py", "--check"]
    assert subprocess.run([sys.executable, *check], cwd=work, check=False).returncode == 0
    # solo copiar el archivo (lo que decia el comentario viejo) deja las Applications sin el valueFile: `--check` falla
    copy_only = steps["aplicar"].splitlines()[0]
    assert copy_only.startswith("cp "), copy_only
    assert run_in(work, copy_only).returncode == 0
    assert subprocess.run([sys.executable, *check], cwd=work, check=False).returncode == 1
    assert "values/kind/postgres.yaml" not in (work / "vectra-risk-gitops/apps/kind/postgres.yaml").read_text(encoding="utf-8")
    applied = run_in(work, steps["aplicar"])
    assert applied.returncode == 0, applied.stdout + applied.stderr
    files = application_value_files(work, "postgres")
    assert files[-1] == work / "vectra-risk-gitops/values/kind/postgres.yaml" and all(f.is_file() for f in files), files
    documents = integration.helm("data", PLATFORM / "data/chart", "vectra-data", files)
    clusters = {d["metadata"]["name"]: d["spec"] for d in documents if d["kind"] == "Cluster"}
    assert set(clusters) == {"registry-db", "case-db", "governance-db", "keycloak-db"}
    for name, spec in clusters.items():
        assert spec["instances"] == 3, name
        assert spec["postgresql"]["syncReplicaElectionConstraint"]["nodeLabelsAntiAffinity"] == ["topology.kubernetes.io/zone"], name
    undone = run_in(work, steps["deshacer"])
    assert undone.returncode == 0, undone.stdout + undone.stderr
    assert not (work / "vectra-risk-gitops/values/kind/postgres.yaml").exists()
    assert subprocess.run([sys.executable, *check], cwd=work, check=False).returncode == 0
    base = {d["metadata"]["name"]: d["spec"]["instances"] for d in integration.helm("data", PLATFORM / "data/chart", "vectra-data", application_value_files(work, "postgres")) if d["kind"] == "Cluster"}
    assert base == {"registry-db": 2, "case-db": 1, "governance-db": 1, "keycloak-db": 1}


def kind_datasource_uids() -> set[str]:
    return {d["uid"] for d in kind_configmap("kube-prometheus-stack-grafana-datasource", "datasource.yaml")["datasources"]}


def dangling_in_rules(documents: list[dict]) -> list[str]:
    """Alertas y reglas de grabacion (`PrometheusRule`) cuyo nombre o expresion nombra un componente que kind no instala."""
    problems = []
    for document in documents:
        if document["kind"] != "PrometheusRule":
            continue
        for group in document["spec"].get("groups", []):
            for rule in group.get("rules", []):
                text = f"{rule.get('alert', '')} {rule.get('record', '')} {rule.get('expr', '')}"
                if REMOVED_NAME.search(text):
                    problems.append(f"{document['metadata']['name']}: {rule.get('alert') or rule.get('record')}: {REMOVED_NAME.findall(text)}")
    return problems


def dangling_in_monitors(documents: list[dict]) -> list[str]:
    """`ServiceMonitor` y `PodMonitor` cuyo selector, namespaceSelector o nombre apunta a un componente que kind no instala."""
    problems = []
    for document in documents:
        if document["kind"] in {"ServiceMonitor", "PodMonitor"}:
            text = json.dumps({"name": document["metadata"]["name"], "selector": document["spec"].get("selector"), "namespaces": document["spec"].get("namespaceSelector")})
            if REMOVED_NAME.search(text):
                problems.append(f"{document['metadata']['name']}: {REMOVED_NAME.findall(text)}")
    return problems


def dangling_in_dashboard(board: dict, datasource_uids: set[str]) -> list[str]:
    """Cada `datasource` (de panel, de consulta o de variable) apunta a una fuente que Grafana de kind declara (o a una variable o a la integrada), y ninguna consulta nombra Loki, Tempo ni Alloy."""
    problems: list[str] = []

    def walk(node: object, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "datasource" and value:
                    uid = value.get("uid") if isinstance(value, dict) else value
                    kind = value.get("type", "") if isinstance(value, dict) else ""
                    if kind in REMOVED_FROM_KIND or not (uid in datasource_uids or str(uid).startswith("$") or uid in {"-- Grafana --", "grafana"}):
                        problems.append(f"{where}: datasource {value}")
                elif key in {"expr", "query", "title"} and isinstance(value, str) and REMOVED_NAME.search(value):
                    problems.append(f"{where}: {key} nombra {REMOVED_NAME.findall(value)}")
                else:
                    walk(value, where)
        elif isinstance(node, list):
            for item in node:
                walk(item, where)

    walk(board, str(board.get("title", "dashboard")))
    return problems


# ---- U01-T12 F-07: referencias colgantes en reglas, monitores y dashboards ---------------------------------------------------------------------
def test_kind_dangling_references_rules_monitors_and_dashboards_name_nothing_kind_does_not_install():
    """Hoy ninguna regla, monitor ni dashboard de kind nombra Loki, Tempo ni Alloy, y todo panel apunta a una fuente de datos que Grafana de kind declara."""
    documents = rendered()
    assert [d for d in documents if d["kind"] == "PrometheusRule"] and [d for d in documents if d["kind"] in {"ServiceMonitor", "PodMonitor"}]
    assert dangling_in_rules(documents) == []
    assert dangling_in_monitors(documents) == []
    boards = sorted((PLATFORM / "observability/dashboards").glob("*.json"))
    assert boards
    for board in boards:
        assert dangling_in_dashboard(json.loads(board.read_text(encoding="utf-8")), kind_datasource_uids()) == [], board.name


def test_kind_dangling_references_are_detected_by_a_mutation():
    """Una regla o un panel que nombra Loki (o una fuente de datos que kind no rinde) hace fallar la comprobacion; sin mutacion, no."""
    rule = {"kind": "PrometheusRule", "metadata": {"name": "r"}, "spec": {"groups": [{"rules": [{"alert": "LokiDown", "expr": 'up{job="loki"} == 0'}]}]}}
    assert dangling_in_rules([rule]) and dangling_in_rules([{**rule, "spec": {"groups": [{"rules": [{"alert": "A", "expr": "up == 0"}]}]}}]) == []
    monitor = {"kind": "ServiceMonitor", "metadata": {"name": "m"}, "spec": {"selector": {"matchLabels": {"app.kubernetes.io/name": "tempo"}}}}
    assert dangling_in_monitors([monitor]) and dangling_in_monitors([{**monitor, "spec": {"selector": {"matchLabels": {"app": "x"}}}}]) == []
    uids = kind_datasource_uids()
    board = {"panels": [{"title": "p", "datasource": {"type": "prometheus", "uid": "prometheus"}, "targets": [{"expr": "up"}]}]}
    assert dangling_in_dashboard(board, uids) == []
    for mutate in (
        lambda b: b["panels"][0]["datasource"].update(type="loki", uid="loki"),
        lambda b: b["panels"][0]["targets"][0].update(datasource={"type": "tempo", "uid": "tempo"}),
        lambda b: b["panels"][0]["targets"][0].update(expr='{app="alloy"} |= "error"'),
    ):
        mutated = json.loads(json.dumps(board))
        mutate(mutated)
        assert dangling_in_dashboard(mutated, uids), mutated
