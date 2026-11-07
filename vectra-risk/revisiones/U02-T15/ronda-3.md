# Ronda 3 — U02-T15

VEREDICTO: NO-VERDE

R-01 a R-05 están cerrados, y CA-1 a CA-6 pasan con mi propia ejecución. Queda en pie un NARANJA, F-09. El arreglo de R-01 añadió un riesgo nuevo que ninguna prueba cubre: que el GET de autorización y el POST de la contraseña usen el mismo jar. Hoy el código está bien. El hallazgo es de cobertura: si se borra la opción `jar` de cualquiera de las dos peticiones, la suite sigue en verde. Contra Keycloak real eso rompería los 200 logins.

**Contexto de la revisión**
- **Tarea:** hash 654f3fef47692416657883d03b4c8d6735ce57b6, el esperado.
- **Diff revisado:** 833c10a..2c5bd64. Toca 6 archivos y todos están dentro del alcance; no toca `CANDIDATAS.md`, el plan, `routes.yaml` ni los realms.
- **Merge 8190312:** `git diff 2c5bd64 8190312 --stat` lista solo archivos de U02-T16 (bitácora, revisiones, tarea y `test_e2e_inventory.py`), más una línea añadida al final de `CANDIDATAS.md` y 11 de `audit.md`. Coincide con lo que dijo el orquestador.
- **Mutaciones:** las hice en una copia sacada con `git archive 8190312`.
- **Estado final:** el worktree queda limpio (`git status --short` no imprime nada) y en 8190312.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | k6 pinneado | `bash platform/install-tools.sh && platform/.tools/bin/k6 version` | pasa: `k6-v2.3.0-linux-amd64.tar.gz: OK`, `k6 v2.3.0 (commit/e088784614, go1.26.8)`. No repetí la mutación del SHA-256: `install-tools.sh` y `tools.env` no cambian en esta ronda (en la ronda 2 dio `FAILED`) |
| 2 | `k6 inspect` sin entorno | `env -i PATH="$PATH" platform/.tools/bin/k6 inspect identity-edge/tests/load/identity.js` | pasa: exit 0. Umbrales p95 de login (500), token (200) y jwks (50), `http_req_failed rate<0.01`, `checks rate>0.99`. El env de `users` es `load-`/1/200 y el de `overhead` es `MAX_DIFF_P95_MS: '5'` |
| 3 | Script según el diseño | `uv run pytest identity-edge/tests/unit/test_load_spec.py -q` | pasa: 33 en 96,1 s. El tiempo se explica: dos `make load` reales de 30 s y un `k6 run` de re-login |
| 4 | Usuarios de carga | `uv run pytest identity-edge/tests/unit/test_load_seed_users.py -q` | pasa: 12 en 123,9 s, con CA-5 corriendo a la vez |
| 5 | U2 y `load-inspect` en `check` | `uv sync --frozen && make -C identity-edge check` | pasa: `ruff` limpio, `load-inspect` en la línea 210 del log, `2582 passed in 2696.48s`, 0 fallos y 0 omitidas, `ca5=0`. Con el merge desaparecen los 5 fallos de U02-T16 |
| 6 | U1 con la herramienta nueva | `make -C platform check-local`, después de CA-5 (11:51 a 11:55) | pasa: `745 passed`, `255 archivos Markdown sin enlaces rotos`, `ca6=0` |

## Verificación de R-01 a R-05 con k6 v2.3.0 real

Sondeo propio (`exp/r02.js` contra `exp/srv.py`, un servidor HTTP mínimo):
- **R-01:** el servidor pone `KC=1; Path=/auth/realms/vectra/` y `ROOT=1; Path=/`.
  - Antes de limpiar se envían `KC=1; ROOT=1`.
  - Después de `cookieJar().clear(BASE)` se sigue enviando `KC=1`.
  - Con `new http.CookieJar()` no se envía ninguna cookie.

  Confirmo el defecto y el arreglo.
- **R-02:** `r.json('code')` devuelve `undefined` sin lanzar con un 429 sin cuerpo, con HTML, con texto y con JSON truncado (`{"code":`). La tesis del codificador es correcta: no es un defecto, y el check `rate_limited` queda en falso, que es lo que debe pasar.
- **R-04:** en `handleSummary`, `exec.test.options.scenarios.overhead.env` vale `{"MAX_DIFF_P95_MS":"5"}` y `Number(...)` da 5. Existe en v2.3.0.

Mutaciones en la copia, todas con `test_load_spec.py` completo:

| Mutación | Resultado |
|---|---|
| R01a: vuelve `cookieJar().clear(BASE_URL)` y el jar del VU | muere: `test_a_relogin_in_the_same_vu_does_not_reuse_the_sso_cookie` |
| R01b: `const jar = http.cookieJar()`, el jar compartido del VU | muere: la misma prueba |
| R05a, R05b, R05c: el redirect con puerto (código de la ronda 2), con `http://` o con ruta | mueren: 3 fallos cada una (`…scaled_down`, `…redirect_uri_is_one_of_the_registered_ones`, `…relogin…`) |
| R03a: `USER_PREFIX` pasa a `'test-'` | muere: 3 fallos, entre ellos `test_the_script_matches_the_design` |
| R03b y R03c: `usersFlow` ignora el env (prefijo fijo, o `first = 5`) | mueren: `…scaled_down`. El script lee de verdad el env que valida `load_checks` |
| R04a: `const budget = 99` en `handleSummary` | muere: 2 fallos (`budget_ms` comparado con NFR-U2-11) |
| R04b: el env de `overhead` pasa a `'50'` | muere: 4 fallos |

## Regresiones de las rondas 1 y 2 (misma copia)
- **Mueren como antes:** M11, M12, M13, M18, M19, M19b, M20, M21, F02d, F05a (4 fallos), F05b y M15.
- **Pasan como deben** (diseño y script cambiados juntos): F02a, F02b y F02c, con 33 pruebas cada una.

Sin regresiones.

## Hallazgos

### F-09 · NARANJA · `identity-edge/tests/load/identity.js:213,221` y `tests/strategies/fake_gateway_server.py` · nadie comprueba que el GET y el POST del login usen el mismo jar
Antes de esta ronda las dos peticiones usaban el jar del VU, así que compartían cookies sin que nadie lo pidiera. El arreglo de R-01 pasa a mano un jar nuevo a cada una, y eso convierte la continuidad en algo que puede romperse. El gateway falso no la modela: pone cookie solo en el POST y no exige ninguna en el POST.
- **Mutación R01c** (se quita `jar,` del POST de `login-actions`): **sobrevive**, `33 passed in 76.66s` (`mut-R01c.log`).
- **Mutación R01d** (se quita `jar,` del GET de autorización): **sobrevive**, `33 passed in 82.25s` (`mut-R01d.log`).

Keycloak deja `AUTH_SESSION_ID` y `KC_RESTART` en `/auth/realms/vectra/` al responder el GET de autorización, y en el POST de `login-actions` los necesita. Sin ellos devuelve la página de cookie no encontrada o de sesión expirada, no un 302. Esto no lo comprobé corriendo: en esta tarea no hay clúster. Si se diera cualquiera de las dos mutaciones, fallarían los 200 logins del Paso 16 y toda la suite seguiría en verde.

Arreglo esperado:
- El falso pone una cookie de sesión de autenticación en la respuesta del GET.
- El POST la exige y responde 400 si falta.
- R01c y R01d tienen que morir.

### F-10 · AMARILLO · `identity.js` (`usersFlow`) · sin el env del escenario, el nombre de usuario sale `undefinedNaN`
Si `usersFlow` se ejecuta fuera del escenario `users`, `Number(undefined)` da NaN y el nombre de usuario sale `undefinedNaN`, sin un error claro. Hoy no es alcanzable: `load_checks` valida el env. No bloquea.

### F-08 (ronda 2) · AMARILLO · `test_load_spec.py:80` · sigue en pie, no bloquea.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva. Siguen las de las rondas 1 y 2, y R-06 a R-10, que ya están en `CANDIDATAS.md`.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/867b1fea-269a-4c16-81df-8687b45e3363/scratchpad/U02-T15-r3-rev/`:
- `ca1.log`, `ca2.json`, `ca3.log`, `ca4.log`, `ca5.log`, `ca6.log`, `ca56.times`
- `mutaciones.log`, `mut-R01c.log`, `mut-R01d.log`
- `bench/mut.py`, el banco de mutaciones
- `exp/r02.js`, `exp/srv.py`, `exp/exp.log`, el sondeo de R-01, R-02 y R-04
- `copy/`, la copia de 8190312

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/tests/load/identity.js:213,221|nadie comprueba que el GET y el POST del login usen el mismo jar (R01c y R01d sobreviven)
INFORME: revisiones/U02-T15/ronda-3.md
```
