"""El `spec` de la `PrometheusRule` que rinde el chart de U8 (Paso 21), versionado en `observability/rules/case-management.rules.yaml`.

`rules_spec.py <render-kind> <render-staging> [--write]`: lee el render de kind y el de staging (`integration.py --chart ... --out DIR`), comprueba que la
`PrometheusRule` es la misma en los dos y que su `spec` es el archivo versionado. Sin `--write` **falla** (codigo 1) si difiere; con `--write` regenera el
archivo. Es el formato que lee `promtool check rules` y `promtool test rules` (`groups:`). No es un directorio `generated` ni `rendered`: `test_traceability.py`
y `test_runbooks.py` los saltan.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

VERSIONED = Path(__file__).resolve().parents[1] / "observability" / "rules" / "case-management.rules.yaml"
HEADER = (
    "# El `spec` de la PrometheusRule que rinde case-management/chart (Paso 21; INF-U8-03; US-603). Lo regenera `make -C case-management rules WRITE=1`;\n"
    "# `make -C case-management rules` falla si difiere del render de kind (y del de staging). Una alerta (CoreWriteAttempt) y ninguna regla de grabacion:\n"
    "# las otras ocho alertas de P-U8 estan diferidas por la demo (T2).\n"
)


def spec_of(render: Path) -> dict[str, Any]:
    docs = [d for d in yaml.safe_load_all(render.read_text(encoding="utf-8")) if d]
    rules = [d for d in docs if d.get("kind") == "PrometheusRule"]
    if len(rules) != 1:
        raise SystemExit(f"{render}: {len(rules)} PrometheusRule (se espera 1)")
    return dict(rules[0]["spec"])


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    """Las expresiones de varias lineas van en bloque literal: se leen y se comparan tal cual."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None)


_Dumper.add_representer(str, _str)


def dump(spec: dict[str, Any]) -> str:
    return HEADER + yaml.dump(spec, Dumper=_Dumper, sort_keys=False, width=1000, allow_unicode=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", type=Path)
    parser.add_argument("staging", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    kind, staging = spec_of(args.kind), spec_of(args.staging)
    if kind != staging:
        print("la PrometheusRule de kind y la de staging difieren")  # noqa: T201 (salida de una herramienta de linea de comandos)
        return 1
    text = dump(kind)
    if args.write:
        VERSIONED.write_text(text, encoding="utf-8")
        return 0
    if not VERSIONED.is_file() or VERSIONED.read_text(encoding="utf-8") != text:
        print(f"{VERSIONED} difiere del render: corre `make -C case-management rules WRITE=1`")  # noqa: T201 (salida de una herramienta de linea de comandos)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
