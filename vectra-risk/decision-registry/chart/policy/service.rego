# Reglas de conftest sobre el Deployment, el Job de migracion y el ServiceMonitor de U3 (Paso 13 y 15 acotados a la demo; INF-U3-03;
# NFR-U3-10, 11, 41; P-U3-01; F44, F60). Cada `# regla: x` tiene un caso que falla en decision-registry/tests/unit/test_chart.py, y cada
# mensaje empieza por `x:`. Lo que exige ver todos los documentos juntos esta en `set.rego`.
package main

import rego.v1

is_deployment if input.kind == "Deployment"

is_migration if {
	input.kind == "Job"
	input.metadata.name == "registry-migration"
}

# Un Job que no es el de migracion: los de reconstruccion, reset y la sonda x06 son de la Application aparte (diferida).
forbidden_job_prefixes := ["registry-aggregator-rebuild", "registry-aggregator-reset", "x06-probe"]

service_pod := input.spec.template.spec if is_deployment

service_container := service_pod.containers[0] if is_deployment

migration_pod := input.spec.template.spec if is_migration

migration_container := migration_pod.containers[0] if is_migration

env_of(container, name) := e if {
	some e in container.env
	e.name == name
}

# regla: forbidden-jobs
deny contains msg if {
	input.kind == "Job"
	some prefix in forbidden_job_prefixes
	startswith(input.metadata.name, prefix)
	msg := sprintf("forbidden-jobs: el Job %s es de decision-registry-rebuild (T5), no de este chart", [input.metadata.name])
}

# regla: service-shape
deny contains msg if {
	is_deployment
	input.metadata.name != "decision-registry-service"
	msg := sprintf("service-shape: el unico Deployment del chart es decision-registry-service, no %s", [input.metadata.name])
}

deny contains msg if {
	is_deployment
	input.metadata.namespace != namespace
	msg := sprintf("service-shape: el namespace es %s, no %s", [input.metadata.namespace, namespace])
}

deny contains msg if {
	is_deployment
	not count(service_pod.containers) == 1
	msg := "service-shape: el pod lleva un solo contenedor"
}

deny contains msg if {
	is_deployment
	object.get(input.spec, "replicas", 1) < 2
	msg := "service-shape: 2 replicas o mas (NFR-U3-10)"
}

deny contains msg if {
	is_deployment
	object.get(service_pod, "serviceAccountName", "") != "decision-registry-service"
	msg := "service-shape: la cuenta de servicio es decision-registry-service (flows.yaml)"
}

deny contains msg if {
	is_deployment
	object.get(input.spec.template.metadata.labels, "app.kubernetes.io/name", "") != "decision-registry-service"
	msg := "service-shape: el pod lleva app.kubernetes.io/name: decision-registry-service (flows.yaml, PDB)"
}

deny contains msg if {
	is_deployment
	object.get(input.metadata.labels, "vectra.io/criticality", "") != "critical"
	msg := "service-shape: vectra.io/criticality: critical (NFR-U3-10)"
}

# regla: service-priority
deny contains msg if {
	is_deployment
	object.get(service_pod, "priorityClassName", "") != "vectra-critical"
	msg := "service-priority: la prioridad del servicio es vectra-critical (INF-U3-03)"
}

# regla: service-spread
deny contains msg if {
	is_deployment
	not some_zone_spread
	msg := "service-spread: topologySpreadConstraints por topology.kubernetes.io/zone (NFR-U1-04)"
}

some_zone_spread if {
	some c in object.get(service_pod, "topologySpreadConstraints", [])
	c.topologyKey == "topology.kubernetes.io/zone"
}

# regla: service-resources
# INF-U3-03: 250m / 256 MiB de requests y 1 CPU / 512 MiB de limits.
deny contains msg if {
	is_deployment
	service_container.resources != {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}}
	msg := "service-resources: requests de 250m / 256Mi y limits de 1 CPU / 512Mi (INF-U3-03)"
}

# regla: service-ports
deny contains msg if {
	is_deployment
	ports := {p.containerPort | some p in service_container.ports}
	ports != {8080, 8081}
	msg := sprintf("service-ports: el contenedor expone 8080 (contrato) y 8081 (metricas y sondas), no %v", [ports])
}

# regla: service-probes
# La readiness es /readyz de 8081 (P-U3-01, NFR-U3-11): sin la replica sincrona el pod sale del balanceo.
deny contains msg if {
	is_deployment
	not service_container.readinessProbe.httpGet
	msg := "service-probes: el contenedor tiene readinessProbe (P-U3-01)"
}

deny contains msg if {
	is_deployment
	not service_container.livenessProbe.httpGet
	msg := "service-probes: el contenedor tiene livenessProbe"
}

deny contains msg if {
	is_deployment
	object.get(service_container.readinessProbe.httpGet, "path", "") != "/readyz"
	msg := "service-probes: readinessProbe en /readyz (P-U3-01)"
}

deny contains msg if {
	is_deployment
	service_container.readinessProbe.httpGet.port != "metrics"
	msg := "service-probes: la readiness va al puerto de metricas (8081)"
}

deny contains msg if {
	is_deployment
	object.get(service_container.livenessProbe.httpGet, "path", "") != "/healthz"
	msg := "service-probes: livenessProbe en /healthz"
}

# regla: service-dsn
# Tres DSN, sin credenciales en la URL: el usuario sale del Secret del rol y la clave de un `passfile`.
service_dsns := {
	"REGISTRY_RW_APP_DSN": {"host": "registry-db-rw", "secret": "pg-role-registry-app", "prefix": "REGISTRY_APP"},
	"REGISTRY_RW_HEALTH_DSN": {"host": "registry-db-rw", "secret": "pg-role-registry-health", "prefix": "REGISTRY_HEALTH"},
	"REGISTRY_RO_VERIFIER_DSN": {"host": "registry-db-ro", "secret": "pg-role-registry-verifier", "prefix": "REGISTRY_VERIFIER"},
}

deny contains msg if {
	is_deployment
	some name, _ in service_dsns
	names := {e.name | some e in service_container.env}
	not name in names
	msg := sprintf("service-dsn: falta %s", [name])
}

deny contains msg if {
	is_deployment
	some name, expected in service_dsns
	e := env_of(service_container, name)
	not startswith(e.value, sprintf("postgresql://%s.", [expected.host]))
	msg := sprintf("service-dsn: %s apunta a %s (INF-U3-04)", [name, expected.host])
}

deny contains msg if {
	is_deployment
	some name, _ in service_dsns
	e := env_of(service_container, name)
	contains(e.value, "@")
	msg := sprintf("service-dsn: %s lleva credenciales en la URL", [name])
}

deny contains msg if {
	is_deployment
	some name, _ in service_dsns
	e := env_of(service_container, name)
	regex.match(`(?i)(password|pass)=`, e.value)
	msg := sprintf("service-dsn: %s lleva una clave en la URL", [name])
}

deny contains msg if {
	is_deployment
	some name, _ in service_dsns
	e := env_of(service_container, name)
	not contains(e.value, "passfile=/run/pgpass/pgpass")
	msg := sprintf("service-dsn: %s lee la clave de un passfile", [name])
}

deny contains msg if {
	is_deployment
	some _, expected in service_dsns
	some suffix in ["USER", "PASSWORD"]
	e := env_of(service_container, sprintf("%s_%s", [expected.prefix, suffix]))
	not e.valueFrom.secretKeyRef.name == expected.secret
	msg := sprintf("service-dsn: %s_%s sale del Secret %s por secretKeyRef", [expected.prefix, suffix, expected.secret])
}

deny contains msg if {
	is_deployment
	some _, expected in service_dsns
	some suffix in ["USER", "PASSWORD"]
	names := {e.name | some e in service_container.env}
	not sprintf("%s_%s", [expected.prefix, suffix]) in names
	msg := sprintf("service-dsn: falta %s_%s (secretKeyRef de %s)", [expected.prefix, suffix, expected.secret])
}

# regla: service-checkpoint-keys
# Las llaves publicas de checkpoints llegan por configuracion (el servicio no tiene acceso a la boveda, P-U3-08).
deny contains msg if {
	is_deployment
	e := env_of(service_container, "REGISTRY_CHECKPOINT_PUBLIC_KEYS")
	not e.valueFrom.configMapKeyRef.name == "decision-registry-checkpoint"
	msg := "service-checkpoint-keys: REGISTRY_CHECKPOINT_PUBLIC_KEYS sale del ConfigMap decision-registry-checkpoint"
}

deny contains msg if {
	is_deployment
	names := {e.name | some e in service_container.env}
	not "REGISTRY_CHECKPOINT_PUBLIC_KEYS" in names
	msg := "service-checkpoint-keys: falta REGISTRY_CHECKPOINT_PUBLIC_KEYS"
}

# regla: service-oidc
# Variables de U0 (F50): sin el emisor, la URL de las llaves y la CA, `create_app` no arranca.
deny contains msg if {
	is_deployment
	names := {e.name | some e in service_container.env}
	missing := {"VECTRA_OIDC_ISSUER", "VECTRA_JWKS_URL", "VECTRA_CA_BUNDLE"} - names
	count(missing) > 0
	msg := sprintf("service-oidc: faltan %v (variables de U0, F50)", [missing])
}

deny contains msg if {
	is_deployment
	e := env_of(service_container, "VECTRA_JWKS_URL")
	not startswith(e.value, "https://")
	msg := "service-oidc: la URL de las llaves de Keycloak va por https (F50)"
}

# regla: workload-image
# El Deployment y el Job de migracion usan la imagen de decision-registry, por digest.
deny contains msg if {
	input.kind in {"Deployment", "Job"}
	pod := input.spec.template.spec
	some c in pod.containers
	parts := split(c.image, "@")
	not count(parts) == 2
	msg := sprintf("workload-image: la imagen %s va por digest", [c.image])
}

deny contains msg if {
	input.kind in {"Deployment", "Job"}
	some c in input.spec.template.spec.containers
	parts := split(c.image, "@")
	count(parts) == 2
	not parts[0] in image_repositories
	msg := sprintf("workload-image: el repositorio %s no es el de decision-registry", [parts[0]])
}

deny contains msg if {
	input.kind in {"Deployment", "Job"}
	some c in input.spec.template.spec.containers
	parts := split(c.image, "@")
	count(parts) == 2
	not regex.match(`^sha256:[0-9a-f]{64}$`, parts[1])
	msg := sprintf("workload-image: el digest %s no es un sha256 completo", [parts[1]])
}

# regla: workload-hardening
deny contains msg if {
	input.kind in {"Deployment", "Job"}
	pod := input.spec.template.spec
	not pod.securityContext.runAsNonRoot == true
	msg := "workload-hardening: el pod corre como no root"
}

deny contains msg if {
	input.kind in {"Deployment", "Job"}
	pod := input.spec.template.spec
	not pod.securityContext.runAsUser == 65532
	msg := "workload-hardening: runAsUser 65532, el de la imagen"
}

deny contains msg if {
	input.kind in {"Deployment", "Job"}
	pod := input.spec.template.spec
	not pod.securityContext.seccompProfile.type == "RuntimeDefault"
	msg := "workload-hardening: seccomp RuntimeDefault"
}

deny contains msg if {
	input.kind in {"Deployment", "Job"}
	some c in input.spec.template.spec.containers
	c.securityContext != {"allowPrivilegeEscalation": false, "readOnlyRootFilesystem": true, "capabilities": {"drop": ["ALL"]}}
	msg := "workload-hardening: el contenedor no escala privilegios, tiene el sistema de archivos de solo lectura y sin capacidades"
}

deny contains msg if {
	input.kind in {"Deployment", "Job"}
	some v in object.get(input.spec.template.spec, "volumes", [])
	not v.emptyDir
	not keycloak_ca(v)
	msg := sprintf("workload-hardening: el volumen %s no es un emptyDir (sin hostPath ni Secret montado; solo el ConfigMap de la CA de Keycloak)", [v.name])
}

keycloak_ca(v) if {
	v.name == "keycloak-ca"
	v.configMap
}

# regla: migration-hook
# El Job de migracion es un hook de sync de Argo CD que se reemplaza en cada sync (P-U1-12; BR-U3-17).
deny contains msg if {
	is_migration
	object.get(input.metadata, ["annotations", "argocd.argoproj.io/hook"], "") != "Sync"
	msg := "migration-hook: el Job de migracion es un hook de sync de Argo CD (argocd.argoproj.io/hook: Sync)"
}

deny contains msg if {
	is_migration
	object.get(input.metadata, ["annotations", "argocd.argoproj.io/hook-delete-policy"], "") != "BeforeHookCreation"
	msg := "migration-hook: hook-delete-policy es BeforeHookCreation"
}

# regla: migration-shape
deny contains msg if {
	is_migration
	object.get(migration_pod, "serviceAccountName", "") != "migration-registry"
	msg := "migration-shape: la cuenta de servicio es migration-registry (F44)"
}

deny contains msg if {
	is_migration
	object.get(input.spec.template.metadata.labels, "vectra.io/workload", "") != "migration-registry"
	msg := "migration-shape: el pod lleva vectra.io/workload: migration-registry (F44)"
}

deny contains msg if {
	is_migration
	object.get(input.spec, "activeDeadlineSeconds", "ausente") != 600
	msg := "migration-shape: activeDeadlineSeconds es 600 (INF-U3-03)"
}

deny contains msg if {
	is_migration
	object.get(migration_pod, "priorityClassName", "") != "vectra-normal"
	msg := "migration-shape: la prioridad del Job de migracion es vectra-normal (INF-U3-03)"
}

deny contains msg if {
	is_migration
	object.get(object.get(input.spec.template, "metadata", {}), ["annotations", "config.alpha.linkerd.io/proxy-enable-native-sidecar"], "") != "true"
	msg := "migration-shape: el Job de migracion con el sidecar nativo de Linkerd (P-U1-05)"
}

deny contains msg if {
	is_migration
	migration_pod.restartPolicy != "Never"
	msg := "migration-shape: restartPolicy es Never"
}

# regla: migration-command
deny contains msg if {
	is_migration
	migration_container.command != ["alembic", "-c", "/app/alembic.ini", "upgrade", "head"]
	msg := "migration-command: el Job ejecuta alembic -c /app/alembic.ini upgrade head"
}

# regla: migration-credentials
# `registry_migrator` por el Secret de U1 (F44); nada literal ni en la URL.
deny contains msg if {
	is_migration
	some name in ["PGUSER", "PGPASSWORD"]
	e := env_of(migration_container, name)
	not e.valueFrom.secretKeyRef.name == "pg-role-registry-migrator"
	msg := sprintf("migration-credentials: %s sale del Secret pg-role-registry-migrator por secretKeyRef", [name])
}

deny contains msg if {
	is_migration
	names := {e.name | some e in migration_container.env}
	missing := {"PGUSER", "PGPASSWORD", "REGISTRY_DATABASE_URL", "REGISTRY_CHECKPOINT_KEY_FINGERPRINT"} - names
	count(missing) > 0
	msg := sprintf("migration-credentials: faltan %v", [missing])
}

deny contains msg if {
	is_migration
	e := env_of(migration_container, "REGISTRY_DATABASE_URL")
	contains(e.value, "@")
	msg := "migration-credentials: REGISTRY_DATABASE_URL lleva credenciales en la URL"
}

deny contains msg if {
	is_migration
	e := env_of(migration_container, "REGISTRY_DATABASE_URL")
	not startswith(e.value, "postgresql://registry-db-rw.")
	msg := "migration-credentials: la migracion va contra registry-db-rw (F44)"
}

# regla: migration-resources
deny contains msg if {
	is_migration
	migration_container.resources != {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}
	msg := "migration-resources: requests de 100m / 128Mi y limits de 500m / 256Mi (INF-U3-03)"
}

# regla: servicemonitor-doc
deny contains msg if {
	input.kind == "ServiceMonitor"
	input.metadata.namespace != namespace
	msg := sprintf("servicemonitor-doc: el namespace es %s", [namespace])
}

deny contains msg if {
	input.kind == "ServiceMonitor"
	object.get(input.spec.selector.matchLabels, "app.kubernetes.io/name", "") != "decision-registry-service"
	msg := "servicemonitor-doc: selecciona el Service decision-registry-service"
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

# regla: hpa-doc
# NFR-U3-10, INF-U3-03: de 2 a 6 replicas por CPU al 70 %.
deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	input.spec.scaleTargetRef.name != "decision-registry-service"
	msg := "hpa-doc: el HPA escala decision-registry-service"
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

# regla: pdb-doc
deny contains msg if {
	input.kind == "PodDisruptionBudget"
	object.get(input.spec.selector.matchLabels, "app.kubernetes.io/name", "") != "decision-registry-service"
	msg := "pdb-doc: el PDB selecciona por app.kubernetes.io/name: decision-registry-service"
}

deny contains msg if {
	input.kind == "PodDisruptionBudget"
	object.get(input.spec, "minAvailable", 0) < 1
	msg := "pdb-doc: minAvailable de al menos 1"
}

# regla: checkpoint-config
deny contains msg if {
	input.kind == "ConfigMap"
	some key in ["REGISTRY_CHECKPOINT_PUBLIC_KEYS", "REGISTRY_CHECKPOINT_KEY_FINGERPRINT"]
	object.get(input.data, key, "") == ""
	msg := sprintf("checkpoint-config: %s no puede estar vacio", [key])
}
