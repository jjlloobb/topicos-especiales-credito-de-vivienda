# Plan de NFR Design — U6 `model-serving`

**Alcance:** convertir NFR-U6-01..41 en patrones y componentes lógicos. Las preguntas
centrales son cómo se componen los pasos de `:predict` y cómo se reemplaza una versión
sin que convivan predictor y explicador de versiones distintas.

**Ya decidido** (no se pregunta): TreeSHAP nativo de XGBoost, verificación del manifiesto al
arrancar, imágenes propias firmadas, staging aislado, réplicas y objetivos de latencia
(NFR-U6-01..41), y RESILIENCY-14 = C.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q2, Q4 |
| Scalability Patterns | Q3 |
| Performance Patterns | Q1, Q4 |
| Security Patterns | **Sin preguntas nuevas**: integridad al cargar, imágenes firmadas y sin egress ya están en NFR-U6-03, 30..32 |
| Logical Components | Q1, Q2 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Composición de `:predict` (Logical Components / Performance)
NFR Requirements eligió el servidor de XGBoost de KServe más un transformer de Vectra. En
modo RawDeployment son **dos Deployments**, con un salto de red extra dentro del
presupuesto de 30 ms, y transformer y predictor pueden quedar en revisiones distintas
durante un despliegue.

A) **Un solo componente predictor propio**: una imagen de Vectra que carga `predictor.json` con la librería de XGBoost y hace en el mismo proceso el armado del vector (`feature_spec.json`), la predicción y `confidence` (envolvente de U5). Responde `{score, confidence, model_version_id}`.
   - Sin transformer separado ni servidor de XGBoost de KServe.
   - Un salto menos, una imagen menos que firmar, y la forma del vector y el modelo no pueden desincronizarse entre procesos.
   - Se precisa la decisión de stack de NFR-U6 («predictor y transformer» pasa a «predictor»).

   (Recomendado)

B) Mantener el servidor de XGBoost de KServe + transformer separado, como en NFR Requirements

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Cómo se reemplaza una versión (Resilience, US-204, FR-MOD-04)
Si la promoción cambia el `storageUri` del `InferenceService` existente, el rolling update
deja durante unos minutos pods del predictor nuevo y del explicador viejo (o al revés).
scoring respondería `version_mismatch` (fail-closed seguro, pero con recomendaciones no
disponibles durante el despliegue).

A) **Azul/verde por versión**:
   - cada versión tiene su propio `InferenceService`, llamado `isvc-<primeros 8 hex del model_version_id>`;
   - el PR de promoción **agrega** el nuevo sin tocar el activo; después del sync manual, `mark_active` cambia `serving-config` para apuntar al nuevo;
   - un PR posterior (de `promotion-tool`) retira el anterior cuando pasa a `inactivo` + 7 días, conservándolo para un rollback rápido.

   Requiere agregar `inference_service` a `ServingConfig` (U0) y que U4/`promotion-tool` lo manejen. Las NetworkPolicies de F19/F22 admiten cualquier `InferenceService` del namespace por etiqueta (recomendado: sin ventana de versiones mezcladas)

B) Rolling update en el mismo `InferenceService`, aceptando `version_mismatch` transitorio durante el despliegue

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Métrica de escalado (Scalability, US-609)

A) **HPA por CPU al 60 %** para el predictor y el explicador, con ventana de estabilización de 60 s hacia arriba y 300 s hacia abajo, y sin escalar a cero (mínimos de NFR-U6-11). La CPU es un buen indicador porque ambos componentes son de cómputo puro (recomendado)

B) Escalado por solicitudes concurrentes con métricas personalizadas (requiere un adaptador de métricas)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Límite de concurrencia por pod (Resilience / Performance, bulkhead)

A) **Límite explícito**: el predictor atiende como máximo **16** solicitudes concurrentes por pod y el explicador **8**. Por encima responden **503 de inmediato** (sin cola), y el llamador lo trata como `timeout`/`explainer_unavailable`, que termina en fail-closed. Así se protege la latencia p95 de las solicitudes que sí entran y el HPA ve la presión en la CPU (recomendado)

B) Sin límite: las solicitudes esperan en la cola del servidor hasta el timeout del llamador

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar `construction/model-serving/nfr-requirements/` (NFR-U6-01..41, stack)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/model-serving/nfr-design/nfr-design-patterns.md`
- [x] 4. Generar `construction/model-serving/nfr-design/logical-components.md` (diagrama validado)
- [x] 5. Si la Q1 o la Q2 cambian artefactos aprobados (NFR-U6, U0, U4), actualizarlos y registrarlo
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
