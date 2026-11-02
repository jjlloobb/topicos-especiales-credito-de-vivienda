# Ronda 3 — U02-T03

VEREDICTO: NO-VERDE

Los cuatro criterios pasan con mi propia ejecución. Corrí 42 mutaciones y las pruebas detectan todas. F-01 a F-04 de la ronda 2 están corregidos. Queda un NARANJA: la exención de `realm-admin` sin MFA vale para **cualquier** cuenta de servicio, y el diseño reserva ese rol para `keycloak-config-cli`. Para cerrarlo hace falta un dato que el diseño no da (el `clientId` del cliente de administración), así que va al usuario.

Sha `eb28e6a` sobre `ade2b51`. Al final de la revisión el worktree sigue limpio (`git status` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`, `UV_OFFLINE=1`) | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 3 | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_*.py identity-edge/tests/unit/test_realm_lint.py -q` | pasa, 113 passed en 5,14 s. Las 8 propiedades corren 500 ejemplos cada una |
| 2 | Cada regla del Paso 2 con su caso que falla y su caso que pasa | `uv run pytest … -k "operacion or break_glass or verification_reader or product_metrics or channel_simulator or case_service"` | pasa, 20 passed |
| 3 | CLI como subproceso | `uv run pytest … -k cli` | pasa, 7 passed. Son solo las 7 pruebas de CLI |
| 4 | El esqueleto sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` | pasa, exit 0 (115 passed). `mypy --strict` no da errores |

**Mutaciones.** Las corrí en la copia `rev-u02t03-r3` y al terminar el `diff` contra HEAD sale vacío. Son 42 y todas las detecta alguna prueba:
- las 29 de la ronda 1 adaptadas, más M08b;
- N01 a N10;
- N11 (cuenta de servicio sin comprobar que el cliente exista);
- N04b (`optionalClientScopes` no exigido);
- N12 (cuenta de servicio sin comprobar roles de usuario);
- N13 (sin exigir `serviceAccountsEnabled`).

M23 y M25 ya no aplican porque esas reglas se quitaron.

**Sondas de las rondas 1 y 2: todas dan el resultado esperado.**
- `offline_access`, `microprofile-jwt`, `phone` y `address`: dan `scope-fuera-del-catalogo`.
- `verification-reader` con `offline_access`: da `scope-fuera-del-catalogo` y `scopes-exactos`.
- `permanentLockout=False`: da `parametro-del-realm`.
- `break-glass` con `realm-admin` como rol de cliente y sin TOTP: da `mfa-obligatorio`.
- `service-account-x` (solo el prefijo) con `cro` en prod: da `usuario-local-en-prod` y `mfa-obligatorio`.
- `serviceAccountClientId` de un cliente inexistente: da lo mismo.
- Un cliente sin `defaultClientScopes` o sin `optionalClientScopes`: da `scopes-por-defecto-heredados`.

## La decisión del codificador, contra el diseño
- **¿El diseño permite `realm-admin` en una cuenta de servicio?** Solo en la de `keycloak-config-cli`.
  - domain-entities.md:20: «`realm-admin` (solo la cuenta *break-glass* y el `keycloak-config-cli`)».
  - infrastructure-design.md:54 (INF-U2-05a): `keycloak-config-cli`, `realm-drift` y `signing-key-age` usan un cliente de administración con `private_key_jwt`; «`realm-drift` y `signing-key-age` solo leen; solo `keycloak-config-cli` escribe».
  - Ningún documento fija el `clientId` de ese cliente, y no está en la tabla de §2.2 (domain-entities.md:64-77).
  - Que la cuenta de servicio vaya sin TOTP sí está respaldado: domain-entities.md:81 dice que los clientes de servicio no tienen roles de usuario ni `acr = mfa`.
- **¿Abre un hueco en prod?** Sí. `_is_service_account` (realm_lint.py:123-130) acepta cualquier cliente con `serviceAccountsEnabled` y solo excluye los roles de negocio y `operacion`. Mis sondas sobre `realm.prod.yaml`, todas dan `[]`:
  - `service-account-case-worker` con `clientRoles: {realm-management: [realm-admin]}` y sin TOTP;
  - `service-account-scoring-service` con `realmRoles: [realm-admin]` y sin TOTP;
  - `service-account-case-worker` con `manage-users` y `manage-realm`.

  Además, la prueba `test_config_applier_service_account_with_realm_admin_needs_no_totp_in_prod` (test_realm_lint.py:270-280) da por **válido** justo ese caso: `case-worker`, un cliente de negocio, con `realm-admin`. La prueba fija el hueco como comportamiento esperado.

## Hallazgos
### F-01 · NARANJA · identity-edge/tools/realm_lint.py:123-130 y tests/unit/test_realm_lint.py:270 · `realm-admin` aceptado en cualquier cuenta de servicio de prod
El diseño limita `realm-admin` a `break-glass` y a `keycloak-config-cli` (domain-entities.md:20, infrastructure-design.md:54). El lint lo acepta, sin MFA, en la cuenta de servicio de cualquier cliente de servicio. Un PR que le dé `realm-admin` a `case-worker` en `realm.prod.yaml` pasaría el lint, y una prueba lo da por válido.

No hay arreglo posible sin un dato nuevo: restringir la exención al cliente de `keycloak-config-cli` exige su `clientId`, y el diseño no lo fija. Inventarlo iría contra la regla del usuario.

Decisión que corresponde al usuario, una de dos:
- (a) fijar el `clientId` del cliente de administración de INF-U2-05a, y que el lint admita `realm-admin` (o los roles de `realm-management`) solo en esa cuenta;
- (b) decidir que ese cliente no vive en `realm.{env}.yaml` (por ejemplo, en el realm `master`), y que el lint rechace cualquier rol de `realm-management` en una cuenta de servicio del realm `vectra`.

## Tareas candidatas (defectos reales fuera de alcance)
- Diseño: nombrar el cliente de administración de INF-U2-05a y decidir si sus roles se versionan en `realm.{env}.yaml`, y si `realm-drift` y `signing-key-age`, que solo leen, comparten cliente con `keycloak-config-cli`, que escribe.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r3/mutaciones.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r3/probe/probe.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/ca4-r3.log`

NARANJA|identity-edge/tools/realm_lint.py:123|realm-admin aceptado sin MFA en la cuenta de servicio de cualquier cliente de prod; el diseño lo reserva para keycloak-config-cli, cuyo clientId no está fijado (decisión del usuario)
INFORME: revisiones/U02-T03/ronda-3.md
VEREDICTO: NO-VERDE
