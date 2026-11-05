{{- /* Imagen por digest: sin registro o sin digest, la plantilla falla. */ -}}
{{- define "valkey.image" -}}
{{- $registry := required "registry es obligatorio (INF-U2-04): el espejo de cada entorno" .root.Values.registry -}}
{{- $digest := required (printf "images.%s.digest es obligatorio (INF-U2-04)" .key) .image.digest -}}
{{- printf "%s/%s@%s" $registry .image.name $digest -}}
{{- end -}}

{{- /* FQDN del pod `<i>` de un StatefulSet con Service headless del mismo nombre. */ -}}
{{- define "valkey.fqdn" -}}
{{- printf "%s-%d.%s.%s.%s" .name (.index | int) .name .root.Values.namespace .root.Values.domain -}}
{{- end -}}

{{- /* Los Sentinel (sin puerto), en orden: sentinel-a-0, sentinel-b-0, sentinel-b-1. */ -}}
{{- define "valkey.sentinelHosts" -}}
{{- $root := . -}}
{{- $hosts := list -}}
{{- range $key := keys $root.Values.sentinel.groups | sortAlpha -}}
{{- $group := get $root.Values.sentinel.groups $key -}}
{{- range $i := until ($group.replicas | int) -}}
{{- $hosts = append $hosts (include "valkey.fqdn" (dict "root" $root "name" $group.name "index" $i)) -}}
{{- end -}}
{{- end -}}
{{- join " " $hosts -}}
{{- end -}}

{{- define "valkey.labels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .instance }}
app.kubernetes.io/part-of: identity-edge
{{- end -}}

{{- define "valkey.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 999
runAsGroup: 999
fsGroup: 999
seccompProfile: { type: RuntimeDefault }
{{- end -}}

{{- define "valkey.containerSecurityContext" -}}
allowPrivilegeEscalation: false
privileged: false
readOnlyRootFilesystem: true
runAsNonRoot: true
capabilities: { drop: [ALL] }
seccompProfile: { type: RuntimeDefault }
{{- end -}}

{{- define "valkey.zoneAffinity" -}}
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: topology.kubernetes.io/zone
              operator: In
              values: [{{ required "la zona de cada grupo es obligatoria (R3): la fija el entorno" .zone | quote }}]
{{- end -}}
