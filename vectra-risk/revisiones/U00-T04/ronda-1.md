# Ronda 1 — U00-T04

VEREDICTO: VERDE

Árbol de trabajo limpio al terminar (`git status --short` vacío) y HEAD en e927781. El hash de la tarea coincide: 4ffbec2b3a7211442aab05eb31aaaf1366911b2a. No queda ningún contenedor `u02t21|u00t04` (cuenta 0). Ninguno de mis contenedores quedó vivo. Los Keycloak ajenos (u02t22-…) no los toqué.

## Medida contra Keycloak real
Corrí `uv run python identity-edge/tools/measure_issuer.py` a las 16:15, con carga 2,7 → 13,0 y sin otro Keycloak arriba. Contenedor `u02t21-0bab41`, en 127.0.0.1:42727. Todo fue a 127.0.0.1:<puerto>; el host interno se desvió por Host/SNI. No toqué ni el 443 ni kind.
- M-c, `aud` configurada: `ServiceTokenProvider` **importado de la rama**, con `token_url` = URL interna y `assertion_audience=https://vectra.localtest.me/auth/realms/vectra`. Respuesta **HTTP 200**, con `iss` = `https://vectra.localtest.me/auth/realms/vectra`.
- M-c, `aud` antigua (`assertion_audience` = URL interna de token): **HTTP 400**, `invalid_client: Invalid token audience`.
- M-b repite lo de U02-T21: URL interna 400, URL pública 200, emisor público 200, emisor interno 400.
- **Mutación:** con `_assertion` firmando `"aud": self._token_url`, repetí la medida. Ahora M-c con `aud` configurada da **400** `Invalid token audience`, así que la medida cae. `test_service_token.py` también cae: 3 fallan y 21 pasan (`test_assertion_claims_and_signature`, `…_is_the_configured_one_and_not_the_token_url`, `…_is_read_from_the_environment`). La mutación quedó revertida.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | U0: `aud` configurada y envío a la URL de token | `uv run pytest contracts/tests/unit/test_service_token.py -q -k assertion_audience` | pasa, 8 de 8 (ver F-03) |
| 2 | Keycloak real | `measure_issuer.py` más los tres `grep` y `docker ps` | 200 y 400; filas 76 y 77 del documento; secretos 0; contenedores 0 |
| 3 | Mundo cerrado | `uv run pytest platform/tests/test_token_issuer.py … -v` | pasa, 91 de 91 |
| 4 | Mutaciones de audiencia | `-k "mutation and audience"`, y aparte `-k "mutation and not audience"` | pasan 19, y siguen pasando las 31 de U02-T21 |
| 5 | Ningún workload atrás | `diff url.txt aud.txt`, los dos `grep`, y `mypy --strict contracts/python` | `diff` vacío (10 archivos en cada lista); el segundo `grep` sin salida; el tercero da una línea por archivo; mypy sin errores |
| 6 | Dobles | las seis órdenes de CA-6 | verde: 5, 1, 1, 1, 2 y 6 pasan. Con U0 mutado, **las seis terminan en 1** |
| 7 | Job de U4 | `uv run pytest governance/tests -k assertion_audience` | pasan los dos casos nombrados. `VECTRA_TOKEN_AUDIENCE` sigue con su valor por omisión `governance-service` |
| 8 | Lo generado está al día | `generate.py --check`; `make -C identity-edge check-jobs-rendered policy-jobs policy-jobs-u1`; `policy-chart` y `policy-chart-u1` de U9 y U11 (los de U4 y U7, dentro de su `check`); `git diff --exit-code` de `openapi/ts` | rc 0 en todos |
| 9 | Cambio mínimo | las dos órdenes de CA-9, contra 8dc7499 | sin salida |
| 10 | `make check` (RL-4) | ver la tabla de regresión | rc 0 en las cuatro que corrí |
| 11 | Documentos y candidatas | los `grep` y `test_links.py` | cada archivo da al menos 1 línea; las dos candidatas quedan «Resuelta (U00-T04)»; 558 archivos sin enlaces rotos |

**El cambio de U0.** El diff contra la base solo toca el parámetro `assertion_audience` (solo por nombre, sin valor por omisión, `ValueError` si está vacío), el claim `aud`, la lectura en `provider_from_env` y los docstrings. La caché, `RENEW_BEFORE`, el candado, el formulario y el `poster` no cambian.

**Constructores (`grep` en todo el repositorio).** Todos pasan la audiencia: `governance/service.py` y `validation_job/run.py`, que son directos, y los que pasan por `provider_from_env`: U2, U7 (como fábrica, llamada al arrancar en `build_deps`), U8, U9 y U11. `promotion-tool` y `console/bff` no piden token. `system-verification` en esta rama no firma aserciones. En `origin/main`, U12 firma `aud = self._environment.issuer` (`clients/oidc.py:638`) sin usar `vectra_common`. `e2e_support.py:293` e `identity.js:302` siguen con `aud` = URL pública: quedan fuera por P-5 y ya están anotados en candidatas.

**Charts.** Lo comprobé sobre los renders mismos, con un volcado del mundo de la prueba en `dump.log`. En kind, staging y prod, los diez workloads que piden token tienen `VECTRA_ASSERTION_AUDIENCE` igual al emisor que publica el render de Keycloak de su entorno: governance-service, bias-monitoring-service, bias-monitoring-job, product-metrics, scoring-service, explainability-service, case-service, case-worker, realm-drift y signing-key-age. Ningún workload que no pide token la lleva. El `model-validation-job` la recibe por la ruta `ApiConfig.assertion_audience` → `JobSpec` → `job_manifest` (`k8s_jobs.py:132`).

**Mis mutaciones sobre los charts.** Las cinco cayeron, y cada mensaje nombra `<env>/<workload>`:
1. Quitar la línea del chart de U7: 9 fallan, cada uno con «kind/scoring-service: pide token … y no rinde».
2. Poner la URL de token en el chart de governance: 3 fallan.
3. Poner el emisor de staging en kind para product-metrics: 1 falla.
4. Añadir un Job nuevo en el chart de U9 con solo `VECTRA_TOKEN_URL`: 3 fallan (`<env>/revisor-nuevo`). El archivo lo borré después.
5. Pasar el ayudante de U8 a `valueFrom`: 6 fallan con «llega sin `value` literal».

**Dobles.**
- Con U0 mutado, el doble de `test_service_build_app` (U4) responde 400 y la prueba cae (2 fallan).
- Sin la exigencia del doble y con U0 mutado, U11 y U7 siguen cayendo: sus pruebas leen la `aud` que recibió el doble.

**Imagen.** `make -C case-management test-image`: 13 pasan en 52 s. La imagen ya llevaba el `service_token` de la rama (lo comprobé dentro del contenedor). Si un chart no pusiera la variable, el contenedor real no arranca: `provider_from_env` lanza `KeyError`, o lo para la lista de obligatorias de U4 y U9. Así que «solo si el chart la pone» no deja pasar ese caso. Ver F-04.

## Regresión (RL-4), en serie con el `TMPDIR` por omisión
| Corrida | rc | Duración | Carga antes → después |
|---|---|---|---|
| `make -C contracts check` | 0 (`bench_gate` ok: p99 0,060 y 1,306 ms) | 351 s | 2,7 → 17,8 |
| `make -C governance check` | 0 | 425 s | 17,8 → 7,9 |
| `make -C scoring-explainability check` | 0 | 531 s | 7,9 → 12,9 |
| `make -C platform check-local` | 0 (925 pasan) | 413 s | 12,9 → 8,7 |
| `generate.py --check`, `uv lock --check`, `test_links.py` | 0, 0, 0 | segundos | 7,4 |

Todo pasó al primer intento; no hubo fallos por tiempo. **No corrí `make -C identity-edge check`** por falta de margen. En su lugar corrí lo que el diff toca: `test_identity_jobs.py` (147 pasan, 59 s; usa `jobs_checks.py` y `jobs_design.py`), `make -C identity-edge lint` y `check-jobs-rendered policy-jobs policy-jobs-u1`, todos con rc 0.

## Hallazgos
Ninguno es ROJO.

### F-01 · NARANJA · identity-edge/jobs/policy/jobs.rego (bloque `assertion_audiences`) · Los tres emisores incrustados como literales en la regla
La regla acepta `VECTRA_ASSERTION_AUDIENCE` solo si es uno de tres literales que copian el `KC_HOSTNAME` de cada render. Si el hostname de un entorno cambia, la regla queda desfasada; la prueba de mundo cerrado sí lo detectaría. El valor no es visible para el usuario, pero está duplicado en un punto de decisión. Lo mismo pasa con `measure_issuer.py`, cuya «aud configurada» es el literal `f"https://{PUBLIC_HOST}/auth/realms/vectra"` y no `kc_env["KC_HOSTNAME"]`. Por RL-2 va a CANDIDATAS.

### F-02 · AMARILLO · governance/tests/integration/test_service_build_app.py:56 · El doble es la única defensa de esta prueba
Con el doble aceptando cualquier `aud` y U0 mutado, el archivo pasa (6 de 6). El defecto lo sigue atrapando `test_service_config.py::test_assertion_audience_…`. En U7 y U11, en cambio, la prueba lee la `aud` registrada.

### F-03 · AMARILLO · contracts/…/service_token.py:45 · Con la variable vacía, el error no nombra la variable
CA-1(e) dice que el error «la nombra». Con `VECTRA_ASSERTION_AUDIENCE=""`, `provider_from_env` lanza `ValueError("assertion_audience must not be empty")`, que nombra el parámetro, no la variable. El alcance (punto 2) solo pide `ValueError` al construir, y ese punto se cumple; además el `required` del chart hace imposible el vacío. La bitácora lo declara.

### F-04 · AMARILLO · */tests/integration/test_image.py (U8, U11) · Falta un caso de imagen sin la variable
Ningún caso de contenedor real comprueba que, sin `VECTRA_ASSERTION_AUDIENCE`, el proceso no arranca y que el log la nombra. Sí lo hay para `VECTRA_TOKEN_URL` en U11 (`drop=("VECTRA_TOKEN_URL",)`). U9 solo fija el conjunto exacto de variables del CronJob.

### F-05 · AMARILLO · platform/tests/test_token_issuer.py, `REQUESTERS` · `case-service` y `case-worker` no están en la lista mínima
Hoy se descubren y se comprueban. Pero si U8 dejara de rendir `VECTRA_TOKEN_URL`, `test_the_workloads_are_discovered` no lo notaría.

**Archivos fuera de «Cambios permitidos».** Los cinco `.rego`, el `workload.rego` de U8, `jobs_checks.py` y los documentos de `aidlc-docs` son necesarios: `policy-chart` y las reglas de entorno exacto fallarían sin ellos, y `jobs_design` lee el diseño. Se limitan a añadir la variable nueva, salvo el `deny` nuevo de `governance/chart/policy/service.rego`, que exige que la variable termine en `/realms/vectra` (también acotado) y el de F-01. Están declarados en la bitácora y en CANDIDATAS.

## Tareas candidatas (defectos reales fuera de alcance)
- F-01, F-02, F-04 y F-05, según RL-2.
- `e2e_support.py:293` e `identity.js:302`: unificar su `aud` con el emisor. Ya está anotada.

## Rutas de transcripciones largas
Todas están en /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/r1/:
- `medida-1.log` y `medida-mutada.log`
- `ca3.log`, `dump.log` y `mut-m1-sin-variable.log` … `mut-m5-valuefrom.log`
- `ca6-verde-*.log`, `ca6-u0mut-*.log`, `gov-sba-*.log`, `pm-both.log` y `se-both.log`
- `cm-test-image.log`
- `check-contracts.log`, `check-governance.log`, `check-scoring-explainability.log` y `check-platform.log`
- `ie-jobs.log`, `ie-lint.log`, `ie-jobs-policy.log` y `policy-*.log`

`check-local.log`, en ese mismo directorio, es de las 01:58, anterior a esta revisión, y no lo uso como evidencia.

```
VEREDICTO: VERDE
NARANJA|identity-edge/jobs/policy/jobs.rego (assertion_audiences)|Tres emisores incrustados como literales en la regla
INFORME: revisiones/U00-T04/ronda-1.md
```
