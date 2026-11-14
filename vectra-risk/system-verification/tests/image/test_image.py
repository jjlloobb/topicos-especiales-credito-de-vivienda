"""La imagen de `system-verification` (U12-T05, Paso 15, CA-2 a CA-5): el contenido, el contenedor real, el sandbox de Chromium y la CA en los dos caminos TLS.

Un `Dockerfile` que construye no prueba que el contenedor funcione (CA-4 de U11-T03). Aqui el contenedor arranca como lo manda el README (`--read-only`, `--tmpfs /tmp`, un uid sin root cualquiera, `--memory 1g`, el perfil `seccomp`
de Chromium y los montajes) y ejecuta secciones contra dobles. `tests/doubles/image_run.py` guarda la orden en un solo sitio y `tests/unit/test_demos_closed_world.py` comprueba que el README la trae igual.

Sin Docker las pruebas **fallan**; no se omiten. Se corren despues de `make -C system-verification image` (el objetivo `check` lo hace): la etiqueta `source-digest` de la imagen debe ser la de las fuentes de hoy.
Los directorios de la verificacion y los certificados salen del worktree (`platform/.tools/tmp/u12t05/`), nunca de `/tmp`, y los contenedores llevan el prefijo `u12t05-` y se borran siempre.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import image_run
import pytest
import tls_server
from image_run import IMAGE, UNIT, base_options, mount, run, unique_name

REPO = UNIT.parent  # vectra-risk/
DOCKERFILE = UNIT / "Dockerfile"
SCRATCH = REPO / "platform" / ".tools" / "tmp" / "u12t05"
VALUES = REPO / "vectra-risk-gitops" / "values" / "kind" / "case-management.yaml"
KUBECTL_DOUBLE = image_run.DOUBLES / "container_kubectl.py"
TEST_USER = "12345:12345"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def docker(*arguments: str, timeout: float = 180) -> subprocess.CompletedProcess[str]:
    if arguments[0] in {
        "run",
        "build",
    }:  # con `pytest -s` queda la orden exacta en la salida (bitacora de la tarea)
        print("$ docker", " ".join(arguments))
    try:
        return run(arguments, timeout=timeout)
    except FileNotFoundError:
        pytest.fail("Docker no esta disponible: la prueba de la imagen falla, no se salta")


def in_image(
    command: list[str], *, entrypoint: str = "python", user: str = TEST_USER, extra: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Una orden dentro de la imagen, con las opciones comunes del README (solo lectura, tmpfs, memoria, usuario sin root)."""
    return docker(
        "run", *base_options(user=user), *(extra or []), "--entrypoint", entrypoint, IMAGE, *command
    )


@pytest.fixture(scope="module", autouse=True)
def image_is_fresh() -> None:
    """La imagen existe y se construyo con las fuentes de hoy: una prueba que pasa con una imagen vieja no prueba nada."""
    probe = docker(
        "image",
        "inspect",
        IMAGE,
        "--format",
        '{{index .Config.Labels "org.vectra.system-verification.source-digest"}}',
    )
    assert probe.returncode == 0, (
        f"falta la imagen {IMAGE}: corre `make -C system-verification image`\n{probe.stderr}"
    )
    sys.path.insert(0, str(UNIT / "image"))
    try:
        from source_digest import digest  # noqa: PLC0415 - la misma funcion que usa `make image`
    finally:
        sys.path.remove(str(UNIT / "image"))
    assert probe.stdout.strip() == digest(REPO), (
        "la imagen es anterior a las fuentes: corre `make -C system-verification image`"
    )


@pytest.fixture
def work() -> Iterator[Path]:
    """Un directorio de trabajo dentro del worktree (no `/tmp`). Se borra al terminar; los archivos que un contenedor con otro uid dejo adentro se borran porque el directorio es del usuario del host."""
    SCRATCH.mkdir(parents=True, exist_ok=True)
    directory = SCRATCH / f"run-{uuid.uuid4().hex[:8]}"
    directory.mkdir()
    directory.chmod(0o777)
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def evidence_dir(work: Path) -> Path:
    path = work / "evidence"
    path.mkdir()
    path.chmod(
        0o777
    )  # un uid cualquiera (12345) tiene que poder escribir; el directorio sigue siendo del usuario del host
    return path


DELIVERY_IN_IMAGE = "/verification/reference-model/.out"  # donde el README monta la entrega de U5 (de solo lectura)


def prepare_command(evidence: Path, *, user: str = TEST_USER, name: str | None = None) -> list[str]:
    options = base_options(user=user)
    if name:
        options.remove("--rm")
        options += ["--name", name]
    return [
        "run",
        *options,
        *mount(evidence, "/verification/evidence", read_only=False),
        *mount(VALUES, "/values/case-management.yaml"),
        IMAGE,
        "prepare",
        "--commit",
        "c0ffee1",
        "--operator",
        "operadora",
        "--values-file",
        "/values/case-management.yaml",
        "--delivery",
        DELIVERY_IN_IMAGE,
    ]


# --- CA-2: contenido -----------------------------------------------------------------------------------------------------------------------------------


def test_content_every_from_is_pinned_by_digest_and_the_image_has_no_unsafe_flags() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    froms = [line for line in text.splitlines() if line.startswith("FROM ")]
    assert froms and all("@sha256:" in line for line in froms)
    forbidden = re.compile(
        r"no-sandbox|ignore_https_errors|ignore-certificate-errors([^-]|$)|NODE_TLS_REJECT_UNAUTHORIZED"
    )
    offenders = [
        str(path.relative_to(UNIT))
        for path in [DOCKERFILE, *(UNIT / "src").rglob("*.py")]
        if forbidden.search(path.read_text(encoding="utf-8"))
    ]
    assert (
        offenders == []
    )  # ni en el Dockerfile ni en `src/` (la CA es la unica via; el sandbox se pide, no se baja)
    oidc = (UNIT / "src/vectra_verification/clients/oidc.py").read_text(encoding="utf-8")
    assert "chromium_sandbox=sandbox" in oidc and "ignore-certificate-errors-spki-list" in oidc


def test_content_python_playwright_chromium_and_the_workspace_packages() -> None:
    code = (
        "import importlib.metadata as m, json, os, sys\n"
        "names = {d.metadata['Name'].lower().replace('_', '-') for d in m.distributions()}\n"
        "try:\n"
        "    import vectra_common\n"
        "    common = True\n"
        "except ImportError:\n"
        "    common = False\n"
        "print(json.dumps({'python': list(sys.version_info[:2]), 'playwright': m.version('playwright'),\n"
        "  'browsers': sorted(os.listdir(os.environ['PLAYWRIGHT_BROWSERS_PATH'])),\n"
        "  'verification': 'vectra-verification' in names, 'contracts': 'vectra-contracts' in names, 'common': common,\n"
        "  'common_dist': 'vectra-common' in names}))"
    )
    done = in_image(["-c", code])
    assert done.returncode == 0, done.stderr
    seen = json.loads(done.stdout)
    assert seen == {
        "python": [3, 12],
        "playwright": "1.64.0",
        "browsers": ["chromium_headless_shell-1248"],  # solo Chromium, revision 1248; ningun otro navegador
        "verification": True,
        "contracts": True,
        "common": False,
        "common_dist": False,
    }


def test_content_kubectl_is_the_real_one_of_the_cluster_version() -> None:
    done = in_image(["version", "--client"], entrypoint="kubectl")
    assert done.returncode == 0, done.stderr
    assert re.search(r"Client Version: v1\.37\.\d+", done.stdout), done.stdout
    cluster = (REPO / "platform" / "kind" / "cluster.yaml").read_text(encoding="utf-8")
    assert "kindest/node:v1.37.0" in cluster  # la version del nodo de kind, de la que sale la del binario


def test_content_no_argocd_helm_k6_git_curl_and_no_kubernetes_manifests() -> None:
    script = (
        "for tool in argocd helm k6 git curl wget; do command -v $tool && echo FOUND:$tool; done; "
        "python - <<'PY'\n"
        "import re, pathlib\n"
        "api, kind = re.compile(r'^\\s*apiVersion:\\s*\\S+', re.M), re.compile(r'^\\s*kind:\\s*\\S+', re.M)\n"
        "hits = []\n"
        "for root in ('/opt', '/usr/local', '/etc', '/verification', '/usr/share', '/var'):\n"
        "    for path in pathlib.Path(root).rglob('*'):\n"
        "        if path.suffix in ('.patch',) or path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:  # un parche es un diff (`git apply`), no un manifiesto\n"
        "            continue\n"
        "        try:\n"
        "            text = path.read_text(encoding='utf-8')\n"
        "        except (UnicodeDecodeError, OSError):\n"
        "            continue\n"
        "        if api.search(text) and kind.search(text):\n"
        "            hits.append(str(path))\n"
        "print('MANIFESTS:' + ','.join(hits))\n"
        "PY"
    )
    done = in_image(["-c", script], entrypoint="sh")
    assert done.returncode == 0, done.stderr
    assert "FOUND:" not in done.stdout, done.stdout
    assert done.stdout.strip().splitlines()[-1] == "MANIFESTS:", done.stdout


def test_content_the_default_user_is_65532_and_no_file_is_writable_by_others_outside_tmp() -> None:
    config = docker(
        "image",
        "inspect",
        IMAGE,
        "--format",
        "{{.Config.User}}|{{.Config.Entrypoint}}|{{.Config.WorkingDir}}",
    )
    assert config.stdout.strip() == "65532:65532|[vectra-verification]|/verification"
    default_user = docker("run", "--rm", "--read-only", "--entrypoint", "id", IMAGE, "-u")
    assert default_user.stdout.strip() == "65532"
    done = in_image(
        [
            "/",
            "-xdev",
            "-not",
            "-path",
            "/proc/*",
            "-not",
            "-path",
            "/tmp",
            "-not",
            "-path",
            "/var/tmp",
            "-perm",
            "-0002",
            "!",
            "-perm",
            "-1000",  # un directorio con el bit pegajoso (`/run/lock`, como `/tmp`) no deja borrar lo ajeno
            "!",
            "-type",
            "l",
        ],
        entrypoint="find",
    )
    assert done.stdout.strip() == "", f"archivos con escritura para otros: {done.stdout}"


def _arg(name: str) -> str:
    match = re.search(rf"^ARG {name}=(\S+)$", DOCKERFILE.read_text(encoding="utf-8"), re.M)
    assert match, f"el Dockerfile no fija ARG {name}"
    return match.group(1)


def _flip_a_digit(value: str) -> str:
    return ("0" if value[0] != "0" else "1") + value[1:]


def test_content_every_download_has_a_fixed_version_and_a_sha256() -> None:
    assert re.fullmatch(r"v1\.37\.\d+", _arg("KUBECTL_VERSION"))
    assert HEX64.match(_arg("KUBECTL_SHA256")) and HEX64.match(_arg("CHROMIUM_SHA256"))
    assert _arg("CHROMIUM_REVISION") == "1248" and re.fullmatch(
        r"\d+\.\d+\.\d+\.\d+", _arg("CHROMIUM_VERSION")
    )
    lock = (UNIT / "image" / "apt.lock").read_text(encoding="utf-8").splitlines()
    assert len(lock) > 20
    for line in lock:
        name, version, arch, sha, filename = line.split(" ")
        assert (
            name and version and arch in {"amd64", "all"} and HEX64.match(sha) and filename.endswith(".deb")
        ), line
    requirements = (UNIT / "image" / "requirements.txt").read_text(encoding="utf-8")
    assert "playwright==1.64.0" in requirements and requirements.count("--hash=sha256:") > 20


def _build_fails(*arguments: str) -> subprocess.CompletedProcess[str]:
    done = docker("build", "--progress=plain", "-f", str(DOCKERFILE), *arguments, str(REPO), timeout=600)
    assert done.returncode != 0, "la construccion deberia fallar con una suma alterada"
    return done


def test_content_the_build_fails_when_a_digit_of_the_kubectl_sum_changes() -> None:
    done = _build_fails(
        "--target", "fetch", "--build-arg", f"KUBECTL_SHA256={_flip_a_digit(_arg('KUBECTL_SHA256'))}"
    )
    assert "SHA-256 distinto" in done.stdout + done.stderr


def test_content_the_build_fails_when_a_digit_of_the_chromium_sum_changes() -> None:
    done = _build_fails(
        "--target", "fetch", "--build-arg", f"CHROMIUM_SHA256={_flip_a_digit(_arg('CHROMIUM_SHA256'))}"
    )
    assert "SHA-256 distinto" in done.stdout + done.stderr


def test_content_the_build_fails_when_a_digit_of_a_deb_sum_changes(work: Path) -> None:
    lines = (UNIT / "image" / "apt.lock").read_text(encoding="utf-8").splitlines()
    name, version, arch, sha, filename = lines[0].split(" ")
    lines[0] = " ".join([name, version, arch, _flip_a_digit(sha), filename])
    context = work / "applock"
    context.mkdir()
    (context / "apt.lock").write_text("\n".join(lines) + "\n", encoding="utf-8")
    done = _build_fails("--target", "debs", "--build-context", f"applock={context}")
    assert "FAILED" in done.stdout + done.stderr and filename in done.stdout + done.stderr


# --- CA-3: el contenedor real --------------------------------------------------------------------------------------------------------------------------


def test_run_help_has_no_effects_and_the_mounted_directory_stays_empty(work: Path) -> None:
    evidence = evidence_dir(work)
    done = docker(
        "run",
        *base_options(user=TEST_USER),
        *mount(evidence, "/verification/evidence", read_only=False),
        IMAGE,
        "--help",
    )
    assert done.returncode == 0, done.stderr
    assert "vectra-verification" in done.stdout and "prepare" in done.stdout and "rt5" in done.stdout
    assert list(evidence.iterdir()) == []


def test_run_prepare_writes_the_manifest_and_the_patch_as_the_user_and_they_pass_the_filter(
    work: Path,
) -> None:
    evidence = evidence_dir(work)
    name = unique_name("prepare")
    try:
        done = docker(*prepare_command(evidence, name=name))
        assert done.returncode == 0, done.stdout + done.stderr
        files = sorted(p.name for p in evidence.iterdir())
        assert files == ["case-management-runid.patch", "manifest.json"]
        for path in evidence.iterdir():
            assert path.stat().st_uid == 12345 and path.stat().st_gid == 12345, path
        from vectra_verification import evidence as filter_

        for path in evidence.iterdir():
            filter_.prepare(path.read_text(encoding="utf-8"), ())  # el filtro de evidencias no se niega
        manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
        assert (
            re.fullmatch(r"[0-9]{8}-[0-9]{4}", manifest["run_id"])
            and manifest["sections"]["prepare"]["state"] == "terminada"
        )
        # la memoria y el sistema de archivos de solo lectura, tal como los dejo `docker run` (el contenedor no se borro: se inspecciona)
        info = docker(
            "inspect",
            name,
            "--format",
            "{{.HostConfig.Memory}} {{.HostConfig.ReadonlyRootfs}} {{.Config.User}}",
        )
        assert info.stdout.split() == [str(1 << 30), "true", TEST_USER]
        print(
            f"memoria del contenedor: {int(info.stdout.split()[0]) / (1 << 30):.0f} GiB; solo lectura: {info.stdout.split()[1]}"
        )
        # no deja nada fuera del montaje y del tmpfs: `docker diff` lista lo que cambio en la capa del contenedor (solo los puntos de montaje)
        changes = [line for line in docker("diff", name).stdout.splitlines() if line.strip()]
        assert all(
            re.fullmatch(r"[AC] /(verification(/evidence)?|values(/case-management\.yaml)?|tmp)?", line)
            or line.startswith(("A /values", "C /values"))
            for line in changes
        ), changes
    finally:
        docker("rm", "-f", name)


def test_run_prepare_again_is_refused_with_3_and_the_manifest_does_not_change(work: Path) -> None:
    evidence = evidence_dir(work)
    assert docker(*prepare_command(evidence)).returncode == 0
    before = (evidence / "manifest.json").read_bytes()
    done = docker(*prepare_command(evidence))
    assert done.returncode == 3, done.stdout + done.stderr
    assert "prepare_manifest_exists" in done.stderr and (evidence / "manifest.json").read_bytes() == before


def test_run_prepare_with_the_delivery_mounted_read_only_records_it_and_without_the_mount_it_still_prepares(
    work: Path,
) -> None:
    """`prepare --delivery` guarda la ruta (dentro del contenedor) en el manifiesto; no lee la entrega: con o sin el montaje, `prepare` termina. El montaje es de solo lectura."""
    delivery = work / "entrega"
    delivery.mkdir()
    (delivery / "test.parquet").write_bytes(b"PAR1")
    with_mount = evidence_dir(work)
    command = prepare_command(with_mount)
    command[command.index(IMAGE) : command.index(IMAGE)] = mount(delivery, DELIVERY_IN_IMAGE)
    done = docker(*command)
    assert done.returncode == 0, done.stdout + done.stderr
    manifest = json.loads((with_mount / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["paths"]["delivery"] == DELIVERY_IN_IMAGE
    other = work / "sin-montaje"
    other.mkdir()
    other.chmod(0o777)
    without = other / "evidence"
    without.mkdir()
    without.chmod(0o777)
    done = docker(*prepare_command(without))
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads((without / "manifest.json").read_text(encoding="utf-8"))["paths"]["delivery"] == DELIVERY_IN_IMAGE


def test_run_a_section_with_data_and_no_delivery_ends_with_ruta_faltante_code_3(work: Path) -> None:
    """Sin `--delivery` (ni en `prepare`), `rt3` no tiene de donde sacar `--packages-dir`: termina con 3 y `ruta_faltante`, sin traza."""
    evidence = evidence_dir(work)
    command = prepare_command(evidence)
    del command[-2:]  # sin `--delivery`
    assert docker(*command).returncode == 0
    done = docker(
        "run", *base_options(user=TEST_USER),
        *mount(evidence, "/verification/evidence", read_only=False),
        "-e", "VAULT_ADDR=http://127.0.0.1:9", "-e", "VAULT_TOKEN=token-de-prueba",
        IMAGE, "rt3",
    )  # fmt: skip
    assert done.returncode == 3, done.stdout + done.stderr
    assert "ruta_faltante" in done.stdout + done.stderr and "Traceback" not in done.stdout + done.stderr


def test_run_entrada_py_travels_in_the_image_and_builds_the_patch_read_only(work: Path) -> None:
    """`demos/prs/entrada.py` (D1 y D2) corre con el `python3` de la imagen, de solo lectura y sin escribir nada; las plantillas de parche fijas ya no existen."""
    values = work / "model-serving.yaml"
    values.write_text("# valores\ninferenceServices: []\n", encoding="utf-8")
    done = docker(
        "run", *base_options(user=TEST_USER), *mount(values, "/work/model-serving.yaml"),
        "--workdir", "/work", "--entrypoint", "python3",
        IMAGE, "/opt/system-verification/demos/prs/entrada.py", "--values", "/work/model-serving.yaml",
        "--version", "mv-2026-11-13-0123abcd", "--storage-uri", "s3://model-store/proxy/mv-2026-11-13-0123abcd/",
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    assert "+  - { modelVersionId: mv-2026-11-13-0123abcd" in done.stdout and "profile: staging" in done.stdout
    assert values.read_text(encoding="utf-8").endswith("inferenceServices: []\n")
    listing = in_image(["-c", "find /opt/system-verification/demos -name '*.tpl' | wc -l"], entrypoint="sh")
    assert listing.stdout.strip() == "0", listing.stdout


def test_run_without_the_evidence_mount_is_a_clear_error_not_a_traceback() -> None:
    done = docker(
        "run", *base_options(user=TEST_USER), *mount(VALUES, "/values/case-management.yaml"), IMAGE,
        "prepare", "--commit", "c0ffee1", "--operator", "operadora", "--values-file", "/values/case-management.yaml",
        "--delivery", DELIVERY_IN_IMAGE,
    )  # fmt: skip
    assert done.returncode == 3, done.stdout + done.stderr
    assert "store_unwritable" in done.stderr and "Traceback" not in done.stderr + done.stdout


def test_run_with_the_host_user_the_files_belong_to_the_host_user(work: Path) -> None:
    evidence = evidence_dir(work)
    done = docker(*prepare_command(evidence, user=f"{os.getuid()}:{os.getgid()}"))
    assert done.returncode == 0, done.stdout + done.stderr
    assert {p.stat().st_uid for p in evidence.iterdir()} == {os.getuid()}


def test_run_rt5_against_doubles_writes_rt_5_through_the_real_live_backend(work: Path) -> None:
    """`live.py` entero, dentro del contenedor: el `kubectl` de mentira va por delante en el `PATH` y trae su Prometheus (`container_kubectl.py`); `VAULT_ADDR` no responde y `rt5` no lo necesita. El `kubectl` real de la imagen
    sigue en `/usr/local/bin/kubectl` y responde a `version --client`."""
    evidence = evidence_dir(work)
    assert docker(*prepare_command(evidence)).returncode == 0
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    log = work / "kubectl-calls.log"
    log.write_text("", encoding="utf-8")
    log.chmod(0o666)
    KUBECTL_DOUBLE.chmod(KUBECTL_DOUBLE.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    done = docker(
        "run", *base_options(user=TEST_USER),
        *mount(evidence, "/verification/evidence", read_only=False),
        *mount(image_run.DOUBLES, "/doubles"),
        *mount(KUBECTL_DOUBLE, "/usr/local/double/kubectl"),
        *mount(log, "/verification/kubectl-calls.log", read_only=False),
        "-e", "PATH=/usr/local/double:/usr/local/bin:/usr/bin:/bin",
        "-e", f"RT5_RUN_ID={manifest['run_id']}",
        "-e", f"RT5_STARTED_AT={manifest['started_at']}",
        "-e", "DOUBLE_KUBECTL_LOG=/verification/kubectl-calls.log",
        "-e", "VAULT_ADDR=http://127.0.0.1:9", "-e", "VAULT_TOKEN=token-de-prueba",
        IMAGE, "rt5", "--after-job-minutes", "0",
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    assert (
        "RT-5: pasa" in done.stdout and "rt-5: pasa" in done.stdout and "seccion rt5: pasa (0)" in done.stdout
    )
    names = sorted(p.name for p in evidence.iterdir())
    assert names == ["RT-5.json", "case-management-runid.patch", "demo-rt-5.json", "manifest.json"], names
    assert all(p.stat().st_uid == 12345 for p in evidence.iterdir())
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert ["get", "pods"] == [c[0:2] for c in calls if c[:2] == ["get", "pods"]][0]
    assert not [c for c in calls if c[0] not in {"get", "logs", "port-forward"}], calls  # solo lectura
    real = in_image(["version", "--client"], entrypoint="/usr/local/bin/kubectl")
    assert real.returncode == 0 and "v1.37" in real.stdout


# --- CA-4: el sandbox de Chromium ----------------------------------------------------------------------------------------------------------------------


def test_sandbox_chromium_starts_sandboxed_under_the_seccomp_profile_and_never_with_no_sandbox() -> None:
    done = docker(
        "run", *base_options(user=TEST_USER), *mount(image_run.DOUBLES, "/doubles"),
        "--entrypoint", "python", IMAGE, "/doubles/container_login.py", "sandbox",
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    seen = json.loads(done.stdout.strip().splitlines()[-1])
    assert "crash" not in seen, seen
    assert seen["env"] == "1"
    processes = seen["processes"]
    assert processes, "no hay procesos de Chromium"
    assert not [
        p for p in processes if p["no_sandbox_flag"]
    ]  # la linea de ordenes de ningun proceso trae `--no-sandbox`
    sandboxed = [p for p in processes if p["user_ns"] != seen["own_user_ns"] and p["no_new_privs"] == "1"]
    assert sandboxed, f"ningun proceso corre en su propio espacio de nombres de usuario: {processes}"


def test_sandbox_without_the_profile_the_login_ends_with_a_clear_error_and_not_a_hang() -> None:
    options = base_options(user=TEST_USER, seccomp=None)
    done = docker(
        "run", *options, *mount(image_run.DOUBLES, "/doubles"), "--entrypoint", "python", IMAGE, "/doubles/container_login.py", "submit",
        timeout=120,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    seen = json.loads(done.stdout.strip().splitlines()[-1])
    assert seen == {"login": "error", "error": "browser_launch_error"}, seen
    assert "state=" not in done.stderr and "nonce" not in done.stderr


def test_run_without_the_tmpfs_the_login_ends_with_a_clear_error_so_the_readme_requires_it() -> None:
    """Rojo documentado: con `--read-only` y sin `--tmpfs /tmp` (`HOME=/tmp` no se puede escribir) Playwright no arranca; el login termina con un codigo estable, no colgado ni con una traza."""
    done = docker(
        "run", *base_options(user=TEST_USER, tmpfs=False), *mount(image_run.DOUBLES, "/doubles"),
        "--entrypoint", "python", IMAGE, "/doubles/container_login.py", "submit",
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.strip().splitlines()[-1]) == {
        "login": "error",
        "error": "browser_launch_error",
    }


# --- CA-5: la CA en los dos caminos TLS, y nada mas ----------------------------------------------------------------------------------------------------


class Pki:
    """Dos CA, un servidor con el certificado correcto (127.0.0.1) y otro con el certificado de otro nombre, y los archivos montados en `/certs`."""

    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.good = tls_server.Authority("u12t05-ca")
        self.other = tls_server.Authority("u12t05-otra-ca")
        self.good_ca = self.good.write_ca(directory / "ca.pem")
        self.other_ca = self.other.write_ca(directory / "otra-ca.pem")
        self.right_name = self.good.issue(directory, ip="127.0.0.1", dns=["localhost"])
        self.wrong_name = self._wrong_name()

    def _wrong_name(self) -> tuple[Path, Path]:
        other_dir = self.directory / "otro-nombre"
        other_dir.mkdir()
        return self.good.issue(other_dir, ip=None, dns=["otro.example"])


def login_in_container(pki: Pki, server: tls_server.LoginServer, ca: str, mode: str) -> dict[str, object]:
    """El formulario de U12-T02 **dentro** del contenedor, contra el servidor de prueba en `127.0.0.1` (red del host)."""
    options = base_options(user=TEST_USER, network_host=True)
    done = docker(
        "run", *options, *mount(image_run.DOUBLES, "/doubles"), *mount(pki.directory, "/certs"),
        "--entrypoint", "python", IMAGE, "/doubles/container_login.py", "tls", f"127.0.0.1:{server.port}",
        "none" if ca == "none" else f"/certs/{ca}", mode,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    seen: dict[str, object] = json.loads(done.stdout.strip().splitlines()[-1])
    assert "crash" not in seen, seen
    assert seen["store_before"] == seen["store_after"], (
        "el almacen de CA del sistema cambio durante la corrida"
    )
    return seen


@pytest.fixture(scope="module")
def pki() -> Iterator[Pki]:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    directory = SCRATCH / f"pki-{uuid.uuid4().hex[:8]}"
    try:
        yield Pki(directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_tls_with_the_ca_mounted_the_navigation_and_the_subresource_both_load(pki: Pki) -> None:
    with tls_server.LoginServer(*pki.right_name) as server:
        seen = login_in_container(pki, server, "ca.pem", "client")
        assert seen["login"] == "ok" and seen["returned"] == f"https://127.0.0.1:{server.port}/callback", seen
        assert (
            server.pixel_hits >= 1
        )  # el subrecurso lo pidio Chromium (huella SPKI) y la navegacion, Node (`NODE_EXTRA_CA_CERTS`)
        assert server.posts == 1


def test_tls_red_only_node_extra_ca_certs_without_the_spki_pin_the_subresource_fails(pki: Pki) -> None:
    """Rojo primero (F-02 de U12-T02): Node confia en la CA (la navegacion pasa) y Chromium no: el subrecurso no carga."""
    with tls_server.LoginServer(*pki.right_name) as server:
        seen = login_in_container(pki, server, "ca.pem", "node-only")
        assert seen["login"] == "ok", seen
        assert server.pixel_hits == 0


@pytest.mark.parametrize("mode", ["client", "node-only"])
def test_tls_with_another_ca_mounted_both_paths_fail_with_oidc_error(pki: Pki, mode: str) -> None:
    with tls_server.LoginServer(*pki.right_name) as server:
        seen = login_in_container(pki, server, "otra-ca.pem", mode)
        assert seen["login"] == "error" and seen["error"] in {"tls_pin_error", "browser_error"}, seen
        assert server.pixel_hits == 0 and server.posts == 0


@pytest.mark.parametrize("mode", ["client", "node-only"])
def test_tls_without_a_ca_both_paths_fail_with_oidc_error(pki: Pki, mode: str) -> None:
    with tls_server.LoginServer(*pki.right_name) as server:
        seen = login_in_container(pki, server, "none", mode)
        assert seen["login"] == "error" and seen["error"] in {"tls_pin_error", "browser_error"}, seen
        assert server.pixel_hits == 0 and server.posts == 0


@pytest.mark.parametrize("mode", ["client", "node-only"])
def test_tls_a_certificate_valid_for_another_name_fails_both_paths(pki: Pki, mode: str) -> None:
    with tls_server.LoginServer(*pki.wrong_name) as server:
        seen = login_in_container(pki, server, "ca.pem", mode)
        assert seen["login"] == "error" and seen["error"] in {"tls_pin_error", "browser_error"}, seen
        assert server.pixel_hits == 0 and server.posts == 0


def test_tls_the_system_ca_store_of_the_image_is_the_same_in_every_run(pki: Pki) -> None:
    with tls_server.LoginServer(*pki.right_name) as server:
        first = login_in_container(pki, server, "ca.pem", "client")["store_before"]
        second = login_in_container(pki, server, "otra-ca.pem", "client")["store_before"]
    assert first == second and isinstance(first, str) and len(first) == 64
