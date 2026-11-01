"""CI de U1: permisos, evidencia, pasos prohibidos y las herramientas de aceptacion que citan los planes."""

import re
import subprocess
import sys
from pathlib import Path

import core_resources
import forbidden_steps as fs
import integration
import pytest
import rego_fixtures
import rollback_note
import test_links as links
import test_runbooks as runbooks
import test_traceability as traceability
import test_waves as waves
import yaml

PLATFORM = Path(__file__).resolve().parents[1]
ROOT = PLATFORM.parent
REPO = ROOT.parent
WORKFLOWS = REPO / ".github/workflows"
MAKEFILE = (PLATFORM / "Makefile").read_text(encoding="utf-8")
PLAN_FOLDER = ROOT / "aidlc-docs/construction/plans"


def workflow(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def triggers(document):
    # YAML 1.1 lee `on` como True.
    return document[True]


def steps(document):
    return [step for job in document["jobs"].values() for step in job.get("steps", [])]


def run_blocks(document):
    return "\n".join(str(step.get("run", "")) for step in steps(document))


def recipe(target):
    match = re.search(rf"^{target}:.*\n((?:\t.*\n)+)", MAKEFILE, flags=re.M)
    assert match, target
    return match.group(1)


# --- 1. Lo que el repositorio necesita no puede quedar ignorado por Git


def sourced_files(script):
    text = script.read_text(encoding="utf-8")
    return [script.parent / name for name in re.findall(r'^\s*(?:source|\.)\s+"?\$here/([^"\s]+)"?', text, flags=re.M)]


def git_ignored(path):
    return subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=REPO, check=False).returncode == 0


def test_sourced_files_are_not_git_ignored():
    scripts = ["install-tools.sh", "charts.sh", "render.sh"]
    sourced = [f for name in scripts for f in sourced_files(PLATFORM / name)]
    assert PLATFORM / "tools.env" in sourced
    for path in sourced:
        assert path.is_file(), path
        assert not git_ignored(path), path


def test_no_platform_or_gitops_file_is_git_ignored():
    """Un manifiesto ignorado funciona en local y no existe al clonar: `secrets.yaml` y `*.env` de la raiz lo causan."""
    listed = subprocess.run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "vectra-risk/platform", "vectra-risk/vectra-risk-gitops"],
        cwd=REPO, check=True, capture_output=True, text=True,
    ).stdout.split()  # fmt: skip
    build_output = {".tools", ".charts", "__pycache__"}
    assert [f for f in listed if not build_output & set(Path(f).parts) and not f.endswith("kind/encryption-config.yaml")] == []


# --- 2. Permisos de los workflows reutilizables


def permissions_of(holder):
    declared = holder.get("permissions")
    return declared if isinstance(declared, dict) else {}


LEVEL = {"none": 0, "read": 1, "write": 2}


def exceeding(granted, needed):
    return {scope: level for scope, level in needed.items() if LEVEL[level] > LEVEL[granted.get(scope, "none")]}


def callers():
    """(archivo, job, permisos concedidos, workflow reutilizable llamado)."""
    for path in sorted(WORKFLOWS.glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in document["jobs"].items():
            uses = job.get("uses", "")
            if uses.startswith("./.github/workflows/"):
                granted = job["permissions"] if "permissions" in job else permissions_of(document)
                yield path.name, name, granted, Path(uses).name


def needed_by(name):
    document = workflow(name)
    needed = dict(permissions_of(document))
    for job in document["jobs"].values():
        for scope, level in permissions_of(job).items():
            needed[scope] = max(needed.get(scope, "none"), level, key=LEVEL.__getitem__)
    return needed


def test_no_reusable_workflow_asks_more_than_its_callers_grant():
    found = list(callers())
    assert {c[3] for c in found} >= {"supply-chain.yml", "policies.yml", "evidence.yml", "tests.yml", "forbidden-steps.yml"}
    for source, job, granted, target in found:
        assert not exceeding(granted, needed_by(target)), (source, job, target)


def test_permission_check_detects_an_excess():
    assert exceeding({"contents": "read"}, {"contents": "read", "id-token": "write"}) == {"id-token": "write"}
    assert not exceeding({"contents": "write"}, {"contents": "read"})


def test_supply_chain_only_scans():
    document = workflow("supply-chain.yml")
    assert document["permissions"] == {"contents": "read"}
    assert "cosign" not in (WORKFLOWS / "supply-chain.yml").read_text(encoding="utf-8").replace("La firma esta en sign-image.yml", "")
    trivy = next(s for s in steps(document) if "trivy-action" in s.get("uses", ""))
    sbom = next(s for s in steps(document) if "sbom-action" in s.get("uses", ""))
    upload = next(s for s in steps(document) if "upload-artifact" in s.get("uses", ""))
    assert trivy["with"]["exit-code"] == "1"
    for produced in (trivy["with"]["output"], sbom["with"]["output-file"]):
        assert produced in upload["with"]["path"]
    assert sbom["if"] == "always()" and upload["if"] == "always()"


def test_sign_image_signs_then_verifies_with_the_key_of_verify_images():
    """`verify-images` admite por llave publica: una firma sin llave se rechazaria al admitir."""
    document = workflow("sign-image.yml")
    assert "id-token" not in document["permissions"]
    inputs = triggers(document)["workflow_call"]["inputs"]
    assert inputs["image"]["required"] and inputs["public-key-path"]["required"]
    script = run_blocks(document)
    assert script.index("cosign sign") < script.index("cosign verify")
    assert "--key env://COSIGN_PRIVATE_KEY" in script and '--key "$PUBLIC_KEY"' in script
    policy = (PLATFORM / "policies/kyverno/verify-images.yaml").read_text(encoding="utf-8")
    assert "publicKeys" in policy


@pytest.mark.parametrize("name", ["supply-chain.yml", "evidence.yml"])
def test_trivy_skips_the_insecure_test_cases(name):
    trivy = next(s for s in steps(workflow(name)) if "trivy-action" in s.get("uses", ""))
    skipped = trivy["with"]["skip-dirs"].split(",")
    for folder in ("vectra-risk/platform/policies/kyverno/fixtures", "vectra-risk/platform/policies/rego/tests"):
        assert folder in skipped
        assert (REPO / folder).is_dir()


# --- 3. contracts.yml


def test_contracts_scans_the_lockfiles_and_keeps_the_audits():
    document = workflow("contracts.yml")
    assert document["jobs"]["supply-chain"]["with"]["path"] == "vectra-risk"
    assert (ROOT / "uv.lock").is_file() and (ROOT / "package-lock.json").is_file()
    script = run_blocks(document)
    assert "pip-audit -r" in script and "npm audit --audit-level=high" in script


def test_contracts_pins_oasdiff():
    document = workflow("contracts.yml")
    script = run_blocks(document)
    assert "main/install.sh" not in script and "| sh" not in script
    step = next(s for s in steps(document) if "oasdiff" in str(s.get("run", "")))
    assert re.fullmatch(r"\d+\.\d+\.\d+", step["env"]["OASDIFF_VERSION"])
    assert "releases/download/v${OASDIFF_VERSION}/oasdiff_${OASDIFF_VERSION}_linux_amd64.tar.gz" in step["run"]


def test_contracts_diff_covers_the_generated_typescript():
    diff = next(line for line in run_blocks(workflow("contracts.yml")).splitlines() if "git diff --exit-code" in line)
    for path in ("contracts/openapi/", "contracts/ts/src/generated", "contracts/ts/src/enums.generated.ts"):
        assert path in diff


# --- 4. Snapshots


def test_rendered_check_runs_in_ci_only():
    assert "git diff --exit-code -- platform/rendered/" in recipe("check-rendered")
    assert "git status --porcelain -- platform/rendered/" in recipe("check-rendered")
    assert "render" in re.search(r"^check-rendered:(.*)$", MAKEFILE, flags=re.M).group(1)
    assert "make -C platform check-rendered" in run_blocks(workflow("policies.yml"))
    assert "check-rendered" not in re.search(r"^check:(.*)$", MAKEFILE, flags=re.M).group(1)
    assert "check-rendered" not in re.search(r"^check-local:(.*)$", MAKEFILE, flags=re.M).group(1)


# --- 5. Evidencia


def test_evidence_fails_on_a_diff_error():
    script = run_blocks(workflow("evidence.yml"))
    assert '"$code" -gt 1' in script and 'exit "$failed"' in script
    assert "core_resources.py" in script


@pytest.mark.parametrize(("exit_code", "expected"), [(0, 0), (1, 0), (2, 1), (3, 1)])
def test_evidence_loop_exit_code(tmp_path, exit_code, expected):
    step = next(s for s in steps(workflow("evidence.yml")) if "kubectl diff" in str(s.get("run", "")))
    start = step["run"].index("failed=0")
    loop = step["run"][start:].replace("evidence/kubectl-diff/resources/*.yaml", "a.yaml")
    fake = tmp_path / "kubectl"
    fake.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    fake.chmod(0o755)
    (tmp_path / "evidence/kubectl-diff").mkdir(parents=True)
    result = subprocess.run(["bash", "-c", loop], cwd=tmp_path, env={"PATH": f"{tmp_path}:/usr/bin:/bin"}, capture_output=True, text=True, check=False)
    assert result.returncode == expected, result.stderr


def test_evidence_artifact_has_everything_nfr_u1_42_asks_for():
    document = workflow("evidence.yml")
    upload = next(s for s in steps(document) if "upload-artifact" in s.get("uses", ""))
    assert upload["if"] == "always()" and upload["with"]["path"] == "vectra-risk/evidence"
    script = run_blocks(document)
    assert "evidence/helm-template" in script
    assert "--junit-xml=evidence/junit.xml" in script and '--hypothesis-seed="$PBT_SEED"' in script and 'junit_suite_name="pbt-seed-$PBT_SEED"' in script
    trivy = next(s for s in steps(document) if "trivy-action" in s.get("uses", ""))
    sbom = next(s for s in steps(document) if "sbom-action" in s.get("uses", ""))
    assert trivy["with"]["output"].startswith("vectra-risk/evidence/") and sbom["with"]["output-file"].startswith("vectra-risk/evidence/")
    assert trivy["with"]["format"] and sbom["with"]["format"] == "spdx-json"


def test_evidence_never_installs_anything_on_the_cluster():
    text = (WORKFLOWS / "evidence.yml").read_text(encoding="utf-8")
    assert not fs.workflow_violations(WORKFLOWS)
    assert "kubectl apply" not in text.replace("nunca se aplica", "") and "kubectl create" not in text


@pytest.mark.parametrize(
    ("document", "reason"),
    [
        ({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "x"}}, None),
        ({"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "ClusterRole", "metadata": {"name": "x"}}, None),
        ({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x", "namespace": "default"}}, None),
        ({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x"}}, None),
        ({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x", "namespace": "vectra-app"}}, "namespace vectra-app"),
        ({"apiVersion": "batch/v1", "kind": "CronJob", "metadata": {"name": "x", "namespace": "vectra-data"}}, "namespace vectra-data"),
        ({"apiVersion": "postgresql.cnpg.io/v1", "kind": "Cluster", "metadata": {"name": "x", "namespace": "default"}}, "CRD"),
        ({"apiVersion": "external-secrets.io/v1", "kind": "ExternalSecret", "metadata": {"name": "x"}}, "CRD"),
    ],
)
def test_core_resources_selection(document, reason):
    found = core_resources.exclusion(document, {"default"})
    assert (found is None) if reason is None else (reason in found)


def test_core_resources_writes_files_and_records_the_limit(tmp_path):
    source = tmp_path / "in.yaml"
    source.write_text(
        "apiVersion: v1\nkind: Namespace\nmetadata: {name: a}\n---\n"
        "apiVersion: example.io/v1\nkind: Thing\nmetadata: {name: b}\n",
        encoding="utf-8",
    )
    only_custom = tmp_path / "custom.yaml"
    only_custom.write_text("apiVersion: example.io/v1\nkind: Thing\nmetadata: {name: c}\n", encoding="utf-8")
    out = tmp_path / "out"
    assert core_resources.main([str(source), str(only_custom), "--out", str(out), "--namespace", "namespace/default"]) == 0
    assert [d["kind"] for d in yaml.safe_load_all((out / "in.yaml").read_text(encoding="utf-8"))] == ["Namespace"]
    assert not (out / "custom.yaml").exists(), "un archivo vacio haria fallar kubectl diff"
    assert "2 Thing: CRD ausente" in (out / "limits.txt").read_text(encoding="utf-8")


def test_core_resources_refuses_an_empty_diff(tmp_path):
    source = tmp_path / "in.yaml"
    source.write_text("apiVersion: example.io/v1\nkind: Thing\nmetadata: {name: b}\n", encoding="utf-8")
    assert core_resources.main([str(source), "--out", str(tmp_path / "out")]) == 1


# --- 6. platform.yml y la nota de rollback


def test_platform_filters_and_triggers():
    on = triggers(workflow("platform.yml"))
    paths = on["pull_request"]["paths"]
    for expected in ("vectra-risk/.trivyignore", "vectra-risk/pyproject.toml", "vectra-risk/uv.lock", "vectra-risk/aidlc-docs/**", "**/Dockerfile*"):
        assert expected in paths
    assert "edited" in on["pull_request"]["types"] and "synchronize" in on["pull_request"]["types"]
    assert on["schedule"][0]["cron"]


def test_platform_calls_tests_and_only_the_scan_runs_on_schedule():
    jobs = workflow("platform.yml")["jobs"]
    assert jobs["tests"]["uses"] == "./.github/workflows/tests.yml" and jobs["tests"]["with"]["path"] == "platform"
    assert "if" not in jobs["supply-chain"]
    for name, job in jobs.items():
        if name != "supply-chain":
            assert job["if"] == "github.event_name == 'pull_request'", name


@pytest.mark.parametrize(
    ("body", "filled"),
    [
        ("## Rollback\nRevert y sync manual.\n", True),
        ("## Rollback\r\nRevert y sync manual.\r\n", True),
        ("## Qué cambia\nx\n\n## Rollback\nRevert.\n\n## Otra\n", True),
        ("## Rollback\n<!-- nota -->\nRevert.\n", True),
        ("## Rollback\n### Pasos\nRevert.\n", True),
        ("", False),
        ("## Qué cambia\nx\n", False),
        ("## Rollback\n", False),
        ("## Rollback\n   \n\t\n", False),
        ("## Rollback\r\n\r\n", False),
        ("## Rollback\n<!-- Una linea -->\n", False),
        ("## Rollback\n<!-- Varias\nlineas\ndel comentario -->\n", False),
        ("## Rollback\n<!-- sin cerrar\n\nRevert\n", False),
        ("## Rollback\n<!-- a -->\n<!-- b\nc -->\n\n## Otra\ntexto de otra seccion\n", False),
        ("<!-- ## Rollback\nRevert\n-->\n## Otra\nx\n", False),
        ("Rollback\nRevert\n", False),
    ],
)
def test_rollback_note(body, filled):
    assert rollback_note.has_rollback_note(body) is filled


def test_rollback_note_script_reads_the_environment():
    script = PLATFORM / "tests/rollback_note.py"
    run = lambda body: subprocess.run([sys.executable, "-I", str(script)], env={"BODY": body}, capture_output=True, check=False).returncode  # noqa: E731
    assert run("## Rollback\nRevert\n") == 0
    assert run("## Rollback\n<!-- a\nb -->\n") == 1


def test_platform_uses_the_rollback_script():
    job = workflow("platform.yml")["jobs"]["rollback-note"]
    assert any("rollback_note.py" in str(s.get("run", "")) for s in job["steps"])
    assert job["steps"][0]["uses"].startswith("actions/checkout")


# --- 7. Pasos prohibidos

FORBIDDEN_SCRIPTS = [
    "kubectl apply -f x",
    "kubectl -n prod apply -f x",
    "kubectl --namespace prod apply -f x",
    "kubectl --context=x apply -f y",
    "kubectl --context x apply -f y",
    "kubectl --kubeconfig=/k -n prod -v 2 apply -f y",
    "kubectl 'apply' -f x",
    'kubectl "apply" -f x',
    'ku"bec"tl apply -f x',
    "/usr/local/bin/kubectl apply -f x",
    "$TOOLS/kubectl apply -f x",
    "sudo kubectl apply -f x",
    "env A=1 kubectl apply -f x",
    "kubectl $VAR",
    'kubectl "$VAR" -f x',
    "kubectl ${VERB} -f x",
    "kubectl -n prod $VAR",
    "kubectl $(echo apply) -f x",
    "kubectl `echo apply` -f x",
    "kubectl ${{ inputs.verb }} -f x",
    "kubectl \\\n  apply \\\n  -f x",
    "kubectl -n prod \\\n  apply -f x",
    'kubectl apply -f "a # b"',
    'echo "x # y" && kubectl apply -f z',
    "echo 'x # y'; kubectl apply -f z",
    "a=1 # comentario\nkubectl apply -f x",
    'bash -c "kubectl apply -f x"',
    "bash -c 'helm upgrade r c'",
    'x="$(kubectl apply -f y)"',
    "x=$(kubectl apply -f y)",
    "K=kubectl; $K apply -f x",
    'K="kubectl apply"; $K -f x',
    "$KUBECTL apply -f x",
    '"$K" delete pod x',
    "ls | xargs kubectl",
    "kubectl create ns x",
    "kubectl replace -f x",
    "kubectl patch deploy x",
    "kubectl delete pod x",
    "kubectl edit deploy x",
    "kubectl scale deploy x --replicas=0",
    "kubectl rollout restart deploy x",
    "kubectl rollout status deploy x",
    "helm install r c",
    "helm upgrade r c",
    "helm rollback r 1",
    "helm uninstall r",
    "helm --kube-context x upgrade r c",
    "helm --kube-context=x install r c",
    "helm -n prod upgrade --install r c",
    "helm $VERB r c",
    "terraform apply",
    "terraform destroy",
    "terraform -chdir=x apply",
    "terraform -chdir x destroy",
    "argocd app sync a",
    "argocd app delete a",
    "argocd app rollback a",
    "argocd app set a --revision b",
    "argocd --server x app sync a",
    "argocd --server=x --grpc-web app sync a",
    "argocd app --grpc-web sync a",
    "argocd app $VERB a",
]

ALLOWED_SCRIPTS = [
    "",
    "# kubectl apply -f x",
    "echo hola # kubectl apply -f x",
    "kubectl diff -f x",
    "kubectl diff --server-side=false -f x",
    "kubectl -n prod diff -f x",
    "kubectl --context=x diff -f y",
    "kubectl get pods -n apply",
    "kubectl get namespaces -o name",
    "kubectl -n $NS get pods",
    "kubectl version --client",
    "kind create cluster",
    "kind create cluster --name delete",
    "helm template a b",
    "helm template a b -f values.yaml --namespace x",
    "helm lint a",
    "helm dependency build a",
    "helm dependency update a",
    "helm pull a --repo b --version 1",
    "helm version --short",
    "terraform plan",
    "terraform -chdir=x plan",
    "argocd app get a",
    "argocd app diff a",
    "argocd version --client",
    "which kubectl",
    "kyverno apply policy.yaml --resource x",
    "$(TOOLS)/kyverno apply policy.yaml --resource x",
    "conftest test x",
    "grep -q apply x",
    'echo "aplicar el cambio"',
    "curl -fsSL https://x/kubectl#apply -o k",
]


def violations_of(script):
    return list(fs.command_violations(fs.without_expressions(script)))


@pytest.mark.parametrize("script", FORBIDDEN_SCRIPTS)
def test_forbidden_command(script):
    assert violations_of(script), script


@pytest.mark.parametrize("script", ALLOWED_SCRIPTS)
def test_allowed_command(script):
    assert not violations_of(script), script


def repo_with(tmp_path, workflow_text, **files):
    folder = tmp_path / ".github/workflows"
    folder.mkdir(parents=True)
    (folder / "ci.yml").write_text(workflow_text, encoding="utf-8")
    for name, content in files.items():
        path = tmp_path / name.replace("__", "/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return folder


def job(*lines):
    return "jobs:\n  a:\n    runs-on: x\n    steps:\n" + "".join(f"      {line}\n" for line in lines)


def test_folded_block_is_one_command(tmp_path):
    assert fs.workflow_violations(repo_with(tmp_path, job("- run: >", "    kubectl", "    apply -f x")))


def test_literal_block_with_continuation(tmp_path):
    assert fs.workflow_violations(repo_with(tmp_path, job("- run: |", "    kubectl \\", "      apply -f x")))


def test_name_and_comment_are_not_run_blocks(tmp_path):
    text = job("- name: kubectl apply no se ejecuta", "  run: echo hola # kubectl apply")
    assert not fs.workflow_violations(repo_with(tmp_path, "# kubectl apply\n" + text))


@pytest.mark.parametrize(
    ("uses", "bad"),
    [
        ("azure/k8s-deploy@v5", True),
        ("Azure/k8s-deploy@abc", True),
        ("helm/chart-deploy@v1", True),
        ("deliverybot/helm@v1", True),
        ("azure/setup-kubectl@v4", False),
        ("azure/setup-helm@v4", False),
        ("helm/kind-action@v1", False),
        ("actions/checkout@v4", False),
    ],
)
def test_deploy_actions(tmp_path, uses, bad):
    assert bool(fs.workflow_violations(repo_with(tmp_path, job(f"- uses: {uses}")))) is bad


def test_deploy_action_with_commands_in_inputs(tmp_path):
    assert fs.workflow_violations(repo_with(tmp_path, job("- uses: x/y@v1", "  with:", "    args: kubectl apply -f x")))


@pytest.mark.parametrize(
    ("expression", "bad"),
    [
        ("secrets.KUBECONFIG", True),
        ("secrets.KUBE_CONFIG", True),
        ("secrets.PROD_KUBE_TOKEN", True),
        ("secrets.kubeconfig", True),
        ("secrets['KUBECONFIG']", True),
        ("secrets.GITHUB_TOKEN", False),
        ("github.token", False),
    ],
)
def test_cluster_secrets(tmp_path, expression, bad):
    text = job("- run: echo hola", "  env:", f"    X: ${{{{ {expression} }}}}")
    assert bool(fs.workflow_violations(repo_with(tmp_path, text))) is bad


@pytest.mark.parametrize(
    ("line", "name", "content", "bad"),
    [
        ("- run: ./deploy.sh", "deploy.sh", "kubectl apply -f x\n", True),
        ("- run: ./deploy.sh", "deploy.sh", "kubectl diff -f x\n", False),
        ("- run: bash deploy.sh", "deploy.sh", "helm upgrade r c\n", True),
        ("- run: sh scripts/deploy", "scripts__deploy", "helm upgrade r c\n", True),
        ("- run: source lib.sh", "lib.sh", "terraform apply\n", True),
        ("- run: scripts/deploy.sh", "scripts__deploy.sh", "argocd app sync a\n", True),
        ("- run: ./uno.sh", "uno.sh", "./dos.sh\n", False),
        ("- run: python tool.py", "tool.py", 'subprocess.run(["kubectl", "apply", "-f", "x"])\n', True),
        ("- run: uv run python tool.py", "tool.py", 'os.system("helm upgrade r c")\n', True),
        ("- run: python tool.py", "tool.py", 'subprocess.run(["kubectl", "diff", "-f", "x"])\n', False),
        ("- run: make", "Makefile", "a:\n\tkubectl apply -f x\n", True),
        ("- run: make deploy", "Makefile", "lint:\n\techo\ndeploy:\n\tkubectl apply -f x\n", True),
        ("- run: make lint", "Makefile", "lint:\n\techo\ndeploy:\n\tkubectl apply -f x\n", False),
        ("- run: make all", "Makefile", "all: deploy\ndeploy:\n\t@helm upgrade r c\n", True),
        ("- run: make -C sub deploy", "sub__Makefile", "deploy:\n\tkubectl apply -f x\n", True),
        ("- run: make -f other.mk deploy", "other.mk", "deploy:\n\tkubectl apply -f x\n", True),
        ("- run: make deploy", "Makefile", "K := kubectl\ndeploy:\n\t$(K) apply -f x\n", True),
        ("- run: make deploy", "Makefile", "deploy:\n\t$(MAKE) real\nreal:\n\tkubectl apply -f x\n", True),
        ("- run: make deploy", "Makefile", "deploy:\n\tcd sub && ./x.sh\n", False),
    ],
)
def test_invoked_scripts_are_scanned(tmp_path, line, name, content, bad):
    folder = repo_with(tmp_path, job(line), **{name: content})
    if content == "./dos.sh\n":
        (tmp_path / "dos.sh").write_text("kubectl delete pod x\n", encoding="utf-8")
        bad = True
    if "cd sub" in content:
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub/x.sh").write_text("kubectl delete pod x\n", encoding="utf-8")
        bad = True
    assert bool(fs.workflow_violations(folder)) is bad


def test_working_directory_is_respected(tmp_path):
    # El `x.sh` limpio de la raiz no debe tapar al de la carpeta donde corre el paso.
    folder = repo_with(tmp_path, job("- run: ./x.sh", "  working-directory: sub"), **{"sub__x.sh": "kubectl apply -f y\n"})
    (tmp_path / "x.sh").write_text("echo limpio\n", encoding="utf-8")
    assert fs.workflow_violations(folder)
    other = tmp_path / "other"
    folder = other / ".github/workflows"
    folder.mkdir(parents=True)
    (folder / "ci.yml").write_text("defaults:\n  run:\n    working-directory: sub\n" + job("- run: ./x.sh"), encoding="utf-8")
    (other / "sub").mkdir()
    (other / "x.sh").write_text("echo limpio\n", encoding="utf-8")
    (other / "sub/x.sh").write_text("kubectl apply -f y\n", encoding="utf-8")
    assert fs.workflow_violations(folder)


def test_a_script_that_cannot_be_read_is_a_violation(tmp_path):
    assert fs.workflow_violations(repo_with(tmp_path, job("- run: ./missing.sh")))


def test_a_make_target_that_cannot_be_read_is_a_violation(tmp_path):
    assert fs.workflow_violations(repo_with(tmp_path, job("- run: make deploy")))
    (tmp_path / "Makefile").write_text("lint:\n\techo\n", encoding="utf-8")
    assert fs.workflow_violations(tmp_path / ".github/workflows")


def test_composite_actions_are_scanned(tmp_path):
    folder = tmp_path / ".github/actions/x"
    folder.mkdir(parents=True)
    (folder / "action.yml").write_text("runs:\n  using: composite\n  steps:\n    - shell: bash\n      run: kubectl apply -f x\n", encoding="utf-8")
    assert fs.workflow_violations(tmp_path / ".github/actions")
    assert fs.main([str(tmp_path / ".github/actions")]) == 1


def test_missing_folder_is_an_error(tmp_path):
    assert fs.workflow_violations(tmp_path / "no-existe")
    assert fs.main([str(tmp_path / "no-existe")]) == 1
    (tmp_path / "vacia").mkdir()
    assert fs.workflow_violations(tmp_path / "vacia")
    assert fs.main([]) == 2


def test_ci_scans_workflows_and_actions():
    run = run_blocks(workflow("forbidden-steps.yml"))
    assert ".github/workflows .github/actions" in run


def test_real_repository_passes():
    assert fs.main([str(WORKFLOWS), str(REPO / ".github/actions")]) == 0


# --- 8. Kyverno: `pass: 0` no aprueba


KYVERNO_OK = re.search(r"^KYVERNO_OK := (.+)$", MAKEFILE, flags=re.M).group(1)


@pytest.mark.parametrize(
    ("report", "ok"),
    [
        ("pass: 184, fail: 0, warn: 0, error: 0, skip: 0", True),
        ("pass: 1, fail: 0, warn: 0, error: 0, skip: 3", True),
        ("pass: 10, fail: 0, warn: 0, error: 0, skip: 0", True),
        ("pass: 0, fail: 0, warn: 0, error: 0, skip: 9", False),
        ("pass: 184, fail: 1, warn: 0, error: 0, skip: 0", False),
        ("pass: 184, fail: 0, warn: 2, error: 0, skip: 0", False),
        ("pass: 184, fail: 0, warn: 0, error: 1, skip: 0", False),
        ("Error: no se pudo cargar la politica", False),
    ],
)
def test_kyverno_gate(report, ok):
    assert bool(re.search(KYVERNO_OK, report)) is ok


def test_every_kyverno_gate_uses_it():
    for target in ("check-integration", "check-chart"):
        assert "'$(KYVERNO_OK)'" in recipe(target), target
    assert "pass: [0-9]+" not in MAKEFILE


# --- 9. RBAC de todo el cluster


@pytest.mark.parametrize(
    ("document", "kept"),
    [
        ({"kind": "ClusterRole", "metadata": {"name": "argo-cd-argocd-server"}}, True),
        ({"kind": "Role", "metadata": {"name": "x", "namespace": "argocd"}}, True),
        ({"kind": "Role", "metadata": {"name": "x", "namespace": "vectra-app"}}, True),
        ({"kind": "Deployment", "metadata": {"name": "x", "namespace": "vectra-app"}}, True),
        ({"kind": "Deployment", "metadata": {"name": "x", "namespace": "kyverno"}}, False),
        ({"kind": "CustomResourceDefinition", "metadata": {"name": "x"}}, False),
    ],
)
def test_integration_keeps_all_rbac(document, kept):
    assert integration.evaluated(document) is kept


# --- 10. Las reglas probadas son las desplegadas


def test_deployed_rules_are_the_tested_rules():
    tested = yaml.safe_load((PLATFORM / "observability/rules/platform-rules.yaml").read_text(encoding="utf-8"))
    deployed = yaml.safe_load((PLATFORM / "observability/rules/platform-rules.prometheusrule.yaml").read_text(encoding="utf-8"))
    assert deployed["kind"] == "PrometheusRule"
    assert deployed["spec"]["groups"] == tested["groups"]


# --- 11. Cuotas


def test_quotas_check_is_part_of_check_local():
    assert "platform/policies/quotas/render.py --check" in recipe("check-local")


def test_quotas_render_check_detects_drift(tmp_path):
    script = PLATFORM / "policies/quotas/render.py"
    run = lambda *args: subprocess.run([sys.executable, str(tmp_path / "render.py"), *args], capture_output=True, text=True, check=False).returncode  # noqa: E731
    (tmp_path / "render.py").write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "quotas.yaml").write_text((PLATFORM / "policies/quotas/quotas.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    assert run("--check") == 1, "sin generated.yaml"
    assert not (tmp_path / "generated.yaml").exists(), "--check no escribe"
    assert run() == 0
    assert run("--check") == 0
    (tmp_path / "generated.yaml").write_text("otro", encoding="utf-8")
    assert run("--check") == 1


def test_generated_quotas_are_current():
    assert subprocess.run([sys.executable, str(PLATFORM / "policies/quotas/render.py"), "--check"], check=False).returncode == 0


# --- 12. conftest


def test_rego_fixtures_cover_every_rule():
    rules = rego_fixtures.declared_rules()
    assert {"native-sidecar", "rbac-wildcards", "deployment-hpa"} <= set(rules) and rules["deployment-hpa"] == "hpa"
    assert len(rules) == len(re.findall(r"^deny contains", "\n".join(p.read_text(encoding="utf-8") for p in (PLATFORM / "policies/rego").glob("*.rego")), flags=re.M))
    for rule in rules:
        assert (PLATFORM / f"policies/rego/tests/{rule}/pass.yaml").is_file() and (PLATFORM / f"policies/rego/tests/{rule}/fail.yaml").is_file(), rule


def test_rego_fixtures_run_in_check_tools():
    assert "platform/tests/rego_fixtures.py" in recipe("check-tools")
    assert "--combine --namespace hpa" in recipe("check-tools")


# --- 15. Trazabilidad


def run_tool(script, *args):
    return subprocess.run([sys.executable, str(PLATFORM / "tests" / script), *args], cwd=ROOT, capture_output=True, text=True, check=False)


def test_traceability_platform_foundation():
    for args in ([], ["--unit", "platform-foundation"], ["--unit", "platform-foundation", "--all"]):
        result = run_tool("test_traceability.py", *args)
        assert result.returncode == 0, result.stdout


def test_traceability_detects_the_prefix():
    assert traceability.own_identifiers("platform-foundation") >= {"NFR-U1-02", "P-U1-04", "INF-U1-06"}
    assert all("-U1-" in i for i in traceability.own_identifiers("platform-foundation"))
    assert all("-U2-" in i for i in traceability.own_identifiers("identity-edge"))


def test_traceability_unit_without_code_fails():
    result = run_tool("test_traceability.py", "--unit", "governance", "--all")
    assert result.returncode == 1 and "sin código" in result.stdout


def test_traceability_unknown_unit_fails():
    assert run_tool("test_traceability.py", "--unit", "no-existe").returncode == 1


def test_traceability_all_skips_units_without_code():
    assert "governance: sin código, se omite" in run_tool("test_traceability.py", "--all").stdout


@pytest.fixture
def fake_unit(tmp_path, monkeypatch):
    construction = tmp_path / "aidlc-docs/construction"
    (construction / "demo/nfr-requirements").mkdir(parents=True)
    (construction / "demo/nfr-design").mkdir(parents=True)
    (construction / "demo/code").mkdir(parents=True)
    (construction / "plans").mkdir()
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo/real.py").write_text("# implementa NFR-U9-01\n", encoding="utf-8")
    (construction / "demo/nfr-requirements/nfr-requirements.md").write_text("| NFR-U9-01 | a |\n| NFR-U9-02 | b |\n| NFR-U1-01 | cita a otra unidad |\n", encoding="utf-8")
    monkeypatch.setattr(traceability, "ROOT", tmp_path)
    monkeypatch.setattr(traceability, "REPO", tmp_path)
    monkeypatch.setattr(traceability, "CONSTRUCTION", construction)
    return construction


def test_traceability_ignores_ids_of_other_units(fake_unit):
    assert traceability.own_identifiers("demo") == {"NFR-U9-01", "NFR-U9-02"}


def test_traceability_missing_id(fake_unit):
    assert traceability.check_unit("demo") == ["NFR-U9-02: sin trazabilidad"]


@pytest.mark.parametrize(
    ("row", "ok"),
    [
        ("| NFR-U9-02 | `demo/` |\n", False),
        ("| NFR-U9-02 | `demo/no-existe.py` |\n", False),
        ("| NFR-U9-02 | sin archivo |\n", False),
        ("| NFR-U9-02 | `demo/real.py` |\n", True),
    ],
)
def test_traceability_row_must_name_a_real_file(fake_unit, row, ok):
    (fake_unit / "demo/code/README.md").write_text(row, encoding="utf-8")
    problems = traceability.check_unit("demo")
    assert (problems == []) is ok
    if not ok:
        assert "solo en code/README.md" in problems[0]


def test_traceability_empty_file_does_not_count(fake_unit, tmp_path):
    (tmp_path / "demo/vacio.py").write_text("", encoding="utf-8")
    (fake_unit / "demo/code/README.md").write_text("| NFR-U9-02 | `demo/vacio.py` |\n", encoding="utf-8")
    assert traceability.check_unit("demo")


def test_traceability_deferred_needs_the_other_plan_to_cite_it(fake_unit):
    (fake_unit / "demo/code/README.md").write_text("| NFR-U9-02 | Diferida a `otra` |\n", encoding="utf-8")
    assert traceability.check_unit("demo")
    (fake_unit / "plans/otra-code-generation-plan.md").write_text("cubre NFR-U9-02\n", encoding="utf-8")
    assert traceability.check_unit("demo") == []


def test_traceability_reads_code_roots_from_the_summary(fake_unit, tmp_path):
    (tmp_path / "otra").mkdir()
    (tmp_path / "otra/x.py").write_text("# NFR-U9-02\n", encoding="utf-8")
    assert traceability.check_unit("demo")
    (fake_unit / "demo/code/README.md").write_text("Raíces de código: `otra/`\n", encoding="utf-8")
    assert traceability.check_unit("demo") == []


def test_traceability_understands_ranges():
    expanded = traceability.with_ranges("NFR-U0-01..03 y br_u0_20_22")
    for identifier in ("NFR-U0-02", "BR-U0-21"):
        assert identifier in expanded


# --- 16. Las herramientas que citan los planes


def cited(tool):
    return [line for path in PLAN_FOLDER.glob("*-code-generation-plan.md") for line in path.read_text(encoding="utf-8").splitlines() if tool in line]


def test_plans_really_cite_these_tools():
    assert len(cited("test_runbooks.py")) >= 11 and len(cited("test_waves.py")) >= 9 and len(cited("test_links.py")) >= 2


def test_runbooks_defaults_and_operational_pass():
    for args in ([], ["--root", "platform"], ["--operational"]):
        result = run_tool("test_runbooks.py", *args)
        assert result.returncode == 0, result.stdout


def test_runbooks_root_without_alerts_fails():
    assert run_tool("test_runbooks.py", "--root", "no-existe").returncode == 1
    assert run_tool("test_runbooks.py", "--root", "platform/kind").returncode == 1


def test_template_sections_come_from_the_template():
    assert runbooks.template_sections() == ["## Síntoma", "## Impacto", "## Diagnóstico", "## Mitigación", "## Escalamiento", "## Verificación"]


GOOD_RUNBOOK = "\n".join(runbooks.template_sections()) + "\n- Corre `x`.\n"


def alert_tree(tmp_path, url, severity="SEV1", templated=False):
    (tmp_path / "chart/templates").mkdir(parents=True)
    labels = "{{ include \"x\" . }}\n" if templated else ""
    (tmp_path / "chart/templates/rules.yaml").write_text(
        f"{labels}apiVersion: monitoring.coreos.com/v1\nkind: PrometheusRule\nspec:\n  groups:\n  - name: a\n    rules:\n"
        f"    - alert: A\n      expr: up\n      labels:\n        severity: {severity}\n      annotations:\n        runbook_url: {url}\n",
        encoding="utf-8",
    )
    return tmp_path / "chart"


@pytest.mark.parametrize("templated", [False, True])
def test_runbooks_alert_with_good_runbook(tmp_path, templated):
    root = alert_tree(tmp_path, "docs/a.md", templated=templated)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/a.md").write_text(GOOD_RUNBOOK, encoding="utf-8")
    assert runbooks.alert_problems(root, base=tmp_path) == ([], 1)


@pytest.mark.parametrize("templated", [False, True])
def test_runbooks_missing_runbook(tmp_path, templated):
    problems, checked = runbooks.alert_problems(alert_tree(tmp_path, "docs/no.md", templated=templated), base=tmp_path)
    assert checked == 1 and "sin archivo" in problems[0]


def test_runbooks_invalid_severity(tmp_path):
    root = alert_tree(tmp_path, "docs/a.md", severity="alta")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/a.md").write_text(GOOD_RUNBOOK, encoding="utf-8")
    assert "severity invalida" in runbooks.alert_problems(root, base=tmp_path)[0][0]


def test_runbooks_incomplete_runbook(tmp_path):
    root = alert_tree(tmp_path, "docs/a.md")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/a.md").write_text("## Síntoma\n", encoding="utf-8")
    assert "le faltan" in runbooks.alert_problems(root, base=tmp_path)[0][0]


def test_runbooks_a_mention_is_not_a_section():
    assert runbooks.missing_sections("Ver ## Impacto en otro lado\n", ["## Impacto"]) == ["## Impacto"]


@pytest.mark.parametrize(
    ("verification", "problems"),
    [
        ("- Corre `kubectl get pods`.\n- Corre `x`.\n", 0),
        ("Corre `x`.\n", 0),
        ("- Corre `x`.\n- Mira la pantalla.\n", 1),
        ("Mira la pantalla.\n", 1),
    ],
)
def test_runbooks_each_verification_step_names_a_command(verification, problems):
    assert len(runbooks.verification_problems(f"## Verificación\n{verification}\n## Otra\n- sin comando\n")) == problems


def test_runbooks_operational_root(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/release.md").write_text(GOOD_RUNBOOK, encoding="utf-8")
    (tmp_path / "docs/otro.md").write_text("# Notas\n", encoding="utf-8")
    assert runbooks.operational_problems(tmp_path / "docs", base=tmp_path) == ([], 1)
    (tmp_path / "docs/release.md").write_text("## Síntoma\n", encoding="utf-8")
    assert runbooks.operational_problems(tmp_path / "docs", base=tmp_path)[0]


def test_waves_pass_on_the_real_applications():
    result = run_tool("test_waves.py")
    assert result.returncode == 0, result.stdout
    assert run_tool("test_waves.py", "--root", "vectra-risk-gitops/apps/prod").returncode == 0
    assert run_tool("test_waves.py", "--root", "no-existe").returncode == 1


def application(wave):
    annotations = {waves.WAVE_ANNOTATION: str(wave)} if wave is not None else {}
    return {"kind": "Application", "metadata": {"annotations": annotations}}


@pytest.mark.parametrize(
    ("apps", "fragment"),
    [
        ({"root": application(0), "a": application(None)}, "sin wave"),
        ({"root": application(0), "a": application(7)}, "fuera de P-U1-12"),
        ({"a": application(0)}, "falta root.yaml"),
        ({"root": application(0), "postgres": application(3)}, "se esperaba 2"),
        ({"root": application(0), "decision-registry-rebuild": application(5)}, "se esperaba 6"),
        ({"root": application(0), "cloudnative-pg": application(2), "postgres": application(2)}, "necesita cloudnative-pg antes"),
        ({"root": application(0), "namespaces": application(2), "quotas": application(1)}, "corre antes que namespaces"),
    ],
)
def test_waves_detect_problems(apps, fragment):
    expected = {"postgres": 2, "decision-registry-rebuild": 6}
    assert any(fragment in p for p in waves.problems_in(apps, expected)), waves.problems_in(apps, expected)


def test_waves_same_wave_is_enough_when_allowed():
    apps = {"root": application(0), "namespaces": application(1), "quotas": application(1)}
    assert waves.problems_in(apps, {}) == []


def test_links_pass_on_the_real_repository():
    result = run_tool("test_links.py")
    assert result.returncode == 0, result.stdout
    assert run_tool("test_links.py", "--root", "no-existe").returncode == 1


@pytest.mark.parametrize(
    ("markdown", "broken"),
    [
        ("[a](existe.md)", []),
        ("[a](existe.md#seccion)", []),
        ("[a](./sub/../existe.md)", []),
        ("![a](existe.md)", []),
        ('[a](existe.md "titulo")', []),
        ("[a](#seccion)", []),
        ("[a](https://x/no.md) [b](mailto:a@b)", []),
        ("`[a](no.md)`", []),
        ("```\n[a](no.md)\n```\n", []),
        ("[a](no.md)", ["no.md"]),
        ("[a](no.md#seccion)", ["no.md#seccion"]),
        ("[a](../fuera/no.md)", ["../fuera/no.md"]),
    ],
)
def test_links(tmp_path, markdown, broken):
    (tmp_path / "existe.md").write_text("x", encoding="utf-8")
    (tmp_path / "doc.md").write_text(markdown, encoding="utf-8")
    assert links.broken_links(tmp_path / "doc.md") == broken


def test_cli_tools_are_executable():
    for name in ("test_runbooks.py", "test_waves.py", "test_links.py", "test_traceability.py"):
        path = PLATFORM / "tests" / name
        assert path.stat().st_mode & 0o100, name
        assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3"), name


# --- 17. Chart de una unidad


def test_policies_takes_a_chart():
    document = workflow("policies.yml")
    inputs = triggers(document)["workflow_call"]["inputs"]
    assert inputs["path"]["default"] == ""
    by_condition = {s.get("if"): s for s in steps(document) if "if" in s}
    assert "make -C platform check-chart" in by_condition["inputs.path != ''"]["run"]
    assert "make -C platform check" in str([s["run"] for s in steps(document) if s.get("if") == "inputs.path == ''"])
    for tool in ("integration.py --chart", "kyverno apply", "conftest test --policy", "--combine --namespace hpa"):
        assert tool in recipe("check-chart"), tool


def test_integration_rejects_a_folder_that_is_not_a_chart(tmp_path):
    assert integration.main(["--chart", "platform/kind", "--out", str(tmp_path)]) == 1


# --- 18. Helm fijado


def tools_env():
    return dict(re.findall(r"^(\w+)=(\S+)$", (PLATFORM / "tools.env").read_text(encoding="utf-8"), flags=re.M))


def test_helm_version_is_pinned():
    assert re.fullmatch(r"v\d+\.\d+\.\d+", tools_env()["HELM_VERSION"])


def test_setup_helm_uses_the_pinned_version():
    action = yaml.safe_load((REPO / ".github/actions/setup-helm/action.yml").read_text(encoding="utf-8"))
    setup = next(s for s in action["runs"]["steps"] if "azure/setup-helm" in s.get("uses", ""))
    assert setup["with"]["version"] == "${{ steps.version.outputs.HELM_VERSION }}"
    assert "HELM_VERSION" in action["runs"]["steps"][0]["run"] and "tools.env" in action["runs"]["steps"][0]["run"]
    for path in WORKFLOWS.glob("*.yml"):
        assert "azure/setup-helm" not in path.read_text(encoding="utf-8"), f"{path.name}: usa .github/actions/setup-helm"
    for name in ("policies.yml", "evidence.yml", "tests.yml"):
        assert any(s.get("uses") == "./.github/actions/setup-helm" for s in steps(workflow(name))), name


def test_install_tools_uses_the_pinned_helm():
    script = (PLATFORM / "install-tools.sh").read_text(encoding="utf-8")
    assert "helm-${HELM_VERSION}-linux-amd64.tar.gz" in script and "get.helm.sh" in script


@pytest.mark.parametrize("name", ["supply-chain.yml", "evidence.yml"])
def test_trivy_version_is_pinned(name):
    """La version por omision de la accion dejo de estar publicada y el CI fallo al instalarla."""
    trivy = next(s for s in steps(workflow(name)) if "trivy-action" in s.get("uses", ""))
    assert trivy["with"]["version"].startswith("v")


def test_contract_baseline_is_read_from_the_repository_root():
    """`git archive` resuelve la ruta desde el directorio actual, y el job corre en `vectra-risk/`."""
    assert 'git -C "$(git rev-parse --show-toplevel)" archive' in run_blocks(workflow("contracts.yml"))
