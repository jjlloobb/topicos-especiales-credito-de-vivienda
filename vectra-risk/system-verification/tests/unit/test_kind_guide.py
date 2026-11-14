"""La guia del operador `docs/paso-18-kind.md` (U12-T06, CA-1, CA-2 y CA-8).

Tres cosas: la **estructura** (las doce fases en orden, con prerrequisitos, pasos, plantilla, duracion y puerta, y la primera pagina con «Quien hace que», los riesgos, los sintomas y el estado final),
el **mundo cerrado** (la guia solo nombra lo que existe en el repositorio: Applications, namespaces, secciones y opciones de la CLI, guiones, PR preparados, rutas, lineas citadas, selectores, series, alertas,
usuarios y rutas de la consola; y respeta el orden de F2 y el de las secciones) y la **coherencia** con el README de la imagen, con los guiones y con los guiones de las demos (una sola verdad).
La prueba de mundo cerrado **no** demuestra que la guia funcione en kind: demuestra que no nombra nada inventado.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import kind_docs as kd
import pytest
from vectra_verification import cli

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
    "vectra-verification-operator", "vectra-producto-panel", "vectra-console", "vectra-e2e-keys", "vectra-risk-gitops", "vectra-payload",
}  # fmt: skip
GENERATED = (
    "reference-model/.out",
    "system-verification/evidence",
    "evidence/",
    "platform/.tools",
    "platform/.charts",
)
KUBE_PREFIXES = ("deploy/", "job/", "pod/", "svc/", "sa/", "statefulset/")
NOT_REPO_PATHS = {"identity/synthetic-users", "grafana/admin", "secret/data"}
# Lo que escribe U12-T05 y todavia no esta en esta rama: se acepta solo mientras no exista y la guia lleve la marca POR CONFIRMAR.
PENDING_T05 = {"system-verification/README.md"}
# Series que no emite este repositorio: las del propio Prometheus y las de cAdvisor (las nombra la guia para medir la retencion y la memoria).
EXTERNAL_SERIES = {"prometheus_tsdb_lowest_timestamp_seconds", "container_memory_working_set_bytes"}
TIMES = {
    "journey-7-3.md": ("≥ 19,3 min", "≈ 21 min"),
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
        for pr in re.findall(r"demos/prs/([\w-]+)", line):
            if not (kd.SYSTEM / "demos/prs" / pr).is_dir():
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
                if span in PENDING_T05 and MARKER in text:
                    continue  # lo escribe U12-T05; la guia lo marca POR CONFIRMAR
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
            if value not in corpus or key not in corpus:
                found.append(f"{where}: el selector {key}={value} no está en ningún chart ni cliente")
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
    for needle in ("14 GiB", "16 GiB", "11,8 GiB", "v0.33.0", "v4.3.0", "OOMKilled", "máquina limpia"):
        assert needle in GUIDE_TEXT, needle


# --- la coherencia -----------------------------------------------------------------------------------------------------------------------------------


def docker_run_flags(text: str) -> set[str]:
    """Las opciones (`--bandera`) del primer bloque con `docker run` o con la lista de opciones del `docker run`."""
    for _, _, body in code_blocks(text):
        if "docker run" in body or "VERIF_RUN=(" in body:
            return set(re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", body))
    return set()


def test_coherence_the_docker_run_is_the_one_of_the_readme_or_says_it_is_pending() -> None:
    """La orden `docker run` de la guia es la del README de la imagen (U12-T05). Mientras el README no exista, la guia lo dice con una marca que el orquestador concilia; cuando exista, la marca se retira y
    cada opcion del `docker run` del README esta en la de la guia."""
    if readme_exists():
        assert MARKER not in GUIDE_TEXT, (
            "el README ya existe: retira las marcas POR CONFIRMAR y concilia la orden docker run"
        )
        missing = docker_run_flags(README.read_text(encoding="utf-8")) - docker_run_flags(GUIDE_TEXT)
        assert missing == set(), f"la orden docker run de la guía no trae {sorted(missing)} del README"
    else:
        assert GUIDE_TEXT.count(MARKER) >= 3
        flags = docker_run_flags(GUIDE_TEXT)
        for flag in ("--read-only", "--tmpfs", "--network", "--user", "--security-opt", "--memory"):
            assert flag in flags, flag
        assert "-e VAULT_TOKEN" in GUIDE_TEXT and "VAULT_TOKEN=" not in GUIDE_TEXT.replace(
            "export VAULT_TOKEN=root", ""
        ), "el token de la bóveda va como variable, no como valor ni archivo"
        assert "no-sandbox" not in GUIDE_TEXT.replace("nunca desactiva el sandbox", "")


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
    used = re.findall(r"demos/verify/((?:journey-7-3|journey-7-4|rt-5|dashboard))\.sh (\d+)", GUIDE_TEXT)
    assert used and all(step in steps[name] for name, step in used)
    for name in steps:  # cada verify se usa en alguna fase
        assert any(u == name for u, _ in used), name


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
    corpus, alerts = kd.corpus(), set(re.findall(r"alert:\s*([A-Za-z]+)", kd.corpus()))
    for script in sorted(kd.KIND_DOCS.glob("*.sh")):
        text = script.read_text(encoding="utf-8")
        for key, value in re.findall(r"-l ([\w./-]+)=([\w.-]+)", text):
            assert value in corpus and key in corpus, f"{script.name}: {key}={value}"
    default = re.search(
        r"wanted = wanted or \[([^\]]*)\]", (kd.KIND_DOCS / "observabilidad.sh").read_text(encoding="utf-8")
    )
    assert default is not None
    assert {a.strip(" \"'") for a in default.group(1).split(",")} <= alerts


def test_the_deferred_k6_and_network_are_not_something_the_operator_runs() -> None:
    assert not re.search(r"\bk6 (run|cloud)", GUIDE_TEXT)
    assert "x04-probe" not in GUIDE_TEXT
