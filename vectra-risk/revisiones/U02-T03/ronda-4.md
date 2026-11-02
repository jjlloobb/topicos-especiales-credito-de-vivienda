# Ronda 4 — U02-T03

VEREDICTO: NO-VERDE

Los cuatro criterios pasan con mi propia ejecución. Corrí 49 mutaciones (las 42 de antes más 7 de la regla nueva) y las pruebas detectan todas. Los nombres de cliente y de rol salen del diseño enmendado. Queda un NARANJA: en kind y staging, una cuenta de servicio con un rol de negocio deja de contar como cuenta de servicio, y con eso esquiva `rol-de-administracion-no-permitido`. Así, la cuenta de servicio de `case-worker` puede tener `realm-admin` sin que el lint falle, lo que contradice INF-U2-05a.

Sha `6e79aa1` sobre `22e80a1`; `d431310` es la enmienda. El commit del codificador (`6e79aa1`) solo toca la bitácora, la respuesta, `realm_builders.py`, `test_realm_lint.py` y `realm_lint.py`. Al final de la revisión el worktree sigue limpio (`git status` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`, `UV_OFFLINE=1`) | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 3 | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_*.py identity-edge/tests/unit/test_realm_lint.py -q` | pasa, 124 passed en 5,20 s. Las 8 propiedades corren 500 ejemplos cada una |
| 2 | Cada regla del Paso 2 con su caso que falla y su caso que pasa | `uv run pytest … -k "operacion or break_glass or verification_reader or product_metrics or channel_simulator or case_service"` | pasa, 20 passed |
| 3 | CLI como subproceso | `uv run pytest … -k cli` | pasa, 7 passed. Son solo las 7 pruebas de CLI |
| 4 | El esqueleto sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` | pasa, exit 0 (126 passed). `mypy --strict` no da errores |

**Mutaciones.** Las corrí en la copia `rev-u02t03-r4` y al terminar el `diff` contra HEAD sale vacío. Las 49 las detecta alguna prueba:
- las 42 de la ronda 3;
- A01, la regla apagada;
- A02, `allowed` amplio;
- A03, `keycloak-reader` con `realm-admin`;
- A04, `keycloak-config-cli` sin `realm-admin`;
- A05, `realm-admin` como rol de realm ignorado;
- A06, cualquier cliente con los roles de los dos de administración;
- A07, `keycloak-config-cli` con `manage-users`.

**Sondas.**
- Las de las rondas 1 a 3: correctas. Las tres de la ronda 3 dan ahora `rol-de-administracion-no-permitido`.
- Las variantes que pediste, en prod:
  - `keycloak-reader` con `realm-admin`: `rol-de-administracion-no-permitido`;
  - `keycloak-reader` con solo `view-realm`: `[]`;
  - `keycloak-reader` con `view-realm` y `manage-users`: `rol-de-administracion-no-permitido`;
  - `keycloak-config-cli` con `realm-admin`: `[]`;
  - `keycloak-config-cli` con `manage-users`: `rol-de-administracion-no-permitido`;
  - `case-worker` con `manage-users` y `manage-realm`: `rol-de-administracion-no-permitido`;
  - `scoring-service` con `realm-admin` como rol de realm: `rol-de-administracion-no-permitido`;
  - `keycloak-config-cli` con `realm-admin` y `cro`: `usuario-local-en-prod`.
- `keycloak-config-cli` con `realm-admin` como rol de realm da `[]`. Es aceptable: se trata del rol que el diseño le concede.

**Nombres y respaldo.** `keycloak-config-cli`, `keycloak-reader`, `realm-admin` y `view-realm` (realm_lint.py:42-47) salen de infrastructure-design.md:55-56 y domain-entities.md:20. La regla nueva tiene respaldo en infrastructure-design.md:57. No queda ninguna regla sin respaldo.

## Hallazgos
### F-01 · NARANJA · identity-edge/tools/realm_lint.py:129-137 y :151-165 · La regla de roles de administración se esquiva en kind y staging con un rol de negocio
`rol-de-administracion-no-permitido` solo se evalúa `if service_account`. Pero `_is_service_account` devuelve `False` cuando la cuenta tiene un rol de negocio u `operacion`, y entonces se trata como un usuario local cualquiera. En prod la atrapa `usuario-local-en-prod`. En kind y staging no la atrapa nada. Mis sondas sobre `realm.kind.yaml`, todas dan `[]`:
- la cuenta de servicio de `case-worker` (`serviceAccountClientId: case-worker`) con `realm-management: [realm-admin]`, `realmRoles: [cro]` y TOTP;
- la cuenta de servicio de `keycloak-config-cli` con `realm-admin` y `cro`.

Esto contradice:
- infrastructure-design.md:57: «`realm-lint` rechaza cualquier rol de `realm-management` en otra cuenta de servicio», sin limitarlo a prod;
- domain-entities.md:81: «Los clientes de servicio no tienen roles de usuario». Esa regla tampoco se comprueba fuera de prod.

El arreglo no necesita datos nuevos del diseño: identificar la cuenta de servicio solo por `serviceAccountClientId` → cliente con `serviceAccountsEnabled`, aplicar a toda cuenta así la regla de `realm-management`, y rechazar en cualquier entorno una cuenta de servicio con roles de usuario. Falta además una prueba en kind o staging para este caso: ninguna de las actuales lo cubre.

## Tareas candidatas (defectos reales fuera de alcance)
- Usuarios locales (no cuentas de servicio) con roles de `realm-management` en kind y staging: hoy pasan. Por ejemplo, `admin-1` con `realm-admin` y TOTP da `[]`. domain-entities.md:20 reserva `realm-admin` para `break-glass` y `keycloak-config-cli`, pero ni el Paso 3 ni INF-U2-05a piden que el lint lo verifique en usuarios locales. Es una decisión de diseño.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r4/mutaciones.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r4/probe/probe.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/ca4-r4.log`

NARANJA|identity-edge/tools/realm_lint.py:129|en kind y staging, una cuenta de servicio con un rol de negocio deja de ser cuenta de servicio y esquiva rol-de-administracion-no-permitido (case-worker con realm-admin y cro da [])
INFORME: revisiones/U02-T03/ronda-4.md
VEREDICTO: NO-VERDE
