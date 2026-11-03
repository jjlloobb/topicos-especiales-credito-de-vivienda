# Ronda 4 — U02-T04

VEREDICTO: NO-VERDE

Los dos NARANJA de la ronda 3 quedan resueltos. Siguen en pie dos NARANJA:
- **F-01:** ES256 en el cliente `grafana`, que el diseño no respalda. Es una decisión del usuario.
- **F-02:** valores derivables del diseño, y con efecto, que ninguna prueba lee de vuelta.

Los cuatro criterios pasan. Por la regla de las 4 rondas, la tarea vuelve al usuario con la consulta D-G.

Comprobaciones previas:
- **Hash de la tarea:** `53b68973…9eba7`, coincide.
- **Worktree:** `wt-U02-T04` en `508fa34`, con `git status --porcelain` vacío al empezar y al terminar.
- **Código revisado:** el commit `508fa34`. Solo toca los 3 YAML, `test_realm_files.py`, `design_values.py`, la bitácora y la respuesta, así que no hay desborde.
- **Entorno:** trabajé sobre una copia (`git archive 508fa34`) con su propio venv y `UV_OFFLINE=1`. Al terminar borré la copia y el venv, y no queda ningún proceso.
- **Diseño de referencia:** juzgo contra el diseño enmendado en `8cf36e1` (BR-U2-09 con ES256 y domain-entities §1.0).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | realm-lint de los 3 realms | `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml` | pasa (rc=0) |
| 2 | Lectura de vuelta contra el diseño | `uv run pytest identity-edge/tests/unit -q -k realm_files` | pasa (90 passed, 4,4 s), pero ver F-02 |
| 3 | Sin secretos en claro | `uv run pytest identity-edge/tests/unit -q -k realm_has_no_secret_values` | pasa (15 passed) |
| 4 | Lo anterior sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` (con pipefail) | pasa (rc=0, «All checks passed!», 619 passed) |

**Mutaciones.** Corrí 100: las 78 de la ronda 3 y 22 nuevas. La ida y vuelta YAML sin cambios da 90 passed. Todas se restauraron. Transcripción en `scratchpad/rev-u02t04-r4-scripts/mut.out`.
- **Las mutaciones previas que debían fallar, siguen fallando.** Las que la ronda 3 marcó «sin respaldo» ahora fallan, porque §1.0 las respalda: WebAuthn, `loginWithEmailAllowed`, `sslRequired` y `resetPasswordAllowed`.
- **Pasan, como debe ser:** `"counter":0` (lo admite E4) y el mapper `amr` sin `id.token.claim` (§1.2 solo exige el access token).
- **ES256 (BR-U2-09), todas fallan:**
  - `case-service` en RS256;
  - `grafana` en RS256;
  - `keycloak-config-cli` sin el atributo;
  - `channel-simulator` en PS256;
  - en el diseño, BR-U2-09 con RS256 (3 failed).
- **§1.0, todas fallan:**
  - WebAuthn solo con ES256;
  - WebAuthn con el orden invertido;
  - `rememberMe`, `displayName` y `webAuthnPolicyRpEntityName` cambiados;
  - un booleano escrito como texto;
  - en el diseño, `sslRequired` external, WebAuthn solo con ES256, y una fila nueva en la tabla (3 failed cada una).
- **Barrido:** mata `defaultDefaultClientScopes` con `profile`. Sobreviven 7 mutaciones (90 passed cada una), que son la evidencia de F-02:
  - `fullScopeAllowed: true` en `vectra-console`;
  - `operacion` agregado a los `scopeMappings` de `vectra-console`;
  - `analista` quitado de los `scopeMappings` de `grafana`;
  - `cro` agregado a los `scopeMappings` de `promotion-tool`;
  - `include.in.token.scope: 'false'`;
  - `temporary: true` en la contraseña de `break-glass`;
  - `use.refresh.tokens: 'false'`.

## Estado de los hallazgos de la ronda 3
- **F-01 (algoritmo de las aserciones):** resuelto. `token.endpoint.auth.signing.alg: ES256` en los 13 clientes `client-jwt` de cada realm, leído de BR-U2-09 (business-rules.md:59).
- **F-02 (ajustes del realm):** resuelto. Los 7 ajustes de §1.0 (domain-entities.md:10-19) se leen y se comparan exactos.

## Clasificación del barrido del codificador
(a) = definido o derivable del diseño; (b) = sin efecto, o con el valor por defecto de Keycloak; (c) = sin respaldo y con efecto, es decir, una decisión del usuario.

| # | Valor | Clase | Evidencia |
|---|---|---|---|
| 1a | `fullScopeAllowed: false` | (a) | domain-entities.md:52: `roles` es un «arreglo plano con **el** rol de negocio». Con `true`, el claim llevaría también `default-roles-vectra`, `offline_access` y `uma_authorization`. |
| 1b | `scopeMappings` de `vectra-console`: los 4 roles de negocio, sin `operacion` | (a) | domain-entities.md:20-23: `operacion` no es rol de negocio y solo sirve en Grafana. :52: el claim `roles` lleva el rol de negocio. |
| 1c | `scopeMappings` de `promotion-tool`: solo `ingeniero_riesgo` | (a) | domain-entities.md:67 (scope asignable solo a `ingeniero_riesgo`) y :123 (F08 exige ese rol). |
| 1d | `scopeMappings` de `grafana` con `analista` | (b) | El realm solo entrega `roles` (domain-entities.md:68, D8). Que `analista` quede sin acceso lo decide la configuración `generic_oauth` de U1, esté o no el rol en el claim. |
| 2 | `default.acr.values: mfa` | (a) | BR-U2-03 (business-rules.md:25-26) y §1.2 (domain-entities.md:43): con LoA, el nivel 2 solo corre si se pide. |
| 3 | `use.refresh.tokens: 'true'` | (a) y (b) | Es el valor por defecto de Keycloak, y BR-U2-06 (business-rules.md:51) exige refresh con rotación. |
| 4 | Subflujos de LoA (niveles 1 y 2) y sus prioridades | (a) para los niveles, (b) para las prioridades | Niveles: domain-entities.md:45 y BR-U2-03. Las prioridades solo ordenan las ejecuciones, como pide la mecánica de LoA de Keycloak. |
| 5 | `temporary: false` en las contraseñas, también la de `break-glass` | (b) | Es el valor por defecto de `CredentialRepresentation`. La rotación de `break-glass` tras cada uso (NFR-U2-24, nfr-requirements.md:37) es operativa, no del realm. |
| 6a | `include.in.token.scope: 'true'` | (a) y (b) | Es el valor por defecto, y los servicios verifican el scope en el token (contracts business-rules.md:207, BR-U0-71). |
| 6b | `display.on.consent.screen: 'false'` | (b) | Ningún cliente pide consentimiento: no tiene efecto. |
| 7 | Nombres de las acciones requeridas y prioridades 10 y 20 | (b) | Son los nombres incorporados de Keycloak. La prioridad solo ordena dos acciones pendientes. Que estén habilitadas sí está definido (BR-U2-03:22-24). |
| 8a | ES256 en `keycloak-config-cli` y `keycloak-reader` | (a) | INF-U2-05a (infrastructure-design.md:54-57) los define como cuentas de servicio con `private_key_jwt`, y BR-U2-09:59 fija ES256 para «cada cliente de servicio». |
| 8b | **ES256 en `grafana`** | **(c)** | `grafana` es un cliente de **usuario** (domain-entities.md:68), y BR-U2-09 solo habla de clientes de servicio. El codificador lo declara como lectura suya. → F-01 y D-G |

También estoy de acuerdo con su grupo 1 (registro, emails, flujos implícitos y `directAccessGrants`): es (b).

## Hallazgos
### F-01 · NARANJA · realm.*.yaml, cliente `grafana`, `token.endpoint.auth.signing.alg: ES256` (realm.prod.yaml:879) · Algoritmo del cliente de usuario `grafana` sin respaldo
El valor tiene efecto: Grafana tiene que firmar su aserción con ese algoritmo, o el login OIDC de Grafana falla. El diseño no lo fija. Además, `test_realm_files_assertions_are_signed_with_the_algorithm_of_br_u2_09` extiende BR-U2-09 a todo cliente `client-jwt`, más allá de lo que dice la regla. Va a D-G.

### F-02 · NARANJA · test_realm_files.py (falta cobertura) · Valores derivables y con efecto sin lectura de vuelta
Sobreviven (90 passed cada una):
- `include.in.token.scope: 'false'`: los tokens de servicio saldrían sin `scope` y BR-U0-71 rechazaría todas las llamadas.
- `fullScopeAllowed: true`: el claim `roles` llevaría más que el rol de negocio, en contra de domain-entities.md:52.
- `operacion` en el token de `vectra-console`, en contra de domain-entities.md:20-23.
- `cro` en `promotion-tool`, en contra de :67 y :123.
- `use.refresh.tokens: 'false'`, en contra de BR-U2-06:51.

CA-2 pide que la prueba compruebe lo que el plan nombra: «mapper `roles`», «rotación de refresh» y los clientes de §2. Es cobertura ausente. El arreglo es leer de vuelta 1a, 1b, 1c, 3 y 6a de la tabla anterior, todos derivables del diseño, sin consultar al usuario.

### F-03 · AMARILLO · test_realm_files.py:116-123 · Listas de §1.0 repetidas a mano
El conjunto de 7 nombres y `== ["ES256", "RS256"]` duplican lo que se acaba de leer de §1.0. Sirven de guarda, pero obligan a tocar la prueba si el diseño agrega un ajuste.

## Decisiones para el usuario (una sola consulta)
- **D-G · Firma de las aserciones `private_key_jwt` fuera de los servicios de §2.2.**
  - **G1, cliente `grafana`:**
    - (a) ES256, como los servicios; se escribe en domain-entities §2.1 y la configuración `generic_oauth` de U1 debe usar una llave EC.
    - (b) RS256.
    - (c) No se fija el atributo, de modo que Keycloak acepte cualquier algoritmo asimétrico.
    - En todos los casos hay que confirmar en U1 que Grafana admite `private_key_jwt` con ese algoritmo.
  - **G2, `keycloak-config-cli` y `keycloak-reader`:**
    - (a) Se confirma que BR-U2-09 los cubre, como cuentas de servicio con ES256.
    - (b) Otro algoritmo, si la herramienta `keycloak-config-cli` no admite ES256.

## Tareas candidatas (defectos reales fuera de alcance)
- La prueba de extremo a extremo en kind que lea el token real: `acr` y `amr` por rol, `break-glass` con MFA, `aud` por scope pedido, el claim `scope`, `client_credentials` firmado con ES256 desde `vectra_common.service_token`, y el login de Grafana y de `keycloak-config-cli` con su aserción.
- `realm_lint.py` sigue con `REALM_PARAMETERS` y `MFA_REQUIRED_ROLES` escritos a mano (U02-T03).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r4-scripts/mut.out` (mutaciones)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r4-scripts/ca4.out` (CA-4)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r4-scripts/mut.py` (script)

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/keycloak/realm/realm.prod.yaml:879|ES256 en el cliente de usuario grafana sin respaldo; BR-U2-09 solo cubre clientes de servicio (D-G)
NARANJA|identity-edge/tests/unit/test_realm_files.py|Sin lectura de vuelta de include.in.token.scope, fullScopeAllowed/scopeMappings y use.refresh.tokens (7 mutaciones sobreviven)
AMARILLO|identity-edge/tests/unit/test_realm_files.py:116|Listas de §1.0 repetidas a mano en la prueba
INFORME: revisiones/U02-T04/ronda-4.md
```
