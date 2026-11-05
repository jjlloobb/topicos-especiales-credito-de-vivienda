"""Valores del diseno de Valkey y de `envoy-ratelimit` (U02-T11, Paso 9), leidos de los documentos (INF-U2-03, 04, 06; R2 a R5).

Cada funcion recibe el texto del documento (por defecto, el vigente): asi una prueba puede cambiar el diseno en memoria y ver que
la comparacion con lo renderizado falla.
"""

import re
from pathlib import Path

from design_values import INFRASTRUCTURE, section, table_rows

_ROOT = Path(__file__).resolve().parents[3]
_FD = _ROOT / "aidlc-docs" / "construction" / "identity-edge"
NFR_REQUIREMENTS = (_FD / "nfr-requirements" / "nfr-requirements.md").read_text(encoding="utf-8")


def _quantity(cell: str) -> dict[str, str]:
    cpu, memory = (p.strip() for p in cell.split("/"))
    return {"cpu": cpu, "memory": memory.replace(" MiB", "Mi").replace(" GiB", "Gi")}


def resources(row_name: str, text: str = INFRASTRUCTURE) -> dict[str, dict[str, str]]:
    """Requests y limits de una fila de la tabla de INF-U2-06."""
    row = next(r for r in table_rows(section(text, "### INF-U2-06")) if r[0].startswith(row_name))
    return {"requests": _quantity(row[1]), "limits": _quantity(row[2])}


def inf04(text: str = INFRASTRUCTURE) -> str:
    return section(text, "### INF-U2-04")


def inf03(text: str = INFRASTRUCTURE) -> str:
    return section(text, "### INF-U2-03")


def valkey_digest(text: str = INFRASTRUCTURE) -> str:
    found = re.search(r"`valkey/valkey:8\.1\.11-alpine` `@(sha256:[0-9a-f]{64})`", inf04(text))
    assert found, "INF-U2-04 sin el digest de Valkey"
    return found.group(1)


def exporter_digest(text: str = INFRASTRUCTURE) -> str:
    found = re.search(r"`oliver006/redis_exporter:v1\.95\.0-alpine` `@(sha256:[0-9a-f]{64})`", inf04(text))
    assert found, "INF-U2-04 sin el digest del exportador"
    return found.group(1)


def ratelimit_digest(text: str = INFRASTRUCTURE) -> str:
    found = re.search(r"`envoyproxy/ratelimit:5ae0682e`.*`@(sha256:[0-9a-f]{64})`", inf03(text))
    assert found, "INF-U2-03 sin el digest de ratelimit"
    return found.group(1)


def registries(text: str = INFRASTRUCTURE) -> dict[str, str]:
    """entorno -> registro del espejo (`registro.banco.internal/vectra` en staging y prod, `kind-registry:5000/vectra` en kind)."""
    found = re.search(r"\(`(registro[\w./-]+)`, y `(kind-registry:\d+)` en kind\)", inf04(text))
    assert found, "INF-U2-04 sin los registros"
    bank, kind = found.group(1), found.group(2) + "/vectra"
    return {"kind": kind, "staging": bank, "prod": bank}


def replica_priorities(text: str = INFRASTRUCTURE) -> dict[str, int]:
    found = re.search(r"`replica-priority` favorece a A: (\d+) en `valkey-a` y (\d+) en `valkey-b`", inf04(text))
    assert found, "INF-U2-04 sin replica-priority"
    return {"valkey-a": int(found.group(1)), "valkey-b": int(found.group(2))}


def maxmemory(text: str = INFRASTRUCTURE) -> tuple[str, str]:
    found = re.search(r"`maxmemory (\w+)`, política `([\w-]+)`", inf04(text))
    assert found, "INF-U2-04 sin maxmemory"
    return found.group(1), found.group(2)


def quorum(text: str = INFRASTRUCTURE) -> int:
    found = re.search(r"con quórum (\d+)", inf04(text))
    assert found, "INF-U2-04 sin quorum"
    return int(found.group(1))


def sentinel_layout(text: str = INFRASTRUCTURE) -> dict[str, int]:
    found = re.search(r"`sentinel-a` \((\d+) réplicas?, zona A\) y `sentinel-b` \((\d+) réplicas?, zona B\)", inf04(text))
    assert found, "INF-U2-04 sin la topologia de Sentinel"
    return {"sentinel-a": int(found.group(1)), "sentinel-b": int(found.group(2))}


def pdb(text: str = INFRASTRUCTURE) -> dict[str, int]:
    found = re.search(r"`minAvailable: (\d+)` sobre la etiqueta común de Valkey y `minAvailable: (\d+)` sobre la de Sentinel", inf04(text))
    assert found, "INF-U2-04 sin los PDB"
    return {"valkey": int(found.group(1)), "sentinel": int(found.group(2))}


def zones(text: str = INFRASTRUCTURE) -> tuple[str, str]:
    """R6: las zonas de A y B son las mismas en kind, staging y prod."""
    found = re.search(r"Las zonas se llaman `([\w-]+)` y `([\w-]+)` en los tres entornos", inf04(text))
    assert found, "INF-U2-04 sin las zonas de los tres entornos (R6)"
    return found.group(1), found.group(2)


def sentinel_timings(text: str = INFRASTRUCTURE) -> list[str]:
    """R7: las tres directivas del master, en el orden del diseno."""
    found = re.findall(r"`(sentinel (?:down-after-milliseconds|failover-timeout|parallel-syncs) [\w-]+ \d+)`", inf04(text))
    assert len(found) == 3, "INF-U2-04 sin los tres tiempos de Sentinel (R7)"
    return found


def master_name(text: str = INFRASTRUCTURE) -> str:
    found = re.search(r"el master se llama `(\w+)`", inf04(text))
    assert found, "INF-U2-04 sin el nombre del master"
    return found.group(1)


def vault_properties(text: str = INFRASTRUCTURE) -> list[str]:
    block = re.search(r"Las propiedades de la clave de Vault `(edge/valkey)` son (.+?)\.", inf04(text))
    assert block, "INF-U2-04 sin las propiedades de Vault"
    return re.findall(r"`([\w-]+)`", block.group(2))


def vault_key(text: str = INFRASTRUCTURE) -> str:
    found = re.search(r"Las propiedades de la clave de Vault `([\w/-]+)`", inf04(text))
    assert found
    return found.group(1)


def _camel(prop: str) -> str:
    head, *rest = prop.split("-")
    return head + "".join(p.capitalize() for p in rest)


def _bullets(block: str) -> list[list[str]]:
    return [re.findall(r"`([^`]+)`", ln) for ln in block.splitlines() if ln.startswith("      - ")]


def _acl_section(text: str) -> dict[str, str]:
    body = inf04(text)
    body = body[body.index("**ACL definitivas") :]
    valkey = body[body.index("**`users.acl` de Valkey:**") : body.index("**ACL de cada `sentinel.conf`:**")]
    sentinel = body[body.index("**ACL de cada `sentinel.conf`:**") : body.index("**Nombres:**")]
    return {"valkey": valkey, "sentinel": sentinel}


def users_acl(text: str = INFRASTRUCTURE) -> list[str]:
    """Las lineas de `users.acl`, con la contrasena como marca de la plantilla de ESO (`>{{ .propiedad }}`)."""
    lines = []
    for items in _bullets(_acl_section(text)["valkey"]):
        if items[0].startswith("user "):
            lines.append(items[0])
            continue
        name, rules = items[0], items[1]
        lines.append(f"user {name} on >{{{{ .{_camel(name)} }}}} {rules}")
    return lines


def sentinel_acl(text: str = INFRASTRUCTURE) -> tuple[list[str], list[str]]:
    """(sentinel-users.conf, sentinel-auth.conf): usuarios y `sentinel-user/pass`, y `auth-user/pass` del master."""
    passwords = {"ratelimit": "sentinel-ratelimit", "sentinel-peer": "sentinel-peer"}
    users: list[str] = []
    auth: list[str] = []
    for items in _bullets(_acl_section(text)["sentinel"]):
        if items[0].startswith("user "):
            users.append(items[0])
        elif items[0].startswith("sentinel auth-user "):
            user = items[0].split()[-1]
            auth += [f"sentinel auth-user {master_name(text)} {user}", f"sentinel auth-pass {master_name(text)} {{{{ .{_camel(user)} }}}}"]
        else:
            name, rules, *extra = items
            users.append(f"user {name} on >{{{{ .{_camel(passwords[name])} }}}} {rules}")
            for line in extra:
                users.append(line)
                if line.startswith("sentinel sentinel-pass"):
                    users[-1] = f"{line} {{{{ .{_camel(passwords[name])} }}}}"
    return users, auth


def valkey_secret_conf() -> list[str]:
    """La tarea (U02-T11) fija `masteruser replication` y `masterauth` de la contrasena de `replication`."""
    return ["masteruser replication", "masterauth {{ .replication }}"]


def ratelimit_resources(text: str = INFRASTRUCTURE) -> dict[str, dict[str, str]]:
    return resources("Servicio de rate limit", text)


# --- envoy-ratelimit (INF-U2-03, R1 y R2) ------------------------------------------------------------------


def ratelimit_url(text: str = INFRASTRUCTURE) -> str:
    """`<master>,<sentinel-a-0>:26379,<sentinel-b-0>:26379,<sentinel-b-1>:26379` con los FQDN de `vectra-edge`, desde INF-U2-03 y 04."""
    found = re.search(r"`rateLimit\.backend\.redis\.url` = `<nombre del master>((?:,<[\w-]+>:\d+)+)`, con los FQDN de `(vectra-edge)`", inf03(text))
    assert found, "INF-U2-03 sin la URL de Redis"
    hosts = []
    for item in found.group(1).strip(",").split(","):
        pod, port = re.fullmatch(r"<([\w-]+)>:(\d+)", item).groups()  # type: ignore[union-attr]
        group = pod.rsplit("-", 1)[0]
        hosts.append(f"{pod}.{group}.{found.group(2)}.svc.cluster.local:{port}")
    return ",".join([master_name(text), *hosts])


def ratelimit_replicas(text: str = INFRASTRUCTURE) -> int:
    found = re.search(r"- réplicas (\d+);", inf03(text))
    assert found, "INF-U2-03 sin las replicas"
    return int(found.group(1))


def ratelimit_hpa(text: str = INFRASTRUCTURE) -> tuple[int, int, int]:
    found = re.search(r"`rateLimitHpa` de (\d+) a (\d+) con CPU al (\d+) %", inf03(text))
    assert found, "INF-U2-03 sin el HPA"
    return int(found.group(1)), int(found.group(2)), int(found.group(3))


def ratelimit_pdb(text: str = INFRASTRUCTURE) -> int:
    found = re.search(r"`rateLimitPDB` `minAvailable: (\d+)`", inf03(text))
    assert found, "INF-U2-03 sin el PDB"
    return int(found.group(1))


def ratelimit_tracing(text: str = INFRASTRUCTURE) -> tuple[str, int]:
    found = re.search(r"tracing OpenTelemetry hacia `([\w.:-]+)` con muestreo del (\d+) %", inf03(text))
    assert found, "INF-U2-03 sin el tracing"
    return found.group(1), int(found.group(2))


def ratelimit_tracing_protocol(text: str = INFRASTRUCTURE) -> str:
    """R8: el protocolo del exportador de trazas de envoy-ratelimit (por defecto es `http`, y el 4317 es gRPC)."""
    found = re.search(r"agrega `TRACING_EXPORTER_PROTOCOL=(\w+)`", inf03(text))
    assert found, "INF-U2-03 sin TRACING_EXPORTER_PROTOCOL (R8)"
    return found.group(1)


def ratelimit_ports(text: str = INFRASTRUCTURE) -> dict[str, int]:
    """Puertos que fija v1.9.3 (`InfraGRPCPort`, `ReadinessPort`, `PrometheusPort`, xDS), como los dice INF-U2-03."""
    body = inf03(text)
    found = {
        "grpc": re.search(r"gRPC en el (\d+) \(`InfraGRPCPort`\)", body),
        "health": re.search(r"health y readiness en el (\d+) \(`ReadinessPort`\)", body),
        "metrics": re.search(r"métricas Prometheus en el (\d+) \(`PrometheusPort`\)", body),
        "xds": re.search(r"xDS del controlador hacia `envoy-ratelimit` en el (\d+)", body),
    }
    assert all(found.values()), "INF-U2-03 sin los puertos"
    return {k: int(v.group(1)) for k, v in found.items()}  # type: ignore[union-attr]


def ratelimit_registries(text: str = INFRASTRUCTURE) -> dict[str, str]:
    """entorno -> repositorio de la imagen de ratelimit (`registro.banco.internal/vectra/ratelimit`, y el de kind)."""
    found = re.search(r"Se espeja en `(registro[\w./-]+)`, y en kind en `(kind-registry[\w.:/-]+)`", inf03(text))
    assert found, "INF-U2-03 sin los repositorios de ratelimit"
    return {"kind": found.group(2), "staging": found.group(1), "prod": found.group(1)}


def ratelimit_failclosed(text: str = INFRASTRUCTURE) -> bool:
    found = re.search(r"`rateLimit\.failClosed: (true|false)`", inf03(text))
    assert found, "INF-U2-03 sin failClosed"
    return found.group(1) == "true"
