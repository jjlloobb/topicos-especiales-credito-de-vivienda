# Componentes — Vectra Risk

Decisiones de diseño aplicadas (plan `application-design-plan.md`, todas las respuestas A):
- **Q1** `governance-service` dedicado para modelos, políticas y fuentes.
- **Q2** `decision-registry-service` es el único escritor del registro.
- **Q3** `case-service` gestiona el ciclo de vida y los reintentos; `scoring-service` conserva la llamada síncrona a explicación.
- **Q4** HTTP síncrono, cola transaccional en PostgreSQL y CronJobs, sin broker.
- **Q5** Envoy Gateway con validación de JWT, más un BFF para la SPA; cada servicio vuelve a validar.
- **Q6** SHAP como `explainer` del mismo `InferenceService` de KServe.
- **Q7** El congelamiento es una transición en `governance-service` ejecutada con una identidad de servicio acotada.
- **Q8** `product-metrics` calcula las métricas de negocio desde el registro.

Criticidad (RESILIENCY-01): **Critical** si su pérdida compromete evidencia
regulatoria; **High** si detiene la ruta de recomendación o de vigilancia (el banco
sigue con su proceso manual gracias al fail-closed); **Medium** o **Low** en los demás
casos.

---

## C01 — `api-gateway` (Envoy Gateway)
- **Propósito**: único punto de entrada HTTP al namespace de Vectra Risk.
- **Responsabilidades**: terminación TLS; validación de JWT (firma, expiración, audiencia, emisor) contra Keycloak; rate limiting; límite de tamaño de payload; access log estructurado; enrutamiento a `console-bff` y a la API de ingesta de `case-service`.
- **Interfaces**: HTTPS público dentro de la red del banco (`/api/console/**` → BFF, `/api/intake/**` → case-service).
- **Criticidad**: High. Si cae, no hay ingesta ni consolas.
- **Restricciones**: SECURITY-02, -08, -11; NFR-SEC-02.

## C02 — `console-spa` (React + TypeScript)
- **Propósito**: una sola aplicación web con vistas por rol: analista, ingeniero de riesgo, CRO y cumplimiento.
- **Responsabilidades**: bandeja y detalle de casos; registro de decisión con justificación estructurada; aprobaciones de modelo y política; alertas de congelamiento; dashboards embebidos; textos i18n en español.
- **Interfaces**: consume solo `console-bff`. Login OIDC con Keycloak (Authorization Code + PKCE).
- **Criticidad**: Medium.
- **Restricciones**: SECURITY-04 (cabeceras), FR-UI-07 (la UI oculta, pero no protege), FR-BIA-08 (frases prohibidas).

## C03 — `console-bff` (FastAPI)
- **Propósito**: backend-for-frontend de la SPA.
- **Responsabilidades**: componer vistas desde case, governance, registry y bias; autorizar por función y por objeto antes de llamar a los servicios; propagar el token del usuario y el correlation ID; devolver errores genéricos.
- **Interfaces**: REST `/api/console/**` (OpenAPI).
- **Criticidad**: High para las consolas.
- **Restricciones**: SECURITY-05, -08, -15. No almacena estado propio.

## C04 — `case-service` (FastAPI + PostgreSQL `case-db`)
- **Propósito**: dueño de la solicitud y del caso.
- **Responsabilidades**:
  - recibir solicitudes del simulador y del alta manual, y validarlas por esquema;
  - guardar los datos del solicitante (PII) en `case-db`;
  - manejar los estados del caso: `en_evaluacion`, `listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado`, `decidido`;
  - invocar a `scoring-service` y reintentar con backoff mediante una cola transaccional (`SKIP LOCKED`);
  - escalar los casos persistentes (métrica que dispara la alerta `FailClosedPersistente`, más la lista para la vista del CRO);
  - recibir la decisión humana y los eventos de consulta de la explicación, y enviarlos al registro;
  - leer el estado del crédito (solo lectura) del core simulado.
- **Interfaces**: REST de ingesta (vía gateway) y REST interno para el BFF.
- **Criticidad**: High.
- **Restricciones**: FR-ING-04 (el texto libre es dato); AUTONOMIA-03 (solo `GET` hacia el core); SECURITY-05.

## C05 — `scoring-service` (FastAPI)
- **Propósito**: producir la **recomendación usable** o un fail-closed.
- **Responsabilidades**:
  - leer de `governance-service` la versión de modelo activa, su estado (congelado o no) y la política vigente;
  - invocar al predictor de KServe;
  - aplicar el **motor de política** (punto de corte, baja confianza, VIS y tope de usura);
  - pedir la explicación a `explainability-service` en el mismo request y verificar que el `model_version_id` sea idéntico;
  - persistir la recomendación en el registro **antes** de responder;
  - si algo falla, responder con el estado fail-closed tipificado.
- **Interfaces**: REST interno `POST /v1/recommendations` (solo lo llama `case-service`).
- **Criticidad**: High.
- **Restricciones**: AUTONOMIA-03 (sin escritura de estado de crédito); AUTONOMIA-05 (sin egress); AUTONOMIA-06; SECURITY-15.

## C06 — `explainability-service` (FastAPI)
- **Propósito**: una explicación fiel, legible y de la misma versión.
- **Responsabilidades**: pedir el vector SHAP al `explainer` del `InferenceService` de la versión solicitada; rechazar si la versión no coincide o no hay explicador; generar la narrativa con el `NarrativeGenerator` activo (plantilla determinística en el MVP); validar la factualidad contra el vector; generar el resumen para el solicitante (US-110).
- **Interfaces**: REST interno `POST /v1/explanations` (solo lo llama `scoring-service`) y `POST /v1/applicant-summaries` (vía BFF, con rol CRO o analista).
- **Criticidad**: High. Sin este servicio no hay recomendaciones usables.
- **Restricciones**: AUTONOMIA-05, AUTONOMIA-06 (sin respaldo genérico); FR-EXP-06 (interfaz reemplazable).

## C07 — `model-serving` (KServe `InferenceService`: predictor + explainer)
- **Propósito**: servir cada versión de modelo **junto con su explicador SHAP** en una sola revisión.
- **Responsabilidades**: `predict` y `explain` de la misma revisión, identificadas con `model_version_id` en metadata; escalado de KServe; lectura de artefactos desde `model-store`.
- **Interfaces**: protocolo de inferencia de KServe (v1/v2), accesible solo desde scoring y explainability por NetworkPolicy.
- **Criticidad**: High.
- **Restricciones**: SECURITY-13 (artefactos con checksum verificado); AUTONOMIA-01 (cambios solo por PR y sync manual).

## C08 — `model-store` (almacenamiento de objetos in-cluster, compatible S3)
- **Propósito**: guardar los artefactos de modelo y de explicador, versionados e inmutables.
- **Criticidad**: High (se necesita para desplegar o restaurar).
- **Restricciones**: SECURITY-01 (cifrado); acceso público bloqueado.

## C09 — `governance-service` (FastAPI + PostgreSQL `governance-db`)
- **Propósito**: gobierno de versiones de modelo, versiones de política y fuentes de datos.
- **Responsabilidades**:
  - registrar modelos (checksum y explicador asociado);
  - llevar la máquina de estados del modelo: `registrado → en_validacion → lista_para_aprobacion → aprobado → activo → congelado → retirado`;
  - aprobaciones del CRO (modelo y política) y de cumplimiento (fuentes, reactivación y descarte);
  - aplicar **transiciones acotadas por identidad**: `bias-monitoring` solo puede `activo → congelado`, y solo `cumplimiento` puede sacar un modelo de `congelado`;
  - servir, en lectura, la versión activa y la política vigente;
  - enviar todos los eventos de gobierno al registro;
  - exponer las versiones aprobadas para que `promotion-tool` genere el PR.
- **Interfaces**: REST interno y REST vía BFF.
- **Criticidad**: High.
- **Restricciones**: AUTONOMIA-04; FR-POL-04 (scoring no tiene escritura aquí); SECURITY-08, -12 (MFA de aprobadores, validado por claim `amr`/`acr`).
- **Acceso a la API de Kubernetes**: es el **único** servicio de negocio que la usa. Solo crea y lee `batch/jobs` en `vectra-staging` para el `model-validation-job` (K01 en `component-dependency.md`). No toca InferenceServices ni ningún otro namespace.

## C10 — `model-validation-job` (Kubernetes Job, lanzado a pedido del ingeniero)
- **Propósito**: validar una versión en staging.
- **Responsabilidades**: calcular AUC-ROC contra el dataset de validación; medir sesgo inicial (reutiliza la librería de disparidad de C11); verificar la sincronía predictor ↔ explainer; enviar el informe a `governance-service`.
- **Criticidad**: Medium (no está en la ruta de originación).

## C11 — `bias-monitoring-service` (FastAPI + CronJob)
- **Propósito**: medir la disparidad, alertar y congelar.
- **Responsabilidades**: leer recomendaciones y decisiones con sus etiquetas de monitoreo desde el registro; calcular la disparidad por grupo y por banda de cuota/ingreso, y la agregada (librería propia validada contra Fairlearn); congelar vía `governance-service` cuando se supera el umbral; generar el paquete de contexto; comparar antes y después para fuentes nuevas; exponer el timestamp del último cálculo, que alimenta la alerta `MonitoreoSesgoDetenido`.
- **Interfaces**: REST interno de consulta (dashboard y paquete) y CronJob de cálculo.
- **Criticidad**: High. Un modelo sin vigilancia es un riesgo regulatorio; ver NFR-RES-11.
- **Restricciones**: AUTONOMIA-04 (sin rutas de reactivación); AUTONOMIA-05; P4 (no certifica).

## C12 — `decision-registry-service` (FastAPI + PostgreSQL `registry-db`)
- **Propósito**: único escritor del registro append-only encadenado.
- **Responsabilidades**:
  - agregar registros (recomendación, decisión humana, consulta de explicación, eventos de gobierno) con hash encadenado y escritura serializada;
  - confirmar solo después de la réplica síncrona (RPO 0 ante fallo de zona);
  - consultas filtradas por rol;
  - generar el expediente de un caso;
  - verificar la integridad de la cadena (también como CLI o Job).
- **Interfaces**: REST interno `append` y `query`.
- **Criticidad**: **Critical**. Si no puede agregar, no hay recomendaciones (FR-SCO-08).
- **Restricciones**: SECURITY-13, -14; rol de BD de la app sin `UPDATE`/`DELETE`; Q15.

## C13 — `product-metrics` (servicio ligero)
- **Propósito**: métricas de negocio.
- **Responsabilidades**: calcular periódicamente, desde el registro, la North Star, la tasa de consulta de la explicación, la tasa sostenida por el comité y el tiempo de originación, y exponerlas en `/metrics`.
- **Criticidad**: Medium.

## C14 — `channel-simulator` (CLI / Job)
- **Propósito**: generar solicitudes sintéticas y el conjunto adversarial RT-1..5 contra la API de ingesta.
- **Criticidad**: Low. Es una herramienta de MVP y de pruebas.

## C15 — `core-banking-mock`
- **Propósito**: simular el core bancario. Expone el estado de crédito en lectura. Tiene una ruta de escritura **solo** para demostrar que RT-5 queda bloqueado por red y por RBAC.
- **Criticidad**: Low (en el MVP).

## C16 — `identity` (Keycloak)
- **Propósito**: simular el SSO del banco (OIDC). Realm con los roles `analista`, `ingeniero_riesgo`, `cro` y `cumplimiento`, MFA obligatorio para aprobadores y protección contra fuerza bruta. Clientes para la SPA, para Grafana y para las identidades de servicio (case, scoring, explainability, governance, bias-monitoring, product-metrics, model-validation-job, channel), vía client credentials con los scopes de `component-dependency.md` §2. Persiste en su propia base `keycloak-db` (F43). La consola de administración no se expone por el gateway (X10).
- **Criticidad**: High (sin él no hay acceso a las consolas).

## C17 — `observability-stack` (in-cluster)
- **Propósito**: Prometheus, Alertmanager, Grafana, Loki (logs), Tempo (trazas) y OpenTelemetry Collector. **Ningún exportador fuera del clúster.** La única salida es la notificación de Alertmanager al canal interno del banco, sin PII (F72).
- **Criticidad**: High para operación; no está en la ruta de la decisión.
- **Restricciones**: AUTONOMIA-05; SECURITY-14 (retención ≥ 90 días, tamper-evident); RESILIENCY-05..07.

## C18 — `delivery` (fuera del runtime)
- **Propósito**: Helm charts, repositorio GitOps, Argo CD (**sync manual**), workflows de GitHub Actions y **`promotion-tool`** (CLI que un humano ejecuta para convertir una versión aprobada en un PR del repositorio GitOps; el clúster no tiene egress hacia Git).
- **Restricciones**: AUTONOMIA-01; SECURITY-10, -13; RESILIENCY-03, -04.

---

## Mapa historias → componentes responsables

| Épica | Componentes |
|---|---|
| E1 (US-101..113) | C14, C01, C04, C05, C06, C07, C12, C02, C03 |
| E2 (US-201..208) | C09, C10, C08, C07, C18, C05 (lectura de política) |
| E3 (US-301..308) | C11, C09, C02, C03, C17 |
| E4 (US-401..404) | C12, C03 |
| E5 (US-501..505) | C04, C12, C13, C17, C02 |
| E6 (US-601..611) | C16, C01, C03, C15, C17, C18, todos (NetworkPolicy y RBAC) |
