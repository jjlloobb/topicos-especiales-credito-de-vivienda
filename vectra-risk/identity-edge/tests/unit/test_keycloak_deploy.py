"""Despliegue de Keycloak (U02-T07, Paso 5): NFR-U2-01, 02, 23, 26; P-U2-04; INF-U2-01, 05a, 05b, 06, 08.

Cada regla de identity-edge/keycloak/policy/ tiene su caso que falla sobre un render alterado, y los valores
que las pruebas esperan salen de los documentos de diseno (las pruebas `design`).
"""

import copy
from collections.abc import Callable
from typing import Any

import keycloak_deploy_checks as kd
import pytest
import yaml

Docs = list[dict[str, Any]]


def _sts(docs: Docs) -> dict[str, Any]:
    return kd.statefulset(docs)


def _pod(docs: Docs) -> dict[str, Any]:
    return _sts(docs)["spec"]["template"]["spec"]


def _container(docs: Docs) -> dict[str, Any]:
    return _pod(docs)["containers"][0]


def _env(docs: Docs, name: str) -> dict[str, Any]:
    (found,) = [e for e in _container(docs)["env"] if e["name"] == name]
    return found


def _drop(kind: str, name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        docs.remove(kd.find(docs, kind, name))

    return mutate


def _set(kind: str, name: str, path: list[str | int], value: Any) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = kd.find(docs, kind, name)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def _env_value(name: str, value: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _env(docs, name).pop("valueFrom", None)
        _env(docs, name)["value"] = value

    return mutate


def _env_drop(name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _container(docs)["env"].remove(_env(docs, name))

    return mutate


def _env_add(name: str, value: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _container(docs)["env"].append({"name": name, "value": value})

    return mutate


def _sts_set(path: list[str | int], value: Any) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = _sts(docs)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def _sts_del(path: list[str]) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = _sts(docs)
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return mutate


def _add_doc(doc: dict[str, Any]) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        docs.append(copy.deepcopy(doc))

    return mutate


def _other_container(docs: Docs) -> None:
    _pod(docs)["containers"].append({"name": "sidecar", "image": "x"})


def _spread_hostname(docs: Docs) -> None:
    _pod(docs)["topologySpreadConstraints"][0]["topologyKey"] = "kubernetes.io/hostname"


def _spread_soft(docs: Docs) -> None:
    _pod(docs)["topologySpreadConstraints"][0]["whenUnsatisfiable"] = "ScheduleAnyway"


def _es_dataFrom(docs: Docs) -> None:
    kd.find(docs, "ExternalSecret", "identity-ca")["spec"]["dataFrom"] = [{"extract": {"key": "identity"}}]


def _service_drop_port(docs: Docs) -> None:
    ports = kd.find(docs, "Service", "keycloak")["spec"]["ports"]
    ports[:] = [p for p in ports if p["port"] != 7800]


def _admin_extra_port(docs: Docs) -> None:
    kd.find(docs, "Service", "keycloak-admin")["spec"]["ports"].append({"name": "http", "port": 80, "targetPort": "http"})


def _probe_port(docs: Docs) -> None:
    _container(docs)["readinessProbe"]["httpGet"]["port"] = "http"


def _volume_drop(docs: Docs) -> None:
    volumes = _pod(docs)["volumes"]
    volumes[:] = [v for v in volumes if v.get("secret", {}).get("secretName") != "keycloak-tls"]


def _env_from_configmap(name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _env(docs, name).pop("value", None)
        _env(docs, name)["valueFrom"] = {"configMapKeyRef": {"name": "x", "key": "y"}}

    return mutate


def _env_extra_key(docs: Docs) -> None:
    _env(docs, "KC_DB")["valueFrom"] = {"configMapKeyRef": {"name": "x", "key": "y"}}


def _env_secret_with_value(docs: Docs) -> None:
    _env(docs, "KC_DB_PASSWORD")["value"] = "x"


def _service(name: str, **spec: Any) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        kd.find(docs, "Service", name)["spec"].update(spec)

    return mutate


def _stranger_service(docs: Docs) -> None:
    docs.append({"apiVersion": "v1", "kind": "Service", "metadata": {"name": "keycloak-extra", "namespace": "vectra-identity"},
                 "spec": {"type": "NodePort", "selector": {"app.kubernetes.io/name": "keycloak", "app.kubernetes.io/instance": "keycloak"},
                          "ports": [{"name": "https", "port": 8443, "targetPort": "https", "protocol": "TCP"}]}})  # fmt: skip


def _node_port(name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        kd.find(docs, "Service", name)["spec"]["ports"][0]["nodePort"] = 30443

    return mutate


def _hpa_utilization(docs: Docs) -> None:
    kd.find(docs, "HorizontalPodAutoscaler", "keycloak")["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"] = 80


def _hpa_metric_memory(docs: Docs) -> None:
    kd.find(docs, "HorizontalPodAutoscaler", "keycloak")["spec"]["metrics"][0]["resource"]["name"] = "memory"


POD = ["spec", "template", "spec"]
CON = [*POD, "containers", 0]


def _vol_add(volume: dict[str, Any], mount: dict[str, Any] | None = None) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _pod(docs)["volumes"].append(volume)
        if mount is not None:
            _container(docs)["volumeMounts"].append(mount)

    return mutate


def _vol_edit(name: str, **change: Any) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        (volume,) = [v for v in _pod(docs)["volumes"] if v["name"] == name]
        volume.pop("secret", None) if "secret" in change else None
        volume.pop("configMap", None) if "configMap" in change else None
        volume.pop("emptyDir", None) if "emptyDir" in change else None
        volume.update(change)

    return mutate


def _mount_edit(name: str, **change: Any) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        (mount,) = [m for m in _container(docs)["volumeMounts"] if m["name"] == name]
        mount.update(change)

    return mutate


def _mount_drop(name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _container(docs)["volumeMounts"][:] = [m for m in _container(docs)["volumeMounts"] if m["name"] != name]

    return mutate


def _probe_edit(probe: str, key: str, value: Any, inner: bool = True) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node = _container(docs)[probe]
        (node["httpGet"] if inner else node)[key] = value

    return mutate


def _sa_automount(docs: Docs) -> None:
    kd.find(docs, "ServiceAccount", "keycloak")["automountServiceAccountToken"] = True


def _annotation(docs: Docs) -> None:
    _sts(docs)["spec"]["template"]["metadata"]["annotations"]["linkerd.io/inject"] = "disabled"


def _label(docs: Docs) -> None:
    _sts(docs)["spec"]["template"]["metadata"]["labels"]["extra"] = "x"


PLAIN_SECRET = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "keycloak-plain", "namespace": "vectra-identity"}, "data": {"password": "cGFzcw=="}}
ROUTE = {"apiVersion": "gateway.networking.k8s.io/v1", "kind": "HTTPRoute", "metadata": {"name": "keycloak-admin", "namespace": "vectra-identity"}, "spec": {}}
STRANGER = {"apiVersion": "external-secrets.io/v1", "kind": "ExternalSecret", "metadata": {"name": "other", "namespace": "vectra-identity"}, "spec": {}}
OTHER_CERT = {"apiVersion": "cert-manager.io/v1", "kind": "Certificate", "metadata": {"name": "other", "namespace": "vectra-identity"}, "spec": {}}
IMAGE = "registro.banco.internal/vectra/keycloak"

# (regla, caso, alteracion). Cada regla de la politica aparece al menos una vez; la prueba exige que la salida la nombre.
MUTATIONS: list[tuple[str, str, Callable[[Docs], None]]] = [
    ("statefulset-shape", "dos contenedores", _other_container),
    ("statefulset-shape", "otro namespace", _sts_set(["metadata", "namespace"], "vectra-app")),
    ("replicas", "1 replica", _sts_set(["spec", "replicas"], 1)),
    ("replicas", "3 replicas", _sts_set(["spec", "replicas"], 3)),
    ("hpa", "minimo 1", _set("HorizontalPodAutoscaler", "keycloak", ["spec", "minReplicas"], 1)),
    ("hpa", "maximo 5", _set("HorizontalPodAutoscaler", "keycloak", ["spec", "maxReplicas"], 5)),
    ("hpa", "maximo 3", _set("HorizontalPodAutoscaler", "keycloak", ["spec", "maxReplicas"], 3)),
    ("hpa", "metrica de memoria", _hpa_metric_memory),
    ("hpa", "apunta a un Deployment", _set("HorizontalPodAutoscaler", "keycloak", ["spec", "scaleTargetRef", "kind"], "Deployment")),
    ("zone-spread", "sin reparto", _sts_del(["spec", "template", "spec", "topologySpreadConstraints"])),
    ("zone-spread", "reparto por nodo", _spread_hostname),
    ("zone-spread", "reparto blando", _spread_soft),
    ("pdb", "maxUnavailable en vez de minAvailable", lambda d: kd.find(d, "PodDisruptionBudget", "keycloak")["spec"].update({"maxUnavailable": 1}) or kd.find(d, "PodDisruptionBudget", "keycloak")["spec"].pop("minAvailable")),
    ("pdb", "minAvailable 2", _set("PodDisruptionBudget", "keycloak", ["spec", "minAvailable"], 2)),
    ("start-optimized", "start sin --optimized", _sts_set(["spec", "template", "spec", "containers", 0, "args"], ["start"])),
    ("start-optimized", "start-dev", _sts_set(["spec", "template", "spec", "containers", 0, "args"], ["start-dev"])),
    ("start-optimized", "sin args", _sts_del(["spec", "template", "spec", "containers", 0, "args"])),
    ("start-optimized", "con command", _sts_set(["spec", "template", "spec", "containers", 0, "command"], ["sh"])),
    ("env-whitelist", "variable de mas", _env_add("KC_BOOTSTRAP_ADMIN_PASSWORD", "x")),
    ("env-whitelist", "falta una variable", _env_drop("KC_DB_POOL_MAX_SIZE")),
    ("env-whitelist", "pool distinto de 20", _env_value("KC_DB_POOL_MAX_SIZE", "100")),
    ("env-whitelist", "envFrom", _sts_set(["spec", "template", "spec", "containers", 0, "envFrom"], [{"secretRef": {"name": "x"}}])),
    ("env-whitelist", "variable repetida", _env_add("KC_DB", "postgres")),
    ("cache-stack", "kubernetes", _env_value("KC_CACHE_STACK", "kubernetes")),
    ("cache-stack", "sin cache-stack", _env_drop("KC_CACHE_STACK")),
    ("proxy-headers", "forwarded", _env_value("KC_PROXY_HEADERS", "forwarded")),
    ("proxy-headers", "sin proxy-headers", _env_drop("KC_PROXY_HEADERS")),
    ("hostname", "otro host", _env_value("KC_HOSTNAME", "https://otro.banco.internal/auth")),
    ("hostname", "sin /auth", _env_value("KC_HOSTNAME", "https://vectra.banco.internal")),
    ("hostname-admin", "admin publico", _env_value("KC_HOSTNAME_ADMIN", "https://vectra.banco.internal/auth")),
    ("hostname-admin", "otro admin", _env_value("KC_HOSTNAME_ADMIN", "https://admin.banco.internal/auth")),
    ("persistent-sessions", "features-disabled en args", _sts_set(["spec", "template", "spec", "containers", 0, "args"], ["start", "--optimized", "--features-disabled=persistent-user-sessions"])),
    ("persistent-sessions", "KC_FEATURES_DISABLED", _env_add("KC_FEATURES_DISABLED", "persistent-user-sessions")),
    ("probes", "readiness al 8080", _probe_port),
    ("probes", "sin liveness", lambda d: _container(d).pop("livenessProbe")),
    ("resources", "limite de CPU", _sts_set(["spec", "template", "spec", "containers", 0, "resources", "limits", "cpu"], "4")),
    ("resources", "request de memoria", _sts_set(["spec", "template", "spec", "containers", 0, "resources", "requests", "memory"], "512Mi")),
    ("priority", "otra prioridad", _sts_set(["spec", "template", "spec", "priorityClassName"], "vectra-normal")),
    ("priority", "sin prioridad", _sts_del(["spec", "template", "spec", "priorityClassName"])),
    ("criticality", "sin etiqueta", lambda d: _sts(d)["metadata"]["labels"].pop("vectra.io/criticality")),
    ("criticality", "otra criticidad", _sts_set(["metadata", "labels", "vectra.io/criticality"], "medium")),
    ("image", "sin digest", _sts_set(["spec", "template", "spec", "containers", 0, "image"], f"{IMAGE}:26.8.1")),
    ("image", "otro repositorio", _sts_set(["spec", "template", "spec", "containers", 0, "image"], "quay.io/keycloak/keycloak@sha256:" + "a" * 64)),
    ("image", "digest corto", _sts_set(["spec", "template", "spec", "containers", 0, "image"], f"{IMAGE}@sha256:abc")),
    ("db-credentials", "contrasena en claro", _env_value("KC_DB_PASSWORD", "secreto")),
    ("db-credentials", "otro Secret", lambda d: _env(d, "KC_DB_USERNAME")["valueFrom"]["secretKeyRef"].update({"name": "otro"})),
    ("tls-mount", "sin el volumen keycloak-tls", _volume_drop),
    ("no-plain-secret", "Secret con data", _add_doc(PLAIN_SECRET)),
    ("external-secret", "otra clave", _set("ExternalSecret", "identity-ca", ["spec", "data", 0, "remoteRef", "key"], "identity/otra")),
    ("external-secret", "otra propiedad", _set("ExternalSecret", "keycloak-reader-client", ["spec", "data", 0, "remoteRef", "property"], "jwks")),
    ("external-secret", "otro store", _set("ExternalSecret", "identity-ca", ["spec", "secretStoreRef", "name"], "otro")),
    ("external-secret", "dataFrom", _es_dataFrom),
    ("external-secret", "ExternalSecret ajeno", _add_doc(STRANGER)),
    ("keycloak-tls", "SAN de mas", _set("Certificate", "keycloak-tls", ["spec", "dnsNames"], ["keycloak.vectra-identity.svc", "x.svc"])),
    ("keycloak-tls", "solo el primer SAN", _set("Certificate", "keycloak-tls", ["spec", "dnsNames"], ["keycloak.vectra-identity.svc"])),
    ("keycloak-tls", "SAN en otro orden", _set("Certificate", "keycloak-tls", ["spec", "dnsNames"], ["keycloak-admin.vectra-identity.svc.cluster.local", "keycloak.vectra-identity.svc"])),
    ("issuer-per-environment", "prod con el issuer de kind", _set("Certificate", "keycloak-tls", ["spec", "issuerRef", "name"], "vectra-internal-ca")),
    ("keycloak-tls", "otro SAN", _set("Certificate", "keycloak-tls", ["spec", "dnsNames"], ["keycloak.otro.svc"])),
    ("keycloak-tls", "duracion", _set("Certificate", "keycloak-tls", ["spec", "duration"], "8760h")),
    ("keycloak-tls", "renovacion", _set("Certificate", "keycloak-tls", ["spec", "renewBefore"], "360h")),
    ("keycloak-tls", "issuer vacio", _set("Certificate", "keycloak-tls", ["spec", "issuerRef", "name"], "")),
    ("keycloak-tls", "Issuer de namespace", _set("Certificate", "keycloak-tls", ["spec", "issuerRef", "kind"], "Issuer")),
    ("keycloak-tls", "otro secretName", _set("Certificate", "keycloak-tls", ["spec", "secretName"], "otro")),
    ("keycloak-tls", "Certificate ajeno", _add_doc(OTHER_CERT)),
    ("backend-tls-policy", "otro puerto", _set("BackendTLSPolicy", "keycloak", ["spec", "targetRefs", 0, "sectionName"], "jgroups")),
    ("backend-tls-policy", "otra CA", _set("BackendTLSPolicy", "keycloak", ["spec", "validation", "caCertificateRefs", 0, "name"], "otra")),
    ("backend-tls-policy", "CA como ConfigMap", _set("BackendTLSPolicy", "keycloak", ["spec", "validation", "caCertificateRefs", 0, "kind"], "ConfigMap")),
    ("backend-tls-policy", "otro hostname", _set("BackendTLSPolicy", "keycloak", ["spec", "validation", "hostname"], "keycloak.otro.svc")),
    ("env-whitelist", "KC_HOSTNAME_ADMIN desde un ConfigMap", _env_from_configmap("KC_HOSTNAME_ADMIN")),
    ("env-whitelist", "KC_CACHE_STACK desde un ConfigMap", _env_from_configmap("KC_CACHE_STACK")),
    ("env-whitelist", "KC_PROXY_HEADERS desde un ConfigMap", _env_from_configmap("KC_PROXY_HEADERS")),
    ("env-whitelist", "KC_DB_URL_PROPERTIES desde un ConfigMap", _env_from_configmap("KC_DB_URL_PROPERTIES")),
    ("env-whitelist", "KC_HTTP_RELATIVE_PATH desde un ConfigMap", _env_from_configmap("KC_HTTP_RELATIVE_PATH")),
    ("env-whitelist", "KC_HOSTNAME desde un ConfigMap", _env_from_configmap("KC_HOSTNAME")),
    ("env-whitelist", "valueFrom y value juntos", _env_extra_key),
    ("env-whitelist", "credencial con value", _env_secret_with_value),
    ("hpa", "objetivo del 80 %", _hpa_utilization),
    ("service-whitelist", "keycloak-admin NodePort", _service("keycloak-admin", type="NodePort")),
    ("service-whitelist", "keycloak-http NodePort", _service("keycloak-http", type="NodePort")),
    ("service-whitelist", "keycloak LoadBalancer", _service("keycloak", type="LoadBalancer")),
    ("service-whitelist", "Service extra NodePort", _stranger_service),
    ("service-whitelist", "keycloak con otro selector", _service("keycloak", selector={"app.kubernetes.io/name": "otro"})),
    ("service-whitelist", "keycloak-headless con IP", _service("keycloak-headless", clusterIP="10.0.0.1")),
    ("service-whitelist", "keycloak-admin con externalIPs", _service("keycloak-admin", externalIPs=["1.2.3.4"])),
    ("service-ports", "nodePort en keycloak-admin", _node_port("keycloak-admin")),
    ("service-ports", "keycloak-http con un puerto menos", lambda d: kd.find(d, "Service", "keycloak-http")["spec"]["ports"].pop()),
    ("service-ports", "sin 7800", _service_drop_port),
    ("service-ports", "admin con dos puertos", _admin_extra_port),
    ("no-gateway-route", "HTTPRoute del admin", _add_doc(ROUTE)),
    ("present", "sin StatefulSet", _drop("StatefulSet", "keycloak")),
    ("present", "sin HPA", _drop("HorizontalPodAutoscaler", "keycloak")),
    ("present", "sin PDB", _drop("PodDisruptionBudget", "keycloak")),
    ("present", "sin Service keycloak", _drop("Service", "keycloak")),
    ("present", "sin Service keycloak-admin", _drop("Service", "keycloak-admin")),
    ("present", "sin keycloak-tls", _drop("Certificate", "keycloak-tls")),
    ("present", "sin BackendTLSPolicy", _drop("BackendTLSPolicy", "keycloak")),
    ("present", "sin identity-ca", _drop("ExternalSecret", "identity-ca")),
    ("present", "sin credencial de config-cli", _drop("ExternalSecret", "keycloak-config-cli-client")),
    ("present", "sin credencial de reader", _drop("ExternalSecret", "keycloak-reader-client")),
    ("hpa-targets-statefulset", "sin StatefulSet", _drop("StatefulSet", "keycloak")),
    # F-06: el pod template entero contra una lista exacta (sondas del revisor y una variante por campo).
    ("volumes", "keycloak.conf desde un ConfigMap con subPath", _vol_add({"name": "conf", "configMap": {"name": "x"}}, {"name": "conf", "mountPath": "/opt/keycloak/conf/keycloak.conf", "subPath": "keycloak.conf"})),
    ("volumes", "quarkus.properties montado", _vol_add({"name": "conf", "configMap": {"name": "x"}}, {"name": "conf", "mountPath": "/opt/keycloak/conf/quarkus.properties", "subPath": "quarkus.properties"})),
    ("volumes", "internal-ca desde otro ConfigMap", _vol_edit("internal-ca", configMap={"name": "otro"})),
    ("volumes", "tls desde otro Secret", _vol_edit("tls", secret={"secretName": "otro"})),
    ("volumes", "volumen de mas sin montar", _vol_add({"name": "extra", "emptyDir": {}})),
    ("volumes", "hostPath", _vol_edit("data", hostPath={"path": "/"})),
    ("volumes", "internal-ca como Secret", _vol_edit("internal-ca", secret={"secretName": "vectra-internal-ca"})),
    ("volumes", "sin el volumen tmp", lambda d: _pod(d)["volumes"].pop(2)),
    ("volume-mounts", "volumen tls montado en otra ruta", _mount_edit("tls", mountPath="/etc/otro")),
    ("volume-mounts", "tls escribible", _mount_edit("tls", readOnly=False)),
    ("volume-mounts", "internal-ca escribible", _mount_edit("internal-ca", readOnly=False)),
    ("volume-mounts", "subPath en tmp", _mount_edit("tmp", subPath="x")),
    ("volume-mounts", "internal-ca en otra ruta", _mount_edit("internal-ca", mountPath="/opt/keycloak/conf")),
    ("volume-mounts", "sin el montaje data", _mount_drop("data")),
    ("volume-mounts", "montaje de mas", lambda d: _container(d)["volumeMounts"].append({"name": "tmp", "mountPath": "/opt/keycloak/conf"})),
    ("pod-spec", "initContainers", _sts_set([*POD, "initContainers"], [{"name": "init", "image": "x"}])),
    ("pod-spec", "hostNetwork", _sts_set([*POD, "hostNetwork"], True)),
    ("pod-spec", "hostPID", _sts_set([*POD, "hostPID"], True)),
    ("pod-spec", "hostIPC", _sts_set([*POD, "hostIPC"], True)),
    ("pod-spec", "shareProcessNamespace", _sts_set([*POD, "shareProcessNamespace"], True)),
    ("pod-spec", "automountServiceAccountToken en el pod", _sts_set([*POD, "automountServiceAccountToken"], True)),
    ("pod-spec", "otra cuenta de servicio", _sts_set([*POD, "serviceAccountName"], "default")),
    ("pod-spec", "nodeSelector", _sts_set([*POD, "nodeSelector"], {"x": "y"})),
    ("pod-spec", "tolerations", _sts_set([*POD, "tolerations"], [{"operator": "Exists"}])),
    ("pod-spec", "dnsPolicy", _sts_set([*POD, "dnsPolicy"], "None")),
    ("pod-spec", "hostAliases", _sts_set([*POD, "hostAliases"], [{"ip": "1.2.3.4", "hostnames": ["x"]}])),
    ("pod-spec", "gracia de terminacion", _sts_set([*POD, "terminationGracePeriodSeconds"], 0)),
    ("pod-spec", "restartPolicy", _sts_set([*POD, "restartPolicy"], "Never")),
    ("pod-spec", "enableServiceLinks", _sts_set([*POD, "enableServiceLinks"], False)),
    ("pod-spec", "afinidad distinta", _sts_set([*POD, "affinity", "podAntiAffinity", "requiredDuringSchedulingIgnoredDuringExecution"], [])),
    ("pod-security", "fsGroup distinto", _sts_set([*POD, "securityContext", "fsGroup"], 0)),
    ("pod-security", "runAsUser 0 en el pod", _sts_set([*POD, "securityContext", "runAsUser"], 0)),
    ("pod-security", "sysctls", _sts_set([*POD, "securityContext", "sysctls"], [{"name": "net.ipv4.ip_forward", "value": "1"}])),
    ("pod-security", "seccomp Unconfined", _sts_set([*POD, "securityContext", "seccompProfile", "type"], "Unconfined")),
    ("container-spec", "command", _sts_set([*CON, "command"], ["sh"])),
    ("container-spec", "workingDir", _sts_set([*CON, "workingDir"], "/")),
    ("container-spec", "lifecycle", _sts_set([*CON, "lifecycle"], {"postStart": {"exec": {"command": ["sh"]}}})),
    ("container-spec", "imagePullPolicy Always", _sts_set([*CON, "imagePullPolicy"], "Always")),
    ("container-spec", "otro nombre", _sts_set([*CON, "name"], "otro")),
    ("container-spec", "stdin", _sts_set([*CON, "stdin"], True)),
    ("container-spec", "sin startupProbe", lambda d: _container(d).pop("startupProbe")),
    ("container-security", "privileged", _sts_set([*CON, "securityContext", "privileged"], True)),
    ("container-security", "runAsUser 0", _sts_set([*CON, "securityContext", "runAsUser"], 0)),
    ("container-security", "raiz escribible", _sts_set([*CON, "securityContext", "readOnlyRootFilesystem"], False)),
    ("container-security", "escalada de privilegios", _sts_set([*CON, "securityContext", "allowPrivilegeEscalation"], True)),
    ("container-security", "capacidad NET_ADMIN", _sts_set([*CON, "securityContext", "capabilities", "add"], ["NET_ADMIN"])),
    ("container-security", "sin drop ALL", _sts_set([*CON, "securityContext", "capabilities", "drop"], ["NET_RAW"])),
    ("ports", "puerto de mas", lambda d: _container(d)["ports"].append({"name": "x", "containerPort": 9999, "protocol": "TCP"})),
    ("ports", "hostPort", lambda d: _container(d)["ports"][2].update({"hostPort": 8443})),
    ("ports", "sin jgroups", lambda d: _container(d)["ports"].pop()),
    ("ports", "9000 en otro numero", lambda d: _container(d)["ports"][1].update({"containerPort": 9001})),
    ("probes", "path de liveness", _probe_edit("livenessProbe", "path", "/auth/otro")),
    ("probes", "esquema HTTP", _probe_edit("readinessProbe", "scheme", "HTTP")),
    ("probes", "retraso de readiness", _probe_edit("readinessProbe", "initialDelaySeconds", 600, inner=False)),
    ("probes", "failureThreshold de startup", _probe_edit("startupProbe", "failureThreshold", 1, inner=False)),
    ("probes", "sonda exec", _sts_set([*CON, "livenessProbe"], {"exec": {"command": ["true"]}})),
    ("template-metadata", "anotacion de mas", _annotation),
    ("template-metadata", "etiqueta de mas", _label),
    ("statefulset-spec", "volumeClaimTemplates", _sts_set(["spec", "volumeClaimTemplates"], [{"metadata": {"name": "x"}}])),
    ("statefulset-spec", "otra estrategia", _sts_set(["spec", "updateStrategy", "type"], "OnDelete")),
    ("service-account", "automount del token", _sa_automount),
    ("service-account", "sin la cuenta de servicio", _drop("ServiceAccount", "keycloak")),
]  # fmt: skip


@pytest.fixture(scope="module")
def prod() -> Docs:
    return kd.load("prod")


# --- lo renderizado cumple ----------------------------------------------------------------------

@pytest.mark.parametrize("env", kd.ENVS)
def test_rendered_keycloak_meets_the_policies(env):
    code, output = kd.conftest(kd.load(env))
    assert code == 0, output


@pytest.mark.parametrize("env", kd.ENVS)
def test_committed_render_matches_a_fresh_render(env):
    fresh = kd.render(env)
    assert fresh.returncode == 0, fresh.stderr
    assert (kd.RENDERED / env / "keycloak.yaml").read_text(encoding="utf-8") == fresh.stdout


# --- cada regla falla sobre un render alterado -------------------------------------------------

def test_every_rule_has_a_failing_case():
    assert {rule for rule, _, _ in MUTATIONS} == kd.policy_rules()


@pytest.mark.parametrize(("rule", "case", "mutate"), MUTATIONS, ids=[f"{r}-{c}" for r, c, _ in MUTATIONS])
def test_rule_fails_on_an_altered_render(rule, case, mutate, prod):
    docs = copy.deepcopy(prod)
    mutate(docs)
    code, output = kd.conftest(docs)
    assert code != 0, f"{rule}/{case}: conftest no fallo"
    assert f"{rule}: " in output, f"{rule}/{case}: la salida no nombra la regla\n{output}"


def test_kind_with_another_issuer_fails():
    docs = kd.load("kind")
    _set("Certificate", "keycloak-tls", ["spec", "issuerRef", "name"], "banco-ca")(docs)
    code, output = kd.conftest(docs)
    assert code != 0 and "issuer-per-environment: " in output


def test_staging_with_the_kind_issuer_fails():
    docs = kd.load("staging")
    _set("Certificate", "keycloak-tls", ["spec", "issuerRef", "name"], "vectra-internal-ca")(docs)
    code, output = kd.conftest(docs)
    assert code != 0 and "issuer-per-environment: " in output


@pytest.mark.parametrize("env", ["kind", "staging"])
def test_a_rule_also_fails_in_other_environments(env):
    docs = kd.load(env)
    _env_value("KC_HOSTNAME_ADMIN", "https://vectra.banco.internal/auth")(docs)
    code, output = kd.conftest(docs)
    assert code != 0 and "hostname-admin: " in output


# --- los valores salen del diseno ---------------------------------------------------------------

def test_design_chart_version_is_the_downloaded_one():
    chart = yaml.safe_load((kd.CHART / "Chart.yaml").read_text(encoding="utf-8"))
    assert chart["version"] == kd.design_chart_version()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_hostnames(env):
    public = kd.design_public_hostnames()[env]
    path = kd.design_hostname_path()
    envs = kd.container_env(kd.load(env))
    assert envs["KC_HOSTNAME"]["value"] == f"https://{public}{path}"
    admin = envs["KC_HOSTNAME_ADMIN"]["value"]
    assert admin.startswith(f"https://{kd.design_admin_hostname()}:") and admin.endswith(path)
    assert kd.find(kd.load(env), "Service", "keycloak-admin")["metadata"]["name"] == kd.design_admin_hostname().split(".")[0]


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_resources(env):
    docs = kd.load(env)
    assert _container(docs)["resources"] == kd.design_keycloak_resources()
    assert kd.container_env(docs)["JAVA_OPTS_APPEND"]["value"] == kd.design_max_ram_percentage()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_replicas_hpa_and_pdb(env):
    docs = kd.load(env)
    low, high = kd.design_replicas()
    spec = kd.find(docs, "HorizontalPodAutoscaler", "keycloak")["spec"]
    assert (spec["minReplicas"], spec["maxReplicas"]) == (low, high)
    assert "replicas" not in _sts(docs)["spec"]
    assert kd.find(docs, "PodDisruptionBudget", "keycloak")["spec"]["minAvailable"] == kd.design_pdb_min_available()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_image_repository_and_digest(env):
    image = _container(kd.load(env))["image"]
    repository, digest = image.split("@")
    assert repository == kd.design_image_repositories()[env]
    assert digest.startswith("sha256:")


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_container_ports_match_flows(env):
    declared = {p["containerPort"] for p in _container(kd.load(env))["ports"]}
    assert set(kd.design_ports().values()) <= declared
    assert declared - set(kd.design_ports().values()) == {8080}


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_start_args_and_image_tag_come_from_the_dockerfile_design(env):
    import theme_checks as tc

    assert _container(kd.load(env))["args"] == tc.design_start_args()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_vault_keys(env):
    docs = kd.load(env)
    read = {}
    for doc in docs:
        if doc["kind"] == "ExternalSecret":
            for item in doc["spec"]["data"]:
                read[item["remoteRef"]["key"]] = item["remoteRef"]["property"]
    assert read == kd.design_vault_entries()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_certificate_and_backend_policy(env):
    docs = kd.load(env)
    cert = kd.design_certificate()
    spec = kd.find(docs, "Certificate", "keycloak-tls")["spec"]
    assert (spec["dnsNames"], spec["duration"], spec["renewBefore"]) == (cert["sans"], cert["duration"], cert["renewBefore"])
    assert kd.find(docs, "BackendTLSPolicy", "keycloak")["spec"]["validation"]["hostname"] == cert["sans"][0]
    assert cert["sans"][1] == kd.design_admin_hostname()


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_hpa_utilization(env):
    metric = kd.find(kd.load(env), "HorizontalPodAutoscaler", "keycloak")["spec"]["metrics"]
    assert [m["resource"]["target"]["averageUtilization"] for m in metric] == [kd.design_hpa_utilization()]


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_secret_names(env):
    docs = kd.load(env)
    found = {d["spec"]["data"][0]["remoteRef"]["key"]: d["spec"]["target"]["name"] for d in docs if d["kind"] == "ExternalSecret"}
    assert found == kd.design_secret_names()
    assert all(d["metadata"]["name"] == d["spec"]["target"]["name"] for d in docs if d["kind"] == "ExternalSecret")


def test_design_issuer_is_the_internal_ca_only_in_kind():
    internal = kd.design_internal_issuer()
    names = {env: kd.find(kd.load(env), "Certificate", "keycloak-tls")["spec"]["issuerRef"]["name"] for env in kd.ENVS}
    assert names["kind"] == internal
    assert names["staging"] != internal and names["prod"] != internal


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_ports_match_flows(env):
    ports = kd.design_ports()
    service = kd.find(kd.load(env), "Service", "keycloak")
    assert sorted(p["port"] for p in service["spec"]["ports"]) == sorted(ports.values())


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_render_fails_without_digest(env):
    result = kd.render(env, "--set", "image.digest=")
    assert result.returncode != 0
    assert "digest" in result.stderr


@pytest.mark.parametrize("env", kd.ENVS)
def test_design_render_without_digest_key_fails(env):
    result = kd.render(env, "--set", "image.digest=null")
    assert result.returncode != 0
    assert "digest" in result.stderr


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_design_render_fails_without_issuer_ref(env):
    result = kd.render(env, "--set", "vectra.tls.issuerRef=null")
    assert result.returncode != 0
    assert "issuerRef" in result.stderr


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_design_render_fails_with_an_empty_issuer_name(env):
    result = kd.render(env, "--set", "vectra.tls.issuerRef.name=")
    assert result.returncode != 0
    assert "issuerRef" in result.stderr


def test_design_common_values_have_no_default_issuer_or_digest():
    common = yaml.safe_load((kd.VALUES / "common.yaml").read_text(encoding="utf-8"))
    assert not common.get("image", {}).get("digest")
    assert "issuerRef" not in common.get("vectra", {}).get("tls", {})


# --- politicas de U1 (Kyverno) ------------------------------------------------------------------

@pytest.mark.parametrize("env", kd.ENVS)
def test_rendered_keycloak_meets_the_u1_kyverno_policies(env):
    ok, output = kd.kyverno(kd.load(env))
    assert ok, output


U1_MUTATIONS: list[tuple[str, Callable[[Docs], None]]] = [
    ("sin prioridad", _sts_del(["spec", "template", "spec", "priorityClassName"])),
    ("raiz escribible", _sts_set(["spec", "template", "spec", "containers", 0, "securityContext", "readOnlyRootFilesystem"], False)),
    ("sin limites", _sts_del(["spec", "template", "spec", "containers", 0, "resources", "limits"])),
    ("pod como root", _sts_set(["spec", "template", "spec", "securityContext", "runAsNonRoot"], False)),
    ("sin digest", _sts_set(["spec", "template", "spec", "containers", 0, "image"], f"{IMAGE}:26.8.1")),
    ("registro ajeno", _sts_set(["spec", "template", "spec", "containers", 0, "image"], "quay.io/keycloak/keycloak@sha256:" + "a" * 64)),
    ("sin criticidad", lambda d: _sts(d)["metadata"]["labels"].pop("vectra.io/criticality")),
    ("Secret en claro", _add_doc(PLAIN_SECRET)),
]


@pytest.mark.parametrize(("case", "mutate"), U1_MUTATIONS, ids=[c for c, _ in U1_MUTATIONS])
def test_u1_kyverno_policies_fail_on_an_altered_render(case, mutate, prod):
    docs = copy.deepcopy(prod)
    mutate(docs)
    ok, output = kd.kyverno(docs)
    assert not ok, f"{case}: kyverno no fallo\n{output}"
