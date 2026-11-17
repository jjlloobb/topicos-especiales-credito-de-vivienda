"""Ejecucion de la funcion `vv` de la guia con un `docker` falso (U12-T09, R-01 y G-01).

Ninguna prueba de `system-verification` ejecuta texto extraido de un documento: lo que se comprueba de la guia se comprueba como **texto** (analisis estatico). Lo unico que corre es esta definicion FIJA de `vv`, `humo` y
`vectra-verification` (copiada aqui, no extraida de la guia; una prueba compara como texto que la guia trae la misma), con una de las colas FIJAS de `TAILS`: `run_vv` no acepta texto arbitrario, ni de la guia ni de
nadie. Corre con un `PATH` de **un solo directorio** (un `docker` falso, el `id` real enlazado y centinelas de `kubectl`, `argocd`, `helm` y `gh` que dejan constancia), sin `env`, `bash` ni `sh` enlazados (el interprete se
lanza por ruta absoluta desde Python), y con el entorno armado desde cero.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

VV_DEFINITION = r"""vv() {
  docker run --rm --name "vectra-verification-$$-$RANDOM" --read-only --tmpfs /tmp --network host \
    --user "$(id -u):$(id -g)" --memory 1g \
    --add-host "vectra.localtest.me:${GATEWAY_ADDRESS:?lee la dirección del gateway: platform/kind/gateway-address.sh}" \
    --security-opt seccomp=system-verification/seccomp/chrome.json \
    --mount type=bind,source="$VERIF_HOME/kubeconfig",target=/kube/config,readonly -e KUBECONFIG=/kube/config \
    --mount type=bind,source="$VERIF_HOME/vectra-ca.pem",target=/certs/ca.pem,readonly -e VERIFICATION_CA_FILE=/certs/ca.pem \
    --mount type=bind,source="$EVID",target=/verification/evidence \
    --mount type=bind,source="$PWD/vectra-risk-gitops/values/kind/case-management.yaml",target=/values/case-management.yaml,readonly \
    --mount type=bind,source="$PWD/reference-model/.out",target=/verification/reference-model/.out,readonly \
    -e VAULT_ADDR -e VAULT_TOKEN -e KUBE_CONTEXT \
    "${VV_EXTRA[@]}" "$VERIFICATION_IMAGE" "$@"
}
vectra-verification() { vv "$@"; }   # el nombre con que la guía llama a la herramienta
humo() { local VV_EXTRA=(--mount type=bind,source="$PWD/system-verification/docs/kind/humo.py",target=/humo.py,readonly --entrypoint python); vv /humo.py "$@"; }
"""

# Las unicas colas que se pueden correr (el nombre es la clave): cada una es una linea fija, escrita aqui.
TAILS = {
    "report": "vv report",
    "three": "vv prepare --commit abc\nhumo flujo --delivery /d\nvectra-verification report",
}
SENTINELS = ("kubectl", "argocd", "helm", "gh")
ALLOWED_ENV = frozenset(
    {"DOCKER_OUT", "VERIF_HOME", "EVID", "VERIFICATION_IMAGE", "VAULT_ADDR", "VAULT_TOKEN", "GATEWAY_ADDRESS"}
)


class NotAFixedCase(Exception):
    """Se pidio correr algo que no es una de las colas fijas: no se lanzo nada."""


def build_path(tmp_path: Path, fake_docker: str) -> tuple[Path, Path]:
    """El `PATH` de un solo directorio y el registro de los centinelas."""
    bin_dir = tmp_path / "vv-bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "sentinel.log"
    log.write_text("", encoding="utf-8")
    real_id = shutil.which("id")
    assert real_id is not None
    if not (bin_dir / "id").exists():
        (bin_dir / "id").symlink_to(real_id)
    for name in SENTINELS:
        (bin_dir / name).write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\nexit 99\n', encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    (bin_dir / "docker").write_text(fake_docker, encoding="utf-8")
    (bin_dir / "docker").chmod(0o755)
    return bin_dir, log


def run_vv(
    tail: str, tmp_path: Path, fake_docker: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Corre `VV_DEFINITION` y la cola fija `tail` (una clave de `TAILS`). Cualquier otra entrada se rechaza antes de lanzar nada."""
    if tail not in TAILS:
        raise NotAFixedCase(f"no es una cola fija: {tail[:40]!r}")
    unknown = set(env) - ALLOWED_ENV
    if unknown:
        raise NotAFixedCase(f"variables de entorno no previstas: {sorted(unknown)}")
    bash = shutil.which("bash")
    assert bash is not None
    bin_dir, log = build_path(tmp_path, fake_docker)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    full_env = {"PATH": str(bin_dir), "HOME": str(home), "LANG": "C", **env}
    done = subprocess.run(  # noqa: S603 - bash por ruta absoluta; el texto es VV_DEFINITION y una cola de TAILS
        [bash, "-c", f"{VV_DEFINITION}\n{TAILS[tail]}\n"],
        env=full_env, capture_output=True, text=True, check=False, cwd=tmp_path,
    )  # fmt: skip
    called = log.read_text(encoding="utf-8").strip()
    assert called == "", f"una herramienta del cluster fue llamada: {called}"
    return done
