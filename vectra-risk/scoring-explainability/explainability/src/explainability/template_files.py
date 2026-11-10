"""Carga de las plantillas versionadas (`templates/*.txt`): lineas `@clave texto`; el resto son comentarios."""

from collections.abc import Sequence
from pathlib import Path

#: En la rueda, `templates/` va dentro del paquete (`force-include`); en el arbol de fuentes, junto a `src/`.
TEMPLATE_DIRS: tuple[Path, ...] = (
    Path(__file__).resolve().parent / "templates",
    Path(__file__).resolve().parents[2] / "templates",
)


class TemplateError(Exception):
    """La plantilla no existe o le falta una clave."""


def read_template(name: str, keys: Sequence[str], dirs: Sequence[Path] = TEMPLATE_DIRS) -> dict[str, str]:
    """Las claves pedidas de la plantilla `name`, en la primera carpeta que la tenga."""
    for folder in dirs:
        path = folder / name
        if path.is_file():
            break
    else:
        raise TemplateError(f"plantilla_no_encontrada: {name}")
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("@"):
            key, _, text = line[1:].partition(" ")
            found[key] = text
    missing = [key for key in keys if key not in found]
    if missing:
        raise TemplateError(f"plantilla_incompleta: {name}: {', '.join(missing)}")
    return {key: found[key] for key in keys}
