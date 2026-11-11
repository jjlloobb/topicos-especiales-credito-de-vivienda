{{- /* Repositorio de la imagen. Argo CD pasa `imageRegistry` de vectra-risk-gitops/envs/<env>/values.yaml: `kind-registry:5000` en kind y
`registro.banco.internal/vectra` en staging y prod. Sin el (render local) vale el `repository` del values. */ -}}
{{- define "bias-monitoring.repository" -}}
{{- if .Values.imageRegistry -}}
{{- if hasSuffix "/vectra" .Values.imageRegistry -}}{{ .Values.imageRegistry }}/bias-monitoring{{- else -}}{{ .Values.imageRegistry }}/vectra/bias-monitoring{{- end -}}
{{- else -}}
{{- required "image.repository es obligatorio" .Values.image.repository -}}
{{- end -}}
{{- end -}}
{{- /* Los cinco parametros de cumplimiento (INF-U9-03, BR-U9-13), exigidos uno a uno. Salen **solo** de `values-monitoring-policy.yaml`: el archivo del
chart (`.Files`, asi un `helm template` sin `-f` lo lee) o, encima de el, los values que Argo CD le pasa con ese mismo archivo. Ninguno esta en `values.yaml`
ni en una plantilla. Sin el archivo y sin values no se renderiza. Devuelve YAML: `include "bias-monitoring.policy" . | fromYaml`. */ -}}
{{- define "bias-monitoring.policy" -}}
{{- $file := (.Files.Get "values-monitoring-policy.yaml" | fromYaml) -}}
{{- $out := dict -}}
{{- range $key := list "threshold_pp" "n_min" "window_days" "schedule" "stale_after" -}}
{{- $value := ternary (get $.Values $key) (get $file $key) (hasKey $.Values $key) -}}
{{- $_ := set $out $key (required (printf "%s es obligatorio (values-monitoring-policy.yaml)" $key) $value) -}}
{{- end -}}
{{- printf "threshold_pp: %v\nn_min: %v\nwindow_days: %v\nschedule: %s\nstale_after: %s" $out.threshold_pp $out.n_min $out.window_days ($out.schedule | quote) ($out.stale_after | quote) -}}
{{- end -}}
