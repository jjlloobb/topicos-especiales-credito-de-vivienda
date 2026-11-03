# U02-T07 — Despliegue de Keycloak

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601
**Depende de:** U02-T06 (imagen y tema), en `main`

Paso 5 del plan de U2, **sin el Job de `keycloak-config-cli`**. Al preparar la tarea (2026-11-03) el orquestador comprobó que ninguna versión publicada de `keycloak-config-cli` admite `private_key_jwt`. Por la decisión Q1 del usuario, el Job y su criterio salen a una tarea propia (plan e INF-U2-05a, enmendados). Las decisiones Q2–Q4 del usuario fijaron la referencia de la imagen y el chart (INF-U2-08), la fase `PostSync` del futuro hook (INF-U2-05a) y las claves de la bóveda (INF-U2-01).

## Alcance

**Dentro:** el Paso 5 del plan, salvo lo que su enmienda saca. Texto del plan, sin recortes:

- [ ] **Paso 5 — Despliegue de Keycloak y `keycloak-config-cli`**
  - Values de `keycloakx`:
    - 2 réplicas con HPA de 2 a 4, spread por zona y PDB;
    - `cache-stack` con `jdbc-ping`;
    - `hostname` y `hostname-admin`, `proxy-headers=xforwarded`;
    - puerto de gestión 9000;
    - recursos de INF-U2-06 y prioridad `vectra-high`;
    - Secrets por `ExternalSecret`, incluida la credencial de administración de INF-U2-05a (seguimiento de la quinta revisión de coherencia, 2026-10-31); la contraseña de la base `keycloak` es `pg-role-keycloak`, que U1 entrega en `vectra-identity` (revisión de consistencia entre unidades, 2026-11-01);
    - `Certificate` `keycloak-tls` para 8443 y `BackendTLSPolicy` de F05 con el certificado de la CA (INF-U2-05b; quinta revisión de coherencia entre unidades, 2026-10-31).
  - `keycloak-config-cli` como Job hook del sync.
  - **Enmienda del 2026-11-03 (decisión Q1 del usuario al preparar U02-T07):** el Job de `keycloak-config-cli` y el criterio «hook de sync presente» salen de este paso a una tarea propia, bloqueada hasta que exista un release de `keycloak-config-cli` con aserciones de cliente y el firmante esté diseñado (INF-U2-05a). El hook será `PostSync`. El resto del paso no cambia.
  - Diseño: NFR-U2-01, 02, 23, 26; P-U2-04; INF-U2-01, 05, 06. Historia: US-601.
  - **Aceptación**: `helm template` + `conftest test identity-edge/keycloak/` (réplicas, HPA, spread, PDB, `start --optimized`, `hostname-admin` interno, sin Secret plano, hook de sync presente, `keycloak-tls` y `BackendTLSPolicy` presentes).

Precisiones del diseño enmendado que la tarea aplica:
- **Chart:** `keycloakx` 7.4.0 de codecentric (INF-U2-08). Ya está descargado en `platform/.charts/keycloakx/keycloakx/`, enlace de solo lectura en tu worktree. Values en `identity-edge/keycloak/values/`: uno común y uno por entorno (`kind`, `staging`, `prod`).
- **Imagen:** `registro.banco.internal/vectra/keycloak` (`kind-registry:5000/vectra/keycloak` en kind), con el digest en los values de cada entorno. La plantilla falla si falta el digest. Las pruebas usan un digest de ejemplo (INF-U2-08).
- **Arranque y hostnames:**
  - Arranque `start --optimized` (NFR-U2-26).
  - `hostname`: el público de INF-U2-01 con el path `/auth`.
  - `hostname-admin`: `keycloak-admin.vectra-identity.svc.cluster.local`, con un Service de ese nombre. No va en el gateway.
- **Sesiones persistentes (NFR-U2-02):** en Keycloak 26.8.1 la función `persistent-user-sessions` está activa por defecto (`Profile.java`, tipo `DEFAULT`). No se desactiva, y `cache-stack` es `jdbc-ping`.
- **Base de datos:** el cluster `keycloak-db` de U1 (`platform/data/chart`), con la credencial del Secret `pg-role-keycloak` en `vectra-identity`, que ya entrega U1. No crees otro.
- **Bóveda:** `ExternalSecret` contra `ClusterSecretStore` `vectra-store`, con las claves `identity/…` de INF-U2-01.
  - Credencial de administración de INF-U2-05a: `identity/clients/keycloak-config-cli` y `identity/clients/keycloak-reader`, propiedad `private-key`.
  - CA: `identity/ca`, propiedad `ca.crt`.
- **TLS:**
  - `Certificate` `keycloak-tls`: SAN `keycloak.vectra-identity.svc`, 90 días con renovación a los 60. El `issuerRef` sale de los values de cada entorno: `vectra-internal-ca` (`ClusterIssuer`) en kind; en staging y prod se exige sin valor por defecto.
  - `BackendTLSPolicy` de F05: hacia el Service `keycloak`, puerto 8443, con `caCertificateRefs` a un Secret de la CA. Envoy Gateway v1.9.3 admite `Secret` (`internal/gatewayapi/backendtlspolicy.go` de ese tag).
- **Nombres de `platform/network/flows.yaml`:** Service y cuenta de servicio `keycloak` en `vectra-identity`. Puertos 8443 (F05/F50), 7800 (F117) y 9000 (F60).

**Fuera:**
- El Job de `keycloak-config-cli` y las variables del realm que consume (`SYNTH_*`, `BREAK_GLASS_PASSWORD`, `LDAP_*`, `CLIENT_<ID>_JWKS`). Van en la tarea separada.
- Las entradas de `vectra-risk-gitops/components.yaml` y sus values por entorno: Paso de integración del plan.
- Construir la imagen. Cualquier cosa contra un clúster.
- Cambios en `contracts/`, `platform/`, `.github/workflows/`, los realms y el tema.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Paso 5 y estructura de destino)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-01, 05, 05a, 05b, 06, 08)
- `aidlc-docs/construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-01, 02, 23, 26)
- `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-04)
- `aidlc-docs/construction/identity-edge/nfr-design/logical-components.md`
- `platform/network/flows.yaml`, `platform/data/chart/`, `platform/policies/` (políticas de U1 que los manifiestos deben cumplir)
- `platform/.charts/keycloakx/keycloakx/values.yaml`

## Criterios de aceptación

- [ ] **CA-1** — Aceptación del Paso 5: los manifiestos renderizados de los tres entornos cumplen las políticas de `identity-edge/keycloak/`.
  ```bash
  make -C identity-edge render-keycloak && platform/.tools/bin/conftest test --policy identity-edge/keycloak/policy identity-edge/keycloak/rendered/
  ```
  Esperado: pasa, con reglas para:
  - réplicas 2, HPA de 2 a 4 por CPU, spread por zona y PDB `minAvailable: 1`;
  - `start --optimized`, `cache-stack=jdbc-ping`, `proxy-headers=xforwarded`, `hostname` público con `/auth` y `hostname-admin` interno;
  - liveness y readiness en el puerto 9000;
  - recursos de INF-U2-06 y prioridad `vectra-high`;
  - ningún `Secret` plano: toda credencial llega por `ExternalSecret` o por el `pg-role-keycloak` de U1;
  - `keycloak-tls` y `BackendTLSPolicy` presentes;
  - imagen del repositorio de INF-U2-08 con digest;
  - `persistent-user-sessions` no desactivada.

  `render-keycloak` es un objetivo nuevo del `Makefile` de `identity-edge`: `helm template` con el chart de `platform/.charts`, los values comunes y los de cada entorno.
- [ ] **CA-2** — Lectura de vuelta de las reglas: cada regla de CA-1 tiene un caso que falla sobre un render alterado. Por ejemplo: 1 réplica, HPA máximo 5, sin spread, sin PDB, `start` sin `--optimized`, `hostname-admin` público, un `Secret` con `data`, sin `keycloak-tls`, sin `BackendTLSPolicy`, imagen sin digest y `--features-disabled=persistent-user-sessions`.
  ```bash
  uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q
  ```
  Esperado: pasa.
- [ ] **CA-3** — Los valores salen del diseño y no de constantes. Las pruebas leen de los documentos de diseño: recursos (INF-U2-06), hostnames (INF-U2-01), repositorio (INF-U2-08) y claves de la bóveda (INF-U2-01). Otra prueba comprueba que el render de staging y prod falla sin digest o sin `issuerRef`.
  ```bash
  uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q -k design
  ```
  Esperado: pasa.
- [ ] **CA-4** — Los manifiestos renderizados cumplen las políticas de U1 (Kyverno y Rego) que aplican a `vectra-identity`.
  ```bash
  platform/.tools/bin/kyverno apply platform/policies/kyverno --resource identity-edge/keycloak/rendered/prod/ && platform/.tools/bin/conftest test --policy platform/policies/rego identity-edge/keycloak/rendered/prod/
  ```
  Esperado: sin fallos. Si una política de U1 exige algo que el diseño de U2 no fija, detente y repórtalo.
- [ ] **CA-5** — Lo anterior sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check && make -C platform check-tools
  ```
  Esperado: todo pasa y termina en 0. `check` incluye `render-keycloak` y el `conftest` de CA-1.

## Plan de pruebas

**Rojo primero:** escribe las políticas y `test_keycloak_deploy.py`, y registra en la bitácora que fallan antes de escribir los values.

## Notas

- Implementa lo que define el diseño enmendado. Si falta un dato, detente y repórtalo.
- `identity-edge/keycloak/rendered/` es salida generada. Versiónala como hace U1 con `platform/rendered/`, y que `check` compruebe que coincide con el render.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker** (el proyecto los deniega por configuración). El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red: el chart ya está en `platform/.charts`.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
