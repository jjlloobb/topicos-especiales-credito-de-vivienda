#!/usr/bin/env python3
"""Falla si un workflow aplica cambios a un cluster o un Dockerfile usa `latest` (NFR-U1-26, NFR-U1-41).

Analiza los bloques `run` (no lineas sueltas), las acciones compuestas y los scripts del repositorio que un
workflow invoca: `./x.sh`, `bash x.sh`, `python x.py` y `make objetivo`. Es deliberadamente conservador: un comando
que no se puede leer (`kubectl $VERBO`) cuenta como prohibido, y una cadena entre comillas se analiza como comando,
porque `bash -c "kubectl apply"` se ve igual que `echo "kubectl apply"`.
"""

import ast
import fnmatch
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import yaml

SELF = Path(__file__).resolve()
#: herramienta -> verbos prohibidos. `kubectl diff`, `helm template`, `helm lint` y `helm dependency` no estan.
VERBS = {
    "kubectl": {"apply", "create", "replace", "patch", "delete", "edit", "scale", "rollout", "annotate", "label", "set", "run", "expose", "autoscale", "drain", "cordon", "taint"},
    "helm": {"install", "upgrade", "rollback", "uninstall", "delete"},
    "terraform": {"apply", "destroy"},
    "tofu": {"apply", "destroy"},
}
#: argocd tiene dos niveles: `argocd app sync`.
ARGOCD_APP_VERBS = {"sync", "delete", "rollback", "set"}
ALL_VERBS = set().union(*VERBS.values(), ARGOCD_APP_VERBS)
#: Acciones de despliegue conocidas. `azure/setup-kubectl` y `helm/kind-action` no despliegan.
DEPLOY_ACTIONS = ["azure/k8s-deploy*", "helm/*-deploy*", "deliverybot/helm*", "actions-hub/kubectl*"]
SECRET_KUBE = re.compile(r"secrets\s*(?:\.\s*|\[\s*['\"])[A-Za-z0-9_-]*kube[A-Za-z0-9_-]*", re.I)
FROM = re.compile(r"^\s*FROM\s+(\S+)", re.I | re.M)
WHOLE_VARIABLE = re.compile(r"^\$(?:\{?(\w+)\}?|\((\w+)\))$")
ASSIGNMENT = re.compile(r"^(\w+)=(.*)$", re.S)
SEPARATORS = ";|&()`\n"
#: La carpeta del propio script, el modismo de `install-tools.sh` y compania.
HERE = re.compile(r"^\$\{?here\}?/")
SHELLS = {"bash", "sh", "dash", "zsh", "source", "."}
SCRIPT_SUFFIXES = {".sh", ".bash"}
DATA_SUFFIXES = {".yaml", ".yml", ".json", ".md", ".txt"}


def tokenize(script: str) -> Iterator[list[tuple[str, bool]]]:
    """Separa un script en comandos; cada palabra es (texto, estaba entre comillas).

    Lo hace a mano porque `shlex` falla con comillas sin cerrar y corta las palabras en un `#` interior.
    Un comentario solo empieza al inicio de una palabra, nunca dentro de comillas.
    """
    command: list[tuple[str, bool]] = []
    word: list[str] | None = None
    quoted = False
    backtick = False
    index = 0
    size = len(script)

    def close() -> None:
        nonlocal word, quoted
        if word is not None:
            command.append(("".join(word), quoted))
        word, quoted = None, False

    while index < size:
        char = script[index]
        if char == "\\":
            if script[index + 1 : index + 2] != "\n":
                word = (word or []) + [script[index + 1 : index + 2]]
            index += 2
        elif char in "'\"":
            end = index + 1
            piece: list[str] = []
            while end < size and script[end] != char:
                if char == '"' and script[end] == "\\" and end + 1 < size:
                    end += 1
                    if script[end] == "\n":
                        end += 1
                        continue
                piece.append(script[end])
                end += 1
            word = (word or []) + piece
            quoted = True
            index = end + 1
        elif char == "#" and word is None:
            newline = script.find("\n", index)
            index = size if newline < 0 else newline
        elif char in SEPARATORS:
            if char == "`":
                # Sustitucion de comando: para quien la recibe, la palabra no se puede leer.
                backtick = not backtick
                if backtick:
                    word = (word or []) + ["$"]
            close()
            if command:
                yield command
            command = []
            index += 1
        elif char.isspace():
            close()
            index += 1
        else:
            word = (word or []) + [char]
            index += 1
    close()
    if command:
        yield command


def is_flag(word: str) -> bool:
    return word.startswith("-") and word != "-"


def is_dynamic(word: str) -> bool:
    return "$" in word


def subcommands(arguments: list[str]) -> tuple[list[str], bool]:
    """Las palabras que pueden ser el subcomando, y si la ultima es seguro una posicional.

    Un flag sin `=` puede llevar su valor aparte (`-n prod`), asi que la palabra siguiente es ambigua: se conservan
    todas hasta la primera posicional que no viene tras un flag. `kubectl -n apply get` da un falso positivo; nunca
    al reves.
    """
    candidates: list[str] = []
    after_flag = False
    for word in arguments:
        if is_flag(word):
            after_flag = "=" not in word
            continue
        candidates.append(word)
        if not after_flag:
            return candidates, True
        after_flag = False
    return candidates, False


def verb_violation(tool: str, arguments: list[str], forbidden: set[str], piped: bool) -> str | None:
    candidates, certain = subcommands(arguments)
    hit = next((c for c in candidates if c in forbidden), None)
    if hit:
        return f"{tool} {hit}"
    unreadable = is_dynamic(candidates[-1]) if certain else any(is_dynamic(c) for c in candidates)
    if unreadable:
        return f"{tool} {candidates[-1]} (verbo no legible)"
    if piped and not candidates:
        return f"{tool} con el verbo tomado de la entrada"
    return None


def tool_violation(tool: str, arguments: list[str], piped: bool) -> str | None:
    if tool != "argocd":
        return verb_violation(tool, arguments, VERBS[tool], piped)
    candidates, _ = subcommands(arguments)
    if "app" in candidates:
        return verb_violation("argocd app", arguments[arguments.index("app") + 1 :], ARGOCD_APP_VERBS, piped)
    return verb_violation("argocd", arguments, set(), piped)


def command_violations(script: str, depth: int = 0) -> Iterator[str]:
    """Comandos prohibidos en un bloque de shell, sin seguir scripts."""
    variables: dict[str, str] = {}
    for command in tokenize(script):
        words = [text for text, _ in command]
        for text, was_quoted in command:
            match = ASSIGNMENT.match(text)
            if match and not is_dynamic(match.group(2)):
                variables[match.group(1)] = match.group(2)
            inner = match.group(2) if match else text
            if was_quoted and depth < 4 and re.search(r"\s", inner):
                # `bash -c "kubectl apply"`, `"$(helm upgrade)"`, `K="kubectl apply"`: tambien se lee como comando.
                yield from command_violations(inner, depth + 1)
        words = [_expand(w, variables) for w in words]
        for position, word in enumerate(words):
            name = word.rsplit("/", 1)[-1]
            piped = "xargs" in words[:position]
            if name in VERBS or name == "argocd":
                found = tool_violation(name, words[position + 1 :], piped)
                if found:
                    yield found
            elif WHOLE_VARIABLE.match(word) and position + 1 < len(words) and words[position + 1] in ALL_VERBS:
                # `$K apply`: la herramienta no se puede leer pero el verbo si.
                yield f"{word} {words[position + 1]} (herramienta no legible)"


def _expand(word: str, variables: dict[str, str]) -> str:
    match = WHOLE_VARIABLE.match(word)
    if match:
        return variables.get(match.group(1) or match.group(2), word)
    return word


# --- Scripts y Makefiles que un workflow invoca


def strings_in_python(source: str) -> Iterator[str]:
    """Comandos en un script de Python: listas de cadenas y cadenas pasadas a un llamado."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.List | ast.Tuple):
            parts = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if parts:
                yield " ".join(parts)
        elif isinstance(node, ast.Call):
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    yield argument.value


def parse_makefile(path: Path) -> tuple[dict[str, tuple[list[str], list[str]]], str | None]:
    """Objetivos -> (prerrequisitos, recetas), con las variables simples expandidas."""
    text = path.read_text(encoding="utf-8").replace("\\\n", " ")
    variables: dict[str, str] = {"CURDIR": str(path.parent), "MAKE": "make"}
    targets: dict[str, tuple[list[str], list[str]]] = {}
    first: str | None = None
    current: list[str] = []

    def expand(value: str) -> str:
        value = value.replace("$(dir $(lastword $(MAKEFILE_LIST)))", f"{path.parent}/")
        for _ in range(5):
            value = re.sub(r"\$\((\w+)\)", lambda m: variables.get(m.group(1), m.group(0)), value)
        value = re.sub(r"\$\(abspath ([^()]*)\)", lambda m: str(Path(m.group(1)).resolve()), value)
        return value.replace("$$", "$")

    for line in text.splitlines():
        if line.startswith("\t"):
            for target in current:
                targets[target][1].append(line.lstrip("\t@-+ "))
            continue
        stripped = line.split("#", 1)[0].rstrip()
        assignment = re.match(r"^(\w+)\s*(?::=|\?=|=)\s*(.*)$", stripped)
        if assignment:
            variables[assignment.group(1)] = expand(assignment.group(2))
            continue
        rule = re.match(r"^([^:\s][^:=]*):(?!=)\s*(.*)$", stripped)
        if rule:
            current = rule.group(1).split()
            for target in current:
                targets.setdefault(target, ([], []))[0].extend(rule.group(2).split())
                if first is None and not target.startswith("."):
                    first = target
        elif stripped:
            current = []
    expanded = {k: ([expand(p) for p in prereqs], [expand(r) for r in recipes]) for k, (prereqs, recipes) in targets.items()}
    return expanded, first


class Scanner:
    """Sigue los scripts del repositorio que invoca un bloque de shell."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo.resolve()
        self.seen: set[tuple[str, ...]] = set()

    def resolve(self, name: str, cwd: Path) -> Path | None:
        for base in (cwd, self.repo):
            candidate = (base / name).resolve()
            if candidate.is_file() and candidate.is_relative_to(self.repo):
                return candidate
        return None

    def script(self, path: Path, origin: str) -> Iterator[str]:
        key = (str(path),)
        if key in self.seen or path == SELF:
            return
        self.seen.add(key)
        where = f"{origin} -> {path.relative_to(self.repo)}"
        try:
            source = path.read_text(encoding="utf-8")
            if path.suffix == ".py":
                for text in strings_in_python(source):
                    yield from (f"{where}: {v}" for v in command_violations(text))
            else:
                yield from self.shell(source, path.parent, where)
        except (UnicodeDecodeError, SyntaxError) as error:
            yield f"{where}: no se puede analizar: {error}"

    def make(self, arguments: list[str], cwd: Path, origin: str) -> Iterator[str]:
        directory = cwd
        makefile: Path | None = None
        targets: list[str] = []
        skip = None
        for index, word in enumerate(arguments):
            if skip == index:
                continue
            if word == "-C" and index + 1 < len(arguments):
                directory = (cwd / arguments[index + 1]).resolve()
                skip = index + 1
            elif word.startswith("-C") and len(word) > 2:
                directory = (cwd / word[2:]).resolve()
            elif word == "-f" and index + 1 < len(arguments):
                makefile = (directory / arguments[index + 1]).resolve()
                skip = index + 1
            elif not is_flag(word) and "=" not in word:
                targets.append(word)
        makefile = makefile or directory / "Makefile"
        if not makefile.is_file():
            yield f"{origin}: make sin Makefile legible en {directory}"
            return
        rules, first = parse_makefile(makefile)
        pending = targets or ([first] if first else [])
        if not targets and not first:
            yield f"{origin}: {makefile} sin objetivos"
        while pending:
            target = pending.pop()
            key = (str(makefile), target)
            if key in self.seen:
                continue
            self.seen.add(key)
            if target not in rules:
                yield f"{origin}: make {target} no existe en {makefile.relative_to(self.repo)}"
                continue
            prerequisites, recipes = rules[target]
            pending += prerequisites
            where = f"{origin} -> make {target}"
            for recipe in recipes:
                yield from self.shell(recipe, makefile.parent, where)

    def shell(self, script: str, cwd: Path, origin: str) -> Iterator[str]:
        yield from (f"{origin}: {v}" for v in command_violations(script))
        for command in tokenize(script):
            words = [text for text, _ in command]
            if words[0] == "cd" and len(words) > 1 and not is_dynamic(words[1]):
                target = (cwd / words[1]).resolve()
                if target.is_dir():
                    cwd = target
                continue
            for position, word in enumerate(words):
                if word.rsplit("/", 1)[-1] == "make" and position == _command_position(words):
                    yield from self.make(words[position + 1 :], cwd, origin)
                    break
                word = HERE.sub("./", word)
                if (cwd / word).is_dir():
                    continue
                # Un archivo de datos como argumento (`cp ./x-$env.yaml`) no se ejecuta.
                if position != _command_position(words) and Path(word).suffix in DATA_SUFFIXES:
                    continue
                after_shell = position > 0 and words[position - 1] in SHELLS and not is_flag(word)
                if Path(word).suffix in SCRIPT_SUFFIXES or word.endswith(".py") or word.startswith("./") or after_shell:
                    found = self.resolve(word, cwd)
                    if found:
                        yield from self.script(found, origin)
                    elif word.startswith("./") or after_shell:
                        yield f"{origin}: no se puede leer el script {word}"


def _command_position(words: list[str]) -> int:
    """Salta `VAR=x` y los lanzadores que preceden al comando real."""
    for index, word in enumerate(words):
        if not ASSIGNMENT.match(word) and word not in {"uv", "run", "env", "sudo", "exec", "time", "command"}:
            return index
    return len(words)


# --- Workflows y acciones


def steps_of(document: Any) -> Iterator[tuple[dict[str, Any], str | None]]:
    """Cada paso con el `working-directory` que hereda."""
    if not isinstance(document, dict):
        return
    default = ((document.get("defaults") or {}).get("run") or {}).get("working-directory")
    for job in (document.get("jobs") or {}).values():
        if isinstance(job, dict):
            inherited = ((job.get("defaults") or {}).get("run") or {}).get("working-directory", default)
            for step in job.get("steps") or []:
                yield step, inherited
            # Un job que llama a un workflow reutilizable tambien es un `uses`.
            if "uses" in job:
                yield {"uses": job["uses"], "with": job.get("with")}, inherited
    for step in (document.get("runs") or {}).get("steps") or []:
        yield step, None


def strings_of(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings_of(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_of(item)


def deploy_action(uses: str) -> bool:
    name = uses.split("@")[0].lower()
    return any(fnmatch.fnmatch(name, pattern) for pattern in DEPLOY_ACTIONS)


def without_expressions(script: str) -> str:
    """`${{ ... }}` lo sustituye GitHub antes del shell: es una palabra que no se puede leer, sin espacios."""
    return re.sub(r"\$\{\{.*?\}\}", "$GITHUB_EXPRESSION", script, flags=re.S)


def local_action_violations(uses: str, root: Path, label: str) -> list[str]:
    target = root / uses
    if target.is_file():
        return []
    if not any((target / name).is_file() for name in ("action.yml", "action.yaml")):
        return [f"{label}: no se puede leer la accion local {uses}"]
    return []


def repo_of(folder: Path) -> Path:
    """La raiz del repositorio es la carpeta que contiene `.github`."""
    resolved = folder.resolve()
    for candidate in [resolved, *resolved.parents]:
        if candidate.name == ".github":
            return candidate.parent
    return resolved


def yaml_files(folder: Path) -> Iterable[Path]:
    return sorted(p for p in folder.rglob("*") if p.suffix in {".yml", ".yaml"})


def workflow_violations(folder: Path, repo: Path | None = None) -> list[str]:
    """Violaciones en una carpeta de workflows o acciones. Una carpeta ausente o vacia es un error, no un aprobado."""
    if not folder.is_dir():
        return [f"{folder}: la carpeta no existe"]
    files = list(yaml_files(folder))
    if not files:
        return [f"{folder}: sin workflows que revisar"]
    root = (repo or repo_of(folder)).resolve()
    scanner = Scanner(root)
    found: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        found += [f"{path}: secreto de cluster: {m.group(0)}" for m in SECRET_KUBE.finditer(text)]
        document = yaml.safe_load(text)
        for step, inherited in steps_of(document):
            label = f"{path}: {step.get('name') or step.get('uses') or 'run'}"
            uses = step.get("uses")
            if uses and deploy_action(str(uses)):
                found.append(f"{label}: accion de despliegue {uses}")
            for value in strings_of(step.get("with")):
                found += [f"{label}: {v}" for v in command_violations(without_expressions(value))]
            if isinstance(uses, str) and uses.startswith("./"):
                found += local_action_violations(uses, root, label)
            if "run" in step:
                directory = step.get("working-directory", inherited)
                cwd = root / directory if isinstance(directory, str) and "$" not in directory else root
                found += scanner.shell(without_expressions(str(step["run"])), cwd, label)
    return found


def dockerfile_violations(root: Path) -> list[str]:
    if not root.is_dir():
        return [f"{root}: la carpeta no existe"]
    found = []
    for path in sorted(root.rglob("Dockerfile*")):
        if "node_modules" in path.parts or ".venv" in path.parts:
            continue
        for image in FROM.findall(path.read_text(encoding="utf-8")):
            base = image.split("@")[0]
            if "@sha256:" not in image and (base.endswith(":latest") or ":" not in base.split("/")[-1]):
                found.append(f"{path}: imagen sin version fija: {image}")
    return found


def main(argv: list[str]) -> int:
    if not argv:
        print("uso: forbidden_steps.py [--dockerfiles DIR | CARPETA...]")
        return 2
    if argv[0] == "--dockerfiles":
        problems = dockerfile_violations(Path(argv[1]))
    else:
        problems = [v for folder in argv for v in workflow_violations(Path(folder))]
    if problems:
        print("\n".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
