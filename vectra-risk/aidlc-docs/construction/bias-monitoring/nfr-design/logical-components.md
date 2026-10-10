# Componentes lógicos — U9 `bias-monitoring`

---

## 1. Inventario

| Componente | Proceso | Función | Patrón | PriorityClass |
|---|---|---|---|---|
| CronJob de cálculo (`python -m vectra_bias.run`; horario de `values-monitoring-policy.yaml`, hoy `2,17,32,47 * * * *` UTC) | `vectra-app` | Corrida: lectura, cálculo, congelamiento, publicación | P-U9-01, 02, 05 | `vectra-high` |
| `bias-monitoring-service` (`Deployment`, 2 réplicas fijas) | `vectra-app` | Dashboard, congelamientos, `compare_source` | P-U9-02, 03, 05 | `vectra-normal` |
| `vectra_disparity` | Librería (CronJob, servicio, U4, U5) | `counts`, `stats`, `disparity` con la supresión de celdas chicas | P-U9-04 | — |
| `freeze_rule`, `context`, `window` | CronJob | Funciones puras de la regla, el paquete y la ventana | P-U9-01 | — |
| `freeze_client` | **Solo** el CronJob | La única llamada a governance (`freeze`), con reintentos; el servicio no puede importarlo | P-U9-01, 05 | — |
| `registry_client` | Los dos | `monitoring_daily:query` y `monitoring/freezes`; sin breaker en el CronJob y con breaker en el servicio | P-U9-02 | — |
| `dashboard_cache` | Servicio | LRU de 64 entradas, 15 min, *single-flight* | P-U9-03 | — |
| `publish` | CronJob | Grupos `run` (siempre), `success` (solo si la corrida fue completa) y `freeze-<model_version_id>` (`PUT` al fallar el `freeze`; `DELETE` al resolverse; lectura previa de los grupos con `GET /api/v1/metrics` y ≤ 16 `DELETE` por corrida) del Pushgateway (BR-U9-20) | P-U9-05 | — |
| `config` | Los dos | Constantes del código y los cinco parámetros de cumplimiento del `ConfigMap` generado de `values-monitoring-policy.yaml` (INF-U9-03) | P-U9-02 | — |
| Reglas de alerta y runbooks | `PrometheusRule` del chart (plantilla con W y el intervalo del horario) | `MonitoreoSesgoDetenido`, `BiasFreezeFailed`, `DisparidadDecisionHumana`, `BiasInvalidEntries` | P-U9-06 | — |

## 2. Dependencias

### Diagrama

```mermaid
flowchart LR
    bff["console-bff"]
    gov["governance-service"]
    subgraph u9["U9"]
        cron["CronJob de calculo"]
        svc["bias-monitoring-service"]
        lib["vectra_disparity"]
    end
    reg["decision-registry"]
    kc["Keycloak"]
    push["Pushgateway"]

    bff -->|"F14"| svc
    gov -->|"F25 compare_source"| svc
    cron -->|"F26"| reg
    svc -->|"F26"| reg
    cron -->|"F27 solo freeze"| gov
    cron -->|"F50 token"| kc
    svc -->|"F50 JWKS y token"| kc
    cron -->|"F106"| push
    cron --> lib
    svc --> lib
```

### Alternativa en texto

```text
console-bff   -> servicio   GET /v1/disparity, /v1/freezes, /v1/freezes/{id}        F14
governance    -> servicio   POST /v1/source-comparisons (compare_source)              F25
CronJob       -> registro   GET /v1/monitoring/freezes, POST /v1/monitoring/daily:query  F26  (sin breaker, batch)
servicio      -> registro   las mismas lecturas para el dashboard                      F26  (con breaker)
CronJob       -> governance POST /v1/models/{id}/freeze (solo freeze)                  F27
CronJob, servicio -> Keycloak  token (bias-monitoring-job / bias-monitoring-service) y JWKS   F50
CronJob       -> Pushgateway  grupos run y success (PUT); freeze-<v> (PUT, DELETE); GET /api/v1/metrics   F106
El CronJob y el servicio usan la librería vectra_disparity; U4 y U5 también.
```

### Presupuesto de una corrida (peor caso, P-U9-02; actualizado en la revisión del Infrastructure Design de U10, 2026-10-10)

| Tramo | Tiempo |
|---|---|
| Token (con un reintento) | 4 s |
| Congelamientos registrados | 3 s |
| 2 solicitudes de conteos | 10 s |
| Cálculo de 3 versiones | ≤ 2 s |
| `freeze` de 3 versiones que fallan (4 intentos con 1 + 2 + 4 s de espera) | 57 s |
| Push de los grupos `run` y `success` | 10 s |
| Lectura de grupos, 3 `PUT`/`DELETE` por versión y ≤ 16 `DELETE` de versiones que ya no se evalúan | ≈ 100 s |
| **Total** | **≈ 186 s ≤ 600 s (`activeDeadlineSeconds`) y ≤ el intervalo del horario (INF-U9-03)** |

El caso normal (sin fallos ni congelamiento) ronda unos pocos segundos, dentro del p95 de 2 min
de NFR-U9-01.

## 3. Resuelto en el Infrastructure Design de U9

El horario, `Forbid`, `backoffLimit`, plazos, PriorityClass, sidecar, `ExternalSecret`, flujos y
alertas se fijaron en INF-U9-01..05 (revisión del Infrastructure Design de U10, 2026-10-10: esta sección decía «pendiente»).
