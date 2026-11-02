# Ronda 3 — U02-T05

VEREDICTO: VERDE

Contexto comprobado: el hash de la tarea es `021c81a338479e1444cc8d3369d7c1ec15917ec0` y coincide. El worktree está en `767e267` y queda limpio (`git status --porcelain` da 0 líneas). Los commits desde `48ba8e1` son tres: `3137fa1` (mi informe de la ronda 2), `a75a6b6` (enmienda E4 y CA-4 del orquestador) y `767e267` (codificador). Este último toca solo `realm_lint.py`, `test_realm_lint.py`, la bitácora y `ronda-2-respuesta.md`.

Ejecuté todo sobre `git archive 767e267` en la scratchpad `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t05-r3/`, con venv propio y `UV_OFFLINE=1`. Al terminar borré el venv y las copias, y no queda ningún proceso en segundo plano.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Pasa con `CONFIGURE_TOTP` o con `otp` referenciada; falla sin ninguna, con literal y con otro tipo; en kind, staging y prod | `uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k otp_credential` | pasa: 348 passed, 170 deselected, 0.41 s (prueba unitaria pura) |
| 2 | Lo anterior sigue cumpliendo | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests -q && uv sync --frozen && make -C identity-edge check` | pasa: 529 passed, sync ok, «All checks passed!», 529 passed, EXIT=0. `mypy --strict`: sin errores |
| 3 | Forma única de domain-entities §3 | `... -k otp_credential_form` | pasa: 87 passed |
| 4 | `credentialData` exacto, campos en su sitio, usuario sin `username` | `... -k otp_credential_data` | pasa: 78 passed |
| — | Solo cambió la regla de MFA | `git diff 2dbe403..767e267 -- identity-edge` | sí. Las únicas líneas que se quitan de la base son las dos del bloque `mfa-obligatorio`. Los hunks del lint son import, constantes, helpers de la credencial y el bloque MFA |
| — | El `ruff format` no metió cambios ajenos | el mismo diff y `ruff format --check` de los dos archivos en `2dbe403` | sí. Contra la base, el test solo añade el bloque OTP (hunk `@@ -78,6 +79,248`) y no quita ninguna línea previa. Los dos archivos ya daban «would be reformatted» en la base, así que lo que no está formateado es anterior a la tarea. El reformateo de 767e267 solo toca líneas de esta tarea |

Los hallazgos de la ronda 2 quedan cerrados:
- F-01: N5 y N6 mueren, 3 failed cada uno.
- F-02: N11 muere con 12 failed. Además, N12 (aceptar `username` vacío) muere con 3 failed.
- F-03: lo resolvió la decisión E4, que fija CA-4.

## Mutaciones: 24 previas y 13 nuevas; lint restaurado y comprobado con `cmp`
| Mutación | Resultado |
|---|---|
| M1 prefijo | 24 failed |
| M2 referencia parcial | 36 failed |
| M3 cualquier literal | 105 failed |
| M4 cualquier tipo de credencial | 48 failed |
| M5 tipo sin distinguir mayúsculas | 12 failed |
| M6 `secretData` como mapa | 6 failed |
| M7 cualquier `$(env:…)` | 42 failed |
| M8 quitar la credencial referenciada | 30 failed |
| M9 aceptar `${…}` | 12 failed |
| M10 `value` de primer nivel | 3 failed |
| M11 quitar la acción `CONFIGURE_TOTP` | 73 failed |
| M12 solo la primera credencial | 3 failed |
| M13 cualquier `SYNTH_*_TOTP_SEED` | 6 failed |
| N1 la variable de otro usuario | 6 failed |
| N2 conservar el `-` | 33 failed |
| N3 borrar el `-` | 30 failed |
| N4 sin mayúsculas | 30 failed |
| N5 `secretEncoding` en `secretData` | 3 failed |
| N6 `secretEncoding` en el primer nivel | 3 failed |
| N7 ignorar `secretEncoding` | 27 failed |
| N8 codificación sin distinguir mayúsculas | 3 failed |
| N9 leer `secretEncoding` solo de `secretData` | 33 failed |
| N10 semilla en `credentialData` | 529 passed, sobrevive (equivalente, ver abajo) |
| N11 aceptar usuario sin `username` | 12 failed |
| N12 aceptar `username` vacío | 3 failed |
| D1 sin comprobar el tipo de cada valor | 9 failed |
| D2 aceptar claves extra (basta que estén las cinco) | 21 failed |
| D3 no admitir `counter: 0` | 3 failed |
| D4 exigir `counter: 0` | 27 failed |
| D5 cualquier `counter` | 12 failed |
| D6 `subType: hotp` | 3 failed |
| D6 `digits: 8` | 3 failed |
| D6 `period: 60` | 3 failed |
| D6 `algorithm: HmacSHA256` | 3 failed |
| D6 `secretEncoding: BASE64` | 6 failed |
| D7 aceptar campos ausentes | 36 failed |
| D8 ignorar claves extra | 9 failed |
| D9 exigir que `secretData` no tenga claves extra | 529 passed, sobrevive (ver F-01) |

**El argumento del codificador sobre N10 es correcto.** N10 solo cambia el resultado cuando la semilla de `secretData` no vale y `credentialData` trae una clave `value`. En ese caso, `_same_json` exige que las claves sean exactamente las cinco, o las cinco más `counter`, así que esa clave `value` ya rechaza la credencial. Es un mutante equivalente bajo CA-4. Lo confirmé con la variante que además quita `value` de `credentialData` antes de comparar (N10b), y muere con 3 failed.

## Hallazgos
### F-01 · AMARILLO · identity-edge/tools/realm_lint.py:188 · `secretData` admite claves extra
`credentialData` es exacto (E4), pero `secretData` solo se lee por `value`. Por eso el lint acepta `secretData: '{"value":"$(env:SYNTH_…_TOTP_SEED)","secretEncoding":"BASE32"}'` cuando `credentialData` está completo. El mutante D9, que rechaza esas claves extra, sobrevive con 529 passed. domain-entities dice que `secretEncoding` va en `credentialData` «y nunca al revés», y escribe `secretData` como `'{"value":"…"}'`. Pero E4 solo declaró exacto `credentialData`, así que es una ambigüedad de diseño y no un incumplimiento de CA-3 ni de CA-4. No bloquea.

### F-02 · AMARILLO · identity-edge/tests/unit/test_realm_lint.py · Formato de ruff fuera de `make check`
`ruff format --check` marca los dos archivos como «would be reformatted», tanto en la base como en `767e267`. `make check` solo corre `ruff check`. No es de esta tarea. Lo anoto porque el codificador lo aplicó por error y lo deshizo a mano.

## Decisiones para el usuario
1. ¿`secretData` debe ser exactamente `{"value": "$(env:SYNTH_<USUARIO>_TOTP_SEED)"}`, sin ninguna clave extra, igual que `credentialData` con E4? Si es así, la regla y las pruebas necesitan un caso más, como un CA nuevo o una tarea aparte. Si no, el comportamiento actual ya es correcto.

## Tareas candidatas (defectos reales fuera de alcance)
- U02-T04: el `credentialData` de `realm.{kind,staging}.yaml` (worktree `wt-U02-T04`, líneas 435, 449 y siguientes) no lleva `"secretEncoding":"BASE32"`. Con este lint dará `mfa-obligatorio` hasta que se alinee con domain-entities §3. Ya lo anoté en la ronda 2.
- Decidir si `make check` debe incluir `ruff format --check` y formatear los archivos existentes de `identity-edge`.

## Rutas de transcripciones largas
- Script de mutación, lint original y log de `make check`: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t05-r3/` (`mut.py`, `orig.py`, `check.log`). El venv y las copias ya están borrados.

AMARILLO|identity-edge/tools/realm_lint.py:188|secretData admite claves extra (D9 sobrevive); queda a decisión del usuario
AMARILLO|identity-edge/tests/unit/test_realm_lint.py|ruff format --check falla desde la base; make check no lo corre
INFORME: revisiones/U02-T05/ronda-3.md
VEREDICTO: VERDE
