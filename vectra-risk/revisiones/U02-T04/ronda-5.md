# Ronda 5 — U02-T04

VEREDICTO: NO-VERDE

Queda un solo hallazgo en pie: la prueba de ES256 no lee de BR-U2-09 qué clientes cubre, como pedía el arbitraje. Dos mutaciones del diseño sobreviven. Todo lo demás está resuelto y verificado:
- los cuatro criterios pasan;
- las 7 mutaciones del barrido que sobrevivían en la ronda 4 mueren ahora, salvo las 2 que clasifiqué como «sin efecto» (b);
- el único cambio en los realms tiene respaldo en el diseño.

Comprobaciones previas:
- **Hash de la tarea:** `53b68973…9eba7`, coincide.
- **Worktree:** `wt-U02-T04` en `7a8c5cc`, con `git status --porcelain` vacío al empezar y al terminar.
- **Código revisado:** el commit `7a8c5cc`. Solo toca los 3 YAML (una línea en cada uno), `test_realm_files.py`, `design_values.py`, la bitácora y la respuesta, así que no hay desborde.
- **Entorno:** trabajé sobre una copia (`git archive 7a8c5cc`) con su propio venv y `UV_OFFLINE=1`. Al terminar borré la copia y el venv, y no queda ningún proceso.
- **Diseño de referencia:** juzgo contra el diseño enmendado en `88ea19c` (BR-U2-09 con G1 y G2, y la fila de `grafana` en §2.1).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | realm-lint de los 3 realms | `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml` | pasa (rc=0) |
| 2 | Lectura de vuelta contra el diseño | `uv run pytest identity-edge/tests/unit -q -k realm_files` | pasa (93 passed, 4,6 s), pero ver F-01 |
| 3 | Sin secretos en claro | `uv run pytest identity-edge/tests/unit -q -k realm_has_no_secret_values` | pasa (15 passed) |
| 4 | Lo anterior sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` (con pipefail) | pasa (rc=0, «All checks passed!», 622 passed) |

**Mutaciones.** Corrí 107: las 100 de la ronda 4 y 7 nuevas. La ida y vuelta YAML sin cambios da 93 passed. Todas se restauraron. Transcripción en `scratchpad/rev-u02t04-r5-scripts/mut.out`.
- **Las mutaciones previas que debían fallar, siguen fallando.**
- **Del barrido de la ronda 4, ahora fallan (1 failed cada una):**
  - `fullScopeAllowed: true` en `vectra-console`;
  - `operacion` en los `scopeMappings` de `vectra-console`;
  - `cro` en los de `promotion-tool`;
  - `include.in.token.scope: 'false'`;
  - `use.refresh.tokens: 'false'` en `vectra-console`.
- **Siguen sobreviviendo, y es correcto porque son de clase (b):** `analista` fuera de los `scopeMappings` de `grafana`, y `temporary: true` en la contraseña de `break-glass`.
- **Nuevas que fallan como deben:**
  - `token.endpoint.auth.signing.alg` en `vectra-console`, un cliente que BR-U2-09 no cubre;
  - `use.refresh.tokens: 'false'` en `grafana` y en `promotion-tool`;
  - `fullScopeAllowed: true` en `keycloak-reader`;
  - en el diseño, quitar la fila `cumplimiento` de §1.1 (6 failed).
- **Pasan, como debe ser:** `"counter":0`, y el mapper `amr` sin `id.token.claim`.
- **Sobreviven, y son la evidencia de F-01 (93 passed cada una):**
  - el diseño sin «y del cliente de usuario `grafana`» en BR-U2-09;
  - el diseño sin «incluidos `keycloak-config-cli` y `keycloak-reader` (INF-U2-05a)» en BR-U2-09.

## Estado de los hallazgos de la ronda 4
- **F-01 (ES256 en `grafana`):** el valor queda respaldado por G1 y G2 (business-rules.md:59 y domain-entities.md:68). La prueba, en cambio, no cumple el arbitraje: ver F-01 de esta ronda.
- **F-02 (valores con efecto sin lectura de vuelta):** resuelto. La nueva `test_realm_files_tokens_carry_only_what_the_design_allows` cubre los valores de clase (a):
  - `include.in.token.scope` (BR-U0-71);
  - `fullScopeAllowed` en todos los clientes (§1.3:52);
  - los `scopeMappings` de `vectra-console`, iguales a los roles de §1.1 sin `operacion`;
  - los `scopeMappings` de `promotion-tool`, iguales al rol de §2.1;
  - `use.refresh.tokens` en los clientes de usuario (BR-U2-06).
- **F-03 (listas repetidas a mano):** resuelto en la prueba de §1.0.

## El único cambio en los realms
`use.refresh.tokens: 'true'` en `grafana` (realm.prod.yaml:883, y lo mismo en kind y staging) tiene respaldo:
- Es el valor por defecto de Keycloak, así que no cambia el comportamiento.
- BR-U2-06 (business-rules.md:51) pide refresh con rotación en las sesiones de usuario, y `grafana` es un cliente de usuario (§2.1:68).

Es de clase (a) y (b). No encontré otros valores con efecto y sin respaldo: la clasificación de la ronda 4 sigue valiendo y no hay valores nuevos.

## Hallazgos
### F-01 · NARANJA · test_realm_files.py:119-133 (el conjunto `covered`) y :126 · Los clientes cubiertos por ES256 no se leen de BR-U2-09
El arbitraje pedía que «la prueba debe leer de BR-U2-09 los clientes cubiertos». La prueba arma el conjunto `covered` con tres fuentes:
- `design_clients(env)`, que viene de §2.2;
- `ADMIN_CLIENT_ROLES`, una constante escrita a mano en `realm_lint.py`;
- `private_key_jwt_user_clients()`, que busca el texto «private_key_jwt» en la columna de tipo de §2.1.

Ninguna de las tres es BR-U2-09. Después, la línea :126 lo comprueba contra un literal: `assert {"grafana", "keycloak-config-cli", "keycloak-reader"} <= covered`.

Prueba de que no está atada a BR-U2-09: quitar `grafana`, o quitar los dos clientes de administración, del texto de BR-U2-09 deja 93 passed. Si el diseño cambiara, la prueba no lo detectaría. Es el mismo tipo de defecto que F-06 y F-07 de la ronda 1.

El arreglo es parsear de BR-U2-09 los clientes que nombra (los ``…`` que siguen a «incluidos» y a «cliente de usuario») y unirlos con los de §2.2, sin la constante del lint ni el literal.

## Tareas candidatas (defectos reales fuera de alcance)
- La prueba de extremo a extremo en kind que lea el token real: `acr` y `amr` por rol, `break-glass` con MFA, `aud` por scope, el claim `scope`, aserciones ES256 desde `vectra_common.service_token`, y el login de Grafana y de `keycloak-config-cli` con su aserción ES256.
- `realm_lint.py` sigue con `REALM_PARAMETERS`, `MFA_REQUIRED_ROLES` y `ADMIN_CLIENT_ROLES` escritos a mano (U02-T03).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r5-scripts/mut.out` (mutaciones)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r5-scripts/ca4.out` (CA-4)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t04-r5-scripts/mut.py` (script)

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/tests/unit/test_realm_files.py:126|Los clientes ES256 no se leen de BR-U2-09 (literal y constante del lint); 2 mutaciones de diseño sobreviven
INFORME: revisiones/U02-T04/ronda-5.md
```
