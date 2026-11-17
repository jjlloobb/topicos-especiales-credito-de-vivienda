"""Auditoria de npm con una unica excepcion acotada y con caducidad (U00-T06).

`npm audit` no tiene lista de excepciones. Este guion lee `npm audit --json` y falla con cualquier
aviso de severidad alta o critica salvo `EXEMPT_ADVISORY`, y solo mientras no pase `EXEMPT_UNTIL`.
Pasada esa fecha el aviso vuelve a poner el check en rojo, sin que nadie tenga que acordarse.

Uso: `python contracts/tools/npm_audit.py [--today AAAA-MM-DD]` desde `vectra-risk/`.
Para retirarlo: borrar este guion y su prueba, y volver a `npm audit --audit-level=high` en el workflow.
"""

import argparse
import datetime
import json
import subprocess
import sys
from typing import Any

# picomatch <= 4.0.7 (ReDoS por extglobs repetidos de una sola rama, CWE-1333, CVSS 7.5). 4.0.7 es la ultima
# version publicada: no hay version corregida. Solo llega por herramientas de desarrollo y de construccion
# (vite, vitest, size-limit, tinyglobby, fdir, typescript-eslint) con patrones glob escritos en el repositorio,
# nunca por una entrada de usuario, y no esta en la imagen final de la SPA (nginx, sin Node).
EXEMPT_ADVISORY = "GHSA-fc5q-39xc-vjpf"
EXEMPT_UNTIL = datetime.date(2026, 12, 17)
BLOCKING = ("high", "critical")


def advisories(vulns: dict[str, Any], name: str, seen: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """Los avisos (no los paquetes intermedios) de los que depende `name`, sin repetir ciclos."""
    found: list[dict[str, Any]] = []
    for via in vulns.get(name, {}).get("via", []):
        if isinstance(via, dict):
            found.append(via)
        elif isinstance(via, str) and via not in seen:
            found.extend(advisories(vulns, via, seen | {name}))
    return found


def ghsa(advisory: dict[str, Any]) -> str:
    return str(advisory.get("url", "")).rsplit("/", 1)[-1]


def evaluate(report: dict[str, Any], today: datetime.date) -> tuple[list[str], list[str]]:
    """(paquetes que bloquean, paquetes exceptuados)."""
    vulns = report.get("vulnerabilities")
    if not isinstance(vulns, dict) or "error" in report:
        return [f"respuesta de npm audit inesperada: {str(report)[:200]}"], []
    active = today <= EXEMPT_UNTIL
    blocking: list[str] = []
    exempt: list[str] = []
    for name, vuln in sorted(vulns.items()):
        if vuln.get("severity") not in BLOCKING:
            continue
        high = [a for a in advisories(vulns, name) if a.get("severity") in BLOCKING]
        others = [a for a in high if ghsa(a) != EXEMPT_ADVISORY]
        if not high or others or not active:
            blocking.append(name)
        else:
            exempt.append(name)
    return blocking, exempt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", type=datetime.date.fromisoformat, default=None)
    parser.add_argument("--from-file", help="leer el JSON de un archivo en vez de ejecutar npm audit")
    args = parser.parse_args(argv)
    today = args.today or datetime.datetime.now(datetime.UTC).date()
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as handle:
            raw = handle.read()
    else:
        raw = subprocess.run(["npm", "audit", "--json"], capture_output=True, text=True, check=False).stdout
    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        print("npm audit no devolvio JSON")
        return 1
    blocking, exempt = evaluate(report, today)
    if exempt:
        print(f"exceptuado {EXEMPT_ADVISORY} hasta {EXEMPT_UNTIL}: {', '.join(exempt)}")
    if blocking:
        reason = "caducada" if today > EXEMPT_UNTIL else "avisos altos no exceptuados"
        print(f"npm audit en rojo ({reason}): {', '.join(blocking)}")
        return 1
    print("npm audit en verde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
