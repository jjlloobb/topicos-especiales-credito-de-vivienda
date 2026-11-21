"""El servidor se niega a arrancar con un kubeconfig que no sea el de `vectra-readonly-agent`.

Dos comprobaciones, las dos obligatorias:

1. **El archivo** (`check_file`, sin red): existe, es 0600, no es `~/.kube/config`, tiene un solo contexto `kind-*`, un solo usuario que se autentica solo
   con `token` (el de administrador de kind usa certificado de cliente), y el `sub` de ese token es `system:serviceaccount:argocd:vectra-readonly-agent`.
   El `sub` se lee del token sin verificar la firma: la firma la verifica el API en cada peticion; aqui solo se descarta el archivo equivocado.
2. **La identidad viva** (`check_live`): `kubectl auth can-i` debe responder «no» a cada fila de `MUST_BE_NO` y «yes» a `MUST_BE_YES`. Una fila sin
   respuesta (API caido) tambien es una negativa: falla cerrado.

El token nunca se imprime ni se guarda fuera del archivo.
"""

from __future__ import annotations

import base64
import json
import os
import stat
from pathlib import Path
from typing import Any, Final

import yaml

from vectra_mcp_readonly.kubectl import K8sError, Kubectl

ENV_VAR: Final = "VECTRA_READONLY_KUBECONFIG"
DEFAULT_PATH: Final = "~/.kube/kind-vectra-readonly"
EXPECTED_SUBJECT: Final = "system:serviceaccount:argocd:vectra-readonly-agent"
#: (verbo, recurso, subrecurso), preguntadas en todos los namespaces. Un «yes» en cualquiera detiene el arranque.
MUST_BE_NO: Final[tuple[tuple[str, str, str | None], ...]] = (
    ("create", "pods", None),
    ("delete", "pods", None),
    ("patch", "deployments", None),
    ("get", "secrets", None),
    ("list", "secrets", None),
    ("create", "pods", "exec"),
    ("impersonate", "users", None),
)
MUST_BE_YES: Final[tuple[tuple[str, str, str | None], ...]] = (("get", "pods", None),)


class StartupRefused(Exception):
    """El kubeconfig no es el de solo lectura: el servidor no arranca."""


def kubeconfig_path(environ: dict[str, str] | os._Environ[str]) -> Path:
    """La ruta de `VECTRA_READONLY_KUBECONFIG` o la fija. Nunca `KUBECONFIG` ni `~/.kube/config`."""
    raw = environ.get(ENV_VAR) or DEFAULT_PATH
    return Path(raw).expanduser()


def _subject(token: object) -> str | None:
    if not isinstance(token, str) or token.count(".") != 2:
        return None
    payload = token.split(".")[1]
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, TypeError):
        return None
    subject = claims.get("sub") if isinstance(claims, dict) else None
    return subject if isinstance(subject, str) else None


def check_file(path: Path, home: Path | None = None) -> str:
    """Devuelve el nombre del unico contexto, o lanza `StartupRefused` con el motivo (sin el token)."""
    home = home if home is not None else Path.home()
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise StartupRefused(
            f"no se pudo leer el kubeconfig {path} ({type(error).__name__}): corre platform/kind/readonly-kubeconfig.sh write"
        ) from None
    if resolved == (home / ".kube" / "config").resolve():  # antes de abrirlo: el de administrador ni se lee
        raise StartupRefused(f"{path} es el kubeconfig de administrador (~/.kube/config)")
    if not resolved.is_file():
        raise StartupRefused(f"{path} no es un archivo")
    try:
        mode = stat.S_IMODE(resolved.stat().st_mode)
        document: Any = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise StartupRefused(
            f"no se pudo leer el kubeconfig {path} ({type(error).__name__}): corre platform/kind/readonly-kubeconfig.sh write"
        ) from None
    if mode & 0o077:
        raise StartupRefused(f"{path} tiene permisos {mode:o} y lleva un token: debe ser 600")
    if not isinstance(document, dict):
        raise StartupRefused(f"{path} no es un kubeconfig")
    contexts, users = document.get("contexts"), document.get("users")
    if not isinstance(contexts, list) or len(contexts) != 1 or not isinstance(users, list) or len(users) != 1:
        raise StartupRefused(f"{path} debe tener un solo contexto y un solo usuario")
    context, user = contexts[0], users[0]
    if not isinstance(context, dict) or not isinstance(user, dict):
        raise StartupRefused(f"{path} no es un kubeconfig")
    name = context.get("name")
    if not isinstance(name, str) or not name.startswith("kind-") or document.get("current-context") != name:
        raise StartupRefused(f"{path}: el contexto debe ser de kind (kind-*) y ser el actual")
    reference = context.get("context")
    if not isinstance(reference, dict) or reference.get("user") != user.get("name"):
        raise StartupRefused(f"{path}: el contexto no usa al unico usuario del archivo")
    credentials = user.get("user")
    if not isinstance(credentials, dict) or set(credentials) != {"token"}:
        raise StartupRefused(
            f"{path}: el usuario debe autenticarse solo con `token` (sin certificado de cliente, exec, as ni contrasena)"
        )
    subject = _subject(credentials["token"])
    if subject != EXPECTED_SUBJECT:
        raise StartupRefused(f"{path}: la identidad del token es {subject!r} y debe ser {EXPECTED_SUBJECT!r}")
    return name


def check_live(kubectl: Kubectl) -> None:
    """La identidad, preguntada al API: no escribe, no lee Secrets, no entra a un pod; si lee pods."""
    for expected, rows in ((False, MUST_BE_NO), (True, MUST_BE_YES)):
        for verb, resource, subresource in rows:
            label = f"{verb} {resource}{'/' + subresource if subresource else ''}"
            try:
                answer = kubectl.can_i(verb, resource, None, subresource)
            except K8sError as error:
                raise StartupRefused(
                    f"`auth can-i {label}` no obtuvo respuesta ({error}): sin confirmar la identidad no se arranca"
                ) from None
            if answer is not expected:
                wanted = "yes" if expected else "no"
                raise StartupRefused(
                    f"`auth can-i {label}` debe responder {wanted}: la identidad no es la de solo lectura"
                )
