"""U01-T19: en kind, las sondas de los operadores aguantan una racha de CPU lenta de la maquina.

Medido el 2026-11-17: en rachas la CPU de todo el cluster rinde 4 a 5 veces menos, las sondas fallan por plazo agotado (`timeoutSeconds` por defecto: 1 s)
y los operadores se reinician. Se renderiza cada chart con sus values de kind (`helm template`, como `test_upstream_charts.py`) y, en cada contenedor de la
lista, toda sonda de vida o de disponibilidad tiene `timeoutSeconds >= 5` y toda sonda de vida un margen (`periodSeconds x failureThreshold`) de al menos 120 s.
Si faltan los charts: `make -C platform charts`.
"""

import copy
from functools import cache

import integration
import pytest

MIN_TIMEOUT = 5
MIN_LIVENESS_MARGIN = 120

# (componente, workload, contenedor): los operadores que se reiniciaron. El application-controller de Argo CD, los controladores de fondo, de informes y
# el cainjector no traen sonda de vida en su chart (la prueba mira las que existan), y el `controller` de cert-manager no trae sonda de disponibilidad.
CONTAINERS = [
    ("argo-cd", "argo-cd-argocd-repo-server", "repo-server"),
    ("argo-cd", "argo-cd-argocd-server", "server"),
    ("argo-cd", "argo-cd-argocd-application-controller", "application-controller"),
    ("cloudnative-pg", "cloudnative-pg", "manager"),
    ("kyverno", "kyverno-admission-controller", "kyverno"),
    ("kyverno", "kyverno-background-controller", "controller"),
    ("kyverno", "kyverno-cleanup-controller", "controller"),
    ("kyverno", "kyverno-reports-controller", "controller"),
    ("metrics-server", "metrics-server", "metrics-server"),
    ("cert-manager", "cert-manager", "cert-manager-controller"),
    ("cert-manager", "cert-manager-webhook", "cert-manager-webhook"),
    ("cert-manager", "cert-manager-cainjector", "cert-manager-cainjector"),
    ("trust-manager", "trust-manager", "trust-manager"),
]  # fmt: skip

# Lo que el chart no deja tocar (sin `timeoutSeconds`, `periodSeconds` ni `failureThreshold` en sus values y plantilla): candidatas, no parches a mano.
# La prueba exige que sigan sin poderse: si el chart los expone, se quita la entrada y la sonda entra en la regla.
UNTOUCHABLE = {
    ("cloudnative-pg", "manager", "livenessProbe"): "webhook.livenessProbe solo expone initialDelaySeconds",
    ("cloudnative-pg", "manager", "readinessProbe"): "webhook.readinessProbe solo expone initialDelaySeconds",
    ("trust-manager", "trust-manager", "readinessProbe"): "plantilla fija initialDelaySeconds y periodSeconds; solo se elige puerto y ruta",
}  # fmt: skip


@cache
def rendered(name: str) -> tuple[dict, ...]:
    component = next(c for c in integration.CONFIG["components"] if c["name"] == name)
    chart = integration.CHARTS / name / component["chart"]
    assert chart.is_dir(), f"Falta {chart}: corre `make -C platform charts`"
    files = [integration.ROOT / f for f in [*component.get("values", []), *component.get("kind_values", [])]]
    return tuple(integration.helm(name, chart, component["namespace"], files))


def container(documents, workload: str, name: str) -> dict:
    found = [
        c
        for d in documents
        if d["kind"] in ("Deployment", "StatefulSet", "DaemonSet") and d["metadata"]["name"] == workload
        for c in d["spec"]["template"]["spec"]["containers"]
        if c["name"] == name
    ]
    assert len(found) == 1, f"{workload}/{name}: {len(found)} contenedores en el render"
    return found[0]


def violations(component: str, workload: str, name: str, spec: dict) -> list[str]:
    """Una linea por regla rota en este contenedor."""
    problems = []
    for probe in ("livenessProbe", "readinessProbe"):
        if probe not in spec or (component, name, probe) in UNTOUCHABLE:
            continue
        values = spec[probe]
        timeout = values.get("timeoutSeconds", 1)  # lo que Kubernetes aplica si falta
        if timeout < MIN_TIMEOUT:
            problems.append(f"{workload}/{name} {probe}: timeoutSeconds {timeout} < {MIN_TIMEOUT}")
        margin = values.get("periodSeconds", 10) * values.get("failureThreshold", 3)
        if probe == "livenessProbe" and margin < MIN_LIVENESS_MARGIN:
            problems.append(f"{workload}/{name} {probe}: periodSeconds x failureThreshold = {margin} s < {MIN_LIVENESS_MARGIN} s")
    return problems


@pytest.mark.parametrize(("component", "workload", "name"), CONTAINERS, ids=[f"{w}/{n}" for _, w, n in CONTAINERS])
def test_probe_margin_in_kind_operators(component, workload, name):
    spec = container(rendered(component), workload, name)
    assert violations(component, workload, name, spec) == []


@pytest.mark.parametrize(("component", "name", "probe"), sorted(UNTOUCHABLE), ids=lambda v: str(v))
def test_probe_margin_untouchable_probes_stay_untouchable(component, name, probe):
    """Si el chart empieza a exponer el plazo, la sonda sale de la lista y entra en la regla."""
    workload = next(w for c, w, n in CONTAINERS if (c, n) == (component, name))
    values = container(rendered(component), workload, name)[probe]
    assert "timeoutSeconds" not in values, f"{component}/{name} {probe} ya trae timeoutSeconds: quitarla de UNTOUCHABLE"


def test_probe_margin_the_rule_catches_a_removed_key():
    """Mutacion: quitar el plazo o bajar el margen de la sonda de vida de un operador tiene que ser un hallazgo."""
    spec = container(rendered("argo-cd"), "argo-cd-argocd-server", "server")
    assert violations("argo-cd", "argo-cd-argocd-server", "server", spec) == []
    for key in ("timeoutSeconds", "failureThreshold"):  # sin `periodSeconds` Kubernetes aplica 10 s: 10 x 12 sigue en 120 s
        mutated = copy.deepcopy(spec)
        del mutated["livenessProbe"][key]
        assert violations("argo-cd", "argo-cd-argocd-server", "server", mutated), key
    mutated = copy.deepcopy(spec)
    del mutated["readinessProbe"]["timeoutSeconds"]
    assert violations("argo-cd", "argo-cd-argocd-server", "server", mutated)
