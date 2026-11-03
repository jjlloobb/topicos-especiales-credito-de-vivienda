# Ronda 2 — U02-T04

VEREDICTO: NO-VERDE

Comprobaciones previas:
- **Hash de la tarea:** `53b68973…9eba7`, coincide.
- **Worktree:** `wt-U02-T04` en `2acc676`, con `git status --porcelain` vacío al empezar y al terminar.
- **Commits revisados:** `f77bd79` (pruebas) y `1862276` (realms), sobre `9dfa65b`. El codificador solo tocó los 3 YAML, `test_realm_files.py`, `design_values.py`, la bitácora y la respuesta, así que no hay desborde.
- **Entorno:** trabajé sobre una copia (`git archive 2acc676`) con su propio venv y `UV_OFFLINE=1`. Al terminar borré la copia y el venv, y no queda ningún proceso en segundo plano.
- **Diseño de referencia:** juzgo contra el diseño enmendado (`05aac38` y E1–E4 de `9dfa65b`).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | realm-lint de los 3 realms | `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml` | pasa (rc=0) |
| 2 | Lectura de vuelta contra el diseño | `uv run pytest identity-edge/tests/unit -q -k realm_files` | pasa (75 passed, 3,7 s), pero ver F-02 y F-03 |
| 3 | Sin secretos en claro | `uv run pytest identity-edge/tests/unit -q -k realm_has_no_secret_values` | pasa (12 passed), pero ver F-05 |
| 4 | Lo anterior sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` (con pipefail) | pasa (rc=0, «All checks passed!», 604 passed) |

**Rojo primero (F-09 de la ronda 1).** Lo reproduje sobre `f77bd79`: los realms son idénticos a los de `8174ab6` (diff vacío) y `-k realm_files` da 15 failed y 60 passed. F-09 queda resuelto.

**Mutaciones.** Corrí 56: 44 sobre los YAML (cargados y reescritos como YAML; una ida y vuelta sin cambios da 75 passed) y 11 sobre el diseño. Todas se restauraron. Transcripción en `scratchpad/rev-u02t04-r2-scripts/mut.out`.
- **Las mataron:**
  - las 21 de la ronda 1 que siguen aplicando;
  - LoA: el nivel 2 cambiado a 1, quitar `default.acr.values`, el factor sin WebAuthn y `analista` sin `conditional-user-configured`;
  - `break-glass`: la condición cambiada a `view-realm` y el subflujo quitado;
  - `amr`: quitar el mapper;
  - audiencia: cambiar la de un scope y volver a poner una audiencia fija en el cliente;
  - OTP (E1–E4): `BASE64`, otra variable y `CONFIGURE_TOTP` en un sintético;
  - D3: un host literal;
  - D2: `cachePolicy`, `useTruststoreSpi` y `startTls` agregados;
  - en el diseño: §6 (access token y SSO), BR-U2-05, §1.1 `analista`, §2.2, §2.1 (post-logout y `aud` de `promotion-tool`), §4 (callback de Grafana), §3 (usuarios por rol) y LoA `mfa` = 3.
- **Sobrevivieron:** ver F-01 a F-05.

## Estado de los hallazgos de la ronda 1
- **F-01:** resuelto por D1. La prueba fija que `group-role-map.yaml` no existe y que la federación no tiene `subComponents`.
- **F-02:** resuelto en lo estático. El flujo de nivel 1 lleva la contraseña. Cada rol MFA y `break-glass` tienen un subflujo de nivel 2 con la condición de rol y el factor TOTP o WebAuthn, y `analista` tiene uno condicionado a `conditional-user-configured`. No se puede ejecutar sin Keycloak: va como tarea candidata.
- **F-03:** resuelto. La condición sobre `realm-management.realm-admin` está en realm.prod.yaml:632, y dos mutaciones la matan.
- **F-04:** abierto (F-01 de esta ronda).
- **F-05:** resuelto en la forma: hay un mapper de audiencia por client scope y los clientes no tienen audiencias fijas. Falta confirmar la regla (D-C).
- **F-06:** resuelto. §6 y BR-U2-05 se leen del diseño y las mutaciones de diseño fallan.
- **F-07:** resuelto en lo esencial. Quedan restos menores en F-04 de esta ronda.
- **F-08:** mejorado. Quedan huecos menores en F-05 de esta ronda.
- **F-09** y **F-10:** resueltos.
- **F-11:** resuelto por D2. La federación solo lleva `$(env:LDAP_*)` y los tres valores de INF-U2-07.

## Cumplimiento de D3, D5, E1–E4 y las demás decisiones
- **D3:** no queda ningún host literal. Solo aparece `http://127.0.0.1` de `promotion-tool`, que el diseño da en §2.1. Todo lo demás es `https://$(env:PUBLIC_HOSTNAME)/…`, y kind y staging son idénticos salvo la línea 1.
- **D5 y E1–E4:** los 10 sintéticos van sin `CONFIGURE_TOTP` y con la credencial de forma exacta. Ejemplo en realm.kind.yaml:716-718: `secretData` con `{"value":"$(env:SYNTH_CRO_1_TOTP_SEED)"}` y `credentialData` con los cinco campos y `BASE32`. `break-glass` conserva `CONFIGURE_TOTP`.
- **D6, D7 y D8:** se cumplen. No hay sesiones persistentes en el realm, el listener es `jboss-logging` y el cliente `grafana` solo entrega `roles`.

## Hallazgos
### F-01 · NARANJA · realm.*.yaml, mapper `amr` (por ejemplo realm.kind.yaml:884-889) · El claim `amr` probablemente sale vacío y la prueba no lo comprueba
domain-entities.md:34 y :43 exigen `amr` en el token. Según la documentación de Keycloak, `oidc-amr-mapper` arma el claim con la referencia configurada en cada ejecución del flujo. Aquí ninguna ejecución la tiene: el propio codificador lo dice en el supuesto 4 y en «Bloqueos». No lo puedo verificar sin Keycloak ni red.

El diseño no define los valores de `amr`, así que hace falta la decisión D-A. Además, la prueba solo mira que el mapper exista: la mutación `access.token.claim: 'false'` sobrevive (75 passed).

### F-02 · NARANJA · realm.*.yaml `loa-pwd` y `loa-mfa` (realm.prod.yaml:608-615) · `loa-max-age: 36000` es un valor inventado y no se prueba
Ningún documento de diseño fija `loa-max-age` (grep sin resultados). Es un literal nuevo con efecto visible para el usuario: decide cuándo se vuelve a pedir el segundo factor por SSO, en la recarga silenciosa de BR-U2-07. Por el invariante 8 es NARANJA, y por la regla del usuario va a D-B.

Las mutaciones a 0 y a 900 sobreviven (75 passed).

### F-03 · AMARILLO · test_realm_files.py, el flujo y los scopes · La lectura de vuelta es asimétrica
- La mutación de diseño «`operacion`: MFA opcional» sobrevive (75 passed). La prueba exige subflujos para los roles obligatorios, pero no que los demás roles no los tengan.
- Un mapper de audiencia agregado al scope de usuario `governance:promotion` sobrevive (75 passed). `test_realm_files_audience_follows_the_requested_scope` solo recorre los clientes de servicio.

### F-04 · AMARILLO · test_realm_files.py:403-406 · La prueba es más estricta que E4 y deja literales a mano
- E4 (domain-entities §3) admite además `"counter":0`. La prueba exige igualdad exacta sin él: esa mutación falla en la prueba (1 failed) mientras `realm-lint` la acepta (rc=0).
- Literales que quedan escritos a mano: `len(ids) == 3` (:212), `== {"pwd": 1, "mfa": 2}` (:107), y `DOMAIN_AUDIENCE` en design_values.py, que depende de D-C.

### F-05 · AMARILLO · test_realm_files.py:461-497 · El detector de secretos tiene huecos menores
Sobreviven `hashedSaltedValue` y `salt` literales en una credencial, y `attributes.client.secret` literal (75 passed cada uno). Keycloak no usa ese atributo como secreto del cliente, pero CA-3 pide fallar ante «un `secret`… literal».

### F-06 · AMARILLO · business-rules.md:107-108 (enmienda de `05aac38`, no es del codificador) · Texto roto en BR-U2-16
Dice «…ni `email`. La / El realm usa el listener… La / correlación…»: la enmienda quedó insertada en medio de la frase. Lo debe arreglar el orquestador.

## Supuestos nuevos del codificador, contra el diseño
| # | Supuesto | Estado | Evidencia |
|---|---|---|---|
| 1 | Audiencia según el dominio del scope | **Implícito en el diseño, sin regla escrita** | En contracts domain-entities.md §7.2 (:328-329) están los dos casos no obvios: «`case:recommend`… (llamar a scoring)» y «`scoring:explain`… (llamar a explainability)». Los demás prefijos coinciden con el dueño del endpoint. La unión por cliente da igual que §2.2 (identity-edge domain-entities.md:66-77) en los 3 entornos. Falta escribirlo en §2.2 → D-C |
| 2 | `default.acr.values: mfa` en los 3 clientes de usuario | **Se deriva del diseño; no hace falta pregunta** | BR-U2-03 (business-rules.md:25-26) dice que el flujo exige el segundo factor siempre y que el token lleva `acr = mfa`. Con flujos de LoA, el nivel 2 solo corre si se pide, así que este atributo es el medio técnico para cumplirlo. Para `analista` sin factor el ACR no es esencial y queda `pwd` (§1.2:31) |
| 3 | `loa-max-age` de 36 000 s | **No definido** | Sin mención en ningún documento. El `mfa_max_age` de 900 s (§6:130) lo aplican los servicios con `auth_time` (BR-U2-04) → F-02 y D-B |
| 4 | `amr` sin referencia por autenticador | **El qué está definido, los valores no** | §1.2:34 y §1.3:43 piden `amr`, sin valores → F-01 y D-A |

## Decisiones para el usuario
- **D-A · Valores de `amr`.** ¿Qué valores lleva el claim?
  - (a) Los de RFC 8176, configurados como referencia en cada ejecución: `pwd` en la contraseña, `otp` en TOTP, `hwk` en WebAuthn.
  - (b) Los mismos de `acr` (`pwd` o `mfa`).
  - (c) Se quita `amr` del diseño (§1.2 y §1.3) y se queda solo `acr` y `auth_time`.
- **D-B · Validez del nivel en SSO (`loa-max-age`).**
  - (a) 36 000 s, el máximo de la sesión SSO: la recarga silenciosa (BR-U2-07) no vuelve a pedir el factor y el step-up sigue con `max_age=0`.
  - (b) 900 s, igual a `mfa_max_age`: pasados 15 minutos, la recarga silenciosa de un usuario MFA falla y debe hacer login completo.
  - (c) 0: se pide el factor en cada autenticación, lo que rompe la recarga silenciosa.
- **D-C · Audiencia por scope.**
  - (a) Se confirma la regla por dominio y se agrega a §2.2 una columna scope → audiencia (la prueba la leería de ahí, no de `DOMAIN_AUDIENCE`).
  - (b) Se vuelve a la unión fija por cliente, como en la ronda 1, aceptando tokens más amplios.
  - (c) Usted da otra asignación.

## Tareas candidatas (defectos reales fuera de alcance)
- Una prueba de extremo a extremo en kind que lea el token real: `acr` por rol con LoA y `default.acr.values`, `break-glass` con MFA, `amr`, `aud` por scope pedido, y validez de 60 s y `jti` de las aserciones (BR-U2-09).
- Arreglar el texto de BR-U2-16 (F-06).
- `realm_lint.py` sigue con `REALM_PARAMETERS` y `MFA_REQUIRED_ROLES` escritos a mano (U02-T03).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r2-scripts/mut.out` (mutaciones)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r2-scripts/ca4.out` (CA-4)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r2-scripts/mut.py` (script de mutaciones)

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/keycloak/realm/realm.kind.yaml:884|amr sin referencias: probablemente vacío; la prueba no mira access.token.claim (D-A)
NARANJA|identity-edge/keycloak/realm/realm.prod.yaml:611|loa-max-age 36000 inventado y sin prueba (D-B)
AMARILLO|identity-edge/tests/unit/test_realm_files.py:168|Lectura de vuelta asimétrica: rol sin MFA obligatorio y scopes de usuario sin cubrir
AMARILLO|identity-edge/tests/unit/test_realm_files.py:403|La prueba rechaza "counter":0, que E4 admite; restos de literales a mano
AMARILLO|identity-edge/tests/unit/test_realm_files.py:461|Detector de secretos: hashedSaltedValue y attributes.client.secret pasan
AMARILLO|aidlc-docs/construction/identity-edge/functional-design/business-rules.md:107|Texto de BR-U2-16 roto por la enmienda
INFORME: revisiones/U02-T04/ronda-2.md
```
