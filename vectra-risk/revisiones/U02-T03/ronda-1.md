# Ronda 1 — U02-T03

VEREDICTO: NO-VERDE

Los cuatro criterios pasan cuando los corro yo. Las 29 mutaciones del validador las detecta al menos una prueba. El veredicto es NO-VERDE por tres motivos de diseño. La traducción de la fuerza bruta contradice BR-U2-05. El formato de `group-role-map.yaml` se inventó. Y hay reglas sin respaldo en el diseño: el codificador debió detenerse, como pide la regla del usuario.

Comprobaciones previas: el hash de la tarea es `495e7b6…` en el worktree y en el repositorio principal. HEAD está en `ce5ab30` sobre `bb5ca90`. Después de la revisión, el worktree sigue limpio: `git status` solo lista archivos ignorados (`platform/.charts`, `platform/.tools` y cachés).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`, `UV_OFFLINE=1`) | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 3 | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_*.py identity-edge/tests/unit/test_realm_lint.py -q` | pasa, 95 passed en 5,12 s. Con `--hypothesis-show-statistics`, cada propiedad corre 500 ejemplos, así que no hay saltos |
| 2 | Cada regla del Paso 2 con un caso que falla y uno que pasa | `uv run pytest … -k "operacion or break_glass or …"` | pasa, 19 passed. Hay un caso de error y uno válido para `operacion`, `break-glass`, `verification-reader`, `product-metrics`, `channel-simulator` y `case-service` |
| 3 | CLI como subproceso | `uv run pytest … -k cli` | pasa, 12 passed. De esos 12, 7 son pruebas reales de CLI y 5 entran por la palabra «client» (ver F-06). Sí existe un caso válido con código 0 (`test_cli_exits_zero_on_valid_realms`) y uno inválido con código distinto de 0 que muestra el archivo y la regla (`test_cli_exits_nonzero_naming_file_and_rule_on_invalid_realm`) |
| 4 | El esqueleto sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` | pasa, termina en 0 (ruff limpio, 97 passed) |

**Mutaciones.** Hice 29, sobre una copia en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r1/`. Al final restauré el archivo y un `diff` contra HEAD sale vacío. Todas las mutaciones las detecta al menos una prueba. Para los cuatro casos nombrados de la aceptación y para el par prod/staging de `case-service`, cada mutación la detecta una prueba con el nombre de ese caso:
- dos roles: M01;
- `core:write-credit`: M02;
- `governance:freeze`: M03;
- `case-service` en producción: M04 y M05;
- `case-service` en staging: M06.

**Scopes.** Salen de verdad de `vectra_contracts.catalog.Scope` (`realm_lint.py:43`). Los realms de ejemplo se construyen desde `SCOPE_HOLDERS`.

## Los puntos que pediste, contra el diseño
1. **Esquema `realm.*.yaml`: definido, de forma implícita.** El realm lo aplica `keycloak-config-cli` (tech-stack-decisions.md:13, business-rules.md:91, logical-components.md:14, plan:124). Eso fija la representación de realm de Keycloak. Los nombres de archivo por entorno los fija el plan (plan:70 y :89). Hay desvíos respecto de esa representación: ver F-04.
2. **`group-role-map.yaml`: no definido.** INF-U2-07 solo dice «mapper de grupos → roles según `group-role-map`» (infrastructure-design.md:88). BR-U2-15 (business-rules.md:96) y domain-entities.md:89 tampoco fijan el formato. Ver F-02.
3. **Fuerza bruta: contradice BR-U2-05.** Ver F-01.
4. **Reglas extra:**
   - `secret` prohibido en todo cliente: BR-U2-09 solo lo exige a los clientes de servicio (business-rules.md:58-59, plan:97). Extenderlo a los clientes de usuario es desborde (F-03).
   - `client-jwt` obligatorio en los de servicio: sustentado por BR-U2-09 (business-rules.md:57) y domain-entities.md:59.
   - Sin comodines en `webOrigins` y en las URIs de post-logout: sustentado. domain-entities.md:55 pide `post_logout_redirect_uris` exactas y orígenes web iguales al host del gateway.
   - `acr.loa.map` fijo: el valor está definido (domain-entities.md:34, plan:71), pero el Paso 3 no pide verificarlo (plan:92-100), y §6 no lo incluye (domain-entities.md:126-133). Pasa lo mismo con `revokeRefreshToken` y `refreshTokenMaxReuse`. Es desborde menor (F-03).
   - MFA para `realm-admin`/`break-glass`: sustentado por domain-entities.md:91 («`break-glass` … con `realm-admin` y MFA»). La implementación no lo detecta en la forma real de Keycloak (F-04).
   - `profile` y `email` vetados salvo que el realm los redefina: sustentado por domain-entities.md:46 y plan:98. Esos scopes de Keycloak emiten justo esos claims.
   - Exención `KEYCLOAK_BUILTIN_SCOPES`: no definida, y contradice PBT-U2-03 y el plan (F-03).

## Hallazgos
### F-01 · ROJO · identity-edge/tools/realm_lint.py:76-90 · La configuración de fuerza bruta nunca bloquea de forma permanente
- BR-U2-05 (business-rules.md:40) y §6 (domain-entities.md:133) exigen «20 fallos en 12 h → bloqueo permanente».
- El validador **exige** `permanentLockout: False` y además **rechaza** `True`, que es el único modo de Keycloak que bloquea de forma permanente: la prueba `test_realm_parameter_out_of_spec_is_rejected[permanentLockout-True]` (test_realm_lint.py:330) lo afirma, y mi sonda lo confirma (`permanentLockout=True` → `['parametro-del-realm']`).
- En Keycloak, `maxTemporaryLockouts` solo tiene efecto con `permanentLockout=true`. El modo «bloqueo permanente tras bloqueos temporales» es `permanentLockout=true` con `maxTemporaryLockouts>0`. Con `false`, los bloqueos son solo temporales.
- Por eso el comentario de :76-77 («el 4.º bloqueo es permanente») es falso.
- Hay un segundo hueco: el «60 s ×2 hasta 900 s» (duplicar en cada serie) no se corresponde con ningún campo verificado. El diseño no dice qué campos de Keycloak lo implementan.
- Según la regla del usuario, el codificador debía detenerse (bitácora, Supuesto 3).

### F-02 · ROJO · realm_lint.py:365-388, tests/property/test_realm_ldap.py · `group-role-map.yaml` con formato inventado
- El formato `groups: {<grupo>: <rol>}` no aparece en el diseño (punto 2). U02-T04 quedaría atado a un formato que nadie aprobó.
- PBT-U2-02 prueba `resolve_ldap_role`. Ese modelo en Python no lo llama la CLI (`main`, `_lint_file`) ni lo usa Keycloak. Es decir, la propiedad verifica un modelo inventado y no el comportamiento real del mapeo LDAP.
- El diseño tampoco dice cómo produce Keycloak el «ningún rol + `ROLE_CONFLICT`» de BR-U2-01 (business-rules.md:15).
- Correspondía detenerse y reportarlo.

### F-03 · ROJO · realm_lint.py:44-62, 92, 236-237, 299-306; tests/strategies/realm_strategies.py:50-52 · Reglas sin respaldo en el diseño (desborde)
- **(a) Exención de 12 scopes propios de Keycloak.** La lista está escrita a mano. PBT-U2-03 (business-logic-model.md:71) y plan:94 dicen «ningún scope fuera del catálogo de U0 pasa». El generador filtra justo esos nombres (`realm_strategies.py:51`), así que la propiedad ya no es la del diseño. Consecuencias en mi sonda:
  - `offline_access`, `microprofile-jwt` (emite `upn`, el username), `phone` y `address` en `case-worker` → `[]`;
  - `verification-reader` con `offline_access` además de sus dos scopes → `[]`, aunque el plan pide «exactamente sus scopes» (plan:100);
  - un `offline_access` en un cliente de servicio choca además con BR-U2-06 («sin refresh»).
- **(b) `secret` en cualquier cliente.** BR-U2-09 lo limita a los de servicio.
- **(c) Comprobaciones no listadas en el Paso 3.** `acr.loa.map`, `revokeRefreshToken` y `refreshTokenMaxReuse`: los valores están en el diseño, pero el Paso 3 no pide verificarlos.

### F-04 · NARANJA · realm_lint.py:31-39, 154-168 · Las comprobaciones de usuario no siguen la representación real de Keycloak
- En Keycloak, `realm-admin` es un rol de cliente de `realm-management`, no un rol de realm. Sonda: `break-glass` con `clientRoles: {realm-management: [realm-admin]}` y sin TOTP en prod → `[]`. La regla de MFA de break-glass no lo detecta.
- Los usuarios de cuenta de servicio (`service-account-*`), que haría falta para el cliente de administración de INF-U2-05a (infrastructure-design.md:54), salen en prod como `usuario-local-en-prod`.
- Un cliente sin `defaultClientScopes` recibe de Keycloak los scopes por defecto del realm, incluidos `profile` y `email`, y el lint no lo detecta (sonda: `[]`).
- Las sondas no se pudieron contrastar con un Keycloak real (no hay clúster). Se basan en la representación conocida de Keycloak 26.

### F-05 · NARANJA · realm_lint.py:65, 67-70 · Literales que duplican el catálogo de U0
`FREEZE_ONLY_CLIENT` y `EXACT_SCOPES` repiten lo que ya está en `SCOPE_HOLDERS` (catalog.py:39, :49-50). Si el catálogo cambia, el lint se desincroniza sin avisar. La tarea pide que salgan del catálogo y no de listas a mano.

### F-06 · AMARILLO · test_realm_lint.py · Selección `-k cli` y aislamiento de una prueba
- `-k cli` arrastra 5 pruebas que no son de CLI («client» en el nombre). Las 7 de CLI son reales, con subproceso y lectura de la salida.
- `test_channel_simulator_in_prod_is_rejected` (:182) evalúa como prod el realm de kind, que también trae `verification-reader`. La prueba seguiría pasando aunque se quitara `channel-simulator` de la regla.

### Sin hallazgo
- `pyproject.toml`: `pyyaml==6.0.3`, la misma versión que ya estaba en el grupo dev, más `vectra-contracts` del workspace, con el mismo patrón que `vectra_common`. En `uv.lock` solo se agregan metadatos y `uv sync --frozen` pasa.
- `sys.path` del conftest: se justifica porque `tests/strategies` chocaría con el paquete `strategies` de `contracts/tests`.
- PBT-U2-01 corresponde a business-logic-model.md:69.
- PBT-U2-02 y 03: ver F-02 y F-03.

## Tareas candidatas (defectos reales fuera de alcance)
- Diseño: fijar el formato de `group-role-map.yaml` y el mecanismo de Keycloak para el `ROLE_CONFLICT` de BR-U2-01.
- Diseño: fijar a qué campos de Keycloak corresponde BR-U2-05, incluido el «×2», que Keycloak no ofrece de forma nativa según lo que conozco.
- Diseño: decidir si los scopes propios de Keycloak cuentan como «scopes» en PBT-U2-03.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r1/mutaciones.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r1/probe/probe.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/ca4.log`

VEREDICTO: NO-VERDE
ROJO|identity-edge/tools/realm_lint.py:89|permanentLockout=false exigido: nunca hay bloqueo permanente, contradice BR-U2-05
ROJO|identity-edge/tools/realm_lint.py:365|formato de group-role-map inventado; PBT-U2-02 prueba un modelo que no usa ni la CLI ni Keycloak
ROJO|identity-edge/tools/realm_lint.py:45|desborde: exención de scopes de Keycloak contra PBT-U2-03, secret en todo cliente, acr/refresh no pedidos
NARANJA|identity-edge/tools/realm_lint.py:31|realm-admin como rol de realm, service-accounts y scopes por defecto no siguen la representación de Keycloak
NARANJA|identity-edge/tools/realm_lint.py:65|FREEZE_ONLY_CLIENT y EXACT_SCOPES duplican SCOPE_HOLDERS del catálogo
AMARILLO|identity-edge/tests/unit/test_realm_lint.py:182|-k cli inflado por «client»; la prueba de channel-simulator en prod no aísla la regla
INFORME: revisiones/U02-T03/ronda-1.md
