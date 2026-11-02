# Ronda 2 — U02-T03

VEREDICTO: NO-VERDE

Los cuatro criterios pasan con mi propia ejecución, y lo que el diseño enmendado (`c8031c7`) decidió sobre F-01, F-02 y F-03 está bien aplicado. Quedan dos defectos NARANJA en el arreglo de F-04: la exención de cuentas de servicio deja pasar en producción un usuario local con rol de negocio y sin TOTP, y sigue abierto el hueco de los scopes opcionales que hereda un cliente.

Sha `e5ca5ce` sobre `ce5ab30`. Al final de la revisión el worktree sigue limpio (`git status` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`, `UV_OFFLINE=1`) | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 3 | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_*.py identity-edge/tests/unit/test_realm_lint.py -q` | pasa, 105 passed en 5,08 s. Las 8 propiedades corren 500 ejemplos cada una |
| 2 | Cada regla del Paso 2 con su caso que falla y su caso que pasa | `uv run pytest … -k "operacion or break_glass or verification_reader or product_metrics or channel_simulator or case_service"` | pasa, 20 passed |
| 3 | CLI como subproceso | `uv run pytest … -k cli` | pasa, 7 passed. Son solo las 7 pruebas de CLI, con un caso válido que sale en 0 y uno inválido que sale distinto de 0 y nombra el archivo y la regla |
| 4 | El esqueleto sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` | pasa, exit 0 (ruff limpio, 107 passed). `mypy --strict realm_lint.py` no da errores |

**Mutaciones.** Las corrí en una copia (`rev-u02t03-r2`) y al terminar el `diff` contra HEAD sale vacío.
- Las 29 de la ronda 1, adaptadas: 28 siguen siendo detectadas. M25 (`acr.loa.map`) ya no aplica porque esa regla se quitó por F-03(c).
- Una nueva, M08b (sacar `channel-simulator` de la lista de clientes que no van a producción): la detecta `test_channel_simulator_in_prod_is_rejected`, así que el arreglo de F-06 funciona.
- Once nuevas, N01 a N11: 8 detectadas y 3 sobreviven (N03, N10, N11; ver F-01 y F-03).

**Sondas de la ronda 1, contra el código nuevo:**
- `offline_access`, `microprofile-jwt`, `phone` y `address` en un cliente de servicio: dan `scope-fuera-del-catalogo`.
- `verification-reader` con `offline_access` además de sus dos scopes: da `scope-fuera-del-catalogo` y `scopes-exactos`.
- `permanentLockout=False`: da `parametro-del-realm`.
- `break-glass` con `realm-admin` como rol de cliente de `realm-management` y sin TOTP: da `mfa-obligatorio`.
- Una cuenta de servicio real (`service-account-*` con `serviceAccountClientId`) en producción: `[]`, correcto.
- Un cliente sin `defaultClientScopes`: da `scopes-por-defecto-heredados`.

**Contra el diseño enmendado:**
- BR-U2-05: los campos coinciden con business-rules.md:42.
- BR-U2-15: el formato `groups: {<grupo>: <rol>}` está en business-rules.md:98. Los roles admitidos son los de negocio y `operacion`.
- PBT-U2-02 se prueba sobre la tabla (business-logic-model.md:70).
- PBT-U2-03 es estricta: el generador incluye los scopes propios de Keycloak y no los filtra (realm_strategies.py:50-53).
- `ROLE_CONFLICT` en ejecución está en CANDIDATAS.md.
- No queda ninguna regla sin respaldo: las de la ronda 1 que estaban respaldadas se quedan, y `secret` en todo cliente, `acr.loa.map` y las de rotación de refresh ya no están.

## Hallazgos
### F-01 · NARANJA · identity-edge/tools/realm_lint.py:132 · Un nombre que empiece por `service-account-` salta las reglas de usuario local en prod y de MFA
`service_account = name.startswith("service-account-") or "serviceAccountClientId" in user`. Mis sondas sobre `realm.prod.yaml`:
- un usuario `{"username": "service-account-x", "realmRoles": ["cro"], "requiredActions": []}` da `[]`;
- un usuario `{"username": "jdoe", "serviceAccountClientId": "no-existe", "realmRoles": ["cro"]}` da `[]`.

Esto deja sin efecto, con una entrada fácil de construir, la regla del plan: «`realm-lint` falla si `realm.prod.yaml` tiene algún usuario local distinto de `break-glass`» (plan:80, domain-entities.md:89). También deja sin efecto la MFA de BR-U2-03.

Las pruebas no cubren la exención:
- N11 sobrevive: dejar solo `serviceAccountClientId` no rompe ninguna prueba;
- N03 sobrevive: quitar la exención de MFA no rompe ninguna prueba.

Para que una cuenta de servicio sea legítima, su `serviceAccountClientId` debería apuntar a un cliente del realm con `serviceAccountsEnabled: true`. Además, domain-entities.md:81 dice que los clientes de servicio no tienen roles de usuario.

### F-02 · NARANJA · realm_lint.py:229 · `optionalClientScopes` ausente sigue heredando los scopes propios de Keycloak
El arreglo de F-04 exige `defaultClientScopes` explícito pero no `optionalClientScopes`. Sin ese campo, Keycloak asigna los scopes opcionales por defecto del realm (`offline_access`, `address`, `phone`, `microprofile-jwt`), justo los que PBT-U2-03 enmendada prohíbe (business-logic-model.md:71).

Mi sonda: borrar `optionalClientScopes` de `case-worker` da `[]`.

Es la misma clase de defecto que señalé en la ronda 1 (F-04, tercer punto). Debí barrerla entera entonces; la registro ahora.

### F-03 · AMARILLO · realm_lint.py:292 · La comparación por tipo no tiene prueba
N10 sobrevive: quitar `type(actual) is not type(expected)` no rompe nada. Falta un caso del tipo `permanentLockout: 1` o `failureFactor: true`.

### F-04 · AMARILLO · test_realm_lint.py · Una prueba que no prueba una regla
`test_realm_without_refresh_rotation_fields_is_not_checked_by_step_3` afirma la forma del realm de ejemplo, no una regla. `LEAKY_BUILTIN_SCOPES` quedó redundante, porque `profile` y `email` ya fallan por estar fuera del catálogo. No bloquea.

## Tareas candidatas (defectos reales fuera de alcance)
- El mecanismo de `ROLE_CONFLICT` en Keycloak (BR-U2-01): ya está en CANDIDATAS.md.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r2/mutaciones.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r2/probe/probe.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/ca4-r2.log`

VEREDICTO: NO-VERDE
NARANJA|identity-edge/tools/realm_lint.py:132|un nombre `service-account-*` o un `serviceAccountClientId` sin cliente evaden usuario-local-en-prod y MFA; exención sin prueba (N03, N11)
NARANJA|identity-edge/tools/realm_lint.py:229|sin `optionalClientScopes` el cliente hereda offline_access/microprofile-jwt y el lint no lo detecta
AMARILLO|identity-edge/tools/realm_lint.py:292|la comparación por tipo de los parámetros no tiene prueba (N10 sobrevive)
AMARILLO|identity-edge/tests/unit/test_realm_lint.py|prueba que afirma la forma del ejemplo; LEAKY_BUILTIN_SCOPES redundante
INFORME: revisiones/U02-T03/ronda-2.md
