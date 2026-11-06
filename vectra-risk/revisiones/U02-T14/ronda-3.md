# Ronda 3 — U02-T14

VEREDICTO: NO-VERDE

F-10 a F-13 quedan cerrados y no hay regresiones. Corrí CA-1 a CA-7 y pasan todos. La forma de la prueba nueva de F-10 bloquea el verde (NARANJA, F-14): copia los realms enteros, así que rompe `check` ante cualquier cambio futuro legítimo de un realm, y no fija contra el diseño el orden de los flujos, que es lo que hacía falta proteger.

Estado del worktree al terminar: limpio (`git status --short` vacío), HEAD en d6e1307. Las mutaciones las hice en una copia de `git archive` en el scratchpad. No queda ningún proceso mío en marcha.

## Criterios de aceptación, verificados por mí (desde `vectra-risk/`, sin `VECTRA_E2E_*` ni `SYNTH_*` en el entorno)
| # | Comando | Resultado |
|---|---|---|
| 1 | `uv sync --frozen && uv run ruff check identity-edge/tests/e2e` | pasa, exit 0 |
| 2 | `env -u VECTRA_E2E_BASE_URL uv run pytest identity-edge/tests/e2e --collect-only -q` | pasa: 26 casos, 0 errores |
| 3 | `uv run pytest identity-edge/tests/unit/test_e2e_inventory.py -q` | pasa, 6 |
| 4 | `uv run pytest identity-edge/tests/unit/test_e2e_echo.py -q` | pasa, 45 |
| 5 | `make -C identity-edge collect-e2e && make -C identity-edge check` | pasa, exit 0: 2511 casos en 918 s. Desde la orden `test --ignore=identity-edge/tests/e2e` no aparece ningún archivo de `tests/e2e` y no hay ningún «skip». Los únicos «Skipped» de todo el log son el `Skipped: 0` de kubeconform |
| 6 | `make -C platform check-local && uv run pytest contracts/tests -q`, en serie después de CA-5 | pasa, exit 0: platform 745 y contratos 502 |
| 7 | `realm_lint.py` sobre los 3 realms `&& pytest test_realm_lint test_realm_diff test_bruteforce_model -q` | pasa, 816 |

## Cierre de los hallazgos de la ronda 2
- **F-10, cerrado.**
  - `git diff 8c18021..d6e1307 -- …/keycloak/realm/ …/jobs/rendered/` cambia solo tres cosas, y lo hace igual en los 3 realms y en los 3 ConfigMaps:
    - `+bruteForceStrategy: LINEAR`;
    - `maxTemporaryLockouts` pasa de 3 a 15;
    - entra el bloque `UPDATE_PASSWORD` (prioridad 57) en `requiredActions`.
  - Volqué todos los flujos de `realm.kind.yaml`: `vectra-browser forms` vuelve a 10/20/30/40/50/60/70, con `vectra-mfa-cro` en el 3.er puesto, y cada `vectra-mfa-<rol>` termina en `factor` con 30.
  - La bitácora cuenta cómo se hizo el reemplazo y por qué no se repite.
- **F-11, cerrado.** Quité la guarda (`if previous is not None` en lugar de `if wait <= 0 and previous …`) y fallan los 3 casos de la prueba nueva. Restaurada, pasan 48.
- **F-12, cerrado.** `at = self.now()` se toma después de `attempt()`. El error que queda va en la dirección segura:
  - `quiet_until` y `locked_until` del modelo son mayores o iguales que los de Keycloak, así que esperar al modelo nunca provoca un fallo rápido que el modelo no prevea;
  - la frontera del fin del bloqueo sigue cubierta por `steady()` y `MARGIN_SECONDS`.
- **F-13, cerrado.** La cita ahora dice línea 123.

## Barrido del diff completo frente a 8c18021 (el patrón de F-10)
Revisé las partes que no son pruebas:
- `realm_lint.py`, `realm_builders.py` y `realm_exports.py`;
- `keycloak.rego`, `values/common.yaml` y `keycloak/rendered/*`;
- `business-rules.md` y `audit.md`;
- `Makefile`, `pyproject.toml`, los paquetes nuevos de `uv.lock` y `CANDIDATAS.md`.

Cada cambio sale de H3, H4, H10, H11 o H12, o de una candidata declarada. No encontré ningún otro cambio sin declarar.

## Hallazgos

### F-14 · NARANJA · `tests/unit/test_realm_files.py:646-664` + `tests/fixtures/realm-baseline-8c18021/` · La salvaguarda de F-10 es una foto de los realms enteros y deja una trampa de mantenimiento
- **Qué hace.** La línea base es una copia byte a byte de los 3 realms de 8c18021 (lo comprobé con `cmp`): 3944 líneas que duplican `keycloak/realm/`. La prueba exige `current == baseline` después de quitar los tres campos de esta tarea.
- **Detecta F-10.** Si cambio una sola `priority: 30` a 57 en `authenticationFlows`, falla 1 caso.
- **Rompe también lo legítimo.** Si cambio `accessTokenLifespan` de 300 a 240, que no tiene nada que ver con F-10, también falla 1 caso.
  - Los realms son artefactos vivos: «realm solo por PR» y futuras unidades de clientes. Cada PR futuro sobre un realm romperá `make check` en una prueba que se llama «8c18021».
  - El propio README prescribe «ampliar la lista de diferencias declaradas en esa prueba». La prueba se convertiría en un registro histórico de excepciones y la copia se iría quedando obsoleta.
- **Qué protege y qué no.** Protege «este diff no tocó nada más», que es trabajo de revisión (`git diff`), no un invariante del producto. Lo que F-10 rompió fue el orden de los subflujos de `vectra-browser forms`, y la prueba no lo fija contra ninguna fuente: si alguien regenera la línea base, el reordenamiento pasa.
- **Literales repetidos.** Repite `LINEAR`, 15 y 3, que ya fija `REALM_PARAMETERS` de `realm_lint`.
- **Arbitraje.** El arbitraje pedía una línea base «de `authenticationFlows`» o el modelo de flujos existente. La prueba va más allá de eso.

**Forma correcta que propongo:**
1. Borrar `realm-baseline-8c18021/` y la prueba.
2. Añadir a `test_realm_files.py` una prueba de invariantes de flujo:
   - En `vectra-browser forms`, las prioridades son estrictamente crecientes y siguen el orden declarado: `vectra-level-pwd` primero, luego los roles MFA en el orden fijado y `vectra-mfa-analista` al final. El orden se lee de una tupla de `realm_builders` (o del diseño de BR-U2-03, si lo fija), no de la foto.
   - Cada `vectra-mfa-<rol>` sigue la plantilla `conditional-level-of-authentication` < `conditional-user-role` (< `conditional-user-configured`) < `… factor`.
   - En cada flujo, las prioridades son únicas y crecientes.
3. Si se prefiere una foto, que sea solo de `authenticationFlows`, con un nombre que no dependa de un commit.

### F-15 · AMARILLO · `test_bruteforce_model.py`, prueba nueva de F-11 · Margen implícito
La prueba usa 2,0 s entre fallos y 0,1 s para el rápido, y depende de que `quickLoginCheckMilliSeconds` del realm esté entre 100 y 2000 ms. Conviene derivar ambos valores de `params.quick_login_check_milliseconds`.

## Tareas candidatas
- Ninguna nueva.

## Rutas de transcripciones
En `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/rev-t14-r3/`:
- `ca1.txt`, `ca2.txt`, `ca3.txt`, `ca4.txt`, `ca5.txt`, `ca6.txt` y `ca7.txt`;
- `copy/`, la copia donde hice las mutaciones.

No tengo Write, así que no escribí `revisiones/U02-T14/ronda-3.md`: este mensaje es el informe completo.

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/tests/unit/test_realm_files.py:646-664 y tests/fixtures/realm-baseline-8c18021/|La salvaguarda de F-10 copia los realms enteros: rompe ante cualquier cambio legítimo y no fija el orden de authenticationFlows contra el diseño
INFORME: revisiones/U02-T14/ronda-3.md
```
