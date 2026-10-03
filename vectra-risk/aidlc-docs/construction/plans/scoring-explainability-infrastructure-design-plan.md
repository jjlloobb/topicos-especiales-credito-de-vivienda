# Plan de Infrastructure Design — U7 `scoring-explainability`

**Alcance:** asignar los componentes de `nfr-design/logical-components.md` a la
infraestructura de U1: recursos, apagado ordenado, cuota de `vectra-app` y configuración de
los presupuestos de tiempo.

**Heredado** (no se pregunta):
- entornos y pool `general` (U1);
- namespace `vectra-app` (deployment-architecture de U1);
- `vectra-high` (P-U1-09);
- réplicas, HPA y PDB de P-U7-06;
- flujos F12, F15, F18–F23 y F103 ya inventariados en `component-dependency.md`. **No hay flujos nuevos ni egress**;
- K02, K03 y K13 para la observabilidad;
- imágenes firmadas y políticas de Kyverno (U1);
- plantillas dentro de la imagen (P-U7-07).

**Categorías obligatorias:**

| Categoría | Aplica | Preguntas |
|---|---|---|
| Deployment Environment | Heredado de U1 | — |
| Compute Infrastructure | Sí | Q1, Q2 |
| Storage Infrastructure | **N/A**: servicios sin estado, sin volúmenes; cachés en memoria (P-U7-05) | — |
| Messaging Infrastructure | **N/A**: solo request/response síncrono | — |
| Networking Infrastructure | Heredado (sin flujos nuevos) | — |
| Monitoring Infrastructure | Heredado de U1; alertas en P-U7-08 | — |
| Shared Infrastructure | Sí: aporte de U7 a la cuota de `vectra-app` (NFR-U1-13) | Q1 |
| Configuración | Sí: dónde viven los presupuestos de P-U7-01/02/04 | Q3 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Recursos y cuota (Compute / Shared)

A)

| Servicio | Requests | Limits | Réplicas |
|---|---|---|---|
| `scoring-service` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA 2–6 |
| `explainability-service` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA 2–6 |

- **Aporte de U7 a la `ResourceQuota` de `vectra-app`**: el máximo del HPA + 30 % (NFR-U1-13). Son 12 pods, con requests de 3 CPU / 3 GiB y limits de 12 CPU / 6 GiB. Con el margen: requests de 3,9 CPU / 3,9 GiB y limits de 15,6 CPU / 7,8 GiB.
- **Probes**: readiness cada 5 s y liveness cada 10 s, sin `startupProbe`. La precarga del diccionario no bloquea el arranque (NFR-U7-21).

(Recomendado: valores iniciales, ajustables con la prueba de carga de U12)

B) Sin límites, solo requests

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Apagado ordenado (Compute / Resilience)
**Hallazgo.** Ninguna unidad define el apagado de los pods. En scoring importa:
- con los 30 s por defecto de Kubernetes y sin drenaje, un pod que recibe `SIGTERM` en medio de un append (hasta ~6,1 s, P-U7-02) puede cortar la solicitud;
- si el commit ya ocurrió, queda una entrada `recommendation` **no entregada** (P-U7-03) por un simple despliegue o escalado hacia abajo, no por una falla.

A) **Drenaje explícito**:
   - `preStop` con `sleep 5`, para que el pod salga de los endpoints de Linkerd antes de dejar de aceptar conexiones;
   - al recibir `SIGTERM`, uvicorn deja de aceptar solicitudes y espera las que están en curso (`timeout_graceful_shutdown` de 10 s);
   - `terminationGracePeriodSeconds: 20` (5 + 10 + margen), por encima del peor caso de 6,1 s;
   - el proxy nativo de Linkerd termina después del contenedor de la app (sidecar nativo, P-U1-05);
   - igual en explainability, aunque su peor caso sea 700 ms.

   Así, un despliegue o un escalado hacia abajo nunca abandona un append (recomendado)

B) Valores por defecto de Kubernetes

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Dónde viven los presupuestos de tiempo (Configuración)
Los presupuestos de NFR-U7-10 / P-U7-01, 02 y 04 son: 700 ms, timeouts por llamada,
intentos, tamaños de pool y umbrales del circuit breaker.

A) **Constantes en el código** (`scoring/config.py`, `explainability/config.py`), versionadas y cubiertas por las pruebas de P-U7-01/02/04:
   - las variables de entorno del chart traen solo URLs, puertos y la audiencia de cada cliente;
   - cambiar un presupuesto exige un PR al código con sus pruebas, no un cambio de values;
   - una prueba falla si la suma de los presupuestos rompe P-U7-01 (`700 + 250 + 50 ≤ 1000 ms`).

   (Recomendado: los valores son parte del diseño verificado y no deben poder diferir entre entornos sin pasar por las pruebas)

B) En los values de Helm, validados al arrancar con Pydantic Settings y con límites

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el NFR Design de U7 y la infraestructura compartida
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/scoring-explainability/infrastructure-design/infrastructure-design.md`
- [x] 4. Generar `construction/scoring-explainability/infrastructure-design/deployment-architecture.md` (diagrama validado)
- [x] 5. Aplicar y registrar los cambios a otros artefactos, si los hay (p. ej. una convención de apagado en U0/U1 según Q2)
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
