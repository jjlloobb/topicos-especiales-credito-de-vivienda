# Reglas de conftest sobre el render del chart de U8 (Paso 20; INF-U8-01 a 07; P-U8-10; NFR-U8-10, 12, 14, 20, 26, 43, 44), por documento (`conftest test`).
# Cada `# regla: x` tiene un caso que falla en case-management/tests/unit/test_chart.py, y cada mensaje empieza por `x:`. Lo que exige ver todo el render junto esta en
# `set.rego` (`--combine --namespace chart_set`), y las reglas sobre los ARCHIVOS de values de staging y produccion, en `values.rego` (`--namespace values.prod` y `values.staging`).
package main

import rego.v1

namespace := "vectra-app"

mock_namespace := "vectra-mock"

# Los Deployment de U8: `case-service` y `case-worker` (vectra-app, HPA) y el mock (vectra-mock, exento de HPA).
app_deployments := {"case-service", "case-worker"}

deployments := app_deployments | {"core-banking-mock"}

# Un solo conjunto de variables por contenedor (INF-U8-01, 07): las de `Settings.from_env`, `WorkerSettings.from_env`, `migrations/env.py` y U0.
u0_env := {"VECTRA_CLIENT_ID", "VECTRA_TOKEN_URL", "VECTRA_CLIENT_KEY_PATH", "VECTRA_CA_BUNDLE"}

pg_env := {"PGUSER", "PGPASSWORD"}

env_sets := {
	"case-service": (u0_env | pg_env | {"CASE_DB_DSN", "CASE_GOVERNANCE_URL", "CASE_REGISTRY_URL", "CASE_CORE_ENABLED", "CASE_ALLOW_TEST_SCENARIOS", "VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL"}),
	"case-worker": (u0_env | pg_env | {"CASE_DB_DSN", "CASE_GOVERNANCE_URL", "CASE_SCORING_URL"}),
	"core-banking-mock": {"VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL", "VECTRA_CA_BUNDLE"},
	"case-migration": (pg_env | {"CASE_DATABASE_URL", "RETENTION_DECIDED_YEARS", "RETENTION_UNDECIDED_YEARS", "RETENTION_INTAKE_KEYS_DAYS"}),
	"rt5-demo": {"CASE_CORE_URL", "RT5_CREDIT_ID"},
}

# Nombres de las constantes de `vectra_case/config.py` (INF-U8-07): ni estos ni nada con su forma pueden ser variables de entorno.
constant_words := `(?i)(TIMEOUT|POOL|BREAKER|BACKOFF|JITTER|LEASE|BATCH|CONCURRENCY|INTERVAL|ATTEMPTS|TTL|GRACE|ABANDON|POLL|WORST_CASE|FAILURE_RATIO|HALF_OPEN|DEADLINE|MARGIN)`

is_deployment if {
	input.kind == "Deployment"
	input.metadata.name in deployments
}

is_app_deployment if {
	input.kind == "Deployment"
	input.metadata.name in app_deployments
}

is_migration if {
	input.kind == "Job"
	input.metadata.name == "case-migration"
}

is_rt5 if {
	input.kind == "Job"
	startswith(input.metadata.name, "rt5-demo-")
}

is_job if is_migration

is_job if is_rt5

is_workload if is_deployment

is_workload if is_job

# El nombre con el que se busca el conjunto de variables y la imagen.
workload_name := input.metadata.name if is_deployment

workload_name := "case-migration" if is_migration

workload_name := "rt5-demo" if is_rt5

pod := input.spec.template.spec if is_workload

all_containers contains c if {
	is_workload
	some c in pod.containers
}

env_names(container) := {e.name | some e in container.env}

env_value(container, name) := value if {
	some e in container.env
	e.name == name
	value := e.value
}

# --- secretos --------------------------------------------------------------------------------------------------------------------------------------

# regla: no-plain-secret
# El chart no crea ningun Secret (la llave la materializa ESO y la base la entrega U1); ninguna variable lleva credenciales ni sale de un Secret salvo PGUSER y PGPASSWORD.
deny contains msg if {
	input.kind == "Secret"
	msg := sprintf("no-plain-secret: el Secret %s no va en el render; lo crea ESO (la llave) o U1 (la base)", [input.metadata.name])
}

deny contains msg if {
	some c in all_containers
	some e in c.env
	contains(object.get(e, "value", ""), "@")
	not startswith(e.value, "sha256:")
	msg := sprintf("no-plain-secret: %s lleva credenciales en la URL (el DSN va sin usuario ni clave, INF-U8-01)", [e.name])
}

deny contains msg if {
	some c in all_containers
	some e in c.env
	e.valueFrom
	not e.name in pg_env
	msg := sprintf("no-plain-secret: %s sale de un Secret o ConfigMap por entorno; solo PGUSER y PGPASSWORD (Secret de U1) y la llave montada de solo lectura", [e.name])
}

deny contains msg if {
	some c in all_containers
	some e in c.env
	e.name in pg_env
	not startswith(e.valueFrom.secretKeyRef.name, "pg-role-case-")
	msg := sprintf("no-plain-secret: %s sale de %s, no de un Secret pg-role-case-* de U1", [e.name, e.valueFrom.secretKeyRef.name])
}

# --- variables -------------------------------------------------------------------------------------------------------------------------------------

# regla: constant-env
# INF-U8-07: ninguna constante de `config.py` es variable de entorno.
deny contains msg if {
	some c in all_containers
	some e in c.env
	regex.match(constant_words, e.name)
	msg := sprintf("constant-env: %s parece una constante de config.py; no es configuracion (INF-U8-07)", [e.name])
}

# regla: service-env
deny contains msg if {
	is_workload
	some e in all_containers_env
	not e in allowed_env(workload_name)
	msg := sprintf("service-env: %s no es una variable de %s (INF-U8-07)", [e, workload_name])
}

# `CASE_CORE_URL` es opcional en case-service (solo con el core habilitado; las dos reglas siguientes lo atan a `CASE_CORE_ENABLED`).
allowed_env(name) := env_sets[name] | {"CASE_CORE_URL"} if name == "case-service"

allowed_env(name) := env_sets[name] if name != "case-service"

all_containers_env contains name if {
	some c in all_containers
	some e in c.env
	name := e.name
}

deny contains msg if {
	is_workload
	missing := env_sets[workload_name] - all_containers_env
	count(missing) > 0
	msg := sprintf("service-env: a %s le faltan %v", [workload_name, missing])
}

# CASE_CORE_URL existe si y solo si el core esta habilitado (produccion no la trae).
deny contains msg if {
	input.metadata.name == "case-service"
	is_deployment
	c := pod.containers[0]
	env_value(c, "CASE_CORE_ENABLED") == "true"
	not "CASE_CORE_URL" in env_names(c)
	msg := "service-env: con CASE_CORE_ENABLED=true falta CASE_CORE_URL"
}

deny contains msg if {
	input.metadata.name == "case-service"
	is_deployment
	c := pod.containers[0]
	env_value(c, "CASE_CORE_ENABLED") != "true"
	"CASE_CORE_URL" in env_names(c)
	msg := "service-env: sin core habilitado no hay CASE_CORE_URL (produccion)"
}

# --- forma de cada proceso -------------------------------------------------------------------------------------------------------------------------

# regla: service-shape
deny contains msg if {
	is_workload
	not count(pod.containers) == 1
	msg := "service-shape: el pod lleva un solo contenedor"
}

deny contains msg if {
	is_deployment
	object.get(input.spec, "replicas", 1) < 2
	msg := "service-shape: 2 replicas o mas (NFR-U8-12; test_kind_profile.py cuenta spec.replicas)"
}

deny contains msg if {
	is_deployment
	object.get(pod, "serviceAccountName", "") != input.metadata.name
	msg := sprintf("service-shape: la cuenta de servicio es %s (flows.yaml)", [input.metadata.name])
}

deny contains msg if {
	is_deployment
	object.get(input.spec.template.metadata.labels, "app.kubernetes.io/name", "") != input.metadata.name
	msg := sprintf("service-shape: el pod lleva app.kubernetes.io/name: %s (flows.yaml, PDB)", [input.metadata.name])
}

deny contains msg if {
	is_app_deployment
	object.get(input.spec.template.metadata.labels, "vectra.io/workload", "") != input.metadata.name
	msg := sprintf("service-shape: el pod lleva vectra.io/workload: %s (el Service y el PDB lo seleccionan; el Job rt5-demo no)", [input.metadata.name])
}

deny contains msg if {
	is_app_deployment
	object.get(input.metadata.labels, "vectra.io/criticality", "") != "high"
	msg := "service-shape: vectra.io/criticality: high (NFR-U8-20)"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "core-banking-mock"
	object.get(input.metadata.labels, "vectra.io/criticality", "") != "low"
	msg := "service-shape: el mock lleva vectra.io/criticality: low"
}

# regla: mock-exempt
# El mock no escala (2 replicas fijas): `vectra.io/hpa-exempt` con su justificacion (quinta revision de coherencia entre unidades, 2026-10-31).
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "core-banking-mock"
	object.get(input.metadata, ["annotations", "vectra.io/hpa-exempt"], "") == ""
	msg := "mock-exempt: el mock lleva vectra.io/hpa-exempt con su justificacion"
}

# regla: service-rollout
deny contains msg if {
	is_deployment
	input.spec.strategy != {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0}}
	msg := "service-rollout: RollingUpdate con maxSurge 1 y maxUnavailable 0 (INF-U8-05)"
}

# regla: service-priority
expected_priority := "vectra-high" if is_app_deployment

expected_priority := "vectra-low" if {
	is_workload
	not is_app_deployment
}

deny contains msg if {
	is_workload
	object.get(pod, "priorityClassName", "") != expected_priority
	msg := sprintf("service-priority: la prioridad de %s es %s, no %s (INF-U8-04)", [workload_name, expected_priority, object.get(pod, "priorityClassName", "")])
}

# regla: service-spread
deny contains msg if {
	is_deployment
	zones := [t | some t in object.get(pod, "topologySpreadConstraints", []); t.topologyKey == "topology.kubernetes.io/zone"]
	count(zones) == 0
	msg := "service-spread: topologySpreadConstraints por topology.kubernetes.io/zone (NFR-U1-04)"
}

# regla: service-resources
# INF-U8-04. El request de memoria es el del diseno (256 MiB) o el de kind (128 MiB, P-1 = b); `test_chart.py` fija cual en cada entorno.
resources_by_name := {
	"case-service": {"cpu": "250m", "limits": {"cpu": "1", "memory": "512Mi"}},
	"case-worker": {"cpu": "200m", "limits": {"cpu": "1", "memory": "512Mi"}},
	"core-banking-mock": {"cpu": "50m", "limits": {"cpu": "250m", "memory": "128Mi"}},
	"case-migration": {"cpu": "100m", "limits": {"cpu": "500m", "memory": "256Mi"}},
	"rt5-demo": {"cpu": "50m", "limits": {"cpu": "250m", "memory": "128Mi"}},
}

memory_requests := {
	"case-service": {"256Mi", "128Mi"},
	"case-worker": {"256Mi", "128Mi"},
	"core-banking-mock": {"64Mi"},
	"case-migration": {"128Mi"},
	"rt5-demo": {"64Mi"},
}

deny contains msg if {
	is_workload
	c := pod.containers[0]
	want := resources_by_name[workload_name]
	c.resources.limits != want.limits
	msg := sprintf("service-resources: los limits de %s son %v (INF-U8-04)", [workload_name, want.limits])
}

deny contains msg if {
	is_workload
	c := pod.containers[0]
	want := resources_by_name[workload_name]
	object.get(c.resources, ["requests", "cpu"], "") != want.cpu
	msg := sprintf("service-resources: el request de CPU de %s es %s (INF-U8-04)", [workload_name, want.cpu])
}

deny contains msg if {
	is_workload
	c := pod.containers[0]
	not object.get(c.resources, ["requests", "memory"], "") in memory_requests[workload_name]
	msg := sprintf("service-resources: el request de memoria de %s es uno de %v (INF-U8-04; kind, P-1)", [workload_name, memory_requests[workload_name]])
}

# regla: service-prestop
# INF-U8-06: `case-service` lleva `preStop.sleep` de 5 s; `case-worker` no lleva `preStop` (no recibe trafico de entrada).
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "case-service"
	object.get(pod.containers[0], ["lifecycle", "preStop", "sleep", "seconds"], 0) != 5
	msg := "service-prestop: case-service lleva lifecycle.preStop.sleep.seconds de 5 (INF-U8-06)"
}

deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name == "case-worker"
	pod.containers[0].lifecycle
	msg := "service-prestop: case-worker no lleva preStop (INF-U8-06)"
}

# regla: service-grace
# INF-U8-06: al menos 20 s en `case-service` y al menos 30 s en `case-worker` (el chart usa 40 s, P-4; `test_chart.py` la compara con `config.WORKER_TERMINATION_GRACE`).
min_grace := {"case-service": 20, "case-worker": 30}

deny contains msg if {
	is_app_deployment
	not "terminationGracePeriodSeconds" in object.keys(pod)
	msg := sprintf("service-grace: terminationGracePeriodSeconds esta declarado en %s (INF-U8-06)", [input.metadata.name])
}

deny contains msg if {
	is_app_deployment
	object.get(pod, "terminationGracePeriodSeconds", 30) < min_grace[input.metadata.name]
	msg := sprintf("service-grace: terminationGracePeriodSeconds de %s es de al menos %v (INF-U8-06)", [input.metadata.name, min_grace[input.metadata.name]])
}

# regla: service-probes
# INF-U8-04: readiness `/readyz` cada 5 s y liveness cada 10 s, las dos en 8081 (`metrics`); sin `startupProbe`. La liveness es `/healthz`: es la ruta que sirve
# `vectra_common.ops_server` (U0); INF-U8-04 la llama `/livez`.
deny contains msg if {
	is_deployment
	object.get(pod.containers[0], ["readinessProbe", "httpGet", "path"], "") != "/readyz"
	msg := "service-probes: la readiness es /readyz"
}

deny contains msg if {
	is_deployment
	object.get(pod.containers[0], ["livenessProbe", "httpGet", "path"], "") != "/healthz"
	msg := "service-probes: la liveness es /healthz (la ruta que sirve ops_server)"
}

deny contains msg if {
	is_deployment
	some probe in ["readinessProbe", "livenessProbe"]
	object.get(pod.containers[0], [probe, "httpGet", "port"], "") != "metrics"
	msg := sprintf("service-probes: %s apunta al puerto de operacion (metrics, 8081)", [probe])
}

deny contains msg if {
	is_deployment
	object.get(pod.containers[0], ["readinessProbe", "periodSeconds"], 0) != 5
	msg := "service-probes: readinessProbe cada 5 s (INF-U8-04)"
}

deny contains msg if {
	is_deployment
	object.get(pod.containers[0], ["livenessProbe", "periodSeconds"], 0) != 10
	msg := "service-probes: livenessProbe cada 10 s (INF-U8-04)"
}

deny contains msg if {
	is_deployment
	pod.containers[0].startupProbe
	msg := "service-probes: sin startupProbe (INF-U8-04)"
}

# regla: service-ports
expected_ports := {
	"case-service": {["http", 8080], ["metrics", 8081]},
	"case-worker": {["metrics", 8081]},
	"core-banking-mock": {["http", 8080], ["metrics", 8081]},
}

deny contains msg if {
	is_deployment
	ports := {[p.name, p.containerPort] | some p in pod.containers[0].ports}
	ports != expected_ports[input.metadata.name]
	msg := sprintf("service-ports: los puertos de %s son %v (el worker no abre 8080)", [input.metadata.name, expected_ports[input.metadata.name]])
}

# regla: service-command
# NFR-U8-10: una imagen y tres ordenes (P-U8-10).
commands := {
	"case-service": ["python", "-m", "vectra_case.app"],
	"case-worker": ["python", "-m", "vectra_case.worker"],
	"core-banking-mock": ["python", "-m", "core_banking_mock.app"],
	"case-migration": ["alembic", "-c", "/app/alembic.ini", "upgrade", "head"],
}

deny contains msg if {
	is_workload
	not is_rt5
	pod.containers[0].command != commands[workload_name]
	msg := sprintf("service-command: la orden de %s es %v (NFR-U8-10, P-U8-10)", [workload_name, commands[workload_name]])
}

# regla: service-sidecar
# P-U1-05: sidecar nativo de Linkerd, para que el proxy termine despues de la app (deployments y Jobs).
deny contains msg if {
	is_workload
	object.get(input.spec.template.metadata, ["annotations", "config.alpha.linkerd.io/proxy-enable-native-sidecar"], "") != "true"
	msg := sprintf("service-sidecar: el pod de %s lleva config.alpha.linkerd.io/proxy-enable-native-sidecar: \"true\"", [input.metadata.name])
}

# regla: service-identity
deny contains msg if {
	input.kind == "Deployment"
	input.metadata.name in app_deployments
	object.get(input.spec.template.spec.containers[0], "env", []) != []
	env_value(pod.containers[0], "VECTRA_CLIENT_ID") != input.metadata.name
	msg := sprintf("service-identity: VECTRA_CLIENT_ID es %s", [input.metadata.name])
}

# --- imagen y endurecimiento -----------------------------------------------------------------------------------------------------------------------

# regla: workload-image
# Por digest. `case-service`, `case-worker`, la migracion y el Job rt5-demo usan la imagen `case-management` (una imagen, tres ordenes); el mock, la suya.
image_name := "core-banking-mock" if input.metadata.name == "core-banking-mock"

image_name := "case-management" if {
	is_workload
	input.metadata.name != "core-banking-mock"
}

deny contains msg if {
	some c in all_containers
	parts := split(c.image, "@")
	not count(parts) == 2
	msg := sprintf("workload-image: la imagen %s va por digest", [c.image])
}

deny contains msg if {
	some c in all_containers
	parts := split(c.image, "@")
	count(parts) == 2
	not endswith(parts[0], concat("/", ["/vectra", image_name]))
	msg := sprintf("workload-image: el repositorio %s no es el de %s", [parts[0], image_name])
}

deny contains msg if {
	some c in all_containers
	parts := split(c.image, "@")
	count(parts) == 2
	not regex.match(`^sha256:[0-9a-f]{64}$`, parts[1])
	msg := sprintf("workload-image: el digest %s no es un sha256 completo", [parts[1]])
}

# regla: hardening
deny contains msg if {
	is_workload
	not pod.securityContext.runAsNonRoot == true
	msg := "hardening: el pod corre como no root"
}

deny contains msg if {
	is_workload
	not pod.securityContext.runAsUser == 65532
	msg := "hardening: runAsUser 65532, el de la imagen"
}

deny contains msg if {
	is_workload
	not pod.securityContext.runAsGroup == 65532
	msg := "hardening: runAsGroup 65532, el de la imagen"
}

deny contains msg if {
	is_workload
	not pod.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := "hardening: seccomp RuntimeDefault"
}

deny contains msg if {
	some c in all_containers
	c.securityContext != {"allowPrivilegeEscalation": false, "readOnlyRootFilesystem": true, "capabilities": {"drop": ["ALL"]}}
	msg := "hardening: el contenedor no escala privilegios, tiene el sistema de archivos de solo lectura y sin capacidades"
}

deny contains msg if {
	is_workload
	some v in object.get(pod, "volumes", [])
	v.hostPath
	msg := sprintf("hardening: el volumen %s es hostPath", [v.name])
}

deny contains msg if {
	is_workload
	some v in object.get(pod, "volumes", [])
	not v.emptyDir
	not v.secret
	not v.configMap
	msg := sprintf("hardening: el volumen %s no es un emptyDir, un Secret ni un ConfigMap", [v.name])
}

# regla: read-only-mounts
# La llave `private_key_jwt` y la CA se montan de solo lectura.
deny contains msg if {
	some c in all_containers
	some m in object.get(c, "volumeMounts", [])
	not m.readOnly == true
	msg := sprintf("read-only-mounts: el montaje %s (%s) va de solo lectura", [m.name, m.mountPath])
}

# --- recursos del chart ----------------------------------------------------------------------------------------------------------------------------

# regla: namespace
expected_namespace(kind, name) := mock_namespace if {
	name == "core-banking-mock"
	kind in {"Deployment", "Service", "PodDisruptionBudget", "ServiceAccount", "ServiceMonitor"}
}

expected_namespace(kind, name) := namespace if {
	not name == "core-banking-mock"
	kind in {"Deployment", "Service", "HorizontalPodAutoscaler", "PodDisruptionBudget", "ServiceAccount", "ExternalSecret", "ServiceMonitor", "Job", "PrometheusRule"}
}

deny contains msg if {
	want := expected_namespace(input.kind, input.metadata.name)
	input.metadata.namespace != want
	msg := sprintf("namespace: %s %s va en %s, no en %s (P-3: el mock en vectra-mock)", [input.kind, input.metadata.name, input.metadata.namespace, want])
}

# regla: service-account-doc
deny contains msg if {
	input.kind == "ServiceAccount"
	object.get(input, "secrets", []) != []
	msg := "service-account-doc: sin secretos en la cuenta de servicio"
}

deny contains msg if {
	input.kind == "ServiceAccount"
	object.get(input, "automountServiceAccountToken", true) != true
	msg := "service-account-doc: Linkerd necesita el token de la cuenta de servicio"
}

deny contains msg if {
	input.kind == "ServiceAccount"
	not input.metadata.name in {"case-service", "case-worker", "migration-case", "core-banking-mock"}
	msg := sprintf("service-account-doc: la cuenta %s no es de flows.yaml", [input.metadata.name])
}

# regla: service-doc
# Cada Service se llama como su Deployment; el worker expone SOLO 8081 (no abre 8080); el servicio y el mock, 8080 y 8081 (F17, F60).
service_ports := {"case-service": {8080, 8081}, "case-worker": {8081}, "core-banking-mock": {8080, 8081}}

deny contains msg if {
	input.kind == "Service"
	not input.metadata.name in deployments
	msg := sprintf("service-doc: el Service %s no es de U8", [input.metadata.name])
}

deny contains msg if {
	input.kind == "Service"
	input.metadata.name in deployments
	ports := {p.port | some p in input.spec.ports}
	ports != service_ports[input.metadata.name]
	msg := sprintf("service-doc: el Service %s expone %v", [input.metadata.name, service_ports[input.metadata.name]])
}

# regla: hpa-doc
# INF-U8-04: de 2 a 6 replicas por CPU al 70 %, con estabilizacion de 60 s hacia arriba y 300 s hacia abajo; solo los dos Deployment de vectra-app.
deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	not input.spec.scaleTargetRef.name in app_deployments
	msg := "hpa-doc: el HPA escala case-service o case-worker (el mock esta exento)"
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	input.spec.minReplicas != 2
	msg := sprintf("hpa-doc: minReplicas es 2, no %v", [input.spec.minReplicas])
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	input.spec.maxReplicas != 6
	msg := sprintf("hpa-doc: maxReplicas es 6, no %v", [input.spec.maxReplicas])
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	metrics := [m | some m in input.spec.metrics; m.type == "Resource"; m.resource.name == "cpu"; m.resource.target.type == "Utilization"; m.resource.target.averageUtilization == 70]
	count(metrics) != 1
	msg := "hpa-doc: una sola metrica, CPU al 70 % de utilizacion"
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	object.get(input.spec, ["behavior", "scaleUp", "stabilizationWindowSeconds"], -1) != 60
	msg := "hpa-doc: estabilizacion de 60 s hacia arriba"
}

deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	object.get(input.spec, ["behavior", "scaleDown", "stabilizationWindowSeconds"], -1) != 300
	msg := "hpa-doc: estabilizacion de 300 s hacia abajo"
}

# regla: pdb-doc
deny contains msg if {
	input.kind == "PodDisruptionBudget"
	not object.get(input.spec.selector.matchLabels, "app.kubernetes.io/name", "") in deployments
	msg := "pdb-doc: el PDB selecciona por app.kubernetes.io/name uno de los Deployment de U8"
}

deny contains msg if {
	input.kind == "PodDisruptionBudget"
	object.get(input.spec, "minAvailable", 0) != 1
	msg := "pdb-doc: minAvailable es 1"
}

deny contains msg if {
	input.kind == "PodDisruptionBudget"
	input.metadata.name in app_deployments
	object.get(input.spec.selector.matchLabels, "vectra.io/workload", "") != input.metadata.name
	msg := "pdb-doc: el PDB de case-service y case-worker selecciona tambien vectra.io/workload (el Job rt5-demo no lo cuenta)"
}

# regla: servicemonitor-doc
deny contains msg if {
	input.kind == "ServiceMonitor"
	not object.get(input.spec.selector.matchLabels, "app.kubernetes.io/name", "") in deployments
	msg := "servicemonitor-doc: selecciona el Service de uno de los Deployment de U8"
}

deny contains msg if {
	input.kind == "ServiceMonitor"
	some endpoint in input.spec.endpoints
	object.get(endpoint, "honorLabels", false) != true
	msg := "servicemonitor-doc: honorLabels: true (shared-infrastructure.md §1)"
}

deny contains msg if {
	input.kind == "ServiceMonitor"
	count(input.spec.endpoints) != 1
	msg := "servicemonitor-doc: un solo endpoint, el de metricas"
}

# regla: no-cronjob
# P-12: el CronJob `case-retention` no se rinde (su CLI es del Paso 16, diferido).
deny contains msg if {
	input.kind == "CronJob"
	msg := sprintf("no-cronjob: el CronJob %s no se rinde (P-12; Paso 16 diferido)", [input.metadata.name])
}

# regla: u1-owned
# INF-U8-03: el `Server`, las `HTTPRoute` y la `AuthorizationPolicy` del mock las genera U1 desde flows.yaml; el chart no crea ninguno.
deny contains msg if {
	input.kind in {"Server", "HTTPRoute", "AuthorizationPolicy", "MeshTLSAuthentication", "NetworkPolicy"}
	msg := sprintf("u1-owned: %s %s es de U1 (platform/network/generated), no del chart", [input.kind, input.metadata.name])
}

# --- migracion -------------------------------------------------------------------------------------------------------------------------------------

# regla: migration-job
deny contains msg if {
	is_migration
	object.get(input.metadata, ["annotations", "argocd.argoproj.io/hook"], "") != "Sync"
	msg := "migration-job: hook de sync de Argo CD (argocd.argoproj.io/hook: Sync; F44)"
}

deny contains msg if {
	is_migration
	object.get(pod, "serviceAccountName", "") != "migration-case"
	msg := "migration-job: la cuenta de servicio es migration-case (flows.yaml)"
}

deny contains msg if {
	is_migration
	object.get(input.spec.template.metadata.labels, "vectra.io/workload", "") != "migration-case"
	msg := "migration-job: el pod lleva vectra.io/workload: migration-case (flows.yaml, F44)"
}

deny contains msg if {
	is_migration
	not "backoffLimit" in object.keys(input.spec)
	msg := "migration-job: backoffLimit explicito"
}

deny contains msg if {
	is_migration
	not "activeDeadlineSeconds" in object.keys(input.spec)
	msg := "migration-job: activeDeadlineSeconds explicito"
}

deny contains msg if {
	is_migration
	object.get(input.spec.template.spec, "restartPolicy", "") != "Never"
	msg := "migration-job: restartPolicy Never"
}

deny contains msg if {
	is_migration
	some e in pod.containers[0].env
	e.name == "PGUSER"
	e.valueFrom.secretKeyRef.name != "pg-role-case-migrator"
	msg := "migration-job: el usuario sale de pg-role-case-migrator (case_migrator)"
}

# --- Job rt5-demo ----------------------------------------------------------------------------------------------------------------------------------

# regla: rt5-job
# INF-U8-03: corre como `case-service` (la cuenta y `app.kubernetes.io/name`, que es lo que admite la NetworkPolicy del mock) y NO lleva `vectra.io/workload: case-service`; sin
# la llave ni variables de la base; `backoffLimit: 0`, `restartPolicy: Never` y sin `ttlSecondsAfterFinished` (se poda al cambiar `probes.runId`).
deny contains msg if {
	is_rt5
	object.get(pod, "serviceAccountName", "") != "case-service"
	msg := "rt5-job: la cuenta de servicio es case-service (la que admite el mock)"
}

deny contains msg if {
	is_rt5
	object.get(input.spec.template.metadata.labels, "app.kubernetes.io/name", "") != "case-service"
	msg := "rt5-job: el pod lleva app.kubernetes.io/name: case-service (lo que admite la NetworkPolicy del mock)"
}

deny contains msg if {
	is_rt5
	"vectra.io/workload" in object.keys(input.spec.template.metadata.labels)
	msg := "rt5-job: el pod NO lleva vectra.io/workload (el Service de case-service le enviaria trafico)"
}

deny contains msg if {
	is_rt5
	input.spec.backoffLimit != 0
	msg := "rt5-job: backoffLimit 0"
}

deny contains msg if {
	is_rt5
	object.get(pod, "restartPolicy", "") != "Never"
	msg := "rt5-job: restartPolicy Never"
}

deny contains msg if {
	is_rt5
	"ttlSecondsAfterFinished" in object.keys(input.spec)
	msg := "rt5-job: sin ttlSecondsAfterFinished (un Job completado se poda al cambiar el runId)"
}

deny contains msg if {
	is_rt5
	count(object.get(pod, "volumes", [])) > 0
	msg := "rt5-job: sin volumenes (ni la llave de Keycloak ni la CA)"
}

deny contains msg if {
	is_rt5
	not regex.match(`^rt5-demo-[0-9]{8}-[0-9]{4}$`, input.metadata.name)
	msg := "rt5-job: el nombre es rt5-demo-<runId> con el formato AAAAMMDD-HHMM"
}

# --- PrometheusRule --------------------------------------------------------------------------------------------------------------------------------

# regla: prometheus-rule
# Paso 21: UNA alerta, `CoreWriteAttempt`, sin regla de grabacion ni `for`, SEV2, con `runbook_url`; la expresion es la de INF-U8-03 (las dos series, la resta con
# `offset 5m` y `or vector(0)`, el filtro de `route_name` y ningun `increase()` sobre la serie de Linkerd).
rules_of(r) := [x | some g in r.spec.groups; some x in g.rules]

deny contains msg if {
	input.kind == "PrometheusRule"
	rules := rules_of(input)
	not count(rules) == 1
	msg := sprintf("prometheus-rule: una sola regla (CoreWriteAttempt), no %d (las otras alertas son T2)", [count(rules)])
}

deny contains msg if {
	input.kind == "PrometheusRule"
	some r in rules_of(input)
	object.get(r, "alert", "") != "CoreWriteAttempt"
	msg := "prometheus-rule: la unica alerta es CoreWriteAttempt, sin reglas de grabacion"
}

deny contains msg if {
	input.kind == "PrometheusRule"
	some r in rules_of(input)
	"for" in object.keys(r)
	msg := "prometheus-rule: CoreWriteAttempt no lleva `for`"
}

deny contains msg if {
	input.kind == "PrometheusRule"
	some r in rules_of(input)
	object.get(r, ["labels", "severity"], "") != "SEV2"
	msg := "prometheus-rule: severity SEV2 (P-U8-06)"
}

deny contains msg if {
	input.kind == "PrometheusRule"
	some r in rules_of(input)
	object.get(r, ["annotations", "runbook_url"], "") != "case-management/observability/runbooks/core-write-attempt.md"
	msg := "prometheus-rule: runbook_url relativo a vectra-risk/ hacia core-write-attempt.md"
}

deny contains msg if {
	input.kind == "PrometheusRule"
	some r in rules_of(input)
	not contains(r.expr, "route_name=\"core-mock-catch-all\"")
	msg := "prometheus-rule: la serie de Linkerd se filtra por route_name=\"core-mock-catch-all\" (INF-U8-03)"
}

deny contains msg if {
	input.kind == "PrometheusRule"
	some r in rules_of(input)
	not contains(r.expr, "offset 5m")
	msg := "prometheus-rule: la resta de la serie de Linkerd usa offset 5m (INF-U8-03)"
}

deny contains msg if {
	input.kind == "PrometheusRule"
	some r in rules_of(input)
	not contains(r.expr, "or vector(0)")
	msg := "prometheus-rule: la serie que nace en 1 se resta con or vector(0) (INF-U8-03)"
}

deny contains msg if {
	input.kind == "PrometheusRule"
	some r in rules_of(input)
	regex.match(`increase\(\s*inbound_http_authz_deny_total`, r.expr)
	msg := "prometheus-rule: increase() sobre la serie de Linkerd nunca la ve nacer en 1 (INF-U8-03)"
}
