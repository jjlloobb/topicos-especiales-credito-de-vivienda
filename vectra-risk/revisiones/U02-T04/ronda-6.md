# Ronda 6 — U02-T04

VEREDICTO: VERDE

El F-01 de la ronda 5 queda resuelto: la prueba de ES256 lee de BR-U2-09 los clientes cubiertos, sin la constante del lint ni el literal. Las dos mutaciones de diseño que sobrevivían ahora mueren, y también las dos nuevas que agregan un cliente al texto. Los cuatro criterios pasan. Las demás mutaciones no cambian de estado, y no queda ningún ROJO ni NARANJA en pie.

Comprobaciones previas:
- **Hash de la tarea:** `53b68973…9eba7`, coincide.
- **Worktree:** `wt-U02-T04` en `54bbda4`, con `git status --porcelain` vacío al empezar y al terminar.
- **Entorno:** trabajé sobre una copia (`git archive 54bbda4`) con su propio venv y `UV_OFFLINE=1`. Al terminar borré la copia y el venv, y no queda ningún proceso.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | realm-lint de los 3 realms | `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml` | pasa (rc=0) |
| 2 | Lectura de vuelta contra el diseño | `uv run pytest identity-edge/tests/unit -q -k realm_files` | pasa (93 passed, 4,6 s) |
| 3 | Sin secretos en claro | `uv run pytest identity-edge/tests/unit -q -k realm_has_no_secret_values` | pasa (15 passed) |
| 4 | Lo anterior sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` (con pipefail) | pasa (rc=0, «All checks passed!», 622 passed) |

## Alcance del cambio
El commit `54bbda4` solo toca:
- `design_values.py`: agrega `assertion_signing_extra_clients()`, que parsea la línea de BR-U2-09 tras «incluidos» y «cliente de usuario», y quita `private_key_jwt_user_clients()`;
- `test_realm_files.py` (:125-126): la cobertura pasa a ser `{*design_clients(env), *design.assertion_signing_extra_clients()}`, sin `ADMIN_CLIENT_ROLES` y sin el literal de tres nombres;
- la bitácora y la respuesta.

Los realms no cambian (`git diff 7a8c5cc 54bbda4 -- identity-edge/keycloak` vacío). `da429b6` es la entrada de auditoría del orquestador (`audit.md`). No hay nada fuera del hallazgo.

## Mutaciones
Corrí las 107 de la ronda 5 y 2 nuevas, todas restauradas. Comparé el estado de cada una (muere o sobrevive) con la transcripción de la ronda 5. Solo cambian, como se esperaba:
- quitar `grafana` del texto de BR-U2-09: antes sobrevivía, ahora **muere**;
- quitar los dos clientes de administración del texto de BR-U2-09: antes sobrevivía, ahora **muere**;
- **nueva:** agregar `vectra-console` a la lista de «incluidos» de BR-U2-09 **muere**;
- **nueva:** agregar `promotion-tool` como «cliente de usuario» en BR-U2-09 **muere**.

Las otras 105 quedan igual que en la ronda 5. Las que sobreviven son las esperadas:
- la ida y vuelta YAML sin cambios;
- `"counter":0` (lo admite E4);
- el mapper `amr` sin `id.token.claim`;
- ES256 en `case-service`, que ya es su valor;
- `analista` fuera de los `scopeMappings` de `grafana` y `temporary: true`, las dos de clase (b).

## Hallazgos
Ninguno en pie.

## Tareas candidatas (defectos reales fuera de alcance)
- La prueba de extremo a extremo en kind que lea el token real: `acr` y `amr` por rol, `break-glass` con MFA, `aud` por scope, el claim `scope`, aserciones ES256 desde `vectra_common.service_token`, y el login de Grafana y de `keycloak-config-cli` con su aserción ES256.
- `realm_lint.py` sigue con `REALM_PARAMETERS`, `MFA_REQUIRED_ROLES` y `ADMIN_CLIENT_ROLES` escritos a mano (U02-T03).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r6-scripts/mut.out` (mutaciones de esta ronda)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r6-scripts/mut.r5.out` (ronda 5, para comparar)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r6-scripts/ca4.out` (CA-4)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r6-scripts/mut.py` (script)

```
VEREDICTO: VERDE
INFORME: revisiones/U02-T04/ronda-6.md
```
