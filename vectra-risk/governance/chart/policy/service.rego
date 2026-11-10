# Reglas de conftest sobre el Deployment, el Job de migracion, el ServiceMonitor, el HPA, el PDB y el RBAC de U4 (Paso 16 acotado a la demo;
# INF-U4-01; NFR-U4-03, 25; F41, F44, F47, F60). Cada `# regla: x` tiene un caso que falla en governance/tests/unit/test_chart.py, y cada
# mensaje empieza por `x:`. Lo que exige ver todos los documentos juntos esta en `set.rego`.
package main

import rego.v1

namespace := "vectra-app"

image_repositories := {"registro.banco.internal/vectra/governance", "kind-registry:5000/vectra/governance"}

is_deployment if input.kind == "Deployment"

is_migration if {
	input.kind == "Job"
	input.metadata.name == "governance-migration"
}



service_pod := input.spec.template.spec if is_deployment

service_container := service_pod.containers[0] if is_deployment

migration_pod := input.spec.template.spec if is_migration

migration_container := migration_pod.containers[0] if is_migration

env_of(container, name) := e if {
	some e in container.env
	e.name == name
}

# regla: no-model-archive
# El CronJob `model-archive` esta diferido (T5; Paso 15): ningun CronJob ni Job de archivo en el render.
deny contains msg if {
	input.kind == "CronJob"
	msg := sprintf("no-model-archive: el CronJob %s esta diferido (model-archive, T5)", [input.metadata.name])
}

deny contains msg if {
	input.kind == "Job"
	contains(input.metadata.name, "archive")
	msg := sprintf("no-model-archive: el Job %s es de model-archive (T5)", [input.metadata.name])
}

# regla: service-shape
deny contains msg if {
	is_deployment
	input.metadata.name != "governance-service"
	msg := sprintf("service-shape: el unico Deployment del chart es governance-service, no %s", [input.metadata.name])
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
	msg := "service-shape: 2 replicas o mas (NFR-U4-03)"
}

deny contains msg if {
	is_deployment
	object.get(service_pod, "serviceAccountName", "") != "governance-service"
	msg := "service-shape: la cuenta de servicio es governance-service (flows.yaml)"
}

deny contains msg if {
	is_deployment
	object.get(input.spec.template.metadata.labels, "app.kubernetes.io/name", "") != "governance-service"
	msg := "service-shape: el pod lleva app.kubernetes.io/name: governance-service (flows.yaml, PDB)"
}

deny contains msg if {
	is_deployment
	object.get(input.metadata.labels, "vectra.io/criticality", "") != "high"
	msg := "service-shape: vectra.io/criticality: high (NFR-U4-03)"
}

# regla: service-priority
deny contains msg if {
	is_deployment
	object.get(service_pod, "priorityClassName", "") != "vectra-high"
	msg := "service-priority: la prioridad del servicio es vectra-high (INF-U4-01)"
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
# INF-U4-01: 250m / 256 MiB de requests y 1 CPU / 512 MiB de limits.
deny contains msg if {
	is_deployment
	service_container.resources != {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}}
	msg := "service-resources: requests de 250m / 256Mi y limits de 1 CPU / 512Mi (INF-U4-01)"
}

# regla: service-ports
deny contains msg if {
	is_deployment
	ports := {p.containerPort | some p in service_container.ports}
	ports != {8080, 8081}
	msg := sprintf("service-ports: el contenedor expone 8080 (contrato) y 8081 (metricas y sondas), no %v", [ports])
}

# regla: service-probes
# La readiness es /readyz de 8081 (NFR-U4-03, NFR-U4-03): sin la replica sincrona el pod sale del balanceo.
deny contains msg if {
	is_deployment
	not service_container.readinessProbe.httpGet
	msg := "service-probes: el contenedor tiene readinessProbe (NFR-U4-03)"
}

deny contains msg if {
	is_deployment
	not service_container.livenessProbe.httpGet
	msg := "service-probes: el contenedor tiene livenessProbe"
}

deny contains msg if {
	is_deployment
	object.get(service_container.readinessProbe.httpGet, "path", "") != "/readyz"
	msg := "service-probes: readinessProbe en /readyz (NFR-U4-03)"
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
# Un solo rol (`gov_app`), sin credenciales en la URL: libpq lee PGUSER y PGPASSWORD del Secret `pg-role-gov-app` de U1.
deny contains msg if {
	is_deployment
	names := {e.name | some e in service_container.env}
	missing := {"GOVERNANCE_DATABASE_DSN", "PGUSER", "PGPASSWORD"} - names
	count(missing) > 0
	msg := sprintf("service-dsn: faltan %v", [missing])
}

deny contains msg if {
	is_deployment
	e := env_of(service_container, "GOVERNANCE_DATABASE_DSN")
	not startswith(e.value, "postgresql://governance-db-rw.")
	msg := "service-dsn: el servicio escribe en governance-db-rw (F41)"
}

deny contains msg if {
	is_deployment
	e := env_of(service_container, "GOVERNANCE_DATABASE_DSN")
	contains(e.value, "@")
	msg := "service-dsn: GOVERNANCE_DATABASE_DSN lleva credenciales en la URL"
}

deny contains msg if {
	is_deployment
	e := env_of(service_container, "GOVERNANCE_DATABASE_DSN")
	regex.match(`(?i)(password|pass|passfile)=`, e.value)
	msg := "service-dsn: GOVERNANCE_DATABASE_DSN lleva una clave en la URL"
}

deny contains msg if {
	is_deployment
	some name in ["PGUSER", "PGPASSWORD"]
	e := env_of(service_container, name)
	not e.valueFrom.secretKeyRef.name == "pg-role-gov-app"
	msg := sprintf("service-dsn: %s sale del Secret pg-role-gov-app por secretKeyRef", [name])
}

# regla: service-model-store
# F47: lectura del model-store con `minio-governance` (`governance-readonly`), por secretKeyRef; el chart no trae claves.
deny contains msg if {
	is_deployment
	some name in ["GOVERNANCE_S3_ACCESS_KEY", "GOVERNANCE_S3_SECRET_KEY"]
	e := env_of(service_container, name)
	not e.valueFrom.secretKeyRef.name == "minio-governance"
	msg := sprintf("service-model-store: %s sale del Secret minio-governance por secretKeyRef (F47)", [name])
}

deny contains msg if {
	is_deployment
	names := {e.name | some e in service_container.env}
	missing := {"GOVERNANCE_S3_ENDPOINT", "GOVERNANCE_S3_ACCESS_KEY", "GOVERNANCE_S3_SECRET_KEY"} - names
	count(missing) > 0
	msg := sprintf("service-model-store: faltan %v (F47)", [missing])
}

# regla: service-validation-config
# Candidatas de U04-T04 y U04-T05: `callback_url`, el endpoint S3 y la URL del token del Job vienen del chart, no del codigo.
deny contains msg if {
	is_deployment
	names := {e.name | some e in service_container.env}
	missing := {"GOVERNANCE_VALIDATION_IMAGE", "GOVERNANCE_VALIDATION_DATASET", "GOVERNANCE_CALLBACK_URL", "GOVERNANCE_JOB_S3_ENDPOINT", "GOVERNANCE_JOB_TOKEN_URL"} - names
	count(missing) > 0
	msg := sprintf("service-validation-config: faltan %v", [missing])
}

deny contains msg if {
	is_deployment
	e := env_of(service_container, "GOVERNANCE_VALIDATION_IMAGE")
	not regex.match(`@sha256:[0-9a-f]{64}$`, e.value)
	msg := "service-validation-config: la imagen del model-validation-job va por digest"
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
# El Deployment y el Job de migracion usan la imagen de governance, por digest.
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
	msg := sprintf("workload-image: el repositorio %s no es el de governance", [parts[0]])
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
# El Job de migracion es un hook de sync de Argo CD que se reemplaza en cada sync (P-U1-12; INF-U4-01).
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
	object.get(migration_pod, "serviceAccountName", "") != "migration-governance"
	msg := "migration-shape: la cuenta de servicio es migration-governance (F44)"
}

deny contains msg if {
	is_migration
	object.get(input.spec.template.metadata.labels, "vectra.io/workload", "") != "migration-governance"
	msg := "migration-shape: el pod lleva vectra.io/workload: migration-governance (F44)"
}

deny contains msg if {
	is_migration
	object.get(input.spec, "activeDeadlineSeconds", "ausente") != 600
	msg := "migration-shape: activeDeadlineSeconds es 600 (INF-U4-01)"
}

deny contains msg if {
	is_migration
	object.get(migration_pod, "priorityClassName", "") != "vectra-normal"
	msg := "migration-shape: la prioridad del Job de migracion es vectra-normal (INF-U4-01)"
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
# `gov_migrator` por el Secret de U1 (F44); nada literal ni en la URL.
deny contains msg if {
	is_migration
	some name in ["PGUSER", "PGPASSWORD"]
	e := env_of(migration_container, name)
	not e.valueFrom.secretKeyRef.name == "pg-role-gov-migrator"
	msg := sprintf("migration-credentials: %s sale del Secret pg-role-gov-migrator por secretKeyRef", [name])
}

deny contains msg if {
	is_migration
	names := {e.name | some e in migration_container.env}
	missing := {"PGUSER", "PGPASSWORD", "GOVERNANCE_DATABASE_URL"} - names
	count(missing) > 0
	msg := sprintf("migration-credentials: faltan %v", [missing])
}

deny contains msg if {
	is_migration
	e := env_of(migration_container, "GOVERNANCE_DATABASE_URL")
	contains(e.value, "@")
	msg := "migration-credentials: GOVERNANCE_DATABASE_URL lleva credenciales en la URL"
}

deny contains msg if {
	is_migration
	e := env_of(migration_container, "GOVERNANCE_DATABASE_URL")
	not startswith(e.value, "postgresql://governance-db-rw.")
	msg := "migration-credentials: la migracion va contra governance-db-rw (F44)"
}

# regla: migration-resources
deny contains msg if {
	is_migration
	migration_container.resources != {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}
	msg := "migration-resources: requests de 100m / 128Mi y limits de 500m / 256Mi (INF-U4-01)"
}

# regla: servicemonitor-doc
deny contains msg if {
	input.kind == "ServiceMonitor"
	input.metadata.namespace != namespace
	msg := sprintf("servicemonitor-doc: el namespace es %s", [namespace])
}

deny contains msg if {
	input.kind == "ServiceMonitor"
	object.get(input.spec.selector.matchLabels, "app.kubernetes.io/name", "") != "governance-service"
	msg := "servicemonitor-doc: selecciona el Service governance-service"
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
# NFR-U4-03, INF-U4-01: de 2 a 6 replicas por CPU al 70 %.
deny contains msg if {
	input.kind == "HorizontalPodAutoscaler"
	input.spec.scaleTargetRef.name != "governance-service"
	msg := "hpa-doc: el HPA escala governance-service"
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
	object.get(input.spec.selector.matchLabels, "app.kubernetes.io/name", "") != "governance-service"
	msg := "pdb-doc: el PDB selecciona por app.kubernetes.io/name: governance-service"
}

deny contains msg if {
	input.kind == "PodDisruptionBudget"
	object.get(input.spec, "minAvailable", 0) < 1
	msg := "pdb-doc: minAvailable de al menos 1"
}

# regla: rbac-k01
# K01 (P-U4-03, NFR-U4-25): el Role de vectra-staging solo deja crear y leer Jobs; el RoleBinding es de governance-service.
deny contains msg if {
	input.kind == "Role"
	input.metadata.namespace != "vectra-staging"
	msg := sprintf("rbac-k01: el Role va en vectra-staging, no en %s", [input.metadata.namespace])
}

deny contains msg if {
	input.kind == "Role"
	count(input.rules) != 1
	msg := "rbac-k01: el Role tiene una sola regla (jobs)"
}

deny contains msg if {
	input.kind == "Role"
	some rule in input.rules
	rule.apiGroups != ["batch"]
	msg := "rbac-k01: solo el grupo batch"
}

deny contains msg if {
	input.kind == "Role"
	some rule in input.rules
	rule.resources != ["jobs"]
	msg := "rbac-k01: solo el recurso jobs"
}

deny contains msg if {
	input.kind == "Role"
	some rule in input.rules
	{v | some v in rule.verbs} != {"create", "get"}
	msg := "rbac-k01: solo los verbos create y get"
}

deny contains msg if {
	input.kind in {"ClusterRole", "ClusterRoleBinding"}
	msg := sprintf("rbac-k01: %s no va en el chart (K01 es un Role de vectra-staging)", [input.kind])
}

deny contains msg if {
	input.kind == "RoleBinding"
	input.metadata.namespace != "vectra-staging"
	msg := "rbac-k01: el RoleBinding va en vectra-staging"
}

deny contains msg if {
	input.kind == "RoleBinding"
	input.subjects != [{"kind": "ServiceAccount", "name": "governance-service", "namespace": "vectra-app"}]
	msg := "rbac-k01: el unico sujeto es la ServiceAccount governance-service de vectra-app"
}

deny contains msg if {
	input.kind == "RoleBinding"
	input.roleRef.kind != "Role"
	msg := "rbac-k01: el RoleBinding apunta a un Role, no a un ClusterRole"
}

# regla: validation-job-objects
# U04-T05: la ServiceAccount del model-validation-job y su ExternalSecret viven en vectra-staging; ninguna otra ServiceAccount de ese namespace.
deny contains msg if {
	input.kind == "ServiceAccount"
	input.metadata.namespace == "vectra-staging"
	input.metadata.name != "model-validation-job"
	msg := sprintf("validation-job-objects: la ServiceAccount %s no va en vectra-staging", [input.metadata.name])
}

deny contains msg if {
	input.kind == "ServiceAccount"
	input.metadata.name == "model-validation-job"
	object.get(input, "automountServiceAccountToken", true) != false
	msg := "validation-job-objects: model-validation-job no monta token de Kubernetes (su identidad es el private_key_jwt, F50)"
}

deny contains msg if {
	input.kind == "ServiceAccount"
	input.metadata.namespace == "vectra-app"
	object.get(input, "secrets", []) != []
	msg := "validation-job-objects: las ServiceAccounts no listan Secrets"
}
