"""`product.json` (Paso 13; BR-U11-04; BR-U11-08; BR-U11-12; BR-U11-13; INF-U11-05; P-U11-05; NFR-U11-06; NFR-U11-33; NFR-U11-41).

El dashboard de la demo D4: el dia D + 1 el presentador ve la North Star, la sostenida, la tasa de consulta y los dias bajo el piso. Un panel vacio es el
defecto que ninguna prueba de render atrapa, asi que aqui el **mundo cerrado**: toda serie que nombra una expresion es un `record` de las reglas
versionadas (`observability/rules/product-metrics.rules.yaml`); toda `:dedup` graba una clave de `collector.PRODUCT_SERIES`; toda etiqueta de un
selector la emite el `collector` para esa serie, y los valores de `metric` y `period` son los que el `collector` publica.
Cada caso de `MUTATIONS` rompe una cosa de `product.json` y una de las comprobaciones debe encontrarla.
"""

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from chart_render import ROOT, render
from vectra_product import collector

DASHBOARD = ROOT / "product-metrics" / "observability" / "dashboards" / "product.json"
CHART_COPY = ROOT / "product-metrics" / "chart" / "files" / "product.json"
RULES = ROOT / "product-metrics" / "observability" / "rules" / "product-metrics.rules.yaml"
OPERACION = ROOT / "platform" / "observability" / "dashboards" / "operacion.json"
SIDECAR = ROOT / "platform" / "observability" / "values" / "kube-prometheus-stack.yaml"
FOLDERS = ROOT / "platform" / "observability" / "grafana" / "folder-permissions.yaml"

NOTE = (
    "aproximación: mide si la decisión siguió la recomendación; la revisión del comité no está en el sistema"
)
NO_TARGET = "sin target acordado"
FOLDER_TITLE = "Vectra / Producto"
Dash = dict[str, Any]

SERIES_TOKEN = re.compile(r"\bvectra[_:][A-Za-z0-9_:]*")
SELECTOR = re.compile(r"(vectra[_:][A-Za-z0-9_:]*)\s*\{([^}]*)\}")
MATCHER = re.compile(r'([A-Za-z_]\w*)\s*(=~|!~|!=|=)\s*"([^"]*)"')
AGGREGATION = re.compile(
    r"\b(?:sum|avg|min|max|count|quantile|topk|bottomk)(?:\s+(?:by|without)\s*\([^)]*\))?\s*\("
)
OPERATION_SERIES = tuple(collector.OPERATION_SERIES) + ("vectra_product_cycle_duration_seconds_bucket",)

# Los cuatro paneles que enseña D4 (enmienda §1.4) y los periodos que tienen datos el dia D + 1: ayer (`day`) y los 30 dias (`30d`); la tasa de consulta
# solo tiene la ventana de 7 dias; los dias bajo el piso no llevan periodo. Un panel que solo consulta `month` esta vacio ese dia (el mes cerrado mas reciente aun no existe).
D4_PANELS = {
    "North Star: decisiones": {"day", "30d"},
    "Recomendaciones sostenidas": {"day", "30d"},
    "Tasa de consulta": {"7d"},
    "Días bajo el piso": None,
}
# BR-U11-12: cada panel del dashboard, por una palabra de su titulo.
REQUIRED_TITLES = (
    "North Star:",
    "desglose",
    "Tasa de consulta",
    "Días bajo el piso",
    "sostenida",
    "Tiempo de originación",
    "Respuesta completa",
    "Fail-closed",
    "no atribuibles",
    "excluidas",
    "degradados",
)
TARGET_METRICS_ON_PANELS = (
    "north_star",
    "noise_floor",
    "sustained_ratio_month6",
    "origination_hours",
    "origination_ratio",
    "complete_response",
)


def load(path: Path = DASHBOARD) -> Dash:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def records() -> dict[str, str]:
    spec = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    return {r["record"]: r["expr"] for g in spec["groups"] for r in g["rules"] if "record" in r}


def expressions(dash: Dash) -> list[tuple[Dash, str]]:
    return [(p, t["expr"]) for p in dash["panels"] for t in p["targets"]]


def source_of(recorded: str) -> str | None:
    """`vectra:product_x:dedup` -> `vectra_product_x` (la clave de `PRODUCT_SERIES` que graba), o `None` si no es una `:dedup`."""
    match = re.fullmatch(r"vectra:(product_[a-z0-9_]+):dedup", recorded)
    return f"vectra_{match.group(1)}" if match else None


def allowed_periods(source: str) -> set[str]:
    if source.startswith("vectra_product_explanation_view_"):
        return {collector.VIEW_PERIOD}
    if source == "vectra_product_unattributable_decisions":
        return set(collector.UNATTRIBUTABLE_PERIODS)
    return {"day", "30d", "month_to_date", collector.MONTH_PERIOD}


def problems(dash: Dash, recorded: dict[str, str]) -> list[str]:
    """Todo lo que esta mal en un `product.json`, con su etiqueta (`tag: detalle`)."""
    found: list[str] = []
    exprs = expressions(dash)
    for panel, expr in exprs:
        for token in SERIES_TOKEN.findall(expr):
            if token.startswith("vectra_product_"):
                found.append(
                    f"raw: {panel['title']}: referencia a la serie cruda {token} (P-U11-05, NFR-U11-06)"
                )
            elif token not in recorded:
                found.append(
                    f"closed-series: {panel['title']}: {token} no es un record de las reglas (panel vacio)"
                )
            if token in OPERATION_SERIES or token.startswith(("vectra_product_cycle", "vectra_circuit")):
                found.append(
                    f"operation: {panel['title']}: {token} es una serie de operacion del ciclo (NFR-U11-41)"
                )
        if AGGREGATION.search(expr):
            for token in SERIES_TOKEN.findall(expr):
                if not token.endswith(":dedup"):
                    found.append(
                        f"aggregate: {panel['title']}: una agregacion sobre {token}, que no es :dedup (NFR-U11-06)"
                    )
        if re.search(r"\bavg(?:_over_time)?\b", expr) and "ratio" in expr:
            found.append(
                f"avg: {panel['title']}: promedio de razones; una razon de varios cortes es sum(numerador) / sum(denominador) (P-U11-05)"
            )
        for series, body in SELECTOR.findall(expr):
            source = source_of(series)
            if source is None:
                continue  # los records sin `:dedup` (`:1h`, `:rate1h`) no llevan etiquetas de la allowlist
            for label, _op, value in MATCHER.findall(body):
                if label not in collector.PRODUCT_SERIES.get(source, frozenset()):
                    found.append(
                        f"closed-label: {panel['title']}: {series} no tiene la etiqueta {label}; el collector emite {sorted(collector.PRODUCT_SERIES.get(source, []))}"
                    )
                elif label == "metric" and value not in collector.TARGET_METRICS:
                    found.append(f"closed-metric: {panel['title']}: metric={value} no esta en TARGET_METRICS")
                elif label == "period" and value not in allowed_periods(source):
                    found.append(f"closed-period: {panel['title']}: period={value} no existe para {series}")
    # series que ninguna regla graba: un `record` sin clave de la allowlist
    for name, expr in recorded.items():
        source = source_of(name)
        if source is not None and source not in collector.PRODUCT_SERIES:
            found.append(f"closed-record: {name} no graba una clave de PRODUCT_SERIES")
    joined = json.dumps(dash, ensure_ascii=False)
    if NOTE not in joined:
        found.append("note: falta la nota de aproximacion de la sostenida (BR-U11-04)")
    if NO_TARGET not in joined:
        found.append("no-target: falta «sin target acordado» en la North Star (BR-U11-12)")
    titles = " | ".join(p["title"].lower() for p in dash["panels"])
    for word in REQUIRED_TITLES:
        if word.lower() not in titles:
            found.append(f"panels: falta el panel de «{word}» (BR-U11-12)")
    all_exprs = " ".join(e for _, e in exprs)
    for metric in TARGET_METRICS_ON_PANELS:
        if f'vectra:product_target:dedup{{metric="{metric}"}}' not in all_exprs:
            found.append(
                f"target-lines: falta la linea del target {metric} tomada de vectra:product_target:dedup (no un numero escrito)"
            )
    for panel in dash["panels"]:
        steps = [
            s
            for s in panel.get("fieldConfig", {}).get("defaults", {}).get("thresholds", {}).get("steps", [])
            if s.get("value") is not None
        ]
        if steps:
            found.append(
                f"target-lines: {panel['title']}: umbrales con numeros escritos en el JSON; los targets salen de la serie"
            )
        description = panel.get("description", "")
        if "Periodo:" not in description:
            found.append(f"period-stated: {panel['title']}: el panel no dice que periodo usa (BR-U11-08)")
        for owner, expr in exprs:
            if owner is not panel:
                continue
            for _series, body in SELECTOR.findall(expr):
                for label, _op, value in MATCHER.findall(body):
                    if label == "period" and value not in description:
                        found.append(f"period-stated: {panel['title']}: usa period={value} y no lo dice")
    for prefix, periods in D4_PANELS.items():
        d4 = [p for p in dash["panels"] if p["title"].startswith(prefix)]
        if not d4:
            found.append(f"panels: falta el panel de D4 «{prefix}»")
            continue
        if periods is None:
            continue
        used = {
            v
            for pnl in d4
            for owner, e in exprs
            if owner is pnl
            for _s, body in SELECTOR.findall(e)
            for lab, _o, v in MATCHER.findall(body)
            if lab == "period"
        }
        if not used & periods:
            found.append(
                f"d4-period: «{prefix}» consulta {sorted(used)} y D + 1 solo tiene datos en {sorted(periods)} (no basta `month`)"
            )
    if dash.get("timezone") != "America/Bogota":
        found.append("timezone: el dashboard muestra la hora de Colombia (America/Bogota; BR-U11-08)")
    for panel in dash["panels"]:
        if panel.get("datasource", {}).get("uid") != "prometheus":
            found.append(f"datasource: {panel['title']}: datasource.uid prometheus")
    return found


def test_the_dashboard_as_is_has_no_problems() -> None:
    assert problems(load(), records()) == []


def _expr(index: int, expr: str) -> Callable[[Dash], None]:
    return lambda d: d["panels"][index]["targets"][0].__setitem__("expr", expr)


def _title_index(prefix: str) -> int:
    return next(i for i, p in enumerate(load()["panels"]) if p["title"].startswith(prefix))


def _drop_panel(prefix: str) -> Callable[[Dash], None]:
    return lambda d: d["panels"].remove(next(p for p in d["panels"] if p["title"].startswith(prefix)))


def _replace_everywhere(old: str, new: str) -> Callable[[Dash], None]:
    def change(d: Dash) -> None:
        text = json.dumps(d, ensure_ascii=False)
        assert old in text, old
        d.clear()
        d.update(json.loads(text.replace(old, new)))

    return change


def _append_target(panel_prefix: str, expr: str) -> Callable[[Dash], None]:
    def change(d: Dash) -> None:
        panel = next(p for p in d["panels"] if p["title"].startswith(panel_prefix))
        panel["targets"].append({"expr": expr, "refId": "Z"})

    return change


def _set_panel(panel_prefix: str, key: str, value: Any) -> Callable[[Dash], None]:
    def change(d: Dash) -> None:
        next(p for p in d["panels"] if p["title"].startswith(panel_prefix))[key] = value

    return change


# (nombre, etiqueta que debe aparecer, cambio de `product.json`)
MUTATIONS: list[tuple[str, str, Callable[[Dash], None]]] = [
    (
        "una serie vectra_product_* cruda",
        "raw",
        _append_target("North Star:", "vectra_product_north_star_ratio"),
    ),
    (
        "sum sobre la serie cruda de la North Star",
        "raw",
        _append_target("North Star:", "sum(vectra_product_north_star_decisions)"),
    ),
    (
        "un sum sobre una serie que no es :dedup",
        "aggregate",
        _append_target("Respuesta completa", "sum(vectra:product_complete_response_ratio:1h)"),
    ),
    (
        "avg de razones",
        "avg",
        _append_target("North Star:", 'avg(vectra:product_north_star_ratio:dedup{period="30d"})'),
    ),
    ("sin la nota de aproximacion", "note", _replace_everywhere(NOTE, "la sostenida")),
    ("sin «sin target acordado»", "no-target", _replace_everywhere(NO_TARGET, "")),
    ("un panel de BR-U11-12 quitado: la tasa de consulta", "panels", _drop_panel("Tasa de consulta")),
    ("un panel de BR-U11-12 quitado: degradados", "panels", _drop_panel("Aviso de datos degradados")),
    (
        "el target de la sostenida escrito como numero",
        "target-lines",
        _replace_everywhere('vectra:product_target:dedup{metric=\\"sustained_ratio_month6\\"}', "0.7"),
    ),
    (
        "el piso F escrito como numero",
        "target-lines",
        _replace_everywhere('vectra:product_target:dedup{metric=\\"noise_floor\\"}', "0.6"),
    ),
    (
        "umbrales con numeros",
        "target-lines",
        _set_panel(
            "Tasa de consulta",
            "fieldConfig",
            {
                "defaults": {
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "green", "value": None}, {"color": "red", "value": 0.6}],
                    }
                }
            },
        ),
    ),
    (
        "una serie que ninguna regla graba",
        "closed-series",
        _append_target("North Star:", "vectra:product_no_existe:dedup"),
    ),
    (
        "la misma serie sin :dedup en las reglas",
        "closed-series",
        _append_target("North Star:", "vectra:product_north_star_ratio"),
    ),
    (
        "una etiqueta que el collector no emite",
        "closed-label",
        _expr(0, 'vectra:product_north_star_ratio:dedup{period="30d", segment="all"}'),
    ),
    (
        "una etiqueta de otra serie (kind en la razon)",
        "closed-label",
        _expr(0, 'vectra:product_north_star_ratio:dedup{kind="sustentada"}'),
    ),
    (
        "un metric fuera de TARGET_METRICS",
        "closed-metric",
        _append_target("Tasa de consulta", 'vectra:product_target:dedup{metric="piso"}'),
    ),
    (
        "period=montly (la errata)",
        "closed-period",
        _expr(0, 'vectra:product_north_star_ratio:dedup{period="montly"}'),
    ),
    (
        "el periodo de 30d en la tasa de consulta",
        "closed-period",
        _expr(
            _title_index("Tasa de consulta"),
            'vectra:product_explanation_view_ratio:dedup{period="30d", channel="all"}',
        ),
    ),
    (
        "la North Star solo con period=month",
        "d4-period",
        _expr(
            _title_index("North Star: decisiones"),
            'vectra:product_north_star_ratio:dedup{period="month", channel="all", outcome="all", model_version_id="all"}',
        ),
    ),
    (
        "la sostenida solo con period=month",
        "d4-period",
        _expr(
            _title_index("Recomendaciones sostenidas"),
            'vectra:product_recommendation_sustained_ratio:dedup{period="month", channel="all", outcome="all"}',
        ),
    ),
    (
        "un panel sin su periodo",
        "period-stated",
        _set_panel("Días bajo el piso", "description", "Una señal de producto."),
    ),
    (
        "un periodo que el panel no dice",
        "period-stated",
        _set_panel("North Star de ayer", "description", "Periodo: ayer."),
    ),
    ("sin la zona horaria de Colombia", "timezone", lambda d: d.__setitem__("timezone", "browser")),
    ("la zona horaria equivocada", "timezone", lambda d: d.__setitem__("timezone", "UTC")),
    (
        "una serie de operacion del ciclo",
        "operation",
        _append_target("Respuesta completa", "vectra_product_cycles_skipped_total"),
    ),
    (
        "el breaker de U3",
        "operation",
        _append_target("Respuesta completa", 'vectra_circuit_state{dependency="decision-registry"}'),
    ),
    (
        "otro datasource",
        "datasource",
        lambda d: d["panels"][0].__setitem__("datasource", {"type": "prometheus", "uid": "otra"}),
    ),
]


@pytest.mark.parametrize(("name", "tag", "change"), MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_each_mutation_of_the_dashboard_is_found(name: str, tag: str, change: Callable[[Dash], None]) -> None:
    mutated = copy.deepcopy(load())
    change(mutated)
    found = problems(mutated, records())
    assert any(f.startswith(f"{tag}:") for f in found), (
        f"{name}: ninguna comprobacion «{tag}» lo encontro: {found}"
    )


def test_every_check_has_a_mutation_that_fails_it() -> None:
    tags = {m[1] for m in MUTATIONS}
    declared = set(re.findall(r'found\.append\(f"([a-z-]+):', Path(__file__).read_text(encoding="utf-8")))
    assert declared - tags - {"closed-record"} == set(), (
        f"comprobaciones sin mutacion: {sorted(declared - tags)}"
    )


def test_a_dedup_record_that_does_not_record_a_key_of_the_allowlist_is_found() -> None:
    recorded = records() | {
        "vectra:product_inventada:dedup": "max without (instance, pod) (vectra_product_inventada)"
    }
    assert any(f.startswith("closed-record:") for f in problems(load(), recorded))


def test_a_dedup_quitada_de_las_reglas_deja_un_panel_vacio_y_se_encuentra() -> None:
    """Una `:dedup` quitada del archivo de reglas, con un panel que la usa: el mundo cerrado falla."""
    recorded = {k: v for k, v in records().items() if k != "vectra:product_north_star_ratio:dedup"}
    assert any(f.startswith("closed-series:") and "north_star_ratio" in f for f in problems(load(), recorded))


# --- el mundo cerrado contra las reglas versionadas -----------------------------------------------------------------------------------------


def test_every_dedup_record_records_exactly_one_key_of_product_series() -> None:
    dedups = {name: expr for name, expr in records().items() if name.endswith(":dedup")}
    sources = []
    for name, expr in dedups.items():
        source = source_of(name)
        assert source in collector.PRODUCT_SERIES, f"{name} no graba una clave de PRODUCT_SERIES"
        assert expr == f"max without (instance, pod) ({source})"
        sources.append(source)
    assert sorted(sources) == sorted(collector.PRODUCT_SERIES)


def test_no_series_of_the_operation_cycle_is_in_product_json_and_operacion_has_the_skipped_cycles_panel() -> (
    None
):
    """NFR-U11-41: `product.json` no lleva series de operacion; `operacion.json` de U1 (dueño del ciclo) tiene el panel de ciclos omitidos."""
    text = json.dumps(load())
    for series in OPERATION_SERIES:
        assert series not in text
    operacion = load(OPERACION)
    skipped = [
        p
        for p in operacion["panels"]
        if any("vectra_product_cycles_skipped_total" in t["expr"] for t in p["targets"])
    ]
    assert len(skipped) == 1 and len(operacion["panels"]) == 5
    ids = [p["id"] for p in operacion["panels"]]
    assert len(set(ids)) == len(ids)
    assert skipped[0]["datasource"] == {"type": "prometheus", "uid": "prometheus"}
    boxes = [
        (p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"], p["gridPos"]["h"])
        for p in operacion["panels"]
    ]
    for i, (x, y, w, h) in enumerate(boxes):
        for x2, y2, w2, h2 in boxes[i + 1 :]:
            assert x + w <= x2 or x2 + w2 <= x or y + h <= y2 or y2 + h2 <= y, (
                "dos paneles de operacion.json se superponen"
            )


# --- el ConfigMap del dashboard (INF-U11-05; BR-U11-12, 13) ------------------------------------------------------------------------------------


def test_the_chart_copy_is_the_canonical_file_byte_for_byte() -> None:
    """P-4 = (a): los archivos canonicos son los de `observability/`; los de `chart/files/` no pueden diferir."""
    assert CHART_COPY.read_bytes() == DASHBOARD.read_bytes()


@pytest.mark.parametrize("env", ("kind", "staging", "prod"))
def test_the_rendered_configmap_is_the_canonical_file_with_the_label_and_folder_of_the_sidecar(
    env: str,
) -> None:
    sidecar = yaml.safe_load(SIDECAR.read_text(encoding="utf-8"))["grafana"]["sidecar"]["dashboards"]
    (config_map,) = [
        d
        for d in render(env)
        if d["kind"] == "ConfigMap" and d["metadata"]["name"] == "product-metrics-dashboard"
    ]
    assert config_map["data"]["product.json"].encode() == DASHBOARD.read_bytes().rstrip(b"\n")
    assert json.loads(config_map["data"]["product.json"]) == load()
    assert sidecar["label"] in config_map["metadata"]["labels"]
    assert config_map["metadata"]["annotations"][sidecar["folderAnnotation"]] == FOLDER_TITLE


def test_the_folder_is_in_folder_permissions_for_the_three_teams_of_br_u11_13() -> None:
    folders = yaml.safe_load(FOLDERS.read_text(encoding="utf-8"))["folders"]
    (folder,) = [f for f in folders if f["title"] == FOLDER_TITLE]
    assert folder["teams"] == {"cro": "View", "cumplimiento": "View", "ingeniero_riesgo": "View"}
    assert load()["folderUid"] == folder["uid"]


def test_the_dashboard_texts_pass_the_forbidden_phrases_tool() -> None:
    import subprocess
    import sys

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "contracts" / "tools" / "forbidden_phrases.py"), str(DASHBOARD)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "", result.stdout
