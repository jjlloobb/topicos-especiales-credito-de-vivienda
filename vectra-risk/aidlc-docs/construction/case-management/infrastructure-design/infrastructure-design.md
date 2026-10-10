# Infrastructure Design — U8 `case-management`

Decisiones del plan (`case-management-infrastructure-design-plan.md`, Q1–Q7 = A). Se apoya
en la infraestructura compartida de U1 y U2. Los IDs `INF-U8-xx` se referencian en el plan
de tareas. Lo que se verifica «en kind» lo ejecuta el operador después de un PR aprobado
(AUTONOMIA-01).

---

## 1. Identidades (Q1)

### INF-U8-01 — `case-worker` con identidad propia en las tres capas

| Capa | `case-service` | `case-worker` | `case-retention` |
|---|---|---|---|
| ServiceAccount (identidad de Linkerd) | `case-service` | `case-worker` | `case-retention` |
| Cliente de Keycloak (U2) | `case-service`: `registry:append:case`, `core:read-credit`, `governance:read-serving` | `case-worker`: `case:recommend`, `governance:read-serving`, `governance:read-feature-spec` | — (no llama a servicios) |
| Rol de `case-db` | `case_app` | `case_worker` | `case_retention` |

- **`case-service` pierde `case:recommend` y `governance:read-feature-spec`**. La API ya no llama a scoring y no arma vectores. Conserva `governance:read-serving` para el barrido de BR-U8-10/14.
- **Rol `case_worker`**:
  - `SELECT` sobre `cases` y `case_identifiers` (para `derive`);
  - `UPDATE (state, attempts, last_cause, recommendation, recommendation_entry_id, escalation_count, updated_at)` sobre `cases`;
  - `SELECT`, `UPDATE` y `DELETE` sobre `evaluation_jobs`;
  - `INSERT` en `evidence_outbox`, **solo** de la entrada `fail_closed` del escalamiento (BR-U8-09). Un permiso no restringe valores, así que la tabla tiene RLS (revisión 2026-10-08, N1):
    - `ALTER TABLE evidence_outbox ENABLE ROW LEVEL SECURITY`;
    - política `worker_fail_closed_only` `FOR INSERT TO case_worker WITH CHECK (entry_type = 'fail_closed')`;
    - política `app_all` `FOR ALL TO case_app USING (true) WITH CHECK (true)`, para que `case_app` siga como antes;
    - `case_worker` no tiene `SELECT` sobre la tabla, así que no necesita una política de lectura. `case_migrator` es dueño de la tabla y RLS no le aplica (sin `FORCE`).

    Sin esto, un worker comprometido podría insertar una `human_decision` y el reconciliador de `case-service` la enviaría al registro con el scope `registry:append:case`;
    - sin `SELECT`, el `INSERT` de `case_worker` no puede usar `RETURNING` ni `ON CONFLICT`: es un `INSERT` simple dentro de un `SAVEPOINT`, y un `unique_violation` sobre la llave de idempotencia se trata como éxito (BR-U8-09; precisado el 2026-10-08, revisión del plan de tareas de U8);
  - sin acceso a `decisions`, `explanation_views`, `intake_keys`, `retention_runs` ni `retention_settings`.
- **Rol `case_app`** (hallazgo 2 de la revisión):
  - pierde `UPDATE` y `DELETE` sobre `evaluation_jobs`; conserva `SELECT` e `INSERT` (alta, `retry`, descongelamiento y el gauge de la cola);
  - sobre `cases`, `UPDATE` **solo** de `(state, attempts, model_frozen_after_recommendation, updated_at)`: decisión, `retry` y los barridos de BR-U8-10/14. **No** puede escribir `recommendation`, `recommendation_entry_id`, `last_cause` ni `escalation_count`, que son del worker. Un pod de la API comprometido no puede fabricar una recomendación.
- `guard_vencido` ya rechaza `vencido` de cualquier rol distinto de `case_retention` (P-U8-05), así que cubre a `case_worker` sin cambios.
- **Transiciones permitidas por rol** (hallazgo 3 de la revisión; precisa BR-U8-12, porque un `CHECK` de PostgreSQL no puede consultar otra tabla):
  - tabla `case_transitions (from_state, to_state, db_role)`, con clave primaria sobre las tres columnas, cargada por la migración;
  - trigger `guard_transition` (`BEFORE INSERT OR UPDATE OF state ON cases`), `SECURITY DEFINER`, propiedad de `case_migrator` y con `SET search_path = pg_catalog, public`. Así ningún rol de la aplicación necesita permisos sobre `case_transitions`;
  - en `UPDATE`, si `NEW.state <> OLD.state`, exige que exista `(OLD.state, NEW.state, session_user)`; si no, excepción. Usa `session_user` y no `current_user`, porque dentro de una función `SECURITY DEFINER` `current_user` es el dueño (`case_migrator`). Cada proceso se conecta directamente con su rol (sin `SET ROLE`), así que `session_user` es `case_app`, `case_worker` o `case_retention`. Esto depende de P-U1-08 (sin PgBouncer, conexiones directas a CloudNativePG): con un pooler que compartiera conexiones entre roles, `session_user` dejaría de identificar al proceso, y habría que revisar este trigger antes de introducirlo (revisión 2026-10-08, N2);
  - en `INSERT`, exige `state = 'en_evaluacion'`, `recommendation IS NULL`, `recommendation_entry_id IS NULL` y el rol `case_app`;
  - `guard_vencido` (P-U8-05) sigue a cargo de la comprobación de fecha.

  | De | A | Rol |
  |---|---|---|
  | `en_evaluacion`, `en_sincronizacion` | `listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado` | `case_worker` |
  | `modelo_congelado`, `no_disponible` | `en_evaluacion` | `case_app` (barrido de BR-U8-10, `retry`) |
  | `listo` | `decidido` | `case_app` |
  | `en_evaluacion`, `listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado` | `vencido` | `case_retention` |

  La transición `en_evaluacion` → `en_sincronizacion` → `no_disponible` de la tabla de BR-U8-12 queda cubierta: `no_disponible` solo se alcanza desde un estado de evaluación y por el worker.
- **Flujos**: F15 pasa a tener origen `case-worker`; F104 y F40 suman `case-worker` como origen. La `NetworkPolicy` y la `AuthorizationPolicy` de scoring admiten solo `case-worker`, y las de governance admiten `case-service` (solo `serving-config`) y `case-worker`.
- Credenciales: la llave privada de cada cliente de Keycloak (`private_key_jwt`) llega por un `ExternalSecret` (U2). La contraseña de cada rol de base es un `Secret` de los roles gestionados de CloudNativePG (U1).
- **Satisface**: SECURITY-06, 08; AUTONOMIA-03; NFR-U8-41, 45.
- **Verificación**:
  - prueba de migraciones con Testcontainers: `case_worker` intenta leer `decisions`, borrar `case_identifiers` y escribir `vencido` → error; `case_app` intenta `DELETE` sobre `evaluation_jobs` → error;
  - `case_worker` inserta en `evidence_outbox` una entrada `fail_closed` → éxito; con cualquier otro `entry_type` (`human_decision`, `explanation_view`) → error de la política RLS; `case_app` inserta los tres tipos → éxito;
  - `case_worker` repite el `INSERT` con la misma llave dentro de un `SAVEPOINT` → `unique_violation`, se vuelve al `SAVEPOINT` y la transacción del escalamiento confirma;
  - `case_app` intenta `UPDATE cases SET recommendation = …` y `SET recommendation_entry_id = …` → error de permisos; `INSERT` de un caso en `listo` o con `recommendation` → excepción de `guard_transition`;
  - para cada fila de `case_transitions`, el rol indicado puede hacer la transición; cualquier otro rol, o un par que no está en la tabla, → excepción; ningún rol de la aplicación puede leer ni escribir `case_transitions`;
  - suite de conectividad de U1 en kind: `case-service` → scoring → denegado; `case-worker` → scoring → permitido; `case-worker` → registro y core → denegados;
  - prueba del realm de U2: el cliente `case-service` no obtiene un token con `case:recommend`; en el realm de producción tampoco con `core:read-credit` ni para la audiencia `core-banking-mock` (INF-U8-02).

## 2. `core-banking-mock` (Q2, Q3)

### INF-U8-02 — Validación de tokens, entornos, fixtures y core deshabilitado en producción (Q2; aclaración Q1 = A)
- El mock está en **F50, solo para el JWKS** de Keycloak, sin client credentials. Valida firma, `aud = core-banking-mock` y scope con `vectra_common` (U0).
- Se despliega **solo en kind y staging**. El value `coreMock.enabled` es `false` en los values de producción, y una regla de `conftest` lo verifica.
- **Core deshabilitado en producción para el MVP** (aclaración del hallazgo 1, respuesta A):
  - value `core.enabled` de `case-service`: `true` en kind y staging, **`false` en producción**; una regla de `conftest` sobre los values de producción lo verifica, junto con `coreMock.enabled = false`;
  - con `core.enabled = false`, `get_case` responde `credit_status = no_disponible` **sin llamar** a nada y **sin contar para el circuit breaker**: es una configuración, no una falla (BR-U8-21, NFR-U8-25, 31). La consola lo muestra como «estado de crédito no integrado» (pendiente para U10);
  - en producción no existe F17 ni X01, y `CoreWriteAttempt` no se despliega (no hay mock ni proxy que la alimente);
  - el cliente `case-service` del realm de producción no tiene `core:read-credit` ni la audiencia `core-banking-mock` (U2 domain-entities §2.2);
  - la integración con el core real queda **pendiente para Operations** (§8): flujo de egress propio en §5 de `component-dependency.md`, revisión de seguridad y un equivalente de X01 fuera de la malla (por ejemplo, un egress gateway que solo admita `GET`).
- Los fixtures van **dentro de la imagen** (`/app/fixtures/credits.json`), versionados y firmados con ella. No hay ConfigMap ni volumen.
- 2 réplicas, PDB `minAvailable: 1`, `vectra-low`, en el namespace `vectra-mock` (NFR-U8-26).
- **Verificación**:
  - `conftest` sobre los values de producción: `coreMock.enabled = false` y `core.enabled = false`;
  - prueba de ejemplo: un token sin `core:read-credit` → 403;
  - prueba de integración con `core.enabled = false` y un core doble que registra las llamadas: `get_case` de un caso `decidido` → `credit_status = no_disponible`, cero llamadas al doble y el breaker del core sigue cerrado sin registrar fallos;
  - suite de conectividad: el mock alcanza el JWKS de Keycloak y nada más.
- **Satisface**: NFR-U8-25, 26, 31, 43; SECURITY-08; AUTONOMIA-03.

### INF-U8-03 — `CoreWriteAttempt` por la primera capa que ve el intento (Q3; P-U8-06, X01)
- La alerta queda así:

  ```text
  increase(vectra_core_write_attempts_total[5m]) > 0
  or
  sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"})
    - (sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"} offset 5m) or vector(0))
    > 0
  ```

  - La segunda serie es la denegación del proxy de Linkerd del mock, **filtrada por la ruta de captura**. Otra denegación del mock, como un scrape mal autorizado, no dispara la alerta (hallazgo 6 de la revisión).
  - **No usa `increase()`** (hallazgo 4): la serie de Linkerd nace en 1 con la primera denegación, e `increase()` no contaría ese primer evento. La resta contra `offset 5m`, con `or vector(0)` cuando la serie todavía no existía, sí lo cuenta.
  - La primera serie puede usar `increase()`, porque el mock la crea en 0 al arrancar (P-U8-06).
  - **Limitación (para el runbook)** (revisión 2026-10-08, N3): el contador de Linkerd vive en el proxy del pod del mock. Si ese pod se reemplaza dentro de los 5 min posteriores a un evento, la serie nueva arranca de nuevo en 1 y la resta contra `offset 5m` del pod anterior puede dar ≤ 0 y ocultar el evento siguiente. El runbook de `CoreWriteAttempt` indica revisar también los logs de denegación del proxy y del mock cuando hubo un reinicio del mock cerca del evento.
- **Las tres capas de X01**:
  1. la `NetworkPolicy` descarta cualquier origen distinto de `case-service`, sin métrica. Ya lo prueba la suite de conectividad de U1;
  2. Linkerd rechaza un método distinto de `GET` desde `case-service` → `inbound_http_authz_deny_total`. Para eso el `Server` del mock tiene, además de la `HTTPRoute` de `GET /v1/credits/{id}` autorizada, una `HTTPRoute` de captura llamada `core-mock-catch-all` (`/`, cualquier método) **sin** `AuthorizationPolicy`. La alerta filtra por ese nombre (`route_name`). Sin ella, una solicitud que no coincide con ninguna ruta terminaría en 404 sin ruta y no en una denegación medida;
  3. si Linkerd estuviera mal configurado, el mock responde 403 por scope y registra el `WriteAttempt`. La descripción de la alerta distingue las dos series: la segunda indica además una configuración rota.
- **Demostración de RT-5** (U12): un Job con la ServiceAccount `case-service`, solo en kind y staging, envía `POST /v1/credits/{id}/status`. La evidencia esperada es el 403 del proxy y la alerta.
- El Job corre en `vectra-app` y su pod lleva la etiqueta `app.kubernetes.io/name: case-service`, que es la que admite la `NetworkPolicy` del mock. Sin ella, la `NetworkPolicy` lo descartaría sin métrica y la demostración no probaría la capa L7 (hallazgo 5 de la revisión).
- Ese Job de demostración tiene la ServiceAccount `case-service`, pero no tiene su llave de Keycloak: no obtiene tokens.
- **Verificación**:
  - `promtool test rules` con cada serie por separado. El caso de Linkerd **arranca en 1** (la serie nace con la primera denegación) y debe disparar; una denegación con otro `route_name` no dispara;
  - en kind (operador), la demostración dispara `CoreWriteAttempt` y `vectra_core_write_attempts_total` sigue en 0.
- Solo existe en kind y staging, como el mock (INF-U8-02).
- **Satisface**: NFR-U8-45(b); SECURITY-11, 14; RT-5.

## 3. Cómputo (Q4, Q5)

### INF-U8-04 — Recursos, escalado y probes (Q4)

| Componente | Requests | Limits | Escalado | PriorityClass |
|---|---|---|---|---|
| `case-service` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA de 2 a 6 por CPU al 70 % (estabilización 60 s hacia arriba / 300 s hacia abajo); spread por zona; PDB `minAvailable: 1` | `vectra-high` |
| `case-worker` | 200m / 256 MiB | 1 CPU / 512 MiB | Igual | `vectra-high` |
| `case-retention` (CronJob) | 100m / 128 MiB | 500m / 256 MiB | 1 pod por corrida (P-U8-07) | `vectra-low` |
| Job de migración | 100m / 128 MiB | 500m / 256 MiB | 1 pod (hook de sync, F44) | `vectra-low` |
| `core-banking-mock` | 50m / 64 MiB | 250m / 128 MiB | 2 réplicas fijas; spread por zona; PDB `minAvailable: 1` | `vectra-low` |

- Readiness (`/readyz`, 8081) cada 5 s, solo con `case-db` (NFR-U8-21); liveness (`/livez`) cada 10 s, solo con el proceso (P-U1-04).
- El CronJob y el Job de migración llevan la anotación del sidecar nativo de Linkerd, para que el Job termine cuando termina el contenedor (como `restore-drill`, P-U1-05).
- Los valores son iniciales y se ajustan con la prueba de carga de U12.
- **Verificación**: `helm template` + `conftest`: requests y limits presentes, HPA 2–6, PDB, `topologySpreadConstraints`, `priorityClassName` y la anotación del sidecar en los Jobs.

### INF-U8-05 — Aporte a las cuotas (NFR-U1-13)

| Namespace | Concepto | CPU | Memoria |
|---|---|---|---|
| `vectra-app` | Requests: 6 × 250m + 6 × 200m + CronJob + migración = 2,9 CPU; 12 × 256 MiB + 2 × 128 MiB = 3 328 MiB | **3,77** con el 30 % | **≈ 4,2 GiB** con el 30 % |
| `vectra-app` | Limits: 12 × 1 CPU + 2 × 500m = 13 CPU; 12 × 512 MiB + 2 × 256 MiB = 6 656 MiB | **16,9** con el 30 % | **≈ 8,45 GiB** con el 30 % |
| `vectra-mock` | Requests / limits del mock (2 pods) con el 30 % | 0,13 / 0,65 | 166 / 333 MiB |

- U1 compone la `ResourceQuota` de cada namespace con los aportes de las unidades (INF-U7-02).
- **Verificación**: la prueba del chart de U1: cada cuota ≥ la suma de los aportes declarados.

### INF-U8-06 — Apagado ordenado (Q5)
- **`case-service`**, como INF-U7-03:
  - `preStop.sleep.seconds: 5`;
  - uvicorn con `timeout_graceful_shutdown = 10`;
  - `terminationGracePeriodSeconds: 20`, por encima del append de la decisión (2,5 s);
  - al recibir `SIGTERM`, los barridos y el reconciliador dejan de tomar trabajo y terminan el lote en curso.
- **`case-worker`**:
  - no expone tráfico de entrada aparte de métricas y probes, así que no necesita `preStop`;
  - al recibir `SIGTERM` deja de sondear la cola y espera las llamadas en vuelo hasta 20 s;
  - `terminationGracePeriodSeconds: 30`, por encima del peor caso de 15,5 s (P-U8-01);
  - lo que no termine se retoma al vencer el arrendamiento de 30 s.
- El proxy nativo de Linkerd termina después del contenedor de la app.
- **Resultado**: un despliegue o un escalado hacia abajo no produce recomendaciones no entregadas (P-U7-03).
- **Verificación**:
  - `conftest`: `preStop.sleep` y `terminationGracePeriodSeconds ≥ 20` en `case-service`, `≥ 30` en `case-worker`;
  - prueba de integración: con un scoring doble que responde a los 10 s, `SIGTERM` al worker a los 0,5 s → el intento termina y el caso queda `listo`;
  - en kind (operador): un `rollout restart` de `case-worker` durante la prueba de carga no deja `evaluation.result_discarded`.
- **Satisface**: RESILIENCY-04, 10; AUTONOMIA-06; P-U7-03.

## 4. Configuración (Q6)

### INF-U8-07 — Constantes en el código; values solo para el entorno y cumplimiento
- **Constantes tipadas** en `vectra_case/config.py`: timeouts (NFR-U8-30), tamaños de pool y límite del reconciliador (P-U8-02), umbrales del circuit breaker (NFR-U8-31), backoff (BR-U8-07), arrendamiento y sondeo (P-U8-01), lotes (P-U8-01, 07), plazo de abandono de 24 h (BR-U8-18) y gracia del worker (INF-U8-06).
- **Values de Helm**:
  - URLs y audiencias de las dependencias;
  - endpoint de telemetría y nivel de log;
  - `allowTestScenarios` (`false` en producción, verificado por política; NFR-U8-44);
  - `retention.decided_years`, `retention.undecided_years` y `retention.intake_keys_days` (P-U8-05);
  - `retention.schedule` y `retention.timeZone` (P-U8-07);
  - `coreMock.enabled` y `core.enabled` (INF-U8-02).
- **Verificación**:
  - prueba unitaria: `WORKER_WORST_CASE (15,5 s) < LEASE (30 s)` y `WORKER_WORST_CASE < WORKER_SHUTDOWN_GRACE (20 s) < terminationGracePeriodSeconds (30 s)`;
  - `RECONCILER_CONCURRENCY (4) < REGISTRY_POOL (10)`;
  - prueba del chart: ninguna de las constantes aparece como variable de entorno.
- **Satisface**: AUTONOMIA-02; SECURITY-11.

## 5. Almacenamiento (Q7)

### INF-U8-08 — `case-db` de 50 Gi con vigilancia del crecimiento
- **Estimado**: ~25 KB por caso (`application` 3 KB; `recommendation` con la `Explanation` 12 KB; outbox, decisión e índices 10 KB). 50 Gi alcanzan para **≈ 2 millones de casos**. El volumen anual del banco es **[VERIFICAR]** (el PRD no lo da).
- **Alerta de volumen: la de U1** (revisión 2026-10-08, hallazgo 7'). U1 ya define `PostgresVolumeUsageHigh` (INF-U1-02) para los cuatro `Cluster` de PostgreSQL, `case-db` incluido: 80 % → SEV3, 90 % → SEV2, con el caso `absent()` si el kubelet deja de reportar el volumen. U8 no define una alerta propia; se retiró `CaseDbVolumeFilling`.
- **Ampliación**: cambio del `storage.size` del `Cluster` en los values, con la expansión de volumen de la StorageClass de U1. No requiere migración.
- La prueba de carga de U12 mide el tamaño real por caso y actualiza el estimado.
- **Verificación**: el `promtool test rules` de `PostgresVolumeUsageHigh` (U1) incluye una serie de `case-db`; en kind (operador), ampliar el volumen de `case-db` sin reiniciar el `Cluster`.
- **Satisface**: RESILIENCY-05, 09.

## 6. Cumplimiento de extensiones (Infrastructure Design U8)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | INF-U8-04 (`vectra-high`; RPO y RTO de `case-db` heredados de U1) |
| RESILIENCY-04 | Cumple | INF-U8-06 |
| RESILIENCY-05 / 07 / 15 | Cumple | INF-U8-03 (alerta con severidad y `runbook_url`); INF-U8-08 (volumen vigilado por `PostgresVolumeUsageHigh` de U1) |
| RESILIENCY-08 / 09 | Cumple | INF-U8-04, 05, 08 |
| RESILIENCY-10 | Cumple | INF-U8-06 |
| RESILIENCY-14 | Cumple | P-U8-09 (enfoque C); sin cambios aquí |
| SECURITY-06 / 08 | Cumple | INF-U8-01 (tres identidades, tres roles de base, `UPDATE` por columna y RLS de `evidence_outbox`), INF-U8-02 (core deshabilitado y sin scopes de core en producción) |
| SECURITY-11 | Cumple | INF-U8-03 (RT-5 con evidencia en cada capa), INF-U8-07 (`allowTestScenarios` por política) |
| SECURITY-14 | Cumple | INF-U8-03 |
| AUTONOMIA-01 | Cumple | `Application` de Argo CD con sync manual (deployment-architecture) |
| AUTONOMIA-02 | Cumple | Cada `INF-U8-xx` tiene su «Verificación» |
| AUTONOMIA-03 | Cumple | INF-U8-01, 02, 03 |
| AUTONOMIA-06 | Cumple | INF-U8-06 |

## 7. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| `component-dependency.md` (F15, F40, F50, F104, §4, diagrama, X01) | F15 con origen `case-worker`; F40 y F104 con `case-worker`; F50 con `core-banking-mock` (solo JWKS); rol `case_worker` y `case_app` sin `UPDATE` ni `DELETE` sobre `evaluation_jobs`; nodo `case-worker` en el diagrama; X01 con la evidencia de cada capa | Q1, Q2, Q3 |
| U0 domain-entities §7.2 | `case:recommend` y `governance:read-feature-spec` pasan a `case-worker`; `governance:read-serving` para `case-service` y `case-worker` | Q1 |
| U2 domain-entities §2 (clientes) | Cliente nuevo `case-worker`; `case-service` sin `case:recommend` ni `governance:read-feature-spec` | Q1 |
| U7 infrastructure-design INF-U7-05, deployment-architecture §1, logical-components §2 | El origen de F15 es `case-worker` | Q1 |
| U8 NFR-U8-41; nfr-design P-U8-06 y logical-components §1 | Rol `case_worker`; `CoreWriteAttempt` con las dos series | Q1, Q3 |
| U8 NFR-U8-41 | Credenciales de `case-db` por proceso y rol (antes «solo case-service») | Revisión, hallazgo 8 |
| U8 NFR-U8-45(b) | `CoreWriteAttempt` también por la denegación del proxy | Revisión, hallazgo 8 |
| U8 BR-U8-12; `component-dependency.md` §4; logical-components §1 | `case_transitions` con rol y trigger `guard_transition` (`SECURITY DEFINER`); `UPDATE` por columna de `case_app` | Revisión, hallazgos 2 y 3 |
| U8 logical-components §1 y §3; P-U8-06 | Caché de gobierno en `case-worker`; pendientes resueltos; la prueba del `WriteAttempt` es del mock aislado | Revisión, hallazgos 9 y 10 |
| U8 business-rules §8, business-logic-model §1; `component-dependency.md` §1, §3, §5, §6, §7 y §8 | Filas viejas anotadas; `evaluation` en `case-worker`; textos al día con `case-worker` y `case-retention` | Revisión, hallazgos 11 y 12 |
| U7 P-U7-02, P-U7-03, §8; business-rules §6; domain-entities §6 | `case-worker` como cliente de scoring; filas de U8 resueltas; caché del diccionario LRU de 4 versiones | Revisión, hallazgos 13 a 15 |
| U8 business-rules BR-U8-22 y §8 | Evidencia de RT-5 en el proxy; filas de los cambios | Q3 |
| U1 deployment-architecture (`vectra-mock`) | El mock solo existe en kind y staging | Q2 |
| U8 BR-U8-21, BR-U8-22, NFR-U8-25, 31, 43; P-U8-06; deployment-architecture; `component-dependency.md` F17, X01, §5 y §7 | Core deshabilitado en producción (`core.enabled = false`): `no_disponible` sin llamar y sin contar para el breaker; F17, X01 y `CoreWriteAttempt` solo en kind y staging; nota en §5 | Aclaración Q1 = A; revisión 2026-10-08, hallazgo 1 |
| U2 domain-entities §2.2 | El cliente `case-service` del realm de producción no tiene `core:read-credit` ni la audiencia `core-banking-mock`; prueba del realm | Revisión 2026-10-08, U2-a |
| U8 logical-components §1; `component-dependency.md` §4 | RLS en `evidence_outbox`: `case_worker` solo inserta `fail_closed` | Revisión 2026-10-08, N1 |
| U8 INF-U8-08, §8 | Se retira `CaseDbVolumeFilling`; se cita `PostgresVolumeUsageHigh` de U1 | Revisión 2026-10-08, hallazgo 7' |
| U8 business-rules §8; business-logic-model §1 | La fila de INF-U8 cita NFR-U8-45; `case_fsm` y `backoff` también en `case-worker`; `retention` en `case-retention` | Revisión 2026-10-08, N4 y N5 |
| U1 INF-U1-02, logical-components §1, §3 y §4, P-U1-04, P-U1-09, tech-stack-decisions §1–§4, NFR-U1-27 | `absent()` en `PostgresVolumeUsageHigh` y fila en la tabla de alertas; readiness de `case-worker`; `core-banking-mock` en `vectra-low`; textos de kind, MinIO, Calico y Alloy al día; bindings hasta K14 | Revisión 2026-10-08, 7'-U1 y U1-a..f |
| U7 INF-U7 §5; nfr-design-patterns §8; logical-components §3; domain-entities §6 | Pendientes de U8 marcados como resueltos; una sola fila para la caché del diccionario | Revisión 2026-10-08, U7-a..d |

## 8. Pendientes
- **Para U1** (Code Generation, chart): sumar los aportes de INF-U8-05 (y de INF-U7-02) a las cuotas de `vectra-app` y `vectra-mock` (NFR-U1-13; revisión 2026-10-08, U1-g).
- **Para Operations**: integración con el core real del banco (INF-U8-02): contrato del API **[VERIFICAR]**, flujo de egress en §5 de `component-dependency.md` (host, puerto y TLS), revisión de seguridad, equivalente de X01 fuera de la malla (egress gateway que solo admita `GET /v1/credits/{id}`), `CoreWriteAttempt` alimentado por ese gateway y el scope `core:read-credit` en el realm de producción.
- **Para U10**: mostrar `credit_status = no_disponible` con `core.enabled = false` como «estado de crédito no integrado».
- **Para U12**: Job de demostración de RT-5 (INF-U8-03) y medición del tamaño por caso (INF-U8-08).
- **Para el plan de tareas de U8**: CLI `case-retention` (ya pendiente del FD), migración con los cuatro roles y la fila de `retention_settings`, `PrometheusRule` con todas las alertas de P-U8 e INF-U8.
