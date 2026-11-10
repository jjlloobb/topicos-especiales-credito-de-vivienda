{{- /* Repositorio de una imagen. Argo CD pasa `imageRegistry` de vectra-risk-gitops/envs/<env>/values.yaml: `kind-registry:5000` en kind y
`registro.banco.internal/vectra` en staging y prod. Sin el (render local) vale el `repository` del values. Uso: include "governance.repository" (list . "governance" .Values.image.repository). */ -}}
{{- define "governance.repository" -}}
{{- $root := index . 0 -}}{{- $name := index . 1 -}}{{- $fallback := index . 2 -}}
{{- if $root.Values.imageRegistry -}}
{{- if hasSuffix "/vectra" $root.Values.imageRegistry -}}{{ $root.Values.imageRegistry }}/{{ $name }}{{- else -}}{{ $root.Values.imageRegistry }}/vectra/{{ $name }}{{- end -}}
{{- else -}}
{{- required (printf "el repositorio de %s es obligatorio" $name) $fallback -}}
{{- end -}}
{{- end -}}
