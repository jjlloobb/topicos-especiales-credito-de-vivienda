#!/usr/bin/env python3
"""Rutas de la boveda que usan los ExternalSecret de kind, y su siembra en Vault dev (INF-U1-10).

`list`: imprime `ruta propiedad` de U1 y de U2 (`identity/` y `edge/`), sin tocar ningun cluster.
`seed`: escribe cada ruta de U1 en Vault con `kubectl exec`. Conserva lo que ya exista y genera el resto al azar, asi que se
puede repetir. Lo ejecuta un operador por medio de `seed-vault.sh`; nunca CI.
`seed-identity`: las rutas de U2 (U02-T19, B-2). Estas no pueden ser al azar: `identity/clients/<id>` lleva un par ES256 real,
`identity/ca` el certificado de `vectra-internal-ca` y `identity/synthetic-users` contrasenas y semillas TOTP con forma valida.
Nunca regenera un par de llaves que ya exista (romperia los tokens vigentes). Ademas escribe las llaves privadas y la CA en un
directorio local fuera del repositorio, para las pruebas e2e y de carga.

Recuperar antes de generar (U01-T16): un reinicio de la maquina vacia la boveda, pero los `Secret` que ESO dejo en el cluster siguen
alli (`deletionPolicy: Retain`). Para cada propiedad que falte en la boveda, `seed` y `seed-identity` buscan su valor en esos `Secret`,
y solo generan uno nuevo si no hay de donde recuperarlo. El cruce propiedad -> `Secret`/clave sale de los `ExternalSecret` VIVOS
(`kubectl get externalsecrets -A`): cubre tambien los `*-client` de U3 a U11, que viven en charts y no estan entre las fuentes de abajo.
Al terminar informan, por ruta, cuantas propiedades se conservaron, recuperaron y generaron (con los nombres de las generadas, nunca
los valores).

Las rutas salen de lo renderizado y no de una lista a mano: un ExternalSecret nuevo se siembra sin tocar este archivo,
siempre que su manifiesto este en SOURCES (lo comprueba `tests/test_vault_paths.py`).
"""

import base64
import hashlib
import json
import os
import re
import secrets
import shlex
import string
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509 import load_pem_x509_certificate

PLATFORM = Path(__file__).resolve().parents[1]
DATA_CHART = PLATFORM / "data/chart"
SOURCES = [
    PLATFORM / "observability/grafana/external-secrets.yaml",
    PLATFORM / "observability/grafana/manifests.yaml",
    PLATFORM / "restore-drill/cronjob.yaml",
    *sorted((PLATFORM / "secrets").glob("*.yaml")),
]
EDGE = PLATFORM.parent / "identity-edge"
#: Los ExternalSecret de U2 en kind, ya renderizados (`make -C identity-edge render-keycloak render-jobs render-valkey`).
IDENTITY_SOURCES = [
    *sorted((EDGE / "keycloak/rendered/kind").glob("*.yaml")),
    *sorted((EDGE / "jobs/rendered/kind").glob("*.yaml")),
    *sorted((EDGE / "charts/valkey/rendered/kind").glob("*.yaml")),
    EDGE / "ratelimit/external-secret.yaml",
]
REALM_KIND = EDGE / "keycloak/realm/realm.kind.yaml"
GATEWAY_KIND_VALUES = EDGE / "gateway/values/kind.yaml"
#: Rutas del contrato de INF-U2-01 que ningun ExternalSecret de kind lee (el realm de kind no usa `BREAK_GLASS_PASSWORD`).
IDENTITY_EXTRA = {"identity/break-glass": {"BREAK_GLASS_PASSWORD"}}
#: El Secret de cert-manager con la CA interna (`platform/mesh/certificates.yaml`); solo se lee su certificado publico.
CA_SECRET = ("cert-manager", "vectra-internal-ca")
CLIENTS_PREFIX = "identity/clients/"
#: Usuario del administrador de arranque si `VECTRA_KC_ADMIN_USER` no dice otro (solo al sembrar; despues se conserva el de la boveda).
DEFAULT_ADMIN_USER = "admin"
#: Fuera del repositorio, con permisos 0700.
KEYS_DIR_DEFAULT = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / "vectra-e2e-keys"  # noqa: S108
ALPHANUMERIC = string.ascii_letters + string.digits
MINIO_VALUES = PLATFORM / "data/minio/values-kind.yaml"
ACCESS_KEY_PROPERTIES = {"accessKey", "access_key_id"}
#: Se reemplaza con `seed-vault.sh grafana-token`, cuando Grafana ya existe.
TOKEN_PENDING = "pendiente-de-bootstrap"  # noqa: S105
#: El relay de notificaciones (F72) es del banco. En kind, una URL valida que no entrega nada.
RELAY_KIND = "http://127.0.0.1:9/sin-relay-en-kind"
NOT_FOUND = 2  # codigo de salida de `vault kv get` cuando la ruta no existe
#: Una plantilla de ESO que copia el valor entero (`{{ .clave }}`): el `Secret` guarda el mismo valor que la boveda.
LITERAL_TEMPLATE = re.compile(r"^\s*\{\{\s*\.(\w+)\s*\}\}\s*$")
EXTERNAL_SECRETS = "externalsecrets.external-secrets.io"
Refs = dict[str, set[str]]
Runner = Callable[[list[str], str | None], "subprocess.CompletedProcess[str]"]


def render_data_chart() -> str:
    command = ["helm", "template", "data", str(DATA_CHART), "-f", str(DATA_CHART / "values-kind.yaml")]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout  # noqa: S603


def external_secrets(text: str) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(text) if d and d.get("kind") == "ExternalSecret"]


def platform_external_secrets() -> list[dict[str, Any]]:
    found = external_secrets(render_data_chart())
    for path in SOURCES:
        found += external_secrets(path.read_text(encoding="utf-8"))
    return found


def identity_external_secrets() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for path in IDENTITY_SOURCES:
        found += external_secrets(path.read_text(encoding="utf-8"))
    return found


def all_external_secrets() -> list[dict[str, Any]]:
    return platform_external_secrets() + identity_external_secrets()


def service_account_clients() -> list[str]:
    """Los clientes de `realm.kind.yaml` con cuenta de servicio: los que firman aserciones (`private_key_jwt`)."""
    realm = yaml.safe_load(REALM_KIND.read_text(encoding="utf-8"))
    return sorted(c["clientId"] for c in realm["clients"] if c.get("serviceAccountsEnabled"))


def identity_refs(documents: list[dict[str, Any]]) -> Refs:
    """Lo que leen los ExternalSecret de U2, mas lo que el contrato pide sin que kind lo lea: la llave privada de cada cliente de servicio."""
    refs = collect(documents)
    for path, properties in IDENTITY_EXTRA.items():
        refs.setdefault(path, set()).update(properties)
    for client in service_account_clients():
        refs.setdefault(f"{CLIENTS_PREFIX}{client}", set()).update({"jwks", "private-key"})
    return refs


def collect(documents: list[dict[str, Any]]) -> Refs:
    refs: Refs = {}
    for document in documents:
        if document["spec"].get("dataFrom"):
            raise ValueError(f"{document['metadata']['name']}: `dataFrom` no dice que propiedades sembrar")
        for item in document["spec"]["data"]:
            refs.setdefault(item["remoteRef"]["key"], set()).add(item["remoteRef"]["property"])
    return refs


def minio_users(documents: list[dict[str, Any]]) -> dict[str, str]:
    """Ruta de la boveda -> `accessKey` del usuario de MinIO que usa esa ruta para su clave."""
    values = yaml.safe_load(MINIO_VALUES.read_text(encoding="utf-8"))
    by_secret = {u["existingSecret"]: u["accessKey"] for u in values["users"]}
    found: dict[str, str] = {}
    for document in documents:
        user = by_secret.get(document["metadata"]["name"])
        if user is not None and document["metadata"]["namespace"] == "vectra-data":
            for item in document["spec"]["data"]:
                found[item["remoteRef"]["key"]] = user
    return found


def fixed_value(path: str, prop: str, users: dict[str, str]) -> str | None:
    """Lo que no puede ser aleatorio. CloudNativePG exige que el usuario sea el rol; MinIO, que sea el del chart."""
    if path.startswith("postgres/roles/") and prop == "username":
        return path.rsplit("/", 1)[1]
    if prop in ACCESS_KEY_PROPERTIES and path in users:
        return users[path]
    if path == "alertmanager/relay" and prop == "url":
        return RELAY_KIND
    if path == "grafana/admin" and prop == "user":
        return "admin"
    return None


@dataclass
class PathReport:
    """Lo que paso con las propiedades de una ruta. Solo nombres y cuentas: ningun valor."""

    kept: int = 0
    recovered: int = 0
    fixed: int = 0
    derived: int = 0
    generated: list[str] = field(default_factory=list)
    #: propiedad generada -> `namespace/Secret` donde solo existe dentro de una plantilla (no se pudo copiar)
    templated: dict[str, list[str]] = field(default_factory=dict)


class Report:
    """El informe de la siembra, por ruta."""

    def __init__(self) -> None:
        self.paths: dict[str, PathReport] = {}

    def path(self, path: str) -> PathReport:
        return self.paths.setdefault(path, PathReport())

    def lines(self) -> list[str]:
        out = []
        for path, line in sorted(self.paths.items()):
            text = f"{path}: conservadas {line.kept}, recuperadas {line.recovered}, generadas {len(line.generated)}"
            if line.generated:
                text += f" ({', '.join(line.generated)})"
            if line.fixed:
                text += f", fijas {line.fixed}"
            if line.derived:
                text += f", derivadas de lo que ya existe {line.derived}"
            out.append(text)
            out += [f"  {prop}: solo vive dentro de una plantilla ({', '.join(places)}); no se copia, se generó" for prop, places in sorted(line.templated.items())]
        generated = {path: line.generated for path, line in self.paths.items() if line.generated}
        if generated:
            out.append(f"Se generaron valores nuevos en {len(generated)} ruta(s): lo que los guardaba (Keycloak, MinIO, Grafana, PostgreSQL, Valkey) hay que realinearlo (install.md, «Vault reiniciado»).")
        else:
            out.append("Todo se conservó o se recuperó: nada que realinear.")
        return out


class RecoveryConflict(RuntimeError):
    """La misma propiedad esta sembrada en varios `Secret` con valores distintos: no se elige en silencio."""


@dataclass(frozen=True)
class Origin:
    namespace: str
    secret: str
    key: str

    def __str__(self) -> str:
        return f"{self.namespace}/{self.secret}"


def kubectl_error(result: "subprocess.CompletedProcess[str]", what: str) -> RuntimeError:
    return RuntimeError(f"No se pudo leer {what}: {result.stderr.strip()}")


class ClusterSecrets:
    """Lo que el cluster guarda: los `ExternalSecret` (que dicen que propiedad de la boveda va a que `Secret`) y los `Secret` mismos. Solo `get`."""

    def __init__(self, context: str, run: Runner | None = None) -> None:
        self.context = context
        self.run = run or kubectl_runner
        self._secrets: dict[tuple[str, str], dict[str, str] | None] = {}

    def external_secrets(self) -> list[dict[str, Any]]:
        result = self.run(["kubectl", "--context", self.context, "get", EXTERNAL_SECRETS, "-A", "-o", "json"], None)
        if result.returncode != 0:
            if "resource type" in result.stderr or "NotFound" in result.stderr:  # sin el CRD (ESO todavia no esta): no hay nada que recuperar
                return []
            raise kubectl_error(result, "los ExternalSecret")
        return json.loads(result.stdout)["items"] if result.stdout.strip() else []

    def secret(self, namespace: str, name: str) -> dict[str, str] | None:
        """Los valores de un `Secret`, o None si no existe. Una lectura por `Secret`, con cache."""
        if (namespace, name) not in self._secrets:
            result = self.run(["kubectl", "--context", self.context, "get", "secret", name, "-n", namespace, "-o", "json"], None)
            if result.returncode == 0:
                data = json.loads(result.stdout).get("data") or {}
                self._secrets[(namespace, name)] = {key: base64.b64decode(value).decode() for key, value in data.items()}
            elif "NotFound" in result.stderr or "not found" in result.stderr:
                self._secrets[(namespace, name)] = None
            else:
                raise kubectl_error(result, f"el Secret {namespace}/{name}")
        return self._secrets[(namespace, name)]


class Recoverer:
    """Busca en los `Secret` del cluster el valor de una propiedad de la boveda. Solo copias literales; lo demas se informa."""

    def __init__(self, cluster: ClusterSecrets) -> None:
        self.cluster = cluster
        self._index: tuple[dict[tuple[str, str], list[Origin]], dict[tuple[str, str], list[str]]] | None = None

    def index(self) -> tuple[dict[tuple[str, str], list[Origin]], dict[tuple[str, str], list[str]]]:
        if self._index is None:
            literal: dict[tuple[str, str], list[Origin]] = {}
            templated: dict[tuple[str, str], list[str]] = {}
            for document in self.cluster.external_secrets():
                target = document["spec"].get("target") or {}
                namespace, name = document["metadata"]["namespace"], target.get("name") or document["metadata"]["name"]
                template = target.get("template") or {}
                template_data = template.get("data") or {}
                for item in document["spec"].get("data") or []:
                    ref = (item["remoteRef"]["key"], item["remoteRef"].get("property", ""))
                    if not template_data and not template.get("templateFrom"):
                        literal.setdefault(ref, []).append(Origin(namespace, name, item["secretKey"]))
                        continue
                    copies = [key for key, text in template_data.items() if (m := LITERAL_TEMPLATE.match(str(text))) and m.group(1) == item["secretKey"]]
                    if copies:
                        literal.setdefault(ref, []).extend(Origin(namespace, name, key) for key in copies)
                    else:
                        templated.setdefault(ref, []).append(f"{namespace}/{name}")
            self._index = (literal, templated)
        return self._index

    def find(self, path: str, prop: str) -> str | None:
        """El valor de la propiedad en el cluster, o None. Dos `Secret` con valores distintos: `RecoveryConflict`."""
        found: dict[str, list[Origin]] = {}
        for origin in self.index()[0].get((path, prop), []):
            content = self.cluster.secret(origin.namespace, origin.secret)
            if content and content.get(origin.key):
                found.setdefault(content[origin.key], []).append(origin)
        if len(found) > 1:
            places = "; ".join(f"{origin}[{origin.key}]" for origins in found.values() for origin in origins)
            raise RecoveryConflict(f"{path} {prop}: los Secret {places} guardan valores distintos; no se elige en silencio. Decida cual es el vigente (borre o corrija el otro) y repita.")
        return next(iter(found), None)

    def templated(self, path: str, prop: str) -> list[str]:
        return sorted(set(self.index()[1].get((path, prop), [])))

    def identity_namespaces(self, paths: set[str]) -> list[str]:
        """Los namespaces con algun ExternalSecret que lee una de `paths`."""
        return sorted({d["metadata"]["namespace"] for d in self.cluster.external_secrets() if any(i["remoteRef"]["key"] in paths for i in d["spec"].get("data") or [])})


def recover_or(recover: Recoverer | None, report: PathReport | None, path: str, prop: str, generate: Callable[[], str]) -> str:
    """El valor de una propiedad que falta en la boveda: el del cluster si esta; si no, uno nuevo (y se informa)."""
    value = recover.find(path, prop) if recover else None
    if value is not None:
        if report:
            report.recovered += 1
        return value
    if report:
        report.generated.append(prop)
        places = recover.templated(path, prop) if recover else []
        if places:
            report.templated[prop] = places
    return generate()


def plan(refs: Refs, users: dict[str, str], current: Callable[[str], dict[str, str]], recover: Recoverer | None = None, report: Report | None = None) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for path, properties in sorted(refs.items()):
        existing = current(path)
        data = dict(existing)
        line = report.path(path) if report else None
        for prop in sorted(properties):
            fixed = fixed_value(path, prop, users)
            if fixed is not None:
                data[prop] = fixed
                if line:
                    line.fixed += 1
            elif prop in data:
                if line:
                    line.kept += 1
            else:
                data[prop] = recover_or(recover, line, path, prop, lambda path=path: TOKEN_PENDING if path == "grafana/folder-permissions" else secrets.token_hex(24))
        result[path] = data
    return result


def kubectl_runner(command: list[str], stdin: str | None) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(command, input=stdin, capture_output=True, text=True, check=False)  # noqa: S603


class Vault:
    """Vault dev dentro del pod. Los valores van por stdin: no aparecen en la linea de comandos."""

    def __init__(self, context: str, token: str, run: Runner = kubectl_runner) -> None:
        self.prefix = ["kubectl", "--context", context, "exec", "-i", "-n", "vault", "vault-0", "--", "env", f"VAULT_TOKEN={token}", "vault", "kv"]
        self.run = run

    def read(self, path: str) -> dict[str, str]:
        result = self.run([*self.prefix, "get", "-format=json", f"secret/{path}"], None)
        if result.returncode == NOT_FOUND:
            return {}
        if result.returncode != 0:
            raise RuntimeError(f"No se pudo leer {path}: {result.stderr}")
        return json.loads(result.stdout)["data"]["data"]

    def write(self, path: str, data: dict[str, str]) -> None:
        result = self.run([*self.prefix, "put", f"secret/{path}", "-"], json.dumps(data))
        if result.returncode != 0:
            raise RuntimeError(f"No se pudo escribir {path}: {result.stderr}")


def seed(vault: Vault, recover: Recoverer | None = None, report: Report | None = None) -> list[str]:
    documents = platform_external_secrets()
    planned = plan(collect(documents), minio_users(documents), vault.read, recover, report)
    for path, data in planned.items():
        vault.write(path, data)
    return list(planned)


# --- U2: valores con forma real (U02-T19, B-2) --------------------------------------------------------------------------


def b64url(number: int, size: int = 32) -> str:
    return base64.urlsafe_b64encode(number.to_bytes(size, "big")).rstrip(b"=").decode()


def public_jwk(key: ec.EllipticCurvePrivateKey) -> dict[str, str]:
    """La llave publica como JWK ES256. El `kid` es la huella de RFC 7638: el mismo par da siempre el mismo `kid`."""
    numbers = key.public_key().public_numbers()
    x, y = b64url(numbers.x), b64url(numbers.y)
    thumbprint = json.dumps({"crv": "P-256", "kty": "EC", "x": x, "y": y}, separators=(",", ":"), sort_keys=True)
    kid = base64.urlsafe_b64encode(hashlib.sha256(thumbprint.encode()).digest()).rstrip(b"=").decode()
    return {"kty": "EC", "crv": "P-256", "x": x, "y": y, "use": "sig", "alg": "ES256", "kid": kid}


def jwks_text(key: ec.EllipticCurvePrivateKey) -> str:
    return json.dumps({"keys": [public_jwk(key)]}, separators=(",", ":"), sort_keys=True)


def private_pem(key: ec.EllipticCurvePrivateKey) -> str:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


def load_private(pem: str) -> ec.EllipticCurvePrivateKey:
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
        raise ValueError("la llave privada no es ES256 (P-256)")
    return key


def client_pair(path: str, data: dict[str, str], wants_private: bool) -> dict[str, str]:
    """Completa `jwks` y `private-key` de un cliente sin tocar un par que ya exista: regenerarlo rompe los tokens vigentes."""
    result = dict(data)
    if "private-key" in result:
        derived = jwks_text(load_private(result["private-key"]))
        if "jwks" not in result:
            result["jwks"] = derived
        elif json.loads(result["jwks"]) != json.loads(derived):
            raise RuntimeError(f"{path}: `jwks` no corresponde a `private-key`; no se regenera el par, corrijalo a mano")
        return result
    if "jwks" in result:
        if wants_private:
            raise RuntimeError(f"{path}: tiene `jwks` sin `private-key`; no se regenera el par, borre la ruta si quiere uno nuevo")
        return result
    key = ec.generate_private_key(ec.SECP256R1())
    result["jwks"] = jwks_text(key)
    if wants_private:
        result["private-key"] = private_pem(key)
    return result


def alphanumeric_password(length: int = 24) -> str:
    """Letras y digitos, sin simbolos: el valor entra por sustitucion de texto a un YAML (`value: $(env:...)`) sin comillas."""
    return secrets.choice(string.ascii_letters) + "".join(secrets.choice(ALPHANUMERIC) for _ in range(length - 1))


def totp_seed() -> str:
    """Base32 de 160 bits (RFC 4226), sin relleno: lo acepta `pyotp.TOTP`."""
    return base64.b32encode(secrets.token_bytes(20)).decode()


def identity_value(path: str, prop: str) -> str:
    """Un valor nuevo para una propiedad de U2 que todavia no existe. `ca.crt` y las llaves de cliente no pasan por aqui."""
    if path == "identity/synthetic-users" and prop.endswith("_TOTP_SEED"):
        return totp_seed()
    if path == "identity/keycloak-admin" and prop == "username":
        return os.environ.get("VECTRA_KC_ADMIN_USER") or DEFAULT_ADMIN_USER
    if prop.endswith("PASSWORD") or prop == "password":
        return alphanumeric_password()
    return secrets.token_hex(24)  # edge/valkey: no necesita forma


def recovered_pair(path: str, data: dict[str, str], wants_private: bool, recover: Recoverer | None) -> tuple[dict[str, str], set[str]]:
    """Lo que los `Secret` del cluster devuelven de un par de cliente que la boveda no tiene: (datos, propiedades recuperadas).

    Nunca la privada de un lado y el `jwks` de otro: sin la privada no se rescata el `jwks` suelto (la privada nueva no le correspondería)
    y el par se genera entero. Con la privada, `client_pair` comprueba que el `jwks` recuperado sea el suyo.
    """
    if recover is None or "private-key" in data or "jwks" in data:
        return data, set()
    result = dict(data)
    if wants_private:
        private = recover.find(path, "private-key")
        if private is None:
            return result, set()
        result["private-key"] = private
        jwks = recover.find(path, "jwks")
        if jwks is None:
            return result, {"private-key"}
        result["jwks"] = jwks
        return result, {"private-key", "jwks"}
    jwks = recover.find(path, "jwks")
    if jwks is None:
        return result, set()
    result["jwks"] = jwks
    return result, {"jwks"}


def report_pair(line: PathReport, before: set[str], recovered: set[str], data: dict[str, str], recover: Recoverer | None, path: str) -> None:
    """Cuenta un par de cliente: conservado, recuperado, derivado del par que ya habia, o generado."""
    line.kept += len(before)
    for prop in sorted(set(data) - before):
        if prop in recovered:
            line.recovered += 1
        elif prop == "jwks" and "private-key" in before | recovered:
            line.derived += 1
        else:
            line.generated.append(prop)
            places = recover.templated(path, prop) if recover else []
            if places:
                line.templated[prop] = places


def plan_identity(
    refs: Refs, current: Callable[[str], dict[str, str]], ca_certificate: Callable[[], str], recover: Recoverer | None = None, report: Report | None = None
) -> dict[str, dict[str, str]]:
    """Lo que debe quedar en cada ruta de U2. Conserva todo lo que existe, recupera del cluster lo que falta y genera el resto; `ca_certificate` solo se llama si falta `identity/ca`."""
    signing = set(service_account_clients())
    result: dict[str, dict[str, str]] = {}
    for path, properties in sorted(refs.items()):
        data = dict(current(path))
        line = report.path(path) if report else None
        if path.startswith(CLIENTS_PREFIX):
            wants_private = path.removeprefix(CLIENTS_PREFIX) in signing or "private-key" in properties
            before = set(data)
            data, recovered = recovered_pair(path, data, wants_private, recover)
            data = client_pair(path, data, wants_private=wants_private)
            if line:
                report_pair(line, before, recovered, data, recover, path)
        else:
            for prop in sorted(properties):
                if prop in data:
                    if line:
                        line.kept += 1
                elif (path, prop) == ("identity/ca", "ca.crt"):
                    data[prop] = ca_certificate()  # la fuente viva (cert-manager), nunca una copia
                    if line:
                        line.derived += 1
                else:
                    data[prop] = recover_or(recover, line, path, prop, lambda path=path, prop=prop: identity_value(path, prop))
        result[path] = data
    return result


def ca_from_cluster(context: str, run: Runner = kubectl_runner) -> Callable[[], str]:
    """El certificado publico (`tls.crt`) de `vectra-internal-ca`. Nunca lee ni imprime `tls.key`."""

    def read() -> str:
        namespace, name = CA_SECRET
        command = ["kubectl", "--context", context, "get", "secret", name, "-n", namespace, "-o", r"jsonpath={.data.tls\.crt}"]
        result = run(command, None)
        if result.returncode != 0 or not result.stdout:
            raise RuntimeError(f"No se pudo leer el certificado de {namespace}/{name}: {result.stderr}")
        pem = base64.b64decode(result.stdout).decode()
        load_pem_x509_certificate(pem.encode())  # falla si no es un certificado
        return pem

    return read


def write_private(path: Path, text: str) -> None:
    """Archivo 0600. Se escribe a un temporal 0600 en el mismo directorio y se reemplaza: el contenido nuevo nunca esta en un archivo con permisos mas amplios."""
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    temporary.replace(path)


def local_files(keys_dir: Path, planned: dict[str, dict[str, str]]) -> list[str]:
    """Deja en `keys_dir` (0700) la llave `<clientId>.pem`, `ca.crt` y un archivo `env` (0600) con las variables de las pruebas. Devuelve sus nombres."""
    if keys_dir.resolve().is_relative_to(PLATFORM.parent.parent.resolve()):
        raise ValueError(f"{keys_dir} esta dentro del repositorio; las llaves privadas van fuera de el")
    keys_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    keys_dir.chmod(0o700)
    for path, data in planned.items():
        if path.startswith(CLIENTS_PREFIX) and "private-key" in data:
            write_private(keys_dir / f"{path.removeprefix(CLIENTS_PREFIX)}.pem", data["private-key"])
    write_private(keys_dir / "ca.crt", planned["identity/ca"]["ca.crt"])
    host = yaml.safe_load(GATEWAY_KIND_VALUES.read_text(encoding="utf-8"))["hostname"]
    variables = {
        "VECTRA_E2E_BASE_URL": f"https://{host}",
        "VECTRA_E2E_CA_BUNDLE": str(keys_dir / "ca.crt"),
        "VECTRA_E2E_ADMIN_CA_BUNDLE": str(keys_dir / "ca.crt"),
        "VECTRA_E2E_CLIENT_KEYS_DIR": str(keys_dir),
        "K6_CLIENT_KEYS_DIR": str(keys_dir),
        "VECTRA_E2E_ADMIN_USER": planned["identity/keycloak-admin"]["username"],
        "VECTRA_E2E_ADMIN_PASSWORD": planned["identity/keycloak-admin"]["password"],
        **dict(sorted(planned["identity/synthetic-users"].items())),
    }
    write_private(keys_dir / "env", "".join(f"export {name}={shlex.quote(value)}\n" for name, value in variables.items()))
    return list(variables)


def seed_identity(
    vault: Vault, ca_certificate: Callable[[], str], keys_dir: Path, recover: Recoverer | None = None, report: Report | None = None
) -> tuple[list[str], list[str]]:
    """Siembra las rutas de U2. Devuelve (rutas escritas, nombres de las variables del archivo `env`). Una segunda corrida no escribe nada."""
    refs = identity_refs(identity_external_secrets())
    current = {path: vault.read(path) for path in refs}
    planned = plan_identity(refs, lambda path: current[path], ca_certificate, recover, report)
    written = [path for path, data in planned.items() if data != current[path]]
    for path in written:
        vault.write(path, planned[path])
    return written, local_files(keys_dir, planned)


def listing() -> Refs:
    """`list`: las rutas de U1 y las de U2."""
    refs = collect(platform_external_secrets())
    for path, properties in identity_refs(identity_external_secrets()).items():
        refs.setdefault(path, set()).update(properties)
    return refs


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "list":
        for path, properties in sorted(listing().items()):
            for prop in sorted(properties):
                print(path, prop)
        return 0
    if len(argv) == 3 and argv[1] == "identity-namespaces":
        for namespace in Recoverer(ClusterSecrets(argv[2])).identity_namespaces(set(identity_refs(identity_external_secrets()))):
            print(namespace)
        return 0
    if len(argv) == 4 and argv[1] == "seed":
        report = Report()
        for path in seed(Vault(argv[2], argv[3]), Recoverer(ClusterSecrets(argv[2])), report):
            print("sembrada", path)
        print("\n".join(report.lines()))
        return 0
    if len(argv) in {4, 5} and argv[1] == "seed-identity":
        keys_dir = Path(argv[4]) if len(argv) == 5 else Path(os.environ.get("VECTRA_E2E_KEYS_DIR") or KEYS_DIR_DEFAULT)
        report = Report()
        written, names = seed_identity(Vault(argv[2], argv[3]), ca_from_cluster(argv[2]), keys_dir, Recoverer(ClusterSecrets(argv[2])), report)
        for path in written:
            print("sembrada", path)
        print("\n".join(report.lines()))
        if not written:
            print("Las rutas de U2 ya estaban sembradas: nada cambia.")
        print(f"Archivo de variables de las pruebas (0600, con valores secretos que no se imprimen): {keys_dir}/env")
        print(f"  source {keys_dir}/env")
        print("  define:", " ".join(n for n in names if not n.startswith("SYNTH_")), "y SYNTH_<USUARIO>_{PASSWORD,TOTP_SEED}")
        return 0
    print("Uso: vault_paths.py list | seed <contexto> <token> | seed-identity <contexto> <token> [directorio-de-llaves] | identity-namespaces <contexto>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
