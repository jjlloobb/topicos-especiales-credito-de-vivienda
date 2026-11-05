"""U02-T13 (Paso 11; CA-3): las alertas de P-U2-09 (enmienda B1-B10), sus monitores y sus runbooks.

Nombres, severidades, `for`, umbrales y ventanas se leen de la tabla de la enmienda de P-U2-09, no de literales de esta prueba. Los
pods que los monitores deben seleccionar salen de los mismos modelos que `platform/network/tests/test_edge_selectors.py` (T12), y los
puertos, de F60 de `platform/network/flows.yaml`. Cada comprobacion es una funcion sobre datos, para probarla tambien sobre una copia
mutada (una familia sin fuente, un umbral cambiado, un runbook borrado, un monitor con otra etiqueta).
"""

import copy
import functools
import re
from pathlib import Path
from typing import Any

import gateway_checks as gc
import pytest
import realm_drift
import signing_key_age
import test_data_plane_policies as data_plane
import test_ratelimit_deployment as ratelimit
import theme_checks as tc
import yaml

ROOT = Path(__file__).resolve().parents[3]
EDGE = ROOT / "identity-edge"
OBS = EDGE / "observability"
RULES_FILE = OBS / "rules" / "identity-edge-rules.yaml"
CR_FILE = OBS / "rules" / "identity-edge-rules.prometheusrule.yaml"
PROMTOOL_TESTS = OBS / "rules" / "tests"
MONITORS_DIR = OBS / "monitors"
RUNBOOKS = EDGE / "runbooks"
TEMPLATE = ROOT / "platform" / "runbooks" / "_template.md"
FLOWS = yaml.safe_load((ROOT / "platform" / "network" / "flows.yaml").read_text(encoding="utf-8"))
PLAN = (ROOT / "aidlc-docs" / "construction" / "plans" / "identity-edge-code-generation-plan.md").read_text(encoding="utf-8")
PATTERNS = (ROOT / "aidlc-docs" / "construction" / "identity-edge" / "nfr-design" / "nfr-design-patterns.md").read_text(encoding="utf-8")
CANDIDATAS = (ROOT / "CANDIDATAS.md").read_text(encoding="utf-8")
MAKEFILE = (EDGE / "Makefile").read_text(encoding="utf-8")
KPS_VALUES = yaml.safe_load((ROOT / "platform" / "observability" / "values" / "kube-prometheus-stack.yaml").read_text(encoding="utf-8"))
KEYCLOAK_VALUES = yaml.safe_load((EDGE / "keycloak" / "values" / "common.yaml").read_text(encoding="utf-8"))
ENVS = ("kind", "staging", "prod")
OBSERVABILITY_NS = "vectra-observability"
Groups = list[dict[str, Any]]

# --- el diseno ------------------------------------------------------------------------------------------------------------------


def design_table() -> dict[str, dict[str, str]]:
    """Alerta -> severidad, expresion (texto del diseno) y `for`, de la tabla de la enmienda de P-U2-09."""
    start = PATTERNS.index("#### Fuentes, umbrales y despliegue")
    section = PATTERNS[start:].split("\n- **B1**", 1)[0]
    rows = {}
    for line in section.splitlines():
        m = re.match(r"\|\s*`(\w+)`\s*\|\s*(SEV\d)\s*\|(.*)\|\s*(\d+[mh])\s*\|\s*$", line)
        if m:
            rows[m.group(1)] = {"severity": m.group(2), "expr": m.group(3).strip(), "for": m.group(4)}
    return rows


DESIGN = design_table()


def seconds(duration: str) -> int:
    return int(duration[:-1]) * {"m": 60, "h": 3600, "d": 86400}[duration[-1]]


def active_text(expr: str) -> str:
    """El texto vigente de una fila: sin lo tachado (`~~...~~`, superado por B10)."""
    return re.sub(r"~~.*?~~", "", expr)


def design_numbers(name: str) -> list[int]:
    """Los umbrales numericos que el diseno fija para `name`, en las unidades de la expresion (segundos, ms, denegaciones/min)."""
    text = active_text(DESIGN[name]["expr"])
    if name == "AuthDeniedBurst":
        return [int(re.search(r"Más de (\d+) denegaciones por minuto", text).group(1))]  # type: ignore[union-attr]
    if name == "SigningKeyAgeHigh":
        return [int(re.search(r"> (\d+) días", text).group(1)) * 86400]  # type: ignore[union-attr]
    if name == "GatewayHighLatency":
        return [int(re.search(r"> (\d+) ms", text).group(1))]  # type: ignore[union-attr]
    if name in ("RealmDriftStale", "SigningKeyAgeStale"):
        return [seconds(re.search(r"> (\d+h)`", text).group(1))]  # type: ignore[union-attr]
    return []


def design_windows(name: str) -> list[str]:
    """Las ventanas `[15m]` que el diseno escribe en la expresion."""
    return re.findall(r"\[(\d+[mh])\]", active_text(DESIGN[name]["expr"]))


def design_tokens(name: str) -> tuple[list[str], list[str]]:
    """(familias de metricas, pares etiqueta="valor") que el diseno cita entre comillas invertidas en la expresion."""
    spans = re.findall(r"`([^`]+)`", active_text(DESIGN[name]["expr"]))
    families = sorted({s for span in spans for s in re.findall(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+", re.sub(r'"[^"]*"', "", span)) if "_" in s})
    pairs = sorted({p for span in spans for p in re.findall(r'\w+="[^"]*"', span)})
    return families, pairs


def design_runbook(name: str) -> str | None:
    m = re.search(r"runbook `([\w-]+)`", DESIGN[name]["expr"])
    return m.group(1) if m else None


def b10_labels() -> dict[str, str]:
    """B10: `event` y `client_id` de `BreakGlassLogin`, y las opciones de la imagen."""
    text = active_text(DESIGN["BreakGlassLogin"]["expr"])
    event = re.search(r"un `(\w+)` en `keycloak_user_events_total`", text)
    client = re.search(r'client_id="([^"]+)"', text)
    assert event and client, "la fila de BreakGlassLogin no lleva event y client_id"
    return {"event": event.group(1), "client_id": client.group(1)}


def plan_runbooks() -> list[str]:
    paso = PLAN[PLAN.index("**Paso 11 — Alertas y runbooks**") :]
    line = re.search(r"Runbooks: (.+)\.", paso).group(1)  # type: ignore[union-attr]
    return re.findall(r"`([\w-]+)`", line)


def b11_text() -> str:
    """El texto de la decision B11 de P-U2-09 (la viñeta, hasta B1)."""
    start = PATTERNS.index("- **B11**")
    return PATTERNS[start:].split("\n- **B1**", 1)[0]


def b11_break_glass_expr() -> str:
    """La expresion de `BreakGlassLogin` de B11, con `X` y `N` sustituidos por lo que el diseno define en B10 y en la propia B11."""
    text = b11_text()
    x_labels = b10_labels()
    x = f'keycloak_user_events_total{{event="{x_labels["event"]}",client_id="{x_labels["client_id"]}",error=""}}'
    n_def = re.search(r"`N = (\(.+?\))`", text).group(1)  # type: ignore[union-attr]
    expr = re.search(r"la expresión es `(.+?)`\.", text).group(1)  # type: ignore[union-attr]
    n = n_def.replace("X", x)
    return " ".join(expr.replace("increase(X[5m])", f"increase({x}[5m])").replace("(N ", f"({n} ").replace("last_over_time(X[1h]", f"last_over_time({x}[1h]").replace("X * 0", f"{x} * 0").split())


def b11_metrics_down() -> dict[str, str]:
    """B11: severidad, `for`, expresion y runbook de `KeycloakMetricsDown` (fila de la tabla y viñeta de B11)."""
    row = DESIGN["KeycloakMetricsDown"]
    text = b11_text()
    absent = re.search(r"`(absent\(up\{job=\"keycloak\"\}\))`", text).group(1)  # type: ignore[union-attr]
    runbook = re.search(r"Runbook `([\w-]+)`", text).group(1)  # type: ignore[union-attr]
    return {**row, "absent": absent, "runbook": runbook}


def operational_runbook() -> str:
    """El runbook operativo de la vuelta de Valkey a la zona A, sin alerta (B7, INF-U2-04). Lo nombra la tarea, no el diseno."""
    assert "**B7**" in PATTERNS and "INF-U2-04" in PATTERNS
    return "valkey-zone-failback"


# --- reglas ---------------------------------------------------------------------------------------------------------------------


def load_groups() -> Groups:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))["groups"]


def alerts(groups: Groups) -> dict[str, dict[str, Any]]:
    return {r["alert"]: r for g in groups for r in g["rules"] if "alert" in r}


def rule_problems(groups: Groups) -> list[str]:
    found: list[str] = []
    rules = alerts(groups)
    if set(rules) != set(DESIGN):
        found.append(f"alertas distintas del diseno: sobran {sorted(set(rules) - set(DESIGN))}, faltan {sorted(set(DESIGN) - set(rules))}")
    for name, row in DESIGN.items():
        rule = rules.get(name)
        if rule is None:
            continue
        expr = str(rule["expr"])
        if rule["labels"].get("severity") != row["severity"]:
            found.append(f"{name}: severidad {rule['labels'].get('severity')} y el diseno dice {row['severity']}")
        if seconds(str(rule.get("for", "0m"))) != seconds(row["for"]):
            found.append(f"{name}: for {rule.get('for', '0m')} y el diseno dice {row['for']}")
        families, pairs = design_tokens(name)
        found += [f"{name}: la expresion no usa {f}" for f in families if f not in expr]
        found += [f"{name}: la expresion no lleva {p}" for p in pairs if p not in expr.replace(" ", "")]
        found += [f"{name}: el umbral {n} no esta en la expresion" for n in design_numbers(name) if not re.search(rf">\s*{n}(?![\d.])", expr)]
        found += [f"{name}: la ventana [{w}] no esta en la expresion" for w in design_windows(name) if f"[{w}]" not in expr]
        url = rule.get("annotations", {}).get("runbook_url", "")
        if not url.startswith("identity-edge/runbooks/") or not (ROOT / url).is_file():
            found.append(f"{name}: runbook_url sin archivo: {url}")
        expected = design_runbook(name)
        if expected and url != f"identity-edge/runbooks/{expected}.md":
            found.append(f"{name}: el diseno manda al runbook {expected} y la alerta apunta a {url}")
    if "KeycloakMetricsDown" in rules:
        expr = str(rules["KeycloakMetricsDown"]["expr"])
        md = b11_metrics_down()
        if md["absent"] not in expr or 'up{job="keycloak"} == 0' not in expr:
            found.append("KeycloakMetricsDown: B11 pide up{job=\"keycloak\"} == 0 o absent(...)")
        if rules["KeycloakMetricsDown"]["annotations"]["runbook_url"] != f"identity-edge/runbooks/{md['runbook']}.md":
            found.append(f"KeycloakMetricsDown: B11 manda al runbook {md['runbook']}")
    if "BreakGlassLogin" in rules:
        expr = str(rules["BreakGlassLogin"]["expr"])
        if " ".join(expr.split()) != b11_break_glass_expr():
            found.append("BreakGlassLogin: la expresion no es la de B11")
        labels = b10_labels()
        for key, value in labels.items():
            if f'{key}="{value}"' not in expr:
                found.append(f'BreakGlassLogin: falta {key}="{value}" (B10)')
        if 'error=""' not in expr:
            found.append('BreakGlassLogin: un login fallido tambien es event="login"; falta error=""')
        if "realm" in expr.replace("realm-", ""):
            found.append("BreakGlassLogin: B10 lo quiere en cualquier realm")
    return found


def test_the_design_table_is_read():
    """Los analizadores devuelven lo que el texto de la fila dice: nada de valores propios de esta prueba."""
    rows = re.findall(r"^\|\s*`(\w+)`\s*\|\s*SEV\d\s*\|.*\|\s*\d+[mh]\s*\|\s*$", PATTERNS[PATTERNS.index("#### Fuentes, umbrales y despliegue") :].split("\n- **B1**", 1)[0], re.M)
    assert sorted(DESIGN) == sorted(rows) and len(rows) == len(set(rows)) > 0
    for name, row in DESIGN.items():
        assert re.fullmatch(r"SEV[123]", row["severity"]) and re.fullmatch(r"\d+[mh]", row["for"]), name
    raw = {n: active_text(DESIGN[n]["expr"]) for n in DESIGN}
    assert [str(n // 86400) for n in design_numbers("SigningKeyAgeHigh")] == re.findall(r"> (\d+) días", raw["SigningKeyAgeHigh"])
    for name in ("RealmDriftStale", "SigningKeyAgeStale"):
        (n,) = design_numbers(name)
        assert f"> {n // 3600}h" in raw[name]
    for name in ("AuthDeniedBurst", "GatewayHighLatency"):
        (n,) = design_numbers(name)
        assert re.search(rf"\b{n}\b", raw[name])
    for name in ("RoleConflict", "LdapUnavailable"):
        assert design_windows(name) and all(f"[{w}]" in DESIGN[name]["expr"] or w in DESIGN[name]["expr"] for w in design_windows(name))
    labels = b10_labels()
    assert labels["event"] and labels["client_id"] and all(f"`{v}`" in DESIGN["BreakGlassLogin"]["expr"] or f'"{v}"' in DESIGN["BreakGlassLogin"]["expr"] for v in labels.values())


def test_the_b11_text_is_read():
    """Lo que se lee de B11 es lo que dice el texto, y la regla de `BreakGlassLogin` es esa expresion."""
    expr = b11_break_glass_expr()
    assert expr.count("increase(") == 1 and expr.count("last_over_time(") == 1 and 'up{job="keycloak"} offset 5m == 1' in expr
    assert "N" not in re.findall(r"\b[A-Z]\b", expr) and "X" not in re.findall(r"\b[A-Z]\b", expr)
    md = b11_metrics_down()
    assert md["severity"] == "SEV2" and md["for"] == "5m" and md["runbook"] == "keycloak-metrics-down"
    assert " ".join(str(alerts(load_groups())["BreakGlassLogin"]["expr"]).split()) == expr


def test_rules_are_the_ones_of_the_design():
    assert rule_problems(load_groups()) == []


def test_the_rules_file_has_only_groups():
    assert list(yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))) == ["groups"]


def test_the_custom_resource_has_the_same_groups_in_vectra_observability():
    cr = yaml.safe_load(CR_FILE.read_text(encoding="utf-8"))
    assert cr["apiVersion"] == "monitoring.coreos.com/v1" and cr["kind"] == "PrometheusRule"
    assert cr["metadata"]["namespace"] == OBSERVABILITY_NS
    assert cr["spec"]["groups"] == load_groups()


def test_the_prometheus_of_u1_picks_up_rules_and_monitors_of_any_namespace():
    """`ruleSelectorNilUsesHelmValues` y los selectores de monitores de `kube-prometheus-stack.yaml`."""
    spec = KPS_VALUES["prometheus"]["prometheusSpec"]
    for key in ("ruleSelectorNilUsesHelmValues", "serviceMonitorSelectorNilUsesHelmValues", "podMonitorSelectorNilUsesHelmValues"):
        assert spec[key] is False, key
    assert spec["podMonitorNamespaceSelector"] == {} and spec["serviceMonitorNamespaceSelector"] == {}


def rules_mutations() -> dict[str, Any]:
    def edit(alert: str, key: str, old: str, new: str):
        def apply(groups: Groups) -> None:
            rule = alerts(groups)[alert]
            if key == "expr":
                assert old in rule["expr"], (alert, old)
                rule["expr"] = rule["expr"].replace(old, new)
            else:
                rule[key] = new

        return apply

    def labels(alert: str, severity: str):
        return lambda groups: alerts(groups)[alert]["labels"].update(severity=severity)

    def drop(alert: str):
        return lambda groups: [g["rules"].remove(alerts(groups)[alert]) for g in groups if alerts(groups)[alert] in g["rules"]]

    return {
        "umbral de AuthDeniedBurst": edit("AuthDeniedBurst", "expr", "> 20", "> 21"),
        "umbral de GatewayHighLatency": edit("GatewayHighLatency", "expr", "> 5", "> 6"),
        "umbral de SigningKeyAgeHigh": edit("SigningKeyAgeHigh", "expr", "6912000", "6912001"),
        "umbral de RealmDriftStale": edit("RealmDriftStale", "expr", "93600", "93601"),
        "umbral de SigningKeyAgeStale": edit("SigningKeyAgeStale", "expr", "10800", "10801"),
        "ventana de RoleConflict": edit("RoleConflict", "expr", "[15m]", "[10m]"),
        "ventana de LdapUnavailable": edit("LdapUnavailable", "expr", "[5m]", "[1m]"),
        "for de KeycloakDown": edit("KeycloakDown", "for", "", "5m"),
        "for de GatewayHighLatency": edit("GatewayHighLatency", "for", "", "1m"),
        "for en una alerta de 0m": edit("BreakGlassLogin", "for", "", "5m"),
        "severidad de BreakGlassLogin": labels("BreakGlassLogin", "SEV2"),
        "severidad de SigningKeyAgeHigh": labels("SigningKeyAgeHigh", "SEV1"),
        "alerta borrada": drop("LdapUnavailable"),
        "alerta de mas": lambda groups: groups[0]["rules"].append({"alert": "Otra", "expr": "vector(1)", "labels": {"severity": "SEV3"}}),
        "cliente de BreakGlassLogin": edit("BreakGlassLogin", "expr", 'client_id="security-admin-console"', 'client_id="vectra-console"'),
        "evento de BreakGlassLogin": edit("BreakGlassLogin", "expr", 'event="login"', 'event="client_login"'),
        "BreakGlassLogin cuenta el login fallido": edit("BreakGlassLogin", "expr", ',error=""', ""),
        "BreakGlassLogin sin la rama de la ultima hora": edit("BreakGlassLogin", "expr", "last_over_time(", "max_over_time("),
        "BreakGlassLogin sin up": edit("BreakGlassLogin", "expr", "offset 5m == 1", "offset 5m >= 0"),
        "BreakGlassLogin con ventana de 30m": edit("BreakGlassLogin", "expr", "[1h] offset 5m", "[30m] offset 5m"),
        "KeycloakMetricsDown sin absent": edit("KeycloakMetricsDown", "expr", " or absent(up{job=\"keycloak\"})", ""),
        "KeycloakMetricsDown sin == 0": edit("KeycloakMetricsDown", "expr", "up{job=\"keycloak\"} == 0", "up{job=\"keycloak\"} == 1"),
        "for de KeycloakMetricsDown": edit("KeycloakMetricsDown", "for", "", "1m"),
        "severidad de KeycloakMetricsDown": labels("KeycloakMetricsDown", "SEV1"),
        "runbook de KeycloakMetricsDown": edit("KeycloakMetricsDown", "annotations", "", {"summary": "x", "runbook_url": "identity-edge/runbooks/keycloak-down.md"}),
        "BreakGlassLogin solo en un realm": edit("BreakGlassLogin", "expr", 'event="login"', 'event="login",realm="vectra"'),
        "metrica de RoleConflict": edit("RoleConflict", "expr", "vectra_role_conflict_total", "vectra_roles_total"),
        "namespace de KeycloakDown": edit("KeycloakDown", "expr", 'namespace="vectra-identity"', 'namespace="vectra-edge"'),
        "runbook de otra alerta": edit("RealmDriftStale", "annotations", "", {"summary": "x", "runbook_url": "identity-edge/runbooks/keycloak-down.md"}),
        "runbook inexistente": edit("KeycloakDown", "annotations", "", {"summary": "x", "runbook_url": "identity-edge/runbooks/no-existe.md"}),
    }


@pytest.mark.parametrize("case", rules_mutations())
def test_a_mutated_rule_is_detected(case):
    groups = copy.deepcopy(load_groups())
    rules_mutations()[case](groups)
    assert rule_problems(groups) != [], case


def test_the_cr_differs_when_a_group_changes():
    cr = yaml.safe_load(CR_FILE.read_text(encoding="utf-8"))
    changed = copy.deepcopy(load_groups())
    alerts(changed)["KeycloakDown"]["for"] = "9m"
    assert cr["spec"]["groups"] != changed


# --- fuentes de las familias de metricas ---------------------------------------------------------------------------------------

PROMQL_WORDS = {"last_over_time", "histogram_quantile", "group_left", "group_right", "label_replace", "label_join"}


def families(groups: Groups) -> set[str]:
    found: set[str] = set()
    for rule in alerts(groups).values():
        bare = re.sub(r"\{[^}]*\}", "", re.sub(r'"[^"]*"', "", str(rule["expr"])))
        found |= {w for w in re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", bare) if w not in PROMQL_WORDS}
    return found


def jobs_used(groups: Groups) -> set[str]:
    return set(re.findall(r'job="([^"]+)"', " ".join(str(r["expr"]) for r in alerts(groups).values())))


#: Quien emite cada familia: un monitor de esta tarea (con el `job` que le pone), kube-state-metrics, el Pushgateway, U0 o una metrica de contrato (B2).
SOURCES: list[tuple[str, tuple[str, str]]] = [
    (r"kube_(statefulset|deployment)_status_replicas_(ready|available)", ("ksm", "")),
    (r"push_time_seconds|vectra_realm_drift|vectra_signing_key_created_timestamp_seconds", ("pushgateway", "")),
    (r"redis_up", ("monitor", "valkey")),
    (r"envoy_(http_downstream_rq_time|cluster_upstream_rq_time)_bucket", ("monitor", "envoy-data-plane")),
    (r"keycloak_user_events_total", ("monitor", "keycloak")),
    (r"vectra_authz_denied_total", ("u0", "")),
    (r"vectra_(role_conflict_total|ldap_connection_failures_total)", ("contract", "")),
]
#: El trabajador de `flows.yaml` al que apunta cada monitor.
MONITOR_WORKLOAD = {"keycloak": "keycloak", "envoy-data-plane": "api-gateway", "envoy-ratelimit": "rate-limit", "valkey": "valkey"}


def source_of(family: str) -> tuple[str, str] | None:
    for pattern, source in SOURCES:
        if re.fullmatch(pattern, family):
            return source
    return None


def load_monitors() -> list[dict[str, Any]]:
    return [d for p in sorted(MONITORS_DIR.glob("*.yaml")) for d in yaml.safe_load_all(p.read_text(encoding="utf-8")) if d]


def monitor_job(doc: dict[str, Any]) -> str:
    (job,) = [r["replacement"] for e in doc["spec"]["podMetricsEndpoints"] for r in e.get("relabelings", []) if r["targetLabel"] == "job"]
    return job


def prometheus_ports(workload: str, flow_id: str = "F60") -> set[int]:
    found: set[int] = set()
    for flow in FLOWS["flows"]:
        if flow["id"] == flow_id and "prometheus" in flow["from"] and workload in flow["to"]:
            found |= set(flow.get("ports", [flow.get("port")]))
    return found


def source_problems(groups: Groups, monitors: list[dict[str, Any]], candidatas: str = CANDIDATAS) -> list[str]:
    found: list[str] = []
    monitor_jobs = {monitor_job(m) for m in monitors}
    for family in sorted(families(groups)):
        source = source_of(family)
        if source is None:
            found.append(f"{family}: ninguna fuente")
            continue
        kind, job = source
        if kind == "monitor" and job not in monitor_jobs:
            found.append(f"{family}: el monitor {job} no existe")
        if kind == "contract" and not re.search(rf"^- .*{re.escape(family)}", candidatas, re.M):
            found.append(f"{family}: su fuente no esta en CANDIDATAS.md")
        if kind == "ksm" and KPS_VALUES["kube-state-metrics"].get("enabled") is False:
            found.append(f"{family}: kube-state-metrics esta apagado en U1")
    for job in jobs_used(groups):
        if job in MONITOR_WORKLOAD and job not in monitor_jobs:
            found.append(f"job {job}: sin monitor")
        if job not in MONITOR_WORKLOAD and job not in {realm_drift.JOB, signing_key_age.JOB}:
            found.append(f"job {job}: ni un monitor de esta tarea ni un job que empuje al Pushgateway")
    return found


def test_every_family_has_a_source():
    assert source_problems(load_groups(), load_monitors()) == []


def test_the_pushgateway_jobs_of_the_stale_rules_are_the_ones_the_jobs_push():
    used = jobs_used(load_groups())
    assert {realm_drift.JOB, signing_key_age.JOB} <= used


def test_the_u0_metric_exists_in_vectra_common_and_prometheus_reaches_its_port():
    text = (ROOT / "contracts" / "python" / "vectra_common" / "src" / "vectra_common" / "metrics.py").read_text(encoding="utf-8")
    assert '"vectra_authz_denied_total"' in text
    assert 8081 in prometheus_ports("ns:vectra-app")


def test_the_pushgateway_is_reachable_by_prometheus():
    assert 9091 in prometheus_ports("pushgateway", "F88")


def test_the_event_metric_options_are_in_the_image_and_in_the_start_env():
    """B10 corregido: `event-metrics-user-enabled` (build) activa `keycloak_user_events_total`; `KC_EVENT_METRICS_USER_TAGS` con `clientId` (arranque) da `client_id`."""
    text = (EDGE / "keycloak" / "Dockerfile").read_text(encoding="utf-8")
    options = tc.design_event_metric_options()
    assert options and all(option in text for option in options)
    name, value = tc.design_event_metric_env()
    assert not any(name[len("KC_") :].lower().replace("_", "-") in option for option in options)  # la opcion de ejecucion no va en el build
    assert name[len("KC_") :].lower().replace("_", "-") not in text and "clientId" in value.split(",")


def source_mutations() -> dict[str, Any]:
    def add_alert(groups: Groups, monitors: list[dict[str, Any]]) -> None:
        groups[0]["rules"].append({"alert": "Nueva", "expr": "mi_metrica_total > 0", "labels": {"severity": "SEV3"}})

    def drop_monitor(job: str):
        def apply(groups: Groups, monitors: list[dict[str, Any]]) -> None:
            monitors[:] = [m for m in monitors if monitor_job(m) != job]

        return apply

    def other_job(groups: Groups, monitors: list[dict[str, Any]]) -> None:
        alerts(groups)["RateLimitBackendDown"]["expr"] = alerts(groups)["RateLimitBackendDown"]["expr"].replace('job="valkey"', 'job="redis"')

    return {
        "familia sin fuente": add_alert,
        "sin monitor de valkey": drop_monitor("valkey"),
        "sin monitor de keycloak": drop_monitor("keycloak"),
        "sin monitor de envoy": drop_monitor("envoy-data-plane"),
        "job sin monitor": other_job,
    }


@pytest.mark.parametrize("case", source_mutations())
def test_a_family_without_source_is_detected(case):
    groups, monitors = copy.deepcopy(load_groups()), copy.deepcopy(load_monitors())
    source_mutations()[case](groups, monitors)
    assert source_problems(groups, monitors) != [], case


def test_a_contract_metric_missing_from_candidatas_is_detected():
    assert source_problems(load_groups(), load_monitors(), candidatas="") != []


# --- monitores ------------------------------------------------------------------------------------------------------------------


@functools.cache
def real_pods(env: str) -> dict[str, dict[str, Any]]:
    """Trabajador -> {ns, labels, ports} de los pods reales, con los modelos de T12 (y los de U2 para Keycloak y Valkey)."""
    plane = data_plane.data_plane_deployment(gc.load_env(env), env)
    limiter = ratelimit.ratelimit_deployment(ratelimit.controller_config(ratelimit.render(env)))
    docs = {
        "keycloak": EDGE / "keycloak" / "rendered" / env / "keycloak.yaml",
        "valkey": EDGE / "charts" / "valkey" / "rendered" / env / "valkey.yaml",
    }

    def of_sets(path: Path, prefix: str) -> dict[str, Any]:
        sets = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d and d["kind"] == "StatefulSet" and d["metadata"]["name"].startswith(prefix)]
        assert sets, prefix
        return {
            "ns": sets[0]["metadata"]["namespace"],
            "pods": [
                {
                    "labels": s["spec"]["template"]["metadata"]["labels"],
                    "ports": {p["name"]: p["containerPort"] for c in s["spec"]["template"]["spec"]["containers"] for p in c.get("ports", []) if "name" in p},
                }
                for s in sets
            ],
        }

    def of_deployment(dep: dict[str, Any], extra: dict[str, int]) -> dict[str, Any]:
        containers = dep["spec"]["template"]["spec"]["containers"]
        ports = {p["name"]: p["containerPort"] for c in containers for p in c.get("ports", []) if "name" in p}
        return {"ns": dep["metadata"]["namespace"], "pods": [{"labels": dep["spec"]["template"]["metadata"]["labels"], "ports": {**ports, **extra}}]}

    return {
        "keycloak": of_sets(docs["keycloak"], "keycloak"),
        "valkey": of_sets(docs["valkey"], "valkey-"),
        # `resource.go` de Envoy Gateway v1.9.3 (linea 93): el puerto `metrics` es `bootstrap.EnvoyStatsPort`, que el modelo no declara.
        # El numero sale de F60 de `flows.yaml` (T3 de U1: estadisticas del data plane), no de un literal de esta prueba.
        "api-gateway": of_deployment(plane, {"metrics": min(prometheus_ports("api-gateway"))}),
        "rate-limit": of_deployment(limiter, {}),
    }


def selects(selector: dict[str, str], labels: dict[str, str]) -> bool:
    return bool(selector) and all(labels.get(k) == v for k, v in selector.items())


def endpoint_port(endpoint: dict[str, Any], pod: dict[str, Any]) -> int | None:
    if "portNumber" in endpoint:
        return int(endpoint["portNumber"])
    return pod["ports"].get(endpoint.get("port", ""))


def monitor_problems(monitors: list[dict[str, Any]], env: str) -> list[str]:
    found: list[str] = []
    by_job = {monitor_job(m): m for m in monitors}
    if set(by_job) != set(MONITOR_WORKLOAD):
        found.append(f"monitores {sorted(by_job)} y se esperaban {sorted(MONITOR_WORKLOAD)}")
    pods = real_pods(env)
    for job, workload in MONITOR_WORKLOAD.items():
        doc = by_job.get(job)
        if doc is None:
            continue
        real = pods[workload]
        own = doc["metadata"]["namespace"]
        names = doc["spec"].get("namespaceSelector", {}).get("matchNames", [own])
        if real["ns"] not in names:
            found.append(f"{job}: busca en {names} y los pods estan en {real['ns']}")
        if doc["kind"] != "PodMonitor":
            found.append(f"{job}: debe ser un PodMonitor")
        selector = doc["spec"]["selector"].get("matchLabels", {})
        for pod in real["pods"]:
            if not selects(selector, pod["labels"]):
                found.append(f"{job}: el selector {selector} no selecciona un pod que lleva {pod['labels']}")
        (ep,) = doc["spec"]["podMetricsEndpoints"]
        for pod in real["pods"]:
            port = endpoint_port(ep, pod)
            if port is None:
                found.append(f"{job}: el puerto {ep.get('port')} no existe en el pod")
            elif port not in prometheus_ports(workload):
                found.append(f"{job}: F60 no abre el {port} hacia {workload}")
    return found


@pytest.mark.parametrize("env", ENVS)
def test_the_monitors_select_the_real_pods_on_ports_f60_opens(env):
    assert monitor_problems(load_monitors(), env) == []


def test_every_monitor_is_in_a_namespace_prometheus_reads_and_carries_the_criticality_label():
    for doc in load_monitors():
        assert doc["apiVersion"] == "monitoring.coreos.com/v1"
        assert doc["metadata"]["labels"].get("vectra.io/criticality"), doc["metadata"]["name"]
        assert doc["metadata"]["namespace"] in {OBSERVABILITY_NS, "vectra-identity"}


def test_keycloak_is_scraped_over_https_on_the_management_path_with_the_internal_ca():
    (doc,) = [m for m in load_monitors() if monitor_job(m) == "keycloak"]
    (ep,) = doc["spec"]["podMetricsEndpoints"]
    values = KEYCLOAK_VALUES
    assert ep["scheme"] == "https" and ep["port"] == "http-internal"
    # El puerto de gestion hereda `http-relative-path` (ManagementPropertyMappers.java de 26.8.1): /auth/metrics.
    assert ep["path"] == values["http"]["relativePath"] + "/metrics"
    assert ep["tlsConfig"]["serverName"] == values["vectra"]["tlsHostname"]
    ca = ep["tlsConfig"]["ca"]["secret"]
    assert ca == {"name": "identity-ca", "key": "ca.crt"}
    assert doc["metadata"]["namespace"] == "vectra-identity"  # el Secret de la CA es de ese namespace


def test_envoy_and_ratelimit_paths():
    paths = {monitor_job(m): m["spec"]["podMetricsEndpoints"][0].get("path") for m in load_monitors()}
    assert paths["envoy-data-plane"] == "/stats/prometheus"
    assert paths["envoy-ratelimit"] == "/metrics"
    assert paths["valkey"] in (None, "/metrics")


def monitor_mutations() -> dict[str, Any]:
    def spec(job: str, change):
        def apply(monitors: list[dict[str, Any]]) -> None:
            (doc,) = [m for m in monitors if monitor_job(m) == job]
            change(doc)

        return apply

    return {
        "etiqueta de keycloak": spec("keycloak", lambda d: d["spec"]["selector"]["matchLabels"].update({"app.kubernetes.io/name": "otro"})),
        "etiqueta de valkey": spec("valkey", lambda d: d["spec"]["selector"]["matchLabels"].update({"app.kubernetes.io/name": "sentinel"})),
        "etiqueta de envoy": spec("envoy-data-plane", lambda d: d["spec"]["selector"].update(matchLabels={"gateway.envoyproxy.io/owning-gateway-name": "otro"})),
        "etiqueta de ratelimit": spec("envoy-ratelimit", lambda d: d["spec"]["selector"]["matchLabels"].update({"app.kubernetes.io/component": "otro"})),
        "namespace de ratelimit": spec("envoy-ratelimit", lambda d: d["spec"].update(namespaceSelector={"matchNames": ["vectra-edge"]})),
        "puerto de valkey": spec("valkey", lambda d: d["spec"]["podMetricsEndpoints"][0].update(port="redis")),
        "puerto de envoy fuera de F60": spec("envoy-data-plane", lambda d: d["spec"]["podMetricsEndpoints"][0].update(portNumber=9902)),
        "puerto inexistente": spec("keycloak", lambda d: d["spec"]["podMetricsEndpoints"][0].update(port="metrics")),
        "monitor borrado": lambda monitors: monitors.pop(),
        "es un ServiceMonitor": spec("valkey", lambda d: d.update(kind="ServiceMonitor")),
    }


@pytest.mark.parametrize("case", monitor_mutations())
def test_a_monitor_that_does_not_select_the_pods_is_detected(case):
    monitors = copy.deepcopy(load_monitors())
    monitor_mutations()[case](monitors)
    assert monitor_problems(monitors, "prod") != [], case


# --- runbooks -------------------------------------------------------------------------------------------------------------------


def runbook_problems(folder: Path, groups: Groups) -> list[str]:
    found: list[str] = []
    expected = set(plan_runbooks()) | {operational_runbook(), b11_metrics_down()["runbook"]}
    present = {p.stem for p in folder.glob("*.md")}
    if present != expected:
        found.append(f"runbooks: sobran {sorted(present - expected)}, faltan {sorted(expected - present)}")
    sections = re.findall(r"^## .+$", TEMPLATE.read_text(encoding="utf-8"), flags=re.M)
    for path in sorted(folder.glob("*.md")):
        headings = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}
        found += [f"{path.name}: falta {s}" for s in sections if s not in headings]
    urls = {Path(r["annotations"]["runbook_url"]).stem for r in alerts(groups).values()}
    found += [f"{n}: ninguna alerta lo usa" for n in sorted((set(plan_runbooks()) | {b11_metrics_down()["runbook"]}) - urls)]
    return found


def test_the_runbooks_are_the_plan_list_plus_the_valkey_failback_and_the_b11_one():
    assert len(plan_runbooks()) == 9 and operational_runbook() == "valkey-zone-failback" and b11_metrics_down()["runbook"] == "keycloak-metrics-down"
    assert runbook_problems(RUNBOOKS, load_groups()) == []


def test_a_deleted_runbook_is_detected(tmp_path):
    for path in RUNBOOKS.glob("*.md"):
        (tmp_path / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "keycloak-down.md").unlink()
    assert runbook_problems(tmp_path, load_groups()) != []


def test_a_runbook_without_a_section_is_detected(tmp_path):
    for path in RUNBOOKS.glob("*.md"):
        (tmp_path / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    broken = tmp_path / "realm-drift.md"
    broken.write_text(broken.read_text(encoding="utf-8").replace("## Escalamiento", "## Otro"), encoding="utf-8")
    assert runbook_problems(tmp_path, load_groups()) != []


def test_an_extra_runbook_is_detected(tmp_path):
    for path in RUNBOOKS.glob("*.md"):
        (tmp_path / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "otro.md").write_text("# otro\n", encoding="utf-8")
    assert runbook_problems(tmp_path, load_groups()) != []


# --- Makefile -------------------------------------------------------------------------------------------------------------------


def make_problems(text: str) -> list[str]:
    found = []
    check = re.search(r"^check:(.*)$", text, re.M)
    for target in ("rules", "runbooks"):
        if not re.search(rf"^{target}:", text, re.M):
            found.append(f"falta el target {target}")
        if not check or target not in check.group(1).split():
            found.append(f"check no incluye {target}")
    rules = re.search(r"^rules:.*?(?=^\S|\Z)", text, re.M | re.S)
    body = rules.group(0) if rules else ""
    if "check rules" not in body or "test rules" not in body:
        found.append("rules debe correr promtool check rules y promtool test rules")
    runbooks = re.search(r"^runbooks:.*?(?=^\S|\Z)", text, re.M | re.S)
    body = runbooks.group(0) if runbooks else ""
    if "--root identity-edge" not in body or "--operational" not in body:
        found.append("runbooks debe correr test_runbooks.py con --root identity-edge y con --operational")
    return found


def test_the_makefile_has_rules_and_runbooks_in_check():
    assert make_problems(MAKEFILE) == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda t: re.sub(r"^(check:.*)$", lambda m: m.group(1).replace(" rules", "").replace(" runbooks", ""), t, flags=re.M),
        lambda t: t.replace("\nrules:", "\nrules-x:"),
        lambda t: t.replace("\nrunbooks:", "\nrunbooks-x:"),
        lambda t: t.replace("test rules", "check rules"),
        lambda t: t.replace("--operational", ""),
    ],
)
def test_a_makefile_without_the_targets_is_detected(mutation):
    assert make_problems(mutation(MAKEFILE)) != []


def test_a_promtool_test_file_exists_and_covers_every_alert():
    files = sorted(PROMTOOL_TESTS.glob("*.yaml"))
    assert files
    text = "\n".join(f.read_text(encoding="utf-8") for f in files)
    for name in DESIGN:
        assert f"alertname: {name}" in text, name
