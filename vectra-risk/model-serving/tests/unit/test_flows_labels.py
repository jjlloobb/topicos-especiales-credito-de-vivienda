"""Paso 8 (NFR-U6-21 y NFR-U6-31): las etiquetas del render de U6 son los selectores de F19, F22, F30 y F46 de `platform/network/flows.yaml`
(`generate.labels_of`), y X08 sigue bloqueado. Solo lee `flows.yaml` y `forbidden.yaml` de U1: no los edita."""

import importlib.util
from typing import Any

import pytest
import yaml
from chart_helpers import ROOT, Doc, isvcs, render_profile

NETWORK = ROOT / "platform" / "network"
FLOWS: dict[str, Any] = yaml.safe_load((NETWORK / "flows.yaml").read_text(encoding="utf-8"))
FORBIDDEN: list[dict[str, Any]] = yaml.safe_load((NETWORK / "forbidden.yaml").read_text(encoding="utf-8"))[
    "forbidden"
]


def selector(endpoint: str) -> dict[str, str]:
    """El selector de pods que `generate.py` usa para el extremo (la misma funcion, no una copia)."""
    spec = importlib.util.spec_from_file_location("network_generate", NETWORK / "generate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.labels_of(FLOWS["workloads"][endpoint])  # type: ignore[no-any-return]


def flow(flow_id: str) -> dict[str, Any]:
    (found,) = [f for f in FLOWS["flows"] if f["id"] == flow_id]
    return found


def pods(docs: list[Doc]) -> list[tuple[str, str, str, dict[str, str]]]:
    """(namespace, componente, ServiceAccount, etiquetas del pod) de cada componente de cada InferenceService."""
    return [
        (i["metadata"]["namespace"], c, i["spec"][c]["serviceAccountName"], i["spec"][c]["labels"])
        for i in isvcs(docs)
        for c in i["spec"]
    ]


def matches(endpoint: str, docs: list[Doc], component: str) -> bool:
    workload = FLOWS["workloads"][endpoint]
    want = selector(endpoint)
    return any(
        ns == workload["ns"]
        and sa == workload["sa"]
        and comp == component
        and all(labels.get(k) == v for k, v in want.items())
        for ns, comp, sa, labels in pods(docs)
    )


@pytest.mark.parametrize(
    ("flow_id", "destinations", "profile"),
    [
        ("F19", [("predictor", "predictor")], "prod"),
        ("F22", [("explainer", "explainer")], "prod"),
        ("F30", [("staging-isvc", "predictor")], "staging"),
        ("F46", [("predictor", "predictor"), ("explainer", "explainer")], "prod"),
        ("F46", [("staging-isvc", "predictor")], "staging"),
    ],
)
def test_las_etiquetas_del_render_son_los_selectores_del_flujo(
    flow_id: str, destinations: list[tuple[str, str]], profile: str
) -> None:
    docs = render_profile(profile)
    sources = flow(flow_id)["from"] + flow(flow_id)["to"]
    for endpoint, component in destinations:
        assert endpoint in sources, f"{endpoint} no es un extremo de {flow_id}"
        assert matches(endpoint, docs, component), (
            f"el render {profile} no tiene los pods de {endpoint} ({selector(endpoint)})"
        )


def test_el_inactivo_conserva_las_etiquetas_de_los_selectores() -> None:
    docs = render_profile("inactive")
    assert matches("predictor", docs, "predictor") and matches("explainer", docs, "explainer")


def test_staging_no_tiene_explicador_y_flows_tampoco_lo_alcanza_con_f30() -> None:
    """INF-U6-02 §3 (abierto): `staging-explainer` esta en `workloads`, pero F30 solo lo lista como destino y el render no lo crea."""
    docs = render_profile("staging")
    assert not matches("staging-explainer", docs, "explainer")
    assert {c for _, c, _, _ in pods(docs)} == {"predictor"}


def test_los_cuatro_flujos_y_el_puerto_del_servicio() -> None:
    assert (flow("F19")["port"], flow("F19")["target_port"]) == (80, 8080)
    assert (flow("F22")["port"], flow("F22")["target_port"]) == (80, 8080)
    assert (flow("F30")["port"], flow("F30")["target_port"]) == (80, 8080)
    assert flow("F46")["to"] == ["minio"] and flow("F46")["port"] == 9000
    docs = render_profile("prod")
    assert {
        p["containerPort"]
        for i in isvcs(docs)
        for c in i["spec"]
        for p in i["spec"][c]["containers"][0]["ports"]
    } == {8080, 8081}


def test_x08_sigue_bloqueado() -> None:
    x08 = [(f["from"], f["to"]) for f in FORBIDDEN if f["id"] == "X08"]
    assert ("model-validation-job", "predictor") in x08 and ("predictor", "staging-isvc") in x08
    allowed = {(src, dst) for f in FLOWS["flows"] for src in f["from"] for dst in f["to"]}
    assert ("model-validation-job", "predictor") not in allowed and (
        "predictor",
        "staging-isvc",
    ) not in allowed
