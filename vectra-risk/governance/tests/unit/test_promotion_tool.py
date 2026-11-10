"""`promotion-tool` (Paso 12; BR-U4-08 y BR-U4-09; NFR-U4-20 y 21): PR de un commit firmado, sin tokens en disco y con el esquema de U6.

Dobles: el IdP (Keycloak, con PKCE verificado), la API de governance (`MockTransport`), `gh` y el comando `kubectl diff` (un `Runner`
que los intercepta). `git` y `helm` son los reales, sobre un repositorio de fixture en `tmp_path`; ninguna prueba toca un cluster.
Necesita `platform/install-tools.sh` (helm).
"""

import base64
import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import yaml
from vectra_promotion import cli, commands, values
from vectra_promotion.api import GovernanceApi
from vectra_promotion.errors import PromotionError
from vectra_promotion.gitops import PromotionRepo, system_runner

ROOT = Path(__file__).resolve().parents[3]
HELM = str(ROOT / "platform" / ".tools" / "bin" / "helm")
DOCS = ROOT / "model-serving" / "docs" / "values.md"
BASE_VALUES = ROOT / "model-serving" / "tests" / "fixtures" / "values-base.yaml"
M1, M2 = "mv-2026-01-01-26300247", "mv-2026-02-01-a1b2c3d4"
ISVC1, ISVC2 = "isvc-26300247", "isvc-a1b2c3d4"
TOKEN = "tok-SECRETO-" + "x" * 40
ISSUER = "https://keycloak.test/auth/realms/vectra"
API = "https://gw.test/api/promotion"
HEADER = "# cabecera del archivo: los comentarios fuera de la lista se conservan\n"
SHA = "a" * 64


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)  # noqa: S603, S607
    return done.stdout


class Doubles:
    """Intercepta `gh` y el comando de diff; todo lo demas (git, helm) corre de verdad."""

    def __init__(self) -> None:
        self.gh: list[list[str]] = []
        self.diff_stdin: list[str] = []
        self.commands: list[list[str]] = []

    def __call__(self, args: Sequence[str], cwd: Path, stdin: str | None) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(args))
        if args[0] == "gh":
            self.gh.append(list(args))
            return subprocess.CompletedProcess(args, 0, "https://github.com/vectra/vectra-risk/pull/7\n", "")
        if args[0] == "fake-kubectl-diff":
            self.diff_stdin.append(stdin or "")
            return subprocess.CompletedProcess(args, 1, "+kind: InferenceService\n+  name: nuevo\n", "")
        return system_runner(args, cwd, stdin)


@pytest.fixture
def doubles() -> Doubles:
    return Doubles()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Un repositorio git con el chart de U6, los values de `kind` en el estado inicial de `test_promotion_renders.py`, un origen y firma SSH."""
    root = tmp_path / "work"
    origin = tmp_path / "origin.git"
    root.mkdir()
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(root, "init", "-q", "-b", "main")
    shutil.copytree(ROOT / "model-serving" / "chart", root / "model-serving" / "chart")
    shutil.copytree(ROOT / "vectra-risk-gitops" / "envs", root / "vectra-risk-gitops" / "envs")
    target = root / "vectra-risk-gitops" / "values" / "kind" / "model-serving.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(HEADER + BASE_VALUES.read_text(encoding="utf-8").split("\n", 1)[1], encoding="utf-8")
    key = tmp_path / "id_signing"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)  # noqa: S603, S607
    (tmp_path / "allowed").write_text(f"ingeniero@vectra.test {(tmp_path / 'id_signing.pub').read_text()}", encoding="utf-8")
    for k, v in {
        "user.name": "Ingeniero",
        "user.email": "ingeniero@vectra.test",
        "gpg.format": "ssh",
        "user.signingkey": str(key),
        "gpg.ssh.allowedSignersFile": str(tmp_path / "allowed"),
    }.items():
        git(root, "config", k, v)
    git(root, "remote", "add", "origin", str(origin))
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "inicial")
    git(root, "push", "-q", "-u", "origin", "main")
    return root


def tool(root: Path, doubles: Doubles, env: str = "kind") -> PromotionRepo:
    return PromotionRepo(
        root, ["fake-kubectl-diff", "-f", "-"], env, "vectra-risk-gitops", "model-serving/chart", "main", helm=HELM, runner=doubles
    )


def model_json(version: str, state: str = "aprobado") -> dict[str, Any]:
    prefix = f"s3://model-store/{version}/"
    return {
        "model_version_id": version, "state": state, "artifact_uri": prefix + "predictor.json", "artifact_format": "xgboost_json",
        "artifact_sha256": SHA, "explainer_uri": prefix + "explainer.json", "explainer_sha256": SHA,
        "inference_service": "isvc-" + version[-8:], "manifest_uri": prefix + "manifest.json", "manifest_sha256": SHA,
        "feature_dictionary_version": "fd-1", "data_sources": [], "registered_by": "u1", "investigation": False,
        "created_at": "2026-02-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z",
    }  # fmt: skip


class Governance:
    """Doble de governance por el gateway: lista las `aprobado` y registra las activaciones."""

    def __init__(self) -> None:
        self.seen: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        if request.url.path == "/api/promotion/v1/models" and request.method == "GET":
            assert request.url.params["state"] == "aprobado"
            return httpx.Response(200, json={"items": [model_json(M2)], "page": 1, "total": 1})
        if request.url.path.endswith("/activation") and request.method == "POST":
            return httpx.Response(204)
        return httpx.Response(404)


def api(governance: Governance) -> GovernanceApi:
    return GovernanceApi(API, TOKEN, httpx.MockTransport(governance))


def merge(root: Path, url_branch: str) -> None:
    """Lo que hace la persona que revisa: fusiona el PR (fast-forward) en `main`."""
    git(root, "merge", "-q", "--ff-only", url_branch)


def branch_of(doubles: Doubles) -> str:
    return doubles.gh[-1][doubles.gh[-1].index("--head") + 1]


def committed_values(root: Path, ref: str) -> list[values.Entry]:
    return values.parse(git(root, "show", f"{ref}:vectra-risk-gitops/values/kind/model-serving.yaml"))


def example(name: str) -> list[values.Entry]:
    match = re.search(rf"<!-- ejemplo:{re.escape(name)} -->\n```yaml\n(.*?)```", DOCS.read_text(encoding="utf-8"), re.DOTALL)
    assert match, name
    return values.parse(match.group(1))


def without_staging(entries: list[values.Entry]) -> list[values.Entry]:
    return [e for e in entries if e["profile"] != "staging"]


def helm_render(root: Path, entries: list[values.Entry], tmp: Path) -> list[dict[str, Any]]:
    path = tmp / "check.yaml"
    path.write_text(yaml.safe_dump({"inferenceServices": entries}), encoding="utf-8")
    envs = root / "vectra-risk-gitops" / "envs" / "kind" / "values.yaml"
    done = subprocess.run(  # noqa: S603
        [HELM, "template", "ms", str(root / "model-serving" / "chart"), "-f", str(envs), "-f", str(path)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    return [d for d in yaml.safe_load_all(done.stdout) if d]


def replicas(docs: list[dict[str, Any]], isvc: str) -> list[int]:
    (item,) = [
        d for d in docs if d["kind"] == "InferenceService" and d["metadata"]["name"] == isvc and d["metadata"]["namespace"] == "vectra-serving"
    ]
    return [item["spec"][c][k] for c in ("predictor", "explainer") for k in ("minReplicas", "maxReplicas")]


# --- list_promotable y create_promotion_pr ---------------------------------------------------------------------------------


def test_list_promotable_returns_the_approved_versions() -> None:
    governance = Governance()
    found = commands.list_promotable(api(governance))
    assert [m.model_version_id for m in found] == [M2]
    assert governance.seen[0].headers["authorization"] == f"Bearer {TOKEN}"


def test_the_promotion_pr_is_one_signed_commit_with_both_pieces_of_the_same_model_version(repo: Path, doubles: Doubles, tmp_path: Path) -> None:
    before = git(repo, "rev-parse", "main").strip()
    url = commands.create_promotion_pr(api(Governance()), tool(repo, doubles), M2)
    branch = branch_of(doubles)
    assert url.endswith("/pull/7")
    assert git(repo, "rev-list", "--count", f"main..{branch}").strip() == "1"  # un solo commit
    assert git(repo, "log", "-1", "--format=%G?", branch).strip() == "G"  # firmado y verificado con la clave del ingeniero
    assert git(repo, "rev-parse", "main").strip() == before  # no toca main
    assert git(repo, "diff", "--name-only", "main", branch).split() == ["vectra-risk-gitops/values/kind/model-serving.yaml"]
    entries = committed_values(repo, branch)
    assert without_staging(entries) == example("promocion:despues")  # agrega al final; el activo no cambia
    assert entries[-1] == {"modelVersionId": M2, "storageUri": f"s3://model-store/{M2}/", "profile": "prod"}
    # predictor y explicador del `InferenceService` renderizado desde el commit llevan el mismo model_version_id y el mismo storageUri
    docs = helm_render(repo, entries, tmp_path)
    (isvc,) = [d for d in docs if d["kind"] == "InferenceService" and d["metadata"]["name"] == ISVC2]
    assert isvc["metadata"]["annotations"]["vectra.io/model-version-id"] == M2
    envs = {c["name"]: c.get("env", []) for c in (isvc["spec"]["predictor"]["containers"] + isvc["spec"]["explainer"]["containers"])}
    stores = {e["value"] for c in envs.values() for e in c if e["name"] == "STORAGE_URI"}
    assert stores == {f"s3://model-store/{M2}/"}
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"  # deja el repositorio donde estaba
    # el encabezado y el resto del archivo no cambian
    assert git(repo, "show", f"{branch}:vectra-risk-gitops/values/kind/model-serving.yaml").startswith(HEADER)


def test_the_pr_carries_the_helm_and_the_kubectl_diff_evidence_and_never_applies(repo: Path, doubles: Doubles) -> None:
    commands.create_promotion_pr(api(Governance()), tool(repo, doubles), M2)
    body = doubles.gh[-1][doubles.gh[-1].index("--body") + 1]
    assert "helm template" in body and "kubectl diff" in body and ISVC2 in body and M2 in body and "+kind: InferenceService" in body
    assert "InferenceService" in doubles.diff_stdin[0] and M2 in doubles.diff_stdin[0]  # el diff recibe el render por stdin
    flat = [" ".join(c) for c in doubles.commands]
    assert not [c for c in flat if re.search(r"\b(apply|sync)\b|helm (install|upgrade)", c)]


def test_a_version_that_is_not_approved_has_no_pr_and_leaves_no_branch(repo: Path, doubles: Doubles) -> None:
    with pytest.raises(PromotionError, match="model_not_promotable"):
        commands.create_promotion_pr(api(Governance()), tool(repo, doubles), "mv-2026-03-01-deadbeef")
    assert git(repo, "branch", "--list").split() == ["*", "main"] and doubles.gh == []


def test_a_change_the_schema_refuses_creates_neither_branch_nor_commit(repo: Path, doubles: Doubles) -> None:
    """Un `storageUri` fuera de `s3://model-store/` lo rechaza `helm template` (esquema de U6) antes de tocar la rama."""
    bad = tool(repo, doubles)
    with pytest.raises(PromotionError, match="helm_template_failed"):
        bad.open_pr("promocion", M2, values.promote(bad.current(), M2, "s3://otro-bucket/x/"), "feat: promover")
    assert git(repo, "branch", "--list").split() == ["*", "main"] and doubles.gh == []


def test_a_dirty_working_tree_is_refused(repo: Path, doubles: Doubles) -> None:
    (repo / "suelto.txt").write_text("x", encoding="utf-8")
    with pytest.raises(PromotionError, match="working_tree_dirty"):
        commands.create_promotion_pr(api(Governance()), tool(repo, doubles), M2)


def test_the_diff_command_is_required_evidence(repo: Path) -> None:
    no_diff = PromotionRepo(repo, [], "kind", "vectra-risk-gitops", "model-serving/chart", helm=HELM)
    with pytest.raises(PromotionError, match="diff_command_required"):
        commands.create_promotion_pr(api(Governance()), no_diff, M2)


# --- los cuatro PR sobre el esquema de U6 (mismo punto de partida que test_promotion_renders.py) --------------------------------


def test_the_promotion_post_activation_and_rollback_prs_pass_the_u6_schema_and_render_what_u6_expects(
    repo: Path, doubles: Doubles, tmp_path: Path
) -> None:
    t = tool(repo, doubles)
    # PR 1: promocion
    commands.create_promotion_pr(api(Governance()), t, M2)
    docs = helm_render(repo, committed_values(repo, branch_of(doubles)), tmp_path)
    assert replicas(docs, ISVC1) == [2, 4, 2, 6] and replicas(docs, ISVC2) == [2, 4, 2, 6]
    merge(repo, branch_of(doubles))
    # PR 2: post-activacion (despues de `mark_active` de M2)
    commands.post_activation_pr(t, M1)
    entries = committed_values(repo, branch_of(doubles))
    assert without_staging(entries) == example("post-activacion:despues")
    docs = helm_render(repo, entries, tmp_path)
    (old,) = [d for d in docs if d["kind"] == "InferenceService" and d["metadata"]["name"] == ISVC1 and d["metadata"]["namespace"] == "vectra-serving"]
    assert replicas(docs, ISVC1) == [1, 1, 1, 1]  # 1 replica por componente
    assert old["metadata"]["labels"]["vectra.io/serving-state"] == "inactivo" and replicas(docs, ISVC2) == [2, 4, 2, 6]
    assert not [d for d in docs if d["kind"] == "PodDisruptionBudget" and d["metadata"]["name"].startswith(ISVC1)]
    merge(repo, branch_of(doubles))
    # PR de rollback: M1 `inactivo` recupera los minimos de produccion antes de su `mark_active`
    commands.rollback_pr(t, M1)
    entries = committed_values(repo, branch_of(doubles))
    assert without_staging(entries) == example("rollback:despues")
    docs = helm_render(repo, entries, tmp_path)
    assert replicas(docs, ISVC1) == [2, 4, 2, 6] and replicas(docs, ISVC2) == [2, 4, 2, 6]
    (restored,) = [d for d in docs if d["kind"] == "InferenceService" and d["metadata"]["name"] == ISVC1 and d["metadata"]["namespace"] == "vectra-serving"]
    assert "vectra.io/serving-state" not in restored["metadata"]["labels"]
    for branch in git(repo, "branch", "--list", "promotion/*").split():
        assert git(repo, "log", "-1", "--format=%G?", branch).strip() == "G"


def test_post_activation_and_rollback_refuse_a_version_in_the_wrong_profile(repo: Path, doubles: Doubles) -> None:
    t = tool(repo, doubles)
    with pytest.raises(PromotionError, match="entry_not_found:inactive"):
        commands.rollback_pr(t, M1)  # M1 esta `prod`, no `inactive`
    with pytest.raises(PromotionError, match="entry_not_found:prod"):
        commands.post_activation_pr(t, M2)  # M2 no esta declarada
    assert doubles.gh == []


def test_the_value_edits_are_the_u6_ones_and_touch_nothing_else() -> None:
    start = values.parse(BASE_VALUES.read_text(encoding="utf-8"))
    promoted = values.promote(start, M2, f"s3://model-store/{M2}/")
    assert promoted[:-1] == start and promoted[-1]["profile"] == "prod"
    assert values.demote(promoted, M1)[0]["profile"] == "inactive" and values.demote(promoted, M1)[1:] == promoted[1:]
    assert values.restore(values.demote(promoted, M1), M1) == promoted
    assert values.isvc_name(M2) == ISVC2
    assert values.storage_uri(f"s3://model-store/{M2}/manifest.json") == f"s3://model-store/{M2}/"
    assert values.storage_uri("s3://model-store/a/b/manifest.json") == "s3://model-store/a/b/"
    with pytest.raises(PromotionError):
        values.promote(promoted, M2, "s3://model-store/x/")  # ya declarada
    with pytest.raises(PromotionError, match="manifest_uri_invalid"):
        values.storage_uri("s3://otro/x/manifest.json")


# --- mark_active -------------------------------------------------------------------------------------------------------------


def test_mark_active_calls_activation_with_the_right_inference_service(repo: Path, doubles: Doubles) -> None:
    t = tool(repo, doubles)
    commands.create_promotion_pr(api(Governance()), t, M2)
    merge(repo, branch_of(doubles))
    governance = Governance()
    isvc = commands.mark_active(api(governance), t, M2, "Revision de CRO #12")
    (request,) = governance.seen
    assert (request.method, request.url.path) == ("POST", f"/api/promotion/v1/models/{M2}/activation")
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert isvc == ISVC2 and f"inference_service={ISVC2}" in json.loads(request.content)["evidence"]
    assert json.loads(request.content)["evidence"].startswith("Revision de CRO #12")


def test_mark_active_refuses_a_version_not_declared_in_prod(repo: Path, doubles: Doubles) -> None:
    governance = Governance()
    with pytest.raises(PromotionError, match="not_promoted_in_values"):
        commands.mark_active(api(governance), tool(repo, doubles), M2, "x")
    assert governance.seen == []


def test_a_refused_activation_fails_without_the_token_in_the_message() -> None:
    bad = GovernanceApi(API, TOKEN, httpx.MockTransport(lambda r: httpx.Response(409, text=f"echo {TOKEN}")))
    with pytest.raises(PromotionError) as error:
        bad.mark_active(M2, "x")
    assert TOKEN not in str(error.value) and "409" in str(error.value)


# --- login PKCE y tokens (NFR-U4-20) -----------------------------------------------------------------------------------------


class IdentityProvider:
    """Doble de Keycloak: el \"navegador\" sigue la redireccion al loopback y el endpoint de token verifica el PKCE."""

    def __init__(self, governance: Governance) -> None:
        self.governance = governance
        self.auth: dict[str, str] = {}
        self.exchanges: list[dict[str, str]] = []

    def browser(self, url: str) -> None:
        self.auth = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        assert self.auth["code_challenge_method"] == "S256" and self.auth["client_id"] == "promotion-tool"
        assert "governance:promotion" in self.auth["scope"]
        # Forma exacta del diseno de U2 (domain-entities 2.1) y del realm (`http://127.0.0.1`): loopback IPv4, cualquier
        # puerto, SIN ruta. Keycloak ignora el puerto (RFC 8252 7.3) pero compara la ruta exacta.
        redirect = urlparse(self.auth["redirect_uri"])
        if (redirect.scheme, redirect.hostname, redirect.path, redirect.query, redirect.fragment) != ("http", "127.0.0.1", "", "", "") or redirect.port is None:
            raise AssertionError(f"Invalid parameter: redirect_uri={self.auth['redirect_uri']}")
        httpx.get(self.auth["redirect_uri"], params={"code": "code-1", "state": self.auth["state"]})

    def transport(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/protocol/openid-connect/token"):
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            self.exchanges.append(form)
            digest = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest()).rstrip(b"=").decode()
            if form["code"] != "code-1" or digest != self.auth["code_challenge"]:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": TOKEN, "token_type": "Bearer"})
        return self.governance(request)


def walk(*roots: Path) -> list[Path]:
    return [p for root in roots for p in root.rglob("*") if p.is_file() and ".git/objects" not in p.as_posix()]


def test_after_a_pkce_login_no_file_in_home_or_the_repository_holds_the_token(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    for var in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
        monkeypatch.setenv(var, str(home))
    governance = Governance()
    idp = IdentityProvider(governance)
    code = cli.main(
        ["--issuer", ISSUER, "--api", API, "--repo", str(repo), "--env", "kind", "mark-active", M2, "--evidence", "x"],
        open_browser=idp.browser,
        transport=httpx.MockTransport(idp.transport),
    )
    assert code == 1  # M2 no esta en `prod` todavia: el login se hizo y la llamada no salio
    code = cli.main(
        ["--issuer", ISSUER, "--api", API, "list-promotable"], open_browser=idp.browser, transport=httpx.MockTransport(idp.transport)
    )
    assert code == 0 and M2 in capsys.readouterr().out
    assert governance.seen[-1].headers["authorization"] == f"Bearer {TOKEN}"  # el token se uso (en memoria)
    assert idp.exchanges[-1]["grant_type"] == "authorization_code" and idp.exchanges[-1]["client_id"] == "promotion-tool"
    for path in walk(home, repo, tmp_path / "origin.git"):
        assert TOKEN.encode() not in path.read_bytes(), f"el token esta en {path}"


def test_a_login_with_a_wrong_state_fails() -> None:
    from vectra_promotion.login import login

    def browser(url: str) -> None:
        redirect = parse_qs(urlparse(url).query)["redirect_uri"][0]
        httpx.get(redirect, params={"code": "c", "state": "otro"})

    with pytest.raises(PromotionError, match="login_failed"):
        login(ISSUER, browser, transport=httpx.MockTransport(lambda r: httpx.Response(500)))


# --- la CLI ------------------------------------------------------------------------------------------------------------------


def test_retire_inference_service_does_not_exist_in_the_cli() -> None:
    names = {name for action in cli.parser()._actions if getattr(action, "choices", None) for name in action.choices}  # noqa: SLF001
    assert {"list-promotable", "create-promotion-pr", "post-activation-pr", "rollback-pr", "mark-active"} <= names
    assert not [n for n in names if "retire" in n or "retir" in n]
    assert not hasattr(commands, "retire_inference_service")
    assert not [n for n in dir(values) if "retire" in n]


def test_the_cli_post_activation_pr_runs_end_to_end(repo: Path, doubles: Doubles, capsys: pytest.CaptureFixture[str]) -> None:
    t = tool(repo, doubles)
    commands.create_promotion_pr(api(Governance()), t, M2)
    merge(repo, branch_of(doubles))
    code = cli.main(
        ["--repo", str(repo), "--env", "kind", "--diff-command", "fake-kubectl-diff -f -", "--gitops", "vectra-risk-gitops",
         "--chart", "model-serving/chart", "--helm", HELM, "post-activation-pr", M1],
        runner=doubles,
    )  # fmt: skip
    assert code == 0 and capsys.readouterr().out.strip().endswith("/pull/7")
    assert cli.main(["--repo", str(repo), "--env", "kind", "--gitops", "vectra-risk-gitops", "rollback-pr", M1], runner=doubles) == 1
    assert "promotion_tool_failed" in capsys.readouterr().err
