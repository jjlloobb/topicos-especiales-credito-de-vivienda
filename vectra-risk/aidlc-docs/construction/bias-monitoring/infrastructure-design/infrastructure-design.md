# Infrastructure Design — U9 `bias-monitoring`

Decisiones del plan (`bias-monitoring-infrastructure-design-plan.md`, Q1–Q5 = A). Se apoya
en la infraestructura compartida de U1 y U2. Los IDs `INF-U9-xx` se referencian en el plan
de tareas. Lo que se verifica «en kind» lo ejecuta el operador después de un PR aprobado
(AUTONOMIA-01). Sin almacenamiento ni mensajería propios: U9 lee conteos del registro (F26).

---

## 1. Cómputo (Q1, Q2)

### INF-U9-01 — Recursos, réplicas y cuota (Q1; NFR-U9-04, 10, 11)

| Componente | Requests | Limits | Réplicas / ejecución | PriorityClass |
|---|---|---|---|---|
| `bias-monitoring-service` | 100m / 128 MiB | 500m / 256 MiB | 2 fijas, `vectra.io/hpa-exempt` (carga baja, caché de 15 min), PDB `minAvailable: 1`, spread por zona | `vectra-normal` |
| CronJob de cálculo | 100m / 128 MiB | 500m / 256 MiB | 1 pod por corrida | `vectra-high` |

- **Aporte a la cuota de `vectra-app`**, con el 30 % de margen (NFR-U1-13): requests ≈ 0,39 CPU y 0,5 GiB; limits ≈ 1,95 CPU y 1 GiB. U1 lo suma en su chart de cuotas (Paso 6 del plan de U1).
- Readiness (`/readyz`, 8081) y liveness solo del proceso (NFR-U9-12, P-U1-04).
- **Verificación**:
  - `helm template` + `conftest`: requests y limits presentes; servicio con 2 réplicas, PDB, spread y la anotación de exención; `priorityClassName` por proceso;
  - `kyverno test` de U1 (`require-hpa-bounds` admite la exención);
  - la prueba de carga con 10 usuarios (NFR-U9-02) y la medición de la corrida (NFR-U9-04) confirman o ajustan los valores.
- **Satisface**: NFR-U9-04, 10, 11, 12; RESILIENCY-01, 08, 09.

### INF-U9-02 — CronJob desfasado del agregador (Q2; NFR-U9-01, 13)
- `schedule: "2,17,32,47 * * * *"` con `timeZone: Etc/UTC`. Corre 2 min después de un lote del agregador de U3, que corre en los minutos 0, 5, 10, etc.
- Configuración del CronJob:
  - `concurrencyPolicy: Forbid`;
  - `startingDeadlineSeconds: 300`: una corrida que no arranca en 5 min se salta, y la siguiente la reemplaza;
  - `backoffLimit: 0`;
  - `activeDeadlineSeconds: 600`;
  - `successfulJobsHistoryLimit: 3` y `failedJobsHistoryLimit: 3`.
- Sidecar nativo de Linkerd, con la anotación explícita en el chart (P-U1-05). Así el Job termina cuando termina el contenedor.
- **Verificación**: `conftest`: horario, `Forbid`, `backoffLimit: 0`, los dos plazos y la anotación del sidecar; en kind, una corrida completa termina como `Complete` y el sidecar se detiene.
- **Satisface**: NFR-U9-01, 13; RESILIENCY-04.

## 2. Configuración (Q3)

### INF-U9-03 — Parámetros de cumplimiento en un archivo propio (Q3; BR-U9-13)
- **Archivo** `values-monitoring-policy.yaml` del chart, igual en los tres entornos, con los cinco parámetros:

  | Parámetro | Valor |
  |---|---|
  | `threshold_pp` | 5 |
  | `n_min` | 30 |
  | `window_days` | 30 |
  | `schedule` | el de INF-U9-02 |
  | `stale_after` (W) | 1 h |

- **Revisión obligatoria de cumplimiento**: `CODEOWNERS` del repositorio GitOps asigna ese archivo al equipo de cumplimiento, y la protección de rama exige la aprobación de los *code owners*. `branch-protection-check` de U4 ya verifica que esa regla esté activa.
- **Rangos válidos**, con una regla de `conftest`:
  - umbral entre 1 y 20 pp;
  - `n_min` ≥ 30;
  - ventana entre 7 y 90 días;
  - W ≥ 30 min;
  - **horario** (revisión del Infrastructure Design de U9, 2026-10-10): una lista de minutos con un intervalo fijo de **5 a 15 min** entre corridas (por ejemplo `2,17,32,47 * * * *`), con un desfase de 1 a 4 min respecto de los múltiplos de 5 (el agregador de U3), y **W ≥ 4 × el intervalo**, para que una sola corrida fallida no dispare la alerta. Un horario fuera de ese rango obliga además a revisar NFR-U9-01.
- **Constantes del código** (no values, como INF-U8-07): timeouts y reintentos (P-U9-02), caché del dashboard (P-U9-03), razón de inválidas (1 %) y atraso máximo del agregador (30 min).
- **Values por entorno**: URLs y audiencias de las dependencias, endpoint de telemetría, URL del Pushgateway y nivel de log.
- **Verificación**:
  - `conftest` con valores dentro y fuera de rango;
  - prueba de que ninguna constante aparece como variable de entorno;
  - prueba de que el paquete y el dashboard muestran los valores en uso (BR-U9-13);
  - `CODEOWNERS` contiene la línea del archivo.
- **Satisface**: BR-U9-13; AUTONOMIA-02; SECURITY-11.

## 3. Identidades y red (Q4)

### INF-U9-04 — Dos identidades y tres barreras para `freeze` (Q4; X04, NFR-U9-30)

| Capa | CronJob | Servicio HTTP |
|---|---|---|
| ServiceAccount (identidad de Linkerd) | `bias-monitoring-job` | `bias-monitoring-service` |
| Cliente de Keycloak (U2) | `bias-monitoring-job`: `governance:freeze`, `registry:read:monitoring` | `bias-monitoring-service`: `registry:read:monitoring` |
| `ExternalSecret` (llave `private_key_jwt`) | Propio | Propio |

**Las tres barreras de `freeze`:**
1. **Scope**: solo el cliente `bias-monitoring-job` tiene `governance:freeze`; `realm-lint` lo verifica (U2).
2. **Código**: el servicio no importa `freeze_client` (import-linter, P-U9-05).
3. **Red**:
   - en governance, la `AuthorizationPolicy` de Linkerd de la ruta `POST /v1/models/{id}/freeze` admite **solo** la identidad `bias-monitoring-job`;
   - la `NetworkPolicy` de F27 admite solo los pods con la etiqueta del CronJob (`app.kubernetes.io/component: bias-calculation`).

**Flujos**, en `flows.yaml` de U1:
- F14 y F25 llegan al servicio;
- F26 sale del CronJob y del servicio;
- F27 sale **solo** del CronJob;
- F50 sale de los dos;
- F60 es el scrape del servicio;
- F106 va del CronJob al Pushgateway.

**Verificación**:
- suite de conectividad de U1: servicio → `freeze` → denegado por Linkerd; CronJob → `freeze` → permitido; servicio → Pushgateway → denegado;
- prueba del realm de U2;
- import-linter.

**Satisface**: NFR-U9-30, 34; SECURITY-06, 07, 08; AUTONOMIA-04.

## 4. Observabilidad (Q5)

### INF-U9-05 — Reglas, runbooks y dashboard como código (Q5; P-U9-06; FR-UI-05, US-307)
- `PrometheusRule` del chart con las alertas de P-U9-06, cada una con `severity` y `runbook_url`. Los umbrales de `MonitoreoSesgoDetenido` (W y 2W) se generan desde `stale_after` de `values-monitoring-policy.yaml`, no se escriben a mano (revisión del Infrastructure Design de U9, 2026-10-10).
- `ServiceMonitor` del servicio (8081). Prometheus lee las métricas del CronJob en el Pushgateway (F88, `honor_labels: true`).
- **Dashboard de Grafana** (`observability/dashboards/bias.json`), como código:
  - paneles de disparidad por atributo y banda, de las agregadas del modelo y de las decisiones humanas (separadas), del tamaño de celda y del estado de las corridas;
  - la leyenda «mide y alerta, no certifica» como texto fijo en el panel principal;
  - las celdas insuficientes solo muestran su tamaño, y la serie `sin_bandas` respeta la etiqueta `partial` (BR-U9-06, 20);
  - el lint de frases prohibidas de U10 también se aplica al JSON;
  - U10 lo embebe. Las ventanas de 90 días siguen saliendo de la API (BR-U9-18), porque Prometheus guarda 30 días.
- **Verificación**:
  - `promtool test rules` (P-U9-06), generado con el `stale_after` del archivo de parámetros, y el test de runbooks de U1;
  - prueba sobre el JSON: la leyenda está, no hay frases prohibidas y ninguna consulta muestra tasas de celdas insuficientes (las consultas filtran por tamaño ≥ `n_min`).
- **Satisface**: NFR-U9-40, 41; RESILIENCY-05, 07, 15; FR-BIA-08.

## 5. Cumplimiento de extensiones (Infrastructure Design U9)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | INF-U9-01 (criticidad por proceso) |
| RESILIENCY-04 | Cumple | INF-U9-02 (sidecar nativo; el Job termina) |
| RESILIENCY-05 / 07 / 15 | Cumple | INF-U9-05 |
| RESILIENCY-08 / 09 | Cumple | INF-U9-01 |
| SECURITY-06 / 07 / 08 | Cumple | INF-U9-04 (tres barreras para `freeze`) |
| SECURITY-11 | Cumple | INF-U9-03 (rangos y revisión de cumplimiento) |
| AUTONOMIA-01 | Cumple | `Application` de Argo CD con sync manual (deployment-architecture) |
| AUTONOMIA-02 | Cumple | Cada `INF-U9-xx` tiene su «Verificación» |
| AUTONOMIA-04 / 05 | Cumple | INF-U9-04; sin egress |

## 6. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U4 (`AuthorizationPolicy` de Linkerd de la ruta `freeze`; INF-U4-04 y plan de U4, Paso 16) | La ruta `POST /v1/models/{id}/freeze` admite solo la identidad `bias-monitoring-job` | Q4 |
| U1 `flows.yaml` y plan de U1 (Pasos 3 y 6) | F27 solo desde los pods del CronJob; aporte de U9 a la cuota de `vectra-app` | Q1, Q4 |
| Repositorio GitOps (`CODEOWNERS`) | `values-monitoring-policy.yaml` asignado al equipo de cumplimiento | Q3 |
| U10 (pendiente) | Embeber `bias.json`; el lint de frases prohibidas cubre ese JSON | Q5 |

## 7. Pendientes
- **Para el plan de tareas de U9**: paquete y punto de entrada del CronJob, chart con los dos procesos, `values-monitoring-policy.yaml` y su regla de `conftest`, dashboard y reglas.
- **Para U10**: embeber el dashboard y aplicarle el lint.
- **Para U12**: la demostración de RT-2 (volumen por celda y latencia de detección, §8b del FD).
