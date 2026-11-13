#!/usr/bin/env python3
"""El OpenAPI exportado de `case-service` y del mock coincide con el de la app y con el contrato de U0 (Paso 22; BR-U8-20; P-7 de U08-T05 = a).

`create_app` de U0 registra las rutas con `include_in_schema=False`, asi que `build_app().openapi()` no trae rutas. El «OpenAPI de la app» es el que
`contracts/tools/codegen.py::spec_for` rinde para las rutas del contrato **que la app sirve de verdad** (`app.routes`). Se comprueba, por servicio:

1. el archivo exportado `docs/openapi/<servicio>.yaml` es identico al de la app (editarlo a mano, o cambiar la app sin regenerarlo, lo rompe);
2. las rutas (metodo y plantilla) de la app son las de `contracts/openapi/<servicio>.yaml`: ni falta una del contrato ni sobra una que el contrato no tiene.

Termina en 1 si algo difiere y **no escribe nada**; `--write` regenera los archivos exportados (el unico caso en que escribe).
Uso: `uv run python case-management/tools/check_openapi.py [--write] [--docs DIR]`.
"""

import argparse
import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
DOCS = CASE / "docs" / "openapi"
CONTRACTS = ROOT / "contracts" / "openapi"
SERVICES = ("case-service", "core-banking-mock")


def _codegen() -> Any:
    spec = importlib.util.spec_from_file_location(
        "vectra_contracts_codegen", ROOT / "contracts" / "tools" / "codegen.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_apps() -> dict[str, FastAPI]:
    """Las apps tal como las arma el codigo (`build_app()` sin argumentos no lee el entorno ni abre conexiones)."""
    from core_banking_mock.app import build_app as build_mock
    from vectra_case.app import build_app as build_case

    return {"case-service": build_case(), "core-banking-mock": build_mock()}


def served(app: FastAPI) -> set[tuple[str, str]]:
    """(metodo, plantilla) de cada ruta de la API; las sondas viven en el puerto 8081 (`ops_app`), no en esta."""
    return {(m.upper(), r.path) for r in app.routes for m in getattr(r, "methods", None) or ()}  # type: ignore[attr-defined]


def exported(service: str, app: FastAPI) -> dict[str, Any]:
    """Lo que la app sirve, como OpenAPI: `spec_for` de U0 sobre las rutas del contrato que la app tiene registradas."""
    from vectra_contracts.routes import REGISTRY

    codegen = _codegen()
    live = served(app)
    return dict(codegen.spec_for(service, [r for r in REGISTRY[service] if (r.method, r.path) in live]))


def dump(spec: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(spec), sort_keys=True, allow_unicode=True)


def contract_routes(service: str) -> set[tuple[str, str]]:
    document = yaml.safe_load((CONTRACTS / f"{service}.yaml").read_text(encoding="utf-8"))
    return {(m.upper(), p) for p, item in document["paths"].items() for m in item}


def check(apps: Mapping[str, FastAPI], docs: Path = DOCS) -> list[str]:
    """Las diferencias, una por linea; vacia si todo coincide. No escribe nada."""
    problems: list[str] = []
    for service in SERVICES:
        app = apps[service]
        live, wanted = served(app), contract_routes(service)
        problems += [
            f"{service}: la app no sirve {m} {p}, que es del contrato" for m, p in sorted(wanted - live)
        ]
        problems += [
            f"{service}: la app sirve {m} {p}, que el contrato no tiene" for m, p in sorted(live - wanted)
        ]
        target = docs / f"{service}.yaml"
        if not target.is_file():
            problems.append(f"{service}: falta el OpenAPI exportado {target}")
        elif target.read_text(encoding="utf-8") != dump(exported(service, app)):
            problems.append(
                f"{service}: {target.name} difiere del OpenAPI de la app (corre `check_openapi.py --write` si el cambio es intencional)"
            )
    return problems


def main(argv: list[str], apps: Mapping[str, FastAPI] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="regenera los archivos exportados")
    parser.add_argument("--docs", type=Path, default=DOCS)
    args = parser.parse_args(argv)
    apps = apps or build_apps()
    if args.write:
        args.docs.mkdir(parents=True, exist_ok=True)
        for service in SERVICES:
            (args.docs / f"{service}.yaml").write_text(
                dump(exported(service, apps[service])), encoding="utf-8"
            )
    problems = check(apps, args.docs)
    for problem in problems:
        print(problem)  # noqa: T201 (salida de una herramienta de linea de comandos)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
