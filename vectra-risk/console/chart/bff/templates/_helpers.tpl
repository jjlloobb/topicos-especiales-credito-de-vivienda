{{- /* Repositorio de la imagen. Argo CD pasa `imageRegistry` de vectra-risk-gitops/envs/<env>/values.yaml: `kind-registry:5000` en kind y
`registro.banco.internal/vectra` en staging y prod. Sin el (render local) vale el `repository` del values. */ -}}
{{- define "console-bff.repository" -}}
{{- if .Values.imageRegistry -}}
{{- if hasSuffix "/vectra" .Values.imageRegistry -}}{{ .Values.imageRegistry }}/console-bff{{- else -}}{{ .Values.imageRegistry }}/vectra/console-bff{{- end -}}
{{- else -}}
{{- required "image.repository es obligatorio" .Values.image.repository -}}
{{- end -}}
{{- end -}}
{{- /* Las variables del proceso (INF-U10-01): `console_bff.app.REQUIRED`, `VECTRA_CA_BUNDLE` (opcional) y `VECTRA_OTLP_ENDPOINT` (F61). Es el `data` del ConfigMap y el
texto del que sale `checksum/config`. */ -}}
{{- define "console-bff.env" -}}
VECTRA_CASE_URL: {{ required "peers.caseUrl es obligatorio" .Values.peers.caseUrl | quote }}
VECTRA_GOVERNANCE_URL: {{ required "peers.governanceUrl es obligatorio" .Values.peers.governanceUrl | quote }}
VECTRA_REGISTRY_URL: {{ required "peers.registryUrl es obligatorio" .Values.peers.registryUrl | quote }}
VECTRA_EXPLAINABILITY_URL: {{ required "peers.explainabilityUrl es obligatorio" .Values.peers.explainabilityUrl | quote }}
VECTRA_BIAS_URL: {{ required "peers.biasUrl es obligatorio" .Values.peers.biasUrl | quote }}
VECTRA_OIDC_ISSUER: {{ required "oidc.issuer es obligatorio" .Values.oidc.issuer | quote }}
VECTRA_JWKS_URL: {{ required "oidc.jwksUrl es obligatorio" .Values.oidc.jwksUrl | quote }}
VECTRA_CA_BUNDLE: {{ printf "%s/ca.crt" (required "keycloak.caMountPath es obligatorio" .Values.keycloak.caMountPath) | quote }}
VECTRA_OTLP_ENDPOINT: {{ required "telemetry.otlpEndpoint es obligatorio" .Values.telemetry.otlpEndpoint | quote }}
{{- end -}}
