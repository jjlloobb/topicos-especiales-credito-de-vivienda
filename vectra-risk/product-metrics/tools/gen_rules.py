#!/usr/bin/env python3
"""Genera las reglas de Prometheus de U11 que salen de datos del codigo (Paso 12; BR-U11-06; BR-U11-14; P-U11-05; NFR-U11-06; NFR-U11-32).

- `chart/files/generated-rules.yaml`: la regla `vectra:product_desync_failclosed:rate1h`, con las causas de
  `vectra_contracts.catalog.FAIL_CLOSED_CAUSES_BY_CATEGORY["desincronia"]` (ordenadas), y una recording rule `:dedup` por **cada** clave de
  `vectra_product.collector.PRODUCT_SERIES` (`vectra:<serie sin el prefijo vectra_>:dedup = max without (instance, pod) (<serie>)`). Ninguna
  para `OPERATION_SERIES`. La plantilla `prometheusrule.yaml` lo incluye con `.Files` (P-4: helm solo lee lo que esta dentro de `chart/`).
- `--spec`: el `spec` de la `PrometheusRule` **renderizada** (con S ya sustituida) en `observability/rules/product-metrics.rules.yaml`, el
  archivo contra el que corre `promtool`. Se rinde en los tres entornos y el `spec` debe ser identico.
- `--check` no escribe nada y termina en 1 si el archivo versionado difiere del generado. La salida es determinista.
Sin argumentos escribe `generated-rules.yaml`; con `--spec`, el archivo de reglas renderizado.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

import yaml
from vectra_contracts.catalog import FAIL_CLOSED_CAUSES_BY_CATEGORY
from vectra_product.collector import PRODUCT_SERIES

ROOT: Final = Path(__file__).resolve().parents[2]
UNIT: Final = ROOT / "product-metrics"
CHART: Final = UNIT / "chart"
GENERATED: Final = CHART / "files" / "generated-rules.yaml"
SPEC: Final = UNIT / "observability" / "rules" / "product-metrics.rules.yaml"
ENVS: Final = ("kind", "staging", "prod")
HELM: Final = ROOT / "platform" / ".tools" / "bin" / "helm"
DESYNC_RECORD: Final = "vectra:product_desync_failclosed:rate1h"
DEDUP_BY: Final = "max without (instance, pod)"
GENERATED_HEADER: Final = (
    "# GENERADO por product-metrics/tools/gen_rules.py: no editar a mano (`gen_rules.py --check` falla si difiere).\n"
    "# La regla de desincronia sale de `vectra_contracts.catalog.FAIL_CLOSED_CAUSES_BY_CATEGORY['desincronia']` (BR-U11-06) y las `:dedup`, de\n"
    "# `vectra_product.collector.PRODUCT_SERIES` (P-U11-05, NFR-U11-06): una por clave, ninguna para las series de operacion.\n"
)
SPEC_HEADER: Final = (
    "# GENERADO por `python product-metrics/tools/gen_rules.py --spec`: el `spec` de la PrometheusRule renderizada (S sustituida), identico en\n"
    "# kind, staging y prod. `promtool test rules product-metrics/observability/rules/tests/*.yaml` corre contra este archivo. No editar a mano.\n"
)


def dedup_name(series: str) -> str:
    """`vectra_product_north_star_ratio` -> `vectra:product_north_star_ratio:dedup`."""
    return f"vectra:{series.removeprefix('vectra_')}:dedup"


def desync_causes() -> list[str]:
    return sorted(str(getattr(c, "value", c)) for c in FAIL_CLOSED_CAUSES_BY_CATEGORY["desincronia"])


def generated_rules() -> dict[str, Any]:
    causes = "|".join(desync_causes())
    return {
        "groups": [
            {
                "name": "vectra-product-desync",
                "rules": [
                    {
                        "record": DESYNC_RECORD,
                        "expr": f'sum(rate(vectra_scoring_failclosed_total{{cause=~"{causes}"}}[1h]))',
                    }
                ],
            },
            {
                "name": "vectra-product-dedup",
                "rules": [
                    {"record": dedup_name(series), "expr": f"{DEDUP_BY} ({series})"}
                    for series in PRODUCT_SERIES
                ],
            },
        ]
    }


def dump(document: dict[str, Any], header: str) -> str:
    return header + yaml.safe_dump(document, sort_keys=False, width=200, default_flow_style=False)


def _helm_template(env: str) -> list[dict[str, Any]]:
    command = [
        str(HELM),
        "template",
        "product-metrics",
        str(CHART),
        "-f",
        str(ROOT / "vectra-risk-gitops" / "envs" / env / "values.yaml"),
        "-f",
        str(CHART / "values-product-metrics-policy.yaml"),
    ]
    if env == "kind":
        command += ["-f", str(CHART / "values-kind.yaml")]
    out = subprocess.run(command, check=True, capture_output=True, text=True).stdout  # noqa: S603
    return [d for d in yaml.safe_load_all(out) if d]


def rendered_spec(env: str) -> dict[str, Any]:
    rules = [d for d in _helm_template(env) if d["kind"] == "PrometheusRule"]
    if len(rules) != 1:
        raise SystemExit(f"{env}: se esperaba una PrometheusRule y hay {len(rules)}")
    return dict(rules[0]["spec"])


def rendered_spec_text() -> str:
    specs = {env: rendered_spec(env) for env in ENVS}
    first = specs[ENVS[0]]
    for env, spec in specs.items():
        if spec != first:
            raise SystemExit(f"el spec de la PrometheusRule de {env} difiere del de {ENVS[0]}")
    return dump(first, SPEC_HEADER)


def shown(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="no escribe: termina en 1 si el versionado difiere"
    )
    parser.add_argument(
        "--spec",
        action="store_true",
        help="el spec renderizado de la PrometheusRule, no generated-rules.yaml",
    )
    args = parser.parse_args(argv)
    target = SPEC if args.spec else GENERATED
    text = rendered_spec_text() if args.spec else dump(generated_rules(), GENERATED_HEADER)
    current = target.read_text(encoding="utf-8") if target.is_file() else None
    if args.check:
        if current != text:
            print(  # noqa: T201
                f"{shown(target)} difiere de lo generado: corre `python product-metrics/tools/gen_rules.py{' --spec' if args.spec else ''}`"
            )
            return 1
        print(f"{shown(target)}: al dia")  # noqa: T201
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"escrito {shown(target)}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
