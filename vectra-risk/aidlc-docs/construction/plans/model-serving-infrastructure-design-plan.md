# Plan de Infrastructure Design — U6 `model-serving`

**Alcance:** asignar los componentes de `nfr-design/logical-components.md` a la
infraestructura de U1: recursos, réplicas de los `InferenceService` inactivos (azul/verde),
probes y cuotas de `vectra-serving`.

**Heredado** (no se pregunta):
- entornos y pool `general` (U1); controlador de KServe en modo RawDeployment (K05);
- model-store en MinIO (INF-U1-03), con lectura de solo lectura (F46);
- flujos F19, F22, F30 y F46, que cubren los `InferenceService` por etiqueta (component-dependency, precisados por U6). **No hay flujos nuevos**;
- imágenes propias firmadas (NFR-U6-30) y políticas de Kyverno (U1).

**Categorías obligatorias:**

| Categoría | Aplica | Preguntas |
|---|---|---|
| Deployment Environment | Heredado de U1 | — |
| Compute Infrastructure | Sí | Q1, Q2 |
| Storage Infrastructure | **N/A**: sin volúmenes; el paquete se descarga del model-store a un `emptyDir` al arrancar | — |
| Messaging Infrastructure | **N/A**: solo request/response síncrono | — |
| Networking Infrastructure | Heredado (sin flujos nuevos) | — |
| Monitoring Infrastructure | Heredado de U1; alertas en P-U6-06 | — |
| Shared Infrastructure | Sí: cuotas de `vectra-serving` (NFR-U1-13) | Q2 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Recursos por componente (Compute)

A)

| Componente | Entorno | Requests | Limits |
|---|---|---|---|
| Predictor | prod | 500m / 512 MiB | 1 CPU / 1 GiB |
| Explicador | prod | 500m / 512 MiB | 2 CPU / 1 GiB |
| Predictor y explicador | staging | 250m / 256 MiB | 1 CPU / 512 MiB |

- `startupProbe` con `periodSeconds: 5` y `failureThreshold: 30` (hasta 150 s para descargar y verificar el paquete); readiness cada 5 s; liveness cada 10 s.
- `emptyDir` de 1 GiB para el paquete.
- Prioridad `vectra-high` en prod y `vectra-low` en staging.

(Recomendado: valores iniciales, ajustables con la prueba de carga de U12)

B) Sin límites, solo requests

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Réplicas del `InferenceService` inactivo durante los 7 días de rollback (Compute / Shared)
Con azul/verde conviven dos `InferenceService` hasta 7 días. Si el inactivo mantiene los
mínimos de producción (2 + 2), `vectra-serving` necesita el doble de capacidad base.

A) **El inactivo baja a 1 réplica por componente** (mínimo 1, sin HPA) cuando `mark_active` lo deja `inactivo`: el PR de promoción ya incluye ese cambio en sus values para la versión anterior, aplicado en el mismo sync. Un rollback empieza con 1 réplica y el HPA lo lleva a 2 en cuanto vuelve a ser activo (la plantilla restaura los mínimos de producción en el PR de rollback). Las cuotas de `vectra-serving` se dimensionan para el activo en su máximo + 1 + 1 del inactivo + 30 % (recomendado)

B) El inactivo conserva los mínimos de producción (2 + 2); cuotas para dos `InferenceService` completos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar NFR Design de U6 y la infraestructura compartida
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/model-serving/infrastructure-design/infrastructure-design.md`
- [x] 4. Generar `construction/model-serving/infrastructure-design/deployment-architecture.md` (diagrama validado)
- [x] 5. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
