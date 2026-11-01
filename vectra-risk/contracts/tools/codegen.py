"""Genera specs, catalogo de scopes y matriz rol x endpoint (NFR-U0-30, P-U0-12, BR-U0-93)."""

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema
from vectra_contracts import __version__, catalog
from vectra_contracts.catalog import SCOPE_HOLDERS, Role, Scope
from vectra_contracts.models.api import Problem
from vectra_contracts.routes import REGISTRY, RouteContract

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "openapi"
TS_ENUMS = ROOT / "ts" / "src" / "enums.generated.ts"
REF = "#/components/schemas/"


def _name(model: type[BaseModel]) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", model.__name__)


def _query_parameters(route: RouteContract, definitions: dict[str, Any]) -> list[dict[str, Any]]:
    assert route.query_model is not None
    schema = definitions[_definition_name(route.query_model, definitions)]
    required = set(schema.get("required", []))
    return [
        {"name": name, "in": "query", "required": name in required, "schema": prop}
        for name, prop in sorted(schema["properties"].items())
    ]


def _definition_name(model: type[BaseModel], definitions: dict[str, Any]) -> str:
    title = model.__name__
    for name in (title, f"{title}-Input"):
        if name in definitions:
            return name
    raise KeyError(title)


def _operation(
    route: RouteContract, names: dict[tuple[type[BaseModel], str], Any], definitions: dict[str, Any]
) -> dict[str, Any]:
    operation: dict[str, Any] = {
        "operationId": route.operation_id,
        "x-vectra-scopes": sorted(s.value for s in route.scopes),
        "x-vectra-any-scopes": sorted(s.value for s in route.any_scopes),
        "x-vectra-roles": sorted(r.value for r in route.roles),
        "x-vectra-mfa": route.mfa,
        "x-vectra-read-only": route.read_only,
        "x-vectra-max-body-bytes": route.max_body_bytes,
    }
    parameters: list[dict[str, Any]] = [
        {"name": p, "in": "path", "required": True, "schema": {"type": "string"}}
        for p in re.findall(r"\{(\w+)\}", route.path)
    ]
    if route.query_model is not None:
        parameters += _query_parameters(route, definitions)
    parameters += [
        {"name": h.name, "in": "header", "required": h.required, "schema": {"type": "string"}}
        for h in route.headers
    ]
    if parameters:
        operation["parameters"] = parameters
    if route.request_model is not None:
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": names[(route.request_model, "validation")]}},
        }
    responses: dict[str, Any] = {
        "default": {
            "description": "Problem",
            "content": {"application/problem+json": {"schema": {"$ref": f"{REF}Problem"}}},
        }
    }
    if route.response_model is not None:
        responses["200"] = {
            "description": "OK",
            "content": {"application/json": {"schema": names[(route.response_model, "serialization")]}},
        }
    else:
        responses["204"] = {"description": "Sin contenido"}
    for status in sorted(route.alternate_statuses):
        responses[str(status)] = (
            {"description": "Sin cambios"} if status == 304 else {**responses["200"], "description": "Aceptada"}
        )
    operation["responses"] = responses
    return operation


def spec_for(service: str, routes: list[RouteContract]) -> dict[str, Any]:
    wanted: set[tuple[type[BaseModel], str]] = {(Problem, "serialization")}
    for route in routes:
        if route.request_model is not None:
            wanted.add((route.request_model, "validation"))
        if route.response_model is not None:
            wanted.add((route.response_model, "serialization"))
        if route.query_model is not None:
            wanted.add((route.query_model, "validation"))
    ordered = sorted(wanted, key=lambda item: (item[0].__name__, item[1]))
    names, definitions = models_json_schema(ordered, ref_template=REF + "{model}")  # type: ignore[arg-type]
    paths: dict[str, Any] = {}
    schemas = definitions.get("$defs", {})
    for route in sorted(routes, key=lambda r: (r.path, r.method)):
        paths.setdefault(route.path, {})[route.method.lower()] = _operation(route, names, schemas)  # type: ignore[arg-type]
    return {
        "openapi": "3.1.0",
        "info": {"title": service, "version": __version__},
        "paths": paths,
        "components": {"schemas": definitions.get("$defs", {})},
    }


def role_matrix() -> str:
    roles = [role.value for role in Role]
    lines = [
        "# Matriz rol x endpoint (US-602). Generado: no editar.",
        "",
        "| Servicio | Metodo | Ruta | " + " | ".join(roles) + " | MFA | Scopes |",
        "|---|---|---|" + "---|" * (len(roles) + 2),
    ]
    for service, routes in sorted(REGISTRY.items()):
        for route in sorted(routes, key=lambda r: (r.path, r.method)):
            marks = " | ".join("x" if Role(name) in route.roles else "" for name in roles)
            scopes = ", ".join(sorted(s.value for s in route.scopes | route.any_scopes))
            lines.append(
                f"| {service} | {route.method} | `{route.path}` | {marks} | {'si' if route.mfa else ''} | {scopes} |"
            )
    return "\n".join(lines) + "\n"


def catalog_enums() -> list[type[StrEnum]]:
    """Cada enumerado del catalogo, en orden de nombre: U10 los recorre para sus etiquetas."""
    found = [v for v in vars(catalog).values() if isinstance(v, type) and issubclass(v, StrEnum) and v is not StrEnum]
    return sorted(found, key=lambda enum: enum.__name__)


def _ts_name(name: str) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()
    return snake[:-1] + "IES" if snake.endswith("Y") else f"{snake}ES" if snake.endswith("S") else f"{snake}S"


def ts_enums() -> str:
    lines = ["// Generado por contracts/tools/codegen.py. No editar.", ""]
    for enum in catalog_enums():
        values = ", ".join(json.dumps(member.value) for member in enum)
        lines.append(f"export const {_ts_name(enum.__name__)} = [{values}] as const;")
    return "\n".join(lines) + "\n"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for service, routes in REGISTRY.items():
        text = yaml.safe_dump(spec_for(service, routes), sort_keys=True, allow_unicode=True)
        (OUT / f"{service}.yaml").write_text(text, encoding="utf-8")
    catalog = {scope.value: list(SCOPE_HOLDERS[scope]) for scope in Scope}
    (OUT / "scopes-catalog.json").write_text(
        json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "role-endpoint-matrix.md").write_text(role_matrix(), encoding="utf-8")
    TS_ENUMS.write_text(ts_enums(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
