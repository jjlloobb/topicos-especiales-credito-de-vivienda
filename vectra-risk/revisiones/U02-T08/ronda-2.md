# Ronda 2 — U02-T08

VEREDICTO: NO-VERDE

Revisé el sha `6e84d9b` sobre `b9577ff`. El diff de la ronda (`af19214..6e84d9b`) tiene tres commits:
- `1bf23af`: la enmienda S1/S2 del orquestador. Toca solo la tarea e INF-U2-09.
- `62282df`: el código.
- `6e84d9b`: la bitácora y la respuesta.

El hash de la tarea coincide (`853ddd14…`). Corrí todo en una copia nueva: `git archive 6e84d9b` más `.tools`, `.charts` y `.github`. Al terminar, el worktree del codificador sigue limpio.

Los 7 criterios pasan y F-01 a F-07 están corregidos. Queda un NARANJA: los roles de un usuario declarado se comparan solo en los campos que Git declara, así que dar `realm-admin` a `analista-1` en staging da 0.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 6 | `uv run pytest …test_realm_diff.py -q && HYPOTHESIS_PROFILE=ci uv run pytest …test_realm_normalize.py -q` | pasa: 190 passed (14,3 s) y 5 passed (26,3 s; cada propiedad tarda entre 2,9 y 9,9 s, no se saltaron) |
| 2 | Reglas de la proyección, con los casos nuevos de S1 y S2 | `uv run pytest identity-edge/tests/unit/test_realm_diff.py -q -rs` | pasa: 190 passed, 0 omitidas |
| 3 | Jobs contra Keycloak y Pushgateway falsos | `uv run pytest identity-edge/tests/unit/test_identity_jobs.py -q -rs` | pasa: 129 passed |
| 4 | Render y políticas | `make -C identity-edge render-jobs policy-jobs && uv run pytest …-k render` | pasa: conftest 555/555 y 5/5 ×3; pytest 98 passed. El nuevo render sale idéntico a `rendered/` |
| 5 | `keycloak-reader` con tres roles | `uv run python …realm_lint.py …realm.*.yaml && uv run pytest …test_realm_lint.py …test_realm_files.py -q` | pasa: 629 passed |
| 6 | Dockerfile y políticas de U1 | `platform/.tools/bin/hadolint … && make -C identity-edge policy-jobs-u1` | pasa: Kyverno `pass: 16, fail: 0` ×3; conftest 35/35 y 3/3 ×3 |
| 7 | Regresión | `uv sync --frozen --offline && make -C identity-edge check && make -C platform check-tools` | pasa: rc=0, 1487 passed, `check-tools` `pass: 239, fail: 0` |

En CA-7 agregué `--offline` porque no hay red.

## Sondas de la ronda 1, repetidas
| Sonda | R1 | R2 |
|---|---|---|
| Scope mapping por defecto de `offline_access` | 1 | **0** (corregido) |
| Flujo nuevo con `builtIn: true` | 0 | **1** (corregido) |
| Ejecución con `priority` repetida | 0 | **4**: 1 duplicado y 3 de valor (corregido) |
| `break-glass` tras enrolar TOTP | 2 | **0** (S1) |
| `redirectUri` de más en `vectra-console` | 0 | **1** (S2) |

Comprobé también: una clave repetida en Git da 1; `account-console` con un rol de más da 1; `offline_access` con `cro` da 1; un client scope con `realm-admin` en `realm-management` da 1. F-04: sin `defaultSignatureAlgorithm` el job falla y no empuja. F-05: queda una sola fuente para los roles por defecto.

## Hallazgos
### F-08 · NARANJA · identity-edge/tools/realm_diff.py:279-292 · Los roles de un usuario declarado solo se comparan en los campos que Git declara
INF-U2-09 enmendado (S1) dice: «Se siguen comparando la existencia del usuario, `enabled`, sus atributos y sus roles». Hoy `_compare` recorre solo las claves de Git. Además, `clientRoles` no está en `WILDCARD_PARENTS`, así que un contenedor de roles que Git no declara nunca se mira.

Sondas (`sondas.txt`):
- U-1, staging: `analista-1` recibe `realm-management: [realm-admin]` → **0**. Git no declara `clientRoles` para ese usuario.
- U-2, prod: `service-account-keycloak-reader` recibe el rol de realm `cro` → **0**. Git no declara `realmRoles` para esa cuenta.
- U-3, prod: la cuenta del reader recibe `broker: [read-token]` → **0**. Git declara `clientRoles` solo con el contenedor `realm-management`.

Es una escalada de privilegios sobre un usuario que Git sí declara, y `RealmDrift` no se entera. El código ya cuenta los contenedores de `clientScopeMappings` que Git no declara (líneas 289-291). La misma clase de caso pide que, en `users`:
- un `realmRoles` o `clientRoles` ausente en Git se lea como vacío, con la exención de `DEFAULT_LIST_ELEMENTS`;
- cada contenedor de roles de cliente que Git no declara cuente.

Hay que barrer los dos campos y los tres entornos. Si el orquestador decide que aquí manda la proyección sobre «sus roles», esto pasa a tarea candidata y deja de bloquear.

### F-09 · AMARILLO · realm_diff.py:269-272 y keycloak_admin.py:131-138 · El alias de la lista basta aunque Keycloak diga `builtIn: false`
Sonda D-7: un flujo propio llamado `docker auth`, con `builtIn: false` y ejecuciones arbitrarias, da **0**, y el lector ni siquiera pide sus ejecuciones. `test_f03_a_flow_of_the_list_is_zero_even_if_it_says_it_is_not_built_in` fija ese comportamiento como el deseado.

Hoy se explota solo si falta un alias de la lista, por ejemplo los flujos de Organization con esa función apagada, porque Keycloak no deja borrar un flujo propio. Exigir las dos condiciones (alias en la lista **y** `builtIn: true`) no abre ninguna vía, porque el flag ya no puede esconder nada por sí solo, y sí cierra esta.

### F-10 · AMARILLO · realm_diff.py:5-6, 24-25 · Comentarios desfasados
- El docstring todavía dice «Un campo de Git con un marcador `$(env:...)` se excluye», que es la regla anterior a S2.
- El comentario de `ENTITY_KEYS` todavía habla de credenciales y de «`priority` (única en un flujo)».

### F-11 · AMARILLO · realm_diff.py:172 · `service_account` exento en cualquier cliente
Sonda D-5: `service_account` en `defaultClientScopes` de `vectra-console`, que es un cliente público sin cuenta de servicio, da 0. La exención debería valer solo para clientes con `serviceAccountsEnabled`. El impacto es bajo: el scope solo agrega claims del cliente.

## Tareas candidatas (para el orquestador)
- **S2, lo permitido por diseño:** un marcador acepta cualquier valor resuelto. Sonda S2-b: `connectionUrl` del LDAP de prod pasa de `ldaps://$(env:LDAP_HOST):636` a `ldap://atacante:389` (sin TLS) y da 0. Se podría exigir que el valor resuelto conserve el texto literal que rodea al marcador (prefijo `ldaps://` y sufijo `:636`, sin expresiones regulares). Requiere una decisión de diseño.
- **La candidata de entidades propias ignoradas, ya en `CANDIDATAS.md`, es más grave de lo que se anotó.** Sonda D-8: `default-roles-vectra` con `realm-admin` como composite da 0. El lector usa `/roles` en forma breve y no lee los composites, así que ese cambio daría `realm-admin` a todos los usuarios, también a los de LDAP, sin deriva. Conviene priorizarla.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/logs2/ (ca1, ca3, ca4, ca5, ca6, ca7 y sondas.txt)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/sondas/sonda2.py

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/tools/realm_diff.py:279-292|Los roles de un usuario declarado solo se comparan en los campos que Git declara
INFORME: revisiones/U02-T08/ronda-2.md
```

VEREDICTO: NO-VERDE
