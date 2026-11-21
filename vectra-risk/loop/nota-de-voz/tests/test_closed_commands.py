"""La lista cerrada de ordenes externas, comprobada dos veces: leyendo el codigo fuente (AST) y mirando lo que el flujo lanza de verdad."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from voz_doubles import FakeConsole

from vectra_nota_de_voz.commands import RECORDERS

PACKAGE = Path(__file__).resolve().parents[1]
SRC = PACKAGE / "src" / "vectra_nota_de_voz"
SOURCES = sorted(SRC.glob("*.py"))
#: Los unicos prefijos de `gh` que existen en el codigo.
GH_ALLOWED = {
    ("gh", "auth", "status"),
    ("gh", "pr", "view"),
    ("gh", "auth", "switch"),
    ("gh", "pr", "review"),
}
#: Palabras que no pueden aparecer como literal en ningun archivo del paquete: otras escrituras de `gh`, tokens e interpretes.
FORBIDDEN_LITERALS = {"merge", "--request-changes", "api", "--show-token", "token", "close", "--admin", "logout", "comment", "edit", "ready", "sh", "bash", "ffmpeg", "curl", "git"}  # fmt: skip
FORBIDDEN_IMPORTS = {
    "pty",
    "socket",
    "urllib",
    "http",
    "requests",
    "httpx",
    "ctypes",
    "multiprocessing",
    "asyncio",
    "pickle",
}


def tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree(path)):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def command_lists(path: Path) -> list[tuple[str, ...]]:
    """Cada lista literal cuyo primer elemento es una cadena: el prefijo de literales con el que empieza."""
    found = []
    for node in ast.walk(tree(path)):
        if (
            isinstance(node, ast.List)
            and node.elts
            and isinstance(node.elts[0], ast.Constant)
            and isinstance(node.elts[0].value, str)
        ):
            prefix = []
            for element in node.elts:
                if not (isinstance(element, ast.Constant) and isinstance(element.value, str)):
                    break
                prefix.append(element.value)
            found.append(tuple(prefix))
    return found


def calls_named(path: Path, attribute: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attribute
    ]


def test_the_sources_are_the_expected_files() -> None:
    assert [p.name for p in SOURCES] == ["__init__.py", "audio.py", "cli.py", "commands.py", "console.py", "errors.py", "note.py", "transcriber.py"]  # fmt: skip


def test_only_commands_py_imports_subprocess_and_nothing_imports_a_network_or_exec_module() -> None:
    for path in SOURCES:
        names = imports(path)
        assert ("subprocess" in names) == (path.name == "commands.py"), path.name
        assert not names & FORBIDDEN_IMPORTS, (path.name, names & FORBIDDEN_IMPORTS)


def test_no_shell_and_no_os_level_process_launch_anywhere() -> None:
    for path in SOURCES:
        for node in ast.walk(tree(path)):
            if isinstance(node, ast.keyword):
                assert node.arg != "shell", f"{path.name}: shell= no se usa"
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os":
                assert not node.attr.startswith(
                    ("system", "popen", "exec", "spawn", "posix_spawn", "fork", "startfile")
                ), node.attr
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("eval", "exec", "compile", "__import__"), (
                    f"{path.name}: {node.func.id}"
                )


def test_subprocess_is_called_in_three_places_with_a_plain_argument_list() -> None:
    path = SRC / "commands.py"
    used = sorted(
        node.func.attr
        for node in ast.walk(tree(path))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    )
    assert used == ["Popen", "run", "run"]
    for name in ("run", "Popen"):
        for call in calls_named(path, name):
            if isinstance(call.func.value, ast.Name) and call.func.value.id == "subprocess":
                assert ast.unparse(call.args[0]) == "list(args)"


def test_every_gh_command_in_the_code_is_on_the_closed_list() -> None:
    gh_lists = [prefix for prefix in command_lists(SRC / "commands.py") if prefix[0] == "gh"]
    assert {prefix[:3] for prefix in gh_lists} == GH_ALLOWED
    assert sorted(prefix[:3] for prefix in gh_lists).count(("gh", "pr", "review")) == 2, (
        "una lista con --comment y otra con --approve"
    )
    for path in SOURCES:
        if path.name != "commands.py":
            assert not [p for p in command_lists(path) if p[0] in ("gh", *RECORDERS)], path.name


def test_gh_pr_review_only_exists_with_comment_or_approve() -> None:
    source = (SRC / "commands.py").read_text(encoding="utf-8")
    reviews = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.List) and ast.unparse(node).startswith("['gh', 'pr', 'review'")
    ]
    modes = sorted(ast.literal_eval(node.elts[4]) for node in reviews)
    assert modes == ["--approve", "--comment"]
    for node in reviews:
        rest = [ast.unparse(element) for index, element in enumerate(node.elts) if index != 4]
        assert rest == ["'gh'", "'pr'", "'review'", "str(number)", "'--body-file'", "str(body_file)"]


def test_the_recorder_commands_are_the_two_on_the_list() -> None:
    first_words = {prefix[0] for prefix in command_lists(SRC / "commands.py")}
    assert first_words == {"gh", *RECORDERS, "--repo"}, "y la cola opcional `--repo <dueno/nombre>`"


def test_no_forbidden_word_is_a_string_literal_in_the_package() -> None:
    for path in SOURCES:
        literals = {
            node.value
            for node in ast.walk(tree(path))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert not literals & FORBIDDEN_LITERALS, (path.name, literals & FORBIDDEN_LITERALS)


def test_each_way_of_launching_a_process_has_exactly_one_caller() -> None:
    """`run` solo lo llama `Gh._run`; `spawn` solo `audio.record`, con `recorder_command(...)`; `interactive` solo el editor de `cli._review`."""
    callers: dict[str, list[str]] = {"spawn": [], "interactive": [], "run": []}
    for path in SOURCES:
        for name in callers:
            for call in calls_named(path, name):
                if ast.unparse(call.func.value) == "subprocess":
                    continue
                callers[name].append(f"{path.name}:{ast.unparse(call)}")
    assert callers["run"] == ["commands.py:self._runner.run(args, self._env)"]
    assert callers["spawn"] == ["audio.py:runner.spawn(recorder_command(program, wav, max_seconds), log)"]
    assert [c for c in callers["interactive"] if "runner" in c] == [
        "cli.py:deps.runner.interactive([*editor, str(draft)])"
    ]
    assert all(
        ".console.interactive()" in c or "cli.py:console.interactive()" == c
        for c in callers["interactive"]
        if "runner" not in c
    )


def allowed(command: tuple[str, ...], editor: str = "nano") -> bool:
    if command[0] in RECORDERS:
        return command[-1].endswith("/nota.wav")
    if command[0] == editor:
        return command[-1].endswith("/nota.md")
    if command[0] != "gh" or command[:3] not in GH_ALLOWED:
        return False
    if command[:3] == ("gh", "pr", "review"):
        return (
            command[4] in ("--comment", "--approve")
            and command[5] == "--body-file"
            and command[6].endswith("/cuerpo.md")
        )
    return True


def test_the_classifier_detects_what_is_off_the_list() -> None:
    assert not allowed(("gh", "pr", "merge", "12"))
    assert not allowed(("gh", "pr", "review", "12", "--request-changes", "--body-file", "/x/cuerpo.md"))
    assert not allowed(("gh", "pr", "review", "12", "--comment", "--body", "texto"))
    assert not allowed(("gh", "api", "repos/a/b"))
    assert not allowed(("gh", "auth", "token"))
    assert not allowed(("sh", "-c", "gh pr view 12"))
    assert not allowed(("ffmpeg", "-i", "/x/nota.wav"))
    assert allowed(("gh", "pr", "review", "12", "--approve", "--body-file", "/x/cuerpo.md"))


@pytest.mark.parametrize(
    "argv, answers",
    [
        (["12"], ["s"]),
        (["12", "--as", "joseluisjedi", "--approve"], ["aprobar", "s"]),
        (["12", "--recorder", "pw-record", "--repo", "a/b"], ["s"]),
        (["12", "--dry-run"], []),
        (["12"], ["n"]),
    ],
)
def test_the_flow_launches_only_commands_on_the_closed_list(argv, answers, launch, runner) -> None:
    launch(FakeConsole(*answers), *argv, env={"EDITOR": "nano"})
    assert runner.calls
    for command in runner.calls:
        assert allowed(command), command


def test_the_readme_lists_the_same_commands() -> None:
    readme = (PACKAGE / "README.md").read_text(encoding="utf-8")
    for prefix in GH_ALLOWED:
        assert f"`{' '.join(prefix)}" in readme, prefix
    for program in RECORDERS:
        assert f"`{program}`" in readme


def test_the_tool_is_not_given_to_any_agent() -> None:
    """La usa la persona que revisa: no esta en `permissions.allow`, ni en el `tools:` de un agente, ni en `.mcp.json`."""
    repo = PACKAGE.parents[2]
    for relative in (
        ".claude/settings.json",
        ".claude/agents/codificador.md",
        ".claude/agents/revisor.md",
        ".mcp.json",
    ):
        text = (repo / relative).read_text(encoding="utf-8")
        assert "nota-de-voz" not in text and "nota_de_voz" not in text, relative
    allow = json.loads((repo / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"][
        "allow"
    ]
    assert not [entry for entry in allow if "gh " in entry or "Bash" in entry], (
        "ninguna orden de consola esta permitida de antemano"
    )
