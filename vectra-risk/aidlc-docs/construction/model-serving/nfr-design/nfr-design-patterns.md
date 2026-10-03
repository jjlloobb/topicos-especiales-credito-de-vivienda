# Patrones de NFR Design — U6 `model-serving`

Decisiones del plan (`model-serving-nfr-design-plan.md`, Q1–Q4 = A). Los IDs `P-U6-xx` se
referencian en Infrastructure Design y en el plan de tareas. Las verificaciones en kind las
ejecuta el operador después de un PR aprobado (AUTONOMIA-01).

---

## 1. Componentes de serving

### P-U6-01 — Predictor de un solo proceso (Q1)
- Imagen de Vectra que, al recibir `:predict` con un `FeatureVector`:
  1. arma el vector numérico en el orden de `feature_spec.json`;
  2. predice con la librería de XGBoost sobre `predictor.json`;
  3. calcula `confidence` con `envelope.confidence` (U5, solo numpy) y `domain_envelope.json`;
  4. responde `{score, confidence, model_version_id}` (el `score` como `float`; scoring lo cuantiza, BR-U0-07).
- Sin transformer separado ni servidor de XGBoost de KServe: un salto de red y una imagen menos, y el armado del vector y el modelo no pueden quedar en revisiones distintas.
- **Verificación**: prueba de contrato de `:predict`; PBT-U5-04 (paridad de `confidence` con U5) contra la imagen; benchmark local de p95 ≤ 30 ms por solicitud (sin red).
- **Satisface**: NFR-U6-04, 05, 10.

### P-U6-02 — Azul/verde por versión (Q2; US-204, FR-MOD-04)
- Cada versión tiene su `InferenceService` `isvc-<primeros 8 hex del model_version_id>`, con predictor y explicador sobre el mismo `storageUri` y la misma anotación (NFR-U6-02).
- Secuencia de promoción:
  1. el PR de `promotion-tool` **agrega** el `InferenceService` nuevo sin tocar el activo;
  2. un humano lo revisa, hace merge y sincroniza a mano;
  3. el nuevo pasa a listo solo con el paquete verificado (P-U6-03);
  4. `mark_active` cambia `serving-config.inference_service`;
  5. scoring y explainability llaman al nuevo en ≤ 6 s (BR-U4-14).
- Nunca conviven predictor y explicador de versiones distintas en el mismo `InferenceService`, así que no hay ventana de `version_mismatch` por despliegue.
- Después de `mark_active`, un PR post-activación baja el anterior a 1 réplica por componente; a los 7 días, un PR lo retira (INF-U6-02).
- Rollback (US-208): un PR restaura los mínimos de producción del `InferenceService` de la versión `inactivo`; con él listo, `mark_active` lo vuelve a activar. El activo nunca queda con menos de 2 réplicas.
- **Verificación**: en kind, promoción de M1 a M2 con tráfico continuo → 0 respuestas `version_mismatch` durante el cambio; rollback a M1 en ≤ 6 s tras `mark_active`.
- **Satisface**: NFR-U6-02; FR-MOD-04; AUTONOMIA-06.

### P-U6-03 — Verificación del paquete al arrancar
- El predictor y el explicador, antes de declararse listos:
  - leen `manifest.json`;
  - verifican el SHA-256 de cada archivo que usan;
  - comprueban que el `model_version_id` coincide con la anotación.
- Si algo no coincide → no listo + `ModelPackageIntegrityFailed`.
- `startupProbe` con margen para la descarga y la verificación; readiness = paquete verificado (P-U1-04).
- **Verificación**: artefactos RT-3 de U5 en staging o kind → el componente no queda listo; un byte alterado → no queda listo.
- **Satisface**: NFR-U6-03, 40; SECURITY-11, 13.

## 2. Escalado y aislamiento

### P-U6-04 — HPA por CPU (Q3; US-609)
- Predictor (2–4) y explicador (2–6) con HPA por CPU al 60 %, estabilización de 60 s hacia arriba y 300 s hacia abajo, sin escalar a cero.
- Solo el `InferenceService` activo recibe tráfico; los `inactivo` quedan en su mínimo hasta que se retiran.
- **Verificación**: prueba de carga de U12 a 20 solicitudes/s + `kubectl get hpa` durante la prueba; ningún componente supera su máximo.
- **Satisface**: NFR-U6-11, 12; RESILIENCY-09.

### P-U6-05 — Límite de concurrencia por pod (Q4)
- El predictor atiende como máximo **16** solicitudes concurrentes por pod y el explicador **8**.
- Por encima responden **503 de inmediato**, sin cola. El llamador lo trata como `timeout` o `explainer_unavailable` y falla cerrado (BR-U0-02).
- Métrica `vectra_serving_rejected_total{component}` y alerta `ServingSaturation` (SEV2) si supera el 1 % de las solicitudes durante 5 min.
- **Verificación**: prueba de carga que supera el límite → 503 inmediatos, p95 de las aceptadas dentro del objetivo; `promtool test rules` de la alerta.
- **Satisface**: RESILIENCY-10 (bulkhead); NFR-U6-10, 41; SECURITY-15.

## 3. Observabilidad

### P-U6-06 — Métricas y alertas de U6

| Alerta | Severidad | Origen |
|---|---|---|
| `ModelPackageIntegrityFailed` | SEV2 | P-U6-03 |
| `ServingSaturation` | SEV2 | P-U6-05 |
| `InferenceServiceNotReady` | SEV1 si es el activo; SEV3 si es un `inactivo` | El `InferenceService` sin réplicas listas |
| `ServingLatencyHigh` | SEV3 | p95 de `:predict` > 30 ms o de `:explain` > 150 ms durante 15 min |

- Métricas en el puerto 8081 (convención de U0) con `ServiceMonitor`; toda alerta con `runbook_url` (P-U1-10).
- **Verificación**: `promtool test rules model-serving/observability/rules/tests/*.yaml` y el test de runbooks de U1.

## 4. Cumplimiento de extensiones (NFR Design U6)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | P-U6-02 (cada cambio de versión entra por PR + sync manual) |
| AUTONOMIA-02 | Cumple | Cada patrón tiene su «Verificación» |
| AUTONOMIA-06 | Cumple | P-U6-02 (sin versiones mezcladas), P-U6-03 |
| SECURITY-11 | Cumple | P-U6-03 (probado con los casos de abuso RT-3 de U5; defensa en profundidad frente a U4) |
| SECURITY-13 | Cumple | P-U6-03 |
| SECURITY-14 | Cumple | P-U6-06 |
| SECURITY-15 | Cumple | P-U6-05 (503 inmediato → fail-closed en el llamador) |
| RESILIENCY-05 / 07 / 15 | Cumple | P-U6-06 |
| RESILIENCY-06 | Cumple | P-U6-03 (readiness = paquete verificado) |
| RESILIENCY-09 | Cumple | P-U6-04 |
| RESILIENCY-10 | Cumple | P-U6-05 (bulkhead) |
