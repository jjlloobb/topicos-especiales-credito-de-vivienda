{{- /* Repositorio de una imagen (`images.<clave>`). Argo CD pasa `imageRegistry` de vectra-risk-gitops/envs/<env>/values.yaml: `kind-registry:5000` en kind y
`registro.banco.internal/vectra` en staging y prod. Sin el (render local) vale el `repository` del values. `.name` es el nombre de la imagen. */ -}}
{{- define "case-management.image" -}}
{{- $root := index . 0 -}}
{{- $key := index . 1 -}}
{{- $name := index . 2 -}}
{{- $image := index $root.Values.images $key -}}
{{- $digest := required (printf "images.%s.digest es obligatorio: sin digest no se renderiza" $key) $image.digest -}}
{{- $repository := "" -}}
{{- if $root.Values.imageRegistry -}}
{{- if hasSuffix "/vectra" $root.Values.imageRegistry -}}{{- $repository = printf "%s/%s" $root.Values.imageRegistry $name -}}{{- else -}}{{- $repository = printf "%s/vectra/%s" $root.Values.imageRegistry $name -}}{{- end -}}
{{- else -}}
{{- $repository = required (printf "images.%s.repository es obligatorio" $key) $image.repository -}}
{{- end -}}
{{- printf "%s@%s" $repository $digest -}}
{{- end -}}

{{- /* DSN de `case-db` sin credenciales (INF-U8-01): libpq lee PGUSER y PGPASSWORD del Secret de U1. Con verify-full o verify-ca agrega la CA interna (P-6; NFR-U8-40:
TLS verificado hacia la base). */ -}}
{{- define "case-management.dsn" -}}
{{- $db := .Values.database -}}
{{- $host := required "database.host es obligatorio" $db.host -}}
{{- $name := required "database.name es obligatorio" $db.name -}}
{{- $mode := required "database.sslmode es obligatorio" $db.sslmode -}}
{{- if has $mode (list "verify-full" "verify-ca") -}}
{{- printf "postgresql://%s/%s?sslmode=%s&sslrootcert=%s/ca.crt" $host $name $mode .Values.internalCA.mountPath -}}
{{- else -}}
{{- printf "postgresql://%s/%s?sslmode=%s" $host $name $mode -}}
{{- end -}}
{{- end -}}

{{- /* PGUSER y PGPASSWORD del Secret de U1 de un rol (`pg-role-case-*`, claves `username` y `password`). */ -}}
{{- define "case-management.pg-env" -}}
- name: PGUSER
  valueFrom: { secretKeyRef: { name: {{ . | quote }}, key: username } }
- name: PGPASSWORD
  valueFrom: { secretKeyRef: { name: {{ . | quote }}, key: password } }
{{- end -}}

{{- /* El pod no corre como root con el mismo usuario que la imagen (65532). */ -}}
{{- define "case-management.pod-security" -}}
runAsNonRoot: true
runAsUser: 65532
runAsGroup: 65532
seccompProfile: { type: RuntimeDefault }
{{- end -}}

{{- /* Volumen de la CA interna (ConfigMap `vectra-internal-ca`, clave ca.crt). */ -}}
{{- define "case-management.ca-volume" -}}
- name: internal-ca
  configMap: { name: {{ .Values.internalCA.configMap | quote }}, items: [{ key: ca.crt, path: ca.crt }] }
{{- end -}}

{{- define "case-management.ca-mount" -}}
- { name: internal-ca, mountPath: {{ .Values.internalCA.mountPath | quote }}, readOnly: true }
{{- end -}}

{{- /* Identidad ante Keycloak de un cliente (F50): el token de servicio se firma con la llave montada y se pide a `VECTRA_TOKEN_URL`. */ -}}
{{- define "case-management.identity-env" -}}
{{- $root := index . 0 -}}
{{- $svc := index . 1 -}}
- { name: VECTRA_CLIENT_ID, value: {{ $svc.clientId | quote }} }
- { name: VECTRA_TOKEN_URL, value: {{ required "keycloak.tokenUrl es obligatorio" $root.Values.keycloak.tokenUrl | quote }} }
- { name: VECTRA_CLIENT_KEY_PATH, value: {{ printf "%s/private-key" $root.Values.identity.mountPath | quote }} }
- { name: VECTRA_CA_BUNDLE, value: {{ printf "%s/ca.crt" $root.Values.internalCA.mountPath | quote }} }
{{- end -}}

{{- /* HPA y PDB de un Deployment de `vectra-app` (INF-U8-04): de 2 a 6 por CPU al 70 %, 60 s hacia arriba y 300 s hacia abajo. */ -}}
{{- define "case-management.hpa-pdb" -}}
{{- $root := index . 0 -}}
{{- $svc := index . 1 -}}
{{- $common := $root.Values.common }}
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ $svc.name }}
  namespace: {{ $root.Values.namespace }}
  labels:
    app.kubernetes.io/name: {{ $svc.name }}
    app.kubernetes.io/part-of: case-management
  annotations:
    argocd.argoproj.io/sync-wave: "2"
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: {{ $svc.name }} }
  minReplicas: {{ $common.hpa.minReplicas }}
  maxReplicas: {{ $common.hpa.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: {{ $common.hpa.cpuUtilization }} }
  behavior:
    scaleUp: { stabilizationWindowSeconds: {{ $common.hpa.scaleUpStabilizationSeconds }} }
    scaleDown: { stabilizationWindowSeconds: {{ $common.hpa.scaleDownStabilizationSeconds }} }
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ $svc.name }}
  namespace: {{ $root.Values.namespace }}
  labels:
    app.kubernetes.io/name: {{ $svc.name }}
    app.kubernetes.io/part-of: case-management
spec:
  minAvailable: {{ $common.pdb.minAvailable }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ $svc.name }}
      vectra.io/workload: {{ $svc.name }}
{{- end -}}
