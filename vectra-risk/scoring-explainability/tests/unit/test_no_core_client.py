"""BR-U7-02, AUTONOMIA-03: nada de U7 nombra al core bancario. Los nombres salen de X01 en `forbidden.yaml` y de `flows.yaml`."""

from pathlib import Path

import yaml

UNIT = Path(__file__).resolve().parents[2]
NETWORK = UNIT.parent / "platform" / "network"
SKIP_DIRS = {".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".hypothesis"}


def core_names() -> set[str]:
    """Destinos de X01 en `forbidden.yaml` y las claves y rutas del servicio del core en `flows.yaml`."""
    forbidden = yaml.safe_load((NETWORK / "forbidden.yaml").read_text(encoding="utf-8"))["forbidden"]
    names = {str(rule["to"]) for rule in forbidden if rule["id"] == "X01"}
    workloads = yaml.safe_load((NETWORK / "flows.yaml").read_text(encoding="utf-8"))["workloads"]
    for name in tuple(names):
        entry = workloads.get(name)
        if isinstance(entry, dict):
            names.update(str(entry[key]) for key in ("name", "sa") if key in entry)
            names.add(str(entry["ns"]))
    return names


def offenders(root: Path, names: set[str]) -> list[str]:
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        hits.extend(f"{path.relative_to(root)}: {name}" for name in sorted(names) if name in text)
    return hits


def test_la_lista_sale_de_la_red() -> None:
    assert "core-banking-mock" in core_names()


def test_ningun_archivo_de_u7_nombra_al_core() -> None:
    assert offenders(UNIT, core_names()) == []


def test_detecta_un_nombre_del_core(tmp_path: Path) -> None:
    (tmp_path / "client.py").write_text('URL = "http://core-banking-mock:8080"\n', encoding="utf-8")
    assert offenders(tmp_path, core_names()) == ["client.py: core-banking-mock"]
