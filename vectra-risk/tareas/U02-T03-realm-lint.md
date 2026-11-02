# U02-T03 — `realm-lint` y sus pruebas

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601
**Depende de:** U02-T02 (esqueleto), en `main`

Paso 3 del plan de U2. Se despacha antes que el Paso 2 (`U02-T04`) porque la aceptación del Paso 2 es correr `realm_lint.py`. El contenido de los dos pasos es el del plan, sin cambios; solo cambia el orden de despacho (decisión del orquestador, 2026-11-02).

## Alcance

**Dentro:** todo el Paso 3 del plan y las reglas de `realm-lint` que fija el Paso 2. Texto del plan, sin recortes:

- [ ] **Paso 3 — `realm-lint` y sus pruebas**
  - El validador verifica:
    - separación de funciones (BR-U2-01) y mapeo de grupos LDAP (BR-U2-15);
    - scopes solo del catálogo de U0 y **ningún cliente con `core:write-credit`**;
    - `governance:freeze` **solo** en `bias-monitoring-job` (revisión del FD de U9, 2026-10-08);
    - en `realm.prod.yaml`: ni `channel-simulator`, ni `case-service` con `core:read-credit` o la audiencia `core-banking-mock` (U8 INF-U8-02; precisado el 2026-10-08);
    - clientes de servicio sin `client_secret` y sin redirect URIs con comodines;
    - claims prohibidos en el access token;
    - parámetros de §6 de domain-entities y política de contraseñas;
    - (pendientes posteriores al cierre, 2026-10-10) `verification-reader` y los usuarios sintéticos solo en kind y staging; `product-metrics` y `verification-reader` con exactamente sus scopes; el rol técnico `operacion` con MFA obligatorio y nunca junto a un rol de negocio.
  - **Casos nombrados nuevos** de `tests/unit/test_realm_lint.py` (pendientes posteriores al cierre, 2026-10-10):
    - `verification-reader` en `realm.prod.yaml` → error; con un scope distinto de `registry:read:metrics` y `registry:read:monitoring` (por ejemplo `registry:append:case`) → error; en `realm.kind.yaml` con sus dos scopes → válido;
    - `product-metrics` con un scope además de `registry:read:metrics` → error; con solo ese scope → válido;
    - un usuario con `operacion` sin la acción requerida de TOTP (MFA no obligatorio) → error; `operacion` junto a `cro` → error; `operacion-1` con TOTP obligatorio → válido.
  - Propiedades PBT-U2-01, 02 y 03, con generadores en `tests/strategies/`.
  - Diseño: BR-U2-01, 09, 15; NFR-U2-40; AUTONOMIA-03. Historia: US-601 (su verificación pide la prueba del realm exportado: MFA por rol y fuerza bruta).
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_*.py identity-edge/tests/unit/test_realm_lint.py`, con casos nombrados: un usuario con dos roles → error; un cliente con `core:write-credit` → error; un cliente distinto de `bias-monitoring-job` con `governance:freeze` → error; `case-service` con `core:read-credit` en `realm.prod.yaml` → error; el mismo cliente en `realm.staging.yaml` → aceptado.

Reglas de `realm-lint` que fija el Paso 2 (citadas del plan):
- `realm-lint` rechaza `operacion` junto a un rol de negocio;
- `realm-lint` falla si `realm.prod.yaml` tiene algún usuario local distinto de `break-glass`, con un caso de prueba que agrega `cro-1` al realm de producción;
- `realm-lint` falla si `verification-reader` aparece en `realm.prod.yaml` o con otro scope;
- `realm-lint` falla si `product-metrics` tiene otro scope;
- `realm-lint` falla si `channel-simulator` aparece en `realm.prod.yaml`;
- `realm-lint` falla si `case-service` tiene `core:read-credit` o la audiencia `core-banking-mock` en `realm.prod.yaml`.

**Fuera:**
- Los archivos `realm.{kind,staging,prod}.yaml` reales y `group-role-map.yaml` (Paso 2, `U02-T04`). Las pruebas usan realms de ejemplo propios, bajo `identity-edge/tests/`.
- Tema, imagen y despliegue de Keycloak (Pasos 4 y 5), `realm-drift` (Paso 6).
- Cambios en `contracts/`, `platform/` y `.github/workflows/`.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Pasos 2 y 3)
- `aidlc-docs/construction/identity-edge/functional-design/` (`business-rules.md`: BR-U2-01, 09, 15; `domain-entities.md`: §1, §2, §3 y §6)
- `aidlc-docs/construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-40) y `tech-stack-decisions.md`
- `contracts/` (catálogo de scopes de U0: los scopes válidos salen de ahí, no de una lista escrita a mano)
- `identity-edge/` (esqueleto de U02-T01 y U02-T02)

## Criterios de aceptación

- [ ] **CA-1** — La aceptación del Paso 3, con sus casos nombrados.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_*.py identity-edge/tests/unit/test_realm_lint.py -q
  ```
  Esperado: todo pasa. Los casos nombrados del plan existen como pruebas propias (un nombre de prueba por caso) y las propiedades PBT-U2-01, 02 y 03 usan generadores en `identity-edge/tests/strategies/`.
- [ ] **CA-2** — Cada regla de `realm-lint` que fija el Paso 2 tiene su caso que falla y su caso que pasa.
  ```bash
  uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k "operacion or break_glass or verification_reader or product_metrics or channel_simulator or case_service"
  ```
  Esperado: pasa, con al menos un caso de error y uno válido por regla.
- [ ] **CA-3** — `realm_lint.py` se usa como en el Paso 2: recibe rutas y termina en 0 o distinto de 0, con el archivo y la regla incumplida en el mensaje. Lectura de vuelta: una prueba lo corre como subproceso sobre un realm de ejemplo válido (código 0) y otro inválido (código distinto de 0, con la regla en la salida).
  ```bash
  uv run pytest identity-edge/tests/unit/test_realm_lint.py -q -k cli
  ```
  Esperado: pasa.
- [ ] **CA-4** — El esqueleto sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: termina en 0.

## Plan de pruebas

**Rojo primero:** escribe los casos nombrados antes que el validador y registra que fallan.

## Notas

- Implementa lo que define el plan y el diseño de la unidad. Si la tarea, el plan y el diseño no coinciden, detente y repórtalo.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker** (el proyecto los deniega por configuración). El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red; si una dependencia nueva la necesita, empuja de vuelta.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
