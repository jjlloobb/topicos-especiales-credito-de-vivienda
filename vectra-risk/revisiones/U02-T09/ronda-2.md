# Ronda 2 — U02-T09

VEREDICTO: NO-VERDE

Corrí los siete criterios y todos pasan. Comprobé en el código los cinco hallazgos de la ronda 1 y las decisiones D-1 a D-4: están implementados. Queda un NARANJA nuevo, de diseño: en v1.9.3 el límite de tasa no se aplica a las rutas `directResponse`. Eso deja sin uso el 429 del cierre y choca con D-5 en `/auth/`. Necesita una decisión del usuario. El worktree quedó limpio.

## Criterios de aceptación, verificados por mí (head 9900c59)
| # | Comando (desde `vectra-risk/`) | Resultado |
|---|---|---|
| 1 | `route_gen.py --check && HYPOTHESIS_PROFILE=ci pytest tests/property/test_routes_*.py -q` | pasa: check rc=0, 13 passed en 223 s |
| 2 | `make -C identity-edge schemas-gateway kubeconform-gateway` | pasa: 32 esquemas, 28/28 válidos ×3, 0 errores |
| 3 | `make -C identity-edge policy-gateway && pytest test_route_gen.py -q` | pasa: conftest 4284 y 27×3, pytest 274 passed |
| 4 | `pytest test_route_gen.py -q -k intake` | pasa: 11 passed |
| 5 | `pytest test_route_gen.py -q` | pasa: 274 passed |
| 6 | `install-tools.sh && charts.sh && make -C platform check-tools` | pasa: rc=0. `platform/` no cambió desde la ronda 1 |
| 7 | `uv sync --frozen && make -C identity-edge check && make -C platform check-local` | pasa: rc=0, 1796 y 619 passed, 208 Markdown sin enlaces rotos |

Sobre CA-7: mi primera corrida dio `2 failed` con `OSError: [Errno 26] Text file busy: platform/.tools/bin/conftest`. La causé yo: corrí CA-6, que reinstala `conftest`, en paralelo con CA-7. La repetí sola y dio rc=0. No es un defecto del diff. El log de esa primera corrida queda en `r2-ca7.log`.

## Hallazgos de la ronda 1, comprobados en el código
- **F-01 / D-1: resuelto.** El grant de `vectra-identity` admite `from` HTTPRoute y `gateway.envoyproxy.io/SecurityPolicy` de `vectra-edge`, y `to` solo `keycloak`. Cumple `validate.go:1470-1488` de v1.9.3. La entrada falsa de `CANDIDATAS.md` ya no está.
- **F-02: resuelto en lo esencial.** `gateway_design.py` lee del diseño los claims, scopes, outlier, reintentos, saltos, barras, prefijos, destinos, Gateway, grants, V3, cookie, F09 y estados. Existe `test_a_value_changed_in_the_design_but_not_in_the_oracle_is_caught`, con 46 casos. Quedan restos en AMARILLO-1.
- **F-03: resuelto.** Hay `closed_policy`, `errors` por ruta y `source_ip` como lista en `routes.yaml`. Ya no hay literales de decisión en `route_gen.py`.
- **IPv6: correcto.** `parseCIDR` y `buildDistinctCIDRMatchRateLimitAction` (`ratelimit.go:521-556`) arman el matcher con el prefijo y la máscara de cada familia. Una IP cae en una sola de las reglas `0.0.0.0/0` y `::/0`, así que no cuenta doble.
- **F-04 / PBT-U2-04: resuelto.**
  - Las propiedades generan consulta (`QUERIES`).
  - `normalize` decodifica los caracteres no reservados, como hace `NormalizePath=true` (`listener.go:397`).
  - La referencia `independent_path` usa `unquote` y `posixpath.normpath`, no el modelo.
  - Hay una prueba explícita de `%2e%2e` hacia `master`, que da 404.
- **F-05: resuelto.** Generé con F09 habilitada en los tres entornos y corrí `kubeconform -strict` con los esquemas nuevos: 32/32 válidos, 0 sin esquema.
- **D-2: implementado.** La política `closed` tiene un 404 con `source: Local` y `%TRACE_ID%`. En Envoy v1.39.5, `HttpResponseLocalReplyInput` (`status_code_input.h:122-131`) marca como local todo lo que no es `via_upstream`, así que el `direct_response` cae en el override. `customResponse.patchRoute` sí habilita el filtro en las rutas de respuesta directa.
- **D-3 y D-4: implementados**, con las cifras leídas de P-U2-02.
- **AMARILLO de la ronda 1:** conftest ahora distingue entornos (`environment-values`). `page_csp` compara el texto exacto. Hay casos para las ramas `deny` que faltaban.

## Hallazgos nuevos

### F-06 · NARANJA (decisión de diseño) · `closed` / BR-U2-08 D-5 · En v1.9.3 las rutas `directResponse` no tienen rate limit
`internal/xds/translator/ratelimit.go:176` (`patchRouteWithRateLimit`) devuelve sin hacer nada cuando `route.GetRoute() == nil`. Las reglas `closed-*` traducen a `Route_DirectResponse` (`route.go:72-73`), así que esa condición siempre se cumple para ellas. Consecuencias:
1. El tráfico a `/api/**`, `/auth/**` y `/federate` fuera de las entradas no cuenta para el límite global de 200/s, que el diseño dice «compartido por todas las rutas».
2. El `responseOverride` 429 de la política `closed` nunca se dispara: es configuración sin uso.
3. Ese 429 lleva `Retry-After: 1` y cubre también `/auth/**`. D-5 dice «en `/auth/**` todo 429 lleva `Retry-After: 60`». Hoy no se dispara, pero el manifiesto declara un valor contrario al diseño.

Hace falta que el usuario decida:
- (a) aceptar que los prefijos cerrados quedan fuera del límite global, quitar el 429 de `closed_policy` y escribirlo en INF-U2-10 o BR-U2-10;
- (b) u otro mecanismo.

No es un defecto del codificador: lo impide v1.9.3. Aun así, la generación actual contradice D-5 en la letra.

### AMARILLO-1 · `tests/strategies/gateway_expected.py` · Quedan valores del diseño escritos a mano en el oráculo
- `"channel"`, el valor de la cabecera del contador de intake. Lo comprobé: alteré en memoria solo la columna de autenticación (`azp = canal`) y el claim cambia, pero el contador sigue diciendo `channel`.
- `read_methods()` devuelve `["GET", "HEAD"]` literal (P-U2-02).
- El mapa `closed_profile`.
- `(404, 429)` del cierre.
- `"/federate"` con `GET`.

Además, 5 de las 46 alteraciones solo se atrapan porque el lector lanza una excepción, no porque cambie el valor: el Service del grant, los prefijos cerrados, las dos reescrituras `/v2/...` y `req/s` en el login. La prueba cuenta la excepción como acierto (`except ...: changed.append(env)`). Sonda: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/alt.py` y `chan.py`.

### AMARILLO-2 · `CANDIDATAS.md:92` · Entrada vieja
La entrada sobre el `Retry-After` del límite global en `/auth/**` quedó resuelta por D-5, pero sigue en la lista.

## El punto que dejó abierto el codificador
**`X-Frame-Options` del 404 bajo `/auth/`:** el diseño no lo exige. §4.1 define `auth` como «las de Keycloak, más `frame-ancestors 'self'`». BR-U2-13 solo pide que `auth` admita el mismo origen, y el 404 ya lleva la CSP `frame-ancestors 'self'`, que es lo que los navegadores aplican. Coincido con el codificador: no es un defecto, y está bien como candidata por si el diseño quiere fijarlo.

## Lo que necesita al usuario
- F-06: qué hacer con los prefijos cerrados frente al límite global y con el 429 de `closed`.

## Tareas candidatas
- Ya están en `CANDIDATAS.md`: los 504, 502 y 400 que no son `Problem`, `keycloakx` en `charts.sh` y el `X-Frame-Options` del 404 de `/auth`.

## Rutas
- Logs: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/` (`r2-ca1.log`, `r2-ca6.log`, `r2-ca7b.log`; `r2-ca7.log` es la corrida interferida)
- Fuentes de v1.9.3 y v1.39.5: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/eg/`

No pude escribir el informe porque no tengo herramienta de escritura. El orquestador debe guardar este texto en `vectra-risk/revisiones/U02-T09/ronda-2.md`.

```
VEREDICTO: NO-VERDE
NARANJA|closed / ratelimit.go:176 v1.9.3 / BR-U2-08 D-5|Las rutas directResponse no tienen rate limit: el 429 de closed no se usa, contradice D-5 en /auth y el tráfico cerrado queda fuera del límite global (decisión del usuario)
AMARILLO|tests/strategies/gateway_expected.py|Quedan literales del diseño en el oráculo (channel, GET/HEAD, closed_profile, 404/429) y 5 alteraciones se atrapan solo por excepción
AMARILLO|CANDIDATAS.md:92|La candidata del Retry-After en /auth sigue en la lista aunque D-5 la resolvió
INFORME: revisiones/U02-T09/ronda-2.md
```
