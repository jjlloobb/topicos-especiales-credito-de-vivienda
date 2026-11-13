{{- /* Repositorio de la imagen. Argo CD pasa `imageRegistry` de vectra-risk-gitops/envs/<env>/values.yaml: `kind-registry:5000` en kind y
`registro.banco.internal/vectra` en staging y prod. Sin el (render local) vale el `repository` del values. */ -}}
{{- define "console-spa.repository" -}}
{{- if .Values.imageRegistry -}}
{{- if hasSuffix "/vectra" .Values.imageRegistry -}}{{ .Values.imageRegistry }}/console-spa{{- else -}}{{ .Values.imageRegistry }}/vectra/console-spa{{- end -}}
{{- else -}}
{{- required "image.repository es obligatorio" .Values.image.repository -}}
{{- end -}}
{{- end -}}
{{- /* El `config.json` (INF-U10-03): exactamente las cinco claves de `SCHEMA` (`console/spa/src/config/load.ts`). Es el `data` del ConfigMap tal cual y el
texto del que sale `checksum/config`: un cambio de hostname cambia las dos cosas. */ -}}
{{- define "console-spa.config" -}}
{{- $host := required "hostname es obligatorio (vectra-risk-gitops/values/<env>/console-spa.yaml)" .Values.hostname -}}
{{- $oidc := .Values.oidc -}}
{{- dict
    "oidc" (dict "authority" (printf "https://%s%s" $host $oidc.issuerPath) "client_id" (required "oidc.clientId es obligatorio" $oidc.clientId))
    "redirect_uri" (printf "https://%s%s" $host $oidc.redirectPath)
    "stepup_redirect_uri" (printf "https://%s%s" $host $oidc.stepupRedirectPath)
    "grafana" (dict "bias_dashboard_uid" (required "grafana.biasDashboardUid es obligatorio" .Values.grafana.biasDashboardUid))
  | toPrettyJson -}}
{{- end -}}
