"""Chart de Valkey (U02-T11, Paso 9; CA-3): INF-U2-04 y 06, R2 a R5; NFR-U2-20, 27, 30.

Lo renderizado de cada entorno se compara con un oraculo que lee del diseno cada valor que el diseno fija (`valkey_design`), y cada regla
de `identity-edge/charts/valkey/policy/` tiene su caso que falla sobre un render alterado.
"""

import copy
import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import keycloak_deploy_checks as kd
import pytest
import valkey_design as design
import yaml
from design_values import INFRASTRUCTURE

ROOT = Path(__file__).resolve().parents[3]
EDGE = ROOT / "identity-edge"
CHART = EDGE / "charts" / "valkey"
POLICY = CHART / "policy"
RENDERED = CHART / "rendered"
HELM = ROOT / "platform" / ".tools" / "bin" / "helm"
CONFTEST = ROOT / "platform" / ".tools" / "bin" / "conftest"
ENVS = ("kind", "staging", "prod")
NAMESPACE = "vectra-edge"

Docs = list[dict[str, Any]]


# --- render y conftest ----------------------------------------------------------------------------------


def helm_template(env: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - herramienta fija de platform/.tools
        [str(HELM), "template", "valkey", str(CHART), "--namespace", NAMESPACE, "-f", str(CHART / "values" / f"{env}.yaml"), *extra],
        capture_output=True, text=True, check=False,
    )  # fmt: skip


def load(env: str) -> Docs:
    return [d for d in yaml.safe_load_all((RENDERED / env / "valkey.yaml").read_text(encoding="utf-8")) if d]


def find(docs: Docs, kind: str, name: str) -> dict[str, Any]:
    (found,) = [d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name]
    return found


def conftest(docs: Docs) -> tuple[int, str]:
    """Las dos pasadas de `make policy-valkey` sobre `docs`. Devuelve (codigo mayor, salida)."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "valkey.yaml"
        target.write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
        first = subprocess.run([str(CONFTEST), "test", "--policy", str(POLICY), str(target)], capture_output=True, text=True, check=False)  # noqa: S603
        second = subprocess.run(  # noqa: S603
            [str(CONFTEST), "test", "--combine", "--namespace", "valkey_set", "--policy", str(POLICY), str(target)],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
    return max(first.returncode, second.returncode), first.stdout + first.stderr + second.stdout + second.stderr


def policy_rules() -> set[str]:
    rules = set()
    for path in sorted(POLICY.glob("*.rego")):
        rules |= set(re.findall(r"^# regla: ([\w-]+)$", path.read_text(encoding="utf-8"), re.MULTILINE))
    return rules


# --- el oraculo: todo lo que el diseno fija ---------------------------------------------------------------


def fqdn(pod: str, service: str) -> str:
    return f"{pod}.{service}.{NAMESPACE}.svc.cluster.local"


def expected_documents(text: str = INFRASTRUCTURE) -> set[tuple[str, str]]:
    """(kind, name) del conjunto exacto de documentos de un entorno."""
    valkeys = set(design.replica_priorities(text))
    sentinels = set(design.sentinel_layout(text))
    found = {("StatefulSet", n) for n in valkeys | sentinels} | {("Service", n) for n in valkeys | sentinels}
    found |= {("PodDisruptionBudget", n) for n in design.pdb(text)}
    found |= {("ServiceAccount", "valkey"), ("ServiceAccount", "sentinel")}
    found |= {("ConfigMap", "valkey-config"), ("ConfigMap", "sentinel-config"), ("ConfigMap", "valkey-scripts")}
    found |= {("ExternalSecret", "valkey-acl")}
    return found


def lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln]


def containers(docs: Docs, name: str) -> dict[str, dict[str, Any]]:
    return {c["name"]: c for c in find(docs, "StatefulSet", name)["spec"]["template"]["spec"]["containers"]}


def env_of(container: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {e["name"]: e for e in container["env"]}


def selects(selector: dict[str, str], labels: dict[str, str]) -> bool:
    return all(labels.get(k) == v for k, v in selector.items())


def problems(docs: Docs, env: str, text: str = INFRASTRUCTURE) -> list[str]:
    """Diferencias entre lo renderizado y el diseno. Vacio si coinciden."""
    found: list[str] = []
    got = {(d["kind"], d["metadata"]["name"]) for d in docs}
    if got != expected_documents(text):
        found.append(f"documentos: sobran {sorted(got - expected_documents(text))}, faltan {sorted(expected_documents(text) - got)}")
    found += [f"namespace de {d['kind']} {d['metadata']['name']}" for d in docs if d["metadata"].get("namespace") != NAMESPACE]
    registry = design.registries(text)[env]
    valkey_image = f"{registry}/valkey@{design.valkey_digest(text)}"
    exporter_image = f"{registry}/redis-exporter@{design.exporter_digest(text)}"
    zone_a, zone_b = design.zones(text)
    zones = {"valkey-a": zone_a, "sentinel-a": zone_a, "valkey-b": zone_b, "sentinel-b": zone_b}
    priorities = design.replica_priorities(text)
    primary = min(priorities, key=lambda n: priorities[n])
    master = design.master_name(text)
    for name, priority in priorities.items():
        by_name = containers(docs, name)
        if by_name["valkey"]["image"] != valkey_image:
            found.append(f"{name}: imagen de Valkey")
        if by_name["exporter"]["image"] != exporter_image:
            found.append(f"{name}: imagen del exportador")
        if by_name["valkey"]["resources"] != design.resources("Valkey (cada", text):
            found.append(f"{name}: recursos de Valkey")
        if by_name["exporter"]["resources"] != design.resources("Exportador", text):
            found.append(f"{name}: recursos del exportador")
        valkey_env = env_of(by_name["valkey"])
        if valkey_env["REPLICA_PRIORITY"]["value"] != str(priority):
            found.append(f"{name}: replica-priority")
        if valkey_env["MASTER_NAME"]["value"] != master:
            found.append(f"{name}: nombre del master")
        want_initial = "" if name == primary else fqdn(f"{primary}-0", primary)
        if valkey_env["INITIAL_PRIMARY"]["value"] != want_initial:
            found.append(f"{name}: primaria inicial")
        if find(docs, "StatefulSet", name)["spec"]["replicas"] != 1:
            found.append(f"{name}: replicas")
    for name, zone in zones.items():
        term = find(docs, "StatefulSet", name)["spec"]["template"]["spec"]["affinity"]["nodeAffinity"]["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"]
        if term != [{"matchExpressions": [{"key": "topology.kubernetes.io/zone", "operator": "In", "values": [zone]}]}]:
            found.append(f"{name}: zona")
    for name, replicas in design.sentinel_layout(text).items():
        sts = find(docs, "StatefulSet", name)
        sentinel = containers(docs, name)["sentinel"]
        if sts["spec"]["replicas"] != replicas:
            found.append(f"{name}: replicas")
        if sentinel["image"] != valkey_image:
            found.append(f"{name}: imagen")
        if sentinel["resources"] != design.resources("Sentinel (cada", text):
            found.append(f"{name}: recursos")
        sentinel_env = env_of(sentinel)
        if sentinel_env["SENTINEL_QUORUM"]["value"] != str(design.quorum(text)):
            found.append(f"{name}: quorum")
        if sentinel_env["MASTER_NAME"]["value"] != master:
            found.append(f"{name}: nombre del master")
        if sentinel_env["DEFAULT_PRIMARY"]["value"] != fqdn(f"{primary}-0", primary):
            found.append(f"{name}: primaria por defecto")
    for name, minimum in design.pdb(text).items():
        if find(docs, "PodDisruptionBudget", name)["spec"]["minAvailable"] != minimum:
            found.append(f"pdb {name}")
    master_conf = lines(find(docs, "ConfigMap", "sentinel-config")["data"]["sentinel-master.conf"])
    if master_conf != design.sentinel_timings(text):
        found.append(f"tiempos de Sentinel {master_conf}")
    maxmemory, policy = design.maxmemory(text)
    conf = lines(find(docs, "ConfigMap", "valkey-config")["data"]["valkey.conf"])
    for want in (f"maxmemory {maxmemory}", f"maxmemory-policy {policy}", 'save ""', "appendonly no"):
        if want not in conf:
            found.append(f"valkey.conf sin `{want}`")
    secret = find(docs, "ExternalSecret", "valkey-acl")["spec"]
    data = secret["target"]["template"]["data"]
    if lines(data["users.acl"]) != design.users_acl(text):
        found.append("users.acl")
    users, auth = design.sentinel_acl(text)
    if lines(data["sentinel-users.conf"]) != users:
        found.append("sentinel-users.conf")
    if lines(data["sentinel-auth.conf"]) != auth:
        found.append("sentinel-auth.conf")
    if lines(data["valkey-secret.conf"]) != design.valkey_secret_conf():
        found.append("valkey-secret.conf")
    properties = [(d["remoteRef"]["key"], d["remoteRef"]["property"]) for d in secret["data"]]
    if sorted(properties) != sorted((design.vault_key(text), p) for p in design.vault_properties(text)):
        found.append("propiedades de Vault")
    return found


@pytest.fixture(scope="module", params=ENVS)
def rendered(request: pytest.FixtureRequest) -> tuple[str, Docs]:
    return request.param, load(request.param)


@pytest.fixture(scope="module")
def prod() -> Docs:
    return load("prod")


# --- lo renderizado coincide con el diseno ------------------------------------------------------------------


def test_the_render_of_each_environment_follows_the_design(rendered: tuple[str, Docs]) -> None:
    env, docs = rendered
    assert problems(docs, env) == []


@pytest.mark.parametrize("env", ENVS)
def test_the_committed_render_matches_a_fresh_render(env: str) -> None:
    fresh = helm_template(env)
    assert fresh.returncode == 0, fresh.stderr
    assert (RENDERED / env / "valkey.yaml").read_text(encoding="utf-8") == fresh.stdout


@pytest.mark.parametrize("env", ENVS)
def test_the_set_of_documents_is_exactly_the_oracle(env: str) -> None:
    got = sorted((d["kind"], d["metadata"]["name"]) for d in load(env))
    assert got == sorted(expected_documents())


@pytest.mark.parametrize("env", ENVS)
def test_the_zones_of_every_environment_are_the_ones_of_the_design(env: str) -> None:
    """R6: las zonas del diseno (A y B) en kind, staging y prod, sin repetirlas aqui."""
    zone_a, zone_b = design.zones()
    for name, zone in (("valkey-a", zone_a), ("sentinel-a", zone_a), ("valkey-b", zone_b), ("sentinel-b", zone_b)):
        term = find(load(env), "StatefulSet", name)["spec"]["template"]["spec"]["affinity"]["nodeAffinity"]
        assert term["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"][0]["matchExpressions"][0]["values"] == [zone]


@pytest.mark.parametrize("env", ENVS)
def test_another_zone_in_the_values_fails_the_oracle_and_conftest(env: str) -> None:
    """R6: otras zonas en `values/<env>.yaml` (la mutacion del revisor) no pasan. Se renderiza con helm de verdad."""
    run = helm_template(env, "--set", "valkey.nodes.a.zone=banco-z1", "--set", "valkey.nodes.b.zone=banco-z2", "--set", "sentinel.groups.a.zone=banco-z1", "--set", "sentinel.groups.b.zone=banco-z2")
    assert run.returncode == 0, run.stderr
    docs = [d for d in yaml.safe_load_all(run.stdout) if d]
    assert any(p.endswith("zona") for p in problems(docs, env))
    code, output = conftest(docs)
    assert code != 0 and "zones: " in output, output


@pytest.mark.parametrize("group", ["a", "b"])
@pytest.mark.parametrize("env", ENVS)
def test_the_zone_of_only_one_sentinel_group_fails_the_oracle_and_conftest(env: str, group: str) -> None:
    """R6 (mutacion M4 del revisor): mover solo un grupo de Sentinel de zona. El oraculo lo ve por si solo, sin ayuda de los nodos de Valkey."""
    run = helm_template(env, "--set", f"sentinel.groups.{group}.zone=zona-ajena")
    assert run.returncode == 0, run.stderr
    docs = [d for d in yaml.safe_load_all(run.stdout) if d]
    assert problems(docs, env) == [f"sentinel-{group}: zona"]
    code, output = conftest(docs)
    assert code != 0 and "zones: " in output, output


@pytest.mark.parametrize(
    ("setting", "directive"),
    [
        ("sentinel.downAfterMilliseconds=3000", "down-after-milliseconds"),
        ("sentinel.failoverTimeout=30000", "failover-timeout"),
        ("sentinel.parallelSyncs=2", "parallel-syncs"),
    ],
)
@pytest.mark.parametrize("env", ENVS)
def test_another_sentinel_time_in_the_values_fails_the_oracle_and_conftest(env: str, setting: str, directive: str) -> None:
    """R7: un tiempo distinto en los values hace fallar el oraculo y conftest."""
    run = helm_template(env, "--set", setting)
    assert run.returncode == 0, run.stderr
    docs = [d for d in yaml.safe_load_all(run.stdout) if d]
    assert any(p.startswith("tiempos de Sentinel") for p in problems(docs, env))
    code, output = conftest(docs)
    assert code != 0 and f"sentinel-timing: {directive}" in output, output


def test_the_sentinel_times_are_read_from_the_design() -> None:
    """Los tiempos salen de INF-U2-04: lo que lee `sentinel_timings` esta en el texto del diseno, y cambiarlo en el texto cambia lo leido."""
    times = design.sentinel_timings()
    assert all(f"`{line}`" in INFRASTRUCTURE for line in times)
    bumped = INFRASTRUCTURE.replace(f"`{times[0]}`", f"`{times[0]}0`")
    assert design.sentinel_timings(bumped)[0] == f"{times[0]}0"


def test_the_images_use_the_registry_of_each_environment() -> None:
    for env, registry in design.registries().items():
        image = containers(load(env), "valkey-a")["valkey"]["image"]
        assert image == f"{registry}/valkey@{design.valkey_digest()}"


@pytest.mark.parametrize("env", ENVS)
def test_each_selector_selects_its_template(env: str) -> None:
    """Un StatefulSet cuyo selector no selecciona su template lo rechaza el apiserver; el Service y el PDB usan las mismas etiquetas."""
    docs = load(env)
    statefulsets = [d for d in docs if d["kind"] == "StatefulSet"]
    assert len(statefulsets) == 4
    for sts in statefulsets:
        labels = sts["spec"]["template"]["metadata"]["labels"]
        assert selects(sts["spec"]["selector"]["matchLabels"], labels), sts["metadata"]["name"]
        service = find(docs, "Service", sts["metadata"]["name"])
        assert sts["spec"]["serviceName"] == service["metadata"]["name"]
        assert selects(service["spec"]["selector"], labels), service["metadata"]["name"]
        assert service["spec"]["clusterIP"] == "None"
    for pdb in (d for d in docs if d["kind"] == "PodDisruptionBudget"):
        selected = [s["metadata"]["name"] for s in statefulsets if selects(pdb["spec"]["selector"]["matchLabels"], s["spec"]["template"]["metadata"]["labels"])]
        assert selected, pdb["metadata"]["name"]
        assert set(selected) == ({"valkey-a", "valkey-b"} if pdb["metadata"]["name"] == "valkey" else {"sentinel-a", "sentinel-b"})


def test_the_pdb_of_valkey_does_not_select_the_sentinels(prod: Docs) -> None:
    sentinel = find(prod, "StatefulSet", "sentinel-a")["spec"]["template"]["metadata"]["labels"]
    assert not selects(find(prod, "PodDisruptionBudget", "valkey")["spec"]["selector"]["matchLabels"], sentinel)


def test_no_password_is_written_in_a_configmap_or_in_clear(prod: Docs) -> None:
    for config in (d for d in prod if d["kind"] == "ConfigMap"):
        for text in config["data"].values():
            assert "{{" not in text
            for directive in ("masterauth", "requirepass", "auth-pass", "sentinel-pass"):
                assert directive not in [ln.split(" ")[0] for ln in lines(text)]
    assert not [d for d in prod if d["kind"] == "Secret"]


# --- un cambio en el diseno que no llega a lo renderizado hace fallar una prueba ---------------------------------


def changed(old: str, new: str) -> str:
    assert old in INFRASTRUCTURE, old
    return INFRASTRUCTURE.replace(old, new)


def _zones_sentence(zone_a: str, zone_b: str) -> str:
    return f"Las zonas se llaman `{zone_a}` y `{zone_b}`"


DESIGN_CHANGES = [
    ("digest de Valkey", lambda: changed(design.valkey_digest()[7:], "0" * 64)),
    ("digest del exportador", lambda: changed(design.exporter_digest()[7:], "1" * 64)),
    ("replica-priority", lambda: changed("10 en `valkey-a`", "11 en `valkey-a`")),
    ("quorum", lambda: changed("con quórum 2", "con quórum 3")),
    ("maxmemory", lambda: changed("`maxmemory 128mb`, política", "`maxmemory 256mb`, política")),
    ("pdb de Sentinel", lambda: changed("`minAvailable: 2` sobre la de Sentinel", "`minAvailable: 3` sobre la de Sentinel")),
    ("replicas de sentinel-b", lambda: changed("`sentinel-b` (2 réplicas, zona B)", "`sentinel-b` (3 réplicas, zona B)")),
    ("linea de la ACL del exportador", lambda: changed("+commandlog|len`", "+commandlog|len +dbsize`")),
    ("permiso de canal del usuario sentinel", lambda: changed("+subscribe &__sentinel__:hello`, sin `+role`", "+subscribe`, sin `+role`")),
    ("comando de Sentinel para ratelimit", lambda: changed("+sentinel|slaves", "+sentinel|replicas")),
    ("usuario de pares", lambda: changed("`sentinel sentinel-user sentinel-peer`", "`sentinel sentinel-user otro`")),
    ("zonas", lambda: changed(_zones_sentence(*design.zones()), _zones_sentence("zona-x", "zona-y"))),
    ("solo la zona de B", lambda: changed(_zones_sentence(*design.zones()), _zones_sentence(design.zones()[0], "zona-y"))),
    *[(f"tiempo de Sentinel {n}", lambda n=n: changed(f"`{design.sentinel_timings()[n]}`", f"`{design.sentinel_timings()[n]}0`")) for n in range(3)],
    ("nombre del master", lambda: changed("el master se llama `ratelimit`", "el master se llama `primary`")),
    ("propiedad de Vault", lambda: changed("`sentinel-peer`, `exporter` y `sentinel-ratelimit`", "`sentinel-peer`, `exporter`, `extra` y `sentinel-ratelimit`")),
    ("recursos de Valkey", lambda: changed("| Valkey (cada nodo) | 100m / 128 MiB |", "| Valkey (cada nodo) | 200m / 128 MiB |")),
]


@pytest.mark.parametrize(("case", "make"), DESIGN_CHANGES, ids=[c for c, _ in DESIGN_CHANGES])
def test_a_design_change_that_does_not_reach_the_render_fails_a_check(case: str, make: Callable[[], str], prod: Docs) -> None:
    assert problems(prod, "prod", make()) != [], case


def test_the_oracle_sees_a_missing_or_extra_document(prod: Docs) -> None:
    assert problems([d for d in prod if d["metadata"]["name"] != "valkey-scripts"], "prod") != []
    assert problems([*prod, copy.deepcopy(find(prod, "ServiceAccount", "valkey")) | {"metadata": {"name": "otra", "namespace": NAMESPACE}}], "prod") != []


# --- el render falla sin lo que cada entorno debe fijar ---------------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
def test_the_render_fails_without_the_registry(env: str) -> None:
    run = helm_template(env, "--set", "registry=")
    assert run.returncode != 0 and "registry es obligatorio" in run.stderr


@pytest.mark.parametrize("env", ENVS)
def test_the_render_fails_without_a_digest(env: str) -> None:
    run = helm_template(env, "--set", "images.valkey.digest=")
    assert run.returncode != 0 and "digest es obligatorio" in run.stderr


@pytest.mark.parametrize("env", ENVS)
def test_the_render_fails_without_the_zone_of_a_group(env: str) -> None:
    run = helm_template(env, "--set", "valkey.nodes.b.zone=")
    assert run.returncode != 0 and "la zona de cada grupo es obligatoria" in run.stderr


# --- lo renderizado cumple las politicas --------------------------------------------------------------------


def test_the_render_meets_the_policies(rendered: tuple[str, Docs]) -> None:
    code, output = conftest(rendered[1])
    assert code == 0, output


# --- cada regla falla sobre un render alterado ---------------------------------------------------------------


def _set(kind: str, name: str, path: list[str | int], value: Any) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = find(docs, kind, name)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def _del(kind: str, name: str, path: list[str | int]) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = find(docs, kind, name)
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return mutate


def _drop(kind: str, name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        docs.remove(find(docs, kind, name))

    return mutate


def _add(doc: dict[str, Any]) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        docs.append(copy.deepcopy(doc))

    return mutate


def _text(kind: str, name: str, path: list[str], old: str, new: str) -> Callable[[Docs], None]:
    """Cambia una linea de un texto (ConfigMap o plantilla del ExternalSecret)."""

    def mutate(docs: Docs) -> None:
        node: Any = find(docs, kind, name)
        for key in path[:-1]:
            node = node[key]
        assert old in node[path[-1]].splitlines(), old
        node[path[-1]] = "\n".join(new if ln == old else ln for ln in node[path[-1]].splitlines() if new or ln != old) + "\n"

    return mutate


def _container_index(name: str, container: str) -> int:
    return [c["name"] for c in find(load("prod"), "StatefulSet", name)["spec"]["template"]["spec"]["containers"]].index(container)


def _env_set(sts: str, container: str, var: str, value: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        for c in find(docs, "StatefulSet", sts)["spec"]["template"]["spec"]["containers"]:
            if c["name"] == container:
                (entry,) = [e for e in c["env"] if e["name"] == var]
                entry.pop("valueFrom", None)
                entry["value"] = value

    return mutate


def _env_secret(sts: str, container: str, var: str, secret: str, key: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        for c in find(docs, "StatefulSet", sts)["spec"]["template"]["spec"]["containers"]:
            if c["name"] == container:
                (entry,) = [e for e in c["env"] if e["name"] == var]
                entry.pop("value", None)
                entry["valueFrom"] = {"secretKeyRef": {"name": secret, "key": key}}

    return mutate


def _pod(sts: str) -> list[str | int]:
    return ["spec", "template", "spec"]


def _container_path(sts: str, container: str, *rest: str | int) -> list[str | int]:
    return [*_pod(sts), "containers", _container_index(sts, container), *rest]


PLAIN_SECRET = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "valkey-password", "namespace": NAMESPACE}, "stringData": {"password": "x"}}
USERS_ACL = ["data", "users.acl"]
TIMINGS = design.sentinel_timings()
TEMPLATE = ["spec", "target", "template", "data"]
SENTINEL_USERS_LINE = design.sentinel_acl()[0][2]
VALKEY_CONF = ["data", "valkey.conf"]

MUTATIONS: list[tuple[str, str, Callable[[Docs], None]]] = [
    ("namespace", "un Service en otro namespace", _set("Service", "valkey-a", ["metadata", "namespace"], "default")),
    ("images", "imagen de otro registro", _set("StatefulSet", "valkey-a", _container_path("valkey-a", "valkey", "image"), "docker.io/valkey/valkey@sha256:" + "0" * 64)),
    ("images", "digest distinto en el exportador", _set("StatefulSet", "valkey-b", _container_path("valkey-b", "exporter", "image"), "kind-registry:5000/vectra/redis-exporter@sha256:" + "0" * 64)),
    ("no-persistence", "volumeClaimTemplates", _set("StatefulSet", "valkey-a", ["spec", "volumeClaimTemplates"], [{"metadata": {"name": "data"}}])),
    ("no-persistence", "el volumen data en un PVC", _set("StatefulSet", "valkey-a", [*_pod("valkey-a"), "volumes", 3], {"name": "data", "persistentVolumeClaim": {"claimName": "x"}})),
    ("no-persistence", "RDB activo", _text("ConfigMap", "valkey-config", VALKEY_CONF, 'save ""', "save 900 1")),
    ("no-persistence", "AOF activo", _text("ConfigMap", "valkey-config", VALKEY_CONF, "appendonly no", "appendonly yes")),
    ("acl-file", "el aclfile en lectura y escritura", _set("StatefulSet", "valkey-a", _container_path("valkey-a", "valkey", "volumeMounts", 2, "readOnly"), False)),
    ("acl-file", "el aclfile de otro Secret", _set("StatefulSet", "valkey-b", [*_pod("valkey-b"), "volumes", 2, "secret", "secretName"], "otro")),
    ("acl-users", "sin `user default off`", _text("ExternalSecret", "valkey-acl", [*TEMPLATE, "users.acl"], "user default off", "")),
    ("acl-users", "permisos de ratelimit ampliados", _text("ExternalSecret", "valkey-acl", [*TEMPLATE, "users.acl"], design.users_acl()[1], design.users_acl()[1].replace("-@dangerous", "+@dangerous"))),
    ("master-auth", "sin masterauth", _text("ExternalSecret", "valkey-acl", [*TEMPLATE, "valkey-secret.conf"], "masterauth {{ .replication }}", "")),
    ("sentinel-acl", "sin el usuario de pares", _text("ExternalSecret", "valkey-acl", [*TEMPLATE, "sentinel-users.conf"], SENTINEL_USERS_LINE, "")),
    ("sentinel-acl", "auth-user de otro usuario", _text("ExternalSecret", "valkey-acl", [*TEMPLATE, "sentinel-auth.conf"], "sentinel auth-user ratelimit sentinel", "sentinel auth-user ratelimit ratelimit")),
    ("sentinel-hostnames", "sin announce-hostnames", _text("ConfigMap", "sentinel-config", ["data", "sentinel-head.conf"], "sentinel announce-hostnames yes", "")),
    ("maxmemory", "otra politica de desalojo", _text("ConfigMap", "valkey-config", VALKEY_CONF, "maxmemory-policy volatile-ttl", "maxmemory-policy allkeys-lru")),
    ("zones", "sin nodeAffinity", _del("StatefulSet", "valkey-a", [*_pod("valkey-a"), "affinity"])),
    ("zones", "afinidad por NotIn", _set("StatefulSet", "valkey-b", [*_pod("valkey-b"), "affinity", "nodeAffinity", "requiredDuringSchedulingIgnoredDuringExecution", "nodeSelectorTerms", 0, "matchExpressions", 0, "operator"], "NotIn")),
    ("zones", "zona ajena al diseno", _set("StatefulSet", "valkey-a", [*_pod("valkey-a"), "affinity", "nodeAffinity", "requiredDuringSchedulingIgnoredDuringExecution", "nodeSelectorTerms", 0, "matchExpressions", 0, "values"], ["banco-z1"])),
    ("sentinel-timing", "down-after distinto", _text("ConfigMap", "sentinel-config", ["data", "sentinel-master.conf"], TIMINGS[0], TIMINGS[0] + "0")),
    ("sentinel-timing", "failover-timeout distinto", _text("ConfigMap", "sentinel-config", ["data", "sentinel-master.conf"], TIMINGS[1], TIMINGS[1] + "0")),
    ("sentinel-timing", "parallel-syncs distinto", _text("ConfigMap", "sentinel-config", ["data", "sentinel-master.conf"], TIMINGS[2], TIMINGS[2] + "0")),
    ("replica-priority", "la misma prioridad", _env_set("valkey-a", "valkey", "REPLICA_PRIORITY", "100")),
    ("initial-primary", "valkey-a como replica", _env_set("valkey-a", "valkey", "INITIAL_PRIMARY", "valkey-b-0.valkey-b.vectra-edge.svc.cluster.local")),
    ("replicas", "valkey-a con 2 replicas", _set("StatefulSet", "valkey-a", ["spec", "replicas"], 2)),
    ("replicas", "sentinel-b con 1", _set("StatefulSet", "sentinel-b", ["spec", "replicas"], 1)),
    ("quorum", "quorum 1", _env_set("sentinel-a", "sentinel", "SENTINEL_QUORUM", "1")),
    ("pdb", "PDB de Valkey en 2", _set("PodDisruptionBudget", "valkey", ["spec", "minAvailable"], 2)),
    ("pdb", "PDB de Sentinel en 1", _set("PodDisruptionBudget", "sentinel", ["spec", "minAvailable"], 1)),
    ("exporter-sidecar", "sin exportador", _del("StatefulSet", "valkey-a", _container_path("valkey-a", "exporter"))),
    ("exporter-sidecar", "otro puerto", _set("StatefulSet", "valkey-b", _container_path("valkey-b", "exporter", "ports", 0, "containerPort"), 9122)),
    ("exporter-sidecar", "otro usuario", _env_set("valkey-a", "exporter", "REDIS_USER", "ratelimit")),
    ("exporter-sidecar", "la contrasena de otra clave", _env_secret("valkey-a", "exporter", "REDIS_PASSWORD", "valkey-acl", "sentinel-lookup-password")),
    ("no-plain-password", "masterauth en el ConfigMap", _text("ConfigMap", "valkey-config", VALKEY_CONF, "replica-read-only yes", "masterauth secreto")),
    ("no-plain-password", "contrasena como valor", _env_set("valkey-a", "exporter", "REDIS_PASSWORD", "secreto")),
    ("no-plain-password", "contrasena de otro Secret", _env_secret("sentinel-a", "sentinel", "REDISCLI_AUTH", "otro", "x")),
    ("resources", "CPU de Valkey ampliada", _set("StatefulSet", "valkey-a", _container_path("valkey-a", "valkey", "resources", "limits", "cpu"), "2")),
    ("resources", "Sentinel sin limits", _del("StatefulSet", "sentinel-a", _container_path("sentinel-a", "sentinel", "resources", "limits"))),
    ("hardening", "sin prioridad", _set("StatefulSet", "valkey-a", [*_pod("valkey-a"), "priorityClassName"], "")),
    ("hardening", "sin criticidad en el pod", _del("StatefulSet", "sentinel-b", ["spec", "template", "metadata", "labels", "vectra.io/criticality"])),
    ("hardening", "sin criticidad en el StatefulSet", _del("StatefulSet", "valkey-b", ["metadata", "labels", "vectra.io/criticality"])),
    ("hardening", "pod como root", _set("StatefulSet", "valkey-a", [*_pod("valkey-a"), "securityContext", "runAsNonRoot"], False)),
    ("hardening", "sin seccomp", _del("StatefulSet", "sentinel-a", [*_pod("sentinel-a"), "securityContext", "seccompProfile"])),
    ("hardening", "raiz escribible", _set("StatefulSet", "valkey-a", _container_path("valkey-a", "valkey", "securityContext", "readOnlyRootFilesystem"), False)),
    ("hardening", "token montado", _set("StatefulSet", "valkey-a", [*_pod("valkey-a"), "automountServiceAccountToken"], True)),
    ("hardening", "cuenta de servicio con token", _set("ServiceAccount", "sentinel", ["automountServiceAccountToken"], True)),
    ("headless-service", "Service con IP", _set("Service", "sentinel-a", ["spec", "clusterIP"], "10.0.0.1")),
    ("headless-service", "no publica las no listas", _set("Service", "valkey-a", ["spec", "publishNotReadyAddresses"], False)),
    ("external-secret", "otro almacen", _set("ExternalSecret", "valkey-acl", ["spec", "secretStoreRef", "name"], "otro")),
    ("external-secret", "otra propiedad", _set("ExternalSecret", "valkey-acl", ["spec", "data", 0, "remoteRef", "property"], "otra")),
    ("external-secret", "otro Secret destino", _set("ExternalSecret", "valkey-acl", ["spec", "target", "name"], "otro")),
    ("plain-secret", "un Secret en claro", _add(PLAIN_SECRET)),
    ("required-documents", "sin el PDB de Sentinel", _drop("PodDisruptionBudget", "sentinel")),
    ("zone-layout", "los dos nodos en la misma zona", _set("StatefulSet", "valkey-b", [*_pod("valkey-b"), "affinity", "nodeAffinity", "requiredDuringSchedulingIgnoredDuringExecution", "nodeSelectorTerms", 0, "matchExpressions", 0, "values"], [design.zones()[0]])),
    ("sentinel-total", "cuatro Sentinel", _set("StatefulSet", "sentinel-b", ["spec", "replicas"], 3)),
    ("selectors", "el selector no selecciona el template", _set("StatefulSet", "valkey-a", ["spec", "selector", "matchLabels", "app.kubernetes.io/instance"], "otra")),
    ("selectors", "el Service no selecciona sus pods", _set("Service", "sentinel-b", ["spec", "selector", "app.kubernetes.io/instance"], "otra")),
    ("selectors", "el PDB no selecciona ningun pod", _set("PodDisruptionBudget", "valkey", ["spec", "selector", "matchLabels", "app.kubernetes.io/name"], "otra")),
]


def test_every_rule_has_a_failing_case() -> None:
    assert {rule for rule, _, _ in MUTATIONS} == policy_rules()


@pytest.mark.parametrize(("rule", "case", "mutate"), MUTATIONS, ids=[f"{r}-{c}" for r, c, _ in MUTATIONS])
def test_rule_fails_on_an_altered_render(rule: str, case: str, mutate: Callable[[Docs], None], prod: Docs) -> None:
    docs = copy.deepcopy(prod)
    mutate(docs)
    code, output = conftest(docs)
    assert code != 0, f"{rule}/{case}: conftest no fallo"
    assert f"{rule}: " in output, f"{rule}/{case}: la salida no nombra la regla\n{output}"


# --- politicas de U1 (Kyverno) ----------------------------------------------------------------------------------


def test_the_render_meets_the_u1_kyverno_policies(rendered: tuple[str, Docs]) -> None:
    ok, output = kd.kyverno(rendered[1])
    assert ok, output


def _sts_all(change: Callable[[dict[str, Any]], None]) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        for sts in (d for d in docs if d["kind"] == "StatefulSet"):
            change(sts)

    return mutate


U1_MUTATIONS: list[tuple[str, Callable[[Docs], None]]] = [
    ("sin prioridad", _sts_all(lambda s: s["spec"]["template"]["spec"].pop("priorityClassName"))),
    ("raiz escribible", _sts_all(lambda s: s["spec"]["template"]["spec"]["containers"][0]["securityContext"].update(readOnlyRootFilesystem=False))),
    ("sin limites", _sts_all(lambda s: s["spec"]["template"]["spec"]["containers"][0]["resources"].pop("limits"))),
    ("pod como root", _sts_all(lambda s: s["spec"]["template"]["spec"]["securityContext"].update(runAsNonRoot=False))),
    ("sin digest", _sts_all(lambda s: s["spec"]["template"]["spec"]["containers"][0].update(image="kind-registry:5000/vectra/valkey:8.1.11-alpine"))),
    ("registro ajeno", _sts_all(lambda s: s["spec"]["template"]["spec"]["containers"][0].update(image="docker.io/valkey/valkey@sha256:" + "a" * 64))),
    ("sin criticidad", _sts_all(lambda s: s["metadata"]["labels"].pop("vectra.io/criticality"))),
    ("Secret en claro", _add(PLAIN_SECRET)),
]


@pytest.mark.parametrize(("case", "mutate"), U1_MUTATIONS, ids=[c for c, _ in U1_MUTATIONS])
def test_u1_kyverno_policies_fail_on_an_altered_render(case: str, mutate: Callable[[Docs], None], prod: Docs) -> None:
    docs = copy.deepcopy(prod)
    mutate(docs)
    ok, output = kd.kyverno(docs)
    assert not ok, f"{case}: kyverno no fallo\n{output}"
