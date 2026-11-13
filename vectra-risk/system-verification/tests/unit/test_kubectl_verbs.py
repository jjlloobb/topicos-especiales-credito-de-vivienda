"""Prueba estatica de los verbos de `kubectl` (U12 Paso 1; NFR-U12-43; INF-U12-02; BR-U12-09; NFR-U12-01).

El codigo y los guiones solo invocan `kubectl` con `get`, `auth can-i`, `logs` y `port-forward` (lista cerrada, P-4 (a)); cualquier otro verbo falla, y de `argocd`
falla toda invocacion (U12 no lo usa). Recorre `src/`, `demos/`, el `Makefile` y, cuando existan, `README.md` y `Dockerfile`; no recorre `tests/`. Detecta el verbo
aunque haya banderas antes y cuando la orden va como lista de argumentos en Python. El Paso 12 reutiliza `scan_tree` sobre `demos/` sin tocar esta prueba.
"""

import ast
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

import pytest

UNIT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "kubectl"

ALLOWED = {"get", "logs", "port-forward"}
# Banderas globales de `kubectl` que consumen el valor siguiente (si van como `--bandera=valor`, ya es un solo token).
GLOBAL_WITH_VALUE = {
    "-n", "--namespace", "--context", "--cluster", "--user", "--kubeconfig", "-s", "--server", "--token", "--as", "--as-group", "--request-timeout",
}  # fmt: skip
OPAQUE = "<expr>"


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    verb: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: kubectl {self.verb}"


def _verb(tokens: list[str]) -> str | None:
    """El verbo de `kubectl` en `tokens` (lo que sigue a `kubectl`), saltando las banderas; `None` si no hay."""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in GLOBAL_WITH_VALUE:
            i += 2
        elif token.startswith("-"):
            i += 1
        else:
            return token
    return None


def _is_allowed(tokens: list[str]) -> tuple[bool, str]:
    verb = _verb(tokens)
    if verb is None:
        return True, ""
    if verb == "auth":
        rest = tokens[tokens.index("auth") + 1 :]
        sub = next((t for t in rest if not t.startswith("-")), "")
        return sub == "can-i", f"auth {sub}".strip()
    return verb in ALLOWED, verb


def _split(fragment: str) -> list[str]:
    try:
        return shlex.split(fragment, comments=False)
    except ValueError:
        return fragment.split()


def _logical_lines(text: str, base_line: int) -> list[tuple[int, str]]:
    """Las lineas del texto, con las partidas por `\\` al final unidas en una sola y el numero de linea en que empiezan."""
    logical: list[tuple[int, str]] = []
    pending, start = "", 0
    for offset, line in enumerate(text.split("\n")):
        if not pending:
            start = base_line + offset
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        logical.append((start, pending + line))
        pending = ""
    if pending:
        logical.append((start, pending))
    return logical


def scan_text(text: str, name: str, base_line: int = 1) -> list[Finding]:
    """Las ordenes prohibidas en un texto (guion, Makefile, Markdown, Dockerfile o una cadena de Python)."""
    findings: list[Finding] = []
    for number, line in _logical_lines(text, base_line):
        for match in re.finditer(r"\bkubectl\b(.*)", line):
            ok, verb = _is_allowed(_split(match.group(1)))
            if not ok:
                findings.append(Finding(name, number, verb))
        if re.search(r"\bargocd\b\s*\S", line):
            findings.append(Finding(name, number, "argocd"))
    return findings


def scan_python(source: str, name: str) -> list[Finding]:
    findings = scan_text_lines(source, name)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.List | ast.Tuple) and node.elts:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                program = first.value.rsplit("/", 1)[-1]
                args = [
                    e.value if isinstance(e, ast.Constant) and isinstance(e.value, str) else OPAQUE
                    for e in node.elts[1:]
                ]
                if program == "kubectl":
                    ok, verb = _is_allowed(args)
                    if not ok:
                        findings.append(Finding(name, node.lineno, verb))
                if program == "argocd":
                    findings.append(Finding(name, node.lineno, "argocd"))
    return findings


def scan_text_lines(source: str, name: str) -> list[Finding]:
    """En Python, cada cadena (tambien los docstrings) se revisa como texto, con el numero de linea de la cadena."""
    findings: list[Finding] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            findings += scan_text(node.value, name, node.lineno)
    return findings


def scan_file(path: Path, name: str | None = None) -> list[Finding]:
    label = name or str(path)
    text = path.read_text(encoding="utf-8")
    return scan_python(text, label) if path.suffix == ".py" else scan_text(text, label)


def scan_tree(root: Path) -> list[Finding]:
    """Los archivos de una unidad que pueden invocar `kubectl`: `src/`, `demos/`, `Makefile`, `README.md` y `Dockerfile`."""
    files: list[Path] = []
    for sub in ("src", "demos"):
        if (root / sub).is_dir():
            files += sorted(
                p
                for p in (root / sub).rglob("*")
                if p.is_file() and p.suffix in {".py", ".sh", ".md", ".yaml", ".yml", ""}
            )
    files += [root / name for name in ("Makefile", "README.md", "Dockerfile") if (root / name).is_file()]
    return [f for path in files for f in scan_file(path, str(path.relative_to(root)))]


def test_real_files_have_no_findings() -> None:
    assert scan_tree(UNIT) == []


def test_fixture_with_kubectl_apply_fails_and_names_file_line_and_verb() -> None:
    findings = scan_file(FIXTURES / "prohibited" / "apply.sh", "apply.sh")
    assert [str(f) for f in findings] == ["apply.sh:2: kubectl apply"]


@pytest.mark.parametrize("verb", ["exec", "apply", "create", "delete", "patch", "scale", "edit", "rollout"])
def test_each_prohibited_verb_fails(verb: str) -> None:
    findings = scan_file(FIXTURES / "prohibited" / f"{verb}.sh", f"{verb}.sh")
    assert [f.verb for f in findings] == [verb]


def test_argocd_app_sync_script_fails() -> None:
    findings = scan_file(FIXTURES / "prohibited" / "argocd-app-sync.sh", "argocd-app-sync.sh")
    assert [f.verb for f in findings] == ["argocd"]


@pytest.mark.parametrize("name", ["get.sh", "can-i.sh", "logs.sh", "port-forward.sh", "list_get.py"])
def test_allowed_commands_pass(name: str) -> None:
    assert scan_file(FIXTURES / "allowed" / name, name) == []


def test_global_flags_before_the_verb_do_not_hide_it() -> None:
    findings = scan_file(FIXTURES / "prohibited" / "context-apply.sh", "context-apply.sh")
    assert [f.verb for f in findings] == ["apply"]


def test_python_argument_list_with_delete_fails() -> None:
    findings = scan_file(FIXTURES / "prohibited" / "list_delete.py", "list_delete.py")
    assert [(f.line, f.verb) for f in findings] == [(3, "delete")]


def test_python_argument_list_with_an_opaque_verb_fails() -> None:
    findings = scan_file(FIXTURES / "prohibited" / "list_variable_verb.py", "list_variable_verb.py")
    assert [f.verb for f in findings] == [OPAQUE]


def test_a_command_split_with_a_backslash_is_one_command() -> None:
    findings = scan_file(FIXTURES / "prohibited" / "continued-delete.sh", "continued-delete.sh")
    assert [f.verb for f in findings] == ["delete"]


def test_a_docstring_that_writes_a_prohibited_command_fails() -> None:
    findings = scan_file(FIXTURES / "prohibited" / "docstring_apply.py", "docstring_apply.py")
    assert [f.verb for f in findings] == ["apply"]


@pytest.mark.parametrize("name", ["cp", "auth-reconcile", "run", "replace", "label", "annotate", "drain"])
def test_closed_list_rejects_verbs_the_enumeration_does_not_name(name: str) -> None:
    findings = scan_file(FIXTURES / "prohibited" / f"{name}.sh", f"{name}.sh")
    assert len(findings) == 1


def test_scan_tree_reaches_demos_and_the_makefile(tmp_path: Path) -> None:
    (tmp_path / "demos").mkdir()
    (tmp_path / "demos" / "x.sh").write_text("kubectl delete pod x\n")
    (tmp_path / "Makefile").write_text("t:\n\tkubectl -n a apply -f b\n")
    assert sorted(f.verb for f in scan_tree(tmp_path)) == ["apply", "delete"]
