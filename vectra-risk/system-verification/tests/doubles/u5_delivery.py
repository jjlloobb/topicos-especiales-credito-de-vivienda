"""Una entrega pequeña de U5 para las pruebas (U12-T02): `datasets/test.parquet` del **generador real** (`vectra_reference.generate.generate` con `with_overrides(config, n_rows=...)`) y un
`adversarial/manifest.json` minimo con la forma de `write_adversarial` (`manifest_version`, `generator_version`, `seed`, `cases`). No se corre `make -C reference-model release` (entrena modelos)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from vectra_reference.generate import generate, load_config, with_overrides

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = ROOT / "platform" / ".tools" / "tmp" / "u12t02"


def make_delivery(directory: Path, n_rows: int | None = 16000) -> dict[str, object]:
    config = load_config()
    with_rows = (
        config if n_rows is None else with_overrides(config, n_rows=n_rows)
    )  # `None`: la configuracion completa de U5 (U12-T03, CA-9)
    (directory / "datasets").mkdir(parents=True, exist_ok=True)
    (directory / "adversarial").mkdir(parents=True, exist_ok=True)
    paths = generate(directory / "datasets", with_rows)
    # el generador escribe train/validation/test juntos: la entrega solo trae `datasets/test.parquet`
    for name in ("train", "validation"):
        paths[name].unlink()
    manifest = {
        "manifest_version": 1,
        "generator_version": config["generator_version"],
        "seed": config["seed"],
        "cases": [],
    }
    (directory / "adversarial" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return {"generator_version": config["generator_version"], "seed": config["seed"], "directory": directory}


def remove(directory: Path) -> None:
    shutil.rmtree(directory, ignore_errors=True)
