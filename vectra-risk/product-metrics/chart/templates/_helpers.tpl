{{- /* Repositorio de la imagen. Argo CD pasa `imageRegistry` de vectra-risk-gitops/envs/<env>/values.yaml: `kind-registry:5000` en kind y
`registro.banco.internal/vectra` en staging y prod. Sin el (render local) vale el `repository` del values. */ -}}
{{- define "product-metrics.repository" -}}
{{- if .Values.imageRegistry -}}
{{- if hasSuffix "/vectra" .Values.imageRegistry -}}{{ .Values.imageRegistry }}/product-metrics{{- else -}}{{ .Values.imageRegistry }}/vectra/product-metrics{{- end -}}
{{- else -}}
{{- required "image.repository es obligatorio" .Values.image.repository -}}
{{- end -}}
{{- end -}}
{{- /* Los ocho parametros de cumplimiento (INF-U11-02, BR-U11-09), exigidos uno a uno. Salen **solo** de `values-product-metrics-policy.yaml`: el
archivo del chart (`.Files`, asi un `helm template` sin `-f` lo lee) o, encima de el, los values que Argo CD le pasa con ese mismo archivo. Ninguno esta
en `values.yaml` ni en una plantilla. `target_north_star` puede ser null (Helm descarta una clave nula de un values: entonces vale la del archivo del
chart), por eso se exige que la clave **exista**, no que tenga valor. Devuelve YAML de las ocho claves, que es el `data` del ConfigMap:
`include "product-metrics.policy" . | fromYaml`. */ -}}
{{- define "product-metrics.policy" -}}
{{- $file := (.Files.Get "values-product-metrics-policy.yaml" | fromYaml) -}}
{{- $out := dict -}}
{{- range $key := list "noise_floor" "noise_sustain_days" "noise_min_decisions" "target_complete_response" "target_origination_hours" "target_origination_ratio" "target_sustained_ratio_month6" "target_north_star" -}}
{{- $found := or (hasKey $.Values $key) (hasKey $file $key) -}}
{{- $_ := required (printf "%s es obligatorio (values-product-metrics-policy.yaml)" $key) (ternary "ok" "" $found) -}}
{{- $value := ternary (get $.Values $key) (get $file $key) (hasKey $.Values $key) -}}
{{- $_ := set $out $key $value -}}
{{- end -}}
{{- $out | toYaml -}}
{{- end -}}
