# Application Design (consolidado) — Vectra Risk

Documento de síntesis. El detalle está en:
- [`components.md`](./components.md): 18 componentes, responsabilidades, criticidad y restricciones.
- [`component-methods.md`](./component-methods.md): tipos compartidos, contrato de sincronía y firmas, incluida la tabla de endpoints del BFF (rol, MFA y regla de objeto).
- [`services.md`](./services.md): orquestación de los flujos S1–S9.
- [`component-dependency.md`](./component-dependency.md): **inventario cerrado** de flujos de red (F01–F104, ampliado en U1, U2, U3 y U4 Infrastructure Design y en U7 y U8 FD), acceso a la API de Kubernetes (K01–K14), roles de BD, egress, flujos prohibidos (X01–X10), diagrama y fronteras de confianza.

---

## 1. Decisiones de diseño

| # | Decisión | Motivo principal |
|---|---|---|
| Q1 | `governance-service` dedicado (modelos, políticas, fuentes, aprobaciones) | Separar modelo y política; scoring solo lee su política (FR-POL-04) |
| Q2 | `decision-registry-service` es el único escritor | Un solo punto controla el append-only y la cadena de hashes |
| Q3 | `case-service` lleva el ciclo de vida y los reintentos; scoring hace la llamada síncrona a la explicación | Separa la orquestación del caso del fail-closed; conserva el flujo SC→EX del PRD |
| Q4 | HTTP síncrono + cola en PostgreSQL + CronJobs; sin broker | Menos superficie que asegurar y respaldar dentro del banco |
| Q5 | Envoy Gateway (JWT, rate limit, access log) + BFF; cada servicio revalida | Defensa en profundidad (SECURITY-08/11) |
| Q6 | Explicador SHAP dentro del mismo `InferenceService` que el predictor | La plataforma despliega ambos en la misma revisión: la sincronía no depende solo del código |
| Q7 | Congelamiento = transición en governance con scope `governance:freeze` | Mínimo privilegio; congelar no requiere escritura en Kubernetes (la única escritura de un servicio de negocio es K01: Jobs de validación en staging); reactivación solo por cumplimiento |
| Q8 | `product-metrics` calcula las métricas de negocio desde el registro | La North Star y la métrica de ruido salen de la fuente de evidencia |

## 2. Inventario de componentes y criticidad (RESILIENCY-01)

| ID | Componente | Tipo | Criticidad | Datos propios |
|---|---|---|---|---|
| C01 | api-gateway | Envoy Gateway | High | — |
| C02 | console-spa | React + TS | Medium | — |
| C03 | console-bff | FastAPI | High | — |
| C04 | case-service | FastAPI | High | `case-db` (PII) |
| C05 | scoring-service | FastAPI | High | — |
| C06 | explainability-service | FastAPI | High | — |
| C07 | model-serving | KServe | High | — |
| C08 | model-store | Objetos compatible S3, in-cluster | High | artefactos |
| C09 | governance-service | FastAPI | High | `governance-db` |
| C10 | model-validation-job | K8s Job | Medium | — |
| C11 | bias-monitoring-service | FastAPI + CronJob | High | — (lee el registro) |
| C12 | decision-registry-service | FastAPI | **Critical** | `registry-db` (append-only) |
| C13 | product-metrics | Servicio ligero | Medium | — |
| C14 | channel-simulator | CLI/Job | Low | — |
| C15 | core-banking-mock | Servicio mock | Low | estado de crédito simulado |
| C16 | identity | Keycloak | High | realm |
| C17 | observability-stack | Prometheus/Alertmanager/Grafana/Loki/Tempo/OTel | High (operación) | métricas, logs, trazas |
| C18 | delivery | Helm, GitOps, Argo CD, GitHub Actions, promotion-tool | — (fuera del runtime) | repositorios |

**Impacto de la indisponibilidad:**
- **registry:** se detienen todas las recomendaciones (fail-closed) y no se pierde evidencia.
- **scoring, explainability o KServe:** casos en `en_sincronizacion`; el banco sigue con su proceso manual.
- **governance:** scoring no puede leer la configuración y hace fail-closed.
- **bias-monitoring:** alerta `MonitoreoSesgoDetenido`; el efecto sobre el modelo lo define Functional Design.

## 3. Contrato central: sincronía scoring ↔ explicación ↔ registro

Una `Recommendation` solo existe si se cumplen las tres condiciones:
1. `explanation.model_version_id == model_version_id`;
2. la factualidad de la narrativa fue validada;
3. el registro confirmó el append.

Cualquier otra combinación devuelve un `FailClosed` tipificado, con causa y bandera
`retryable`. No existe ningún tipo ni ruta de "explicación de respaldo" (AUTONOMIA-06).
Es propiedad PBT candidata para Functional Design.

## 4. Diagrama

Ver `component-dependency.md` §7 (Mermaid validado y alternativa en texto).

## 5. Trazabilidad

- Cada una de las 49 historias tiene al menos un componente responsable (ver el mapa en `components.md`).
- FR-EXP-06 (narrativa por LLM a futuro) queda cubierto por la interfaz `NarrativeGenerator` en `component-methods.md`.

## 6. Pendientes para etapas posteriores

| Tema | Etapa |
|---|---|
| Efecto de `MonitoreoSesgoDetenido` sobre el modelo (NFR-RES-11 / US-308) | Functional Design (unidad de bias-monitoring) |
| Umbrales, parámetros de backoff, TTL de `serving-config`, ventana W | Functional Design |
| Topología física de PostgreSQL, réplica síncrona, WAL fuera del sitio | Infrastructure Design |
| mTLS entre servicios (malla o TLS por servicio) | NFR Design |
| Latencia objetivo, SLA, intervalo WAL | NFR Requirements |

## 7. Cumplimiento de extensiones (Application Design)

Criterio de estado:
- **Cumple**: el diseño contiene la decisión o la restricción y la evidencia la nombra.
- **N/A en esta etapa**: la regla verifica artefactos que todavía no existen (configuración, código o pruebas). Se indica la etapa que la verificará y el componente que ya tiene asignada la obligación.

Ninguna regla aplicable queda sin evidencia.

### 7.1 Límite de autonomía

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | `promotion-tool` + PR + sync manual (S3); K04 es la única escritura de Argo CD al clúster, tras sync aprobado; migraciones como hook del sync (F44); X07 |
| AUTONOMIA-02 | N/A en esta etapa | Aplica a los criterios de aceptación de las tareas (Code Generation Planning). §6 de `component-dependency.md` ya asigna una prueba a cada flujo prohibido |
| AUTONOMIA-03 | Cumple | F17 (solo `GET` y solo desde case-service); X01; scoring y explainability sin acceso al core ni a la API de Kubernetes (§3) |
| AUTONOMIA-04 | Cumple | F27 (scope `governance:freeze`); X03, X04; `resolve_frozen` solo para `cumplimiento` con MFA (tabla del BFF) |
| AUTONOMIA-05 | Cumple | §5: el egress es un inventario cerrado y no incluye scoring, explainability ni bias; X02; observabilidad in-cluster salvo F72 sin PII |
| AUTONOMIA-06 | Cumple | Contrato §3 y tipo `FailClosed` (`component-methods.md`); sin tipo ni ruta de respaldo |

### 7.2 Security Baseline

| Regla | Estado | Evidencia |
|---|---|---|
| SECURITY-01 Cifrado en reposo y en tránsito | Cumple | Almacenes identificados: `case-db`, `governance-db`, `registry-db`, `keycloak-db` y model-store (§2.4 de dependencias), con cifrado asignado (C08, C12); backups y WAL cifrados (F70); TLS en todos los flujos (§0). La configuración concreta se verifica en Infrastructure Design |
| SECURITY-02 Access logging en intermediarios | Cumple | api-gateway (C01) con access log estructurado; único ingress (F01, X09) |
| SECURITY-03 Logging de aplicación | Cumple | Logging estructurado con correlation ID propagado por el BFF (C03) y los servicios; centralizado in-cluster (F61–F63); sin PII (AUTONOMIA-05, US-604) |
| SECURITY-04 Cabeceras HTTP | Cumple | Asignadas a F02 (api-gateway → console-spa) y a C02; los valores exactos se configuran en NFR Design |
| SECURITY-05 Validación de entradas | Cumple | Todos los endpoints validan por esquema (preámbulo de `component-methods.md`); límite de payload y rate limit en el gateway (C01); texto libre tratado como dato (C04, FR-ING-04) |
| SECURITY-06 Mínimo privilegio | Cumple | Scopes por flujo (§2), RBAC de Kubernetes cerrado K01–K14 (§3; K07–K13 agregados en U1 y K14 en U2 Infrastructure Design), roles de BD por servicio sin DDL en runtime y `registry_app` solo INSERT/SELECT (§4); X04, X05, X07 |
| SECURITY-07 Red restrictiva | Cumple | Namespaces (§1); deny-by-default con inventario cerrado de flujos (§0, §2); egress cerrado (§5); único ingress (X09) |
| SECURITY-08 Control de acceso en la aplicación | Cumple | Tabla del BFF con rol, MFA y regla de objeto por endpoint; cada servicio revalida el JWT (Q5=A); JWT validado en el gateway (F03); CORS: la SPA y la API comparten origen detrás del gateway, no se usa wildcard |
| SECURITY-09 Hardening | Cumple | Consola de administración de Keycloak no expuesta (X10); errores genéricos en el BFF (C03); sin servicios expuestos salvo el gateway (X09); `mark_active` y los endpoints internos fuera del BFF. Credenciales por defecto y versiones de runtime se verifican en Infrastructure Design y en Code Generation |
| SECURITY-10 Cadena de suministro | Cumple | C18 (CI en GitHub Actions con escaneo, SBOM e imágenes pinneadas, US-606); imágenes solo desde el registro aprobado (§5) |
| SECURITY-11 Diseño seguro | Cumple | Autenticación y autorización aisladas en gateway, BFF y Keycloak (C01, C03, C16); rate limiting (C01); casos de abuso: flujos prohibidos X01–X10 + RT-1..5 |
| SECURITY-12 Autenticación y credenciales | Cumple | Keycloak (C16): hash adaptativo, fuerza bruta, MFA obligatorio para aprobadores; el BFF exige MFA por endpoint; identidades de servicio con client credentials (F50); sin credenciales en el código (Secrets, NFR-SEC-12) |
| SECURITY-13 Integridad de software y datos | Cumple | Checksum de artefactos (F47, C08, US-201); cadena de hashes del registro (C12); separación autor/aprobador en el pipeline (C18, S3); cambios críticos auditados (F24) |
| SECURITY-14 Alertas y monitoreo | Cumple | Fallos de autorización registrados por el BFF (paso 1 de C03) y alertados; almacenamiento append-only (X06); Loki in-cluster con retención ≥ 90 días asignada (NFR-SEC-14); dashboards en Grafana (F06) |
| SECURITY-15 Manejo de excepciones y fail-safe | Cumple | Tipo `FailClosed`; el circuit breaker abierto lleva a fail-closed (§8 de dependencias); errores genéricos del BFF; handler global asignado a cada servicio FastAPI (NFR-SEC-15) |

### 7.3 Resiliency Baseline

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 Criticidad | Cumple | §2: criticidad e impacto de la indisponibilidad por componente; dependencias en `component-dependency.md` |
| RESILIENCY-02 SLA/RTO/RPO | Cumple | Heredado de requirements (NFR-RES-02/03, R1/R2); el diseño lo soporta con la réplica síncrona (F45) y el backup fuera del sitio (F70) |
| RESILIENCY-03 Gestión de cambios | Cumple | S3, C18: PR + evidencia + aprobación + sync manual (R3=B) |
| RESILIENCY-04 Despliegue y rollback | Cumple | Rollback por revert + sync manual (S3 paso 6); migraciones como hook (F44); rolling update y HPA en Infrastructure Design |
| RESILIENCY-05 Observabilidad | Cumple | C17; métricas (F60), trazas (F61/F62), logs (F63), dashboards (F65) |
| RESILIENCY-06 Health checks | Cumple | Puerto 8081 de health y métricas separado de la API (§0). La readiness profunda y sus dependencias se definen en NFR Design |
| RESILIENCY-07 Monitoreo de resiliencia | N/A en esta etapa | Las alarmas de réplica, backup y zona se definen en NFR e Infrastructure Design. El diseño ya expone los puntos de medición: operador de PostgreSQL (K06), F45, F70 |
| RESILIENCY-08 Multi-zona | N/A en esta etapa | R7=A registrado; la distribución por zonas es de Infrastructure Design. Ningún componente del diseño impone instancia única, salvo el escritor serializado del registro, cuya réplica está en F45 |
| RESILIENCY-09 Autoscaling | N/A en esta etapa | R8=A registrado; HPA y escalado de KServe en Infrastructure Design. Todos los servicios de `vectra-app` son stateless salvo sus bases |
| RESILIENCY-10 Aislamiento de dependencias | Cumple | Timeouts y circuit breakers (§8 de dependencias); el registro es hoja (no depende de servicios de negocio) |
| RESILIENCY-11 Estrategia DR | Cumple | Backup & Restore (R1) con WAL fuera del sitio (F70) |
| RESILIENCY-12 Backups | Cumple | F70 con cifrado; la retención y la validación de restore se detallan en Infrastructure Design (US-608) |
| RESILIENCY-13 Procedimientos de recuperación | N/A en esta etapa | Los runbooks son artefactos de Infrastructure Design y NFR Design; la validación posterior usa `verify_chain` (C12) |
| RESILIENCY-14 Pruebas de resiliencia | N/A en esta etapa | La pregunta obligatoria va en NFR Design |
| RESILIENCY-15 Respuesta a incidentes | Cumple | Alertmanager → canal interno del banco (F72) con `runbook_url`; proceso propuesto (R9=B) |

### 7.4 Property-Based Testing

| Regla | Estado | Evidencia |
|---|---|---|
| PBT-01 Identificación de propiedades | N/A en esta etapa | Se formaliza en Functional Design; candidatas ya identificadas: invariante del contrato §3, cadena de hashes, máquina de estados del modelo, disparidad contra el oráculo de Fairlearn |
| PBT-02..08, PBT-10 | N/A en esta etapa | Aplican a los planes de tareas y al código |
| PBT-09 Framework | Cumple | Heredado de requirements (NFR-TST-01): Hypothesis y fast-check, coherentes con el stack del diseño (FastAPI y React) |
