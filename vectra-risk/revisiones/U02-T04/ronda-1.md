# Ronda 1 — U02-T04

VEREDICTO: NO-VERDE

Tarea con hash `ee5a6c1…4cea` (coincide). Worktree `wt-U02-T04` en `8174ab6`, base `bafca5f`, un solo commit. Al terminar, `git status --porcelain` sale vacío. El diff solo toca los 3 YAML, `test_realm_files.py`, `design_values.py` y la bitácora, así que no hay desborde. Corrí todo sobre una copia (`git archive`) en `scratchpad/rev-u02t04-r1/`, con su propio venv y `UV_OFFLINE=1`.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | realm-lint de los 3 realms | `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml` | pasa (rc=0) |
| 2 | Lectura de vuelta contra el diseño | `uv run pytest identity-edge/tests/unit -q -k realm_files` | pasa (63 passed, 3,06 s), pero ver F-01, F-06 y F-07 |
| 3 | Sin secretos en claro | `uv run pytest identity-edge/tests/unit -q -k realm_has_no_secret_values` | pasa (8 passed), pero ver F-08 |
| 4 | Lo anterior sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` (con pipefail) | pasa (rc=0, 244 passed) |

Mutaciones: 27 en total, 22 sobre los YAML y 5 sobre el diseño, restauradas una por una (comprobado con `diff -rq` contra el worktree). Transcripción en `scratchpad/rev-u02t04-r1-scripts/mut.out`.
- **Las mataron:** subflujo MFA de `operacion`, `accessTokenLifespan`, `/stepup-callback`, un comodín, `failureFactor` en el realm, `governance:freeze` fuera de su cliente, `break-glass` sin TOTP, LDAP `WRITABLE` o `ldap://389`, `passwordPolicy`, eventos de administración con detalle, `revokeRefreshToken`, `acr.loa.map`, `webauthn-register`, los mappers `name` o `email`, refresh en una cuenta de servicio, y en el diseño la tabla §2.2 y el host de INF-U2-01.
- **Sobrevivieron:** ver F-06, F-07 y F-08.

## Hallazgos

### F-01 · ROJO · plan Paso 2 (code-generation-plan.md:88, :42) · El Paso 2 no está completo: faltan `group-role-map.yaml` y los mappers de grupo LDAP
El plan pide «prod: federación LDAPS `READ_ONLY` con `group-role-map.yaml` (INF-U2-07)». INF-U2-07 (infrastructure-design.md:91) exige el «mapper de grupos → roles según `group-role-map`». El archivo no existe. El componente `ldap-banco` (realm.prod.yaml:1035) no tiene ningún mapper de grupo o rol, así que en producción ningún usuario LDAP recibe rol.

El codificador se detuvo, como manda la regla del usuario: no es culpa suya. Pero el alcance «dentro» no está entregado y la tarea no puede cerrar hasta que el usuario decida (D1 y D2).

### F-02 · NARANJA · realm.{env}.yaml:18 y :194 (`vectra-browser forms`) · El flujo no puede emitir `acr = mfa`
BR-U2-03 (business-rules.md:25-26) dice «su token tiene `acr = mfa`». BR-U2-04 (:30) pide step-up con `acr_values=mfa`. F08 (domain-entities.md:56) exige `acr = mfa`.

El realm tiene `acr.loa.map`, pero el flujo no tiene ninguna ejecución `conditional-level-of-authentication`. Sin esas condiciones, Keycloak emite el nivel 1 en un login fresco y 0 por SSO, y con este mapa el 1 sale como `pwd`, haya OTP o no. Esto no se puede verificar aquí (no hay Keycloak): el codificador lo dejó como supuesto 7a.

Ninguna prueba cubre cómo se llega a `mfa`. Hay que modelar el LoA 2 (condiciones de nivel combinadas con la condición de rol) o presentar evidencia de lo contrario.

### F-03 · NARANJA · realm.prod.yaml:417 y el flujo :189 · `break-glass` sin MFA en el flujo
domain-entities.md:91 dice que `break-glass` tiene «`realm-admin` y MFA». Sus subflujos condicionales solo miran los roles de realm (`ingeniero_riesgo`, `cro`, `cumplimiento`, `operacion`, `analista`), y `break-glass` no tiene ninguno. Su `CONFIGURE_TOTP` solo obliga a registrar el TOTP una vez: después, el flujo lo deja entrar con la contraseña sola.

Falta una condición sobre el rol de cliente `realm-management realm-admin`, o un mecanismo equivalente.

### F-04 · NARANJA · realm.{env}.yaml, mappers de `vectra-console`, `promotion-tool` y `grafana` (desde :604) · Falta el claim `amr`
domain-entities.md:34 y :43 lo exigen: «El token incluye `acr`, `amr` y `auth_time`». Está definido en el diseño. Keycloak tiene un mapper AMR nativo desde la 23 (`oidc-amr-mapper`, junto con la referencia por autenticador), así que la afirmación del supuesto 7b («sin mapper nativo claro») no se sostiene. Ninguna prueba lo exige.

### F-05 · NARANJA · realm.kind.yaml:796-837 (y los demás clientes de servicio) · La audiencia es la unión de todas, no el destino
business-logic-model.md:46-47 dice que se pide `audience=<destino>` y el token sale con `aud = destino`. domain-entities.md:61-62 dice que cada cliente pide «la audiencia correspondiente».

Los `oidc-audience-mapper` fijos ponen todas las audiencias en cada token. Por ejemplo, un token de `case-service` lleva siempre `core-banking-mock`, `decision-registry-service` y `governance-service`, y se puede reusar ante cualquiera de los tres. La audiencia debería atarse al scope pedido, por ejemplo con el mapper de audiencia dentro de cada client scope. La prueba (`audiences(client) == …`) valida la unión, no el comportamiento del diseño.

### F-06 · NARANJA · test_realm_files.py:91 · El valor leído del diseño queda anulado por la constante del lint
La línea es `{**design.brute_force_fields(), **REALM_PARAMETERS}`, y `REALM_PARAMETERS` (realm_lint.py:70-81) vuelve a escribir a mano los mismos campos y gana. Mutaciones de diseño que sobreviven:
- BR-U2-05 con `failureFactor: 6`: 63 passed.
- domain-entities §6 con access token de 600 s: 63 passed.

`design_values.brute_force_fields()` es, en la práctica, código muerto. Las vidas de tokens y sesiones de §6 nunca se leen del diseño. CA-2 pide comparar «contra los valores de domain-entities, no contra una lista nueva escrita a mano».

### F-07 · NARANJA · test_realm_files.py:32, :154, :163, :169-170, :308, :133 · Barrido de la clase «valores escritos a mano en la prueba»
- `MFA_ROLES = ("ingeniero_riesgo","cro","cumplimiento")` no se lee de la columna MFA de §1.1. La mutación «`analista` obligatorio» en el diseño sobrevive (63 passed).
- `ids == {"vectra-console","promotion-tool","grafana"}`.
- `len(names) == 10`.
- `redirectUris == ["http://127.0.0.1"]` y `audiences(promotion) == {"governance-service"}`, cuando §2.1 los da.
- `post.logout.redirect.uris == f"https://{host}/"` es un valor que el diseño no define (D4).
- Las rutas `/callback` y `/stepup-callback` están literales en vez de salir de §4.
- El alias fijo `"vectra-mfa-cro factor"`: solo se comprueba el factor de un rol.

Además, la redirect URI de `grafana` no se comprueba: la mutación a `https://evil.example/...` sobrevive.

### F-08 · NARANJA · test_realm_files.py:353-377 · El detector de secretos tiene huecos (CA-3)
- `value: $(env:SYNTH_CRO_1_PASSWORD)Hunter2` pasa como referencia (63 passed). La causa es la regla del residuo de 16 o más caracteres en :377.
- Un `privateKey` literal en `org.keycloak.keys.KeyProvider` no lo detecta el detector: `privateKey` no está en `SECRET_KEYS`. La mutación solo cayó por casualidad, en otra prueba.

El criterio dice «falla si un YAML tiene una contraseña, un `secret` o una semilla TOTP literal». Una referencia debe ser exactamente `$(env:NOMBRE)`, y las llaves privadas y certificados deben entrar en la lista.

### F-09 · AMARILLO · bitácora:10-14 · «Rojo primero» sin evidencia en Git
Pruebas y realms entran en un mismo commit. Los conteos del rojo (62 failed) son una afirmación del codificador, no evidencia reproducible.

### F-10 · AMARILLO · bitácora:40 · Formato de la bitácora
Se pidieron las secciones «Supuestos» y «Bloqueos» por separado. Están mezcladas en «Supuestos y huecos de especificación».

### F-11 · AMARILLO · realm.prod.yaml:1040-1081 · Parámetros de LDAP que el diseño no fija
`fullSyncPeriod: -1`, `authType simple`, `validatePasswordPolicy false`, `trustEmail false`, `priority 0`, y `cachePolicy: NO_CACHE`. Este último interpreta «sin caché de contraseñas» (INF-U2-07:92) como sin caché de usuarios. Van a D2.

## Supuestos y bloqueos del codificador, contra el diseño
| # | Tema | Estado | Evidencia |
|---|---|---|---|
| B1 | Nombres de los grupos LDAP | **No definido** | BR-U2-15 (business-rules.md:98) solo fija el formato `groups: {<grupo>: <rol>}`. domain-entities.md:24 habla de un «grupo LDAP de operación», sin nombre. → D1 |
| B2 | URL o host del LDAP | **No definido** | INF-U2-07:89-90 fija LDAPS 636, la CA del banco y el bind desde ESO, pero no el host. component-dependency.md:283 dice además que en el MVP F73 «no existe». → D2 |
| S1 | Hostnames de staging y prod | **Definido como ejemplo, con otro dueño** | INF-U2-01 (infrastructure-design.md:16-17, :21): «de ejemplo… se fijan con el banco **en los values de cada entorno**». Escritos en el realm, dejan una segunda fuente de verdad. → D3 |
| S2 | URI de post-logout y callback de Grafana | **No definido** | domain-entities.md:55 exige `post_logout_redirect_uris` exactas, sin valor. :103 dice «Grafana hace su propio OIDC», sin la ruta de callback. → D4 |
| S3 | 12 clientes frente a «los 10» | **Definido, sin contradicción real** | La tabla §2.2 (domain-entities.md:66-77) tiene 12 filas. Sin `channel-simulator` ni `verification-reader`, que solo existen fuera de prod, quedan 10, el mismo número de NFR-U2-10 (nfr-requirements.md:25). Implementar las 12 es correcto. El texto del plan (:79) es impreciso: corregirlo es cosa del orquestador. |
| S4 | `CONFIGURE_TOTP` frente a la semilla de ESO | **Contradicción en el diseño** | BR-U2-03:22-24 y business-logic-model.md:24 piden la required action solo «sin TOTP configurado». domain-entities.md:88 dice que la semilla viene de ESO, y el lint de U02-T03 exige `CONFIGURE_TOTP` a todo usuario con MFA. Una acción puesta explícitamente hace que Keycloak pida configurar otra vez. → D5 |
| S5a | Sesiones persistentes | **Definido, pero fuera del realm** | NFR-U2-02 (nfr-requirements.md:16) y tech-stack-decisions.md:10 («sesiones persistentes nativas»): es del servidor (Pasos 4 y 5), aunque el plan (:74) lo ponga en el Paso 2. → D6 |
| S5b | Eventos sin username ni email | **Definido el qué, no el cómo** | BR-U2-16 (business-rules.md:106-108) y domain-entities.md:122-123 piden `details` filtrados. Con `jboss-logging` a secas (realm.kind.yaml:33), los eventos de login sí llevan `username`. El diseño no dice qué mecanismo lo filtra. → D7 |
| S6 | Sin mapper de `amr` | **Definido; el supuesto es incorrecto** | domain-entities.md:34 y :43. Es F-04: no necesita pregunta. |
| S7 | Tabla de Grafana fuera del realm | **Parcialmente definido** | domain-entities.md:57 da la tabla rol → rol y equipo. bias-monitoring infrastructure-design.md:131 dice que los equipos se mapean «desde los roles del token». Ningún plan dice dónde vive la configuración OIDC de Grafana. → D8 |
| S8 | Llaves públicas como `$(env:CLIENT_*_JWKS)` | No definido el nombre de las variables, que fija un contrato con el Paso 5 | domain-entities.md:82: las llaves se registran en el realm. Aceptable, a confirmar en D3. |
| S9 | Validez de 60 s de las aserciones (BR-U2-09:60) y `clientScopeMappings` | Sin verificar (no hay Keycloak) | No hay prueba de extremo a extremo. Va como tarea candidata. |

## Decisiones para el usuario
- **D1 · Grupos LDAP → rol (B1).** ¿Qué hacemos con `group-role-map.yaml`?
  - (a) Usted da ahora los nombres de los 5 grupos del banco (4 de negocio y `operacion`).
  - (b) Los nombres van como referencias `$(env:LDAP_GROUP_<ROL>)` resueltas desde ESO o los values, y `realm-lint` las acepta (habría que tocar el lint, en otra tarea).
  - (c) Se saca `group-role-map.yaml` y los mappers a una tarea propia, y el Paso 2 se cierra sin ellos.
- **D2 · Conexión LDAP (B2 y F-11).**
  - (a) Host, base DN, atributos y vendor desde ESO o values, como dejó el codificador, y usted confirma los valores por defecto de F-11.
  - (b) Usted da los valores reales y van literales en `realm.prod.yaml`.
  - (c) Como component-dependency.md:283 dice que en el MVP F73 no existe, `realm.prod.yaml` va sin federación hasta Operations, y se enmienda INF-U2-07.
- **D3 · Hostnames y nombres de variables (S1 y S8).**
  - (a) Se dejan los hostnames de ejemplo literales en el realm y se cambian cuando el banco los fije.
  - (b) El realm usa `$(env:PUBLIC_HOSTNAME)` y la única fuente son los values (INF-U2-01:21).
  - En los dos casos: ¿aprueba los nombres `CLIENT_<ID>_JWKS`, `SYNTH_<USUARIO>_*`, `BREAK_GLASS_PASSWORD` y `LDAP_*` como contrato del Paso 5?
- **D4 · URIs que el diseño no fija (S2).**
  - Post-logout: (a) `https://<host>/`; (b) una ruta propia de la SPA, por ejemplo `/logged-out`, agregada a §4.
  - Callback de Grafana: (a) `https://<host>/grafana/login/generic_oauth`, la ruta estándar de Grafana; (b) otra que fije la unidad dueña de Grafana (U1).
- **D5 · TOTP de los usuarios sintéticos (S4).**
  - (a) La semilla viene de ESO y se quita `CONFIGURE_TOTP` de los sintéticos con semilla (cambiar `realm-lint` en otra tarea).
  - (b) Se mantiene `CONFIGURE_TOTP` y se quita la semilla: cada persona configura su TOTP y las pruebas de extremo a extremo lo hacen con `pyotp`.
  - (c) Se aceptan las dos cosas y la reconfiguración en el primer login.
- **D6 · Sesiones persistentes (S5a).**
  - (a) Se confirma que es una opción del servidor y se mueve del Paso 2 a los Pasos 4 y 5 (enmienda del plan).
  - (b) Se deja una nota en el realm sin efecto y se verifica en el Paso 5.
- **D7 · Filtrado de `username` y `email` en los eventos de login (S5b).**
  - (a) Un listener de eventos propio en la imagen (Paso 4).
  - (b) Se descartan los campos en el pipeline de Alloy o Loki (U1).
  - (c) Se acepta `jboss-logging` y se enmienda BR-U2-16.
- **D8 · Dónde vive el mapeo de Grafana a roles y equipos (S7).**
  - (a) En la configuración `generic_oauth` de Grafana de U1, con el realm entregando solo el claim `roles`. Ojo: la sincronización de equipos por OAuth podría requerir Grafana Enterprise; hay que comprobarlo.
  - (b) Grupos de Keycloak y un claim `groups` en el realm (Paso 2).
  - (c) El Job `grafana-folder-permissions` de U1 asigna los equipos.

## Tareas candidatas (defectos reales fuera de alcance)
- Una prueba de extremo a extremo en kind que lea el token real: `acr`/`amr`/`auth_time` por rol, `break-glass` con MFA, `aud` por scope pedido, y validez de 60 s y `jti` de las aserciones (BR-U2-09).
- `REALM_PARAMETERS` y `MFA_REQUIRED_ROLES` de `realm_lint.py` (U02-T03) están escritos a mano. Deberían leerse del diseño.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r1-scripts/mut.out` (mutaciones)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r1-scripts/ca4.out` (CA-4)

```
VEREDICTO: NO-VERDE
ROJO|identity-edge-code-generation-plan.md:88|Falta group-role-map.yaml y los mappers de grupo LDAP (bloqueado por D1/D2)
NARANJA|identity-edge/keycloak/realm/realm.kind.yaml:194|El flujo no tiene condiciones de LoA: no puede emitir acr=mfa
NARANJA|identity-edge/keycloak/realm/realm.prod.yaml:417|break-glass sin MFA en el flujo de login
NARANJA|identity-edge/keycloak/realm/realm.kind.yaml:604|Falta el mapper amr exigido por domain-entities §1.2/§1.3
NARANJA|identity-edge/keycloak/realm/realm.kind.yaml:819|La audiencia de servicio es la unión fija, no el destino pedido
NARANJA|identity-edge/tests/unit/test_realm_files.py:91|REALM_PARAMETERS anula los valores leídos de BR-U2-05; §6 nunca se lee
NARANJA|identity-edge/tests/unit/test_realm_files.py:32|Valores escritos a mano en la prueba (MFA_ROLES, ids, URIs, conteos, alias)
NARANJA|identity-edge/tests/unit/test_realm_files.py:377|El detector de secretos acepta un residuo literal e ignora privateKey
AMARILLO|vectra-risk/bitacoras/U02-T04.md:10|Rojo primero sin evidencia en Git
AMARILLO|vectra-risk/bitacoras/U02-T04.md:40|Supuestos y bloqueos sin secciones separadas
AMARILLO|identity-edge/keycloak/realm/realm.prod.yaml:1040|Parámetros de LDAP no fijados por el diseño
INFORME: revisiones/U02-T04/ronda-1.md
```
