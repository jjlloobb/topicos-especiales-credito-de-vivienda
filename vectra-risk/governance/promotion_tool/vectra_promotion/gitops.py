"""PR de un solo commit firmado sobre los values de `model-serving` (BR-U4-09; NFR-U4-21), con la evidencia en el cuerpo del PR.

Usa `git` y `gh` con la identidad y la sesion del propio ingeniero. La evidencia son dos comandos de solo lectura: `helm template` del
chart de U6 (que valida los values contra `values.schema.json`) y el comando `kubectl diff` que el ingeniero pasa. Nada sincroniza ni
aplica: el PR lo fusiona una persona y Argo CD lo recoge.
"""

import hashlib
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vectra_promotion import values
from vectra_promotion.errors import PromotionError

Runner = Callable[[Sequence[str], Path, str | None], subprocess.CompletedProcess[str]]
ENVS = ("kind", "staging", "prod")
MAX_DIFF = 30_000


def system_runner(args: Sequence[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, input=stdin, capture_output=True, text=True, check=False)  # noqa: S603


@dataclass
class PromotionRepo:
    repo: Path
    diff_command: Sequence[str]
    env: str
    gitops: str = "vectra-risk/vectra-risk-gitops"
    chart: str = "vectra-risk/model-serving/chart"
    base: str = "main"
    remote: str = "origin"
    helm: str = "helm"
    gh: str = "gh"
    runner: Runner = field(default=system_runner)

    def __post_init__(self) -> None:
        if self.env not in ENVS:
            raise PromotionError("env_invalid")

    @property
    def values_path(self) -> Path:
        return self.repo / self.gitops / "values" / self.env / "model-serving.yaml"

    def _run(self, args: Sequence[str], stdin: str | None = None) -> str:
        done = self.runner(args, self.repo, stdin)
        if done.returncode != 0:
            raise PromotionError(f"command_failed:{args[0]}:{(done.stderr or '').strip().splitlines()[:1]}")
        return done.stdout

    def current(self) -> list[values.Entry]:
        try:
            return values.parse(self.values_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise PromotionError("values_file_not_found") from error

    def render(self, text: str) -> str:
        """`helm template` con los values del entorno y el archivo editado: valida el esquema antes de renderizar."""
        with tempfile.TemporaryDirectory() as tmp:
            edited = Path(tmp) / "model-serving.yaml"
            edited.write_text(text, encoding="utf-8")
            args = [self.helm, "template", "ms", str(self.repo / self.chart)]
            env_values = self.repo / self.gitops / "envs" / self.env / "values.yaml"
            if env_values.is_file():
                args += ["-f", str(env_values)]
            done = self.runner([*args, "-f", str(edited)], self.repo, None)
        if done.returncode != 0:
            raise PromotionError(f"helm_template_failed:{(done.stderr or '').strip().splitlines()[:1]}")
        return done.stdout

    def diff(self, rendered: str) -> str:
        """`kubectl diff` contra kind: sale 0 (sin cambios) o 1 (hay diferencias); otro codigo es un error."""
        done = self.runner(list(self.diff_command), self.repo, rendered)
        if done.returncode not in (0, 1):
            raise PromotionError(f"diff_failed:{done.returncode}")
        return done.stdout

    def evidence(self, rendered: str, diff: str) -> str:
        docs = [d for d in yaml.safe_load_all(rendered) if d]
        rows = []
        for d in docs:
            meta: dict[str, Any] = d.get("metadata", {})
            version = (meta.get("annotations") or {}).get("vectra.io/model-version-id", "")
            rows.append(f"| {d.get('kind')} | {meta.get('name')} | {meta.get('namespace', '')} | {version} |")
        shown = diff if len(diff) <= MAX_DIFF else diff[:MAX_DIFF] + "\n... (recortado)\n"
        digest = hashlib.sha256(rendered.encode()).hexdigest()
        return (
            f"### Evidencia\n\n`helm template` (sha256 del render completo: `{digest}`):\n\n"
            "| kind | nombre | namespace | model_version_id |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n"
            f"`kubectl diff` contra kind (solo lectura):\n\n```diff\n{shown or '(sin diferencias)'}\n```\n\n"
            "Este PR no sincroniza ni aplica nada: lo fusiona una persona y Argo CD lo recoge.\n"
        )

    def open_pr(self, kind: str, version: str, entries: Sequence[values.Entry], summary: str) -> str:
        """Un solo commit firmado con el archivo de values editado; empuja la rama y abre el PR con `gh`."""
        if not self.diff_command:
            raise PromotionError("diff_command_required")
        if self._run(["git", "status", "--porcelain"]).strip():
            raise PromotionError("working_tree_dirty")
        text = values.edit(self.values_path.read_text(encoding="utf-8"), entries)
        rendered = self.render(text)  # falla aqui, sin tocar la rama, si el esquema no admite el cambio
        body = self.evidence(rendered, self.diff(rendered))
        isvc = values.isvc_name(version)
        branch = f"promotion/{kind}-{isvc}-{self.env}"
        original = self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
        self._run(["git", "switch", "-c", branch, self.base])
        try:
            self.values_path.write_text(text, encoding="utf-8")
            self._run(["git", "add", str(self.values_path.relative_to(self.repo))])
            title = f"{summary} {isvc} ({version}) en {self.env}"
            self._run(["git", "commit", "-S", "-m", title, "-m", f"model_version_id: {version}\ninference_service: {isvc}"])
            if int(self._run(["git", "rev-list", "--count", f"{self.base}..HEAD"]).strip()) != 1:
                raise PromotionError("not_a_single_commit")
            self._run(["git", "push", "-u", self.remote, branch])
            url = self._run(
                [self.gh, "pr", "create", "--base", self.base, "--head", branch, "--title", title, "--body", body]
            ).strip()
        finally:
            self._run(["git", "switch", original])
        return url
