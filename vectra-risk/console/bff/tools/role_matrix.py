"""Matriz rol x endpoint del BFF (BR-U10-19; NFR-U10-46; US-602): tres fuentes que tienen que coincidir.

1. **Generada** desde `REGISTRY["console-bff"]` (`RouteContract.roles`, `.mfa`), el registro de contratos de U0.
2. **C03** (`aidlc-docs/inception/application-design/component-methods.md`, las seis tablas de `console-bff`): columnas
   «Roles» y «MFA». Es el oraculo de la matriz; nunca es `REGISTRY` ni el codigo del BFF.
3. **Versionada**: las filas `console-bff` de `contracts/openapi/role-endpoint-matrix.md`, que genera `contracts/tools/codegen.py`
   (P-4 (a) de U10-T02: no hay otro archivo de matriz; las columnas de estado del token viven en `test_role_matrix.py`).

`--check` sale con 0 si las tres coinciden y con 1, mostrando la diferencia fila por fila, si no. Admite `--c03 <ruta>` y
`--matrix <ruta>` para probar el rojo sobre copias.
"""

import argparse
import re
import sys
from pathlib import Path

from vectra_contracts.routes import REGISTRY

ROOT = Path(__file__).resolve().parents[3]
C03 = ROOT / "aidlc-docs/inception/application-design/component-methods.md"
MATRIX = ROOT / "contracts/openapi/role-endpoint-matrix.md"
SERVICE = "console-bff"
ROLE_COLUMNS = ("analista", "ingeniero_riesgo", "cro", "cumplimiento")

# (metodo, ruta) -> (roles, mfa)
Matrix = dict[tuple[str, str], tuple[frozenset[str], bool]]

_ENDPOINT = re.compile(r"`(GET|POST|PUT|DELETE) (/api/console/[^`\s]+)`")


def from_registry() -> Matrix:
    return {(r.method, r.path): (frozenset(role.value for role in r.roles), r.mfa) for r in REGISTRY[SERVICE]}


def _roles(cell: str) -> frozenset[str]:
    text = cell.replace("*", "").strip()
    if text == "todos":
        return frozenset(ROLE_COLUMNS)
    if text in ("", "—", "-"):
        return frozenset()
    return frozenset(part.strip() for part in text.split(",") if part.strip())


def _mfa(cell: str) -> bool:
    return cell.strip().lower().startswith(("sí", "si"))


def from_c03(path: Path = C03) -> Matrix:
    """Las filas de las tablas de la seccion `## C03 \\`console-bff\\`` (hasta el siguiente `## `)."""
    section = False
    found: Matrix = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line.startswith("## C03")
            continue
        if not section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        match = _ENDPOINT.search(cells[1]) if len(cells) >= 4 else None
        if match:
            found[(match.group(1), match.group(2))] = (_roles(cells[2]), _mfa(cells[3]))
    return found


def from_versioned(path: Path = MATRIX) -> Matrix:
    """Las filas `console-bff` de la matriz de U0: `| servicio | metodo | ruta | analista | ingeniero | cro | cumplimiento | MFA | Scopes |`."""
    found: Matrix = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 8 or cells[0] != SERVICE:
            continue
        roles = frozenset(role for role, mark in zip(ROLE_COLUMNS, cells[3:7], strict=True) if mark == "x")
        found[(cells[1], cells[2].strip("`"))] = (roles, _mfa(cells[7]))
    return found


def _describe(value: tuple[frozenset[str], bool] | None) -> str:
    if value is None:
        return "ausente"
    roles, mfa = value
    return f"roles={sorted(roles)} mfa={'si' if mfa else 'no'}"


def differences(sources: dict[str, Matrix]) -> list[str]:
    """Una linea por fila en la que las fuentes no coinciden, con el valor de cada una."""
    keys = sorted(set().union(*sources.values()))
    lines: list[str] = []
    for key in keys:
        values = {name: matrix.get(key) for name, matrix in sources.items()}
        if len(set(values.values())) > 1:
            detail = "; ".join(f"{name}: {_describe(value)}" for name, value in values.items())
            lines.append(f"{key[0]} {key[1]}: {detail}")
    return lines


def check(c03: Path = C03, matrix: Path = MATRIX) -> tuple[int, str]:
    sources = {"REGISTRY": from_registry(), "C03": from_c03(c03), "versionada": from_versioned(matrix)}
    lines = differences(sources)
    if lines:
        return 1, "role_matrix: las matrices no coinciden:\n" + "\n".join(lines)
    count = len(sources["REGISTRY"])
    return 0, f"role_matrix: {count} endpoints comparados; REGISTRY, C03 y role-endpoint-matrix.md coinciden"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        required=True,
        help="compara las tres fuentes y sale con 1 si difieren",
    )
    parser.add_argument(
        "--c03",
        type=Path,
        default=C03,
        help="ruta de component-methods.md (para probar el rojo sobre una copia)",
    )
    parser.add_argument("--matrix", type=Path, default=MATRIX, help="ruta de role-endpoint-matrix.md")
    args = parser.parse_args(argv)
    code, message = check(args.c03, args.matrix)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
