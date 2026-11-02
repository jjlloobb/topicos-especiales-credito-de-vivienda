# Ronda 2 — U02-T05

VEREDICTO: NO-VERDE

Contexto comprobado: el hash de la tarea es `b88dc3e7f37514d07893b668da55fca514b6bbc4` y coincide. El worktree está en `48ba8e1` y queda limpio (`git status --porcelain` da 0 líneas). Los commits desde `c1e6c98` son tres: `de330cf` (informe de la ronda 1), `a5c6494` (enmienda de diseño y tarea del orquestador) y `48ba8e1` (codificador). El diff del código contra la base `2dbe403` toca solo `identity-edge/tools/realm_lint.py` y `tests/unit/test_realm_lint.py`. No cambia nada en `contracts/`, `platform/` ni `.github/`.

Ejecuté todo sobre `git archive 48ba8e1` en la scratchpad `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t05-r2/`, con venv propio y `UV_OFFLINE=1`. El volumen de `/tmp` llegó a su cuota a mitad de la revisión. Para seguir borré solo mis copias de la ronda 1 (`rev-u02t05-r1/`) y, al terminar, el venv de esta ronda. No toqué los directorios de otras revisiones. La scratchpad sigue ocupando unos 5.5 GB por revisiones anteriores.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Pasa con `CONFIGURE_TOTP` o con `otp` referenciada; falla sin ninguna, con literal y con otro tipo; en kind, staging y prod | `uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k otp_credential` | pasa: 261 passed, 170 deselected, 0.34 s (prueba unitaria pura) |
| 2 | Lo anterior sigue cumpliendo | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests -q && uv sync --frozen && make -C identity-edge check` | pasa: 442 passed, sync ok, «All checks passed!», 442 passed, EXIT=0. `mypy --strict` del lint: sin errores |
| 3 | Forma única de domain-entities §3 | `uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k otp_credential_form` | pasa: 78 passed |
| — | Rojo primero | pruebas de `48ba8e1` contra el `realm_lint.py` de `c1e6c98` | 42 failed, 219 passed. Coincide con la bitácora |
| — | Solo cambió la regla de MFA | hunks de `git diff 2dbe403..48ba8e1 -- realm_lint.py` | sí: import, constantes, `otp_seed_reference`, `_json_object`, `_has_referenced_otp` y el bloque `mfa-obligatorio` con su mensaje. Ninguna otra regla cambia |

Los hallazgos de la ronda 1 quedan cerrados: F-01 por la decisión del usuario y CA-3, F-02 porque M10 y M12 mueren ahora, F-03 por el nombre `SYNTH_` y F-04 porque el rojo coincide.

## Mutaciones (24): lint restaurado y comprobado con `cmp`
| Mutación | Resultado |
|---|---|
| M1 prefijo (`startswith`) | 24 failed |
| M2 referencia parcial (`in`) | 36 failed |
| M3 cualquier literal | 105 failed |
| M4 cualquier tipo de credencial | 48 failed |
| M5 tipo sin distinguir mayúsculas | 12 failed |
| M6 `secretData` como mapa | 6 failed |
| M7 cualquier `$(env:…)` | 42 failed |
| M8 quitar la credencial referenciada | 24 failed |
| M9 aceptar `${…}` | 12 failed |
| M10 `value` de primer nivel | 3 failed |
| M11 quitar la acción `CONFIGURE_TOTP` | 67 failed |
| M12 solo la primera credencial | 3 failed |
| M13 cualquier `SYNTH_*_TOTP_SEED` | 6 failed |
| N1 la variable de otro usuario | 6 failed |
| N2 conservar el `-` | 27 failed |
| N3 borrar el `-` en vez de cambiarlo por `_` | 24 failed |
| N4 sin mayúsculas | 24 failed |
| N7 ignorar `secretEncoding` | 27 failed |
| N8 codificación sin distinguir mayúsculas | 3 failed |
| N9 leer `secretEncoding` solo de `secretData` | 24 failed |
| **N5** aceptar `secretEncoding` dentro de `secretData` | **442 passed, sobrevive** |
| **N6** aceptar `secretEncoding` en el primer nivel de la credencial | **442 passed, sobrevive** |
| **N10** aceptar la semilla dentro de `credentialData` | **442 passed, sobrevive** |
| **N11** aceptar un usuario sin `username` | **442 passed, sobrevive** |

## Hallazgos
### F-01 · NARANJA · identity-edge/tests/unit/test_realm_lint.py:177-198 (BAD_FORMS) · Las pruebas no fijan los campos en sitio equivocado
domain-entities §3 enmendado dice que `secretEncoding` va en `credentialData` y la semilla en `secretData`, y que «cualquier otra forma … es inválida». El lint hoy hace lo correcto, porque lee cada dato de su campo. Pero ninguna prueba lo fija, y tres mutantes sobreviven con 442 passed:
- N5: `secretEncoding` dentro de `secretData`.
- N6: `secretEncoding` en el primer nivel de la credencial.
- N10: la semilla dentro de `credentialData`.

El caso «`secretEncoding` en otro campo» era uno de los pedidos expresamente para esta ronda. Faltan las formas inválidas correspondientes en `BAD_FORMS`: `credentialData` sin `secretEncoding` y con él en `secretData` o en el primer nivel, y `secretData` sin `value` con la semilla en `credentialData`. Es cobertura ausente de un requisito del diseño.

### F-02 · AMARILLO · identity-edge/tools/realm_lint.py:161-163 · Usuario sin `username`
N11 sobrevive: si `_has_referenced_otp` devuelve `True` para un usuario sin `username`, ninguna prueba falla. Hoy el código devuelve `False`, que es lo correcto, pero no está fijado.

### F-03 · AMARILLO · identity-edge/tools/realm_lint.py:166-170 · El resto de `credentialData` no se valida
domain-entities §3 escribe la forma única con `credentialData` completo: `{"subType":"totp","digits":6,"period":30,"algorithm":"HmacSHA1","secretEncoding":"BASE32"}`. El lint solo comprueba `secretEncoding`, así que acepta `digits: 8` o `algorithm: HmacSHA256`. CA-3 solo enumera `secretEncoding`, y la lista entre paréntesis del diseño no nombra esos campos. Por eso no lo cuento como incumplimiento, sino como ambigüedad del diseño (pregunta 1).

## Decisiones para el usuario
1. En la forma única, ¿`credentialData` debe tener además exactamente `subType: totp`, `digits: 6`, `period: 30` y `algorithm: HmacSHA1`, y `realm-lint` debe rechazar otros valores? ¿O solo es obligatorio `secretEncoding: BASE32` y el resto es un ejemplo? Si son obligatorios, ¿se admiten claves extra como el `"counter":0` que hoy escribe U02-T04?

## Tareas candidatas (defectos reales fuera de alcance)
- U02-T04: su `realm.{kind,staging}.yaml` (worktree `wt-U02-T04`, líneas 435, 449 y siguientes) tiene `credentialData` sin `"secretEncoding":"BASE32"`. Con este lint dará `mfa-obligatorio` en todos los sintéticos con MFA. Hay que alinearlo con domain-entities §3 al retomar U02-T04.

## Rutas de transcripciones largas
- Script de mutación y log de `make check`: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t05-r2/` (`mut.py`, `check.log`). El venv se borró por la cuota de disco.

VEREDICTO: NO-VERDE
NARANJA|identity-edge/tests/unit/test_realm_lint.py:177|Sobreviven N5, N6 y N10: ninguna prueba fija secretEncoding o la semilla en otro campo
AMARILLO|identity-edge/tools/realm_lint.py:161|Sobrevive N11: usuario sin username aceptado sin que falle ninguna prueba
AMARILLO|identity-edge/tools/realm_lint.py:166|credentialData: solo se valida secretEncoding; digits, period y algorithm quedan a decisión del usuario
INFORME: revisiones/U02-T05/ronda-2.md
