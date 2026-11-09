{{- /* `isvc-<8 hex>`: los 8 hex finales del model_version_id (`mv-<fecha>-<8 hex>`), como `isvc_name` de governance (U4). */ -}}
{{- define "model-serving.name" -}}
isvc-{{ trunc -8 .modelVersionId }}
{{- end -}}

{{- /* Namespace del perfil: `serving` o `staging` de .Values.namespaces. */ -}}
{{- define "model-serving.namespace" -}}
{{- $profile := index .root.Values.profiles .item.profile -}}
{{- index .root.Values.namespaces $profile.namespace -}}
{{- end -}}

{{- /* Repositorio de la imagen: con `imageRegistry` (Argo CD, envs/<env>/values.yaml) se arma <registro>/vectra/<imagen>. */ -}}
{{- define "model-serving.image" -}}
{{- $image := index .root.Values.images .component -}}
{{- $digest := required (printf "images.%s.digest es obligatorio" .component) $image.digest -}}
{{- if .root.Values.imageRegistry -}}
{{- $base := ternary .root.Values.imageRegistry (printf "%s/vectra" .root.Values.imageRegistry) (hasSuffix "/vectra" .root.Values.imageRegistry) -}}
{{ $base }}/model-{{ .component }}@{{ $digest }}
{{- else -}}
{{ required (printf "images.%s.repository es obligatorio" .component) $image.repository }}@{{ $digest }}
{{- end -}}
{{- end -}}

{{- /* Etiquetas del pod de un componente: `vectra.io/component` (selector de flows.yaml) y `app.kubernetes.io/name` (PDB). */ -}}
{{- define "model-serving.podLabels" -}}
app.kubernetes.io/name: {{ .name }}-{{ .component }}
app.kubernetes.io/part-of: vectra-risk
vectra.io/component: {{ .component }}
vectra.io/criticality: high
vectra.io/inference-service: {{ .name }}
{{- end -}}
