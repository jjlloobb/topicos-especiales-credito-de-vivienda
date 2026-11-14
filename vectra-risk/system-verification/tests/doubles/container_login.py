"""Lo que `test_image.py` ejecuta **dentro del contenedor** con `python /doubles/container_login.py <modo> ...` (U12-T05, CA-4 y CA-5). Usa el codigo de la imagen (`vectra_verification.clients.oidc`), no una copia.

    tls <host:puerto> <ca|none> <client|node-only>   el formulario de login contra un servidor HTTPS de prueba (`client`: `OidcClient` con la CA y la huella SPKI, como en la herramienta; `node-only`: `HeadlessForm`
                                                     sin huella, solo `NODE_EXTRA_CA_CERTS`)
    sandbox                                          lanza Chromium como lo lanza la herramienta y mira sus procesos en /proc
    submit                                           el formulario contra una URL cualquiera: lo que importa es si Chromium arranca (sin el perfil `seccomp`, `browser_launch_error`)

Imprime **una** linea JSON en stdout. Un fallo que no sea `OidcError` sale como `{"crash": ...}`: la prueba lo trata como error de la prueba o de la imagen."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from vectra_verification import guard
from vectra_verification.clients.oidc import HeadlessForm, OidcClient, OidcError
from vectra_verification.clock import Clock
from vectra_verification.credentials import Secret

STORES = ("/etc/ssl/certs", "/usr/local/share/ca-certificates", "/usr/share/ca-certificates")


def system_store() -> str:
    """Una huella del almacen de CA del sistema: nombres y contenido de lo que hay en las rutas habituales."""
    digest = hashlib.sha256()
    for root in STORES:
        for path in sorted(Path(root).rglob("*")) if Path(root).exists() else []:
            digest.update(str(path).encode())
            if path.is_file() and not path.is_symlink():
                digest.update(path.read_bytes())
    return digest.hexdigest()


def tls(address: str, ca: str, mode: str) -> dict[str, object]:
    host, port = address.rsplit(":", 1)
    ca_file = None if ca == "none" else Path(ca)
    issuer = f"https://{host}:{port}/auth/realms/vectra"
    environment = guard.Environment("kind", host, issuer)
    guard.ENVIRONMENTS = (*guard.ENVIRONMENTS, environment)  # la barrera acepta este entorno de prueba
    client = OidcClient(environment, None, Clock(), ca_file=ca_file)  # type: ignore[arg-type]
    result: dict[str, object] = {"store_before": system_store()}
    try:
        form = client._form_driver() if mode == "client" else HeadlessForm(None, ca_file=ca_file)  # noqa: SLF001
        returned = form.submit(
            f"{issuer}/protocol/openid-connect/auth?state=s",
            f"https://{host}:{port}/callback",
            "usuario",
            Secret("contrasena-de-prueba"),
            lambda: "123456",
        )
        result["login"] = "ok"
        result["returned"] = returned.split("?")[0]
        form.close()
    except OidcError as error:
        result["login"] = "error"
        result["error"] = str(error)
    result["store_after"] = system_store()
    return result


def sandbox() -> dict[str, object]:
    form = HeadlessForm(None)
    browser = form._launch()  # noqa: SLF001 - igual que en `submit`
    page = browser.new_page()
    page.set_content("<p>hola</p>")
    processes = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().decode(errors="replace").split("\0")
            status = dict(
                line.split(":\t", 1) for line in (entry / "status").read_text().splitlines() if ":\t" in line
            )
        except OSError:
            continue
        if not cmdline or "chrome-headless-shell" not in cmdline[0]:
            continue
        kind = next((a.split("=", 1)[1] for a in cmdline if a.startswith("--type=")), "browser")
        processes.append(
            {
                "type": kind,
                "no_sandbox_flag": "--no-sandbox" in cmdline,
                "seccomp": status.get("Seccomp", "").strip(),
                "no_new_privs": status.get("NoNewPrivs", "").strip(),
                "user_ns": os.readlink(entry / "ns" / "user"),
            }
        )
    own = os.readlink("/proc/self/ns/user")
    form.close()
    return {
        "processes": processes,
        "own_user_ns": own,
        "env": os.environ.get("VERIFICATION_CHROMIUM_SANDBOX"),
    }


def submit() -> dict[str, object]:
    form = HeadlessForm(None)
    try:
        form.submit("https://127.0.0.1:1/auth", "https://127.0.0.1:1/callback", "u", Secret("p"), lambda: "1")
    except OidcError as error:
        return {"login": "error", "error": str(error)}
    finally:
        form.close()
    return {"login": "ok"}


def main(argv: list[str]) -> int:
    try:
        if argv[0] == "tls":
            result = tls(argv[1], argv[2], argv[3])
        elif argv[0] == "sandbox":
            result = sandbox()
        elif argv[0] == "submit":
            result = submit()
        else:
            return 2
    except Exception as error:  # noqa: BLE001 - la prueba lo ve como {"crash": ...}
        result = {"crash": f"{type(error).__name__}: {str(error)[:300]}"}
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
