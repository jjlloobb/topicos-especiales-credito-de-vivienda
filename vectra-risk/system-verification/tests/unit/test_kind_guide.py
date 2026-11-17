"""La guia del operador `docs/paso-18-kind.md` (U12-T06, CA-1, CA-2 y CA-8).

Tres cosas: la **estructura** (las doce fases en orden, con prerrequisitos, pasos, plantilla, duracion y puerta, y la primera pagina con «Quien hace que», los riesgos, los sintomas y el estado final),
el **mundo cerrado** (la guia solo nombra lo que existe en el repositorio: Applications, namespaces, secciones y opciones de la CLI, guiones, PR preparados, rutas, lineas citadas, selectores, series, alertas,
usuarios y rutas de la consola; y respeta el orden de F2 y el de las secciones) y la **coherencia** con el README de la imagen, con los guiones y con los guiones de las demos (una sola verdad).
La prueba de mundo cerrado **no** demuestra que la guia funcione en kind: demuestra que no nombra nada inventado.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import kind_docs as kd
import pytest
import yaml
from vectra_verification import cli, driver, guard, rt2_latency
from vectra_verification.scenarios import rt2

README = kd.SYSTEM / "README.md"
MARKER = "POR CONFIRMAR contra el README de U12-T05"
GUIDE_TEXT = kd.GUIDE.read_text(encoding="utf-8")
FIRST_PAGE = (
    "## Quién hace qué",
    "## Riesgos que pueden impedir una demo",
    "## Si algo falla: a qué unidad apunta cada síntoma",
    "## Cómo dejar el clúster como estaba",
)
LABELS = ("Plantilla:", "Duración:", "**Puerta de")
# Nombres de `vectra-*` que no son namespaces (nodos de Docker, recursos y la propia herramienta).
NOT_NAMESPACES = {
    "vectra-verification", "vectra-risk", "vectra-risk-gitops", "vectra-control-plane", "vectra-worker", "vectra-worker2", "vectra-internal-ca", "vectra-spa-route", "vectra-verification-operators",
    "vectra-verification-operator", "vectra-normal", "vectra-producto-panel", "vectra-console", "vectra-e2e-keys", "vectra-risk-gitops", "vectra-payload",
}  # fmt: skip
GENERATED = (
    "reference-model/.out",
    "system-verification/evidence",
    "evidence/",
    "platform/.tools",
    "platform/.charts",
)
KUBE_PREFIXES = ("deploy/", "job/", "pod/", "svc/", "sa/", "statefulset/")
NOT_REPO_PATHS = {"identity/synthetic-users", "grafana/admin", "secret/data", "edge/valkey", "identity/break-glass"}  # rutas de la bóveda
# Series que no emite este repositorio: las del propio Prometheus y las de cAdvisor (las nombra la guia para medir la retencion y la memoria).
EXTERNAL_SERIES = {"prometheus_tsdb_lowest_timestamp_seconds", "container_memory_working_set_bytes"}
TIMES = {
    "journey-7-3.md": ("12,4 a 19,3 min", "hasta 25 min", "5 min"),
    "journey-7-4.md": ("más de 75 min", "≈ 30 min"),
    "rt-5.md": ("5 min",),
    "dashboard.md": ("22:18 UTC", "23:00 UTC", "02:40 UTC"),
}


def section(text: str, phase: str) -> str:
    match = re.search(rf"^## {phase} .*?(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, phase
    return match.group(0)


def code_blocks(text: str) -> list[tuple[int, str, str]]:
    """`(linea, informacion, contenido)` de cada bloque de codigo."""
    blocks, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        if re.match(r"^\s*```", lines[i]):
            start, info = i + 1, lines[i].strip()[3:].strip()
            i += 1
            body = []
            while i < len(lines) and not re.match(r"^\s*```", lines[i]):
                body.append(lines[i])
                i += 1
            blocks.append((start, info, "\n".join(body)))
        i += 1
    return blocks


@cache
def cli_options() -> dict[str, set[str]]:
    parser = cli.build_parser({})
    action = next(a for a in parser._actions if a.dest == "section")  # noqa: SLF001
    return {
        n: {o for o in sub._option_string_actions if o.startswith("--")} for n, sub in action.choices.items()
    }  # noqa: SLF001


@cache
def humo_options() -> dict[str, set[str]]:
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("humo_kind", kd.KIND_DOCS / "humo.py")
    assert spec is not None and spec.loader is not None
    module = sys.modules.get("humo_kind") or importlib.util.module_from_spec(spec)
    sys.modules["humo_kind"] = module
    if not hasattr(module, "parser"):
        spec.loader.exec_module(module)
    top = module.parser({})
    action = next(a for a in top._actions if a.dest == "command")  # noqa: SLF001
    return {
        n: {o for o in sub._option_string_actions if o.startswith("--")} for n, sub in action.choices.items()
    }  # noqa: SLF001


@cache
def all_file_names() -> set[str]:
    skip = {".venv", "node_modules", ".git", "__pycache__", ".tools", ".charts"}
    return {
        p.name for p in kd.VECTRA.rglob("*") if p.is_file() and not skip & set(p.relative_to(kd.VECTRA).parts)
    }


def resolve(path: str) -> Path | None:
    for base in (kd.VECTRA, kd.VECTRA.parent, kd.SYSTEM):
        if (base / path).exists():
            return base / path
    return None


def lines_of(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def readme_exists() -> bool:
    return README.is_file()


# --- el mundo cerrado --------------------------------------------------------------------------------------------------------------------------------


@cache
def option_catalogue() -> dict[str, list[object]]:
    """Cada opcion de la CLI y de `humo`: sus acciones (con `choices` y `type`), para comprobar **los valores** que la guia les da."""
    found: dict[str, list[object]] = {}
    for parsers in (cli_parsers(), humo_parsers()):
        for sub in parsers.values():
            for action in sub._actions:  # noqa: SLF001
                for option in action.option_strings:
                    found.setdefault(option, []).append(action)
    return found


@cache
def cli_parsers() -> dict[str, object]:
    action = next(a for a in cli.build_parser({})._actions if a.dest == "section")  # noqa: SLF001
    return dict(action.choices)


@cache
def humo_parsers() -> dict[str, object]:
    humo_options()  # carga el modulo
    import sys

    top = sys.modules["humo_kind"].parser({})
    return dict(next(a for a in top._actions if a.dest == "command").choices)  # noqa: SLF001


def option_value_findings(where: str, line: str) -> list[str]:
    """`--opcion valor` o `--opcion=valor`: si la opcion tiene `choices`, el valor es uno de ellos; si tiene `type`, el valor lo convierte (ni `--reactivation presentador` ni `--operator-timeout abc`)."""
    found = []
    for option, value in re.findall(r"(--[a-z][a-z-]*)[ =]([^\s`'\")(,;|<$-][^\s`'\")(,;|]*)", line):
        actions = option_catalogue().get(option, [])
        choices = [set(a.choices) for a in actions if getattr(a, "choices", None)]  # type: ignore[attr-defined]
        if choices and not any(value in c for c in choices):
            found.append(
                f"{where}: el valor {value} de {option} no es ninguno de {sorted(set().union(*choices))}"
            )
        types = [a.type for a in actions if getattr(a, "type", None)]  # type: ignore[attr-defined]
        if types and not any(_converts(kind, value) for kind in types):
            found.append(f"{where}: el valor {value} de {option} no es un número")
    return found


def _converts(kind: object, value: str) -> bool:
    try:
        kind(value)  # type: ignore[operator]
    except (TypeError, ValueError):
        return False
    return True


@cache
def pod_names_in_the_repository() -> str:
    """Los nombres de pod que el repositorio mismo usa (`pod/vault-0` en `seed-vault.sh`, `vault_paths.py`, los charts)."""
    chunks = [kd.corpus()]
    for path in (kd.VECTRA / "platform").rglob("*.sh"):
        chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def pod_name_findings(where: str, line: str) -> list[str]:
    """Un `pod/<nombre>-<n>` (de un StatefulSet) de la guia o de un guion es el que el repositorio nombra: `pod/vault-0`, no `pod/vault-1`."""
    return [
        f"{where}: el pod {name} no lo nombra ningún guion ni chart del repositorio"
        for name in re.findall(r"\bpod/([a-z][a-z0-9-]*-\d+)\b", line)
        if not re.search(rf"\b{re.escape(name)}\b", pod_names_in_the_repository())
    ]


def closed_world_findings(text: str) -> list[str]:
    """Todo lo que el texto de la guia nombra y no existe, con su linea."""
    found: list[str] = []
    applications = kd.applications() | kd.components()
    namespaces = kd.namespaces()
    sections = cli_options()
    humo = humo_options()
    names = all_file_names()
    users = kd.realm_users()
    routes = kd.spa_routes()
    alerts = set(re.findall(r"alert:\s*([A-Za-z]+)", kd.corpus()))
    corpus = kd.corpus()
    for number, line in enumerate(text.split("\n"), 1):
        where = f"{number}"
        for app in re.findall(r"Application `([a-z0-9-]+)`", line) + re.findall(
            r"applications\.argoproj\.io ([a-z0-9-]+)", line
        ):
            if app not in applications:
                found.append(f"{where}: la Application {app} no existe")
        for namespace in re.findall(r"(?:^|\s)(?:-n|--namespace)[ =]([a-z0-9-]+)", line):
            if namespace not in namespaces:
                found.append(f"{where}: el namespace {namespace} no existe")
        for token in re.findall(r"(?<![\w/.-])(vectra-[a-z0-9]+(?:-[a-z0-9]+)*)(?![\w/.-])", line):
            if token not in namespaces and token not in NOT_NAMESPACES:
                found.append(f"{where}: `{token}` no es un namespace ni un nombre conocido")
        for match in re.finditer(r"vectra-verification (?!-)([a-z0-9][a-z0-9-]*)((?: --[a-z-]+)*)", line):
            section_name, options = match.group(1), re.findall(r"--[a-z-]+", match.group(2))
            if section_name in kd.DEFERRED_SECTIONS:
                found.append(f"{where}: la sección diferida {section_name} no se ejecuta")
            elif section_name not in sections:
                found.append(f"{where}: la sección {section_name} no existe en la CLI")
            else:
                found += [
                    f"{where}: la opción {o} no existe en la sección {section_name}"
                    for o in options
                    if o not in sections[section_name]
                ]
        for match in re.finditer(r"\bhumo (login|flujo|consola|modelos)((?: --[a-z-]+)*)", line):
            found += [
                f"{where}: la opción {o} no existe en humo {match.group(1)}"
                for o in re.findall(r"--[a-z-]+", match.group(2))
                if o not in humo[match.group(1)]
            ]
        for script in re.findall(r"\b([\w-]+\.(?:sh|py))\b", line):
            if script not in names:
                found.append(f"{where}: el guion {script} no existe")
        for script, step in re.findall(r"\b((?:journey-7-3|journey-7-4|rt-5|dashboard)\.sh) (\d+)", line):
            steps = set(
                re.findall(
                    r"^\s{2}(\d+)\)", (kd.SYSTEM / "demos/verify" / script).read_text(encoding="utf-8"), re.M
                )
            )
            if step not in steps:
                found.append(f"{where}: {script} no tiene el paso {step}")
        for pr in re.findall(r"demos/prs/([\w-]+(?:\.py)?)", line):
            if not (kd.SYSTEM / "demos/prs" / pr).exists():
                found.append(f"{where}: el PR preparado {pr} no existe en demos/prs")
        for span in re.findall(r"`([^`\n]+)`", line):
            if (
                re.fullmatch(r"[\w.@-][\w./@-]*/[\w./@-]*", span)
                and not span.startswith(KUBE_PREFIXES)
                and span not in NOT_REPO_PATHS
            ):
                if (
                    span.startswith(GENERATED)
                    or span.startswith("/")
                    or resolve(span.rstrip("/")) is not None
                ):
                    continue
                if (
                    re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}/[\w.-]+", span)
                    and "." in span.split("/")[0]
                    and not (kd.VECTRA / span).exists()
                ):
                    continue  # una etiqueta como `app.kubernetes.io/name`
                found.append(f"{where}: la ruta `{span}` no existe")
        for path, tail in re.findall(r"`([\w./@-]+)`,? líneas? ([\d, ay]+)", line):
            target = resolve(path)
            if target is None:
                continue
            for number_text in re.findall(r"\d+", tail):
                if int(number_text) > lines_of(target):
                    found.append(f"{where}: `{path}` no tiene la línea {number_text}")
        for key, value in re.findall(r"-l ([\w./-]+)=([\w.-]+)", line):
            if not kd.label_exists(key, value):
                found.append(
                    f"{where}: el selector {key}={value} no es la etiqueta `{key}: {value}` de ningún chart ni cliente"
                )
        found += option_value_findings(where, line)
        found += pod_name_findings(where, line)
        for name in re.findall(r"alertname=\"([A-Za-z]+)\"", line) + re.findall(
            r"alerta `([A-Za-z]+)`", line
        ):
            if name not in alerts:
                found.append(f"{where}: la alerta {name} no está en ninguna regla")
        for series in re.findall(r"\b((?:vectra|inbound|container|prometheus)_[a-z0-9_]+)\b", line):
            if series not in EXTERNAL_SERIES and series not in corpus:
                found.append(f"{where}: la serie {series} no la emite ningún chart ni código")
        for user in re.findall(r"\b((?:analista|ingeniero|cro|cumplimiento|operacion)-\d+)\b", line):
            if user not in users:
                found.append(f"{where}: el usuario {user} no está en el realm de kind")
        for route in re.findall(r"`ruta (/[^`\s]*)`", line):
            if route not in routes:
                found.append(f"{where}: la ruta de la consola {route} no existe")
    return found


# --- las cifras: cada una en el sitio donde se usa, contra lo que las fija -------------------------------------------------------------------------------


def to_minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def exit_code_findings(text: str) -> list[str]:
    """Los códigos de salida que la guía da, contra las constantes de la CLI (`cli.EXIT_*`) y de `demos/verify/lib.sh`; todo «código N» de la guía está en esta lista de hechos."""
    found = []
    read = re.search(r"\*\*Cómo leer el código de salida\*\*[^\n]*|Cómo leer el código de salida[^\n]*", text)
    sentence = read.group(0) if read else ""
    for code, words in (
        (cli.EXIT_PASS, "todo `pasa`"),
        (cli.EXIT_FAIL, "algo `falla`"),
        (cli.EXIT_NOT_RUN, "`no ejecutado`"),
        (cli.EXIT_REFUSED, "la herramienta se negó"),
    ):
        if f"`{code}` {words}" not in sentence:
            found.append(f"«Cómo leer el código de salida»: falta «`{code}` {words}» (la CLI da {code})")
    lib = (kd.SYSTEM / "demos/verify/lib.sh").read_text(encoding="utf-8")
    verify = {
        "expected": int(re.search(r"expected\(\) \{[^}]*exit (\d)", lib).group(1)),  # type: ignore[union-attr]
        "not_expected": int(re.search(r"not_expected\(\) \{[^}]*exit (\d)", lib).group(1)),  # type: ignore[union-attr]
        "cannot_read": int(re.search(r"cannot_read\(\) \{[^}]*exit (\d)", lib).group(1)),  # type: ignore[union-attr]
    }
    for code, words in (
        (verify["expected"], "`0` lo esperado"),
        (verify["not_expected"], "`1` no es lo esperado"),
        (verify["cannot_read"], "`2` no se pudo leer"),
    ):
        if not words.startswith(f"`{code}`") or words not in sentence:
            found.append(
                f"«Cómo leer el código de salida»: los `verify` dan {code} y la guía no dice «{words}»"
            )
    facts = (
        (r"código (\d) y `ruta_faltante`", cli.EXIT_REFUSED),
        (r"repetirlo se niega \(código (\d)\)", cli.EXIT_REFUSED),
        (r"`browser_launch_error` \(código (\d)\)", cli.EXIT_NOT_RUN),
        (r"que no existe da código (\d)", cli.EXIT_NOT_RUN),
        (r"código (\d) sin mensaje", cli.EXIT_PASS),
        (r"código (\d) y sin mensaje", cli.EXIT_PASS),
        (r"Esperado: código (\d) \(modelo", cli.EXIT_PASS),
        (r"`OOMKilled` \(código (\d+)\)", 137),
    )
    covered = set()
    for pattern, expected in facts:
        for match in re.finditer(pattern, text):
            covered.add(match.start(1) - len("código "))
            if int(match.group(1)) != expected:
                found.append(f"«{match.group(0)}»: el código es {expected}, no {match.group(1)}")
    for pattern, _ in facts[:4] + facts[7:]:
        if not re.search(pattern, text):
            found.append(f"la guía ya no dice «{pattern}»")
    for match in re.finditer(r"código (\d+)", text):
        if not any(abs(match.start() - at) <= 1 for at in covered):
            found.append(f"«{match.group(0)}» no es ningún hecho conocido de la CLI ni de los guiones")
    return found


def time_findings(text: str) -> list[str]:
    """Las horas y los minutos de `decisions`, derivados de `guard` (la estimación y la hora límite) y de U11 (02:30 UTC más 10 min): cada cifra, en el sitio donde se usa. Toda hora UTC de la guía es una de ellas y las de Colombia son su UTC menos 5 h."""
    found = []
    estimate = guard.estimated_duration(2000, 10.0)
    minutes = round(estimate.total_seconds() / 60)
    limit = datetime(2026, 1, 1, guard.CUTOFF.hour, guard.CUTOFF.minute, tzinfo=UTC) - estimate
    limit_text, cutoff_text = (
        f"{limit.hour:02d}:{limit.minute:02d}",
        f"{guard.CUTOFF.hour:02d}:{guard.CUTOFF.minute:02d}",
    )
    if re.findall(r"2 000 × 1 s \+ 300 s ≈ (\d+) min", text) != [str(minutes)]:
        found.append(f"la estimación de `decisions` (2 000 / 10 + 2 000 × 1 s + 300 s) es ≈ {minutes} min")
    utc_ok = {cutoff_text, limit_text, "21:45", "00:00", "02:30", "02:40", "17:00"}
    for number, line in enumerate(text.split("\n"), 1):
        for clock in re.findall(r"(\d\d:\d\d) UTC", line):
            if clock not in utc_ok:
                found.append(
                    f"{number}: la hora {clock} UTC no es la de `guard` ni la de U11 ({sorted(utc_ok)})"
                )
        for clock in re.findall(r"(\d\d:\d\d) de Colombia", line):
            utc = (to_minutes(clock) + 5 * 60) % (24 * 60)
            if f"{utc // 60:02d}:{utc % 60:02d}" not in utc_ok:
                found.append(f"{number}: la hora {clock} de Colombia no es una de las UTC menos 5 h")
        for clock in re.findall(
            r"[Ll]anza antes de ≈? ?(\d\d:\d\d) UTC|se lanza antes de ≈? ?(\d\d:\d\d) UTC", line
        ):
            if limit_text not in clock:
                found.append(
                    f"{number}: `decisions` se lanza antes de {limit_text} UTC, no de {''.join(clock)}"
                )
        for clock in re.findall(r"antes de las (\d\d:\d\d) UTC", line):
            if "decisions" in line and clock != cutoff_text and "12:00" not in line:
                found.append(f"{number}: la hora límite de `decisions` es {cutoff_text} UTC, no {clock}")
    if len(re.findall(r"[Ll]anza antes de ≈? ?\d\d:\d\d UTC|se lanza antes de ≈? ?\d\d:\d\d UTC", text)) < 3:
        found.append(f"la hora de lanzamiento (≈ {limit_text} UTC) falta de F6, del calendario o de K-04")
    if to_minutes("21:45") >= to_minutes(limit_text):
        found.append("la holgura de ≈ 21:45 UTC debe ser anterior a la hora límite")
    dashboard = (kd.SYSTEM / "demos/dashboard.md").read_text(encoding="utf-8")
    if (
        "02:30 UTC" not in dashboard
        or "10 min de desfase" not in dashboard
        or "02:30 UTC más hasta 10 min" not in text
    ):
        found.append("la pasada de U11 es a las 02:30 UTC más hasta 10 min (≈ 02:40 UTC)")
    return found


def f2_order_findings(text: str) -> list[str]:
    """El orden de F2: la politica y el eco retirado antes de `console-bff`, `product-metrics` el ultimo, el registro primero; y `decisions` antes de `rt2`."""
    body = section(text, "F2")
    marks = [
        ("decision-registry", body.find("sync decision-registry")),
        ("governance", body.find("sync governance")),
        ("política", body.find("**Política activa**")),
        ("model-serving", body.find("sync model-serving")),
        ("modelo de referencia", body.find("**Modelo de referencia `activo`**")),
        ("scoring-explainability", body.find("sync scoring-explainability")),
        ("case-management", body.find("sync case-management")),
        ("bias-monitoring", body.find("sync bias-monitoring")),
        ("eco retirado", body.find("delete -f identity-edge/tests/e2e/echo/manifests.yaml")),
        ("console-bff", body.find("sync console-bff")),
        ("product-metrics", body.find("sync product-metrics")),
    ]
    found = [f"F2: falta {name}" for name, at in marks if at < 0]
    positions = [at for _, at in marks if at >= 0]
    if positions != sorted(positions):
        found.append(
            "F2: el orden no es registro, governance, política, model-serving, modelo, scoring, casos, bias, eco, consola, product-metrics"
        )
    sync_positions = [
        (at, name)
        for name, at in marks
        if name not in {"política", "modelo de referencia", "eco retirado"} and at >= 0
    ]
    if sync_positions and max(sync_positions)[1] != "product-metrics":
        found.append("F2: product-metrics no es el último sync")
    commands = "\n".join(body for _, _, body in code_blocks(text))
    decisions, rt2 = (
        commands.find("vectra-verification decisions"),
        re.search(r"vectra-verification rt2(?![\w-])", commands),
    )
    if decisions < 0 or (rt2 is not None and decisions > rt2.start()):
        found.append("`decisions` no va antes de `rt2`")
    return found


def test_closed_world_the_guide_names_nothing_that_does_not_exist() -> None:
    assert closed_world_findings(GUIDE_TEXT) == []


def test_the_figures_of_the_guide_are_the_ones_of_the_cli_the_guard_and_the_scripts() -> None:
    """F-02: los códigos de salida, las horas y los minutos de la guía coinciden, cada uno en su sitio, con `cli.EXIT_*`, con `guard` y con `demos/verify/lib.sh`."""
    assert exit_code_findings(GUIDE_TEXT) == []
    assert time_findings(GUIDE_TEXT) == []


# Las seis mentiras que la ronda 1 dejó vivas (revisiones/U12-T06/ronda-1.md, F-02): cada una tiene que hacer fallar una prueba.
SURVIVORS = {
    "el código 3 cambiado a 4": lambda t: t.replace(
        "`3` la herramienta se negó", "`4` la herramienta se negó"
    ),
    "prepare repetido da 1": lambda t: t.replace(
        "repetirlo se niega (código 3)", "repetirlo se niega (código 1)"
    ),
    "pod/vault-1": lambda t: t.replace("pod/vault-0", "pod/vault-1"),
    "--reactivation presentador": lambda t: t.replace(
        "--reactivation presenter", "--reactivation presentador"
    ),
    "la hora límite 23:58": lambda t: t.replace("antes de ≈ 22:18 UTC", "antes de ≈ 23:58 UTC"),
    "≈ 10 min": lambda t: t.replace("≈ 42 min", "≈ 10 min"),
}


@pytest.mark.parametrize("name", sorted(SURVIVORS))
def test_red_each_mutation_the_round_1_review_left_alive_now_dies(name: str) -> None:
    mutated = SURVIVORS[name](GUIDE_TEXT)
    assert mutated != GUIDE_TEXT, name
    found = closed_world_findings(mutated) + exit_code_findings(mutated) + time_findings(mutated)
    assert found, f"{name}: ninguna prueba la detecta"


def test_closed_world_f2_keeps_the_order_policy_before_the_console_and_product_metrics_last() -> None:
    assert f2_order_findings(GUIDE_TEXT) == []


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (
            lambda t: t + "\nCorre `Application `inventada`` y la Application `app-que-no-existe`.\n",
            "la Application app-que-no-existe no existe",
        ),
        (
            lambda t: t + "\nMira `kubectl get pods -l app.kubernetes.io/name=selector-que-no-existe`.\n",
            "el selector",
        ),
        (lambda t: t + "\nVer `CANDIDATAS.md`, línea 9999.\n", "no tiene la línea 9999"),
        (
            lambda t: t + "\nCorre vectra-verification rt9 y vectra-verification network.\n",
            "la sección rt9 no existe",
        ),
        (
            lambda t: t + "\nCorre vectra-verification rt3 --opcion-inventada.\n",
            "la opción --opcion-inventada",
        ),
        (
            lambda t: t + "\nVer `system-verification/docs/kind/no-existe.sh` y no-existe.sh.\n",
            "el guion no-existe.sh no existe",
        ),
        (lambda t: t + "\nEntra con `analista-9` y la ruta `ruta /nada`.\n", "el usuario analista-9"),
        (
            lambda t: t + '\nConsulta alertname="AlertaInventada" y vectra_serie_inventada_total.\n',
            "la alerta AlertaInventada",
        ),
        (
            lambda t: t + "\nEn `-n vectra-inventado` y `kubectl get pods -n vectra-inventado`.\n",
            "el namespace vectra-inventado",
        ),
        (lambda t: t + "\nUsa demos/prs/no-existe y rt-5.sh 9.\n", "no tiene el paso 9"),
        (
            lambda t: t + "\nBorra con `kubectl get pods -l app.kubernetes.io/name=keycloakx`.\n",
            "no es la etiqueta `app.kubernetes.io/name: keycloakx`",
        ),
        (
            lambda t: t + "\nCorre `vectra-verification rt2 --reactivation presentador`.\n",
            "el valor presentador",
        ),
        (lambda t: t + "\nCorre `vectra-verification rt2 --operator-timeout abc`.\n", "no es un número"),
        (lambda t: t + "\nAbre pod/vault-1 con `kubectl get`.\n", "el pod vault-1"),
    ],
)
def test_red_closed_world_each_invented_name_makes_it_fail(mutate: object, needle: str) -> None:
    """Rojo de CA-2: una Application inventada, un selector que no existe, una «línea 9999», una sección, una opción, un guion, un usuario, una alerta, un namespace y un paso de verify que no existen fallan."""
    found = closed_world_findings(mutate(GUIDE_TEXT))  # type: ignore[operator]
    assert any(needle in f for f in found), found


def test_red_f2_product_metrics_before_decision_registry_fails() -> None:
    """Rojo de CA-2: `product-metrics` antes de `decision-registry` hace fallar el orden de F2."""
    swapped = GUIDE_TEXT.replace("sync decision-registry\n", "sync product-metrics\n", 1)
    assert (
        "F2: el orden no es registro, governance, política, model-serving, modelo, scoring, casos, bias, eco, consola, product-metrics"
        in f2_order_findings(swapped)
    )


def test_red_f2_the_policy_after_console_bff_fails() -> None:
    """La política va antes de `console-bff` y el eco retirado también: moverlos después del sync de la consola hace fallar."""
    body_marker = "**Política activa**"
    assert body_marker in GUIDE_TEXT
    moved = GUIDE_TEXT.replace(body_marker, "**Politica (movida)**", 1).replace(
        "sync console-bff console-spa", "sync console-bff console-spa\n    **Política activa**", 1
    )
    assert any("el orden" in f for f in f2_order_findings(moved))
    moved_echo = GUIDE_TEXT.replace(
        "delete -f identity-edge/tests/e2e/echo/manifests.yaml",
        "delete -f identity-edge/tests/e2e/echo/MOVIDO.yaml",
        1,
    ).replace(
        "sync console-bff console-spa",
        "sync console-bff console-spa\n    delete -f identity-edge/tests/e2e/echo/manifests.yaml",
        1,
    )
    assert any("el orden" in f for f in f2_order_findings(moved_echo))


def test_red_decisions_after_rt2_fails() -> None:
    mutated = GUIDE_TEXT.replace("vectra-verification decisions\n", "vectra-verification rt2\n", 1)
    assert "`decisions` no va antes de `rt2`" in f2_order_findings(mutated)


# --- la estructura -----------------------------------------------------------------------------------------------------------------------------------


def test_structure_twelve_phases_in_order_each_with_its_parts() -> None:
    headings = re.findall(r"^## (F\d+) ", GUIDE_TEXT, re.M)
    assert headings == [f"F{n}" for n in range(12)]
    missing = []
    for phase in kd.PHASES + ("F11",):
        body = section(GUIDE_TEXT, phase)
        for label in LABELS:
            if label not in body:
                missing.append(f"{phase}: falta «{label}»")
        if phase != "F11" and "**Prerrequisitos" not in body and "Prerrequisitos de la máquina" not in body:
            missing.append(f"{phase}: faltan prerrequisitos")
        if "**Pasos" not in body:
            missing.append(f"{phase}: faltan los pasos")
        if not code_blocks(body) and phase not in ("F11",):
            missing.append(f"{phase}: sin ningún comando")
        if f"<!-- inventario:{phase} -->" not in body:
            missing.append(f"{phase}: sin su tabla del inventario")
    assert missing == []


def test_structure_the_first_page_has_who_does_what_the_risks_the_symptoms_and_the_final_state() -> None:
    first_phase = GUIDE_TEXT.index("## F0 ")
    head = GUIDE_TEXT[:first_phase]
    for title in FIRST_PAGE:
        assert title in head, title
    risks = section(GUIDE_TEXT.replace("## Riesgos que pueden impedir una demo", "## F99 riesgos"), "F99")
    assert all(f"**R-{n}**" in risks for n in range(1, 9))
    symptoms = GUIDE_TEXT[GUIDE_TEXT.index("## Si algo falla") : GUIDE_TEXT.index("## Cómo dejar el clúster")]
    assert (
        symptoms.count("\n| ") >= 15
        and "Unidad" in symptoms
        and "sale con código 0 y sin mensaje" in symptoms
    )


def test_structure_every_wait_says_how_long_and_what_to_look_at() -> None:
    bad = []
    for number, line in enumerate(GUIDE_TEXT.split("\n"), 1):
        for wait in re.findall(r"\*\*Espera[^*]*\*\*[^\n]*", line):
            if not re.search(r"\d", wait) or not re.search(r"[Mm]ira|[Mm]ientras", wait + line):
                bad.append(f"{number}: {wait[:80]}")
    assert bad == [] and "**Espera" in GUIDE_TEXT


def test_structure_the_tables_of_the_inventory_are_the_ones_the_inventory_renders() -> None:
    """La guia repite cada fase del inventario tal cual: una sola verdad (la tabla se genera de `inventario.yaml`)."""
    stale = []
    for phase in kd.PHASES + ("F11",):
        match = re.search(
            rf"<!-- inventario:{phase} -->\n(.*?)\n<!-- /inventario:{phase} -->", GUIDE_TEXT, re.S
        )
        assert match is not None, phase
        if match.group(1) != kd.render_phase_table(phase):
            stale.append(phase)
    assert stale == []


def test_the_guide_is_written_for_any_machine() -> None:
    """Sin rutas, nombres de usuario ni estado propio de la maquina donde se escribio (requisito del usuario: otra maquina con kind)."""
    forbidden = (
        r"/home/",
        r"/Users/",
        r"\bjjlloobb\b",
        r"en esta máquina",
        r"\.claude/worktrees",
        r"localhost:\d+/(?!vectra)",
        r"C:\\",
    )
    found = [pattern for pattern in forbidden if re.search(pattern, GUIDE_TEXT)]
    assert found == []
    for needle in (
        "14 GiB",
        "16 GiB",
        f"{budget_gib()} GiB",
        "v0.33.0",
        "v4.3.0",
        "OOMKilled",
        "máquina limpia",
    ):
        assert needle in GUIDE_TEXT, needle


# --- la coherencia -----------------------------------------------------------------------------------------------------------------------------------


def vv_block(text: str) -> str:
    """El bloque de codigo que define la funcion `vv` (la orden `docker run` unica: la del README y la de la guia)."""
    found = [body for _, _, body in code_blocks(text) if re.search(r"^\s*vv\(\) \{", body, re.M)]
    assert len(found) == 1, "la funcion `vv` se define una sola vez"
    return found[0]


def vv_function(text: str) -> str:
    """Solo la funcion `vv`, de `vv() {` a su llave de cierre."""
    match = re.search(r"^\s*vv\(\) \{.*?^\s*\}", vv_block(text), re.M | re.S)
    assert match is not None
    return match.group(0)


def vv_tokens(block: str) -> set[str]:
    """Lo que la orden fija: banderas largas, `-e VARIABLE`, el destino de cada montaje, `readonly` y el perfil seccomp (no las rutas de origen, que cambian de una maquina a otra)."""
    tokens = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", block))
    tokens |= {f"-e {name}" for name in re.findall(r"(?<![\w-])-e ([A-Z_]+)", block)}
    tokens |= {f"target={target}" for target in re.findall(r"target=([\w/.-]+)", block)}
    tokens |= {f"readonly:{target}" for target in re.findall(r"target=([\w/.-]+),readonly", block)}
    tokens |= {"seccomp" for _ in re.findall(r"seccomp=\S*chrome\.json", block)}
    return tokens


def test_coherence_the_docker_run_is_the_one_of_the_readme() -> None:
    """La orden `docker run` de la guia es la funcion `vv` del README de la imagen (U12-T05): cada bandera, cada variable, cada montaje (su destino y si es de solo lectura) y el perfil seccomp del README estan en la de la guia.
    Las marcas «POR CONFIRMAR» ya no existen."""
    assert readme_exists() and MARKER not in GUIDE_TEXT, (
        "el README existe: la guia no lleva marcas POR CONFIRMAR"
    )
    readme, guide = (
        vv_tokens(vv_function(README.read_text(encoding="utf-8"))),
        vv_tokens(vv_function(GUIDE_TEXT)),
    )
    assert readme >= {
        "--read-only",
        "--tmpfs",
        "--network",
        "--user",
        "--memory",
        "--security-opt",
        "-e VAULT_TOKEN",
        "-e KUBE_CONTEXT",
        "seccomp",
    }
    assert readme - guide == set(), (
        f"la orden docker run de la guía no trae {sorted(readme - guide)} del README"
    )
    assert guide - readme <= {"--name", "--entrypoint"}, sorted(guide - readme)
    assert "--add-host" in readme and "--add-host" in guide, (
        "U12-T09: `vv` lleva `--add-host vectra.localtest.me:<dirección>` (la de `guard.KIND.host`)"
    )
    assert "VAULT_TOKEN=" not in GUIDE_TEXT.replace("export VAULT_TOKEN=root", ""), (
        "el token va como variable, no como valor ni archivo"
    )
    assert "no-sandbox" not in GUIDE_TEXT.replace("nunca desactiva el sandbox", "")


def test_coherence_the_functions_of_the_guide_build_the_docker_command_of_the_readme(tmp_path: Path) -> None:
    """Se corre el bloque real de la guia con un `docker` de mentira que escribe sus argumentos: `vv` y `humo` arman la orden del README (el punto de entrada de la imagen intacto en `vv`, `python` y el guion montado en `humo`),
    la imagen va justo antes de los argumentos y `VV_EXTRA` no se filtra de `humo` a la orden siguiente."""
    block = vv_block(GUIDE_TEXT)
    functions = block[block.index("vv() {") :]
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "docker").write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$DOCKER_OUT.$$"\n', encoding="utf-8")
    (fake / "docker").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake}:{os.environ['PATH']}",
        "DOCKER_OUT": str(tmp_path / "argv"),
        "VERIF_HOME": "/h",
        "EVID": "/e",
        "VERIFICATION_IMAGE": "img@sha256:x",
        "VAULT_ADDR": "http://127.0.0.1:8200",
        "VAULT_TOKEN": "t",
        "GATEWAY_ADDRESS": "172.18.0.7",
    }
    script = f"{functions}\nvv prepare --commit abc\nhumo flujo --delivery /d\nvectra-verification report\n"
    done = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, check=False, cwd=tmp_path
    )
    assert done.returncode == 0, done.stderr
    runs = [
        p.read_text(encoding="utf-8").split("\n")[:-1]
        for p in sorted(tmp_path.glob("argv.*"), key=lambda p: p.stat().st_mtime_ns)
    ]
    assert len(runs) == 3
    prepare, humo, report = runs
    flags = vv_tokens(vv_block(README.read_text(encoding="utf-8")))
    for argv in runs:
        assert (
            argv[0] == "run"
            and "--rm" in argv
            and "--read-only" in argv
            and "--network" in argv
            and argv[argv.index("--network") + 1] == "host"
        )
        assert argv[argv.index("--memory") + 1] == "1g" and any(
            a.startswith("seccomp=") and a.endswith("chrome.json") for a in argv
        )
        assert argv.count("VAULT_TOKEN") == 1 and "VAULT_TOKEN=t" not in argv and "t" not in argv, (
            "el token va como variable, sin valor"
        )
        assert {f"target={a.split('target=')[1].split(',')[0]}" for a in argv if "target=" in a} >= {
            f for f in flags if f.startswith("target=")
        }
    assert prepare[prepare.index("img@sha256:x") :] == ["img@sha256:x", "prepare", "--commit", "abc"]
    assert "--entrypoint" not in prepare and "--entrypoint" not in report
    assert report[report.index("img@sha256:x") :] == ["img@sha256:x", "report"]
    at = humo.index("img@sha256:x")
    assert humo[at:] == ["img@sha256:x", "/humo.py", "flujo", "--delivery", "/d"]
    assert humo[humo.index("--entrypoint") + 1] == "python" and any(
        a.endswith("target=/humo.py,readonly") for a in humo
    )


def test_coherence_the_known_limits_of_the_tool_are_warned_where_the_operator_meets_them() -> None:
    """Los dos defectos conocidos de D2 (N-1 y N-2 de la revision de U12-T04, en `CANDIDATAS.md`) se advierten en la fase de D2 como avisos visibles, y los demas limites de la herramienta y de la imagen, en su fase."""
    f8 = section(GUIDE_TEXT, "F8")
    first, second = (re.search(rf"> \*\*Advertencia {n}[^\n]*(?:\n>[^\n]*)*", f8) for n in (1, 2))
    assert first is not None and second is not None, "D2: faltan los avisos visibles (blockquote) 1 y 2"
    assert all(
        word in first.group(0)
        for word in (
            "Ctrl-C",
            "parada del contenedor",
            "SIGKILL",
            "está corregido",
            "antes** de guardar",
            "mientras se envía el lote",
            "se reenvía entero",
        )
    ), first.group(0)
    assert "llega una fase tarde" not in first.group(0).replace("llegaba una fase tarde", ""), (
        "N-1 esta corregido (U12-T05, ronda 2): la guia no puede decir que el guardado aun llega tarde"
    )
    assert all(
        word in second.group(0)
        for word in ("--operator-timeout", "3 600 s", "no hay forma de retomar solo el cierre")
    ), second.group(0)
    assert f8.index("Advertencia 1") < f8.index("**Pasos")
    assert "Interrúmpela solo con Ctrl-C" in f8 and "dentro del plazo" in f8
    f0 = section(GUIDE_TEXT, "F0")
    for needle in (
        "Solo Linux",
        "`--network host`",
        "cópiala allí",
        "`--memory 1g` no está medido",
        "containers-common",
        "recortado",
        "no Docker Desktop (tampoco en Linux)",
        "`make`, `python3` y `git`",
        "`kind-vectra`",
        "`KUBE_CONTEXT=<contexto>`",
        "Cómo leer el código de salida",
        "no es un fallo del sistema",
        "`browser_launch_error`",
        "solo un `NotFound` es «no existe»",
        "La ventana TOTP no se comparte entre procesos",
        "30 s",
    ):
        assert needle in f0, needle
    assert "el resultado esperado es el mismo" not in f0, "el README ya no afirma equivalencias no medidas"
    f1 = section(GUIDE_TEXT, "F1")
    assert all(word in f1 for word in ("`docker save`", "`docker load`", "apt.lock")), (
        "F1: el camino fiable hacia otra maquina es llevar la imagen construida"
    )
    f6 = section(GUIDE_TEXT, "F6")
    assert "no cuenta la espera" in f6 and "1 800 s" in f6, (
        "F6: la estimacion de `decisions` no cuenta la espera a `listo`"
    )
    assert "sigue en `firing`" in section(
        GUIDE_TEXT, "F7"
    ) or "**`FailClosedPersistente` sigue en `firing`**" in section(GUIDE_TEXT, "F7")


def test_coherence_the_eight_sections_appear_in_the_order_of_the_cli_and_no_deferred_one_is_run() -> None:
    commands = "\n".join(body for _, _, body in code_blocks(GUIDE_TEXT))
    positions = {name: commands.find(f"vectra-verification {name}") for name in kd.CLI_SECTIONS}
    assert all(at >= 0 for at in positions.values()), positions
    for name in ("prepare", "decisions", "rt5", "rt3", "rt2-setup", "rt2", "u11", "report"):
        assert re.search(rf"vectra-verification {name}\b", commands)
    order = [commands.find(f"vectra-verification {name}") for name in ("prepare", "decisions", "rt5", "rt3")]
    order += [
        commands.find("vectra-verification rt2-setup"),
        re.search(r"vectra-verification rt2(?!-)", commands).start(),
        commands.find("vectra-verification u11"),
        commands.find("vectra-verification report"),
    ]  # type: ignore[union-attr]
    assert order == sorted(order)
    for name in kd.DEFERRED_SECTIONS:
        assert f"vectra-verification {name}" not in GUIDE_TEXT, name
    assert (
        "k6" not in GUIDE_TEXT.replace("no usan `k6`", "").replace("**no** usan `k6`", "")
        or "no" in GUIDE_TEXT[GUIDE_TEXT.find("k6") - 40 : GUIDE_TEXT.find("k6")]
    )
    for deferred in ("decision-registry-rebuild", "x04-probe", "x06-probe"):
        assert deferred not in GUIDE_TEXT


def test_coherence_the_verifies_are_invoked_as_u12_t04_defined_them() -> None:
    steps = {
        name: set(
            re.findall(
                r"^\s{2}(\d+)\)",
                (kd.SYSTEM / "demos/verify" / f"{name}.sh").read_text(encoding="utf-8"),
                re.M,
            )
        )
        for name in ("journey-7-3", "journey-7-4", "rt-5", "dashboard")
    }
    used = re.findall(r"(?<![\w-])((?:journey-7-3|journey-7-4|rt-5|dashboard))\.sh (\d+)", GUIDE_TEXT)
    assert used and all(step in steps[name] for name, step in used)
    for name in steps:  # cada verify se usa en alguna fase
        assert any(u == name for u, _ in used), name
    for (
        name,
        numbers,
    ) in steps.items():  # y cada paso de cada verify (D4: `dashboard.sh 1` es Grafana, `2` las series, `3` la alerta, `4` la evidencia y `5` que `decisions` paso)
        assert {step for u, step in used if u == name} == numbers, (name, sorted(numbers))


def test_coherence_the_times_are_the_ones_of_the_demo_scripts() -> None:
    """Los tiempos de D1, D2, D3 y `decisions` son los de los guiones de U12-T04 (una sola fuente): cada cifra esta en el guion y en la guia."""
    missing = []
    for demo, phrases in TIMES.items():
        text = (kd.SYSTEM / "demos" / demo).read_text(encoding="utf-8").lower().replace("**", "")
        for phrase in phrases:
            if phrase.lower() not in text:
                missing.append(f"{demo} ya no dice «{phrase}»")
            if phrase.lower() not in GUIDE_TEXT.lower().replace("**", ""):
                missing.append(f"la guía no dice «{phrase}» de {demo}")
    assert missing == []


def test_coherence_the_scripts_name_what_exists() -> None:
    """Los selectores y las alertas de los guiones de `docs/kind/` salen del repositorio (K-20), y las alertas que `observabilidad.sh reglas` pide por omision existen."""
    alerts = set(re.findall(r"alert:\s*([A-Za-z]+)", kd.corpus()))
    for script in sorted(kd.KIND_DOCS.glob("*.sh")):
        text = script.read_text(encoding="utf-8")
        for key, value in re.findall(r"-l ([\w./-]+)=([\w.-]+)", text):
            assert kd.label_exists(key, value), f"{script.name}: {key}={value}"
    default = re.search(
        r"wanted = wanted or \[([^\]]*)\]", (kd.KIND_DOCS / "observabilidad.sh").read_text(encoding="utf-8")
    )
    assert default is not None
    assert {a.strip(" \"'") for a in default.group(1).split(",")} <= alerts


def test_the_deferred_k6_and_network_are_not_something_the_operator_runs() -> None:
    assert not re.search(r"\bk6 (run|cloud)", GUIDE_TEXT)
    assert "x04-probe" not in GUIDE_TEXT


# --- la ronda 2: lo que la ronda 1 encontró leyendo y ejecutando (F-03, F-04 y F-06) ------------------------------------------------------------------

RESTART = "Después de reiniciar la máquina"
DELIVERY = "--delivery /verification/reference-model/.out"


def restart_section(text: str) -> str:
    match = re.search(rf"^## {RESTART}.*?(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, f"falta la sección «{RESTART}»"
    return match.group(0)


def test_f03_the_partial_batch_is_not_in_the_evidence_and_the_operator_notes_the_cut_time() -> None:
    """F-03: un Ctrl-C **durante** el lote deja el envío parcial fuera del manifiesto (`rows_sent` solo trae el lote que terminó): la guía no puede decir que «la evidencia trae dos lotes»."""
    f8 = section(GUIDE_TEXT, "F8")
    first = re.search(r"> \*\*Advertencia 1[^\n]*(?:\n>[^\n]*)*", f8)
    assert first is not None
    text = first.group(0).replace("\n> ", " ")
    assert "dos lotes" not in text, "el envío parcial no queda en la evidencia: no hay «dos lotes» que ver"
    for needle in ("no queda en la evidencia", "hora del corte", "casos repetidos", "se reenvía entero"):
        assert needle in text, needle


def test_f06_two_humo_of_the_same_user_wait_30_s_in_f4_and_humo_flujo_always_carries_the_delivery() -> None:
    f4 = section(GUIDE_TEXT, "F4")
    step3 = f4[f4.index("3. **Los modelos que hay**") :]
    assert all(
        word in step3.split("\n")[0] for word in ("30 s", "ingeniero-1", "login_rejected", "bloqueo")
    ), step3[:600]
    assert f4.index("humo flujo --delivery") < f4.index("humo modelos")
    bare = [
        (number, line.strip()[:100])
        for number, line in enumerate(GUIDE_TEXT.split("\n"), 1)
        if re.search(rf"humo flujo(?! {re.escape(DELIVERY)})", line)
    ]
    assert bare == [], "`humo flujo` sin --delivery da código 2: la ruta relativa no existe en la imagen"


def test_f04_the_restart_of_the_machine_has_one_place_that_f0_f5_the_risk_and_the_symptoms_point_to() -> None:
    restart_section(GUIDE_TEXT)
    assert GUIDE_TEXT.index(f"## {RESTART}") < GUIDE_TEXT.index("## F0 ")
    f0, f5 = section(GUIDE_TEXT, "F0"), section(GUIDE_TEXT, "F5")
    symptoms = GUIDE_TEXT[GUIDE_TEXT.index("## Si algo falla") : GUIDE_TEXT.index("## Cómo dejar el clúster")]
    risk7 = next(line for line in GUIDE_TEXT.split("\n") if line.startswith("| **R-7**"))
    for where, text in (("F0", f0), ("F5", f5), ("síntomas", symptoms), ("R-7", risk7)):
        assert RESTART in text, f"{where} no remite a «{RESTART}»"
    assert "arranque.sh vault linkerd-cni" in f0 or "linkerd-cni" in f0, (
        "el diagnóstico de F0 lee linkerd-cni"
    )
    assert "sysctl fs.inotify.max_user_instances" in f0 and "tras un reinicio" in f0.replace(
        "después de un reinicio", "tras un reinicio"
    )


def test_f04_the_restart_section_has_what_was_measured_in_order_and_says_what_was_not() -> None:
    body = restart_section(GUIDE_TEXT)
    flat = " ".join(body.split())
    for needle in (
        # 1. inotify
        "sysctl fs.inotify.max_user_instances",
        "128",
        "1024",
        "`linkerd-cni`",
        "couldn't initialize inotify: too many open files",
        "`max_user_watches`",
        "1048576",
        "`/etc/sysctl.d/`",
        "arranque.sh linkerd-cni",
        # 2. los pods con malla no se recuperan solos
        "no se recuperan solos",
        "Failed to validate networking configuration",
        "linkerd-network-validator",
        "`Unknown`",
        # 3. bóveda vacía
        "could not get secret data from provider",
        "seed-vault.sh identity",
        "claves nuevas",
        # 4. MinIO
        "User already exists",
        "`minio-post-job`",
        "no cambia la clave",
        "The request signature we calculated does not match",
        "`priorityClassName: vectra-normal`",
        "reinicia los pods de Tempo",
        # 5. Grafana
        "250 MiB",
        "256 MiB",
        "`OOMKilled`",
        "512 MiB",
        "reset-admin-password",
        "seed-vault.sh grafana-token",
        "`grafana-config`",
        "deriva",
        # 6. lo no medido y lo que la lista cerrada no admite
        "no está medido",
        "lista cerrada",
    ):
        assert needle in flat, f"«{RESTART}» no dice «{needle}»"
    pods = flat[flat.index("no se recuperan solos") :]
    order = [pods.find(f"`{ns}`") for ns in ("linkerd", "vectra-data", "vectra-observability")]
    assert all(at >= 0 for at in order) and order == sorted(order), (
        "los pods se recrean en el orden medido: linkerd, vectra-data, vectra-observability"
    )
    assert "Keycloak" in flat and re.search(r"Keycloak[^.]*no está medido|no está medido[^.]*Keycloak", flat)
    assert len(re.findall(r"\*\*(?:[Oo]rden|[Óó]rdenes) del operador\*\*", body)) >= 5, (
        "cada paso con una escritura la marca como del operador"
    )


def test_f04_the_symptoms_table_has_the_rows_of_the_restart() -> None:
    symptoms = GUIDE_TEXT[GUIDE_TEXT.index("## Si algo falla") : GUIDE_TEXT.index("## Cómo dejar el clúster")]
    rows = [line for line in symptoms.split("\n") if line.startswith("| ")]
    for needles in (
        ("`Unknown`", "`ContainerCreating`", "`linkerd-cni`", "too many open files"),
        ("Tempo", "Loki", "403", "MinIO", "de cuando estaban instalados"),
        ("Grafana", "401", "`admin`"),
        ("bóveda", "se reinició", "restartCount"),
    ):
        assert any(all(n in row for n in needles) for row in rows), f"falta la fila de síntomas con {needles}"
    r7 = next(line for line in GUIDE_TEXT.split("\n") if line.startswith("| **R-7**"))
    assert "reinicia lo que lee esas claves" not in r7, (
        "no basta: Keycloak y MinIO conservan las claves viejas"
    )


# --- U12-T07: la remisión al runbook de U1 y las cuatro cifras que sobrevivieron a las mutaciones (F-02 y F-04 de la ronda 2) --------------------------

RUNBOOK = kd.VECTRA / "platform/runbooks/install.md"
BIAS_POLICY = kd.VECTRA / "bias-monitoring/chart/values-monitoring-policy.yaml"


def number(text: str) -> int:
    return int(re.sub(r"\D", "", text))


def figure_findings(text: str) -> list[str]:
    """Las cuatro cifras que la ronda 2 de U12-T06 encontró sin atar: cada una contra su origen."""
    found = []
    latency = int(rt2_latency.LIMIT.total_seconds())
    limits = [number(m) for m in re.findall(r"rt2_latency`? (?:≤|a) ([\d  ]+) s", text)]
    if len(limits) < 2 or set(limits) != {latency}:
        found.append(f"`rt2_latency` ≤ {latency} s (`rt2_latency.LIMIT`), en la guía: {limits}")
    parts = re.findall(r"(\d[\d ]*) / (\d+) \+ (\d[\d ]*) × (\d+) s \+ (\d+) s ≈ (\d+) min", text)
    want = (
        driver.DEMO_VOLUME,
        int(cli.build_parser({}).parse_args(["decisions"]).rate),
        driver.DEMO_VOLUME,
        int(guard.DECISION_SECONDS_PER_CASE),
        int(guard.MARGIN_SECONDS),
    )
    if not parts or any(tuple(number(x) for x in part[:5]) != want for part in parts):
        found.append(
            f"la fórmula de `decisions` es volumen / ritmo + volumen × s + margen = {want}; la guía: {parts}"
        )
    batch = re.findall(r"\(≈ (\d+) s a (\d+) solicitudes por segundo\)", text)
    rate = int(rt2.Rt2Params.__dataclass_fields__["rate"].default)
    if batch != [(str(rt2.BATCH_VOLUME // rate), str(rate))]:
        found.append(
            f"el lote de `rt2` son {rt2.BATCH_VOLUME} / {rate} = {rt2.BATCH_VOLUME // rate} s; la guía: {batch}"
        )
    schedule = str(yaml.safe_load(BIAS_POLICY.read_text(encoding="utf-8"))["schedule"]).split()[0]
    minutes = [int(m) for m in schedule.split(",")]
    interval = minutes[1] - minutes[0]
    cron = re.findall(r"bias cada (\d+) min, minutos ([\d, y]+?);", text)
    if cron != [(str(interval), ", ".join(map(str, minutes[:-1])) + f" y {minutes[-1]}")]:
        found.append(
            f"bias corre en los minutos {minutes} (cada {interval} min, `values-monitoring-policy.yaml`); la guía: {cron}"
        )
    return found


def all_findings(text: str) -> list[str]:
    return (
        closed_world_findings(text) + exit_code_findings(text) + time_findings(text) + figure_findings(text)
    )


def test_the_four_figures_the_round_2_review_found_loose_are_tied_to_their_origin() -> None:
    assert figure_findings(GUIDE_TEXT) == []


# Las cuatro mutaciones de la ronda 2 (revisiones/U12-T06/ronda-2.md, F-04): cada una tiene que hacer fallar una prueba.
SURVIVORS_2 = {
    "rt2_latency ≤ 900 s": lambda t: t.replace("`rt2_latency` ≤ 1 800 s", "`rt2_latency` ≤ 900 s"),
    "2 000 / 20": lambda t: t.replace("2 000 / 10 + 2 000 × 1 s", "2 000 / 20 + 2 000 × 1 s"),
    "≈ 15 s el lote": lambda t: t.replace("(≈ 150 s a 10 solicitudes", "(≈ 15 s a 10 solicitudes"),
    "bias cada 5 min": lambda t: t.replace("bias cada 15 min", "bias cada 5 min"),
}


@pytest.mark.parametrize("name", sorted(SURVIVORS_2))
def test_red_each_mutation_the_round_2_review_left_alive_now_dies(name: str) -> None:
    mutated = SURVIVORS_2[name](GUIDE_TEXT)
    assert mutated != GUIDE_TEXT, name
    assert all_findings(mutated), f"{name}: ninguna prueba la detecta"


def github_anchor(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def restart_steps(text: str) -> list[str]:
    """Los pasos numerados de «Después de reiniciar la máquina»: cada uno hasta el siguiente número (el 7 llega hasta el párrafo en negrita que cierra la sección)."""
    body = restart_section(text)
    starts = [m.start() for m in re.finditer(r"^\d+\. \*\*", body, re.M)]
    ends = starts[1:] + [len(body)]
    return [body[a:b] for a, b in zip(starts, ends, strict=True)]


# U12-T08 (F-06): cada paso de la guia cita pasos de «Vault reiniciado» (`install.md`) por numero; el numero tiene que ser el del paso del runbook que se llama como el tema. La guia pide los
# titulos de la izquierda (todos) y admite los de la derecha; el numero sale del runbook, no se copia aqui: si el runbook renumera, la guia falla.
RUNBOOK_TITLES_REQUIRED = {
    1: {"Límites de inotify"},
    2: {"Recrear los pods con malla"},
    3: {"Resiembra"},
    4: {"Claves de MinIO", "Tempo y Loki"},
    5: {"Grafana"},
    6: {"Identidad (Keycloak)", "PostgreSQL"},
}
RUNBOOK_TITLES_ALLOWED = {
    4: {"Resiembra"}
}  # el paso 4 de la guia remite al 3 del runbook («Vault reiniciado», paso 3) para la sincronizacion previa
CITATION = (
    r"pasos? (\d+)(?: y (\d+))? de \[«Vault reiniciado»\]"  # paso N de [«Vault reiniciado»](...) y pasos N y M
    r"|«Vault reiniciado», paso (\d+)"  # («Vault reiniciado», paso N)
    r"|paso (\d+) del runbook"  # (paso N del runbook: ...)
)


def runbook_step_numbers() -> dict[str, int]:
    """El numero de cada paso de «Vault reiniciado» en `install.md`, por titulo (`N. **Titulo.**`)."""
    runbook = RUNBOOK.read_text(encoding="utf-8")
    body = runbook.split("### Vault reiniciado", 1)[1].split("\n### ", 1)[0]
    return {title: int(n) for n, title in re.findall(r"^(\d+)\. \*\*(.+?)\.?\*\*", body, re.M)}


def runbook_step_number_findings(text: str) -> list[str]:
    found = []
    numbers = runbook_step_numbers()
    for guide_step, step in enumerate(restart_steps(text)[: len(RUNBOOK_TITLES_REQUIRED)], 1):
        required = RUNBOOK_TITLES_REQUIRED[guide_step]
        allowed = {title for title in required | RUNBOOK_TITLES_ALLOWED.get(guide_step, set())}
        missing_titles = sorted(title for title in allowed if title not in numbers)
        if missing_titles:
            found.append(
                f"paso {guide_step}: el runbook ya no tiene el paso «{missing_titles[0]}» en «Vault reiniciado»"
            )
            continue
        cited = {int(n) for groups in re.findall(CITATION, step) for n in groups if n}
        for n in re.findall(
            r"«Vault reiniciado», paso (\d+)", step
        ):  # la sincronizacion previa de MinIO es la resiembra
            if int(n) != numbers["Resiembra"]:
                found.append(
                    f"paso {guide_step}: «Vault reiniciado», paso {n} no es la resiembra (paso {numbers['Resiembra']})"
                )
        wanted = {numbers[title] for title in required}
        permitted = {numbers[title] for title in allowed}
        if not wanted <= cited or not cited <= permitted:
            found.append(
                f"paso {guide_step} de «{RESTART}»: cita los pasos {sorted(cited)} del runbook; «{'» y «'.join(sorted(required))}» son los {sorted(wanted)}"
                + (f" (y se admite {sorted(permitted - wanted)})" if permitted - wanted else "")
            )
    return found


def runbook_findings(text: str) -> list[str]:
    """F-02: lo que la lista cerrada no admite son órdenes del operador y están en `platform/runbooks/install.md`; cada paso de la sección del reinicio remite a su sección con un enlace que resuelve, y la guía no contradice el inotify del runbook."""
    found = []
    if re.search(r"pregunta abierta", text, re.I):
        found.append("la guía dice «pregunta abierta»: la decisión es remitir al runbook de U1")
    runbook = RUNBOOK.read_text(encoding="utf-8")
    headings = {github_anchor(h) for h in re.findall(r"^#+ (.+)$", runbook, re.M)}
    steps = restart_steps(text)
    if len(steps) != 7:
        found.append(f"«{RESTART}» tiene {len(steps)} pasos numerados, no 7")
    for number_, step in enumerate(steps, 1):
        links = re.findall(r"\]\(((?:\.\./)+platform/runbooks/install\.md)(?:#([^)\s]+))?\)", step)
        if (
            not any(anchor for _, anchor in links) and number_ != 7
        ):  # el 7 es la puerta de salida: no ejecuta nada del runbook
            found.append(
                f"paso {number_} de «{RESTART}»: no remite a una sección de `platform/runbooks/install.md` con un enlace a su ancla"
            )
        for path, anchor in links:
            if not (kd.GUIDE.parent / path).resolve() == RUNBOOK.resolve():
                found.append(f"paso {number_}: el enlace {path} no es el runbook")
            if anchor and anchor not in headings:
                found.append(f"paso {number_}: el runbook no tiene la sección #{anchor}")
    body = restart_section(text)
    for section_name in ("Vault reiniciado", "Tras reiniciar la máquina"):
        if f"«{section_name}»" not in body or f"#{github_anchor(section_name)})" not in body:
            found.append(f"«{RESTART}» no enlaza la sección «{section_name}» del runbook")
    wanted = re.search(r"max_user_instances=(\d+)", runbook)
    watches = re.search(r"max_user_watches=(\d+)", runbook)
    assert wanted is not None and watches is not None, "el runbook ya no dice el valor de inotify"
    first = steps[0] if steps else ""
    allowed = {128, 840, int(wanted.group(1)), int(watches.group(1))}
    numbers = {number(n) for n in re.findall(r"\d[\d ]{2,}", first.replace("`/etc/sysctl.d/`", ""))}
    if not numbers <= allowed or f"**{wanted.group(1)}**" not in first:
        found.append(
            f"paso 1: el valor de inotify es el del runbook (**{wanted.group(1)}**); la guía dice {sorted(numbers - allowed)}"
        )
    if "la lista de abajo" in body:
        found.append("«la lista de abajo» se refiere a la de arriba (el paso 7 está al final de la lista)")
    return found + runbook_step_number_findings(text)


def test_f02_every_step_of_the_restart_points_to_the_runbook_of_u1_and_agrees_with_its_inotify() -> None:
    assert runbook_findings(GUIDE_TEXT) == []


RUNBOOK_MUTATIONS = {
    "pregunta abierta": lambda t: t.replace("y la lista no se amplió", "y queda como pregunta abierta"),
    "inotify 512": lambda t: t.replace("el del runbook, **1024**", "el del runbook, **512**"),
    "paso 4 sin enlace": lambda t: t.replace(
        "(solo si lo reactivaste) están en los pasos 4 y 5 de [«Vault reiniciado»](../../platform/runbooks/install.md#vault-reiniciado)",
        "(solo si lo reactivaste) están en los pasos 4 y 5 del runbook",
    ),
    "ancla inexistente": lambda t: t.replace(
        "install.md#tras-reiniciar-la-máquina", "install.md#tras-reiniciar"
    ),
    "enlace a otro archivo": lambda t: t.replace(
        "../../platform/runbooks/install.md#vault-reiniciado",
        "../../platform/runbooks/otro.md#vault-reiniciado",
    ),
    "la lista de abajo": lambda t: t.replace("la lista de arriba", "la lista de abajo"),
    # U12-T08, F-06: los numeros de paso del runbook que cita la guia estan atados al titulo del paso del runbook.
    "Grafana cita el paso 5 (es Tempo y Loki)": lambda t: t.replace(
        "están en el paso 6 de [«Vault reiniciado»]", "están en el paso 5 de [«Vault reiniciado»]"
    ),
    "Keycloak cita el paso 9": lambda t: t.replace(
        "en el paso 8 de [«Vault reiniciado»]", "en el paso 9 de [«Vault reiniciado»]"
    ),
    "PostgreSQL cita el paso 6": lambda t: t.replace("(paso 7 del runbook:", "(paso 6 del runbook:"),
    "MinIO cita los pasos 3 y 4": lambda t: t.replace(
        "los pasos 4 y 5 de [«Vault reiniciado»]", "los pasos 3 y 4 de [«Vault reiniciado»]"
    ),
    "la resiembra cita el paso 2": lambda t: t.replace(
        "(`platform/kind/seed-vault.sh` y `platform/kind/seed-vault.sh identity`, F0 paso 5; paso 3 de [«Vault reiniciado»]",
        "(`platform/kind/seed-vault.sh` y `platform/kind/seed-vault.sh identity`, F0 paso 5; paso 2 de [«Vault reiniciado»]",
    ),
    "la sincronizacion de MinIO cita el paso 4": lambda t: t.replace(
        "(«Vault reiniciado», paso 3)", "(«Vault reiniciado», paso 4)"
    ),
    "inotify cita el paso 2": lambda t: t.replace(
        "el paso 1 de [«Vault reiniciado»]", "el paso 2 de [«Vault reiniciado»]"
    ),
}


@pytest.mark.parametrize("name", sorted(RUNBOOK_MUTATIONS))
def test_red_f02_each_break_of_the_runbook_reference_makes_the_guide_fail(name: str) -> None:
    mutated = RUNBOOK_MUTATIONS[name](GUIDE_TEXT)
    assert mutated != GUIDE_TEXT, name
    assert runbook_findings(mutated), f"{name}: ninguna prueba la detecta"


# --- U12-T07, punto 4: kind ya no instala Loki, Tempo ni Alloy (U01-T11) --------------------------------------------------------------------------

GITOPS = kd.VECTRA / "vectra-risk-gitops"
MINIO_KIND = kd.VECTRA / "platform/data/minio/values-kind.yaml"
HISTORICAL = (
    "ya no",
    "no se instala",
    "no instala",
    "entonces",
    "de cuando",
    "solo si los reactivaste",
    "no está en kind",
    "no están en kind",
    "no están instalados",
)


def absent_from_kind() -> set[str]:
    """Los componentes de `components.yaml` cuya Application no está en `apps/kind/` (hoy Loki, Tempo y Alloy)."""
    components = yaml.safe_load((GITOPS / "components.yaml").read_text(encoding="utf-8"))
    names = {c["name"] for c in (components["components"] if isinstance(components, dict) else components)}
    return names - {p.stem for p in (GITOPS / "apps/kind").glob("*.yaml")}


# Los verbos de `kubectl` y `argocd` con los que se le pide algo a un componente (solo en forma de orden; la prosa dice «reinicia», «sincroniza»: no son estos tokens).
ORDER_VERBS = (
    r"(?:sync|wait|get|logs|describe|port-forward|delete|rollout|exec|top|restart|status|history|diff)"
)


def asks_for(line: str, name: str) -> bool:
    """¿La línea le pide algo al componente `name` (una orden, un recurso, un selector) y no solo lo nombra?

    U12-T08 (F-02 de la revisión de U12-T07): se mira cada aparición, no la línea entera, y la exención histórica («ya no») no la salva. Es una petición si:
    el nombre es un recurso (`svc/alloy`, `deploy/tempo`, `pod/loki-0`) o un valor de selector (`name=loki`, `instance=loki`); le sigue a un verbo de orden en la misma línea
    (`sync loki`, `app wait loki`, `get app loki`, `logs ... tempo-0`, `port-forward ... loki-0`); o está dentro de un fragmento de código de varias palabras
    (una orden o un selector: `` `-n vectra-observability get pods tempo` ``); un fragmento que es solo el nombre (`` `Tempo` ``) es una mención.
    """
    word = re.escape(name)
    if re.search(rf"[/=]{word}\b", line, re.I):
        return True
    if re.search(rf"\b{ORDER_VERBS}\b(?:\s+\S+){{0,8}}?\s+[`\"']?{word}\b", line, re.I):
        return True
    spans = re.findall(r"`([^`]+)`", line)
    return any(re.search(rf"\b{word}\b", span, re.I) and len(span.split()) > 1 for span in spans)


def absent_component_findings(text: str, where: str) -> list[str]:
    """Una línea que nombra un componente que kind no instala debe decirlo (histórico, «ya no»); y nunca le pide nada al componente, lo diga o no (`asks_for`)."""
    found = []
    absent = absent_from_kind()
    for number_, line in enumerate(text.split("\n"), 1):
        for name in sorted(absent):
            if not re.search(rf"\b{re.escape(name)}\b", line, re.I):
                continue
            if asks_for(line, name):
                found.append(
                    f"{where}:{number_}: le pide algo a `{name}` (orden, recurso o selector), que no está en `apps/kind/`"
                )
            elif not any(marker in line.lower() for marker in HISTORICAL):
                found.append(f"{where}:{number_}: nombra `{name}` sin decir que kind ya no lo instala")
    return found


def minio_users_in_kind() -> int:
    return len(yaml.safe_load(MINIO_KIND.read_text(encoding="utf-8"))["users"])


def minio_findings(text: str) -> list[str]:
    users = minio_users_in_kind()
    step = next((s for s in restart_steps(text) if s.startswith("4. ")), "")
    counts = {int(n) for n in re.findall(r"los (\d+) usuarios de MinIO de kind", step)}
    return (
        []
        if counts == {users}
        else [f"el paso 4 dice {sorted(counts)} usuarios de MinIO; `values-kind.yaml` tiene {users}"]
    )


def test_ca5_the_guide_and_the_inventory_ask_for_nothing_kind_no_longer_installs() -> None:
    assert {"loki", "tempo", "alloy"} <= absent_from_kind(), "U01-T11: kind no instala Loki, Tempo ni Alloy"
    inventory = kd.INVENTORY.read_text(encoding="utf-8")
    assert absent_component_findings(GUIDE_TEXT, "paso-18-kind.md") == []
    assert absent_component_findings(inventory, "inventario.yaml") == []
    assert minio_findings(GUIDE_TEXT) == []
    for text in (GUIDE_TEXT, inventory):
        assert "name=loki" not in text


CA5_MUTATIONS = {
    "K-20 vuelve a pedir Loki": lambda t: t.replace(
        "Selectores y puertos de partida: Prometheus",
        "Selectores y puertos de partida: Loki (app.kubernetes.io/name=loki, 3100), Prometheus",
        1,
    ),
    "el síntoma de Tempo sin su aviso": lambda t: t.replace("de cuando estaban instalados", ""),
    "12 usuarios": lambda t: t.replace(
        "los 10 usuarios de MinIO de kind", "los 12 usuarios de MinIO de kind"
    ),
    # U12-T08, F-02 de la revision de U12-T07: las tres que sobrevivieron, inyectadas en la linea del paso 13 (que ya dice «kind no instala Loki»).
    "port-forward a svc/alloy": lambda t: _in_step_13(
        t, "`kubectl port-forward -n vectra-observability svc/alloy 12345`"
    ),
    "logs de deploy/tempo": lambda t: _in_step_13(t, "`kubectl logs -n vectra-observability deploy/tempo`"),
    "argocd app wait loki": lambda t: _in_step_13(t, "`argocd app wait loki --health`"),
    # y cada forma de orden con cada componente ausente, para que no dependa de una sola
    "svc/loki": lambda t: _in_step_13(t, "`kubectl get svc/loki -n vectra-observability`"),
    "deployment/tempo": lambda t: _in_step_13(t, "`kubectl rollout restart deployment/tempo`"),
    "pod/alloy": lambda t: _in_step_13(t, "`kubectl describe pod/alloy-0`"),
    "app wait alloy sin comillas": lambda t: _in_step_13(t, "Espera con argocd app wait alloy."),
    "logs de tempo sin recurso": lambda t: _in_step_13(
        t, "Mira `kubectl logs -n vectra-observability tempo-0`."
    ),
    "port-forward de loki": lambda t: _in_step_13(
        t, "Abre `kubectl port-forward -n vectra-observability loki-0 3100`."
    ),
    "selector instance": lambda t: _in_step_13(t, "Usa `-l app.kubernetes.io/instance=loki`."),
}


def _in_step_13(text: str, injected: str) -> str:
    """Pega `injected` al final de la linea del paso 13 («Observabilidad»), la que ya dice que kind no instala Loki."""
    marker = "Si K-21 falla, es R-6."
    assert text.count(marker) == 1
    return text.replace(marker, f"{marker} {injected}")


@pytest.mark.parametrize("name", sorted(CA5_MUTATIONS))
def test_red_ca5_each_break_is_found(name: str) -> None:
    mutated = CA5_MUTATIONS[name](GUIDE_TEXT)
    assert mutated != GUIDE_TEXT, name
    assert absent_component_findings(mutated, "guía") + minio_findings(mutated), name


# --- U12-T08, punto 4: la cifra de requests de kind es `BUDGET_GIB` en todos los sitios donde se dice -------------------------------------------------

KIND_PROFILE_TESTS = kd.VECTRA / "platform/tests/test_kind_profile.py"
# (archivo, cuantas veces dice la cifra de requests): la guia (R-4, la regla de la memoria y K-01), el inventario (K-01), la plantilla de prerrequisitos
# (el resultado esperado y la fila de la tabla), la tabla de `cierre-demo.md` y el README. Si alguien anade o quita una mencion, esta lista cambia con el.
REQUEST_FIGURE_SITES = {
    "docs/paso-18-kind.md": (kd.GUIDE, 3),
    "docs/kind/inventario.yaml": (kd.INVENTORY, 1),
    "evidence/kind/00-prerrequisitos.md": (kd.TEMPLATES / "00-prerrequisitos.md", 2),
    "evidence/cierre-demo.md": (kd.CLOSURE, 1),
    "README.md": (README, 1),
}


def budget_gib() -> str:
    """`BUDGET_GIB` de `platform/tests/test_kind_profile.py`, escrito como lo escribe la guia: `13,8`."""
    match = re.search(r"^BUDGET_GIB = ([0-9.]+)$", KIND_PROFILE_TESTS.read_text(encoding="utf-8"), re.M)
    assert match is not None, "`BUDGET_GIB` ya no esta en test_kind_profile.py"
    return match.group(1).replace(".", ",")


def request_figures(text: str) -> list[str]:
    """Las cifras que dicen cuanto piden los requests del perfil de kind: «suman X GiB» y «X GiB de requests»."""
    return [
        a or b
        for a, b in re.findall(
            r"requests del perfil de kind suman (\d+,\d+) GiB|(\d+,\d+) GiB de requests", text
        )
    ]


def request_figure_findings(texts: dict[str, str], budget: str) -> list[str]:
    found = []
    for where, (_, count) in REQUEST_FIGURE_SITES.items():
        figures = request_figures(texts[where])
        if len(figures) != count:
            found.append(f"{where}: dice la cifra de requests {len(figures)} veces y eran {count}")
        found += [
            f"{where}: dice {figure} GiB de requests y `BUDGET_GIB` es {budget}"
            for figure in figures
            if figure != budget
        ]
    return found


def site_texts() -> dict[str, str]:
    return {where: path.read_text(encoding="utf-8") for where, (path, _) in REQUEST_FIGURE_SITES.items()}


def test_the_request_figure_of_kind_is_budget_gib_in_every_place_it_is_said() -> None:
    assert request_figure_findings(site_texts(), budget_gib()) == []
    assert "11,8" not in "".join(site_texts().values())
    assert "línea 34" not in GUIDE_TEXT, (
        "la guia cita BUDGET_GIB por una linea que cambia: sin numero de linea"
    )


@pytest.mark.parametrize("where", sorted(REQUEST_FIGURE_SITES))
def test_red_the_old_figure_in_each_place_makes_it_fail(where: str) -> None:
    """Un sitio con la cifra vieja (uno a la vez) con `BUDGET_GIB` al dia."""
    texts = site_texts()
    texts[where] = texts[where].replace(budget_gib(), "11,8", 1)
    assert texts[where] != site_texts()[where], where
    assert request_figure_findings(texts, budget_gib()), f"{where}: ninguna prueba lo detecta"


def test_red_a_new_budget_gib_makes_every_place_fail() -> None:
    """`BUDGET_GIB` cambia y ningun sitio: falla uno por cada archivo."""
    findings = request_figure_findings(site_texts(), "15,3")
    assert {f.split(":")[0] for f in findings} == set(REQUEST_FIGURE_SITES)


# --- U12-T09: el árbol limpio de `promotion-tool`, `EVID` fijo, la máquina llega al gateway y lo que hoy era falso -------------------------------------------------------------------
# Cada prueba ata una afirmación de la guía al código que la hace cierta (leído, no medido en kind) y trae su rojo: la mutación que la devuelve a lo que decía `main`.

GITOPS_PY = kd.VECTRA / "governance/promotion_tool/vectra_promotion/gitops.py"
INSTALL_MD = kd.VECTRA / "platform/runbooks/install.md"
PROMOTION_ORDER = re.compile(
    r"promotion-tool (?:create-promotion-pr|post-activation-pr|rollback-pr|mark-active)"
)


def f0_evid_block(text: str) -> str:
    """Las líneas del bloque de F0 que fijan `EVID` (de la guarda de `$VERIF_HOME/evid` a `VERIFICATION_DIR`), sin comentarios."""
    block = next(body for _, _, body in code_blocks(text) if '"$VERIF_HOME/evid"' in body)
    lines = [line.strip() for line in block.split("\n")]
    first = next(i for i, line in enumerate(lines) if "$VERIF_HOME/evid" in line and not line.startswith("#"))
    last = next(i for i, line in enumerate(lines) if line.startswith("export VERIFICATION_DIR="))
    return "\n".join(line for line in lines[first : last + 1] if not line.startswith("#"))


def run_evid_block(text: str, tmp_path: Path, date: str, commit: str, home: str = "h") -> str:
    """Corre el bloque de `EVID` en una terminal nueva con una fecha y un commit dados (`date` y `git` de mentira) y devuelve el `EVID` que queda."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "date").write_text('#!/bin/sh\necho "$FAKE_DATE"\n', encoding="utf-8")
    (bin_dir / "git").write_text('#!/bin/sh\necho "$FAKE_COMMIT"\n', encoding="utf-8")
    for name in ("date", "git"):
        (bin_dir / name).chmod(0o755)
    script = f'export VERIF_HOME="{tmp_path / home}"; mkdir -p "$VERIF_HOME"\n{f0_evid_block(text)}\necho "$EVID"\n'
    done = subprocess.run(
        ["bash", "-c", script],
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_DATE": date, "FAKE_COMMIT": commit},
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    return done.stdout.strip().split("\n")[-1]


def evid_findings(text: str, tmp_path: Path) -> list[str]:
    found = []
    first = run_evid_block(text, tmp_path, "20261116", "aaaaaaa")
    later = run_evid_block(
        text, tmp_path, "20261117", "bbbbbbb"
    )  # una terminal nueva tras las 00:00 UTC y tras un `git pull`
    if first != later:
        found.append(f"EVID cambió entre terminales: {first} y {later}")
    if not first.endswith("20261116-aaaaaaa"):
        found.append(f"EVID no sale de la fecha y el commit de la primera vez: {first}")
    if (tmp_path / "h").resolve() not in Path(first).resolve().parents:
        found.append(f"EVID no vive en $VERIF_HOME (fuera del repositorio): {first}")
    return found


def dirty_tree_findings(text: str) -> list[str]:
    """Lo que ensucia el árbol en que corre `promotion-tool`: la evidencia o un parche dentro del repositorio, y una orden de `promotion-tool` sin `git pull` antes."""
    found = []
    source = GITOPS_PY.read_text(encoding="utf-8")
    if "working_tree_dirty" not in source or '"git", "status", "--porcelain"' not in source:
        found.append("`gitops.py` ya no exige el árbol limpio: la guía explica un motivo que no existe")
    if 'self._run(["git", "switch", "-c", branch, self.base])' not in source:
        found.append(
            "`gitops.py` ya no crea la rama desde el `main` local: el `git pull` de la guía ya no tiene motivo"
        )
    for number, _, body in code_blocks(text):
        for line in body.split("\n"):
            if re.search(r"EVID=\"?\$PWD|EVID=\"?\./|EVID=\"?system-verification", line):
                found.append(f"{number}: EVID dentro del repositorio: {line.strip()[:80]}")
            for target in re.findall(r">\s*([^\s&|)>]+\.patch)", line):
                if not target.startswith(("$", '"$', "/")):
                    found.append(f"{number}: un parche escrito en el directorio de trabajo: {target}")
    for number, line in enumerate(text.split("\n"), 1):
        if re.match(r"^\d+\. ", line) and PROMOTION_ORDER.search(line) and "pull --ff-only" not in line:
            found.append(f"{number}: una orden de `promotion-tool` sin `git pull --ff-only` antes")
    for needle in (
        'export PROMO="$VERIF_HOME/promocion"',
        "git clone",
        'git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only',
        "ingeniero-2",
    ):
        if needle not in text:
            found.append(f"falta «{needle}»")
    return found


def test_t09_the_guide_keeps_promotion_tool_in_a_clean_up_to_date_clone_and_the_evidence_out_of_the_tree() -> (
    None
):
    assert dirty_tree_findings(GUIDE_TEXT) == []


T09_DIRTY_MUTATIONS = {
    "EVID dentro del repositorio": lambda t: t.replace(
        "printf '%s\\n' \"$VERIF_HOME/evidence/", "printf '%s\\n' \"$PWD/system-verification/evidence/"
    ).replace('export EVID="$(cat "$VERIF_HOME/evid")"', 'export EVID="$PWD/system-verification/evidence/x"'),
    "proxy.patch en el directorio de trabajo": lambda t: t.replace(
        '> "$VERIF_HOME/proxy.patch"', "> proxy.patch"
    ),
    "promotion-tool sin pull": lambda t: t.replace(
        '(con `git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only` antes, como en el paso 3)',
        "(como en el paso 3)",
    ).replace("la invocación completa está en", "la invocación completa está en"),
    "sin el clon de promoción": lambda t: t.replace('export PROMO="$VERIF_HOME/promocion"', "export PROMO=."),
}


@pytest.mark.parametrize("name", sorted(T09_DIRTY_MUTATIONS))
def test_t09_red_each_return_to_the_dirty_tree_is_found(name: str) -> None:
    mutated = T09_DIRTY_MUTATIONS[name](GUIDE_TEXT)
    assert mutated != GUIDE_TEXT, name
    assert dirty_tree_findings(mutated), f"{name}: ninguna prueba lo detecta"


def test_t09_evid_is_fixed_once_and_every_new_terminal_reads_it(tmp_path: Path) -> None:
    assert evid_findings(GUIDE_TEXT, tmp_path) == []


def test_t09_red_evid_computed_again_in_each_terminal_points_to_another_directory(tmp_path: Path) -> None:
    """Rojo: el `EVID` de `main` (se calcula con `date -u` y `git rev-parse` en cada terminal) cambia tras las 00:00 UTC o tras un `git pull`."""
    mutated = GUIDE_TEXT.replace('[ -s "$VERIF_HOME/evid" ] || printf', "printf")
    assert mutated != GUIDE_TEXT
    assert any("cambió entre terminales" in f for f in evid_findings(mutated, tmp_path))


def test_t09_the_machine_reaches_the_gateway_vv_carries_add_host_and_f0_and_f5_run_the_script() -> None:
    readme = README.read_text(encoding="utf-8")
    for where, text in (("guía", GUIDE_TEXT), ("README", readme)):
        assert re.search(r'--add-host "vectra\.localtest\.me:\$\{GATEWAY_ADDRESS:\?', text), (
            f"{where}: `vv` no lleva --add-host con la dirección del gateway"
        )
        assert "llega al gateway de kind" not in text, (
            f"{where}: dice que `vectra.localtest.me` llega al gateway de kind"
        )
    host = guard.KIND.host
    assert host == "vectra.localtest.me", (
        "`guard.KIND.host` cambió: --add-host y /etc/hosts nombran otro host"
    )
    assert "gateway-address.sh" in section(GUIDE_TEXT, "F0") and "gateway-address.sh" in section(
        GUIDE_TEXT, "F5"
    )
    assert "/etc/hosts" in section(GUIDE_TEXT, "F0") and "/etc/hosts" in readme
    operators = (kd.VECTRA / "platform/operators/envoy-gateway.yaml").read_text(encoding="utf-8")
    assert "type: GatewayNamespace" in operators, "el Service ya no se nombra como el Gateway: `api-gateway`"
    for where, text in (("guía", GUIDE_TEXT), ("README", readme)):
        assert "get svc api-gateway -n vectra-edge" in text, (
            f"{where}: la dirección se lee del Service `api-gateway`"
        )
        assert "-l app.kubernetes.io/name=api-gateway" not in text, (
            f"{where}: lee el Service por etiqueta (F-04)"
        )
    assert (kd.VECTRA / "platform/kind/gateway-address.sh").is_file(), (
        "U01-T16 está en `main`: sin excepción PENDING"
    )
    assert "pending_script" not in globals() and "PENDING" not in globals(), (
        "la excepción de U01-T16 ya no existe"
    )


def test_t09_vv_refuses_to_start_without_the_gateway_address(tmp_path: Path) -> None:
    block = vv_block(GUIDE_TEXT)
    functions = block[block.index("vv() {") :]
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "docker").write_text('#!/bin/sh\necho ran > "$DOCKER_OUT"\n', encoding="utf-8")
    (fake / "docker").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake}:{os.environ['PATH']}",
        "DOCKER_OUT": str(tmp_path / "ran"),
        "VERIF_HOME": "/h",
        "EVID": "/e",
        "VERIFICATION_IMAGE": "i",
    }
    env.pop("GATEWAY_ADDRESS", None)
    done = subprocess.run(
        ["bash", "-c", f"{functions}\nvv report"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert done.returncode != 0 and not (tmp_path / "ran").exists(), (
        "`vv` arrancó el contenedor sin la dirección del gateway"
    )
    assert "gateway-address.sh" in done.stderr


def test_t09_the_add_host_value_is_the_address_the_operator_exports(tmp_path: Path) -> None:
    block = vv_block(GUIDE_TEXT)
    functions = block[block.index("vv() {") :]
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "docker").write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$DOCKER_OUT"\n', encoding="utf-8")
    (fake / "docker").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake}:{os.environ['PATH']}",
        "DOCKER_OUT": str(tmp_path / "argv"),
        "VERIF_HOME": "/h",
        "EVID": "/e",
        "VERIFICATION_IMAGE": "i",
        "GATEWAY_ADDRESS": "172.18.0.2",
    }
    done = subprocess.run(
        ["bash", "-c", f"{functions}\nvv report"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert done.returncode == 0, done.stderr
    argv = (tmp_path / "argv").read_text(encoding="utf-8").split("\n")
    assert argv[argv.index("--add-host") + 1] == "vectra.localtest.me:172.18.0.2"


FALSE_STATEMENTS = (
    "Nada de esto se ha ejecutado aún en kind",
    "todos los charts llevan el digest de ejemplo",
    "llega al gateway de kind",
    "install.md` pide 512",
    "No sobrevive a un reinicio**: vuelve a aplicarlo",
    "(hoy son de ejemplo: ImagePullBackOff)",
    "el runbook no pide reaplicar el límite",
)


def false_statement_findings(guide: str, readme: str, inventory: str) -> list[str]:
    """Las afirmaciones que el código o el repositorio desmienten hoy (U12-T09, punto 14), cada una contra su origen."""
    found = [f"dice «{s}»" for s in FALSE_STATEMENTS if s in guide or s in readme or s in inventory]
    leftovers = [
        p
        for p in (kd.VECTRA / "vectra-risk-gitops/values/kind").rglob("*.yaml")
        if "sha256:0000" in p.read_text(encoding="utf-8")
    ]
    if leftovers:
        found.append(f"los values de kind aún traen un digest de ejemplo: {leftovers[0].name}")
    runbook = INSTALL_MD.read_text(encoding="utf-8")
    if "max_user_instances=1024" not in runbook or "/etc/sysctl.d/" not in runbook:
        found.append("`install.md` ya no pide 1024 persistente: la guía dice lo contrario de lo que cita")
    if "pide **1024**" not in guide:
        found.append("la guía no dice que `install.md` pide 1024")
    for number, line in enumerate(guide.split("\n"), 1):
        for match in re.finditer(r"install\.md`?,? (?:línea|líneas) [\d, ay]+", line):
            found.append(f"{number}: cita `install.md` por número de línea: {match.group(0)}")
    if (
        "wave: 6" not in (kd.VECTRA / "vectra-risk-gitops/components.yaml").read_text(encoding="utf-8")
        or "líneas 63 a 96" in guide
    ):
        found.append("la cita de `components.yaml` por números de línea")
    for needle in ("Tras suspender la máquina",):
        if needle not in guide or needle not in runbook:
            found.append(f"«{needle}» no está en la guía y en `install.md`")
    symptoms = guide[guide.index("## Si algo falla") : guide.index("## Cómo dejar el clúster")]
    rows = [line for line in symptoms.split("\n") if line.startswith("| ")]
    for needles in (
        ("JWKS", "`use: enc`", "U00-T05"),
        ("≈ 90 s", "PortSkipped"),
        ("calico", "Unauthorized"),
        ("`sync keycloak`", "`Failed`", "segundo sync"),
        ("certificate expired", "Tras suspender la máquina"),
        ("127.0.0.1:443", "gateway-address.sh"),
        ("decisions_lectura_agotada",),
    ):
        if not any(all(n in row for n in needles) for row in rows):
            found.append(f"falta la fila de síntomas con {needles}")
    return found


def test_t09_the_guide_says_nothing_the_repository_contradicts() -> None:
    inventory = kd.INVENTORY.read_text(encoding="utf-8")
    assert false_statement_findings(GUIDE_TEXT, README.read_text(encoding="utf-8"), inventory) == []


T09_FALSE_MUTATIONS = {
    "Nada de esto se ha ejecutado": lambda t: t.replace(
        "Esta guía solo se ha ejecutado **en parte** en kind", "Nada de esto se ha ejecutado aún en kind"
    ),
    "digest de ejemplo en R-2": lambda t: t.replace(
        "una imagen sin publicar o un digest de los values que no es el que se publicó",
        "todos los charts llevan el digest de ejemplo",
    ),
    "inotify 512": lambda t: t.replace("`install.md` pide **1024**", "`install.md` pide 512"),
    "install.md línea 150": lambda t: t.replace(
        "`platform/runbooks/install.md`, «Vault reiniciado» |",
        "`platform/runbooks/install.md`, líneas 150 a 163 |",
        1,
    ),
    "sin la fila del certificado": lambda t: t.replace("certificate expired", "certificado vencido"),
}


@pytest.mark.parametrize("name", sorted(T09_FALSE_MUTATIONS))
def test_t09_red_each_false_statement_that_comes_back_is_found(name: str) -> None:
    mutated = T09_FALSE_MUTATIONS[name](GUIDE_TEXT)
    assert mutated != GUIDE_TEXT, name
    assert false_statement_findings(
        mutated, README.read_text(encoding="utf-8"), kd.INVENTORY.read_text(encoding="utf-8")
    ), name


def test_t09_rt3_c_is_uploaded_to_the_model_store_and_the_inventory_says_so() -> None:
    from vectra_verification.scenarios import rt3

    assert "RT3-c" in rt3.REGISTRY_CASES, "`rt3` ya no exige RT3-c"
    owner = (kd.VECTRA / "model-serving/docs/paso-11-kind.md").read_text(encoding="utf-8")
    assert "for case in RT3-a RT3-b RT3-c RT3-d;" in owner and "adversarial/rt3/RT3-c/" in owner
    k24 = next(e for e in kd.entries() if e["id"] == "K-24")
    assert "RT3-c" in " ".join([k24["que"], *k24["comprobacion"]])
    assert "RT3-a, c y d en el model-store (K-24)" in section(GUIDE_TEXT, "F7")


def test_t09_the_windows_of_time_say_what_the_code_says() -> None:
    """D4 vive en el día D + 1 UTC, el proxy no se recongela el mismo día UTC y el cron de bias evalúa también el modelo de referencia."""
    compute = (kd.VECTRA / "product-metrics/src/vectra_product/compute.py").read_text(encoding="utf-8")
    assert 'periods[PeriodKey("day")] = _period(*over(yesterday, yesterday))' in compute, (
        "`period=day` ya no es el «ayer»"
    )
    assert 'period="day"' in (kd.SYSTEM / "src/vectra_verification/scenarios/u11.py").read_text(
        encoding="utf-8"
    )
    window = (kd.VECTRA / "bias-monitoring/src/vectra_bias/window.py").read_text(encoding="utf-8")
    assert (
        "reactivated_at.astimezone(UTC).date() + timedelta(days=1)" in window
        and "v.last_day >= today - timedelta(days=1)" in window
    )
    f9, f6, calendar = (
        section(GUIDE_TEXT, "F9"),
        section(GUIDE_TEXT, "F6"),
        GUIDE_TEXT[: GUIDE_TEXT.index("## Documentos dueños")],
    )
    assert "hasta las 00:00 UTC de D + 2" in f9 and "no está medido en kind" in f9
    assert (
        "no se recongela el mismo día UTC" in calendar
        and "otro día UTC" in calendar
        and "otro paquete" in calendar
    )
    assert "`humo modelos`" in f6 and "evaluated_versions" in f6 and "sigue `activo`" in f6
    for where in (
        (kd.SYSTEM / "demos/dashboard.md").read_text(encoding="utf-8"),
        (kd.INVENTORY).read_text(encoding="utf-8"),
    ):
        assert "00:00 UTC de D + 2" in where


def test_t09_repeating_d3_and_d2_after_a_partial_failure_has_commands_for_each_case() -> None:
    manifest = (kd.SYSTEM / "src/vectra_verification/manifest.py").read_text(encoding="utf-8")
    chart = (kd.VECTRA / "case-management/chart/templates/rt5-demo-job.yaml").read_text(encoding="utf-8")
    values = (kd.VECTRA / "governance/promotion_tool/vectra_promotion/values.py").read_text(encoding="utf-8")
    fsm = (kd.VECTRA / "governance/src/vectra_governance/model_fsm.py").read_text(encoding="utf-8")
    assert (
        "values_already_have_runid" in manifest
        and "backoffLimit: 0" in chart
        and "ttlSecondsAfterFinished" in chart
    )
    assert (
        '"already_declared"' in values
        and "active_version_frozen" in fsm
        and 'f"promotion/{kind}-{isvc}-{self.env}"' in GITOPS_PY.read_text(encoding="utf-8")
    )
    d3 = (kd.SYSTEM / "demos/prs/rt5-run-id/README.md").read_text(encoding="utf-8")
    d2 = (kd.SYSTEM / "demos/journey-7-4.md").read_text(encoding="utf-8")
    f5, f8 = section(GUIDE_TEXT, "F5"), section(GUIDE_TEXT, "F8")
    for where, text, needles in (
        ("F5", f5, ("values_already_have_runid", "apply -R", "con prune", "rt5 --redo")),
        (
            "rt5-run-id/README.md",
            d3,
            ("values_already_have_runid", "apply -R", "prune", "rt5 --redo", "Repetir D3"),
        ),
        ("F8", f8, ("already_declared", "active_version_frozen", "nombre fijo", "reactivar")),
        ("journey-7-4.md", d2, ("already_declared", "active_version_frozen", "nombre fijo", "reactivar")),
    ):
        for needle in needles:
            assert needle in text, f"{where} no dice «{needle}»"


def test_t09_the_users_are_split_between_the_tool_the_promotion_tool_and_the_presenter() -> None:
    f3 = section(GUIDE_TEXT, "F3")
    table = re.search(r"\| Quién \| Usuario \| Dónde \|\n\s*\|---\|---\|---\|\n((?:\s*\|.*\n){3})", f3)
    assert table is not None, "F3 no trae el reparto de usuarios"
    owners = []
    for row in table.group(1).strip().split("\n"):
        cell = row.split("|")[2]
        if (
            not row.split("|")[1].strip().startswith("La herramienta")
        ):  # lo que va entre paréntesis dice de quién es el otro usuario: no es el dueño
            cell = re.sub(r"\([^)]*\)", "", cell)
        owners.append(set(re.findall(r"`((?:analista|ingeniero|cro|cumplimiento)-\d)`", cell)))
    tool, promotion, presenter = owners
    assert tool & promotion == set() and tool & presenter == set() and promotion & presenter == set(), owners
    assert promotion == {"ingeniero-2"} and "analista-2" in tool and presenter == {"cro-2", "cumplimiento-2"}
    assert (owners[0] | owners[1] | owners[2]) <= set(kd.realm_users()), (
        "un usuario del reparto no está en el realm de kind"
    )
    assert "Una sola pestaña por usuario" in f3 and "bloqueo por fuerza bruta" in f3
    assert "ANALYSTS" in f3 and 'ANALYSTS: Final = ("analista-1", "analista-2")' in (
        kd.SYSTEM / "src/vectra_verification/driver.py"
    ).read_text(encoding="utf-8")


# --- U12-T09, ronda 2 (F-01, F-03, F-05, F-06, M-01) -------------------------------------------------------------------------------------------------------


def verification_pr_findings(text: str) -> list[str]:
    """F-01: las plantillas se llenan fuera de los dos árboles y F10 las lleva al PR de verificación, con la evidencia, sin ensuciar el clon de `promotion-tool`."""
    found = []
    f0, f10 = section(text, "F0"), section(text, "F10")
    for needle in ('"$VERIF_HOME/plantillas"', "se llenan en esa copia", "evidence/kind", "cierre-demo.md"):
        if needle not in f0:
            found.append(f"F0 paso 11 no dice «{needle}»")
    step4 = f10[f10.index("4. **El PR de verificación**") :]
    for needle in (
        'cp -r "$EVID"', 'cp -r "$VERIF_HOME/plantillas/kind/."', 'cp "$VERIF_HOME/plantillas/cierre-demo.md"',
        "system-verification-code-generation-plan.md", "`[x]`",
    ):  # fmt: skip
        if needle not in step4:
            found.append(f"F10 paso 4 no dice «{needle}»")
    if "evidence/<fecha>-<commit>/verification-report.md" in text:
        found.append(
            "F10 apunta al informe por una ruta del repositorio, y la evidencia está en `$EVID` hasta el paso 4"
        )
    if "`$EVID/verification-report.md`" not in f10:
        found.append("F10 no lee el informe de `$EVID`")
    return found


def test_r2_the_verification_pr_carries_the_templates_and_the_evidence_without_dirtying_the_clone() -> None:
    assert verification_pr_findings(GUIDE_TEXT) == []


R2_MUTATIONS = {
    "sin copiar las plantillas": lambda t: t.replace('   cp -r "$VERIF_HOME/plantillas/kind/." ', "   # ", 1),
    "la ruta vieja del informe": lambda t: t.replace("`$EVID/verification-report.md`", "`system-verification/evidence/<fecha>-<commit>/verification-report.md`"),
    "plantillas llenas en el clon": lambda t: t.replace("se llenan en esa copia", "se llenan en el clon"),
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(R2_MUTATIONS))
def test_r2_red_the_verification_pr_without_the_templates_is_found(name: str) -> None:
    mutated = R2_MUTATIONS[name](GUIDE_TEXT)
    assert mutated != GUIDE_TEXT, name
    assert verification_pr_findings(mutated), name


def test_r2_a_second_verification_has_written_commands_and_says_which_commit_names_the_directory() -> None:
    f0 = section(GUIDE_TEXT, "F0")
    for needle in (
        'mv "$VERIF_HOME/evid" "$VERIF_HOME/evid.<fecha>"',
        "git pull --ff-only",
        "es solo una etiqueta",
        "`prepare --commit`",
    ):
        assert needle in f0, needle
    assert "guarda el `evid` anterior" in section(GUIDE_TEXT, "F5")


def test_r2_deleting_a_remote_branch_is_a_named_operator_order_not_a_silent_step() -> None:
    for where, text in (
        ("F8", section(GUIDE_TEXT, "F8")),
        ("journey-7-4.md", (kd.SYSTEM / "demos/journey-7-4.md").read_text(encoding="utf-8")),
    ):
        assert "local, y remota" not in text and "local y remota" not in text, where
        assert (
            "escritura en GitHub" in text
            and "orden del operador" in text
            and "git push origin --delete <rama>" in text
        ), where


def test_r2_scenarios_md_lists_every_sim_normal_code() -> None:
    doc = (kd.VECTRA / "aidlc-docs/construction/system-verification/code/scenarios.md").read_text(
        encoding="utf-8"
    )
    common = (kd.SYSTEM / "src/vectra_verification/scenarios/common.py").read_text(encoding="utf-8")
    assert 'f"{prefix}_{error.code}"' in common and "sim_normal_lectura_agotada" in doc


def test_r2_the_restart_section_and_r7_say_what_seed_vault_and_the_runbook_say_today() -> None:
    runbook = INSTALL_MD.read_text(encoding="utf-8")
    seed = (kd.VECTRA / "platform/kind/seed-vault.sh").read_text(encoding="utf-8")
    assert (
        "recupera antes de generar" in runbook
        and "--restart=always" in runbook
        and "nada que realinear" in runbook.lower()
    )
    assert "recover" in seed.lower() or "recuper" in seed.lower()
    body = restart_section(GUIDE_TEXT)
    flat = " ".join(body.split())
    for needle in (
        "`--restart=always`", "recupera antes de generar", "seis rutas", "nada que realinear", "ejecutores falsos",
        "no se ha corrido aún en el clúster", "gateway-address.sh", "`envoy-ratelimit`", "juntos y enseguida",
    ):  # fmt: skip
        assert needle in flat, needle
    assert "se lanza con `--rm` y no sobrevive al reinicio: sin él" not in flat
    r7 = next(line for line in GUIDE_TEXT.split("\n") if line.startswith("| **R-7**"))
    assert "recuperan de los `Secret` antes de generar" in r7 and "solo lo que el informe diga generado" in r7
    assert "pon al día lo que guardaba las claves viejas" not in r7
