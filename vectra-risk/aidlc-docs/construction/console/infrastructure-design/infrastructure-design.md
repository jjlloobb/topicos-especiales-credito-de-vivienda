# Infrastructure Design — U10 `console`

Decisiones del plan (`console-infrastructure-design-plan.md`, Q1–Q6 = A). Los IDs
`INF-U10-xx` se referencian en el plan de tareas.

U10 no tiene almacenamiento ni mensajería propios: el BFF no guarda estado y todo es HTTP
síncrono. La tabla `integrity_checks` de la verificación asíncrona (P-U10-05) es de U3 (§6).

---

## 1. Cómputo (Q1)

### INF-U10-01 — Recursos, réplicas y cuotas (NFR-U10-10, 12, 20, 22; NFR-U1-13)

| Componente | Namespace | Requests | Limits | Réplicas | PriorityClass |
|---|---|---|---|---|---|
| `console-bff` | `vectra-app` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA de 2 a 6 por CPU al 70 % (estabilización 60 s hacia arriba / 300 s hacia abajo); spread por zona; PDB `minAvailable: 1` | `vectra-high` |
| `console-spa` | `vectra-edge` | 50m / 32 MiB | 200m / 64 MiB | 2 fijas con `vectra.io/hpa-exempt`; spread por zona; PDB `minAvailable: 1` | `vectra-normal` |

- **Aporte a las cuotas**, con el 30 % de margen y **con** el sidecar de Linkerd. El sidecar usa los recursos que fija U1 P-U1-14 (100m / 20 MiB de requests y 500m / 128 MiB de limits por pod):

  | Namespace | Pods en el peor momento | Requests | Limits |
  |---|---|---|---|
  | `vectra-app` (BFF) | 7: 6 del HPA + 1 de `maxSurge: 1` durante un rollout | ≈ 3,19 CPU y 2,4 GiB | ≈ 13,7 CPU y 5,7 GiB |
  | `vectra-edge` (SPA) | 4: 2 + 2 de `maxSurge: 100%` | ≈ 0,78 CPU y 0,26 GiB | ≈ 3,64 CPU y 0,97 GiB |

  La cuota se dimensiona con los pods del peor momento, incluido el rollout: si no, un despliegue con el HPA al máximo quedaría trabado por la cuota. El BFF usa `maxSurge: 1` y `maxUnavailable: 0` (segunda revisión del Infrastructure Design de U10, 2026-10-10; antes la tabla contaba 6 y 2 pods, sin el rollout).

- Estrategia de rollout: BFF con `maxSurge: 1` y `maxUnavailable: 0`; SPA con `maxSurge: 100%` y `maxUnavailable: 0` (INF-U10-02). La cuota cuenta esos pods (segunda revisión del Infrastructure Design de U10, 2026-10-10).
- BFF: readiness (`/readyz`, 8081) solo del proceso, porque no tiene base y sus destinos tienen su propio circuito (P-U1-04); liveness solo del proceso. `preStop` de 5 s; uvicorn con `timeout_graceful_shutdown = 10`; `terminationGracePeriodSeconds: 20`.
- SPA: readiness y liveness con un `GET /healthz` estático de nginx.
- **Verificación**:
  - `helm template` + `conftest` (recursos, réplicas, HPA, PDB, spread, PriorityClass, exención);
  - `kyverno test` de U1 (`require-hpa-bounds` con la exención de la SPA);
  - la prueba de carga de P-U10-11 confirma o ajusta los valores.
- **Satisface**: NFR-U10-10, 12, 20, 22; RESILIENCY-01, 08, 09.

## 2. Imagen y configuración de la SPA (Q2, Q4)

### INF-U10-02 — Imagen con la versión anterior (P-U10-06)
- Dockerfile en tres etapas:
  1. `build`: `npm ci --ignore-scripts` y `vite build`, que genera `dist/`, `manifest.json` y `version.json`;
  2. `previous`: `FROM ${PREVIOUS_IMAGE} AS previous`, donde `PREVIOUS_IMAGE` es un `ARG` cuyo valor por omisión es `no-previous`, una etapa anterior del mismo Dockerfile (`FROM scratch AS no-previous`) que solo contiene un `manifest.json` vacío y `/usr/share/nginx/html/assets/` vacío. Así el Dockerfile es el mismo en todos los releases y nunca necesita un `FROM` condicional (tercera revisión del Infrastructure Design de U10, 2026-10-10):
     - **primer release** (los values de producción en GitOps no tienen digest de `console-spa`): el workflow no pasa `PREVIOUS_IMAGE`, la etapa es `no-previous`, la imagen no trae recursos anteriores y la etiqueta `vectra.io/previous-digest` vale `none`;
     - **releases siguientes**: el workflow pasa `PREVIOUS_IMAGE=<registro>/console-spa@<digest de producción>`, verificado antes con `cosign verify`;
     - `spa-previous-digest-check` acepta `none` **solo** si producción todavía no tiene digest; con un digest en producción, `none` falla;
  3. final: `nginx-unprivileged` por digest, con `dist/` y los recursos de `previous` listados en **su** `manifest.json`. Se conserva solo esa versión; lo que `previous` traía de versiones más viejas se descarta.
- **Qué es «la versión anterior»** (revisión del Infrastructure Design de U10, 2026-10-10): el digest que **está desplegado en producción** cuando se construye la imagen, no el último release publicado. El workflow de release de `console/spa/` lo lee de los values de producción de `console-spa` en `vectra-risk-gitops` y lo pasa como `PREVIOUS_IMAGE_DIGEST`; verifica su firma antes de copiar (`cosign verify`). No hay archivo de digest en el monorepo. Con esto:
  - un salto de releases (producción en N−1 y se publica N+1 sin desplegar N) incluye los recursos de N−1, que son los de las pestañas abiertas;
  - **un rollback es un release nuevo** (*roll forward*): se construye desde el commit anterior y trae los recursos de la versión que está en producción. Revertir el digest en GitOps a una imagen vieja queda solo como emergencia; las pestañas abiertas ven el mensaje de recarga de BR-U10-21 y el runbook `console-spa-emergency-rollback` lo explica;
  - una imagen se promueve de staging a producción **sin reconstruirla**; staging puede pasar por una versión que producción nunca tuvo, y ahí se acepta el mensaje de recarga;
  - **una imagen reconstruida es una imagen nueva** (tercera revisión del Infrastructure Design de U10, 2026-10-10): si `spa-previous-digest-check` pide reconstruir, el digest nuevo vuelve a entrar por un PR a **staging**, pasa sus pruebas de humo y solo después se promueve a producción. Nunca se promueve a producción un digest que no estuvo desplegado en staging.
- **Comprobación al promover** (segunda revisión del Infrastructure Design de U10, 2026-10-10): el build guarda el digest copiado en la etiqueta OCI `vectra.io/previous-digest` de la imagen. El PR de promoción a producción en `vectra-risk-gitops` corre el check `spa-previous-digest-check`, que lee esa etiqueta (`crane config`) y la compara con el digest que producción tiene **en ese momento**. Si difieren (porque producción cambió entre el build y la promoción), el check falla y el PR pide reconstruir la imagen con el digest actual; la reconstruida vuelve a pasar por staging. El mismo check falla si el digest a promover **no** figura en el historial de los values de staging del repositorio GitOps (tercera revisión del Infrastructure Design de U10, 2026-10-10). El check es obligatorio en la protección de `main` del repositorio GitOps. Prueba: un PR con una imagen cuya etiqueta no coincide → falla; con la etiqueta igual → pasa.
- **Actualización progresiva** (revisión del Infrastructure Design de U10, 2026-10-10): durante el rollout conviven pods viejos (con N−1 y N−2) y nuevos (con N y N−1). Para que una pestaña que recibió el `index.html` de N no pida sus recursos a un pod viejo, el gateway de U2 enruta `/` y los estáticos con **afinidad por cookie** a un pod de la SPA (cookie `vectra-spa-route`, `Secure`, `HttpOnly`, `SameSite=Strict`, sin significado de autenticación ni datos). Si el pod desaparece, la pestaña pasa a un pod nuevo, que tiene N y N−1. La estrategia del Deployment es `maxSurge: 100%` y `maxUnavailable: 0`, para que el cambio sea corto.
- `nginx.conf`:
  - `index.html`, `version.json` y `config.json` con `Cache-Control: no-store`;
  - `assets/*` con `public, max-age=31536000, immutable`;
  - fallback a `index.html` **solo** para rutas sin extensión (`location ~ ^[^.]*$`); un archivo con extensión que no existe (por ejemplo `/assets/x.js` de una versión retirada) responde 404 y la SPA muestra el mensaje de recarga, nunca HTML con estado 200 (revisión del Infrastructure Design de U10, 2026-10-10);
  - sin `server_tokens`.

  Las cabeceras de seguridad las pone el gateway (U2).
- **Verificación**: `hadolint`; prueba sobre la imagen: contiene los recursos de N y de la versión de producción, y ninguno más viejo; `curl` en kind de las cabeceras de caché, de un `/cases/123` → `index.html` y de un `/assets/no-existe.js` → 404; prueba de Playwright de P-U10-06 durante un rollout real en kind (pestaña abierta antes del cambio y pestaña nueva a mitad del rollout, las dos sin `chunk_load_failed`); prueba de que el workflow toma el digest de los values de producción.
- **Satisface**: P-U10-06; NFR-U10-45; RESILIENCY-04.

### INF-U10-03 — `config.json` por entorno (domain-entities §4 de U10)
- El chart genera `config.json` desde los values del entorno y lo monta como archivo de solo lectura desde un `ConfigMap`. Contiene **solo lo que cambia por entorno** (tercera revisión del Infrastructure Design de U10, 2026-10-10):
  - `oidc.authority`, `client_id` y los dos `redirect_uri`;
  - el `uid` de `bias.json`.
- Los tiempos (refrescos, step-up, inactividad, consulta de versión, límite del `reporter`, timeout de la API) son **constantes del código** de la SPA (domain-entities §4), iguales en los tres entornos, como los timeouts del BFF.
- `version.json` va en la imagen. La imagen es la **misma** en kind, staging y producción.
- nginx con `readOnlyRootFilesystem` usa `emptyDir` en `/tmp` y en su directorio de caché temporal.
- El `ConfigMap` se monta como volumen completo (no con `subPath`) y el pod template lleva la anotación `checksum/config` con el hash de `config.json`, así que un cambio de configuración reinicia los pods en el sync (revisión del Infrastructure Design de U10, 2026-10-10).
- **Verificación** (`conftest`):
  - `config.json` no contiene claves con nombres de secreto ni valores con forma de llave;
  - los `redirect_uri` coinciden con los del cliente `vectra-console` en `realm.{env}.yaml` de U2;
  - la imagen de producción es un digest que ya estuvo en staging, también después de una reconstrucción por el check del digest anterior (INF-U10-02; tercera revisión del Infrastructure Design de U10, 2026-10-10).
- **Satisface**: SECURITY-09, 12.

## 3. Red (Q3)

### INF-U10-04 — Malla, `Server` y políticas (NFR-U10-46; F02, F03, F10–F14, F50, F60)

| Pieza | `Server` (puerto) | Admite | Sale hacia |
|---|---|---|---|
| `console-spa` | 8080 | Solo la identidad del data plane del gateway (F02) | Nada |
| `console-bff` | 8080 | Solo el gateway (F03) | F10 case, F11 governance, F12 explainability, F13 registry, F14 bias, F50 JWKS de Keycloak |
| `console-bff` | 8081 | Solo Prometheus (F60) | — |

- Las dos piezas van en la malla de Linkerd. `vectra-edge` (con el data plane de Envoy, el rate limit, Valkey y la SPA) y `vectra-app` llevan la etiqueta `vectra.io/mesh: enabled`; U1 los declara en la lista de namespaces mallados de su chart `platform/namespaces` (revisión del Infrastructure Design de U10, 2026-10-10). Si la versión de Envoy Gateway obliga a dejar el data plane en `envoy-gateway-system` (U2 INF), ese namespace también se malla, porque la `AuthorizationPolicy` de la SPA y del BFF admite la identidad del data plane.
- `NetworkPolicy` y `AuthorizationPolicy` las genera `platform/network/generate.py` de U1 desde `flows.yaml`. **Casos bloqueados nuevos** en la suite de conectividad:
  - SPA → cualquier servicio de `vectra-app`;
  - BFF → `vectra-data` (el BFF no tiene base);
  - BFF → `vectra-serving`.
- `/grafana/**` sigue en U2 (perfil `grafana`): el iframe de BR-U10-16 no pasa por el BFF.
- **Verificación**: `generate.py --check`; suite de conectividad de U1 con los casos permitidos y bloqueados de esta tabla (operador en kind).
- **Satisface**: SECURITY-06, 07; AUTONOMIA-03.

## 4. Observabilidad (Q5)

### INF-U10-05 — Dashboard, reglas y runbooks (P-U10-10, 11)
- `PrometheusRule` del chart del BFF con las **seis** alertas y las recording rules de P-U10-10, cada una con `severity` y `runbook_url` (tercera revisión del Infrastructure Design de U10, 2026-10-10: decía «cinco»).
- Dashboard `console/observability/dashboards/console.json` (ConfigMap de dashboards de U1), con estos paneles:
  - por ruta: tasa, errores y p50/p95/p99;
  - por destino: el sobrecosto de NFR-U10-01 y el estado del circuito;
  - errores del navegador por `error_code`;
  - presupuesto de errores del SLO a 30 días;
  - réplicas del HPA.
- Runbooks:
  - `console-bff-error-budget`;
  - `console-bff-down`;
  - `console-dependency-circuit-open`;
  - `console-client-errors-spike`, que explica cómo distinguir un `chunk_load_failed` de un despliegue (P-U10-06) de uno real, y que también es el `runbook_url` de `ConsoleChunkOrCspError` (con una sección propia para `csp_violation`; tercera revisión del Infrastructure Design de U10, 2026-10-10).
- `ServiceMonitor` del puerto 8081 del BFF. La SPA no expone métricas: sus errores llegan por el BFF (P-U10-09).
- Evidencias de rendimiento: el reporte de k6 y el de Lighthouse CI se adjuntan al PR; `size-limit` corre en cada PR.
- **Verificación**: `promtool test rules`; `uv run python platform/tests/test_runbooks.py --root console`; prueba sobre `console.json`: sin frases prohibidas (`forbidden_phrases.py`) y sin paneles con datos del solicitante.
- **Satisface**: NFR-U10-21, 34; RESILIENCY-05, 07, 15.

## 5. Entornos (Q6)

### INF-U10-06 — kind, staging, producción y CI (NFR-U10-63)

| Entorno | BFF | Realm (U2) | Destinos | Pruebas |
|---|---|---|---|---|
| CI (sin clúster) | Proceso local con dobles de los destinos y un emisor de JWT de prueba | — | Dobles | Playwright contra Vite, Vitest, fast-check, Hypothesis, matriz rol × endpoint |
| kind | HPA con `minReplicas = maxReplicas = 2` (no se quita el HPA, así que `require-hpa-bounds` no necesita exención; revisión del Infrastructure Design de U10, 2026-10-10) | `realm.kind.yaml`, con dos usuarios por rol y TOTP de prueba | Reales (U3, U4, U7, U8, U9) | Playwright extremo a extremo, k6 y Lighthouse CI (operador) |
| staging | Igual que producción | `realm.staging.yaml`, con los mismos usuarios sintéticos | Reales, con datos sintéticos de U12 | Humo después del sync |
| producción | HPA de 2 a 6 | `realm.prod.yaml`, sin usuarios de prueba (`realm-lint`) | Reales | — |

- Usuarios de prueba: los de U2 domain-entities §3 (`analista-1` y `-2`, `ingeniero-1` y `-2`, `cro-1` y `-2`, `cumplimiento-1` y `-2`), en kind y staging, con contraseña y TOTP desde ESO, nunca en Git. Dos por rol permiten probar aprobador ≠ proponente (políticas, U4 BR-U4-10). `realm-lint` falla si `realm.prod.yaml` tiene algún usuario local distinto de `break-glass` (revisión del Infrastructure Design de U10, 2026-10-10).
- **Verificación**: `realm-lint`; los values por entorno con `conftest`; evidencia del operador en kind.
- **Satisface**: AUTONOMIA-01; SECURITY-12.

## 6. Cumplimiento de extensiones (Infrastructure Design U10)

| Regla | Estado | Evidencia |
|---|---|---|
| SECURITY-06 / 07 | Cumple | INF-U10-04 |
| SECURITY-09 / 10 | Cumple | INF-U10-02, 03 (imagen firmada y verificada, misma imagen en los tres entornos) |
| SECURITY-12 | Cumple | INF-U10-03, 06 (sin secretos en `config.json`; semillas TOTP fuera de Git) |
| RESILIENCY-01 / 08 / 09 | Cumple | INF-U10-01 |
| RESILIENCY-04 | Cumple | INF-U10-02 |
| RESILIENCY-05 / 07 / 15 | Cumple | INF-U10-05 |
| AUTONOMIA-01 | Cumple | Sync manual en la wave 5; pruebas con clúster por el operador (INF-U10-06) |
| AUTONOMIA-02 | Cumple | Cada `INF-U10-xx` tiene su «Verificación» |
| AUTONOMIA-03 | Cumple | INF-U10-04 (casos bloqueados) |

## 7. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U3 (roles `registry_ondemand` y `registry_verifier` de solo lectura; `full` mensual encolada por `registry-verify-ondemand`; `RegistryFullVerificationOverdue`; emisor de métricas; archivo en tramos; readiness por quórum; NFR-U3-43; F97, F98, F99; INF-U3-04); U0 §5.1 (`acr` y `auth_time` en todo actor de usuario); U3 BR-U3-16 y U8 BR-U8-18; U4 NFR-U4-04 (edad máxima de 30 s) y BR-U4-14; U1 NFR-U1-12 (inactivo con 1 réplica), deployment-architecture (wave 6); U6 INF-U6-02; U9 (Grafana, Pushgateway, margen de RT-2); U2 (rol `operacion`, equipos de Grafana, BR-U2-13, §8); `aidlc-state.md` (revisiones posteriores a la aprobación); U10 (etiqueta y check del digest anterior, step-up con `OidcClient` y prueba de concepto, cuota con el rollout, timeouts como constantes, filas históricas, corrección de BR-U10-09b) | segunda revisión del Infrastructure Design de U10, 2026-10-10 |
| U1 P-U1-13 (nuevo), P-U1-14 (nuevo), P-U1-10, P-U1-12, P-U1-05, NFR-U1-12, 13, deployment-architecture, plan (Pasos 3, 5, 6); `component-dependency.md` F109 | Pushgateway con persistencia y autorización por identidad; lista de namespaces mallados; recursos del proxy; `console-spa` exento de HPA; `InferenceService` de staging fuera de `require-hpa-bounds`; silencios por F109; waves de Envoy Gateway y Valkey; `case_retention` real en el simulacro | revisión del Infrastructure Design de U10, 2026-10-10 |
| U2 BR-U2-04, 13, 15, domain-entities §3, §4 y §4.1, business-logic-model §2.2, PBT-U2-05, plan (Pasos 5, 7, 13) | Step-up en ventana emergente; `auth` también admite `frame-ancestors 'self'`; COOP `same-origin`; rutas `/callback` y `/stepup-callback`; afinidad por cookie; usuarios nombrados; 403 en el gateway sin rol; límite de `/auth/**` para el NAT | revisión del Infrastructure Design de U10, 2026-10-10 |
| U0 §6, §7.1b, §7.2, §8.1, §9.2, §9.6; BR-U0-21, 72, 94; NFR-U0-23, 47; P-U0-01, 08; tech-stack; logical-components; plan (Pasos 3, 10) | `max_body_bytes`; tipos de la verificación y reglas de estructura; `deadline_exceeded`; `process_kind`; codificación del circuito; frases literales con U7; catálogo de scopes | revisión del Infrastructure Design de U10, 2026-10-10 |
| U8 BR-U8-13b, plan (Paso 13); C04 | `get_case_identifiers` para el expediente | revisión del Infrastructure Design de U10, 2026-10-10 |
| U4 NFR-U4-13 (nuevo) | Lecturas desde el BFF p95 ≤ 300 ms | revisión del Infrastructure Design de U10, 2026-10-10 |
| U9 logical-components, P-U9-02, 06, business-logic-model (PBT-U9-05), plan (Pasos 8, 13) | Inventario y presupuesto al día; `for` de `DisparidadDecisionHumana` = 2 × intervalo; invariante del ciclo de vida de `freeze-<v>` | revisión del Infrastructure Design de U10, 2026-10-10 |
| U1 plan (Paso 6) y chart de cuotas | Aporte de U10 a `vectra-app` y `vectra-edge` (INF-U10-01) | Q1 |
| U1 `flows.yaml`, plan (Paso 3) y suite de conectividad | Casos bloqueados SPA → `vectra-app`, BFF → `vectra-data` y BFF → `vectra-serving` | Q3 |
| U2 domain-entities §3, `realm-lint` y plan | Nombres de los dos usuarios sintéticos por rol en kind y staging; `realm-lint` rechaza usuarios locales en producción salvo `break-glass` | Q6; revisión del Infrastructure Design de U10, 2026-10-10 |
| U2 rutas del gateway | Afinidad por cookie `vectra-spa-route` en `/` y los estáticos (INF-U10-02) | revisión del Infrastructure Design de U10, 2026-10-10 |
| U1 chart `platform/namespaces` y Paso 5 | Lista explícita de namespaces mallados, con `vectra-edge` | revisión del Infrastructure Design de U10, 2026-10-10 |
| U3 BR-U3-01, 02, 04, 08, 13b, domain-entities §5.0 y §6, business-logic-model §2.6, P-U3-04, 08, 09, logical-components, INF-U3-03, plan (Pasos 2, 8, 12, 14, 18); U1 P-U1-08 | **Rediseño** (revisión del Infrastructure Design de U10, 2026-10-10): la verificación bajo demanda la ejecuta el CronJob `registry-verify-ondemand` con la identidad de verificación (firmas y bucket WORM); la API solo registra la solicitud (202, o 200 con la activa); barrido de huérfanas en cada corrida; la `full` mensual pasa por la misma tabla; sin conexión extra en el servicio, así que P-U1-08 vuelve a no tener excepciones | P-U10-05 |

## 8. Pendientes diferidos (revisión del Infrastructure Design de U10, 2026-10-10, Q2 = B)

Llegaron sin detalle y se resuelven cuando se abra la etapa de su unidad o se revise su plan:

| Unidad | Hallazgo | Cuándo |
|---|---|---|
| U4 | «NFR-U4-31 y 22» (el 10 quedó resuelto con NFR-U4-13 y la edad máxima de NFR-U4-04; tercera revisión del Infrastructure Design de U10, 2026-10-10) | Revisión del plan de tareas de U4 |
| U5 | Pendientes de las revisiones anteriores | Revisión del plan de tareas de U5 |
| U6 | «staging solo con predictor; InferenceServiceNotReady» | Revisión del plan de tareas de U6 |
| U7 | «lint, etiquetas y escenarios» | Revisión del plan de tareas de U7 |
| U8 | «concurrencia frente a la capacidad del explainer; F104» | Revisión del plan de tareas de U8 |
| U11, U12 | Pendientes de las revisiones anteriores | Functional Design de cada unidad |
| [VERIFICAR] | Pendientes con cumplimiento, incluida la decisión sin step-up (BR-U10-09b) | Antes de Operations |

