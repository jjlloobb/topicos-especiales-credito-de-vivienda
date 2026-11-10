"""Los scripts del operador de `governance/docs/kind/` (U04-T07, CA-2): corren con `--dry-run` o contra dobles de `kubectl`, `docker`, `uv` y
`make` que registran sus argumentos y su stdin. Ninguno toca un clúster, y el token nunca aparece en un argumento ni en el entorno del cliente.
"""

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

KIND = Path(__file__).resolve().parents[2] / "docs" / "kind"
SCRIPTS = sorted(KIND.glob("*.sh"))
TOKEN = "SECRETO-DE-LA-PRUEBA-123"

FAKE_KUBECTL = r"""#!/usr/bin/env bash
# Doble de kubectl: registra los argumentos (uno por linea, entre marcas) y el stdin; responde lo minimo que pide cada script.
{
  echo "--- kubectl"
  printf '%s\n' "$@"
} >> "$LOG"
case "$*" in
  *"get pods"*) printf 'governance-service-aaa\ngovernance-service-bbb\n'; exit 0 ;;
  *"--dry-run=client"*) echo "kind: Pod"; exit 0 ;;
  *" top "*) echo "NAME CPU MEMORY"; exit 0 ;;
  *"python -c"*" sondear"*|*" sondear") cat > /dev/null; echo "listo 200 etag-1"; echo "cambio 100.5 congelado etag-2"; exit 0 ;;
  *"python -c"*" freeze "*|*" freeze "*) cat > /dev/null; echo "freeze 100.0 204 "; exit 0 ;;
esac
{ echo "--- stdin"; cat; } >> "$LOG"
"""
FAKE_DOCKER = """#!/usr/bin/env bash
echo "--- docker $*" >> "$LOG"
case "$*" in
  *inspect*governance:dev*) echo "localhost:5001/vectra/governance@sha256:1111111111111111111111111111111111111111111111111111111111111111" ;;
  *inspect*model-validation-job:dev*) echo "localhost:5001/vectra/model-validation-job@sha256:2222222222222222222222222222222222222222222222222222222222222222" ;;
esac
"""
FAKE_MAKE = "#!/usr/bin/env bash\necho \"--- make $*\" >> \"$LOG\"\n"
FAKE_UV = "#!/usr/bin/env bash\necho \"--- uv $*\" >> \"$LOG\"\necho fake-token\n"


@pytest.fixture
def world(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {"kubectl": FAKE_KUBECTL, "docker": FAKE_DOCKER, "make": FAKE_MAKE, "uv": FAKE_UV}.items():
        path = bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SYNTH_", "VECTRA_E2E"))}
    return {**env, "PATH": f"{bin_dir}:{os.environ['PATH']}", "LOG": str(tmp_path / "log"), "ESPERA_SONDAS": "0"}


def run(script: str, *args: str, env: dict[str, str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(KIND / script), *args], input=stdin, capture_output=True, text=True, env=env, check=False, timeout=60)  # noqa: S603


def log(env: dict[str, str]) -> str:
    path = Path(env["LOG"])
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_hay_scripts_y_todos_son_ejecutables() -> None:
    assert {s.name for s in SCRIPTS} >= {"token.sh", "llamar.sh", "imagenes.sh", "freeze-cuerpo.sh", "medir-freeze.sh", "memoria.sh", "registro-cuerpo.sh"}
    for script in SCRIPTS:
        assert script.stat().st_mode & stat.S_IXUSR, script.name
        assert script.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n"), script.name


def test_ningun_script_aplica_instala_ni_sincroniza_y_ninguno_lleva_credenciales() -> None:
    for script in SCRIPTS:
        text = "\n".join(line for line in script.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#"))
        assert not re.search(r"kubectl\b[^\n]*\bapply\b|helm\s+(install|upgrade)|argocd\s+app\s+sync", text), script.name
        assert not re.search(r"(?i)(password|secret|token)\w*=['\"]?\w{8,}", text), script.name
        assert "kubectl create secret" not in text, script.name


@pytest.mark.parametrize("script", [s.name for s in SCRIPTS])
def test_cada_script_tiene_dry_run_que_no_toca_nada(script: str, world: dict[str, str]) -> None:
    args = {"token.sh": ["cro-2"], "llamar.sh": ["politica-x", "GET", "/v1/policies"], "freeze-cuerpo.sh": ["mv-x"], "registro-cuerpo.sh": ["x"], "medir-freeze.sh": ["mv-x"], "memoria.sh": ["antes"]}
    done = run(script, "--dry-run", *args.get(script, []), env=world)
    assert done.returncode == 0, done.stderr
    assert "dry-run" in done.stdout or script == "llamar.sh"
    forbidden = {"uv", "docker", "make"} if script != "llamar.sh" else {"uv", "docker", "make"}
    assert not any(f"--- {tool}" in log(world) for tool in forbidden), log(world)
    assert "apply" not in log(world)


def test_llamar_pasa_el_token_por_stdin_y_no_por_argumentos(world: dict[str, str]) -> None:
    done = run("llamar.sh", "politica-propone", "POST", "/v1/policies", env=world, stdin=f"{TOKEN}\n" + '{"cutoff":"0.5000"}\n')
    assert done.returncode == 0, done.stderr
    recorded = log(world)
    argv_part = recorded.split("--- stdin")[0]
    assert TOKEN not in argv_part and TOKEN not in done.stdout
    assert TOKEN in recorded.split("--- stdin")[1], "el token debe llegar al pod por stdin"
    assert '{"cutoff":"0.5000"}' in recorded
    args = argv_part.splitlines()
    assert {"-i", "--rm", "--restart=Never", "--override-type=strategic", "--command"} <= set(args)
    assert "--image=kind-registry:5000/vectra/governance@sha256:" + "1" * 64 in args, "el digest sale de docker inspect"
    assert "politica-propone" in args and args[-2:] == ["POST", "/v1/policies"]


def test_llamar_arma_un_pod_que_cumple_la_admision_de_u1(world: dict[str, str]) -> None:
    run("llamar.sh", "politica-lee", "GET", "/v1/policies", env=world, stdin=f"{TOKEN}\n")
    args = [a for a in log(world).splitlines() if a.startswith("--overrides=")]
    assert len(args) == 1
    overrides = json.loads(args[0].removeprefix("--overrides="))
    spec = overrides["spec"]
    container = spec["containers"][0]
    assert container["name"] == "politica-lee" and "@sha256:" in container["image"]
    assert spec["serviceAccountName"] == "console-bff" and spec["priorityClassName"] == "vectra-low"
    assert spec["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["readOnlyRootFilesystem"] is True and container["securityContext"]["capabilities"] == {"drop": ["ALL"]}
    assert {"requests", "limits"} <= set(container["resources"])
    assert overrides["metadata"]["labels"]["vectra.io/criticality"] == "medium"
    assert overrides["metadata"]["annotations"]["config.alpha.linkerd.io/proxy-enable-native-sidecar"] == "true"
    assert TOKEN not in log(world).split("--- stdin")[0]


def test_llamar_con_dry_run_rinde_el_pod_sin_servidor(world: dict[str, str]) -> None:
    done = run("llamar.sh", "--dry-run", "politica-lee", "GET", "/v1/policies", env=world)
    assert done.returncode == 0 and "kind: Pod" in done.stdout
    args = log(world).splitlines()
    assert "--dry-run=client" in args and "-i" not in args and "--rm" not in args


def test_llamar_falla_sin_argumentos(world: dict[str, str]) -> None:
    assert run("llamar.sh", env=world).returncode != 0


def test_token_no_lleva_el_secreto_en_argumentos_y_pide_el_usuario(world: dict[str, str]) -> None:
    done = run("token.sh", "cro-2", env=world)
    assert done.returncode == 0 and done.stdout.strip() == "fake-token"
    recorded = log(world)
    assert "e2e_support" in recorded and "cro-2" in recorded
    assert run("token.sh", env=world).returncode != 0
    servicio = run("token.sh", "--servicio", "scoring-service", "governance:read-serving", env=world)
    assert servicio.returncode == 0 and servicio.stdout.strip() == "fake-token"
    assert "service_token" in log(world) and "governance:read-serving" in log(world)


def test_imagenes_publica_las_dos_y_da_el_yaml_de_values(world: dict[str, str]) -> None:
    done = run("imagenes.sh", env=world)
    assert done.returncode == 0, done.stderr
    recorded = log(world)
    assert "make -C" in recorded and "image-validation" in recorded and "push localhost:5001/vectra/governance:dev" in recorded
    assert "push localhost:5001/vectra/model-validation-job:dev" in recorded
    assert f"image:\n  digest: sha256:{'1' * 64}\nvalidation:\n  image:\n    digest: sha256:{'2' * 64}" in done.stdout


def test_registro_cuerpo_arma_el_cuerpo_de_u4_con_la_convencion_de_rutas(tmp_path: Path, world: dict[str, str]) -> None:
    manifest = {"model_version_id": "mv-2026-01-01-8a98ab02", "files": [{"name": "predictor.json", "sha256": "a" * 64}, {"name": "explainer.json", "sha256": "b" * 64}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    done = run("registro-cuerpo.sh", str(tmp_path), env=world)
    assert done.returncode == 0, done.stderr
    body = json.loads(done.stdout)
    base = "s3://model-store/mv-2026-01-01-8a98ab02/"
    assert body["artifact_uri"] == base + "predictor.json" and body["explainer_uri"] == base + "explainer.json" and body["manifest_uri"] == base + "manifest.json"
    assert body["artifact_sha256"] == "a" * 64 and body["explainer_sha256"] == "b" * 64 and body["artifact_format"] == "xgboost_json"
    assert body["manifest_sha256"] == hashlib.sha256((tmp_path / "manifest.json").read_bytes()).hexdigest()
    assert run("registro-cuerpo.sh", env=world).returncode != 0


def test_memoria_lee_con_kubectl_top(world: dict[str, str]) -> None:
    done = run("memoria.sh", "antes", env=world)
    assert done.returncode == 0 and "## antes" in done.stdout and "NAME CPU MEMORY" in done.stdout
    assert "top\npod\n-n\nvectra-app" in log(world)


def test_medir_freeze_sondea_las_dos_replicas_y_calcula_el_maximo(world: dict[str, str]) -> None:
    done = run("medir-freeze.sh", "mv-2026-01-01-aaaaaaaa", env=world)
    assert done.returncode == 0, done.stderr
    assert "governance-service-aaa cambio_en=0.50" in done.stdout and "governance-service-bbb cambio_en=0.50" in done.stdout
    assert "maximo=0.5" in done.stdout
    assert TOKEN not in log(world)
