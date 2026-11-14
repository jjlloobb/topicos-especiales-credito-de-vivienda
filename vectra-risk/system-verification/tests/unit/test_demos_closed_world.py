"""Mundo cerrado de las demos (U12-T04, CA-2 y CA-5; leccion de la enmienda §8): cada recurso, namespace, ruta, usuario, dashboard, alerta, serie, clave de values y seccion de la CLI que un guion, un `verify` o un PR nombra
**existe** en el repositorio. La prueba **recorre `demos/`** y extrae los nombres; nada esta escrito a mano como «permitido». Si se borra la fuente, el guion falla. `check(<carpeta>)` devuelve las violaciones con
archivo y linea: las mutaciones de abajo la corren sobre una copia de `demos/`.

Convenciones de redaccion que la prueba lee (estan en `cli.md`): una ruta de la SPA se escribe `ruta /x` (en una sola pareja de comillas invertidas); una alerta, `alerta X`; una Application, `Application x`; un dashboard, `dashboard X` con `uid` y `carpeta`; un panel,
`panel X`; una orden de la CLI, `vectra-verification <seccion> --opcion`; un `verify`, `nombre.sh N`.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import fake_kubectl_bin
import pytest
import yaml
from vectra_verification import cli

SYSTEM = Path(__file__).resolve().parents[2]
VECTRA = SYSTEM.parent
DEMOS = SYSTEM / "demos"
GENERATED_PREFIXES = ("reference-model/.out", "evidence", "<", "{")


class Violation(NamedTuple):
    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.message}"


# --- las fuentes ------------------------------------------------------------------------------------------------------------------------------------


def _read(path: str) -> str:
    return (VECTRA / path).read_text(encoding="utf-8")


def routes() -> dict[str, tuple[bool, set[str]]]:
    found = {}
    for match in re.finditer(
        r'path: "([^"]+)", operation: "[^"]*", roles: \[([^\]]*)\].*?entry: (true|false)',
        _read("console/spa/src/views/shared/routes.ts"),
    ):
        found[match.group(1)] = (match.group(3) == "true", set(re.findall(r'"([a-z_]+)"', match.group(2))))
    return found


def realm_users() -> dict[str, set[str]]:
    realm = yaml.safe_load(_read("identity-edge/keycloak/realm/realm.kind.yaml").replace("$(env:", "(env:"))
    return {u["username"]: set(u.get("realmRoles", [])) for u in realm["users"]}


def namespaces() -> set[str]:
    flows = yaml.safe_load(_read("platform/network/flows.yaml"))
    return set(flows["meshed_namespaces"]) | set(flows["system_namespaces"])


def applications() -> set[str]:
    return set(re.findall(r"\{ name: ([a-z0-9-]+),", _read("vectra-risk-gitops/components.yaml")))


def dashboards() -> dict[str, dict[str, object]]:
    found = {}
    for path in (
        "product-metrics/observability/dashboards/product.json",
        "platform/observability/dashboards/operacion.json",
    ):
        document = json.loads(_read(path))
        panels = [p["title"] for p in document["panels"]]
        found[document["title"]] = {"uid": document["uid"], "panels": set(panels)}
    return found


def folders() -> set[str]:
    return {
        f["title"]
        for f in yaml.safe_load(_read("platform/observability/grafana/folder-permissions.yaml"))["folders"]
    }


def folder_uids() -> set[str]:
    return {
        f["uid"]
        for f in yaml.safe_load(_read("platform/observability/grafana/folder-permissions.yaml"))["folders"]
    }


_SKIP = {
    ".venv",
    "node_modules",
    ".tools",
    ".charts",
    ".git",
    "system-verification",
    "tareas",
    "aidlc-docs",
    "bitacoras",
    "revisiones",
    "entradas",
    "__pycache__",
    "loop",
}
_corpus: list[str] = []


def corpus() -> str:
    """El texto de los archivos de reglas, metricas, dashboards y codigo del repositorio (no de U12 ni de la documentacion)."""
    if not _corpus:
        chunks = []
        for path in VECTRA.rglob("*"):
            relative = path.relative_to(VECTRA)
            if (
                path.is_file()
                and path.suffix in {".py", ".yaml", ".yml", ".json", ".rego", ".ts"}
                and not _SKIP & set(relative.parts)
            ):
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        _corpus.append("\n".join(chunks))
    return _corpus[0]


def alert_names() -> set[str]:
    return set(re.findall(r"alert:\s*([A-Za-z]+)", corpus()))


def job_prefixes() -> set[str]:
    """Los nombres de Job de prueba que el chart de case-management declara: `printf "rt5-demo-%s" $runId`."""
    return set(
        re.findall(r'printf "(rt5-[a-z]+)-%s"', _read("case-management/chart/templates/rt5-demo-job.yaml"))
    )


def promotion_commands() -> set[str]:
    return set(
        re.findall(
            r'sub\.add_parser\("([a-z-]+)"\)', _read("governance/promotion_tool/vectra_promotion/cli.py")
        )
    )


def values_keys() -> set[str]:
    """Las claves de values que el repositorio declara: las referenciadas como `.Values.a.b` y las de primer nivel de los values y de `flows.yaml`."""
    keys = {m.replace(".Values.", "") for m in re.findall(r"\.Values\.[A-Za-z0-9_.]+", corpus())}
    for path in list((VECTRA / "vectra-risk-gitops").rglob("*.yaml")) + [
        VECTRA / "platform/network/flows.yaml"
    ]:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(document, dict):
            keys |= {str(k) for k in document}
    return keys


def cli_options() -> dict[str, set[str]]:
    parser = cli.build_parser({})
    action = next(a for a in parser._actions if a.dest == "section")  # noqa: SLF001
    return {
        name: {opt for opt in sub._option_string_actions if opt.startswith("--")}
        for name, sub in action.choices.items()
    }  # noqa: SLF001


def verify_steps(script: Path) -> set[str]:
    return set(re.findall(r"^\s{2}(\d+)\)", script.read_text(encoding="utf-8"), re.M))


# --- la comprobacion ---------------------------------------------------------------------------------------------------------------------------------

USER = re.compile(r"\b((?:analista|ingeniero|cro|cumplimiento|operacion)-\d+)\b")
NAMESPACE = re.compile(r"(?<![\w/.-])(vectra-[a-z0-9]+(?:-[a-z0-9]+)*)(?![\w/.-])")
NOT_NAMESPACES = {"vectra-verification", "vectra-risk", "vectra-risk-gitops"}
STEP_ROW = re.compile(r"^\|\s*(\d+)\s*\|")


def _ticks(line: str) -> list[str]:
    return re.findall(r"`([^`]+)`", line)


def check_markdown(path: Path, name: str) -> list[Violation]:
    out: list[Violation] = []
    text = path.read_text(encoding="utf-8")
    known_routes, users, spaces, apps, boards, sections = (
        routes(),
        realm_users(),
        namespaces(),
        applications(),
        dashboards(),
        cli_options(),
    )
    uids = {str(v["uid"]) for v in boards.values()} | folder_uids()
    all_options = set().union(*sections.values())
    for number, line in enumerate(text.split("\n"), start=1):

        def bad(message: str, number: int = number) -> None:
            out.append(Violation(name, number, message))

        row_users = USER.findall(line)
        for user in row_users:
            if user not in users:
                bad(f"usuario inexistente en realm.kind.yaml: {user}")
        for route in re.findall(r"`ruta (/[^`]*)`", line):
            if route not in known_routes or not known_routes[route][0]:
                bad(f"ruta de la SPA sin entry: true en routes.ts: {route}")
                continue
            for user in row_users:
                if user in users and not users[user] & known_routes[route][1]:
                    bad(
                        f"el usuario {user} ({sorted(users[user])}) no tiene el rol de {route} ({sorted(known_routes[route][1])})"
                    )
        for token in NAMESPACE.findall(line):
            if token not in spaces and token not in NOT_NAMESPACES and token not in uids:
                bad(f"namespace que no esta en flows.yaml: {token}")
        for app in re.findall(r"Application(?:es)? `([a-z0-9-]+)`", line):
            if app not in apps:
                bad(f"Application que no esta en components.yaml: {app}")
        for alert in re.findall(r"alerta `([A-Za-z]+)`", line) + re.findall(r'alertname="([A-Za-z]+)"', line):
            if alert not in alert_names():
                bad(f"alerta que ninguna regla del repositorio define: {alert}")
        for tick in _ticks(line):
            if (
                re.fullmatch(r"vectra_[a-z0-9_]+|vectra:[a-z0-9_:]+|inbound_http_authz_deny_total", tick)
                and tick not in corpus()
            ):
                bad(
                    f"serie que ningun archivo de metricas, reglas o dashboards del repositorio nombra: {tick}"
                )
            if (
                re.fullmatch(r"[A-Za-z0-9_./-]+", tick)
                and "/" in tick
                and not tick.startswith(GENERATED_PREFIXES)
                and ".out" not in tick
            ):
                first = tick.split("/", 1)[0]
                if (VECTRA / first).is_dir() or first == "demos":
                    if not (VECTRA / tick).exists() and not (SYSTEM / tick).exists():
                        bad(f"ruta citada que no existe: {tick}")
            if tick.startswith("vectra-verification "):
                words = tick.split()[1:]
                if not words or words[0] not in sections or words[0] not in cli.SECTIONS_RUN:
                    bad(f"seccion de la CLI que no es un subcomando: {words[0] if words else ''}")
                else:
                    for option in (w for w in words[1:] if w.startswith("--")):
                        if option not in sections[words[0]] | {"--help"}:
                            bad(f"opcion que la seccion {words[0]} no tiene: {option}")
            elif tick.startswith("--") and tick.split()[0].rstrip(",") not in all_options | {"--help"}:
                bad(f"opcion de la CLI que no existe: {tick.split()[0]}")
        for prefix in re.findall(r"(rt5-[a-z]+)-<runId>", line):
            if prefix not in job_prefixes():
                bad(
                    f"Job de prueba que el chart no declara: {prefix}-<runId> (el chart trae {sorted(job_prefixes())})"
                )
        for tick in _ticks(line):
            if tick.startswith("promotion-tool "):
                words = tick.split()
                if len(words) < 2 or words[1] not in promotion_commands():
                    bad(f"subcomando que promotion-tool no tiene: {words[1] if len(words) > 1 else ''}")
        for title in re.findall(r"[Dd]ashboard `([^`]+)`", line):
            if title not in boards:
                bad(f"dashboard que ni product.json ni operacion.json tienen: {title}")
            else:
                for uid in re.findall(r"uid `([^`]+)`", line):
                    if uid != boards[title]["uid"]:
                        bad(f"el uid {uid} no es el del dashboard {title}")
        for uid in re.findall(r"uid `([^`]+)`", line):
            if uid not in uids:
                bad(f"uid que ningun dashboard tiene: {uid}")
        for folder in re.findall(r"carpeta `([^`]+)`", line):
            if folder not in folders():
                bad(f"carpeta que folder-permissions.yaml no tiene: {folder}")
        for panel in re.findall(r"[Pp]anel `([^`]+)`", line):
            if not any(panel in b["panels"] for b in boards.values()):  # type: ignore[operator]
                bad(f"panel que ningun dashboard tiene: {panel}")
        for key in re.findall(r"clave de values `([A-Za-z0-9_.]+)`", line):
            if key not in values_keys():
                bad(f"clave de values que el repositorio no declara: {key}")
        if STEP_ROW.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 5 or cells[1] not in {"presentador", "operador"}:
                bad("fila de paso mal formada (N | quien | que hace | que se ve y donde | verify)")
            else:
                reference = re.search(r"`([a-z0-9-]+\.sh) (\d+)", cells[4])
                if reference is None:
                    if not re.match(r"—.*(no observable|opcional)", cells[4]):
                        bad("el paso no nombra un verify ni dice por que no es observable")
                else:
                    script = DEMOS_DIR_OF(path) / "verify" / reference.group(1)
                    if not script.is_file():
                        bad(f"verify que no existe: {reference.group(1)}")
                    elif reference.group(2) not in verify_steps(script):
                        bad(f"el verify {reference.group(1)} no acepta el paso {reference.group(2)}")
    return out


# El orden de los pasos (F-03 y AMARILLO de la ronda 1): la primera aparicion de cada ancla en el guion, por (linea, columna). Una regla (a, b) se aplica solo si el guion nombra las dos.
ANCHORS = {
    "prepare": r"vectra-verification prepare",
    "pr-runid": r"rt5-run-id",
    "rt5": r"vectra-verification rt5(?![-\w])",
    "decisions": r"vectra-verification decisions",
    "u11": r"vectra-verification u11",
    "apagar": r"apagar\.patch",
    "rt3": r"vectra-verification rt3(?![-\w])(?! --closing)",
    "revertir": r"revertir\.patch",
    "rt3-closing": r"vectra-verification rt3 --closing",
    "pr-proxy": r"Arma el PR `proxy-staging`",
    "rt2-setup": r"vectra-verification rt2-setup",
    "create": r"promotion-tool create-promotion-pr",
    "mark": r"promotion-tool mark-active",
    "post": r"promotion-tool post-activation-pr",
    "rt2": r"vectra-verification rt2(?![-\w])",
    "rollback": r"promotion-tool rollback-pr",
}
ORDER = [
    ("prepare", "pr-runid"),
    ("pr-runid", "rt5"),
    ("prepare", "rt5"),
    ("prepare", "decisions"),
    ("decisions", "u11"),
    ("apagar", "rt3"),
    ("rt3", "revertir"),
    ("revertir", "rt3-closing"),
    ("pr-proxy", "rt2-setup"),
    ("rt2-setup", "rt2"),
    ("decisions", "rt2"),
    ("create", "mark"),
    ("mark", "post"),
    ("post", "rt2"),
    ("rt2", "rollback"),
    ("post", "rollback"),
]


def check_order(path: Path, name: str) -> list[Violation]:
    first: dict[str, tuple[int, int]] = {}
    lines = path.read_text(encoding="utf-8").split("\n")
    for number, line in enumerate(lines, start=1):
        for anchor, pattern in ANCHORS.items():
            found = re.search(pattern, line)
            if found and anchor not in first:
                first[anchor] = (number, found.start())
    out = [
        Violation(name, first[after][0], f"`{after}` aparece antes que `{before}` y debe ir despues")
        for before, after in ORDER
        if before in first and after in first and first[after] <= first[before]
    ]
    for number, line in enumerate(
        lines, start=1
    ):  # dentro de un mismo paso: el rollback va antes que el mark-active de la referencia
        rollback, mark = re.search(ANCHORS["rollback"], line), list(re.finditer(ANCHORS["mark"], line))
        if rollback and mark and not any(m.start() > rollback.start() for m in mark):
            out.append(Violation(name, number, "el mark-active va despues del rollback-pr"))
    steps = [int(m.group(1)) for line in lines if (m := STEP_ROW.match(line))]
    if steps != list(range(1, len(steps) + 1)):
        out.append(Violation(name, 1, f"los pasos no estan numerados 1..N en orden: {steps}"))
    return out


def DEMOS_DIR_OF(path: Path) -> Path:  # noqa: N802
    return path.parent


def check_patch(path: Path, name: str) -> list[Violation]:
    out = []
    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        if line.startswith("+++ b/"):
            target = line.removeprefix("+++ b/").removeprefix("vectra-risk/")
            if not (VECTRA / target).is_file():
                out.append(Violation(name, number, f"el parche nombra un archivo que no existe: {target}"))
    return out


def check_verify(path: Path, name: str) -> list[Violation]:
    out = []
    users = namespaces()
    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        for token in NAMESPACE.findall(line):
            if token not in users and token not in NOT_NAMESPACES:
                out.append(Violation(name, number, f"namespace que no esta en flows.yaml: {token}"))
        for prefix in re.findall(r"(rt5-[a-z]+)-[$\"]", line):
            if prefix not in job_prefixes():
                out.append(Violation(name, number, f"Job de prueba que el chart no declara: {prefix}"))
        for alert in re.findall(r'alertname="([A-Za-z]+)"', line):
            if alert not in alert_names():
                out.append(Violation(name, number, f"alerta que ninguna regla define: {alert}"))
        for series in re.findall(r"(vectra_[a-z0-9_]+|inbound_http_authz_deny_total)", line):
            if series not in corpus():
                out.append(Violation(name, number, f"serie inexistente: {series}"))
    return out


def check(demos: Path) -> list[Violation]:
    found: list[Violation] = []
    for path in sorted(demos.glob("*.md")):
        found += check_markdown(path, f"{path.name}") + check_order(path, f"{path.name}")
    for path in sorted((demos / "verify").glob("*.sh")):
        found += check_verify(path, f"verify/{path.name}")
    for path in sorted((demos / "prs").rglob("*.patch*")):
        found += check_patch(path, str(path.relative_to(demos))) if path.suffix == ".patch" else []
    return found


def copy_of(tmp_path: Path) -> Path:
    target = tmp_path / "demos"
    shutil.copytree(DEMOS, target)
    return target


def mutate(tmp_path: Path, file: str, old: str, new: str) -> list[Violation]:
    demos = copy_of(tmp_path)
    path = demos / file
    text = path.read_text(encoding="utf-8")
    assert old in text, f"la mutacion no encuentra {old!r} en {file}"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return check(demos)


# --- CA-2 --------------------------------------------------------------------------------------------------------------------------------------------


def test_the_real_demos_name_nothing_that_does_not_exist() -> None:
    assert [str(v) for v in check(DEMOS)] == []


def test_the_four_scripts_their_verifies_and_the_five_prs_exist() -> None:
    for name in ("journey-7-3", "journey-7-4", "rt-5", "dashboard"):
        assert (DEMOS / f"{name}.md").is_file() and (DEMOS / "verify" / f"{name}.sh").is_file(), name
    for name in ("f22-apagado", "rt5-run-id", "rt3-staging", "proxy-staging", "promocion"):
        assert (DEMOS / "prs" / name).is_dir(), name


@pytest.mark.parametrize(
    ("file", "old", "new", "expected"),
    [
        ("journey-7-3.md", "`ruta /casos` con `analista-2`", "`ruta /fallos` con `analista-2`", "/fallos"),
        (
            "journey-7-4.md",
            "Con `cumplimiento-2`, abre la `ruta /congelamientos`",
            "Con `cro-1`, abre la `ruta /congelamientos`",
            "cro-1",
        ),
        ("journey-7-3.md", "`analista-2` (rol `analista`)", "`analista-3` (rol `analista`)", "analista-3"),
        ("journey-7-3.md", "los pods de `vectra-serving`", "los pods de `vectra-apps`", "vectra-apps"),
        (
            "journey-7-3.md",
            "la alerta `FailClosedPersistente`: la muestra",
            "la alerta `CoreWriteAttempts`: la muestra",
            "CoreWriteAttempts",
        ),
        (
            "journey-7-4.md",
            "la Application `model-serving` en Argo CD.",
            "la Application `decision-registry-rebuild` en Argo CD.",
            "decision-registry-rebuild",
        ),
        ("dashboard.md", "panel `North Star de ayer`", "panel `North Star de hoy`", "North Star de hoy"),
        ("dashboard.md", "`vectra-verification u11`", "`vectra-verification pii`", "pii"),
        ("dashboard.md", "`vectra-verification u11`", "`vectra-verification u11 --no-existe`", "--no-existe"),
        ("rt-5.md", "`rt-5.sh 3`", "`rt-5.sh 9`", "no acepta el paso 9"),
        ("rt-5.md", "clave de values `probes.runId`", "clave de values `probes.runid`", "probes.runid"),
        ("dashboard.md", "carpeta `Vectra / Producto`", "carpeta `Vectra / Producta`", "Producta"),
        (
            "rt-5.md",
            "`vectra_core_write_attempts_total`",
            "`vectra_core_write_attempt_total`",
            "vectra_core_write_attempt_total",
        ),
        (
            "journey-7-3.md",
            "`demos/prs/f22-apagado/revertir.patch`",
            "`demos/prs/f22-apagado/revertir-no.patch`",
            "no existe",
        ),
    ],
)
def test_red_each_mutation_of_a_script_fails_naming_the_file_and_the_line(
    tmp_path: Path, file: str, old: str, new: str, expected: str
) -> None:
    found = mutate(tmp_path, file, old, new)
    assert any(v.file == file and v.line > 0 and expected in v.message for v in found), [
        str(v) for v in found
    ]


def swapped(text: str, first: str, second: str) -> str:
    """El texto con la linea que contiene `first` y la que contiene `second` intercambiadas."""
    lines = text.split("\n")
    i, j = (next(n for n, line in enumerate(lines) if marker in line) for marker in (first, second))
    lines[i], lines[j] = lines[j], lines[i]
    return "\n".join(lines)


@pytest.mark.parametrize(
    ("file", "first", "second", "expected"),
    [
        ("journey-7-4.md", "vectra-verification rt2-setup", "vectra-verification rt2 --reactivation", "rt2"),
        ("journey-7-4.md", "Arma el PR `proxy-staging`", "vectra-verification rt2-setup", "rt2-setup"),
        ("journey-7-4.md", "Promueve `<M2>`", "vectra-verification rt2 --reactivation", "rt2"),
        ("journey-7-4.md", "vectra-verification rt2 --reactivation", "Mientras `rt2` verifica", "rollback"),
        ("rt-5.md", "Abre el PR `rt5-run-id`", "Corre `vectra-verification rt5`", "rt5"),
        ("dashboard.md", "corre `vectra-verification decisions`", "corre `vectra-verification u11`", "u11"),
        ("journey-7-3.md", "apagar.patch", "rt3 --packages-dir", "rt3"),
        ("journey-7-3.md", "revertir.patch", "rt3 --packages-dir", "rt3"),
    ],
)
def test_red_steps_in_an_impossible_order_fail_naming_the_file_and_the_line(
    tmp_path: Path, file: str, first: str, second: str, expected: str
) -> None:
    """AMARILLO de la ronda 1: la prueba de mundo cerrado ve el orden de las secciones y de los PR de cada guion."""
    demos = copy_of(tmp_path)
    path = demos / file
    path.write_text(swapped(path.read_text(encoding="utf-8"), first, second), encoding="utf-8")
    found = check(demos)
    assert any(v.file == file and v.line > 0 and expected in v.message for v in found), [
        str(v) for v in found
    ]


@pytest.mark.parametrize(
    ("file", "old", "new", "expected"),
    [
        ("rt-5.md", "Job `rt5-demo-<runId>`", "Job `rt5-probe-<runId>`", "rt5-probe"),
        (
            "journey-7-4.md",
            "`promotion-tool post-activation-pr <M1>`",
            "`promotion-tool post-activate-pr <M1>`",
            "post-activate-pr",
        ),
        (
            "journey-7-4.md",
            "`promotion-tool rollback-pr <M1>`, fusión, sync de la Application `model-serving` en Argo CD, espera a que los pods de `<M1>` estén `Ready` y, **después**, `promotion-tool mark-active <M1>`",
            "`promotion-tool mark-active <M1>`, y **después** `promotion-tool rollback-pr <M1>`",
            "mark-active va despues",
        ),
    ],
)
def test_red_a_job_name_outside_the_chart_or_a_command_of_promotion_tool_that_does_not_exist_fails(
    tmp_path: Path, file: str, old: str, new: str, expected: str
) -> None:
    found = mutate(tmp_path, file, old, new)
    assert any(v.file == file and v.line > 0 and expected in v.message for v in found), [
        str(v) for v in found
    ]


def test_red_a_deleted_source_makes_the_script_fail(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: D103
    """Si se borra la fuente (una ruta de `routes.ts`), el guion falla: la prueba no tiene su propia lista de permitidos."""
    original = routes()
    monkeypatch.setattr(
        __import__("sys").modules[__name__],
        "routes",
        lambda: {k: v for k, v in original.items() if k != "/casos"},
    )
    assert any("/casos" in v.message for v in check(DEMOS))


def test_the_scripts_carry_the_phrases_and_times_the_task_requires() -> None:
    dashboard = (DEMOS / "dashboard.md").read_text(encoding="utf-8")
    assert (
        "port-forward" in dashboard
        and "grafana-admin" in dashboard
        and "Los permisos por carpeta y rol no se enseñan" in dashboard
    )
    journey = (DEMOS / "journey-7-4.md").read_text(encoding="utf-8")
    assert (
        "cumplimiento-1" in journey
        and "cumplimiento-2" in journey
        and "--reactivation" in journey
        and "`tool`" in journey
        and "`presenter`" in journey
    )
    for file, needles in {
        "journey-7-3.md": ("19,3",),
        "journey-7-4.md": ("75",),
        "rt-5.md": ("5 min",),
        "dashboard.md": ("23:00 UTC", "02:30 UTC"),
    }.items():
        text = (DEMOS / file).read_text(encoding="utf-8")
        assert all(n in text for n in needles), file
    assert "no se abre" in journey and "/fallos" not in (DEMOS / "journey-7-3.md").read_text(encoding="utf-8")


def test_d1_says_what_happens_when_f22_is_reverted_and_d2_follows_the_sequence_of_promotion_tool() -> None:
    """F-01 y F-03 (ronda 2): la alerta NO se apaga al revertir F22 (los casos de la sonda siguen en `no_disponible`); y D2 trae `post-activation-pr`, `rollback-pr` y `mark-active` de la referencia."""
    d1 = (DEMOS / "journey-7-3.md").read_text(encoding="utf-8")
    row = next(line for line in d1.split("\n") if line.startswith("| 6 |"))
    assert "**sigue en `firing`**" in row and "se apaga" not in row and "closing_rt3" in row
    assert "reintento del CRO" in d1 and "No afectan a D2, D3 ni D4" in d1
    verify = (DEMOS / "verify" / "journey-7-3.sh").read_text(encoding="utf-8")
    assert "closing_rt3" in verify and "se apago" not in verify
    d2 = (DEMOS / "journey-7-4.md").read_text(encoding="utf-8")
    for command in ("create-promotion-pr", "post-activation-pr", "rollback-pr", "mark-active"):
        assert f"`promotion-tool {command} <M" in d2, command
    assert "espera el cierre" in d2 and "closing_rt2" in d2
    verify = (DEMOS / "verify" / "journey-7-4.sh").read_text(encoding="utf-8")
    assert "closing_rt2" in verify and "esta activo" in verify


def test_every_step_of_every_verify_is_named_by_its_script() -> None:
    for name in ("journey-7-3", "journey-7-4", "rt-5", "dashboard"):
        text = (DEMOS / f"{name}.md").read_text(encoding="utf-8")
        named = set(re.findall(rf"`{re.escape(name)}\.sh (\d+)", text))
        assert named == verify_steps(DEMOS / "verify" / f"{name}.sh"), name


# --- CA-5: cada orden de los verify cabe en K16 ---------------------------------------------------------------------------------------------


def k16() -> dict[tuple[str, str], set[str]]:
    allowed: dict[tuple[str, str], set[str]] = {}
    for document in yaml.safe_load_all(_read("platform/rbac/verification-operator/k16.yaml")):
        if document.get("kind") == "Role":
            for rule in document["rules"]:
                for resource in rule["resources"]:
                    allowed.setdefault((document["metadata"]["namespace"], resource), set()).update(
                        rule["verbs"]
                    )
    return allowed


def kubectl_commands(text: str) -> list[tuple[int, list[str]]]:
    commands = []
    for number, line in enumerate(text.split("\n"), start=1):
        if line.lstrip().startswith("#"):
            continue
        for match in re.finditer(r"\bkubectl\b", line):
            tail = re.split(r"&&|\|\||[;|&)`]", line[match.end() :])[0]
            try:
                commands.append((number, shlex.split(tail)))
            except ValueError:
                commands.append((number, tail.split()))
    return commands


def k16_findings(text: str, name: str) -> list[str]:
    allowed, found = k16(), []
    for number, tokens in kubectl_commands(text):
        where = f"{name}:{number}"
        words, i = [], 0
        while i < len(tokens):
            if tokens[i] in {"--context", "-n", "-l", "-o", "--address"}:
                if tokens[i] == "-n":
                    words.append(("ns", tokens[i + 1]))
                i += 2
                continue
            if tokens[i].startswith("-"):
                i += 1
                continue
            words.append(("w", tokens[i]))
            i += 1
        namespace = next((v for k, v in words if k == "ns"), None)
        positional = [v for k, v in words if k == "w"]
        if not positional:
            continue
        verb, rest = positional[0], positional[1:]
        if verb == "get":
            raw = rest[0] if rest else ""
            resource = raw.split("/", 1)[0].split(".", 1)[0]
            resource = resource if resource.endswith("s") else resource + "s"
            if (namespace, resource) not in allowed or "get" not in allowed[(namespace, resource)]:
                found.append(f"{where}: kubectl get {raw} -n {namespace} no cabe en K16")
        elif verb == "logs":
            if "get" not in allowed.get((namespace or "", "pods/log"), set()):
                found.append(f"{where}: kubectl logs -n {namespace} no cabe en K16 (pods/log)")
        elif verb == "port-forward":
            target = rest[0] if rest else ""
            if "create" not in allowed.get((namespace or "", "pods/portforward"), set()):
                found.append(f"{where}: port-forward -n {namespace} no cabe en K16 (pods/portforward)")
            if not (target.startswith("pod/") or target == "$POD"):
                found.append(f"{where}: port-forward a {target}: siempre a pod/..., nunca a svc/...")
        else:
            found.append(f"{where}: kubectl {verb} no es de lectura")
    return found


@pytest.mark.parametrize("script", sorted((DEMOS / "verify").glob("*.sh")), ids=lambda p: p.name)
def test_k16_every_kubectl_command_of_every_verify_fits_in_k16(script: Path) -> None:
    assert k16_findings(script.read_text(encoding="utf-8"), script.name) == []


@pytest.mark.parametrize(
    ("line", "needle"),
    [
        ("kubectl get cronjobs -n vectra-app", "cronjobs"),
        ("kubectl get pods -n vectra-mock", "vectra-mock"),
        ("kubectl port-forward -n vectra-observability svc/prometheus :9090", "svc/prometheus"),
        ("kubectl get secrets -n vectra-app", "secrets"),
        ("kubectl get networkpolicies -n vectra-serving", "networkpolicies"),
        ("kubectl logs x -n vectra-staging", "pods/log"),
        ("kubectl delete pod x -n vectra-app", "no es de lectura"),
    ],
)
def test_k16_red_a_command_that_k16_does_not_give_fails_with_its_reason(line: str, needle: str) -> None:
    assert any(needle in f for f in k16_findings(line + "\n", "x.sh"))


# --- cada verify contra el doble de kubectl y de Prometheus ---------------------------------------------------------------------------------


def run_verify(
    tmp_path: Path,
    script: str,
    *args: str,
    state: dict[str, object] | None = None,
    files: dict[str, str] | None = None,
) -> tuple[int, str, list[list[str]]]:
    bin_dir, work = tmp_path / "bin", tmp_path / "verificacion"
    work.mkdir(parents=True, exist_ok=True)
    for name, text in (files or {}).items():
        (work / name).write_text(text, encoding="utf-8")
    env = {
        **os.environ,
        **fake_kubectl_bin.install(bin_dir, state or {}),
        "VERIFICATION_DIR": str(work),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "KUBE_CONTEXT": "kind-vectra",
    }
    done = subprocess.run(
        ["sh", str(DEMOS / "verify" / script), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )
    log = bin_dir / "calls.log"
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return done.returncode, done.stdout + done.stderr, calls


PROM_POD = {"vectra-observability|app.kubernetes.io/name=prometheus": ["prometheus-0"]}
FAIL_ALERT = 'ALERTS{alertname="FailClosedPersistente", alertstate="firing"}'
GAUGE = "max(vectra_cases_failclosed_persistent)"
CORE_ALERT = 'ALERTS{alertname="CoreWriteAttempt", alertstate="firing"}'
DENY = 'inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"}'
STALE = 'ALERTS{alertname="ProductMetricsStale", alertstate="firing"}'
MANIFEST = '{"run_id": "20261113-1000"}'


def evidence(result: str) -> str:
    return json.dumps({"evidence": {"result": result}})


def closing_manifest(section: str, result: str, **more: object) -> str:
    """El `manifest.json` con el cierre que la CLI registra aparte (`closing_rt3`, `closing_rt2`)."""
    return json.dumps({"run_id": "20261113-1000", f"closing_{section}": {"result": result, **more}})


@pytest.mark.parametrize(
    ("script", "step", "ok_state", "bad_state", "files"),
    [
        ("journey-7-3.sh", "1", {"pods": {"vectra-serving|None": ["explainer-0"]}}, {"pods": {}}, {}),
        (
            "journey-7-3.sh",
            "2",
            {"pods": PROM_POD, "prom": {GAUGE: [1]}},
            {"pods": PROM_POD, "prom": {GAUGE: [0]}},
            {},
        ),
        (
            "journey-7-3.sh",
            "3",
            {"pods": PROM_POD, "prom": {FAIL_ALERT: [1]}},
            {"pods": PROM_POD, "prom": {}},
            {},
        ),
        (
            "journey-7-3.sh",
            "4",
            {},
            {},
            {"manifest.json": closing_manifest("rt3", "pasa")},
        ),
        ("rt-5.sh", "1", {"jobs": {"rt5-demo-20261113-1000": {}}}, {"jobs": {}}, {"manifest.json": MANIFEST}),
        (
            "rt-5.sh",
            "2",
            {"jobs": {"rt5-demo-20261113-1000": {"succeeded": "1"}}},
            {"jobs": {"rt5-demo-20261113-1000": {"succeeded": ""}}},
            {"manifest.json": MANIFEST},
        ),
        (
            "rt-5.sh",
            "4",
            {"pods": PROM_POD, "prom": {CORE_ALERT: [1]}},
            {"pods": PROM_POD, "prom": {}},
            {"manifest.json": MANIFEST},
        ),
        (
            "rt-5.sh",
            "5",
            {"pods": PROM_POD, "prom": {DENY: [1], "max(vectra_core_write_attempts_total)": [0]}},
            {"pods": PROM_POD, "prom": {DENY: [1], "max(vectra_core_write_attempts_total)": [3]}},
            {"manifest.json": MANIFEST},
        ),
        (
            "rt-5.sh",
            "6",
            {},
            {},
            {"manifest.json": MANIFEST, "RT-5.json": evidence("pasa"), "demo-rt-5.json": evidence("pasa")},
        ),
        (
            "journey-7-4.sh",
            "2",
            {
                "pods": PROM_POD,
                "prom": {
                    "min(vectra_bias_last_run_ok)": [1],
                    "max(vectra_bias_last_run_timestamp)": [1763000000],
                },
            },
            {
                "pods": PROM_POD,
                "prom": {
                    "min(vectra_bias_last_run_ok)": [0],
                    "max(vectra_bias_last_run_timestamp)": [1763000000],
                },
            },
            {},
        ),
        (
            "dashboard.sh",
            "1",
            {"phases": {"vectra-observability|app.kubernetes.io/name=grafana": ["Running"]}},
            {"phases": {"vectra-observability|app.kubernetes.io/name=grafana": ["Pending"]}},
            {},
        ),
        ("dashboard.sh", "3", {"pods": PROM_POD, "prom": {}}, {"pods": PROM_POD, "prom": {STALE: [1]}}, {}),
        ("dashboard.sh", "4", {}, {}, {"demo-dashboard.json": evidence("pasa")}),
    ],
)
def test_each_verify_gives_0_for_the_expected_state_and_1_for_another_with_the_double(
    tmp_path: Path,
    script: str,
    step: str,
    ok_state: dict[str, object],
    bad_state: dict[str, object],
    files: dict[str, str],
) -> None:
    code, text, calls = run_verify(tmp_path / "ok", script, step, state=ok_state, files=files)
    assert code == 0, text
    if script.startswith(("rt-5", "dashboard")) and step in {"6", "4"} and not ok_state:
        return
    other = dict(files)
    for name in [n for n in other if n.endswith(".json") and n != "manifest.json"]:
        other[name] = evidence("falla")
    if script == "journey-7-3.sh" and step == "4":
        other["manifest.json"] = closing_manifest("rt3", "no ejecutado")
    code, text, _ = run_verify(tmp_path / "bad", script, step, state=bad_state, files=other)
    assert code == 1, text
    assert all(
        c[0] == "--context" and c[1] == "kind-vectra" and c[2] in {"get", "logs", "port-forward"}
        for c in calls
    )


def test_the_verifies_exit_2_when_the_double_does_not_answer(tmp_path: Path) -> None:
    for script, step, files in (
        ("journey-7-3.sh", "1", {}),
        ("journey-7-3.sh", "2", {}),
        ("rt-5.sh", "2", {"manifest.json": MANIFEST}),
        ("dashboard.sh", "1", {}),
        ("journey-7-4.sh", "1", {}),
    ):
        code, text, _ = run_verify(
            tmp_path / f"{script}{step}",
            script,
            step,
            *(["isvc-26300247"] if script == "journey-7-4.sh" else []),
            state={"down": True},
            files=files,
        )
        assert code == 2 and "NO SE PUDO LEER" in text, (script, step, text)
    code, text, _ = run_verify(
        tmp_path / "prom", "journey-7-3.sh", "3", state={"pods": PROM_POD, "prom_down": True}
    )
    assert code == 2, text
    code, text, _ = run_verify(
        tmp_path / "pf", "journey-7-3.sh", "3", state={"pods": PROM_POD, "pf_fails": True}
    )
    assert code == 2 and "port-forward" in text
    code, text, _ = run_verify(tmp_path / "nopod", "journey-7-3.sh", "3", state={"pods": {}})
    assert code == 2 and "no hay pod de Prometheus" in text
    for script in ("journey-7-3.sh", "journey-7-4.sh", "rt-5.sh", "dashboard.sh"):
        code, _, _ = run_verify(tmp_path / f"uso-{script}", script, "99", files={"manifest.json": MANIFEST})
        assert code == 2, script
    code, text, _ = run_verify(tmp_path / "sin-manifiesto", "rt-5.sh", "1")
    assert code == 2 and "prepare" in text
    code, text, _ = run_verify(tmp_path / "sin-evidencia", "dashboard.sh", "4")
    assert code == 2 and "no existe la evidencia" in text


def test_verify_the_isvc_steps_and_the_job_log_and_the_dashboard_series(tmp_path: Path) -> None:
    ready = {"isvc": {"isvc-26300247": "True"}}
    assert run_verify(tmp_path / "a", "journey-7-4.sh", "1", "isvc-26300247", state=ready)[0] == 0
    assert (
        run_verify(
            tmp_path / "b", "journey-7-4.sh", "1", "isvc-26300247", state={"isvc": {"isvc-26300247": "False"}}
        )[0]
        == 1
    )
    closed = {"manifest.json": closing_manifest("rt2", "pasa")}
    assert (
        run_verify(tmp_path / "c", "journey-7-4.sh", "4", "isvc-26300247", state=ready, files=closed)[0] == 0
    )
    # F-03: el InferenceService listo no basta; la referencia tiene que estar `activo` en governance (lo que `rt2` vio al cerrar)
    for index, closing in enumerate(("no ejecutado", "falla")):
        other = {"manifest.json": closing_manifest("rt2", closing)}
        done = run_verify(
            tmp_path / f"c{index}", "journey-7-4.sh", "4", "isvc-26300247", state=ready, files=other
        )
        assert done[0] == 1 and "no esta activo" in done[1], done
    assert (
        run_verify(
            tmp_path / "c2",
            "journey-7-4.sh",
            "4",
            "isvc-26300247",
            state=ready,
            files={"manifest.json": MANIFEST},
        )[0]
        == 2
    )
    assert (
        run_verify(
            tmp_path / "c3",
            "journey-7-4.sh",
            "4",
            "isvc-26300247",
            state={"isvc": {"isvc-26300247": "False"}},
            files=closed,
        )[0]
        == 1
    )

    def section(result: str) -> str:
        return json.dumps({"sections": {"rt2-setup": {"result": result}, "decisions": {"result": result}}})

    assert (
        run_verify(tmp_path / "s1", "journey-7-4.sh", "5", files={"manifest.json": section("pasa")})[0] == 0
    )
    assert (
        run_verify(tmp_path / "s2", "journey-7-4.sh", "5", files={"manifest.json": section("no ejecutado")})[
            0
        ]
        == 1
    )
    assert run_verify(tmp_path / "s3", "journey-7-4.sh", "5", files={"manifest.json": MANIFEST})[0] == 2
    assert run_verify(tmp_path / "s4", "dashboard.sh", "5", files={"manifest.json": section("pasa")})[0] == 0
    assert run_verify(tmp_path / "s5", "dashboard.sh", "5", files={"manifest.json": section("falla")})[0] == 1
    assert run_verify(tmp_path / "s6", "dashboard.sh", "5", files={"manifest.json": MANIFEST})[0] == 2
    assert run_verify(tmp_path / "d", "journey-7-4.sh", "1")[0] == 2
    job = {"pods": {"vectra-app|job-name=rt5-demo-20261113-1000": ["rt5-demo-x"]}, "jobs": {}}
    proxy = "rt5-demo: POST http://core -> 403 l5d-proxy-error: unauthorized\n"
    app = "rt5-demo: POST http://core -> 403 l5d-proxy-error: None\n"
    assert (
        run_verify(
            tmp_path / "e", "rt-5.sh", "3", state={**job, "log": proxy}, files={"manifest.json": MANIFEST}
        )[0]
        == 0
    )
    assert (
        run_verify(
            tmp_path / "f", "rt-5.sh", "3", state={**job, "log": app}, files={"manifest.json": MANIFEST}
        )[0]
        == 1
    )
    assert (
        run_verify(
            tmp_path / "g",
            "rt-5.sh",
            "3",
            state={**job, "log": "otra cosa\n"},
            files={"manifest.json": MANIFEST},
        )[0]
        == 1
    )
    series = {
        'vectra:product_north_star_ratio:dedup{period="day", channel="all", outcome="all", model_version_id="all"}': [
            0.4
        ],
        'vectra:product_recommendation_sustained_ratio:dedup{period="30d", channel="all", outcome="all"}': [
            0.5
        ],
        'vectra:product_explanation_view_ratio:dedup{period="7d", channel="all"}': [0.6],
        "vectra:product_noise_days_below_floor:dedup": [0],
    }
    assert run_verify(tmp_path / "h", "dashboard.sh", "2", state={"pods": PROM_POD, "prom": series})[0] == 0
    partial = dict(series)
    partial.pop("vectra:product_noise_days_below_floor:dedup")
    assert run_verify(tmp_path / "i", "dashboard.sh", "2", state={"pods": PROM_POD, "prom": partial})[0] == 1


def test_the_verifies_leave_no_process_and_write_nothing_in_the_evidence_directory(tmp_path: Path) -> None:
    before = sorted(p.name for p in (SYSTEM / "evidence").iterdir())
    run_verify(tmp_path, "journey-7-3.sh", "3", state={"pods": PROM_POD, "prom": {FAIL_ALERT: [1]}})
    assert sorted(p.name for p in (SYSTEM / "evidence").iterdir()) == before
    leftover = subprocess.run(
        ["pgrep", "-f", str(tmp_path / "bin" / "kubectl")], capture_output=True, text=True, check=False
    )
    assert leftover.stdout.strip() == ""
