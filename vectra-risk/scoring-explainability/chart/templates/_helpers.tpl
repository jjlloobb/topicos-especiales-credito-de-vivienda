{{- /* Repositorio de la imagen de un servicio (`images.<clave>`). Argo CD pasa `imageRegistry` de vectra-risk-gitops/envs/<env>/values.yaml:
`kind-registry:5000` en kind y `registro.banco.internal/vectra` en staging y prod. Sin el (render local) vale el `repository` del values. */ -}}
{{- define "scoring-explainability.repository" -}}
{{- $root := index . 0 -}}
{{- $key := index . 1 -}}
{{- $image := index $root.Values.images $key -}}
{{- $name := (index $root.Values.services $key).name -}}
{{- if $root.Values.imageRegistry -}}
{{- if hasSuffix "/vectra" $root.Values.imageRegistry -}}{{ $root.Values.imageRegistry }}/{{ $name }}{{- else -}}{{ $root.Values.imageRegistry }}/vectra/{{ $name }}{{- end -}}
{{- else -}}
{{- required (printf "images.%s.repository es obligatorio" $key) $image.repository -}}
{{- end -}}
{{- end -}}
