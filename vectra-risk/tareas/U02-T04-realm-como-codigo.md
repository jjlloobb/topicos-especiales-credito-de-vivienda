# U02-T04 — Realm como código

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601
**Depende de:** U02-T03 (`realm-lint`)

Paso 2 del plan de U2. Se despacha después del Paso 3 (`U02-T03`) porque su aceptación es correr `realm_lint.py`.

## Alcance

**Dentro:** todo el Paso 2 del plan. Texto del plan, sin recortes:

- [ ] **Paso 2 — Realm como código**
  - `realm.{env}.yaml`:
    - los 4 roles de negocio y el mapeo de ACR (`pwd` = 1, `mfa` = 2);
    - el flujo de login con OTP **condicional por rol** (obligatorio para `ingeniero_riesgo`, `cro` y `cumplimiento`) y TOTP como *required action*;
    - WebAuthn opcional;
    - fuerza bruta (BR-U2-05), vidas de tokens y sesiones con rotación de refresh (BR-U2-06) y política de contraseñas (NFR-U2-24); las sesiones persistentes son opción del servidor y pasan a los Pasos 4 y 5 (enmienda del 2026-11-02, decisión del usuario tras la ronda 1 de U02-T04);
    - eventos de login y de administración sin username ni email (BR-U2-16).
  - Clientes de domain-entities §2:
    - `vectra-console` y `promotion-tool` (PKCE S256, redirect URIs exactas; `vectra-console` con la de login y `/stepup-callback`, U10 BR-U10-06, revisión del FD de U10, 2026-10-10);
    - rol técnico `operacion` y el mapper de Grafana a roles y equipos (`cro`, `cumplimiento`, `operacion`; domain-entities §1.1 y §2.1); `realm-lint` rechaza `operacion` junto a un rol de negocio; usuarios `operacion-1` y `operacion-2` en kind y staging (segunda revisión del Infrastructure Design de U10, 2026-10-10);
    - `grafana` y los 10 de servicio con `private_key_jwt` (incluidos `case-worker`, agregado el 2026-10-08 por U8 INF-U8-01, y `bias-monitoring-job`, revisión del FD de U9, 2026-10-08); solo `bias-monitoring-job` tiene `governance:freeze`;
    - usuarios sintéticos de domain-entities §3 (`analista-1` y `-2`, `ingeniero-1` y `-2`, `cro-1` y `-2`, `cumplimiento-1` y `-2`), un rol cada uno, con contraseña y TOTP desde ESO, en `realm.kind.yaml` y `realm.staging.yaml`; `realm-lint` falla si `realm.prod.yaml` tiene algún usuario local distinto de `break-glass`, con un caso de prueba que agrega `cro-1` al realm de producción (revisión del Infrastructure Design de U10, 2026-10-10);
    - `verification-reader` (`private_key_jwt`) con **solo** `registry:read:metrics` y `registry:read:monitoring`, únicamente en `realm.kind.yaml` y `realm.staging.yaml`; `realm-lint` falla si aparece en `realm.prod.yaml` o con otro scope (Infrastructure Design de U12, 2026-10-10);
    - `product-metrics` (`private_key_jwt`) con **solo** `registry:read:metrics`; `realm-lint` falla si tiene otro scope (NFR-U11-20; NFR Requirements de U11, 2026-10-10);
    - `channel-simulator` (`private_key_jwt`, `intake:submit`, audiencia `case-service`) solo en `realm.kind.yaml` y `realm.staging.yaml`; `realm-lint` falla si aparece en `realm.prod.yaml` (precisado el 2026-10-06, revisión del FD de U8);
    - `case-service` con `core:read-credit` y la audiencia `core-banking-mock` solo en `realm.kind.yaml` y `realm.staging.yaml`; `realm-lint` falla si aparecen en `realm.prod.yaml`, y una prueba sobre el realm de producción comprueba que `case-service` no obtiene un token con ese scope ni con esa audiencia (precisado el 2026-10-08 por U8 INF-U8-02, core deshabilitado en producción);
    - clientes de administración de INF-U2-05a: `keycloak-config-cli` (cuenta de servicio con `realm-admin`) y `keycloak-reader` (cuenta de servicio con solo `view-realm`), ambos con `private_key_jwt` (enmienda del 2026-11-02, decisión del usuario tras la ronda 3 de U02-T03);
    - mapper de audiencias y mapper `roles`;
    - access token sin `preferred_username`, `email` ni `name`.
  - kind y staging: ≥ 2 usuarios sintéticos por rol. prod: federación LDAPS `READ_ONLY` (INF-U2-07) y el usuario `break-glass`. `group-role-map.yaml` y los mappers de grupo LDAP a rol pasan a una tarea propia, que se despacha cuando el banco dé los nombres de los grupos; hasta entonces, en prod los usuarios LDAP no reciben rol (enmienda del 2026-11-02, decisión del usuario tras la ronda 1 de U02-T04).
  - Diseño: BR-U2-01, 03..07, 09, 12, 15, 16; NFR-U2-24; INF-U2-07. Historia: US-601.
  - **Aceptación**: `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml` termina en 0 (Paso 3).

**Fuera:**
- Cambiar `realm-lint` (Paso 3, `U02-T03`). Si un realm correcto según el diseño no pasa el lint, empuja de vuelta con la evidencia.
- Tema, imagen, `values` y despliegue de Keycloak (Pasos 4 y 5).
- Secretos reales: las contraseñas y semillas TOTP de los usuarios sintéticos vienen de ESO; en los YAML van como referencias, nunca como valores.
- Cambios en `contracts/`, `platform/` y `.github/workflows/`.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Paso 2)
- `aidlc-docs/construction/identity-edge/functional-design/` (`business-rules.md`: BR-U2-01, 03..07, 09, 12, 15, 16; `domain-entities.md`: §1, §1.1, §2, §2.1, §3 y §6)
- `aidlc-docs/construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-24) e `infrastructure-design/infrastructure-design.md` (INF-U2-07)
- `contracts/` (catálogo de scopes de U0)
- `identity-edge/tools/realm_lint.py` (de U02-T03)

## Criterios de aceptación

- [ ] **CA-1** — La aceptación del Paso 2.
  ```bash
  uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml
  ```
  Esperado: termina en 0 con los tres realms.
- [ ] **CA-2** — Los realms contienen lo que pide el Paso 2. Lectura de vuelta: una prueba lee los tres YAML y comprueba, por entorno, los clientes, roles, usuarios y parámetros que el plan nombra (incluidos los que solo existen en kind y staging, y `break-glass` y la federación LDAPS solo en prod), contra los valores de domain-entities, no contra una lista nueva escrita a mano.
  ```bash
  uv run pytest identity-edge/tests/unit -q -k realm_files
  ```
  Esperado: pasa.
- [ ] **CA-3** — Sin secretos en claro.
  ```bash
  uv run pytest identity-edge/tests/unit -q -k realm_has_no_secret_values
  ```
  Esperado: pasa; la prueba falla si un YAML tiene una contraseña, un `secret` o una semilla TOTP literal.
- [ ] **CA-4** — Lo anterior sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: termina en 0.

## Plan de pruebas

**Rojo primero:** escribe las pruebas de CA-2 y CA-3 antes que los realms y registra que fallan.

## Notas

- Implementa lo que define el plan y el diseño de la unidad. Si la tarea, el plan y el diseño no coinciden, detente y repórtalo.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker** (el proyecto los deniega por configuración). El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
