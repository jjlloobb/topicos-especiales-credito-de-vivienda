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

- **Aporte a la cuota de `vectra-app`**, con el 30 % de margen (NFR-U1-13), para 3 pods (2 réplicas y 1 corrida; `Forbid` impide dos a la vez) (revisión del FD de U10, 2026-10-10, B8):

  | | Requests | Limits |
  |---|---|---|
  | Sin el sidecar | ≈ 0,39 CPU y 0,5 GiB | ≈ 1,95 CPU y 1 GiB |
  | Con el sidecar de Linkerd (100m / 20 MiB de requests y 500m / 128 MiB de limits por pod, fijados por U1 P-U1-14) | ≈ 0,78 CPU y 0,56 GiB | ≈ 3,9 CPU y 1,46 GiB |

  La cuota cuenta los contenedores de init con `restartPolicy: Always` (sidecar nativo), así que U1 suma la fila **con** el sidecar. Los valores del proxy los fija U1 P-U1-14 (revisión del Infrastructure Design de U10, 2026-10-10). U1 lo suma en su chart de cuotas (Paso 6 del plan de U1).
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

- **Revisión obligatoria de cumplimiento** (revisión del FD de U10, 2026-10-10, A5): el archivo vive en el **monorepo** (`vectra-risk/bias-monitoring/chart/`), donde se edita, y llega a `vectra-risk-gitops` con el chart. Por eso hay una línea de `CODEOWNERS` en **los dos** repositorios: en el monorepo (`bias-monitoring/chart/values-monitoring-policy.yaml`, donde se aprueba el cambio) y en GitOps (la copia que despliega Argo CD). La protección de `main` exige la aprobación de los *code owners* en los dos. `branch-protection-check` de U4 verifica ambos repositorios (antes, solo GitOps). La misma regla cubre `contracts/forbidden-phrases.yaml` de U0 (BR-U0-94).
- **Rangos válidos**, con una regla de `conftest`:
  - umbral entre 1 y 20 pp;
  - `n_min` ≥ 30;
  - ventana entre 7 y 90 días;
  - W ≥ 30 min;
  - **horario** (revisión del Infrastructure Design de U9, 2026-10-10): una lista de minutos con un intervalo fijo de **5, 10 o 15 min** entre corridas (por ejemplo `2,17,32,47 * * * *`), con un desfase de 1 a 4 min respecto de los múltiplos de 5 (el agregador de U3), y **W ≥ 4 × el intervalo**, para que una sola corrida fallida no dispare la alerta. El intervalo debe ser múltiplo de 5 y dividir 60: con 6 o 12 min el desfase respecto del agregador cambia de una corrida a otra (revisión del FD de U10, 2026-10-10, A6). Un horario fuera de ese rango obliga además a revisar NFR-U9-01;
  - **plazo**: `activeDeadlineSeconds` ≤ el intervalo en segundos (hoy 600 s con 15 min; con 5 min, el plazo debe bajar a ≤ 300 s, que sigue cubriendo el peor caso de ≈ 186 s de P-U9-02) (revisión del FD de U10, 2026-10-10, A6).
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
  - el lint de frases prohibidas (lista única de U0, BR-U0-94; precisado el 2026-10-10 por U10 FD, Q8) también se aplica al JSON;
  - U10 lo embebe. Las ventanas de 90 días siguen saliendo de la API (BR-U9-18), porque Prometheus guarda 30 días;
  - **organización y permisos de Grafana** (segunda revisión del Infrastructure Design de U10, 2026-10-10): una sola organización `Vectra`; `bias.json` va aprovisionado (solo lectura, sin edición desde la UI) en la carpeta `Vectra / Sesgo`, con permiso `View` **solo** para los equipos `cumplimiento` y `cro` (mapeados desde los roles del token de Keycloak, U2). Ningún otro equipo ve la carpeta; el iframe de U10 usa la sesión OIDC de Grafana del mismo usuario, así que un `analista` ve «sin acceso» también dentro del iframe. Los permisos los aplica el Job `grafana-folder-permissions` de U1, que quita la herencia de los roles de organización (`ingeniero_riesgo` es `Viewer` y `operacion` es `Editor`, y sin quitarla verían la carpeta); se prueba con `ingeniero-1` y `operacion-1` → 403 (FD de U11, 2026-10-10).
- **Permisos en el Pushgateway** (U1 P-U1-13; segunda revisión del Infrastructure Design de U10, 2026-10-10): `bias-monitoring-job` puede `PUT` y `DELETE` solo en `/metrics/job/bias-monitoring/**` (grupos `run`, `success` y `freeze-<v>`) y `GET /api/v1/metrics` para listar los grupos antes de borrar los de versiones que ya no se evalúan (BR-U9-20). El `GET` devuelve también los grupos de otros jobs; el CronJob filtra por `job="bias-monitoring"` y nunca toca otros. `bias-monitoring-service` no tiene acceso al Pushgateway.
- **Verificación**:
  - `promtool test rules` (P-U9-06), generado con el `stale_after` del archivo de parámetros, y el test de runbooks de U1;
  - prueba sobre el JSON: la leyenda está, no hay frases prohibidas y ninguna consulta muestra tasas de celdas insuficientes (las consultas filtran por tamaño ≥ `n_min`);
  - prueba del aprovisionamiento: la carpeta `Vectra / Sesgo` solo da `View` a `cumplimiento` y `cro`; en kind, un usuario `analista` recibe 403 en el dashboard.
- **Satisface**: NFR-U9-40, 41; RESILIENCY-05, 07, 15; FR-BIA-08.

## 5. Cumplimiento de extensiones (Infrastructure Design U9)

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
| Monorepo y repositorio GitOps (`CODEOWNERS`); U4 `branch-protection-check` | `values-monitoring-policy.yaml` asignado al equipo de cumplimiento en los dos repositorios; el check verifica la protección de los dos | Q3; revisión del FD de U10, 2026-10-10, A5 |
| U10 (pendiente) | Embeber `bias.json`; el lint de frases prohibidas cubre ese JSON | Q5 |

## 7. Pendientes
- **Para el plan de tareas de U9**: paquete y punto de entrada del CronJob, chart con los dos procesos, `values-monitoring-policy.yaml` y su regla de `conftest`, dashboard y reglas.
- **Para U10**: embeber el dashboard y aplicarle el lint.
- **Para U12**: la demostración de RT-2 (volumen por celda y latencia de detección, §8b del FD).
