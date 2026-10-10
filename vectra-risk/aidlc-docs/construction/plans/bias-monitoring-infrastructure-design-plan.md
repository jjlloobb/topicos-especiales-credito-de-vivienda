# Plan de Infrastructure Design — U9 `bias-monitoring`

**Alcance:** asignar los componentes de `nfr-design/logical-components.md` a la
infraestructura de U1 y U2, y cerrar su §3 (pendientes para esta etapa).

**Heredado** (no se pregunta):
- **Entornos y ubicación:** pool `general` y namespace `vectra-app` (U1); sin base propia, así que no hay `Cluster` de CloudNativePG.
- **CronJob:**
  - `concurrencyPolicy: Forbid`, `backoffLimit: 0`, `activeDeadlineSeconds: 600`, `vectra-high`;
  - sidecar nativo de Linkerd, explícito en el chart (P-U1-05);
  - requests 100m / 128 MiB y limits 500m / 256 MiB, ajustables con la medición (NFR-U9-04).
- **Servicio:** 2 réplicas fijas con `vectra.io/hpa-exempt`, PDB, spread por zona, `vectra-normal` y readiness solo del proceso (NFR-U9-10..12).
- **Identidades:** un `ExternalSecret` por cliente de Keycloak (`bias-monitoring-job` y `bias-monitoring-service`), desde la bóveda (U2, ESO).
- **Observabilidad:**
  - métricas del CronJob al Pushgateway (F106), en los grupos `run` y `success`;
  - métricas del servicio en 8081 (F60);
  - reglas en una `PrometheusRule` del chart, con `runbook_url` (P-U1-10).
- **Seguridad de la cadena:** imágenes firmadas y políticas de Kyverno (U1).

**Categorías obligatorias:**

| Categoría | Aplica | Preguntas |
|---|---|---|
| Deployment Environment | Sí: el mismo chart en kind, staging y prod | Q2, Q3 |
| Compute Infrastructure | Sí | Q1, Q2 |
| Storage Infrastructure | **N/A**: sin base de datos ni volúmenes; lee el registro | — |
| Messaging Infrastructure | **N/A**: sin cola; la corrida lee conteos y llama a `freeze` | — |
| Networking Infrastructure | Sí: que solo el CronJob alcance `freeze` | Q4 |
| Monitoring Infrastructure | Sí: el dashboard de Grafana | Q5 |
| Shared Infrastructure | Sí: aporte a la cuota de `vectra-app` (NFR-U1-13) | Q1 |
| Configuración | Sí: qué va en values y quién aprueba el umbral | Q3 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Recursos del servicio y aporte a la cuota (Compute / Shared)

A)
   | Componente | Requests | Limits | Réplicas |
   |---|---|---|---|
   | `bias-monitoring-service` | 100m / 128 MiB | 500m / 256 MiB | 2 fijas |
   | CronJob de cálculo | 100m / 128 MiB | 500m / 256 MiB | 1 pod por corrida |

   Aporte a la cuota de `vectra-app` con el 30 % de margen (NFR-U1-13): requests ≈ 0,39 CPU / 0,5 GiB; limits ≈ 1,95 CPU / 1 GiB. La prueba de carga con 10 usuarios (NFR-U9-02) confirma los valores del servicio. (Recomendado)

B) El servicio con 250m / 256 MiB de requests y 1 CPU / 512 MiB de limits, como los demás servicios

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Horario del CronJob respecto del agregador de U3 (Compute / Deployment)
El agregador de U3 corre cada 5 min, en los minutos 0, 5, 10, etc. Si la corrida de bias
empieza justo con él, puede leer conteos de hasta 5 min atrás.

A) **Desfasado 2 min**: `schedule: "2,17,32,47 * * * *"` en UTC (`timeZone: Etc/UTC`) y `startingDeadlineSeconds: 300`, para que cada corrida empiece poco después de un lote del agregador. Una corrida que no arranca en 5 min se salta, y la siguiente la reemplaza. (Recomendado)

B) `*/15 * * * *` sin desfase

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Configuración y quién aprueba el umbral (Configuración; BR-U9-13)
BR-U9-13 pide que cambiar el umbral, `n_min`, la ventana, la frecuencia o W sea un PR
revisado por cumplimiento.

A) **Values propios y revisión obligatoria de cumplimiento**:
   - los cinco parámetros viven en un archivo de values propio del chart (`values-monitoring-policy.yaml`), igual en los tres entornos;
   - `CODEOWNERS` del repositorio GitOps exige la aprobación del equipo de cumplimiento para ese archivo, y la protección de rama lo hace obligatorio (como `branch-protection-check` de U4);
   - una regla de `conftest` rechaza valores fuera de rango (umbral entre 1 y 20 pp, `n_min` ≥ 30, ventana entre 7 y 90 días);
   - los timeouts, los reintentos y el tamaño de la caché son constantes del código (como INF-U8-07), no values.

   (Recomendado)

B) Los cinco parámetros en los values por entorno, sin `CODEOWNERS` propio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Que solo el CronJob alcance `freeze` (Networking; X04, NFR-U9-30)
Hoy la separación es de cliente de Keycloak (scope) y de código (import-linter). La red no
la refuerza: el servicio y el CronJob están en el mismo namespace.

A) **Dos ServiceAccounts y autorización de Linkerd por identidad**:
   - ServiceAccounts `bias-monitoring-job` (CronJob) y `bias-monitoring-service` (servicio);
   - en governance, la `AuthorizationPolicy` de Linkerd de la ruta `POST /v1/models/{id}/freeze` admite **solo** la identidad `bias-monitoring-job`; el servicio HTTP queda bloqueado en L7 aunque tuviera un token válido;
   - la `NetworkPolicy` hacia governance (F27) admite solo los pods con la etiqueta del CronJob;
   - suite de conectividad de U1: servicio → `freeze` → denegado; CronJob → `freeze` → permitido.

   (Recomendado: tercera barrera, además del scope y del código)

B) Una sola ServiceAccount para los dos; la separación queda en el scope y en el código

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Dashboard de Grafana del sesgo (Monitoring; FR-UI-05, US-307)
La consola embebe dashboards de Grafana (U10). La historia de la disparidad vive en
Prometheus (30 días).

A) **U9 entrega el dashboard como código**:
   - un dashboard JSON (`observability/dashboards/bias.json`) sobre las métricas de BR-U9-20: disparidad por atributo y banda, agregadas del modelo y de las decisiones humanas, tamaño de celda y estado de las corridas;
   - el panel principal lleva siempre la leyenda «mide y alerta, no certifica» como texto fijo, y el lint de frases prohibidas de U10 también se aplica al JSON;
   - las celdas insuficientes solo muestran su tamaño, igual que las métricas (BR-U9-20);
   - U10 lo embebe; las ventanas de 90 días siguen saliendo de la API (BR-U9-18).

   (Recomendado)

B) Sin dashboard de Grafana: la consola usa solo la API de U9

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `infrastructure-design.md`: INF-U9-xx (recursos y cuota, CronJob, identidades, red, configuración, observabilidad), cada uno con su verificación
- [x] `deployment-architecture.md`: topología (diagrama y texto alternativo), ciclo de vida, inventario de recursos de Kubernetes
- [x] Cambios a otras unidades registrados (U1 cuotas, U2 clientes, U4 `AuthorizationPolicy` de `freeze`, U10 dashboard)
- [x] Tabla de cumplimiento de extensiones
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
