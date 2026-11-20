# Ronda 1 — U02-T26

VEREDICTO: VERDE

No hay ROJO ni NARANJA. Una salvedad sobre CA-4: mi única corrida de `make -C identity-edge check` terminó con rc 2. Falló una sola prueba, de latencia con k6 contra un gateway falso. Esa prueba no toca nada del diff y, repetida sola, pasa. Lo detallo en F-00, para que el orquestador lo vea y decida.

Comprobaciones previas: el hash de la tarea es `13bab671f4603889a3f239bdc4a8a22769d7276a` y coincide. HEAD `22c70b6`, base `524273a`, un commit, 13 archivos.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Lo generado lleva el plazo y sigue en 503 | `make -C identity-edge route-gen check-route-gen && grep -n -A6 -E 'timeout\|failure_mode_deny\|status_on_error' …/generated/kind/envoypatchpolicies.yaml` | **pasa**: rc 0; `failure_mode_deny: true`, `code: 503`, `timeout` `0.5s`; worktree limpio después |
| 2 | Una prueba lo fija | `uv run pytest identity-edge/tests/unit -q -p no:cacheprovider -k "fail_closed or ratelimit_timeout"` (y `--collect-only`) | **pasa**: 16 passed en 5,3 s. El filtro recoge 16 de 2877, todas las pruebas nuevas de `test_route_gen.py`. No recoge las alteraciones de `test_gateway_xds.py` (sus ids usan guion), pero CA-4 sí las corre |
| 3 | El xDS acepta el parche | `make -C identity-edge xds-gateway` (carga 23) | **pasa**: rc 0; kind, staging y prod con 46 condiciones y 0 sin aceptar |
| 4 | La unidad sigue en verde | `make -C identity-edge check`, una vez (carga 29,8 al empezar y 3,8 al terminar; 25 min) | **rc 2**: todos los objetivos previos pasan; pytest da `1 failed, 2903 passed`. La que falla es `test_load_spec.py::test_the_script_runs_against_a_fake_gateway_scaled_down`. Repetí ese archivo solo (carga 12,6): 35 passed. Ver F-00 |

Lo que leí en `identity-edge/.tools/xds/{kind,staging,prod}.yaml` (es el render de CA-3), en los tres entornos:
- `envoy.filters.http.ratelimit/vectra-edge/auth-rate-limits` tiene `timeout: 0.500s`, `failureModeDeny: true` y `statusOnError: ServiceUnavailable`.
- `…/edge-rate-limits` y el filtro del listener (`envoy.filters.http.ratelimit`) no tienen `timeout`, ni `failureModeDeny`, ni `statusOnError`.

El parche localiza el filtro por nombre (`?(@.name=='…/auth-rate-limits')`), no por índice, y los otros dos parches no cambian.

## Lo que pediste apretar
1. **La causa: confirmada en una fuente local, aunque no en la versión exacta.** go-control-plane `envoy@v1.32.4`, en una capa de contenedor local (`~/.local/share/containers/storage/overlay/07dec647…/diff/go/pkg/mod/github.com/envoyproxy/go-control-plane/envoy@v1.32.4/extensions/filters/http/ratelimit/v3/rate_limit.pb.go:214-216`), dice: «The timeout in milliseconds for the rate limit service RPC. If not set, this defaults to 20ms». El `egctl` de `platform/.tools` está compilado con go-control-plane v1.40.0, que no trae ese comentario, así que en esa versión no lo pude confirmar. El render de antes del cambio no lleva `timeout`, y eso cuadra con la bitácora.
2. **El parche está bien y va solo en ese filtro**, en los tres entornos (ver arriba).
3. **`edge.rego` no afloja nada.** Probé `conftest` con mutaciones del `EnvoyPatchPolicy`:
   - rechaza: sin timeout, timeout de más, timeout en lugar de `status_on_error`, `failure_mode_deny: false`, `code: 500`, `op: remove` en el timeout, timeout sobre `edge-rate-limits`, y la ruta `failure_mode_deny` con `false`;
   - acepta: el original;
   - también acepta un valor `0.02s` o `100s` (ver F-02).
4. **Rojo primero y mutaciones**, en una copia del scratchpad, con CA-2 y `route_gen --check`:
   - sin `timeout`: 4 fallan, rc 1;
   - `failure_mode_deny: false`: 3 fallan, rc 1;
   - `20ms`, `3s`, `500`, `2s` y `21ms`: 3 fallan, rc 1;
   - `0.5s`: pasa, rc 0; es el mismo valor en el formato `Ns`, que se admite a propósito.

   Llamando directamente al validador: `20ms`, `3s`, `2001ms`, `500`, `' 500ms'` y `1e3ms` dan `RoutesError`; `2000ms` da `2s` y `20.5ms` da `0.0205s`.

   No vuelvo a correr el «rojo» del codificador (14 failed, 2 passed), pero es coherente: las dos que pasaban son las `refuses_…[failure_mode_deny|status_on_error]`, que aceptan `KeyError`.
5. **Staging y prod:** la bitácora y el ADR dicen con claridad que el valor es una «decisión de diseño a confirmar». El comentario de `routes.yaml` solo dice «igual en los tres entornos» (ver F-03).
6. **Runbook:** separa bien el servicio caído de la consulta lenta, y los campos `status`, `response_flags` y `duration_ms` existen en `access_log.fields`. Con `GatewayNamespace` el Deployment se llama `api-gateway`. Hay un detalle con varias réplicas (ver F-04).
7. **Órdenes para el orquestador:** son correctas y prudentes. La Application `gateway` existe (`vectra-risk-gitops/apps/kind/gateway.yaml`, `targetRevision: main`), la orden va «tras fusionar», se lee de vuelta con `status.ancestors[*].conditions` y se miden N logins con cero `RLSE`.
8. **Lo demás:** `CANDIDATAS.md` solo crece al final (3 líneas). No hay cambios en `platform/operators`. No encontré secretos.

No corrí el pytest de `platform`: busqué con grep y nada de `platform` lee `edge.rego` ni `envoypatchpolicies.yaml`. Solo lee `envoyproxies.yaml` y `securitypolicies.yaml`, que no cambian.

## Hallazgos
### F-00 · AMARILLO · CA-4 · Mi corrida de `check` sale rc 2 por una prueba de carga que depende del tiempo
`test_load_spec.py::test_the_script_runs_against_a_fake_gateway_scaled_down` falló así: «NFR-U2-11 sobrecosto p95 gateway 16.76 ms - directo 10.84 ms = 5.92 ms (maximo 5 ms): FALLA». Compara dos gateways Python falsos con k6, no usa nada del diff, y la carga estaba entre 13 y 30. Repetida sola pasa (35 passed). No la cuento como ROJO del diff, pero tampoco puedo decir que vi rc 0 en mi propia corrida. Si quieres esa evidencia, hace falta otra corrida completa con la máquina en calma.

### F-01 · AMARILLO · `tools/route_gen.py:689` · El mensaje de error repite los topes a mano
El mensaje escribe «(20ms)» y «2s» como texto fijo, en vez de tomarlos de `RATELIMIT_TIMEOUT_DEFAULT_S` y `RATELIMIT_TIMEOUT_MAX_S`. La comparación sí usa esas constantes.

### F-02 · AMARILLO · `gateway/policy/edge.rego:578-583` · La regla no mira el valor del timeout
Exige un `timeout` pero acepta `0.02s` o `100s`. El rango solo lo cubren `route_gen`, `check-route-gen` y `test_gateway_xds`. Con mirar el formato y el rango en rego, una edición a mano de lo generado también quedaría frenada por la política.

### F-03 · AMARILLO · `gateway/routes.yaml:47` · El comentario no dice que staging y prod están por confirmar
Lo dicen la bitácora y el ADR, pero el comentario de `routes.yaml` no.

### F-04 · AMARILLO · `runbooks/rate-limit-backend-down.md:22` · `kubectl logs deploy/…` lee un solo pod
`envoy-ratelimit` tiene dos réplicas y `deploy/…` solo muestra los logs de una. Mejor `-l <selector> --prefix`.

### F-05 · AMARILLO · `tests/unit/test_gateway_xds.py:61` y `test_route_gen.py` · Las pruebas no traen un caso que aísle `status_on_error`
`"0.500s"` va como texto fijo en vez de salir de `AUTH_RATELIMIT_TIMEOUT`; eso es aceptable en un oráculo. El problema es que `refuses_…[failure_mode_deny|status_on_error]` aceptan `KeyError`, o sea, el generador no valida que esos campos estén. Y la mutación de `status_on_error` en `routes.yaml` no la repetí yo con el filtro de CA-2.

## Tareas candidatas (defectos reales fuera de alcance)
- U2 (`identity-edge/tests/unit/test_load_spec.py`, el fixture `within_budget`): el umbral de 5 ms del sobrecosto p95 contra gateways falsos depende de la carga y rompe `make check` en un portátil cargado. Hay que darle margen o aislarlo.
- Las tres que añadió el codificador (sentinel, plazo de los filtros fail-open y el 503 de `mark-active`) me parecen bien fundadas.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4ae739e1-8e17-45a7-86d4-a1f29d9f6082/scratchpad/rev-u02t26-ca4.log (CA-4 completo; bórralo cuando lo guardes)

Limpieza: quité `platform/.tools` (el enlace) y `platform/.charts` (la copia), y también la copia del scratchpad y las mutaciones. `git status --short` queda vacío. `identity-edge/.tools/` ya estaba antes (ignorado por git) y mi CA-3 lo reescribió.

```
VEREDICTO: VERDE
AMARILLO|CA-4 (test_load_spec.py)|check rc 2 en mi corrida por una prueba de latencia ajena al diff; aislada pasa
AMARILLO|tools/route_gen.py:689|el mensaje de error repite 20ms y 2s a mano
AMARILLO|gateway/policy/edge.rego:578|la regla no acota el valor del timeout
AMARILLO|gateway/routes.yaml:47|no marca staging/prod como decisión por confirmar
AMARILLO|runbooks/rate-limit-backend-down.md:22|logs deploy/… lee un solo pod de varias réplicas
INFORME: revisiones/U02-T26/ronda-1.md
```
