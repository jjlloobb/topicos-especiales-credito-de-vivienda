# Ronda 1 — U02-T09

VEREDICTO: NO-VERDE

Corrí yo los siete criterios y todos pasan. El veredicto es NO-VERDE por otra razón. Una afirmación de la bitácora sobre la API de v1.9.3 es falsa y deja rotas todas las rutas con JWT. Además, una parte de CA-3 no se cumple aunque su comando termine en 0. El worktree quedó limpio (`git status --short` vacío) y no hubo pruebas omitidas.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|
| 1 | `route_gen.py --check && HYPOTHESIS_PROFILE=ci pytest tests/property/test_routes_*.py -q` | pasa: rc=0 y 11 passed en 292 s (iba en paralelo con CA-7). Con una línea añadida a un `generated/` copiado, `--check --out` da rc=1 |
| 2 | `make -C identity-edge schemas-gateway kubeconform-gateway` | pasa: 30 esquemas y 28/28 válidos por entorno, 0 errores y 0 sin esquema |
| 3 | `make -C identity-edge policy-gateway && pytest test_route_gen.py -q` | el comando pasa (4284 y 18×3 en conftest, 179 passed), pero **la parte «valores leídos del diseño» no se cumple** (F-02) |
| 4 | `pytest test_route_gen.py -q -k intake` | pasa: 11 passed en 0,85 s. Es en memoria, no depende de estado externo |
| 5 | `pytest test_route_gen.py -q` | pasa: 179 passed |
| 6 | `install-tools.sh && charts.sh && make -C platform check-tools` | pasa: rc=0, `kubeconform` 13944911 B, `gateway-helm/` presente |
| 7 | `uv sync --frozen && make -C identity-edge check && make -C platform check-local` | pasa: CA7 rc=0, 1699 passed, 619 passed, 206 Markdown sin enlaces rotos. Ojo: usa el `keycloakx` que el codificador copió a `.charts/` |

## Hallazgos: defectos del código o de la evidencia

### F-01 · ROJO · `CANDIDATAS.md` (entrada de ReferenceGrant/JWKS) y `referencegrants.yaml` · Evidencia falsa: la JWKS cruzada sí exige ReferenceGrant
La bitácora dice que `validateExtServiceBackendReference` no pide `ReferenceGrant`. En el tag v1.9.3, `internal/gatewayapi/validate.go:1470-1488` exige uno cuando el namespace del `backendRef` no es el de la política (`crossNamespaceFrom{group: gateway.envoyproxy.io, kind: SecurityPolicy, namespace: vectra-edge}`). Si no lo hay, devuelve `backend ref to Service vectra-identity/keycloak not permitted by any ReferenceGrant`. `buildRemoteJWKS` (`securitypolicy.go:1907-1935`) pasa por esa función.
- Consecuencia: las SecurityPolicy `console`, `intake` y `promotion` quedan inválidas, y las tres rutas con JWT no funcionan.
- No se arregla solo en el código: INF-U2-10 y la tarea dicen que cada ReferenceGrant admite «solo HTTPRoute de vectra-edge», y eso choca con v1.9.3. Ver la decisión D-1.

### F-02 · ROJO · CA-3 · `tests/strategies/gateway_expected.py` · El oráculo escribe a mano valores que fija el diseño
CA-3 exige que los valores que fija el diseño se lean del diseño. `gateway_design` solo lee perfiles, hostnames, números de la tabla, timeouts, tamaños, la lista V1, `Retry-After`, la URL de la JWKS y los roles. El resto va escrito en `gateway_expected.py`. Literales encontrados en el mismo barrido:
- claims: `vectra-console`, `promotion-tool`, `ingeniero_riesgo`, `mfa` y `channel`;
- scopes: `intake:submit` y `governance:promotion`;
- `cacheDuration` `300s`;
- outlier: 5, `30s`, 50 y `consecutiveLocalOriginFailures` 5 (P-U2-02);
- reintento: 1, `connect-failure` y 20/100;
- `numTrustedHops` 1, `UnescapeAndRedirect` y `disableMergeSlashes`;
- destinos y puertos (de `SPA` a `PROMETHEUS`, INF-U2-10);
- `x-vectra-*`, `server` y `x-envoy-`;
- caminos de intake y promoción y sus reescrituras (V3);
- la cookie: nombre, TTL y atributos (V6);
- `federate-basic-auth`, `identity/federate` y `.htpasswd` (V7).

Las mismas cifras se repiten en `routes.yaml` y en `gateway.rego`. Si el diseño cambia, nada falla.

### F-03 · NARANJA · `tools/route_gen.py:369`, `:49`, `:319-329` · Literales en puntos de decisión
- `closed_traffic_policy` escribe `retry_after = "1"` en el código. Las demás rutas lo toman de `routes.yaml`.
- `PER_IP_CIDR = "0.0.0.0/0"` decide que solo cuente IPv4.
- `error_codes()` decide qué estados lleva cada ruta con reglas escritas en el código, no declaradas en `routes.yaml`.
- `JWT_SAFE_METHODS` (línea 50) no se usa (amarillo).

### F-04 · NARANJA · PBT-U2-04 (`test_routes_closed.py`) · Huecos de cobertura
1. Ninguna propiedad manda query: `route(..., raw)` siempre recibe `{}`. Por eso `GET /api/promotion/v1/models?state=aprobado` nunca se ve llegar al backend en la PBT; solo en una prueba unitaria.
2. `normalize` trata `%2e` como un segmento literal. En v1.9.3 `NormalizePath` es `true` (`listener.go:397`), así que Envoy lo decodifica y resuelve los puntos. Mi sonda: `GET /auth/realms/vectra/account/%2e%2e/%2e%2e/master/x` según el modelo va a keycloak; Envoy lo normaliza a `/auth/realms/master/x` y da 404. `SEPARATOR` incluye `/%2e/`, así que la propiedad dice cubrir una codificación que modela mal.
3. La referencia y el modelo usan el mismo `gc.normalize`, y `redirected` se compara con la misma condición que lo calcula. Para las codificaciones, la propiedad es tautológica.

### F-05 · NARANJA · F09 habilitada · Sin esquema para `ExternalSecret`
Generé con `f09.enabled: true` en el scratchpad y corrí `kubeconform -strict` con los esquemas de `crd_schemas.py`. Resultado: `could not find schema for ExternalSecret`, `Errors: 1`. Habilitar F09 rompe `make check`, y ninguna prueba corre `kubeconform` con F09 habilitada.

### AMARILLO
- Muchas ramas `deny` no tienen caso que falle. Comprobé con mis propias mutaciones que sí fallan, pero ninguna prueba lo fija:
  - `jwks-internal`: `backendRefs` e `issuer`;
  - `client-policy`: `removeOnMatch` y `enableEnvoyHeaders`;
  - `cookie-affinity` (`type`), `outlier` (5xx) y `consecutiveLocalOriginFailures`;
  - `route-parent` (hostnames);
  - CSP de `grafana` y de `auth`, y `X-Frame-Options` de `auth`;
  - `reference-grants-exact` (falta un grant, o `kind` distinto de Service);
  - 3 de las 4 ramas de `federate-coherence`.
- conftest no distingue entornos: un issuer o hostname de otro entorno pasa con rc=0. Lo atrapa la comparación de pytest.
- `page_csp` compara con `contains`, no con el texto exacto (PBT-U2-05 sí compara exacto).
- El 404 de `closed-auth` sale sin `X-Frame-Options`, porque el perfil `auth` solo agrega la CSP.
- El 429 por el límite global de 200/s en `/auth/**` sale con `Retry-After: 60` (lectura literal de V5).
- `crd_schemas.py` quita las reglas CEL de los CRDs. Revisé las de BTP, SP, CTP y HRF y ninguna se viola.

## Necesitan una decisión de diseño del usuario (no son del codificador)
- **D-1 (ROJO, de F-01):** ¿se permite que el ReferenceGrant de `vectra-identity` admita también `gateway.envoyproxy.io/SecurityPolicy` de `vectra-edge` hacia `keycloak`? Si no, la JWKS debe ir por otro camino.
- **D-2 (ROJO, desvío 1, confirmado):** en Envoy v1.39.5, `RouteEntryImplBase::formatBody` (`config_impl.cc:1138-1139`) arma el contexto con `{&req, &resp, nullptr, direct_body}`, sin span. Así el 404 de `directResponse` llevaría `"correlation_id":"-"`, lo que incumple BR-U2-14 y P-U2-07. La tarea pedía detenerse en ese caso. La opción del codificador, un `responseOverride` 404 con `source: Local` en `closed`, es plausible: `custom_response` va en el orden 0 y ve el local reply del router. Falta aprobarla.
- **D-3 (NARANJA, desvío 2):** los límites en una BTP del `Gateway`. Lo comprobé en el código:
  - `backendtrafficpolicy.go:1247-1253` conserva los nombres de regla de la política del Gateway cuando la ruta no trae `rateLimit`;
  - `ratelimit.go:225-263`: un contador `shared` usa el dominio de su política.

  Es técnicamente correcto y la letra de la tarea («en la BTP de cada ruta») no cabe en v1.9.3. Aun así, la nota «no lo sustituyas por otro mecanismo» exige que el usuario lo ratifique.
- **D-4 (NARANJA, desvío 3):** P-U2-02 no da cifra de reintentos para promoción, `/auth/**` ni `/grafana/**`. La regla era detenerse si falta un dato, y el codificador eligió 1 reintento y el 20 %. Comprobé que Envoy Gateway no agrega 503 cuando hay `triggers` (`route.go:865-874`). Falta que el usuario fije la cifra en el diseño.

## Lo que revisé y está bien
- Cabeceras internas: se quitan por prefijo al entrar y de nuevo por regla hacia el backend. El orden de filtros de v1.9.3 (`httpfilters.go`: JWT 10, buffer 12, RBAC 301, ratelimit 303, router 310) hace que el rate limit lea `x-vectra-*` antes de que se quiten. `Idempotency-Key` y `X-Test-Scenario` no aparecen en ningún filtro.
- Los cuerpos `Problem` validan con U0 y el JSON no lleva otro `%` que el del operador.
- Intake por entorno: el simulador está solo en kind y staging, sale de `values` y la prueba lo cruza con el diseño.
- `platform/` solo cambia `tools.env`, `install-tools.sh`, `charts.sh` y `check-tools`; el `.gitignore` de la raíz agrega `identity-edge/.tools/`. Nada fuera de lo permitido.
- Copiar `keycloakx`: el render con 0 diferencias muestra que es el mismo chart. Es un hueco previo a esta tarea y no contamina la evidencia, pero CA-7 no se reproduce en un clon nuevo sin ese paso.

## Tareas candidatas (fuera de alcance)
- Las 504 (timeout hacia el upstream), 502 y 400 que genera Envoy no son `Problem`. BR-U2-14 no incluye 504 aunque ya se configuran timeouts.
- `charts.sh` no baja `keycloakx` (el codificador ya lo anotó).
- Validar el `ExternalSecret` de F09 con el esquema de ESO 2.14.0 (ligado a F-05).

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/ca6.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/ca7.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/tasks/b2geqa4ma.output (CA-1)
- Fuentes de Envoy Gateway v1.9.3 y Envoy v1.39.5: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/eg/
- Mis sondas: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/probe.py, branches.py y f09gen.py

No pude escribir el informe: no tengo herramienta de escritura. El orquestador debe guardar este texto en `vectra-risk/revisiones/U02-T09/ronda-1.md`.

```
VEREDICTO: NO-VERDE
ROJO|CANDIDATAS.md / referencegrants.yaml (validate.go:1470-1488 v1.9.3)|La JWKS cruzada exige ReferenceGrant para SecurityPolicy; la evidencia dice lo contrario y las rutas JWT quedan rotas
ROJO|CA-3 / tests/strategies/gateway_expected.py|El oráculo escribe a mano valores que fija el diseño (claims, scopes, outlier, reintentos, destinos, cookie, F09...)
ROJO|D-2 HTTPRouteFilter problem-not-found (config_impl.cc:1138 v1.39.5)|El 404 de directResponse sale con correlation_id "-"; requiere decisión
NARANJA|tools/route_gen.py:369,49,319|Literales en puntos de decisión (Retry-After del cierre, CIDR IPv4, códigos por ruta)
NARANJA|tests/property/test_routes_closed.py|PBT-U2-04 sin query, modela mal %2e y normaliza igual en modelo y referencia
NARANJA|F09 habilitada|ExternalSecret sin esquema: kubeconform falla y no hay prueba
NARANJA|D-3 edge-rate-limits|Límites en la BTP del Gateway en vez de la de cada ruta; requiere ratificación
NARANJA|D-4 reintentos de promoción, auth y grafana|Cifra inventada donde P-U2-02 no la fija; requiere decisión
INFORME: revisiones/U02-T09/ronda-1.md
```
