"""El arbol de identity-edge/ contiene todos los directorios de §1 del plan (U02-T02)."""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_PLAN = _ROOT / "aidlc-docs" / "construction" / "plans" / "identity-edge-code-generation-plan.md"
_EDGE = _ROOT / "identity-edge"
_ENTRY = re.compile(r"^(?P<prefix>[|` -]*?)(?P<marker>\|--|`--) (?P<name>\S+?)(?:\s+#\s*(?P<comment>.*))?$")
_COMMENT_DIR = re.compile(r"(?<![\w./-])([A-Za-z0-9_-]+)/(?=[,\s(]|$)")


def _plan_directories() -> set[str]:
    """Lee los directorios de la «Estructura de destino» (§1) directamente del plan."""
    text = _PLAN.read_text(encoding="utf-8")
    section = text.split("### Estructura de destino", 1)[1]
    block = section.split("```text", 1)[1].split("```", 1)[0]
    dirs: set[str] = set()
    stack: list[str] = []
    lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
    # La primera linea no vacia es la raiz (`vectra-risk/identity-edge/`); el resto son entradas.
    for line in lines[1:]:
        m = _ENTRY.match(line)
        if m is None:
            # Nunca se descarta en silencio: una linea que no se entiende rompe la prueba.
            raise AssertionError(f"linea de §1 que la prueba no sabe interpretar: {line!r}")
        depth = len(m["prefix"]) // 4
        name = m["name"]
        stack = stack[:depth]
        if name.endswith("/"):
            stack.append(name.rstrip("/"))
            dirs.add("/".join(stack))
            for sub in _COMMENT_DIR.findall(m["comment"] or ""):
                dirs.add("/".join([*stack, sub]))
        else:
            stack.append(name)
    return dirs


def test_skeleton_matches_plan() -> None:
    """§1 ⊆ arbol real. Es un subconjunto a proposito: §1 aun no lista directorios que
    crean otros pasos (p. ej. tests/strategies/), asi que los sobrantes no se reprochan."""
    expected = _plan_directories()
    # Sanidad: la lectura del plan debe encontrar la estructura completa.
    assert {"keycloak/themes/vectra", "tests/e2e", "tests/load", "charts/valkey"} <= expected
    missing = sorted(d for d in expected if not (_EDGE / d).is_dir())
    assert not missing, f"faltan directorios de §1: {missing}"
