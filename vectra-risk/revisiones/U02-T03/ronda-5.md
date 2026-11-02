# Ronda 5 — U02-T03

VEREDICTO: VERDE

Juzgo contra la tarea enmendada en `871c385`; `git hash-object` da `901c24b231c8efd546070d7f26a67ea45dcfda3f`, como se esperaba. El sha revisado es `c5dec69`, sobre `83412d8`. Al final de la revisión el worktree sigue limpio: `git status` sale vacío.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`, `UV_OFFLINE=1`) | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 3 | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_*.py identity-edge/tests/unit/test_realm_lint.py -q` | pasa, 179 passed en 5,17 s; las 8 propiedades corren 500 ejemplos cada una |
| 2 | Reglas del Paso 2, cada una con un caso que falla y uno que pasa | `uv run pytest … -k "operacion or break_glass or verification_reader or product_metrics or channel_simulator or case_service"` | pasa, 23 passed |
| 3 | CLI por subproceso | `uv run pytest … -k cli` | pasa, 7 passed; son solo las 7 pruebas de CLI |
| 4 | El esqueleto sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` | pasa, exit 0, 181 passed; `mypy --strict` sin errores |
| 5 | Cuentas de servicio en kind, staging y prod | `uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k service_account` | pasa, 72 passed |

**Los 72 casos de `-k service_account` son reales, no están inflados por el nombre.** Son 14 pruebas, todas parametrizadas por `ENVS = ["kind", "staging", "prod"]` (test_realm_lint.py:260-386), así que hay 24 casos por entorno. Cada una afirma la regla concreta que prueba:
- Regla 1, qué cuenta como cuenta de servicio (:280-307). Pasa: una cuenta real de `case-worker` da `[]`. Fallan los tres casos donde un usuario con `cro` no es cuenta de servicio y por eso cae en `mfa-obligatorio`, y además en `usuario-local-en-prod` solo en prod:
  - solo el prefijo `service-account-`;
  - un cliente inexistente;
  - un cliente que no es de servicio (`vectra-console`).
- Regla 2, ningún rol de usuario (:313-325). Fallan los 5 roles (4 de negocio y `operacion`) con `cuenta-de-servicio-con-rol-de-usuario`; sin roles, pasa.
- Regla 3, solo las dos cuentas de administración tienen roles de `realm-management` (:331-386).
  - Pasan `keycloak-config-cli` con `realm-admin` y `keycloak-reader` con `view-realm`.
  - Fallan con `rol-de-administracion-no-permitido`:
    - `keycloak-reader` con cualquiera de 4 roles de más;
    - `keycloak-config-cli` con `manage-users`;
    - `case-worker` con 4 roles de `realm-management`;
    - `scoring-service` con `realm-admin` como rol de realm.
  - El caso exacto de la ronda 4 está en los tres entornos: `case-worker` con `realm-admin` y `cro` dispara las dos reglas.

**Mutaciones: 55, y todas las detecta al menos una prueba.** Las corrí en una copia (`rev-u02t03-r5`); al terminar, el `diff` contra HEAD sale vacío.
- Son las 47 de la ronda 4 que siguen aplicando: N11 y N12 cambian de texto porque `_is_service_account` se reescribió.
- Más estas 8 nuevas:
  - N11: no comprobar el cliente;
  - N12: exigir además que no haya rol de negocio;
  - C01: regla de rol de usuario apagada;
  - C02: `operacion` fuera de los roles de usuario;
  - C03: regla de administración solo en prod;
  - C04: regla de rol de usuario solo en prod;
  - C05: cuenta de servicio por el prefijo del nombre;
  - C06: regla de administración apagada en kind.

**Sondas de las rondas 1 a 4, en los tres entornos.** Todas dan lo esperado:
- scopes propios de Keycloak: `scope-fuera-del-catalogo`;
- `permanentLockout=False`: `parametro-del-realm`;
- sin `optionalClientScopes`: `scopes-por-defecto-heredados`;
- prefijo solo o cliente inexistente: `mfa-obligatorio`, y además `usuario-local-en-prod` en prod;
- `case-worker` o `scoring-service` con roles de `realm-management`: `rol-de-administracion-no-permitido`;
- `keycloak-reader` con `realm-admin`: `rol-de-administracion-no-permitido`;
- `keycloak-reader` con `view-realm` y `keycloak-config-cli` con `realm-admin`: `[]`;
- cualquier cuenta de servicio con `cro` u `operacion`: `cuenta-de-servicio-con-rol-de-usuario`.

**Respaldo en el diseño:** las tres reglas del CA-5 se apoyan en domain-entities.md:81 e infrastructure-design.md:55-57. Los nombres de cliente y de rol salen de ahí. No queda ninguna regla sin respaldo.

## Hallazgos
Ninguno ROJO, NARANJA ni AMARILLO.

## Tareas candidatas (defectos reales fuera de alcance)
- Usuarios locales con roles de `realm-management` en kind y staging. Quedaron fuera por decisión del usuario. Ejemplos que hoy dan `[]` en kind y staging:
  - `admin-1` con `realm-admin` y TOTP;
  - un usuario cuyo `serviceAccountClientId` apunta a `vectra-console` (no es de servicio), con `realm-admin`.

  Según el CA-5 no son cuentas de servicio, así que caen en esta candidata. En prod los atrapa `usuario-local-en-prod`.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r5/mutaciones.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t03-r5/probe/probe.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/ca-r5.log`

INFORME: revisiones/U02-T03/ronda-5.md
VEREDICTO: VERDE
