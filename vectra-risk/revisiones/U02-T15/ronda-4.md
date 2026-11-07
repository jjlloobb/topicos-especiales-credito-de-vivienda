# Ronda 4 — U02-T15 (acotada a F-09)

VEREDICTO: VERDE

F-09 está cerrado. Probé las cuatro mutaciones sobre copias del `identity.js` real y las cuatro mueren. Una mutación de control sobre el gateway falso confirma que la prueba parametrizada nueva es la que detecta el fallo. CA-1 a CA-6 pasan, corridos por mí, con CA-6 en serie después de CA-5. No queda ningún ROJO ni NARANJA. El worktree está limpio en `60f0ceb`, y el hash de la tarea coincide (`654f3fef…`).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | k6 pinneado | `bash platform/install-tools.sh && platform/.tools/bin/k6 version` | pasa: `k6 v2.3.0 (commit/e088784614…)`, SHA OK, ca1=0 (ver la nota de abajo) |
| 2 | Umbrales sin env | `env -i PATH="$PATH" platform/.tools/bin/k6 inspect identity-edge/tests/load/identity.js` | pasa: ca2=0, `p(95)<500/200/50` y `http_req_failed` |
| 3 | Script según el diseño | `uv run pytest identity-edge/tests/unit/test_load_spec.py -q -rA` | pasa: `35 passed in 75.82s`, sin omitidas |
| 4 | Usuarios de carga | `uv run pytest identity-edge/tests/unit/test_load_seed_users.py -q -rA` | pasa: `12 passed in 38.11s` |
| 5 | `check` de U2 con `load-inspect` | `uv sync --frozen && make -C identity-edge check` | pasa: `2584 passed in 1159.54s`, ninguna omitida, `k6 inspect` presente en el log, ca5=0 |
| 6 | U1 sigue cumpliendo (en serie después de CA-5) | `make -C platform check-local` | pasa: ca6=0, `258 archivos Markdown sin enlaces rotos` |

Sobre CA-1: la primera corrida dio `curl: (23)` porque mis cinco copias de mutación llenaron el tmpfs `/tmp`. Fue culpa mía, no del código. Liberé espacio, la volví a correr y salió ca1=0. No volví a probar la parte del SHA-256 alterado: `platform/` no cambia en esta ronda.

Sobre CA-6: el codificador reportó 257 archivos y yo veo 258. El archivo de más es `ronda-4-respuesta.md`, que entró en el mismo commit, así que la cuenta cuadra.

## F-09: mutaciones corridas por mí
Las hice sobre copias completas de `vectra-risk/` en el scratchpad. Cada una lleva el `identity.js` real mutado y corre la suite completa `test_load_spec.py` sin `-x`.

| Mutación | Resultado | Pruebas que la matan |
|---|---|---|
| R01a: `http.cookieJar()` + `jar.clear(BASE_URL)` | muere, `3 failed, 32 passed` | `test_a_relogin_in_the_same_vu_does_not_reuse_the_sso_cookie` y las 2 parametrizadas de F-09 |
| R01b: `const jar = http.cookieJar()` | muere, `3 failed, 32 passed` | las mismas |
| R01c: sin `jar,` en `POST login-actions` | muere, `7 failed, 28 passed` | relogin (`RELOGIN false false`, 400 de AUTH_SESSION_ID), 2 parametrizadas, `two_legs`, `p95_difference…make_load`, `every_request_is_tagged…` |
| R01d: sin `jar,` en `GET auth` | muere, `7 failed, 28 passed` | las mismas 7 |
| FG0 (control): el falso deja de exigir AUTH_SESSION_ID | `2 failed, 33 passed`: fallan justo las 2 parametrizadas (`RELOGIN true true`) | — |

Lo que muestra cada fila:
- **R01c y R01d (lo que pedía el arbitraje):** en la ronda 3 sobrevivían con `33 passed`. Ahora mueren contra el `identity.js` real, no solo dentro de la prueba en memoria. Mi R01c y R01d quitan las mismas líneas (213 y 221) que la regex de la prueba.
- **R01a y R01b:** siguen muriendo, y la prueba de re-login sigue pasando en CA-3.
- **FG0:** las dos pruebas parametrizadas dependen de que el falso exija la cookie, y comprueban el motivo concreto: `AUTH_SESSION_ID` aparece en `bad_requests`. No pasan por cualquier fallo.

El codificador había dicho que solo vio la parametrizada en la corrida completa. Ahora queda comprobado que discrimina.

**No se reabrió nada.** El diff de la ronda (`6de04f9..60f0ceb`) solo toca `fake_gateway_server.py` (+11), `test_load_spec.py` (+25/−4), la bitácora y la respuesta. `identity.js` no cambia y no hay desborde de alcance.

## Hallazgos
### F-11 · AMARILLO · identity-edge/tests/unit/test_load_spec.py:206-232 · el arnés de re-login lanza `TypeError` en `handleSummary`
En las corridas de `_relogin` k6 imprime `TypeError: Cannot read property 'env' of undefined at handleSummary (relogin.js:388)`. Pasa porque `setup` deja de exportarse, así que `data` llega como `undefined`. No cambia las aserciones, porque `RELOGIN …` se imprime antes, pero ensucia la salida y podría tapar otro error del script. Ya venía de la ronda 3: el helper solo lo heredó.

### F-12 · AMARILLO · identity-edge/tests/strategies/fake_gateway_server.py:121,160 · el AUTH_SESSION_ID no queda atado a su login
El POST acepta cualquier AUTH_SESSION_ID emitido antes, y no lo consume. Un script que reusara la cookie de un login anterior en un jar viejo pasaría este control. Hoy eso no ocurre, porque esos jars compartidos ya mueren por la cookie SSO (R01a y R01b), así que no bloquea.

## Tareas candidatas (defectos reales fuera de alcance)
- F-11: exportar o simular `setup` en el arnés de re-login, o neutralizar `handleSummary`, para que la salida de k6 quede sin excepción.
- F-12, opcional: atar el AUTH_SESSION_ID a su `session_code` y consumirlo en el POST.
- F-10 y F-08 siguen en `CANDIDATAS.md` por arbitraje. No los reabro.

## Rutas de transcripciones largas
Todas están en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T15-r4-rev/`:
- `U02-T15-r4-rev-mut-R01a.log`
- `U02-T15-r4-rev-mut-R01b.log`
- `U02-T15-r4-rev-mut-R01c.log`
- `U02-T15-r4-rev-mut-R01d.log`
- `U02-T15-r4-rev-mut-FG0.log`
- `U02-T15-r4-rev-ca1.log` a `U02-T15-r4-rev-ca6.log`, uno por criterio
- `U02-T15-r4-rev-status.log` (`git status` vacío después de CA-6)

Las copias mutadas (`copy-R01a`, `copy-R01b`, `copy-R01c`, `copy-R01d`, `copy-FG0`) siguen en ese mismo directorio. Se pueden borrar.

No escribí el informe en `vectra-risk/revisiones/U02-T15/ronda-4.md` porque mis herramientas son de solo lectura. Este mensaje es el informe completo.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tests/unit/test_load_spec.py:206-232|el arnés de re-login lanza TypeError en handleSummary (no bloquea)
AMARILLO|identity-edge/tests/strategies/fake_gateway_server.py:121,160|el AUTH_SESSION_ID no queda atado a su login (no bloquea)
INFORME: revisiones/U02-T15/ronda-4.md
```
