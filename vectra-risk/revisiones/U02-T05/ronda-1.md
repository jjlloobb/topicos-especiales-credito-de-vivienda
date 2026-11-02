# Ronda 1 — U02-T05

VEREDICTO: NO-VERDE

Contexto comprobado: el hash de la tarea es `f08998b3fd99f54011b89ec5ca7777933e6a934e` y coincide. El worktree está en `c1e6c98`, rama `tarea/U02-T05`. Hay un solo commit sobre `2dbe403` y cambia 3 archivos: `realm_lint.py`, `test_realm_lint.py` y la bitácora. Todas las ejecuciones las hice sobre `git archive` de los dos sha, en la scratchpad `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t05-r1/`, con venv propio y `UV_OFFLINE=1`.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Pasa con `CONFIGURE_TOTP` o con `otp` referenciada; falla sin ninguna, con literal y con otro tipo; en kind, staging y prod | `uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k otp_credential` | pasa: 201 passed, 170 deselected, 0.25 s (prueba unitaria pura, sin estado externo) |
| 2 | Lo anterior sigue cumpliendo | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests -q && uv sync --frozen && make -C identity-edge check` | pasa: 382 passed, sync ok, ruff y pruebas ok, EXIT=0 |
| — | Rojo primero | pruebas nuevas contra el `realm_lint.py` de `2dbe403` | 12 failed: los 12 de `test_otp_credential_referenced_without_totp_action_is_accepted`, como se esperaba |
| — | Solo cambió la regla de MFA | `git diff 2dbe403..c1e6c98 -- identity-edge/tools/realm_lint.py` | sí: `import json`, dos constantes, `_has_referenced_otp` y el bloque `mfa-obligatorio` con su mensaje. Ninguna otra regla cambia. `mypy --strict`: sin errores |
| — | Worktree limpio | `git status --porcelain` | limpio, en `c1e6c98`. Solo quedan ignorados preexistentes (`platform/.charts`, `.tools`) |

## Juicio del supuesto: la forma de la credencial `otp`
- **El diseño no la fija.** domain-entities §3, en la fila enmendada, dice «credencial OTP con la semilla desde ESO» y que `realm-lint` «acepta `CONFIGURE_TOTP` o una credencial OTP referenciada». La tarea fija el tipo `otp` y la referencia exacta `$(env:NOMBRE)`. Ninguno de los dos documentos dice en qué campo va el secreto. El contrato de variables de INF-U2-01 enmendado (infrastructure-design §1) solo fija los nombres `SYNTH_<USUARIO>_*`, no la forma. Tampoco BR-U2-03 ni el plan dicen nada.
- **Sin red no puedo confirmar que coincida con lo que importa keycloak-config-cli.** No hay esquema, chart, CRD ni jar de Keycloak o de keycloak-config-cli en el repositorio, en `~/.cache` ni en `platform/.charts`. Lo que hay en `.charts` con `secretData` es de ESO y no viene al caso. De memoria, que no es evidencia: la `CredentialRepresentation` de Keycloak declara `secretData` y `credentialData` como String JSON, y `OTPSecretData` guarda la semilla en `value`. Eso coincide con el supuesto. Dos puntos quedan sin confirmar:
  - Si keycloak-config-cli aplica `credentials` a usuarios que ya existen.
  - Si Keycloak lee la semilla como texto crudo o como Base32 (campo `secretEncoding` de `credentialData`).
- **Coherencia interna:** el realm de U02-T04 (`wt-U02-T04`, sin fusionar) usa exactamente esa forma: `secretData: '{"value":"$(env:SYNTH_..._TOTP_SEED)"}'`. Este lint, corrido sobre `realm.{kind,staging,prod}.yaml` de U02-T04, no da ninguna violación `mfa-obligatorio`. Pero los dos lados nacen del mismo supuesto, así que eso no lo confirma.

## Hallazgos
### F-01 · NARANJA · identity-edge/tools/realm_lint.py:42-45, 141-154 · La forma de la credencial se asumió en vez de detenerse
La tarea dice «Si falta un dato, detente y repórtalo», y la regla del usuario es la misma. El codificador reconoce en «Supuestos» que «el diseño no define la forma de la credencial» y aun así implementó una. Tres partes son decisiones de diseño, no hechos del diseño:
- Que el secreto va en `secretData` como String JSON y la semilla en `value`.
- Que se rechaza `secretData` como mapa YAML.
- Que se rechaza el tipo heredado `totp`.

Lo señaló con transparencia y el código es correcto bajo el supuesto. Si el usuario ratifica la forma, basta enmendar domain-entities §3 y no hace falta tocar código. Hasta entonces no es «exactamente lo que define el diseño».

### F-02 · AMARILLO · identity-edge/tests/unit/test_realm_lint.py:100-160 · Dos mutantes sobreviven
- M10: tomar la semilla del `value` de primer nivel de la credencial da 382 passed. Ninguna prueba fija que `{type: otp, value: "$(env:X)"}` se rechace. Keycloak usaría ese `value` como contraseña, así que conviene fijarlo.
- M12: mirar solo la primera credencial `otp` da 382 passed. No hay caso con varias credenciales, ni con la forma real `[password, otp]` de U02-T04.

Las otras 11 mutaciones mueren:

| Mutación | Fallos |
|---|---|
| `match` | 24 |
| `search` (referencia parcial) | 36 |
| aceptar literales | 84 |
| cualquier tipo de credencial | 48 |
| tipo sin distinguir mayúsculas | 12 |
| `secretData` como mapa | 3 |
| nombre de variable vacío | 24 |
| quitar la credencial referenciada | 12 |
| aceptar `${X}` | 12 |
| quitar la acción `CONFIGURE_TOTP` | 55 |
| `\w+` como nombre | 382 passed, mutante equivalente a efectos del diseño |

### F-03 · AMARILLO · identity-edge/tests/unit/test_realm_lint.py:117 · Nombre de variable fuera del contrato
Las pruebas usan `$(env:CRO_1_TOTP_SEED)`. El contrato de INF-U2-01 enmendado es `SYNTH_<USUARIO>_*`. El lint acepta cualquier `NOMBRE`, y la tarea no pide restringir el prefijo. Ver la pregunta 3.

### F-04 · AMARILLO · bitacoras/U02-T05.md:12 · El rojo registrado es de otra versión de las pruebas
La bitácora registra «12 failed, 138 passed, 221 deselected». Con las pruebas actuales contra la base sale 12 failed, 189 passed, 170 deselected. Los 12 fallos son los mismos y el total de 371 coincide, así que es evidencia de un conjunto anterior de pruebas, no falsa. Lo reproduje yo.

## Decisiones para el usuario
1. **Forma de la credencial OTP en el realm.** ¿Se fija en domain-entities §3 como `credentials: [{type: otp, secretData: '{"value":"$(env:SYNTH_<USUARIO>_TOTP_SEED)"}', credentialData: '{"subType":"totp","digits":6,"period":30,"algorithm":"HmacSHA1",...}'}]`, con `secretData` como String JSON y la semilla en `value`? ¿Y `realm-lint` rechaza cualquier otra forma: `secretData` como mapa YAML, un `value` de primer nivel o el tipo heredado `totp`?
2. **Codificación de la semilla.** ¿La semilla que entrega ESO está en Base32 (la que usa `pyotp` en system-verification)? Si es así, ¿`credentialData` debe llevar `"secretEncoding":"BASE32"` y debe exigirlo el lint? Sin red no puedo verificar cómo lo interpreta la versión de Keycloak del proyecto.
3. **Nombre de la variable.** ¿El lint exige que la referencia sea `$(env:SYNTH_<USUARIO>_TOTP_SEED)` (contrato de INF-U2-01), o le basta cualquier `$(env:NOMBRE)` como dice hoy la tarea?

## Tareas candidatas (defectos reales fuera de alcance)
- U02-T04 y el Paso 5: confirmar que keycloak-config-cli aplica `credentials` (contraseña y OTP) a usuarios que ya existen y no solo al crearlos. Si no, rotar la semilla en ESO no llega al realm.

## Rutas de transcripciones largas
- Copias, venv y script de mutación: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t05-r1/` (`src/`, `base/`, `red/`, `mut.py`, `t04/`)

VEREDICTO: NO-VERDE
NARANJA|identity-edge/tools/realm_lint.py:141|La forma de la credencial otp (secretData String JSON con value) se asumió; el diseño no la fija
AMARILLO|identity-edge/tests/unit/test_realm_lint.py:100|Sobreviven los mutantes value de primer nivel y solo la primera credencial otp
AMARILLO|identity-edge/tests/unit/test_realm_lint.py:117|El nombre de variable de las pruebas no sigue el contrato SYNTH_<USUARIO>_*
AMARILLO|bitacoras/U02-T05.md:12|El rojo registrado es de una versión anterior de las pruebas
INFORME: revisiones/U02-T05/ronda-1.md
