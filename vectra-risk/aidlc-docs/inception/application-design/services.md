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
2. El worker de `case-service` llama a `scoring-service.recommend` con features y etiquetas de monitoreo.
3. `scoring-service`:
   1. lee `serving-config` de governance, con caché corta. Si el modelo está congelado → `FailClosed(model_frozen)`;
   2. llama a `predict` en KServe;
   3. aplica la política;
   4. llama a `explainability-service.explain` con el mismo `model_version_id`;
   5. comprueba la igualdad de versión;
   6. hace `append` de la recomendación en el registro, que espera la confirmación síncrona;
   7. devuelve la `Recommendation`.
4. `case-service` pasa el caso a `listo`.
5. El analista abre el caso: el BFF registra `explanation_view` al abrir el detalle.
6. El analista registra su decisión, con factores y texto. `case-service` hace `append(human_decision)` y pasa el caso a `decidido`.

## S2 — Desincronía y fail-closed (journey 7.3, US-111..113)

- Cualquier fallo del paso 3.d–3.f devuelve `FailClosed` con `retryable=true`: versión distinta, explicador ausente, error, timeout, factualidad fallida o registro sin confirmar. **No se usa ningún respaldo** (AUTONOMIA-06).
- `case-service` pasa el caso a `en_sincronizacion` y reprograma el trabajo con backoff exponencial y un límite. Parámetros en Functional Design.
- Si se agotan los reintentos, el caso pasa a `no_disponible` y sube la métrica `vectra_cases_failclosed_persistent`. Alertmanager dispara `FailClosedPersistente` y el caso aparece en `list_persistent_failures` (consola del CRO).
- Cada fail-closed también se agrega al registro (`fail_closed`), con fines de auditoría y métricas. scoring escribe la entrada de cada intento (BR-U7-16) y case-service escribe una sola al agotar los reintentos (BR-U8-09) (precisado el 2026-10-03 por U8 FD Q4).

## S3 — Promoción de versión de modelo (journey 7.2, US-201..204, US-208)

1. El ingeniero sube el artefacto y el explicador a `model-store` y registra la versión en governance con su checksum.
2. Pide la validación: governance lanza el `model-validation-job` en staging. El job envía el informe (AUC, sesgo inicial, sincronía).
3. La versión pasa a `lista_para_aprobacion`. El CRO, con MFA, aprueba desde la consola. El evento va al registro.
4. Un humano ejecuta `promotion-tool create_promotion_pr`. El PR lleva un **solo commit** con predictor + explainer y la evidencia (`helm template`, `kubectl diff`). CI ejecuta sus verificaciones.
5. Revisión y merge humanos, luego **sync manual** en Argo CD (AUTONOMIA-01). Tras el sync, el ingeniero ejecuta `mark_active`. Solo entonces `serving-config` apunta a la nueva versión.
6. Rollback: PR de revert + sync manual + `mark_active` de la versión anterior.

## S4 — Vigilancia y congelamiento (journey 7.4, US-301..308)

1. El CronJob de `bias-monitoring` consulta el registro (recomendaciones y decisiones con `MonitoringLabels`) y calcula la disparidad por grupo y por banda, y la agregada.
2. Si la disparidad agregada del **modelo** supera el umbral, ejecuta `governance.freeze_model(mv_id, contexto)` con su identidad acotada. Governance cambia el estado a `congelado` y agrega el evento `freeze` al registro. Sube la métrica, que dispara la alerta `ModeloCongelado`.
3. Desde ese momento, scoring devuelve `FailClosed(model_frozen)` para nuevas solicitudes y `case-service` marca los casos como `modelo_congelado`.
4. Cumplimiento revisa el paquete en la consola y ejecuta `resolve_frozen`. **Ninguna** otra ruta saca un modelo de `congelado` (AUTONOMIA-04).
5. La disparidad de las **decisiones humanas** se calcula y se alerta, pero **no** congela.
6. Si el último cálculo tiene más de W de antigüedad, se dispara la alerta `MonitoreoSesgoDetenido`. El efecto sobre el modelo queda **abierto para Functional Design** (NFR-RES-11).

## S5 — Fuente de datos nueva (US-306)

El ingeniero propone la fuente en governance. Governance pide a bias `compare_source`
(antes y después, en staging). Cumplimiento decide y el evento va al registro. La fuente
solo se usa si queda aprobada.

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
scopes mínimos (p. ej. `governance:freeze` solo para bias-monitoring).
