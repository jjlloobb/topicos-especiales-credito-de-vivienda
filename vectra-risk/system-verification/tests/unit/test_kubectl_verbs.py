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
# Banderas globales sin valor. Una bandera antes del verbo que no este en estas dos listas es un hallazgo: no se adivina si lleva valor (falla cerrado).
GLOBAL_FLAGS = {"-h", "--help", "--insecure-skip-tls-verify", "--warnings-as-errors"}
OPAQUE = "<expr>"
UNPARSABLE = "<unparsable>"
# Palabras que, justo antes de `kubectl`, lo vuelven una invocacion indirecta (la orden no se lee tal cual).
WRAPPERS = {
    "xargs",
    "eval",
    "exec",
    "env",
    "sudo",
    "nohup",
    "time",
    "watch",
    "command",
    "builtin",
    "timeout",
    "nice",
    "doas",
}
PROGRAMS = ("kubectl", "argocd")
_PROGRAM_WORD = re.compile(r"\b(kubectl|argocd)\b")
_REFERENCE = re.compile(r"[/:@]|https://")
_SEPARATORS = re.compile(r"&&|\|\||[;|&)`\n]")


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    verb: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: kubectl {self.verb}"


def _flag_name(token: str) -> str:
    return token.split("=", 1)[0] if token.startswith("--") else token


def _verb(tokens: list[str], quoted: bool = False) -> tuple[str | None, int]:
    """El verbo de `kubectl` en `tokens` (lo que sigue a `kubectl`) y su posicion; `None` si no hay.

    Falla cerrado: una bandera que no es una global conocida se devuelve como verbo (`--bandera`); si la linea no se pudo leer entera (`quoted`) y el verbo o el valor
    de una bandera traen comillas sueltas, se devuelve `<unparsable>`.
    """
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if quoted and ('"' in token or "'" in token):
            return UNPARSABLE, i
        if token in GLOBAL_WITH_VALUE:
            i += 2
        elif token.startswith("-"):
            if token in GLOBAL_FLAGS or (
                token.startswith("--") and "=" in token and _flag_name(token) in GLOBAL_WITH_VALUE
            ):
                i += 1
            else:
                return token, i
        else:
            return token, i
    return (UNPARSABLE if quoted else None), i


def _is_allowed(tokens: list[str], quoted: bool = False) -> tuple[bool, str]:
    verb, position = _verb(tokens, quoted)
    if verb is None:
        return True, ""
    if verb == "auth":
        sub = tokens[position + 1] if position + 1 < len(tokens) else ""
        return sub == "can-i", f"auth {sub}".strip()
    return verb in ALLOWED, verb


def _split(fragment: str) -> tuple[list[str], bool]:
    """Las palabras de un fragmento y si hubo que leerlo sin comillas (porque estaban sin cerrar)."""
    try:
        return shlex.split(fragment, comments=False), False
    except ValueError:
        return fragment.split(), True


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


def _indirect(prefix: str) -> bool:
    """El programa no se invoca tal cual: va en una asignacion (`K=kubectl`, `:=`), tras un envoltorio (`xargs`, `eval`...) o en una sustitucion asignada."""
    before = prefix.rstrip().rstrip("\"'")
    if before.endswith(("=", "$(which", "$(command -v", "`which")):
        return True
    if re.search(r"=\s*(\$\(|`)[^)`]*$", prefix) and not re.search(r"=\s*(\$\(|`)\s*$", prefix):
        return True  # F-06: `POD=$(kubectl get ...)` no es indirecta (el verbo de dentro se juzga igual); `K=$(which kubectl)` y `X=$(echo kubectl)` si
    words = re.findall(r"[\w.-]+", before)
    return bool(words) and words[-1] in WRAPPERS or bool(re.search(r"\beval\b", prefix))


def scan_text(text: str, name: str, base_line: int = 1) -> list[Finding]:
    """Las ordenes prohibidas en un texto (guion, Makefile, Markdown, Dockerfile o una cadena de Python).

    Cada aparicion de `kubectl` se juzga aparte, hasta el siguiente separador (`&&`, `||`, `;`, `|`, `&`, `)`, la comilla invertida o el fin de linea; la
    continuacion con `\\` ya viene unida). Lo que no se entiende (bandera global desconocida, comillas sin cerrar, el programa en una variable o tras
    `xargs`/`eval`) es un hallazgo. No es un analizador de shell.
    """
    findings: list[Finding] = []
    for number, line in _logical_lines(text, base_line):
        for match in _PROGRAM_WORD.finditer(line):
            program = match.group(1)
            if _indirect(line[: match.start()]):
                findings.append(Finding(name, number, f"{program} <indirect>"))
                continue
            tail = line[match.end() :]
            if Path(name).name == "Dockerfile" and _REFERENCE.match(tail.lstrip()):
                continue  # F-06: el binario como ruta o URL (`COPY ... /usr/local/bin/kubectl /...`): lo que sigue a `kubectl` ahi no es un argumento
            cut = _SEPARATORS.search(tail)
            tokens, quoted = _split(tail[: cut.start()] if cut else tail)
            if program == "argocd":
                if tail.strip():
                    findings.append(Finding(name, number, "argocd"))
                continue
            ok, verb = _is_allowed(tokens, quoted)
            if not ok:
                findings.append(Finding(name, number, verb))
    return findings


def _mentions(value: str) -> bool:
    return _PROGRAM_WORD.search(value) is not None


def _is_program_name(value: str) -> bool:
    return value.rsplit("/", 1)[-1] in PROGRAMS


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def scan_python(source: str, name: str) -> list[Finding]:
    """Cada cadena como texto; cada lista cuyo primer elemento es `kubectl`/`argocd` como orden; y fallan cerrado el nombre del programa en una variable,
    la concatenacion, el f-string, `%` y `.format`, y la lista cuyos elementos hasta el verbo no son literales."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [Finding(name, error.lineno or 1, UNPARSABLE)]
    findings = scan_text_lines(tree, name)
    parents = _parents(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.List | ast.Tuple) and node.elts:
            first = node.elts[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and _is_program_name(first.value)
            ):
                findings += _scan_command_list(node, first.value.rsplit("/", 1)[-1], name)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _mentions(node.value):
            findings += _scan_context(node, parents.get(node), name)
    return findings


def _scan_command_list(node: ast.List | ast.Tuple, program: str, name: str) -> list[Finding]:
    if program == "argocd":
        return [Finding(name, node.lineno, "argocd")]
    args: list[str] = []
    for element in node.elts[1:]:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            args.append(element.value)
        else:
            break
    verb, _ = _verb(args)
    if verb is None:
        return [Finding(name, node.lineno, OPAQUE)]
    ok, label = _is_allowed(args)
    return [] if ok else [Finding(name, node.lineno, label)]


def _scan_context(node: ast.Constant, parent: ast.AST | None, name: str) -> list[Finding]:
    """Una cadena que nombra `kubectl`/`argocd` solo es texto si no se arma con otras piezas ni se guarda en una variable."""
    value = str(node.value)
    if isinstance(parent, ast.JoinedStr):
        return [Finding(name, node.lineno, "<fstring>")]
    if isinstance(parent, ast.BinOp):
        return [Finding(name, node.lineno, "<concat>")]
    if isinstance(parent, ast.Attribute) and parent.attr in {"format", "format_map", "join"}:
        return [Finding(name, node.lineno, "<format>")]
    if _is_program_name(value) and not (
        isinstance(parent, ast.List | ast.Tuple) and parent.elts and parent.elts[0] is node
    ):
        return [Finding(name, node.lineno, "<variable>")]
    return []


def scan_text_lines(tree: ast.AST, name: str) -> list[Finding]:
    """En Python, cada cadena (tambien los docstrings) se revisa como texto, con el numero de linea de la cadena."""
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            findings += scan_text(node.value, name, node.lineno)
    return findings


def _is_python(path: Path, text: str) -> bool:
    return path.suffix == ".py" or (text.startswith("#!") and "python" in text.split("\n", 1)[0])


def scan_file(path: Path, name: str | None = None) -> list[Finding]:
    label = name or str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:  # un binario: no es texto que alguien ejecute como orden
        return []
    if (
        path.suffix == ".patch"
    ):  # F-06: en un parche se juzgan solo las lineas anadidas; el contexto de `flows.yaml` nombra el namespace de Argo CD en una lista
        text = "\n".join(
            line[1:] if line.startswith("+") and not line.startswith("+++") else ""
            for line in text.split("\n")
        )
    return scan_python(text, label) if _is_python(path, text) else scan_text(text, label)


def scan_tree(root: Path) -> list[Finding]:
    """Todo archivo de texto de `src/` y `demos/` (cualquier extension o ninguna), el `Makefile`, `README.md` y `Dockerfile`."""
    files: list[Path] = []
    for sub in ("src", "demos"):
        if (root / sub).is_dir():
            files += sorted(
                p
                for p in (root / sub).rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and ".pyc" != p.suffix
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


# --- Ronda 2 (F-01): la barrera falla cerrada. Lo que el detector no entiende es un hallazgo, no un pase. ---

CHAINED = [
    "kubectl get pods && kubectl delete pod x",
    "kubectl get ns; kubectl apply -f x.yaml",
    "kubectl get deploy x -o yaml | kubectl apply -f -",
    "kubectl get ns || kubectl delete ns x",
    "kubectl get ns && \\\n  kubectl apply -f x.yaml",
    "echo $(kubectl get ns) `kubectl delete ns x`",
    "bash -c 'kubectl get ns && kubectl apply -f x'",
]
INDIRECT_SHELL = [
    "K=kubectl\n$K apply -f x",
    'K="kubectl"\n$K apply -f x',
    "KUBECTL := kubectl\nt:\n\t$(KUBECTL) apply -f x",
    "K=$(which kubectl)\n$K apply -f x",
    "echo apply -f x | xargs kubectl",
    "eval kubectl apply -f x",
    'eval "$K apply"; K=kubectl',
    "sudo kubectl get pods",
    "A=argocd\n$A app sync",
    "echo app sync | xargs argocd",
    "kubectl --certificate-authority get apply",
    "kubectl --unknown-flag get pods",
    "kubectl auth --as can-i reconcile",
    "kubectl auth reconcile -f x",
    "kubectl auth",
    "kubectl --token 'a;b' apply -f x",
    'kubectl get "unterminated && kubectl apply',
]
INDIRECT_PYTHON = [
    'subprocess.run(["kubectl"] + ["apply", "-f", "x"])',
    'K = "kubectl"\nsubprocess.run([K, "delete", "pod", "x"])',
    'subprocess.run(f"kubectl {v} -f x", shell=True)',
    'subprocess.run("kubectl " + v, shell=True)',
    'subprocess.run("kubectl %s -f x" % v, shell=True)',
    'subprocess.run("kubectl {} -f x".format(v), shell=True)',
    'subprocess.run(["kubectl", *args])',
    'subprocess.run(["kubectl", verb, "x"])',
    'subprocess.run(["kubectl"])',
    'A = "argocd"\nsubprocess.run([A, "app", "sync"])',
    'subprocess.run(["xargs", "kubectl"])',
    'subprocess.run(["kubectl", "--certificate-authority", "get", "apply"])',
    'subprocess.run(["kubectl", "auth", "reconcile"])',
    'subprocess.run("kubectl get ns; kubectl apply -f x", shell=True)',
]
LEGIT_SHELL = [
    "kubectl get pods",
    "kubectl -n a get x | grep y",
    "kubectl get x && echo ok",
    "kubectl get a; kubectl get b",
    "kubectl get a | kubectl get b",
    "kubectl get pods \\\n  -o yaml",
    "kubectl auth can-i get pods",
    "kubectl --context kind-vectra -n a get pods",
    "kubectl --namespace=a get pods",
    "kubectl logs job/x --tail=5",
    "\t@kubectl -n a get pods",
    "echo 'se usa kubectl get y no el apply'",
    "kubectl get cm x -o jsonpath='{.data.a}'",
]
LEGIT_PYTHON = [
    'subprocess.run(["kubectl", "--context", "kind-vectra", "-n", "vectra-app", "get", "pods"])',
    'subprocess.run(["kubectl", "get", "pods", name], check=True)',
    'subprocess.run(["/usr/bin/kubectl", "auth", "can-i", "get", "pods"])',
    '"""Solo kubectl get y logs."""',
]


@pytest.mark.parametrize("text", CHAINED + INDIRECT_SHELL)
def test_f01_shell_forms_the_detector_does_not_understand_are_findings(text: str) -> None:
    assert scan_text(text, "x.sh") != []


@pytest.mark.parametrize("text", INDIRECT_PYTHON + [c for c in CHAINED[:3]])
def test_f01_python_forms_the_detector_does_not_understand_are_findings(text: str) -> None:
    source = text if text.startswith(("subprocess", "K =", "A =")) else f"x = {text!r}\n"
    assert scan_python(source, "x.py") != []


def test_f01_each_chained_kubectl_is_judged_on_its_own() -> None:
    findings = scan_text("kubectl delete a && kubectl apply -f x; kubectl get y | kubectl patch z", "x.sh")
    assert [f.verb for f in findings] == ["delete", "apply", "patch"]


@pytest.mark.parametrize("text", LEGIT_SHELL)
def test_f01_legitimate_shell_forms_still_pass(text: str) -> None:
    assert scan_text(text, "x.sh") == []


@pytest.mark.parametrize("text", LEGIT_PYTHON)
def test_f01_legitimate_python_forms_still_pass(text: str) -> None:
    assert scan_python(text + "\n", "x.py") == []


@pytest.mark.parametrize(
    "suffix", [".bash", ".zsh", ".ksh", ".txt", ".toml", ".cfg", ".env", ".json", ".j2", ".cmd"]
)
def test_f01_scan_tree_reads_every_text_file_not_a_list_of_extensions(tmp_path: Path, suffix: str) -> None:
    (tmp_path / "demos").mkdir()
    (tmp_path / "demos" / f"x{suffix}").write_text("kubectl delete pod x\n")
    assert [f.verb for f in scan_tree(tmp_path)] == ["delete"]


def test_f01_scan_tree_reads_files_without_extension_and_skips_binaries(tmp_path: Path) -> None:
    (tmp_path / "src" / "deep").mkdir(parents=True)
    (tmp_path / "src" / "deep" / "run").write_text("#!/bin/sh\nkubectl apply -f x\n")
    (tmp_path / "src" / "blob.bin").write_bytes(b"\xff\xfe\x00kubectl delete\x80")
    assert [f.verb for f in scan_tree(tmp_path)] == ["apply"]


def test_f01_a_python_file_that_does_not_parse_is_a_finding(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def (:\n")
    assert [f.verb for f in scan_tree(tmp_path)] == ["<unparsable>"]


# --- U12-T04 (F-06 de U12-T01, P-13): el detector se amplia, no se relaja ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["pod-substitution.sh", "Dockerfile", "argocd-context.patch"])
def test_f06_the_forms_that_are_accepted_have_a_fixture_in_allowed(name: str) -> None:
    assert scan_file(FIXTURES / "allowed" / name, name) == []


@pytest.mark.parametrize(
    ("name", "label", "verbs"),
    [
        ("pod-substitution-delete.sh", "x.sh", ["delete"]),
        ("assigned-binary.sh", "x.sh", ["kubectl <indirect>"]),
        ("which-binary.sh", "x.sh", ["kubectl <indirect>"]),
        ("variable-verb.sh", "x.sh", ["$V"]),
        ("nohup.sh", "x.sh", ["kubectl <indirect>"]),
        ("watch.sh", "x.sh", ["kubectl <indirect>"]),
        ("context-substitution.sh", "x.sh", None),
        ("added-apply.patch", "x.patch", ["apply"]),
        ("dockerfile-variable/Dockerfile", "Dockerfile", ["$V"]),
        ("dockerfile-word/Dockerfile", "Dockerfile", ["delete"]),
    ],
)
def test_f06_the_neighbouring_forms_keep_failing(name: str, label: str, verbs: list[str] | None) -> None:
    findings = scan_file(FIXTURES / "prohibited" / name, label)
    assert findings, name
    if verbs is not None:
        assert [f.verb for f in findings] == verbs


def test_f06_the_binary_as_a_path_is_accepted_only_in_a_dockerfile() -> None:
    line = "COPY --from=tools /usr/local/bin/kubectl /usr/local/bin/kubectl\n"
    assert scan_text(line, "Dockerfile") == [] and scan_text(line, "guion.sh") != []
    assert (
        scan_text("RUN kubectl $V x\n", "Dockerfile") != []
        and scan_text("RUN kubectl --foo x\n", "Dockerfile") != []
    )


def test_f06_a_patch_is_judged_by_its_added_lines_and_prose_with_the_bare_name_passes() -> None:
    assert scan_text("Solo se usa `kubectl`\nSe sincroniza en Argo CD", "README.md") == []
    assert scan_text("sincroniza la Application `network` en Argo CD, con prune\n", "demos/x.md") == []
