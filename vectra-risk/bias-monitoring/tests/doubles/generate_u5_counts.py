"""Genera `u5_counts.json`: CountTable agregadas (nunca filas) del dataset `validation` de U5 (U09-T01, Paso 4).

Corre una sola vez (`uv run python bias-monitoring/tests/doubles/generate_u5_counts.py`), con la semilla de
referencia de U5, y escribe el archivo junto a este script. Las pruebas de U9 leen el JSON; ni `vectra_bias` ni
`vectra_disparity` importan `vectra_reference`. Usa las etiquetas de `monitoring_labels` y los `outcome` de
`outcomes_of` de U5 (solo `favorable` cuenta como favorable, BR-U9-01).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from vectra_reference import proxy as px
from vectra_reference import release as rel
from vectra_reference.generate import load_config

OUT = Path(__file__).with_name("u5_counts.json")


def _tables(rows, outcomes, evaluated_on):  # type: ignore[no-untyped-def]
    cells: dict[str, dict[tuple[str, str], list[int]]] = {
        a: defaultdict(lambda: [0, 0]) for a in px.ATTRIBUTES
    }
    for row, outcome in zip(rows, outcomes, strict=True):
        labels = px.monitoring_labels(row, evaluated_on)
        for attribute in px.ATTRIBUTES:
            cell = cells[attribute][(labels[attribute], labels["banda"])]
            cell[0] += 1
            cell[1] += int(outcome == px.FAVORABLE)
    return {
        attribute: [
            {"group": group, "band": band, "favorable": fav, "total": total}
            for (group, band), (total, fav) in sorted(table.items())
        ]
        for attribute, table in cells.items()
    }


def main() -> None:
    config = load_config()
    evaluated_on = date.fromisoformat(str(config["reference_date"]))
    captured: list[tuple[list, list[str]]] = []  # type: ignore[type-arg]
    original = px.outcomes_of

    def spy(rows, *args, **kwargs):  # type: ignore[no-untyped-def]
        outcomes = original(rows, *args, **kwargs)
        captured.append((list(rows), list(outcomes)))
        return outcomes

    px.outcomes_of = spy  # type: ignore[assignment]
    with tempfile.TemporaryDirectory() as tmp:
        base = rel.run_release(Path(tmp))
        proxy = rel.run_proxy_release(base)
    # Orden de las llamadas: modelo base (validation), variante proxy (validation); las 5 corridas comparten modelo.
    assert len(captured) == 2
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()  # noqa: S607
    payload = {
        "provenance": {
            "script": "bias-monitoring/tests/doubles/generate_u5_counts.py",
            "u5_commit": commit,
            "seed": config["seed"],
            "reference_date": str(config["reference_date"]),
            "dataset": "validation",
            "base_run": base.manifest["model_version_id"],
            "proxy_run": "proxy/run-1",
            "proxy_model_version_id": proxy.manifests[0]["model_version_id"],
            "u5_disparity_pp": {"base": base.manifest["disparity_pp"], "proxy": proxy.disparity_pp},
        },
        "base": _tables(*captured[0], evaluated_on),
        "proxy": _tables(*captured[1], evaluated_on),
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
