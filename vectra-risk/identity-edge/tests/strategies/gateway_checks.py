"""Gateway (U02-T09, Paso 7): documentos generados, modelo de enrutamiento de Envoy y comprobaciones.

El modelo (`route`) lee solo los manifiestos generados, nunca `routes.yaml` (PBT-U2-04). Imita el orden de
precedencia de Envoy Gateway v1.9.3 (`internal/gatewayapi/sort.go`: Exact > RegularExpression > PathPrefix; luego
mas caracteres de camino; luego mas cabeceras, con el metodo como cabecera `:method`; luego mas parametros de consulta)
y el procesamiento de caminos de `ClientTrafficPolicy.path` (`UnescapeAndRedirect`, fusion de barras, normalizacion).
"""

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[3]
EDGE = _ROOT / "identity-edge"
GATEWAY = EDGE / "gateway"
GENERATED = GATEWAY / "generated"
POLICY = GATEWAY / "policy"
ROUTES_YAML = GATEWAY / "routes.yaml"
VALUES = GATEWAY / "values"
TOOLS_BIN = _ROOT / "platform" / ".tools" / "bin"
CONFTEST = TOOLS_BIN / "conftest"
KUBECONFORM = TOOLS_BIN / "kubeconform"
CHART = _ROOT / "platform" / ".charts" / "envoy-gateway" / "gateway-helm"
ESO_CHART = _ROOT / "platform" / ".charts" / "external-secrets" / "external-secrets"
ENVS = ("kind", "staging", "prod")

Docs = list[dict[str, Any]]


def load_dir(directory: Path) -> dict[str, Docs]:
    """`{archivo: documentos}` de un directorio generado."""
    return {
        p.name: [d for d in yaml.safe_load_all(p.read_text(encoding="utf-8")) if d] for p in sorted(directory.glob("*.yaml"))
    }


def flat(files: dict[str, Docs]) -> Docs:
    return [d for name in sorted(files) for d in files[name]]


def load_env(env: str) -> Docs:
    return flat(load_dir(GENERATED / env))


def find(docs: Docs, kind: str, name: str) -> dict[str, Any]:
    (found,) = [d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name]
    return found


def of_kind(docs: Docs, kind: str) -> Docs:
    return [d for d in docs if d["kind"] == kind]


def identities(docs: Docs) -> list[tuple[str, str, str]]:
    return sorted((d["kind"], d["metadata"].get("namespace", ""), d["metadata"]["name"]) for d in docs)


# --- conftest ------------------------------------------------------------------------------------


def conftest(docs: Docs, env: str = "prod") -> tuple[int, str]:
    """Las dos pasadas de `make policy-gateway` sobre `docs`, en un directorio `<env>/`. Devuelve (codigo mayor, salida)."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / env).mkdir()
        target = Path(tmp) / env / "gateway.yaml"
        target.write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
        first = subprocess.run([str(CONFTEST), "test", "--policy", str(POLICY), str(target)], capture_output=True, text=True, check=False)  # noqa: S603 - herramienta fija de platform/.tools
        second = subprocess.run(  # noqa: S603 - herramienta fija de platform/.tools
            [str(CONFTEST), "test", "--combine", "--namespace", "gateway_set", "--policy", str(POLICY), str(target)],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
    return max(first.returncode, second.returncode), first.stdout + first.stderr + second.stdout + second.stderr


def policy_rules() -> set[str]:
    rules = set()
    for path in sorted(POLICY.glob("*.rego")):
        rules |= set(re.findall(r"^# regla: ([\w-]+)$", path.read_text(encoding="utf-8"), re.MULTILINE))
    return rules


# --- modelo de enrutamiento --------------------------------------------------------------------

_ESCAPED_SLASH = re.compile(r"%2f|%5c", re.IGNORECASE)
_UNRESERVED_ESCAPE = re.compile(r"%((?:2[dDeE])|(?:3[0-9])|(?:4[1-9a-fA-F])|(?:5[0-9aA])|(?:6[1-9a-fA-F])|(?:7[0-9aA])|(?:5[fF])|(?:7[eE]))")
_TYPE_RANK = {"Exact": 2, "RegularExpression": 1, "PathPrefix": 0}


def normalize(raw: str) -> tuple[str, bool]:
    """(camino que Envoy enruta, si hubo redireccion por `%2F` o `%5C`).

    `UnescapeAndRedirect` redirige (307) al camino con las barras sin escapar; despues Envoy normaliza (`\\` -> `/`,
    segmentos `.` y `..`) y fusiona las barras repetidas. El modelo devuelve el destino final de esa redireccion.
    """
    redirected = _ESCAPED_SLASH.search(raw) is not None
    path = re.sub(r"%2f", "/", raw, flags=re.IGNORECASE)
    path = re.sub(r"%5c", "/", path, flags=re.IGNORECASE).replace("\\", "/")
    # `NormalizePath` (RFC 3986): se decodifican los caracteres no reservados (`%2e`, `%61`...) antes de resolver los puntos.
    path = _UNRESERVED_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), path)
    trailing = path.endswith("/") or path.endswith(("/.", "/.."))
    segments: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    out = "/" + "/".join(segments)
    if trailing and out != "/":
        out += "/"
    return out, redirected


@dataclass
class Outcome:
    kind: str  # "backend" | "direct" | "nomatch"
    route: str | None = None
    rule: str | None = None
    backend: tuple[str, str, int] | None = None
    status: int | None = None
    upstream_path: str | None = None
    path: str = ""
    redirected: bool = False
    ambiguous: bool = False
    headers: dict[str, list[str]] = field(default_factory=dict)


def _path_matches(match: dict[str, Any], path: str) -> bool:
    kind, value = match["type"], match["value"]
    if kind == "Exact":
        return path == value
    if kind == "PathPrefix":
        return value == "/" or path == value or path.startswith(value.rstrip("/") + "/")
    if kind == "RegularExpression":
        return re.fullmatch(value, path) is not None
    raise AssertionError(f"tipo de camino desconocido: {kind}")


def _specificity(match: dict[str, Any]) -> tuple[int, ...]:
    path = match["path"]
    count = 0 if path["type"] == "PathPrefix" and path["value"] == "/" else len(path["value"])
    methods = 1 if match.get("method") else 0
    queries = match.get("queryParams", [])
    exact_queries = sum(1 for q in queries if q.get("type", "Exact") == "Exact")
    return (_TYPE_RANK[path["type"]], count, methods, methods, len(queries), exact_queries)


def _candidates(docs: Docs, method: str, path: str, query: dict[str, str]) -> list[tuple[tuple[int, ...], dict[str, Any], dict[str, Any]]]:
    found = []
    for route in sorted(of_kind(docs, "HTTPRoute"), key=lambda d: d["metadata"]["name"]):
        for rule in route["spec"]["rules"]:
            for match in rule["matches"]:
                if match.get("method") and match["method"] != method:
                    continue
                if not _path_matches(match["path"], path):
                    continue
                if any(query.get(q["name"]) != q["value"] for q in match.get("queryParams", [])):
                    continue
                found.append((_specificity(match), route, rule))
    return found


def _response_headers(rule: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in rule.get("filters", []):
        if f["type"] == "ResponseHeaderModifier":
            for entry in f["responseHeaderModifier"].get("set", []) + f["responseHeaderModifier"].get("add", []):
                out.setdefault(entry["name"], []).append(entry["value"])
    return out


def route(docs: Docs, method: str, raw_path: str, query: dict[str, str] | None = None) -> Outcome:
    """Que hace el gateway con `method raw_path?query`, segun los manifiestos `docs`."""
    path, redirected = normalize(raw_path)
    found = _candidates(docs, method, path, query or {})
    if not found:
        return Outcome("nomatch", path=path, redirected=redirected)
    best = max(key for key, _, _ in found)
    top = [(r, rule) for key, r, rule in found if key == best]
    (top_route, top_rule) = top[0]
    ambiguous = len({(r["metadata"]["name"], rule["name"]) for r, rule in top}) > 1
    outcome = Outcome(
        "backend", route=top_route["metadata"]["name"], rule=top_rule["name"], path=path, redirected=redirected,
        ambiguous=ambiguous, headers=_response_headers(top_rule), upstream_path=path,
    )  # fmt: skip
    for f in top_rule.get("filters", []):
        if f["type"] == "ExtensionRef":
            hrf = find(docs, "HTTPRouteFilter", f["extensionRef"]["name"])["spec"]
            if "directResponse" in hrf:
                outcome.kind, outcome.status, outcome.upstream_path = "direct", hrf["directResponse"]["statusCode"], None
            if "urlRewrite" in hrf:
                rewrite = hrf["urlRewrite"]["path"]["replaceRegexMatch"]
                outcome.upstream_path = re.sub(rewrite["pattern"], rewrite["substitution"], path)
        if f["type"] == "URLRewrite":
            outcome.upstream_path = f["urlRewrite"]["path"]["replaceFullPath"]
    if outcome.kind == "backend":
        (ref,) = top_rule["backendRefs"]
        outcome.backend = (ref["name"], ref["namespace"], ref["port"])
    return outcome


# --- evaluacion de la autorizacion de una SecurityPolicy ---------------------------------------


def authorizes(policy: dict[str, Any], token: dict[str, Any]) -> bool:
    """403 si devuelve False. Imita `authorization` de Envoy Gateway: las reglas `Allow` por orden y `defaultAction`.

    Reclamos (`claims`): todos deben coincidir; un reclamo de texto coincide si es uno de `values`; uno de arreglo, si
    contiene alguno. `scopes`: todos deben estar en `scope` (separado por espacios).
    """
    authz = policy["spec"]["authorization"]
    for rule in authz["rules"]:
        jwt = rule["principal"]["jwt"]
        claims_ok = all(_claim_matches(c, token) for c in jwt.get("claims", []))
        scopes = set(str(token.get("scope", "")).split())
        scopes_ok = all(s in scopes for s in jwt.get("scopes", []))
        if claims_ok and scopes_ok:
            return rule["action"] == "Allow"
    return authz["defaultAction"] == "Allow"


def _claim_matches(claim: dict[str, Any], token: dict[str, Any]) -> bool:
    node: Any = token
    for part in claim["name"].split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    if claim.get("valueType", "String") == "StringArray":
        return isinstance(node, list) and any(v in claim["values"] for v in node)
    return isinstance(node, str) and node in claim["values"]


# --- kubeconform -------------------------------------------------------------------------------


def kubeconform(directory: Path, schemas: Path) -> tuple[int, str]:
    """`kubeconform -strict` sin `-ignore-missing-schemas`, con los esquemas de `crd_schemas.py`."""
    run = subprocess.run(  # noqa: S603 - herramienta fija de platform/.tools
        [
            str(KUBECONFORM), "-strict", "-summary",
            "-schema-location", str(schemas) + "/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json",
            str(directory),
        ],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    return run.returncode, run.stdout + run.stderr
