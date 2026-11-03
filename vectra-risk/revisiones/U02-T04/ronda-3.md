# Ronda 3 — U02-T04

VEREDICTO: NO-VERDE

Los hallazgos F-01 a F-06 de la ronda 2 quedan resueltos y verificados con mutaciones. Quedan en pie dos NARANJA nuevos. Los dos estaban en los realms desde la ronda 1 y yo no los marqué en las rondas 1 ni 2: es una falla mía de barrido, no del codificador.

Comprobaciones previas:
- **Hash de la tarea:** `53b68973…9eba7`, coincide.
- **Worktree:** `wt-U02-T04` en `73f41e0`, con `git status --porcelain` vacío al empezar y al terminar.
- **Commits revisados:** `e03a656` y `73f41e0`. El codificador solo tocó los 3 YAML, `test_realm_files.py`, `design_values.py`, la bitácora y la respuesta, así que no hay desborde.
- **Entorno:** trabajé sobre una copia (`git archive 73f41e0`) con su propio venv y `UV_OFFLINE=1`. Al terminar borré la copia y el venv, y no queda ningún proceso.
- **Diseño de referencia:** juzgo contra el diseño enmendado en `1f49c2f` (D-A, D-B, D-C y BR-U2-16) y `32cbe2a` (claves de `amr` y D-D).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | realm-lint de los 3 realms | `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml` | pasa (rc=0) |
| 2 | Lectura de vuelta contra el diseño | `uv run pytest identity-edge/tests/unit -q -k realm_files` | pasa (84 passed, 4,7 s), pero ver F-01 y F-02 |
| 3 | Sin secretos en claro | `uv run pytest identity-edge/tests/unit -q -k realm_has_no_secret_values` | pasa (15 passed) |
| 4 | Lo anterior sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` (con pipefail) | pasa (rc=0, «All checks passed!», 613 passed) |

**Mutaciones.** Corrí 78: las 56 de la ronda 2 y 22 nuevas. Una ida y vuelta YAML sin cambios da 84 passed. Todas se restauraron. Transcripción en `scratchpad/rev-u02t04-r3-scripts/mut.out`.
- **Las 55 mutaciones previas que debían fallar, fallan**, incluidas las cinco que sobrevivían en la ronda 2:
  - `loa-max-age` en 0 y en 900;
  - el mapper `amr` con `access.token.claim: 'false'`;
  - una audiencia en `governance:promotion`;
  - `hashedSaltedValue` y `client.secret` literales;
  - en el diseño, «`operacion` opcional».
- **`"counter":0` ahora pasa** (84 passed, lint rc=0), como admite E4.
- **Las nuevas fallan como deben:**
  - `amr`: un valor cambiado de `otp` a `totp`, `maxAge` en 0, WebAuthn sin config, la contraseña sin config, y el OTP de `analista` apuntando a `amr-hwk`;
  - `loa-max-age` de 900 en `loa-pwd`;
  - simetría: `analista` obligatorio, y su subflujo con un rol inexistente;
  - detector: `secretData` como mapa literal, `bindCredential` literal, `keystorePassword` literal y `secret` en un client scope;
  - en el diseño: §1.2 con `amr` `totp`, §6 con `default.reference.maxAge` de 900, §6 con `loa-max-age` de 900, y §2.2 con `case:` apuntando a `governance-service`.
- **Sobrevive, y es correcto:** el mapper `amr` sin `id.token.claim`. §1.2 solo exige el claim en el access token.
- **Sobreviven, y son la evidencia de F-01 y F-02:** `token.endpoint.auth.signing.alg` en ES256, WebAuthn en RS256, `loginWithEmailAllowed: true`, `sslRequired: external` y `resetPasswordAllowed: true` (84 passed cada una).

## Estado de los hallazgos de la ronda 2
- **F-01 (`amr`):** resuelto. Las configuraciones `amr-pwd`, `amr-otp` y `amr-hwk` llevan `default.reference.value` y `default.reference.maxAge` = '36000' (realm.prod.yaml:629-640), están asignadas a cada ejecución y se leen de §1.2 y §6. El mapper emite en el access token.
- **F-02 (`loa-max-age`):** resuelto. La prueba compara cada condición de nivel con §6.
- **F-03 (simetría y scopes de usuario):** resuelto.
- **F-04 (`counter` y literales):** resuelto. `DOMAIN_AUDIENCE` se reemplazó por la lectura de la tabla de §2.2.
- **F-05 (detector):** resuelto.
- **F-06 (BR-U2-16):** resuelto por el orquestador en `1f49c2f`.

## Hallazgos
### F-01 · NARANJA · realm.{kind,staging,prod}.yaml, `token.endpoint.auth.signing.alg: RS256` (por ejemplo realm.prod.yaml:878; 15, 15 y 13 apariciones) · Los realms rechazan la firma ES256 que usan los servicios
BR-U2-09 (business-rules.md:59) admite «`private_key_jwt` con RS256 o ES256». Los realms fijan solo RS256 en los 13 clientes `client-jwt` de cada entorno.

El cliente de U0 que pide los tokens de servicio firma la aserción con `algorithm: str = "ES256"` (contracts/python/vectra_common/src/vectra_common/service_token.py:34), y `provider_from_env` no pasa otro valor. Con este realm, Keycloak rechazaría la aserción de todos los servicios, salvo que despliegue con otra configuración.

El valor RS256 no tiene respaldo en el diseño, y la prueba no lo cubre: la mutación a ES256 sobrevive. Va a D-E.

### F-02 · NARANJA · realm.*.yaml:6, :8, :11, :12, :14, :37-39 · Valores visibles para el usuario sin respaldo en el diseño
El barrido de esta ronda encontró estos valores, que ningún documento de U2 define (grep sin resultados):
- `webAuthnPolicySignatureAlgorithms: [ES256]`: deja fuera a los autenticadores que solo firman RS256. El diseño solo dice «WebAuthn opcional» (BR-U2-03:24, plan :73).
- `webAuthnPolicyRpEntityName: Vectra` y `displayName: Vectra`: se muestran al usuario.
- `loginWithEmailAllowed: false`: el usuario no puede entrar con su email.
- `sslRequired: all`, `resetPasswordAllowed: false` y `rememberMe: false`.

Por el invariante 8 y la regla del usuario, son NARANJA y van a D-F. Ninguna prueba los fija: las mutaciones sobreviven.

## Supuestos del codificador
La bitácora dice «Supuestos (ronda 3): ninguno nuevo», y los de la ronda 2 quedan respaldados:
- la audiencia por scope, en la tabla de §2.2;
- `loa-max-age`, en §6;
- los valores de `amr`, en §1.2;
- `default.reference.maxAge`, en §6 (D-D).

`default.acr.values: mfa` sigue derivándose de BR-U2-03 (business-rules.md:25-26), como dije en la ronda 2. Los valores sin respaldo que quedan son los de F-01 y F-02: no los declaró como supuestos porque vienen de la ronda 1.

## Decisiones para el usuario
- **D-E · Algoritmo de las aserciones `private_key_jwt` (F-01).**
  - (a) Fijar ES256 en todos los clientes `client-jwt`, igual que el cliente de U0, y escribirlo en BR-U2-09.
  - (b) No fijar el atributo, de modo que Keycloak acepte RS256 y ES256 como dice BR-U2-09.
  - (c) Mantener RS256 y cambiar el valor por defecto de `service_token.py` en U0, en otra tarea.
- **D-F · Ajustes del realm sin respaldo (F-02).**
  - (a) Aceptarlos como están y agregarlos al diseño (§1 de domain-entities), con prueba que los lea de ahí.
  - (b) Dejar los valores por defecto de Keycloak, quitándolos del YAML.
  - (c) Decidir uno por uno, en particular:
    - WebAuthn: solo ES256, o ES256 y RS256;
    - `loginWithEmailAllowed`;
    - `resetPasswordAllowed`, que en prod no aplica a usuarios LDAP.

## Tareas candidatas (defectos reales fuera de alcance)
- La prueba de extremo a extremo en kind que lea el token real, con la misma lista de las rondas 1 y 2. Debería incluir además un `client_credentials` firmado con ES256 desde `vectra_common.service_token`.
- `realm_lint.py` sigue con `REALM_PARAMETERS` y `MFA_REQUIRED_ROLES` escritos a mano (U02-T03).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r3-scripts/mut.out` (mutaciones)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r3-scripts/ca4.out` (CA-4)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r3-scripts/mut.py` (script)

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/keycloak/realm/realm.prod.yaml:878|signing.alg RS256 sin respaldo; U0 firma las aserciones con ES256 (service_token.py:34) (D-E)
NARANJA|identity-edge/keycloak/realm/realm.kind.yaml:12|Valores visibles sin respaldo: WebAuthn ES256, rpEntityName, displayName, loginWithEmail, sslRequired, resetPassword, rememberMe (D-F)
INFORME: revisiones/U02-T04/ronda-3.md
```
