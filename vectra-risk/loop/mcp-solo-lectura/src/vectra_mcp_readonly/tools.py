"""Las seis lecturas del servidor. Cada una proyecta **campos elegidos** de lo que devuelve `kubectl get` (nunca el objeto entero: sin `env`, sin
anotaciones, sin `data`) y pasa por `bound`, que acota el numero de elementos, el largo de cada texto y el total de caracteres.

Sin E/S propia: todo sale del `Kubectl` que reciben.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Final

from vectra_mcp_readonly.guard import EXPECTED_SUBJECT
from vectra_mcp_readonly.kubectl import Kubectl, Rejected, redact, shown, valid_namespace

MAX_ITEMS: Final = 50
MAX_FIELD_CHARS: Final = 240
MAX_CHARS: Final = 16000
ARGOCD_NAMESPACE: Final = "argocd"
#: `kind` de la herramienta `workloads` -> recurso de `kubectl get`. Lista cerrada: `secrets` (o cualquier otro) se rechaza antes de llamar a `kubectl`.
WORKLOAD_KINDS: Final = {
    "deployments": "deployments.apps",
    "statefulsets": "statefulsets.apps",
    "daemonsets": "daemonsets.apps",
    "jobs": "jobs.batch",
}
#: Las preguntas fijas de `permissions`: (verbo, recurso, subrecurso).
PROBES: Final[tuple[tuple[str, str, str | None], ...]] = (
    ("get", "pods", None),
    ("list", "applications.argoproj.io", None),
    ("list", "inferenceservices.serving.kserve.io", None),
    ("get", "secrets", None),
    ("create", "pods", None),
    ("delete", "pods", None),
    ("patch", "deployments", None),
    ("create", "pods", "exec"),
)
READ_VERBS: Final = frozenset({"get", "list", "watch"})
_RULE: Final = re.compile(r"^(\S*)\s+(\[.*?\])\s+(\[.*?\])\s+\[(.*)\]\s*$")

Result = dict[str, Any]


def _clip(value: Any) -> Any:
    if isinstance(value, str):
        value = redact(value)
        return value if len(value) <= MAX_FIELD_CHARS else value[: MAX_FIELD_CHARS - 1] + "…"
    if isinstance(value, dict):
        return {key: _clip(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clip(item) for item in value]
    return value


def bound(result: Result) -> Result:
    """Acota la salida: `MAX_ITEMS` elementos, `MAX_FIELD_CHARS` por texto y `MAX_CHARS` en total. `total` es lo que habia; `truncated` dice si se corto."""
    items = [_clip(item) for item in result.get("items", [])]
    out: Result = {key: _clip(value) for key, value in result.items() if key != "items"}
    out["total"] = len(items)
    kept = items[:MAX_ITEMS]
    out["items"] = kept
    while kept and len(json.dumps(out, ensure_ascii=False)) > MAX_CHARS:
        kept.pop()
    out["truncated"] = len(kept) < len(items)
    return out


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _name(item: dict[str, Any]) -> str:
    return str(_dict(item.get("metadata")).get("name", ""))


def _condition(status: dict[str, Any], kind: str) -> dict[str, Any]:
    for condition in _list(status.get("conditions")):
        if isinstance(condition, dict) and condition.get("type") == kind:
            return condition
    return {}


def argo_applications(kubectl: Kubectl) -> Result:
    """Estado de sync y salud de cada Application de Argo CD."""
    items = []
    for app in kubectl.get("applications.argoproj.io", ARGOCD_NAMESPACE):
        status = _dict(app.get("status"))
        sync, health = _dict(status.get("sync")), _dict(status.get("health"))
        revision = sync.get("revision") or next(
            iter(_list(sync.get("revisions"))), None
        )  # varias fuentes: la primera
        items.append(
            {
                "name": _name(app),
                "sync": str(sync.get("status", "Unknown")),
                "health": str(health.get("status", "Unknown")),
                "revision": revision[:12] if isinstance(revision, str) else None,
                "operation": _dict(status.get("operationState")).get("phase"),
            }
        )
    items.sort(key=lambda item: (item["sync"] == "Synced" and item["health"] == "Healthy", item["name"]))
    return bound(
        {
            "namespace": ARGOCD_NAMESPACE,
            "sync": dict(Counter(item["sync"] for item in items)),
            "health": dict(Counter(item["health"] for item in items)),
            "items": items,
        }
    )


def _pod_row(pod: dict[str, Any]) -> dict[str, Any]:
    status = _dict(pod.get("status"))
    containers = [c for c in _list(status.get("containerStatuses")) if isinstance(c, dict)]
    reason = status.get("reason")
    for container in containers:
        state = _dict(container.get("state"))
        waiting, terminated = _dict(state.get("waiting")), _dict(state.get("terminated"))
        if waiting.get("reason"):
            reason = waiting["reason"]
        elif terminated.get("reason") and terminated.get("exitCode") not in (0, None):
            reason = reason or terminated["reason"]
    return {
        "name": _name(pod),
        "phase": str(status.get("phase", "Unknown")),
        "ready": f"{sum(1 for c in containers if c.get('ready') is True)}/{len(_list(_dict(pod.get('spec')).get('containers')))}",
        "restarts": sum(int(c.get("restartCount") or 0) for c in containers),
        "reason": reason,
        "started": status.get("startTime"),
    }


def pods(kubectl: Kubectl, namespace: str) -> Result:
    """Pods de un namespace: fase, contenedores listos, reinicios y motivo de espera."""
    namespace = valid_namespace(namespace)
    items = [_pod_row(pod) for pod in kubectl.get("pods", namespace)]
    items.sort(
        key=lambda item: (
            item["phase"] in ("Running", "Succeeded") and item["reason"] is None,
            -item["restarts"],
            item["name"],
        )
    )
    return bound(
        {"namespace": namespace, "phases": dict(Counter(item["phase"] for item in items)), "items": items}
    )


def events(kubectl: Kubectl, namespace: str, only_warnings: bool = False) -> Result:
    """Eventos recientes de un namespace, del mas nuevo al mas viejo."""
    namespace = valid_namespace(namespace)
    if not isinstance(only_warnings, bool):
        raise Rejected(f"argumento rechazado: only_warnings {shown(only_warnings)} no es booleano")
    items = []
    for event in kubectl.get("events", namespace):
        involved = _dict(event.get("involvedObject"))
        last = (
            event.get("lastTimestamp")
            or event.get("eventTime")
            or _dict(event.get("metadata")).get("creationTimestamp")
        )
        if only_warnings and event.get("type") != "Warning":
            continue
        items.append(
            {
                "last": str(last or ""),
                "type": str(event.get("type", "")),
                "reason": str(event.get("reason", "")),
                "object": f"{involved.get('kind', '')}/{involved.get('name', '')}",
                "count": event.get("count"),
                "message": str(event.get("message", "")),
            }
        )
    items.sort(key=lambda item: str(item["last"]), reverse=True)
    return bound({"namespace": namespace, "only_warnings": only_warnings, "items": items})


def inference_services(kubectl: Kubectl, namespace: str) -> Result:
    """InferenceServices de KServe de un namespace: si estan listos y su URL."""
    namespace = valid_namespace(namespace)
    items = []
    for service in kubectl.get("inferenceservices.serving.kserve.io", namespace):
        status = _dict(service.get("status"))
        ready = _condition(status, "Ready")
        model = _dict(_dict(_dict(service.get("spec")).get("predictor")).get("model"))
        items.append(
            {
                "name": _name(service),
                "ready": str(ready.get("status", "Unknown")),
                "reason": ready.get("reason"),
                "message": ready.get("message"),
                "url": status.get("url"),
                "model_format": _dict(model.get("modelFormat")).get("name"),
                "runtime": model.get("runtime"),
            }
        )
    items.sort(key=lambda item: (item["ready"] == "True", item["name"]))
    return bound({"namespace": namespace, "items": items})


def workloads(kubectl: Kubectl, namespace: str, kind: str = "deployments") -> Result:
    """Replicas deseadas y listas de los Deployments, StatefulSets, DaemonSets o Jobs de un namespace."""
    namespace = valid_namespace(namespace)
    if not isinstance(kind, str) or kind not in WORKLOAD_KINDS:
        raise Rejected(
            f"argumento rechazado: kind {shown(kind)} no esta en la lista cerrada {sorted(WORKLOAD_KINDS)}"
        )
    items = []
    for workload in kubectl.get(WORKLOAD_KINDS[kind], namespace):
        spec, status = _dict(workload.get("spec")), _dict(workload.get("status"))
        if kind == "jobs":
            row = {
                "active": status.get("active", 0),
                "succeeded": status.get("succeeded", 0),
                "failed": status.get("failed", 0),
            }
        elif kind == "daemonsets":
            row = {"desired": status.get("desiredNumberScheduled", 0), "ready": status.get("numberReady", 0)}
        else:
            row = {
                "desired": spec.get("replicas", 0),
                "ready": status.get("readyReplicas", 0),
                "updated": status.get("updatedReplicas", 0),
            }
        items.append({"name": _name(workload), **row})
    items.sort(key=lambda item: str(item["name"]))
    return bound({"namespace": namespace, "kind": kind, "items": items})


def permissions(kubectl: Kubectl, namespace: str) -> Result:
    """Lo que la propia identidad puede hacer en un namespace: las preguntas fijas de `can-i` y el resumen de `can-i --list`."""
    namespace = valid_namespace(namespace)
    probes = [
        {
            "verb": verb,
            "resource": f"{resource}{'/' + sub if sub else ''}",
            "allowed": kubectl.can_i(verb, resource, namespace, sub),
        }
        for verb, resource, sub in PROBES
    ]
    by_verbs: dict[tuple[str, ...], list[str]] = {}
    for line in kubectl.can_i_list(namespace).splitlines()[1:]:
        match = _RULE.match(line)
        if match is None:
            continue
        resource = match.group(1) or f"(no recurso) {match.group(2)}"
        by_verbs.setdefault(tuple(sorted(match.group(4).split())), []).append(resource)
    items = [
        {
            "verbs": list(verbs),
            "read_only": set(verbs) <= READ_VERBS,
            "resource_count": len(names),
            "resources": sorted(names)[:MAX_ITEMS],
        }
        for verbs, names in sorted(by_verbs.items())
    ]
    return bound({"namespace": namespace, "identity": EXPECTED_SUBJECT, "probes": probes, "items": items})
