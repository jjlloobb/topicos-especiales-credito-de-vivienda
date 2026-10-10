# Servicios y orquestación — Vectra Risk

Patrón general: HTTP síncrono entre servicios dentro del clúster, con mTLS o TLS según lo
que se defina en NFR Design. El trabajo diferido (reintentos, cálculos periódicos) usa una
**cola transaccional en PostgreSQL** y **CronJobs**. No hay broker de mensajes (Q4=A).

Cada servicio es **dueño de sus datos**:
- `case-db` pertenece a case-service;
- `governance-db` pertenece a governance-service;
- `registry-db` pertenece a decision-registry-service.

Ningún servicio lee la base de otro: todo pasa por API. La topología física de
PostgreSQL (un clúster con varias bases o varios clústeres) se decide en Infrastructure
Design.

---

## S1 — Originación explicada (journey 7.1, US-101..108)

1. El `channel-simulator` (o el analista, vía BFF) envía la solicitud. `case-service` la valida, la guarda y crea el caso en `en_evaluacion`. Luego encola `evaluate(case_id)`.
2. El worker de `case-service` lee de governance la versión activa y su `feature_spec` (F104), arma con `derive` el `FeatureVector` y las etiquetas de monitoreo, y llama a `scoring-service.recommend` con esa `model_version_id` (precisado el 2026-10-06).
3. `scoring-service`:
   1. lee `serving-config` de governance, con caché corta. Si el modelo está congelado → `FailClosed(model_frozen)`. Si `ScoringRequest.model_version_id` no es la versión activa → `FailClosed(version_mismatch)` sin llamar a KServe ni al explicador (precisado el 2026-10-06: comparación de versión de U8 FD Q1);
   2. llama a `predict` en KServe;
   3. aplica la política;
   4. llama a `explainability-service.explain` con el mismo `model_version_id`;
   5. comprueba la igualdad de versión;
   6. hace `append` de la recomendación en el registro, que espera la confirmación síncrona;
   7. devuelve la `Recommendation`.
4. `case-service` pasa el caso a `listo`.
5. El analista abre el detalle de la explicación: el BFF llama a `record_explanation_view` y **case-service** escribe `explanation_view` en el registro, con la recomendación consultada, solo la primera vez por caso y usuario (BR-U8-19). Una apertura posterior responde 204 sin evento nuevo (precisado el 2026-10-06).
6. El analista registra su decisión, con factores y texto. `case-service` hace `append(human_decision)` y pasa el caso a `decidido`.

## S2 — Desincronía y fail-closed (journey 7.3, US-111..113)

- La versión pedida distinta de la activa (paso 3.1) y cualquier fallo de los pasos 3.4–3.6 devuelven `FailClosed` con `retryable=true`: versión distinta, explicador ausente, error, timeout, factualidad fallida o registro sin confirmar. **No se usa ningún respaldo** (AUTONOMIA-06).
- `case-service` pasa el caso a `en_sincronizacion` y reprograma el trabajo con backoff exponencial y un límite: 6 intentos, unos 15,5 min de esperas (BR-U8-07) (precisado el 2026-10-06).
- Si se agotan los reintentos, el caso pasa a `no_disponible` y sube la métrica `vectra_cases_failclosed_persistent`. Alertmanager dispara `FailClosedPersistente` y el caso aparece en `list_persistent_failures` (consola del CRO).
- Cada `FailClosed` que emite scoring también se agrega al registro (`fail_closed`), con fines de auditoría y métricas. Los intentos que fallan antes de llegar a scoring no tienen entrada propia: quedan en el caso y, si el caso escala, en la entrada de escalamiento (BR-U8-09) (precisado el 2026-10-06, revisión del FD de U8). scoring escribe la entrada de cada intento (BR-U7-16) y case-service escribe una sola al agotar los reintentos (BR-U8-09) (precisado el 2026-10-06 por U8 FD Q4).

## S3 — Promoción de versión de modelo (journey 7.2, US-201..204, US-208)

1. El ingeniero sube el artefacto y el explicador a `model-store` y registra la versión en governance con su checksum.
2. Pide la validación: governance lanza el `model-validation-job` en staging. El job envía el informe (AUC, sesgo inicial, sincronía).
3. La versión pasa a `lista_para_aprobacion`. El CRO, con MFA, aprueba desde la consola. El evento va al registro.
4. Un humano ejecuta `promotion-tool create_promotion_pr`. El PR lleva un **solo commit** con predictor + explainer y la evidencia (`helm template`, `kubectl diff`). CI ejecuta sus verificaciones.
5. Revisión y merge humanos, luego **sync manual** en Argo CD (AUTONOMIA-01). Tras el sync, el ingeniero ejecuta `mark_active`. Solo entonces `serving-config` apunta a la nueva versión.
6. Rollback: PR de revert + sync manual + `mark_active` de la versión anterior.

## S4 — Vigilancia y congelamiento (journey 7.4, US-301..308)

1. El CronJob de `bias-monitoring` lee del registro **conteos agregados** por día (`monitoring_daily`, que mantiene el agregador de U3 con una recomendación por caso) y calcula la disparidad por grupo y por banda, y la agregada ponderada por banda (U9 FD, 2026-10-08).
2. Si la disparidad agregada del **modelo** supera el umbral (5 pp) y el límite inferior de su intervalo es > 0 (U9 BR-U9-11), ejecuta `governance.freeze_model(mv_id, contexto)` con su identidad acotada. Governance cambia el estado a `congelado` de inmediato y agrega el evento `freeze` al registro, con `frozen_at`; si el registro está caído, lo reintenta el reconciliador (BR-U4-17) (precisado el 2026-10-06). Sube la métrica, que dispara la alerta `ModeloCongelado`.
3. Desde ese momento, scoring devuelve `FailClosed(model_frozen)` para nuevas solicitudes y `case-service` marca los casos como `modelo_congelado`. Los casos `listo` de esa versión siguen `listo`, con el aviso `model_frozen_after_recommendation` (BR-U8-14) (precisado el 2026-10-06).
4. Cumplimiento revisa el paquete en la consola y ejecuta `resolve_frozen`. **Ninguna** otra ruta saca un modelo de `congelado` (AUTONOMIA-04).
5. La disparidad de las **decisiones humanas** se calcula y se alerta, pero **no** congela.
6. Si el último cálculo tiene más de W de antigüedad, se dispara la alerta `MonitoreoSesgoDetenido`. Resuelto en el FD de U4: el modelo **sigue sirviendo**; la alerta es SEV2 y pasa a SEV1 si supera 2W (NFR-RES-11) (precisado el 2026-10-06). W = 1 h y la alerta sale de `vectra_bias_last_success_timestamp` (U9 BR-U9-21; U9 FD, 2026-10-08).

## S5 — Fuente de datos nueva (US-306)

El ingeniero propone la fuente en governance junto con una versión candidata que la
declara. El `model-validation-job` puntúa el dataset de validación con la versión activa
(antes) y con la candidata (después) y devuelve tablas de conteo por atributo. Governance las
envía a bias por `compare_source` (F25). Cumplimiento decide y el evento va al registro. La
fuente solo se usa si queda aprobada (U9 FD, 2026-10-08).

## S6 — Política de negocio (US-205..207)

El CRO propone una versión de política, que queda como `propuesta`, y la aprueba con MFA:
pasa a `activa` y la anterior a `histórica`. Scoring la ve en su siguiente lectura de
`serving-config`. Scoring **no tiene** permisos de escritura sobre la política.

## S7 — Expediente y auditoría (caso de uso 2, US-401..404, US-110)

El CRO o cumplimiento pide `get_case_dossier`. El registry compone el expediente con las
entradas del caso y el resultado de `verify_chain`. El resumen para el solicitante lo
genera explainability a partir de la explicación registrada, y **nunca recalcula** con
otra versión.

## S8 — Métricas de producto (US-501..505)

`product-metrics` consulta el registro periódicamente y expone las métricas de negocio.
Prometheus las recoge, las recording y alerting rules calculan `RuidoExplicacion` y
Grafana presenta los dashboards de producto.

## S9 — Autenticación y autorización (US-601, US-602)

La SPA hace el login OIDC con PKCE contra Keycloak. El gateway valida el JWT. El BFF
autoriza por función y por objeto. Cada servicio vuelve a validar el JWT y el rol o
scope: el de usuario propagado, o el de servicio obtenido por client credentials con
scopes mínimos (p. ej. `governance:freeze` solo para `bias-monitoring-job`, el CronJob de U9; el servicio HTTP de bias no lo tiene; quinta revisión del FD de U9, 2026-10-10).
