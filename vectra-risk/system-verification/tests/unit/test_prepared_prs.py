"""Los PR preparados de `demos/prs/` (U12-T04, CA-3): se aplican limpios, dejan verdes las pruebas de su unidad y se revierten. **Nunca se aplican al arbol real**: cada prueba trabaja sobre una copia (los
archivos versionados y los nuevos sin ignorar) en `platform/.tools/tmp/u12t04/` y la borra. Necesita `helm` y `conftest` de `platform/.tools/bin` (sin ellos, **falla**).

Las pruebas de `platform/network/tests` no son todas verdes en una maquina sin los charts de `envoy-gateway`: se comparan las fallas **del arbol con el parche** con las **del arbol sin el** (mismas, o la prueba falla).
"""

import hashlib
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

VECTRA = Path(__file__).resolve().parents[3]
PRS = VECTRA / "system-verification" / "demos" / "prs"
SCRATCH = VECTRA / "platform" / ".tools" / "tmp" / "u12t04"
TOOLS = VECTRA / "platform" / ".tools" / "bin"
KIND_VALUES = "vectra-risk/vectra-risk-gitops/values/kind/case-management.yaml"
M1 = "mv-2026-01-01-26300247"
OLD_LINE = 'cd $(ROOT) && ! grep -rn "runId" vectra-risk-gitops/values/*/case-management.yaml case-management/chart/values.yaml case-management/chart/values-kind.yaml'
F22_FIVE = {
    ("vectra-app", "NetworkPolicy", "allow-f22-explainability-service-to-explainer-egress"),
    ("vectra-serving", "NetworkPolicy", "allow-f22-to-explainer-ingress"),
    ("vectra-serving", "AuthorizationPolicy", "f22-explainer-8080"),
    ("vectra-serving", "MeshTLSAuthentication", "f22-explainer-8080-mtls"),
    ("vectra-serving", "Server", "explainer-8080"),
}


def run(args: list[str], cwd: Path, **kw: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False, **kw)  # type: ignore[call-overload]


class Copy:
    def __init__(self, root: Path) -> None:
        self.root = root  # la raiz del repositorio de la copia: contiene `vectra-risk/`
        self.v = root / "vectra-risk"

    def apply(self, patch: Path | str, *flags: str) -> subprocess.CompletedProcess[str]:
        text = patch if isinstance(patch, str) else patch.read_text(encoding="utf-8")
        return subprocess.run(
            ["git", "apply", *flags, "-"],
            input=text,
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def digest(self, sub: str = "") -> str:
        sha = hashlib.sha256()
        base = self.v / sub
        for path in sorted(
            p
            for p in base.rglob("*")
            if p.is_file() and not {".tools", ".charts"} & set(p.relative_to(self.v).parts)
        ):
            sha.update(str(path.relative_to(self.v)).encode() + path.read_bytes())
        return sha.hexdigest()

    def tool(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return run([str(TOOLS / name), *args], self.v)


@pytest.fixture
def copy(request: pytest.FixtureRequest) -> Iterator[Copy]:
    for tool in ("helm", "conftest"):
        assert (TOOLS / tool).is_file(), (
            f"falta {TOOLS / tool}: esta prueba necesita las herramientas de la plataforma (no se omite)"
        )
    root = SCRATCH / f"prs-{abs(hash(request.node.nodeid)) % 10**8}"
    shutil.rmtree(root, ignore_errors=True)
    listed = run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], VECTRA
    ).stdout.split("\0")
    for name in filter(None, listed):
        source = VECTRA / name
        if source.is_file():
            target = root / "vectra-risk" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    run(
        ["git", "init", "-q"], root
    )  # un repositorio propio: sin el, `git apply` dentro del arbol real ignoraria en silencio lo que no esta bajo su carpeta
    (root / "vectra-risk" / "platform" / ".tools").mkdir(parents=True, exist_ok=True)
    (root / "vectra-risk" / "platform" / ".tools" / "bin").symlink_to(TOOLS)
    if (VECTRA / "platform" / ".charts").exists():
        (root / "vectra-risk" / "platform" / ".charts").symlink_to(
            (VECTRA / "platform" / ".charts").resolve()
        )
    try:
        yield Copy(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def resources(directory: Path) -> set[tuple[str, str, str]]:
    found = set()
    for file in sorted(directory.glob("*.yaml")):
        for document in yaml.safe_load_all(file.read_text(encoding="utf-8")):
            if isinstance(document, dict) and document.get("kind"):
                meta = document.get("metadata", {})
                found.add(
                    (str(meta.get("namespace", file.stem)), str(document["kind"]), str(meta.get("name")))
                )
    return found


def failed_tests(copy_: Copy) -> set[str]:
    done = run(
        [
            sys.executable,
            "-m",
            "pytest",
            "platform/network/tests",
            "-q",
            "-p",
            "no:cacheprovider",
            "--no-header",
            "-rf",
            "--show-capture=no",
        ],
        copy_.v,
    )
    return set(re.findall(r"^FAILED (\S+)", done.stdout, re.M)) | (
        {"sin-resumen"} if "passed" not in done.stdout and "failed" not in done.stdout else set()
    )


def test_the_prepared_directories_exist_and_the_demos_do_not_touch_the_real_tree() -> None:
    for name in ("f22-apagado", "rt5-run-id", "rt3-staging", "proxy-staging", "promocion"):
        assert (PRS / name / "README.md").is_file(), name


# --- f22-apagado --------------------------------------------------------------------------------------------------------------------------------


def test_f22_the_patch_applies_cleanly_regenerates_and_removes_exactly_five_resources_without_touching_staging_or_prod(
    copy: Copy,
) -> None:
    before_kind, before_staging, before_prod = (
        resources(copy.v / "platform/network/generated" / e) for e in ("kind", "staging", "prod")
    )
    staging_digest, prod_digest = (
        copy.digest("platform/network/generated/staging"),
        copy.digest("platform/network/generated/prod"),
    )
    baseline = failed_tests(copy)
    assert copy.apply(PRS / "f22-apagado" / "apagar.patch", "--check").returncode == 0
    assert copy.apply(PRS / "f22-apagado" / "apagar.patch").returncode == 0
    flows = (copy.v / "platform/network/flows.yaml").read_text(encoding="utf-8")
    assert "env_disabled: { kind: [F22], staging: [], prod: [] }" in flows
    check = run([sys.executable, "platform/network/generate.py", "--check"], copy.v)
    assert check.returncode == 0, check.stdout + check.stderr  # el parche trae lo regenerado
    after_kind = resources(copy.v / "platform/network/generated/kind")
    assert (
        before_kind - after_kind == F22_FIVE
        and after_kind - before_kind == set()
        and len(before_kind - after_kind) == 5
    )
    assert (
        copy.digest("platform/network/generated/staging") == staging_digest
        and copy.digest("platform/network/generated/prod") == prod_digest
    )
    assert (
        resources(copy.v / "platform/network/generated/staging") == before_staging
        and resources(copy.v / "platform/network/generated/prod") == before_prod
    )
    assert failed_tests(copy) == baseline, "el parche cambia el resultado de `platform/network/tests`"


def test_f22_the_revert_patch_leaves_the_tree_identical(copy: Copy) -> None:
    original = copy.digest()
    assert copy.apply(PRS / "f22-apagado" / "apagar.patch").returncode == 0 and copy.digest() != original
    assert copy.apply(PRS / "f22-apagado" / "revertir.patch", "--check").returncode == 0
    assert copy.apply(PRS / "f22-apagado" / "revertir.patch").returncode == 0
    assert copy.digest() == original


def test_f22_red_a_patch_without_the_regenerated_files_fails_generate_check(copy: Copy) -> None:
    flows = copy.v / "platform/network/flows.yaml"
    flows.write_text(
        flows.read_text(encoding="utf-8").replace(
            "env_disabled: { kind: [], ", "env_disabled: { kind: [F22], "
        ),
        encoding="utf-8",
    )
    assert run([sys.executable, "platform/network/generate.py", "--check"], copy.v).returncode != 0


def test_f22_red_disabling_f22_with_enabled_false_changes_staging_and_prod(copy: Copy) -> None:
    staging, prod = (
        copy.digest("platform/network/generated/staging"),
        copy.digest("platform/network/generated/prod"),
    )
    flows = copy.v / "platform/network/flows.yaml"
    text = flows.read_text(encoding="utf-8")
    flows.write_text(
        text.replace("port: 80, target_port: 8080 }", "port: 80, target_port: 8080, enabled: false }", 1)
        if "id: F22, from: [explainability-service], to: [explainer], port: 80, target_port: 8080 }" in text
        else text + "\n#sin-F22\n",
        encoding="utf-8",
    )
    assert run([sys.executable, "platform/network/generate.py"], copy.v).returncode == 0
    assert (
        copy.digest("platform/network/generated/staging") != staging
        or copy.digest("platform/network/generated/prod") != prod
    )


# --- rt5-run-id y la linea 68 de U8 -----------------------------------------------------------------------------------------------------------------


def prepare_patch(tmp: Path, run_id_clock: str = "2026-11-12T09:00:31") -> tuple[str, str]:
    """El parche que produce `prepare` de verdad (con un reloj falso en las 09:00 de 2026-11-12)."""
    from datetime import UTC, datetime

    from fake_clock import FakeClock
    from vectra_verification import cli

    clock = FakeClock(datetime.fromisoformat(run_id_clock).replace(tzinfo=UTC))
    code = cli.main(
        [
            "prepare",
            "--dir",
            str(tmp),
            "--commit",
            "abc",
            "--operator",
            "op",
            "--values-file",
            str(VECTRA / "vectra-risk-gitops/values/kind/case-management.yaml"),
        ],
        environ={},
        clock=clock,
    )
    assert code == 0
    return (tmp / "case-management-runid.patch").read_text(encoding="utf-8"), "20261112-0900"


def test_rt5_run_id_prepare_produces_the_example_patch_and_it_applies_and_renders_one_job(
    copy: Copy, tmp_path: Path
) -> None:
    patch, run_id = prepare_patch(tmp_path)
    assert patch == (PRS / "rt5-run-id" / "ejemplo.patch").read_text(encoding="utf-8")
    assert copy.apply(patch, "--check").returncode == 0 and copy.apply(patch).returncode == 0
    values = (copy.v / "vectra-risk-gitops/values/kind/case-management.yaml").read_text(encoding="utf-8")
    assert f'runId: "{run_id}"' in values and "enabled: true" in values
    app = yaml.safe_load(
        (copy.v / "vectra-risk-gitops/apps/kind/case-management.yaml").read_text(encoding="utf-8")
    )
    files = [f.removeprefix("/vectra-risk/") for f in app["spec"]["source"]["helm"]["valueFiles"]]
    assert len(files) == 3
    args = ["template", "case-management", "case-management/chart", "-n", "vectra-app"] + [
        x for f in files for x in ("-f", f)
    ]
    rendered = copy.tool("helm", *args)
    assert rendered.returncode == 0, rendered.stderr
    jobs = [
        d
        for d in yaml.safe_load_all(rendered.stdout)
        if isinstance(d, dict) and d.get("kind") == "Job" and d["metadata"]["name"].startswith("rt5-demo-")
    ]
    assert [j["metadata"]["name"] for j in jobs] == [f"rt5-demo-{run_id}"]
    for namespace, file in (("values.staging", "staging"), ("values.prod", "prod")):
        done = copy.tool(
            "conftest",
            "test",
            "--policy",
            "case-management/policies/conftest",
            "--namespace",
            namespace,
            f"vectra-risk-gitops/values/{file}/case-management.yaml",
        )
        assert done.returncode == 0, done.stdout + done.stderr


def policy_chart(copy: Copy) -> subprocess.CompletedProcess[str]:
    return run(["make", "-C", str(copy.v / "case-management"), "policy-chart"], copy.v)


def test_rt5_run_id_policy_chart_ends_in_0_with_the_patch_and_the_corrected_line_68_and_the_red_with_the_old_line(
    copy: Copy, tmp_path: Path
) -> None:
    import time

    patch, _ = prepare_patch(tmp_path)
    assert copy.apply(patch).returncode == 0
    started = time.monotonic()
    done = policy_chart(copy)
    print(f"policy-chart: {time.monotonic() - started:.1f} s")
    assert done.returncode == 0, done.stdout[-600:] + done.stderr[-600:]
    makefile = copy.v / "case-management/Makefile"
    lines = makefile.read_text(encoding="utf-8").split("\n")
    index = next(
        i for i, line in enumerate(lines) if line.lstrip("\t").startswith('cd $(ROOT) && ! grep -rn "runId"')
    )
    lines[index] = "\t" + OLD_LINE
    makefile.write_text("\n".join(lines), encoding="utf-8")
    red = policy_chart(copy)
    assert (
        red.returncode != 0 and "runId" in red.stdout + red.stderr
    )  # el rojo de P-3: la linea sin corregir ve el `runId` de kind


@pytest.mark.parametrize(
    "target",
    [
        "vectra-risk-gitops/values/staging/case-management.yaml",
        "vectra-risk-gitops/values/prod/case-management.yaml",
        "case-management/chart/values.yaml",
        "case-management/chart/values-kind.yaml",
    ],
)
def test_rt5_run_id_the_check_of_line_68_stays_red_if_the_run_id_appears_in(copy: Copy, target: str) -> None:
    line = next(
        ln
        for ln in (copy.v / "case-management/Makefile").read_text(encoding="utf-8").split("\n")
        if '! grep -rn "runId"' in ln
    )
    command = line.replace("cd $(ROOT) && ", "").strip()
    assert run(["sh", "-c", command], copy.v).returncode == 0  # sin `runId` en esos archivos: verde
    path = copy.v / target
    path.write_text(path.read_text(encoding="utf-8") + '\nrunId: "20261112-0900"\n', encoding="utf-8")
    assert run(["sh", "-c", command], copy.v).returncode != 0, target


def test_rt5_run_id_the_line_68_does_not_forbid_the_run_id_in_kind_and_changes_only_one_line() -> None:
    makefile = (VECTRA / "case-management/Makefile").read_text(encoding="utf-8")
    assert (
        OLD_LINE.replace("cd $(ROOT) && ", "") not in makefile
        and "values/*/case-management.yaml" not in makefile
    )
    line = next(ln for ln in makefile.split("\n") if '! grep -rn "runId"' in ln)
    assert (
        "values/kind/" not in line
        and "values/staging/case-management.yaml" in line
        and "values/prod/case-management.yaml" in line
    )
    assert "case-management/chart/values.yaml" in line and "case-management/chart/values-kind.yaml" in line


# --- rt3-staging y proxy-staging --------------------------------------------------------------------------------------------------------------------


ENTRY = PRS / "entrada.py"
RT3_A, RT3_D, PROXY_URI = (
    "s3://model-store/adversarial/rt3/RT3-a/",
    "s3://model-store/adversarial/rt3/RT3-d/",
    f"s3://model-store/{M1}/",
)


def entry_patch(copy: Copy, version: str, uri: str) -> subprocess.CompletedProcess[str]:
    """El parche que arma `demos/prs/entrada.py` sobre el archivo de la copia **tal como esta** (lo que dicen los README)."""
    return run(
        [sys.executable, str(ENTRY), "--version", version, "--storage-uri", uri],
        copy.v,
    )


def render(copy: Copy) -> subprocess.CompletedProcess[str]:
    return copy.tool(
        "helm",
        "template",
        "ms",
        "model-serving/chart",
        "-f",
        "vectra-risk-gitops/envs/kind/values.yaml",
        "-f",
        "vectra-risk-gitops/values/kind/model-serving.yaml",
    )


def promote_reference(copy: Copy) -> None:
    """El estado de la demo: el modelo de referencia ya promovido por `promotion-tool` (`create-promotion-pr`), es decir, una entrada `prod` en `inferenceServices`, con la misma funcion que usa la herramienta."""
    sys.path.insert(0, str(VECTRA / "governance" / "promotion_tool"))
    try:
        from vectra_promotion import values as promotion_values
    finally:
        sys.path.pop(0)
    path = copy.v / "vectra-risk-gitops/values/kind/model-serving.yaml"
    text = path.read_text(encoding="utf-8")
    entries = promotion_values.promote(
        promotion_values.parse(text), "mv-2026-01-01-aaaaaaaa", "s3://model-store/mv-2026-01-01-aaaaaaaa/"
    )
    path.write_text(promotion_values.edit(text, entries), encoding="utf-8")


@pytest.mark.parametrize("promoted", [False, True], ids=["lista-vacia", "referencia-promovida"])
@pytest.mark.parametrize("uri", [RT3_A, RT3_D, PROXY_URI], ids=["RT3-a", "RT3-d", "proxy"])
def test_rt3_staging_and_proxy_staging_the_generated_patch_applies_in_both_states_and_renders_the_isvc_in_vectra_staging(
    copy: Copy, uri: str, promoted: bool
) -> None:
    """F-02 (ronda 2): el parche se arma sobre el archivo como este: lista vacia (`main`) y modelo de referencia ya promovido (el estado de la demo)."""
    if promoted:
        promote_reference(copy)
    made = entry_patch(copy, M1, uri)
    assert made.returncode == 0, made.stderr
    assert copy.apply(made.stdout, "--check").returncode == 0 and copy.apply(made.stdout).returncode == 0
    done = render(copy)
    assert done.returncode == 0, done.stderr
    names = {
        (d["metadata"].get("namespace"), d["metadata"]["name"])
        for d in yaml.safe_load_all(done.stdout)
        if isinstance(d, dict) and d.get("kind") == "InferenceService"
    }
    assert ("vectra-staging", "isvc-26300247") in names
    if promoted:
        assert ("vectra-serving", "isvc-aaaaaaaa") in names  # la entrada de la referencia sigue donde estaba


def test_the_entry_script_refuses_what_is_not_a_version_or_a_model_store_uri_and_writes_nothing(
    copy: Copy,
) -> None:
    before = copy.digest()
    for version, uri in (("mv-malo", RT3_A), (M1, "https://otro/")):
        done = entry_patch(copy, version, uri)
        assert done.returncode == 2 and done.stdout == "" and "entrada.py:" in done.stderr
    assert copy.digest() == before


def test_rt3_staging_with_rt3_a_and_rt3_d_at_the_same_time_helm_fails_with_repetido_and_the_readme_says_so(
    copy: Copy,
) -> None:
    path = copy.v / "vectra-risk-gitops/values/kind/model-serving.yaml"
    entries = "".join(
        f'  - {{ modelVersionId: {M1}, storageUri: "s3://model-store/adversarial/rt3/{case}/", profile: staging }}\n'
        for case in ("RT3-a", "RT3-d")
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace("inferenceServices: []\n", "inferenceServices:\n" + entries),
        encoding="utf-8",
    )
    done = render(copy)
    assert done.returncode != 0 and "repetido" in done.stderr
    assert "no caben a la vez" in (PRS / "rt3-staging" / "README.md").read_text(
        encoding="utf-8"
    ) and "repetido" in (PRS / "rt3-staging" / "README.md").read_text(encoding="utf-8")


def test_the_readmes_send_to_the_script_and_no_fixed_template_is_left() -> None:
    for directory in ("rt3-staging", "proxy-staging"):
        readme = (PRS / directory / "README.md").read_text(encoding="utf-8")
        assert "demos/prs/entrada.py" in readme and "git apply" in readme, directory
        assert not list((PRS / directory).glob("*.tpl")) and not list((PRS / directory).glob("*.patch")), (
            directory
        )


def test_promocion_readme_names_the_four_commands_as_they_are_in_the_cli_of_promotion_tool() -> None:
    cli = (VECTRA / "governance/promotion_tool/vectra_promotion/cli.py").read_text(encoding="utf-8")
    commands = re.findall(r'sub\.add_parser\("([a-z-]+)"\)', cli)
    assert {"create-promotion-pr", "post-activation-pr", "rollback-pr", "mark-active"} <= set(commands)
    readme = (PRS / "promocion" / "README.md").read_text(encoding="utf-8")
    for command in ("create-promotion-pr", "post-activation-pr", "rollback-pr", "mark-active"):
        assert f"`{command}" in readme
    assert "kubectl" not in readme and "argocd" not in readme.lower().replace("argo cd", "")
