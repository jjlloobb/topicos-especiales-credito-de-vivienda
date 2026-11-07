# Ronda 5 — U02-T15

VEREDICTO: VERDE

Revisé `tarea/U02-T15` en el sha `818cf7b331e2c3ceaf1bb01b3227bd46a5746ae2`, con el hash de la tarea `654f3fef…` (coincide). Corrí yo mismo CA-1 a CA-6, todos pasan, y no queda ningún hallazgo ROJO ni NARANJA. El worktree quedó limpio (`git status --short` vacío) y en el mismo HEAD.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | k6 pinneado | `bash platform/install-tools.sh && platform/.tools/bin/k6 version` | pasa: `k6 v2.3.0`, ca1=0. En una copia con `K6_SHA256` alterado sale 1 (`sha256sum: … did NOT match`) y no instala k6 |
| 2 | Umbrales sin entorno | `env -i PATH="$PATH" platform/.tools/bin/k6 inspect identity-edge/tests/load/identity.js` | pasa: ca2=0, con login `p(95)<500`, token `p(95)<200`, jwks `p(95)<50` y `http_req_failed rate<0.01` |
| 3 | El script corresponde al diseño | `uv run pytest identity-edge/tests/unit/test_load_spec.py -q -rs` | pasa: `37 passed in 72.49s`, sin omitidas |
| 4 | Usuarios de carga | `uv run pytest identity-edge/tests/unit/test_load_seed_users.py -q -rs` | pasa: `15 passed in 49.33s` |
| 5 | `check` de U2 con `load-inspect` | `uv sync --frozen && make -C identity-edge check` | pasa: `2695 passed in 1193.40s`, ca5=0. `load-inspect` corre `k6 inspect`. Ninguna prueba omitida: las 4 coincidencias de «skip» en el log son los `--skip-tests`/`--skip-crds` de helm |
| 6 | U1, en serie después de CA-5 | `make -C platform check-local` | pasa: ca6=0, `284 archivos Markdown sin enlaces rotos` |

## Lo que verifiqué de cada hallazgo
**C-01.** Bajé el código del tag `26.8.1` con `gh api` y la cita es exacta:
- `HistoryPasswordPolicyProvider.java:56-64` rechaza una contraseña igual a cualquier credencial `password` vigente.
- Las líneas `66-77` rechazan además las `N-1` más recientes de `PASSWORD_HISTORY`.
- `PasswordCredentialProvider.java:90-91` valida y lanza `ModelException`.
- `UserResource.resetPassword` (795-825) convierte esa `ModelException` en 400.
- El chart pinneado es `26.8.1` (`platform/.charts/keycloakx/keycloakx/values.yaml:21`).

`FakeAdmin.reset-password` modela las dos ramas, y el corte `recent[len-(N-1):]` da el resultado correcto también con menos de N-1 entradas.

Borrar y volver a crear al usuario no rompe nada que dependa de su id:
- `delete` busca por `username` exacto, no por id.
- En el Paso 16 y en `tests/load/README.md` nadie guarda ids.
- Las sesiones, los fallos de fuerza bruta y el bloqueo permanente de un usuario se van con él, que es justo lo que pide C-03.
- El `sub` nuevo solo cambia el bucket del rate limit por `sub`, que dura 1 s.
- Los eventos viejos se quedan con el id viejo, y eso no afecta a la carga.

Mutaciones en una copia del código:
- **M4**, volver al `reset-password` de antes: 4 fallos (idempotente, segunda corrida, rehabilitar, reparar rol).
- **M6**, `FakeAdmin` sin historial: falla `test_the_fake_admin_rejects_reusing_the_current_password`.
- **M7**, `FakeAdmin` sin el chequeo de la contraseña vigente: falla esa misma prueba.

**C-03.** `test_it_re_enables_and_cleans_an_existing_user` contamina 3 usuarios con `enabled=False`, `requiredActions=["CONFIGURE_TOTP"]` y `otp=True`, y comprueba que quedan habilitados, sin acciones, sin OTP, con la contraseña y con el rol. La mutación **M5** (no tocar al usuario existente) la hace fallar, junto con `test_it_repairs_a_user_that_lost_its_role`.

**C-02.** Mis mutaciones sobre `identity.js`:
- **M1**, quitar la línea `retryNotBefore`: `AssertionError: 30 logins en 30 iteraciones … assert 30 <= 1`.
- **M2**, `LOGIN_BACKOFF_S = 0`: el mismo fallo, 30 logins.
- En las dos, `test_a_healthy_login_is_not_throttled` sigue pasando con 30 tokens y 1 login. Un VU sano no se frena, y un refresh fallido seguido de un login bueno no activa la espera.

Cota real: `console-burst` llega a 15 VUs y `overhead` a 10, así que el peor caso es unos 25 logins cada 30 s, alrededor de 2,5 req/s contra el límite de 10/s.

**C-05.** `PUBLIC_ORIGIN` sale del mismo cálculo que `REDIRECT_URI` y coincide con `KC_HOSTNAME=https://vectra.localtest.me/auth` (`keycloak/rendered/kind/keycloak.yaml:251`). La mutación **M3** (`aud` con el `BASE_URL` crudo) hace fallar `test_the_script_runs_against_a_fake_gateway_scaled_down` (`checks rate>0.99: FALLA`, `http_req_failed rate<0.01: FALLA`). Con el código original, la misma prueba pasa en la misma copia.

**Nada más se reabrió.** C-04 y C-06 a C-08 están en `CANDIDATAS.md:165-169`. El diff no toca `Makefile`, `load_checks.py`, `CANDIDATAS.md` ni el check `keys.#` (`identity.js:337`). Todo el diff cabe en C-01, C-02, C-03 y C-05.

## Hallazgos
No hay ROJO ni NARANJA. Quedan tres AMARILLO, que no bloquean:

### F-01 · AMARILLO · `tests/strategies/fake_admin.py:84` · la rama de las N-1 contraseñas anteriores no se prueba
Ninguna prueba ejercita el rechazo de una contraseña anterior que ya no es la vigente. Con la mutación M7 solo falla la prueba de la contraseña vigente. `seed_users.py` no usa ese camino, así que no hay riesgo hoy.

### F-02 · AMARILLO · `tests/load/identity.js:252` · `LOGIN_BACKOFF_S` está fuera del bloque de constantes
Es una constante con nombre y con la justificación en un comentario, igual que `USER_RENEW_S`, pero está a mitad del archivo y no junto a las otras (líneas 40-44).

### F-03 · AMARILLO · `tests/unit/test_load_spec.py:156` · el `aud` esperado es un literal
La prueba fija `https://127.0.0.1/auth/realms/vectra/...` a mano. Como oráculo independiente sirve, pero podría derivarse de `KC_HOSTNAME`, o del realm y el host, como ya hace `console_redirect_uris`.

Sobre la evidencia: los logs rojos que cita la bitácora (`U02-T15-r5-c01-rojo.log`, `…c02-c05-rojo.log`) ya no existen, porque `/tmp` se borró. Reproduje esos rojos yo mismo con M1, M3 y M4. Las cifras de la bitácora (2695 en CA-5, 37 y 15) coinciden con mis corridas.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva.

## Rutas de transcripciones largas
- Ninguna: borré todos los temporales y logs de `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T15-r5-rev/` al terminar, como pediste. Las cifras citadas arriba son las de esas corridas.

No escribí el informe en el repositorio: soy de solo lectura. El texto de arriba es el contenido para `revisiones/U02-T15/ronda-5.md`.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tests/strategies/fake_admin.py:84|la rama de las N-1 contraseñas anteriores no se prueba
AMARILLO|identity-edge/tests/load/identity.js:252|LOGIN_BACKOFF_S está fuera del bloque de constantes
AMARILLO|identity-edge/tests/unit/test_load_spec.py:156|el aud esperado es un literal
INFORME: revisiones/U02-T15/ronda-5.md
```
