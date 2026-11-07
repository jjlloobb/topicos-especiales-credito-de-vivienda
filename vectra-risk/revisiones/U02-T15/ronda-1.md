# Ronda 1 — U02-T15

VEREDICTO: NO-VERDE

Revisé e5a27fe sobre origin/main 08e29d2. El hash de la tarea es 0862abdbe6a81f54fb27ec6ee46ccbf75793a72a, el esperado. Corrí CA-1 a CA-6 desde `vectra-risk/`, con CA-5 y CA-6 en serie. Al terminar, el worktree está limpio (`git status --short` sin salida) y sigue en e5a27fe. Todo lo generado (copia mutada, venv y logs) está en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/U02-T15-rev1/`.

Los seis criterios se cumplen, contando aparte los 5 fallos ya conocidos de CA-5. Quedan dos hallazgos NARANJA: el sustituto de J3 no tiene ninguna prueba, y hay literales del diseño en pruebas que la tarea prohíbe.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | k6 pinneado | `bash platform/install-tools.sh && platform/.tools/bin/k6 version` | pasa: `k6-v2.3.0-linux-amd64.tar.gz: OK` contra `checksums.txt` y contra el SHA fijado; `k6 v2.3.0 (commit/e088784614, go1.26.8)`. En una copia con `K6_SHA256=49c3…`: `FAILED`, exit 1, y `k6` no queda en `bin` (`ca1-mut.log`) |
| 2 | `k6 inspect` sin entorno | `env -i PATH="$PATH" platform/.tools/bin/k6 inspect identity-edge/tests/load/identity.js` | pasa: exit 0; `thresholds` trae `{flow:login}` `p(95)<500`, `{flow:token}` `p(95)<200`, `{flow:jwks}` `p(95)<50` y `http_req_failed` `rate<0.01` (`ca2.json`) |
| 3 | Script según el diseño | `uv run pytest identity-edge/tests/unit/test_load_spec.py -q` | pasa: 22 pruebas en 36,4 s. El tiempo se explica: la ejecución contra el gateway falso tarda 30,9 s |
| 4 | Usuarios de carga | `uv run pytest identity-edge/tests/unit/test_load_seed_users.py -q` | pasa: 12 pruebas en 23,0 s |
| 5 | U2 y `load-inspect` en `check` | `uv sync --frozen && make -C identity-edge check` | pasa salvo lo conocido: `load-inspect` corre (k6 inspect y `load_checks.py`, líneas 210-211 del log) y pasa. Resultado: `5 failed, 2546 passed`, sin omitidas. Los 5 fallos son exactamente los de `test_e2e_inventory.py` (U02-T16): `ValueError: substring not found` en `:61`. `ca5=2` solo por esos 5 (`ca5.log`) |
| 6 | U1 con la herramienta nueva | `make -C platform check-local` (después de CA-5) | pasa: `745 passed`, `ca6=0` (`ca6.log`) |

**Pin de k6.** Lo comprobé con `gh api repos/grafana/k6/releases/tags/v2.3.0`:
- se publicó el 2026-09-21T15:17:03Z, hace 46 días, y no es prerelease;
- el digest del asset `k6-v2.3.0-linux-amd64.tar.gz` es `sha256:39c3117b…8ab1`, igual a `K6_SHA256`.

**Mis mutaciones** (`mutaciones.log`, sobre una copia). Matan:
- el diseño cambiado: login 500→400, token 200→150, JWKS 50→40, J7 1 %→2 %, NFR-U2-11 5→3 ms, J5 10/s→1/s, perfil 15→20 min;
- la consola de `routes.yaml` en 20→50;
- en el script: sin `bias-monitoring-job`, o `channel-simulator` en lugar de `channel`;
- quitar `expectedStatuses(200, 429)`;
- en el seed: rol `cro`, `CONFIGURE_TOTP`;
- en el realm: `vectra-mfa-analista` sin `conditional-user-configured`.

Los umbrales salen del diseño. Las mutaciones que sobreviven van en F-01 y F-03.

## Evaluación de las dos decisiones del codificador

**1. J3, `handleSummary`.** Es cierto, lo probé con k6 v2.3.0 real (`j3/`):
- `throw` dentro de `handleSummary` da exit 0;
- `exec.test.abort()` da exit 0;
- `exec.test.fail()` da exit 0. En `default`, en cambio, `exec.test.fail()` da 110.

No encontré ningún mecanismo nativo que cumpla la letra:
- Un umbral sobre una `Trend` personalizada mide el p95 de las diferencias, no la diferencia de los p95 que fija la enmienda de NFR-U2-12.
- `teardown()` con `exec.test.fail()` sí da 110, pero tendría que leer las submétricas por la API REST (`--address`). En v2.3.0 esa API devuelve `p(95):0` durante el teardown, y además el cálculo saldría de `handleSummary`.

La salida que eligió el codificador es razonable: el cálculo se queda en `handleSummary` y `make load` lee el veredicto. Lo probé con un k6 falso: si el veredicto trae `ok:false`, `make load` sale con 1. El desvío de la letra lo tiene que ratificar el usuario. El problema es que el sustituto no tiene ninguna prueba (F-01).

**2. Rol `analista`.** Correcto y sin hueco:
- `domain-entities.md:42` define `pwd` como «Login sin segundo factor (`analista` sin MFA)». BR-U2-03 no nombra `analista`.
- En el realm, `vectra-mfa-analista` exige `conditional-user-configured`. Sin OTP ni WebAuthn el subflujo se salta.
- `default.acr.values: mfa` va como acr por defecto del cliente, no `essential`, así que no fuerza el nivel. Es una afirmación sobre el comportamiento de Keycloak que no comprobé contra un Keycloak real; queda para el Paso 16, como dice la bitácora.
- La ruta `console` de `routes.yaml` admite `roles: analista` y no exige `acr`. `scopeMappings` de `vectra-console` incluye `analista`.

## Hallazgos

### F-01 · NARANJA · `identity-edge/tests/load/identity.js:382`, `tests/strategies/load_checks.py:317`, `identity-edge/Makefile:48-51` · el sustituto de J3 («termina con error») no tiene ninguna prueba
Lo único que hace cumplir NFR-U2-11 es esta cadena: `handleSummary`, luego `overhead-verdict.json`, luego `verdict_problems` y por último `|| code=1`. Ninguna prueba la ejercita con un veredicto que falla, así que estas cuatro mutaciones pasan la suite (`22 passed`):
- **M11:** `ok: true` fijo en `handleSummary`;
- **M12:** `verdict_problems` ignora `overhead`;
- **M13:** el target `load` sin `|| code=1`;
- **M20:** el tramo `direct` apunta a `BASE_URL`. La prueba falsa pone `K6_ECHO_DIRECT_URL = gateway.url`, así que no distingue los dos tramos.

Falta un caso con diferencia de p95 por encima del umbral, que demuestre veredicto `ok:false` y salida distinta de cero de `make load`, y que los dos tramos van a destinos distintos.

### F-02 · NARANJA · `identity-edge/tests/unit/test_load_spec.py:45-54` y `:58-73` · pruebas que fijan valores del diseño con literales propios
La tarea dice: «Ninguna prueba de pytest fija con un literal propio un valor que el diseño fija». El precedente es F-02 de U02-T11 ronda 2, que se calificó NARANJA. Hay dos casos:
- `test_the_design_values_are_the_ones_of_the_plan` repite como literales 500, 200, 50, 0,01, 5, 120/900, 10, 200, 10, 300, `load-`, 20, `"1"` y `"analista"`. Si cambian a la la vez el diseño y el script, esa prueba falla igual.
- Los patrones de `MUTANTS` llevan los mismos valores: `p\(95\)<500`, `const USERS = 200`, `RAMP_S = 120`, `SUSTAIN_S = 900`, `RENEW_S = 300`, `OVERHEAD_P95_BUDGET_MS = 5`, `RETRY_AFTER: '1'`, `USER_PREFIX: 'load-'`. Tras un cambio legítimo del diseño, dan «la mutacion no encuentra».

### F-03 · NARANJA · `identity.js:140` · el umbral `checks: ['rate>0.99']` es un literal sin fuente y nadie lo comprueba
J5 dice que un 429 cuenta como fallo «con `checks` y `http_req_failed`». La parte de `checks`, y también las comprobaciones de `Retry-After` y `rate_limited` de J4, solo hacen fallar la corrida si existe este umbral. Hay dos problemas:
- **Nadie lo comprueba.** Con M19, que borra el umbral, `load_checks.py` sale en 0.
- **El valor no se deriva de nada.** Nada lo liga a J7.

Hay que derivarlo de J7, o escalarlo, y añadirlo a `threshold_problems`.

### F-04 · AMARILLO · `identity.js:136` · el POST de la contraseña puede cambiar de flujo sin que nada lo note
Con M18 (`flow:'token'` en el POST de `login-actions`) la suite pasa. Así, el p95 de login podría dejar de medir el POST de la contraseña sin que ninguna prueba lo detecte.

### F-05 · AMARILLO · `test_load_seed_users.py:241-260` · pruebas de copia mutada tautológicas
`test_a_copy_with_a_role_that_requires_mfa_fails` y `test_a_copy_that_enrols_otp_is_detected` solo afirman propiedades que la mutación ya garantiza. No corren el oráculo sobre la copia. CA-4 se cumple igual, porque mis M15 y M16 hacen fallar las pruebas reales, pero estas dos no demuestran nada.

### F-06 · AMARILLO · `bitacoras/U02-T15.md` y el docstring de `load_checks.py` · la bitácora ubica mal los umbrales
Dicen que los umbrales salen en `options.thresholds`. En v2.3.0, `k6 inspect` imprime `thresholds` y `scenarios` en el primer nivel del JSON. El código lo lee bien; el registro que pedía la tarea es inexacto.

### F-07 · AMARILLO · `CANDIDATAS.md` · las candidatas no están donde dice la tarea
La tarea pide que las candidatas vayan a `CANDIDATAS.md`. El codificador las dejó solo en la bitácora, para no chocar con U02-T13. El orquestador debe trasladarlas.

**Sin hallazgo:**
- **Alcance:** no hay desborde. Nada toca `routes.yaml`, los realms ni la imagen de U12, y el checkbox del plan sigue igual. Añadir `k6` a `check-tools` de `platform/Makefile` es coherente con J2.
- **PromQL:** la métrica y la etiqueta coinciden con `statsd_conf.yaml` de Envoy Gateway v1.9.3 (`ratelimit_server.*.response_time`, que se exporta como `ratelimit_service_response_time_seconds` con `grpc_method`).
- **`k6 inspect`:** ejecuta el init context, lo comprobé con un `console.log`.
- **«Rojo primero»:** la rama tiene un solo commit, así que solo consta en la bitácora y no se puede verificar en el historial.

## Tareas candidatas (defectos reales fuera de alcance)
- `test_e2e_inventory.py` busca `- [ ] **Paso 13`. Ya está asignado a U02-T16.
- Los buckets por defecto de `ratelimit_service_response_time_seconds` (el primero es de 5 ms) no permiten resolver 2 ms. Lo propone la bitácora.
- El port-forward del tramo `direct` puede sesgar la diferencia de p95. Lo propone la bitácora.
- El texto de J5 dice «por debajo de 10/s», pero cada login cuenta 2 hits en `auth-login`, así que el techo real es 5 logins/s.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/U02-T15-rev1/`:
- `ca1.log`, `ca1-mut.log`, `ca2.json`, `ca3.log`, `ca4.log`, `ca5.log`, `ca6.log`
- `mutaciones.log` (M01–M20)
- `j3/` (pruebas de exit code de k6)
- `make-load-false.log`, `make-load-true.log`

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/tests/load/identity.js:382, load_checks.py:317, Makefile:48-51|el sustituto de J3 (veredicto + make load) no tiene ninguna prueba: M11, M12, M13 y M20 sobreviven
NARANJA|identity-edge/tests/unit/test_load_spec.py:45-54, 58-73|literales propios de valores del diseño en pruebas
NARANJA|identity-edge/tests/load/identity.js:140|umbral de checks con un literal sin fuente y sin comprobación (M19 sobrevive)
INFORME: revisiones/U02-T15/ronda-1.md
```
