#!/usr/bin/env bash
# Crea, consulta o destruye el Cluster efimero del simulacro (K12). Lo usa drill.py dentro del CronJob.
# Uso: restore-cluster.sh create <nombre> <origen> [tamano] | destroy <nombre> | lsn <nombre>
#
# Entorno (cronjob.yaml y configmap-<entorno>.yaml):
#   RESTORE_IMAGE        imagen de PostgreSQL; el mismo digest del chart de datos.
#   BACKUP_DESTINATION   p. ej. s3://vectra-backups.
#   BACKUP_ENDPOINT      S3 del banco, o MinIO en kind.
#   RESTORE_STORAGE_SIZE opcional: tamano para todos los origenes (kind). Por defecto, el de datos del origen (INF-U1-02).
set -euo pipefail
action="$1"; name="$2"; namespace=vectra-restore-drill

case "$action" in
  destroy)
    kubectl delete clusters.postgresql.cnpg.io "$name" -n "$namespace" --ignore-not-found --wait=true
    ;;
  lsn)
    # Imprime un entero. El CR no publica el LSN, asi que se pregunta a PostgreSQL con `kubectl exec` (K12: pods/exec
    # limitado a las instancias del simulacro). Tras promover, CloudNativePG reinicia la instancia y
    # pg_last_wal_replay_lsn() puede ser NULL; entonces vale el LSN actual, justo despues de lo reproducido.
    primary="$(kubectl get clusters.postgresql.cnpg.io "$name" -n "$namespace" -o 'jsonpath={.status.currentPrimary}')"
    kubectl exec "$primary" -n "$namespace" -c postgres -- psql -d postgres -Atc \
      "SELECT (COALESCE(pg_last_wal_replay_lsn(), pg_current_wal_lsn()) - '0/0')::bigint"
    ;;
  create)
    source="$3"
    size="${4:-${RESTORE_STORAGE_SIZE:-}}"
    if [ -z "$size" ]; then
      case "$source" in
        registry-db) size=100Gi ;;
        case-db) size=50Gi ;;
        *) echo "Origen sin tamano conocido: $source" >&2; exit 2 ;;
      esac
    fi
    kubectl create -f - <<YAML
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: $name
  namespace: $namespace
  labels: { vectra.io/criticality: medium }
spec:
  imageName: ${RESTORE_IMAGE:?falta RESTORE_IMAGE}
  instances: 1
  priorityClassName: vectra-low
  inheritedMetadata:
    labels:
      app.kubernetes.io/name: restore-cluster
      vectra.io/criticality: medium
    annotations:
      config.linkerd.io/skip-inbound-ports: "8000"
  storage: { size: $size }
  resources:
    requests: { cpu: 500m, memory: 1Gi }
    limits: { cpu: "1", memory: 2Gi }
  bootstrap:
    recovery: { source: $source }
  externalClusters:
    - name: $source
      barmanObjectStore:
        destinationPath: "${BACKUP_DESTINATION:?falta BACKUP_DESTINATION}/$source"
        endpointURL: "${BACKUP_ENDPOINT:?falta BACKUP_ENDPOINT}"
        s3Credentials:
          accessKeyId: { name: restore-drill-readonly-credentials, key: ACCESS_KEY_ID }
          secretAccessKey: { name: restore-drill-readonly-credentials, key: SECRET_ACCESS_KEY }
YAML
    kubectl wait clusters.postgresql.cnpg.io "$name" -n "$namespace" --for=condition=Ready --timeout=2h
    ;;
  *)
    echo "Accion desconocida: $action" >&2
    exit 2
    ;;
esac
