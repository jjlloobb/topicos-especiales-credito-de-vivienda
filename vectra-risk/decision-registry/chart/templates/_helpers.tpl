{{- /* Repositorio de la imagen. Argo CD pasa `imageRegistry` de vectra-risk-gitops/envs/<env>/values.yaml (env_values): `kind-registry:5000` en
kind y `registro.banco.internal/vectra` en staging y prod. Sin el (render local) vale image.repository. */ -}}
{{- define "decision-registry.repository" -}}
{{- if .Values.imageRegistry -}}
{{- if hasSuffix "/vectra" .Values.imageRegistry -}}{{ .Values.imageRegistry }}/decision-registry{{- else -}}{{ .Values.imageRegistry }}/vectra/decision-registry{{- end -}}
{{- else -}}
{{- required "image.repository es obligatorio" .Values.image.repository -}}
{{- end -}}
{{- end -}}
