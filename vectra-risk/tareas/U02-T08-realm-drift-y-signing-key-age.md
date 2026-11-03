# U02-T08 — `realm-drift` y `signing-key-age`

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601
**Depende de:** U02-T07 (despliegue de Keycloak, Secrets `keycloak-reader-client` e `identity-ca`), en `main`

Paso 6 del plan de U2. Al preparar la tarea (2026-11-03) el orquestador comprobó en el código de Keycloak 26.8.1 que `view-realm` no permite leer clientes, client scopes ni usuarios, y que `partial-export` exige `manage-realm`. Las decisiones R1–R4 del usuario fijaron:
- R1: los roles de `keycloak-reader` (INF-U2-05a);
- R2: la comparación por proyección sobre Git;
- R3: la imagen `identity-jobs` y el ConfigMap del realm;
- R4: la métrica de `signing-key-age`.

R2, R3 y R4 están en INF-U2-09, y P-U2-05 queda enmendado.

## Alcance

**Dentro:** todo el Paso 6 del plan. Texto del plan, sin recortes:

- [ ] **Paso 6 — `realm-drift` y `signing-key-age`**
  - CronJob diario que exporta el realm, lo normaliza (sin secretos, IDs internos ni timestamps) y lo compara con Git; empuja `vectra_realm_drift` al Pushgateway (F112, `PUT /metrics/job/realm-drift`; revisión de consistencia entre unidades, 2026-11-01), de donde sale `RealmDrift` (cuarta revisión de coherencia entre unidades, 2026-10-31).
  - CronJob horario `signing-key-age`: lee por F94 la llave de firma activa y empuja su antigüedad al Pushgateway (F112, `PUT /metrics/job/signing-key-age`; revisión de consistencia entre unidades, 2026-11-01) para `SigningKeyAgeHigh`. Sin Deployment ni scrape (seguimiento de la quinta revisión de coherencia, 2026-10-31).
  - **Enmienda del 2026-11-03 (decisiones R1–R4 del usuario al preparar U02-T08):** `keycloak-reader` necesita además `view-clients` y `view-users` para leer clientes, client scopes y usuarios, así que el paso amplía sus roles en los tres realms y la regla de `realm-lint` (INF-U2-05a). La comparación es una proyección sobre Git, la métrica de `signing-key-age` es `vectra_signing_key_created_timestamp_seconds`, y la imagen `identity-jobs` y el ConfigMap del realm están en INF-U2-09.
  - Diseño: BR-U2-12; P-U2-05; INF-U2-05a, 06, 09.
  - **Aceptación**: `uv run pytest identity-edge/tests/unit/test_realm_diff.py` y una propiedad: `normalize(normalize(x)) == normalize(x)`, y dos exportaciones que solo difieren en secretos o timestamps no generan diferencias.

Precisiones del diseño enmendado que la tarea aplica. Todas salen de INF-U2-09 salvo que se indique otra fuente.
- **Ubicación** (estructura de destino del plan):
  - normalización y comparación en `identity-edge/tools/realm_diff.py`;
  - los dos jobs, su `Dockerfile`, los values por entorno (`kind`, `staging`, `prod`) y `rendered/<env>/` en `identity-edge/jobs/`.
- **`keycloak-reader`** (INF-U2-05a):
  - en los tres realms, la cuenta `service-account-keycloak-reader` y el `clientScopeMappings` de `realm-management` para `keycloak-reader` tienen exactamente `view-realm`, `view-clients` y `view-users`;
  - `realm-lint` (`ADMIN_CLIENT_ROLES`) admite exactamente ese conjunto para `keycloak-reader` y sigue rechazando cualquier otro rol;
  - `keycloak-config-cli` no cambia.
- **Lectura por F94:**
  - token por `private_key_jwt` ES256 con `vectra_common.service_token` de U0 (`provider_from_env`), sin otro firmante;
  - llave del Secret `keycloak-reader-client` (propiedad `private-key`) y CA del Secret `identity-ca` (`ca.crt`), los dos ya creados por U02-T07;
  - API de administración en `https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/admin/realms/vectra`, y token en `https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra/protocol/openid-connect/token`.
- **Comparación de `realm-drift`:** proyección sobre Git.
  - Solo cuentan los campos que fija `realm.<env>.yaml`.
  - Las entidades se emparejan por su clave:
    - `clientId` para clientes;
    - `name` para client scopes, roles y componentes;
    - `alias` para flujos, acciones requeridas y configuración de autenticadores;
    - `username` para usuarios.
  - Cada entidad de Git que falta en Keycloak, y cada una de Keycloak que no está en Git, es una diferencia.
  - Los usuarios se leen uno a uno por su `username` de Git. Nunca se listan.
  - Un campo cuyo valor en Git contiene `$(env:…)` se excluye.
  - La normalización quita secretos, IDs internos y timestamps, y es idempotente.
  - `vectra_realm_drift` es el número de diferencias.
- **`signing-key-age`:**
  - empuja `vectra_signing_key_created_timestamp_seconds`, con etiquetas `kid` y `algorithm`;
  - el valor es el `notBefore` del certificado de la llave `ACTIVE` de uso `SIG` con mayor prioridad del algoritmo de firma por defecto del realm, leída en `GET /admin/realms/vectra/keys`;
  - si la llave no tiene certificado, el job falla.
- **Push** a `http://pushgateway.vectra-observability.svc:9091`, con `PUT /metrics/job/realm-drift` y `PUT /metrics/job/signing-key-age` (F112).
- **CronJobs:**
  - horarios en UTC: `realm-drift` a las `0 3 * * *` y `signing-key-age` a las `0 * * * *`, ambos con `concurrencyPolicy: Forbid`;
  - cuentas de servicio `realm-drift` y `signing-key-age` en `vectra-identity` (`platform/network/flows.yaml`);
  - prioridad `vectra-low` y recursos de INF-U2-06: requests 100m / 256 MiB, limits 500m / 512 MiB;
  - sidecar nativo de Linkerd, como los CronJobs de U1 (`add-native-sidecar-to-jobs`).
- **Imagen:**
  - repositorio `registro.banco.internal/vectra/identity-jobs` (`kind-registry:5000/vectra/identity-jobs` en kind), con el digest en los values de cada entorno. La plantilla falla si falta, y las pruebas usan un digest de ejemplo;
  - `identity-edge/jobs/Dockerfile` sobre `docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159`, con los scripts de los dos jobs y `vectra_common`, y `USER` numérico distinto de root.
- **Realm de Git:** el render genera un ConfigMap con el `realm.<env>.yaml` del entorno, sin tocarlo, y `realm-drift` lo lee montado.

**Fuera:**
- La `PrometheusRule` con `RealmDrift` y `SigningKeyAgeHigh` y los runbooks: Paso de observabilidad del plan.
- Las entradas de `vectra-risk-gitops/components.yaml`: Paso de integración del plan.
- Construir la imagen. Cualquier cosa contra un clúster.
- El Job de `keycloak-config-cli` (tarea propia, bloqueada).
- Cambios en `contracts/`, `platform/`, `.github/workflows/`, el tema y los values de Keycloak de U02-T07.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Paso 6 y estructura de destino)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-01, 05a, 06, 09)
- `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-05)
- `aidlc-docs/construction/identity-edge/functional-design/business-rules.md` (BR-U2-09, BR-U2-12)
- `aidlc-docs/construction/identity-edge/functional-design/domain-entities.md` (§1.1, roles técnicos)
- `contracts/python/vectra_common/src/vectra_common/service_token.py`
- `identity-edge/tools/realm_lint.py`, `identity-edge/keycloak/realm/`, `identity-edge/keycloak/` (render y políticas de U02-T07, como modelo)
- `platform/network/flows.yaml`, `platform/policies/`, `platform/observability/grafana/` y `platform/restore-drill/` (CronJobs de U1 que empujan al Pushgateway)

## Criterios de aceptación

- [ ] **CA-1** — Aceptación del Paso 6.
  ```bash
  uv run pytest identity-edge/tests/unit/test_realm_diff.py -q && HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_normalize.py -q
  ```
  Esperado: pasa. Las propiedades corren con el perfil `ci` y comprueban:
  - `normalize(normalize(x)) == normalize(x)`;
  - dos exportaciones que solo difieren en secretos, IDs internos o timestamps dan 0 diferencias.
- [ ] **CA-2** — Reglas de la proyección. Cada una tiene un caso que pasa y uno que falla en `test_realm_diff.py`, con el realm de Git de los tres entornos:
  - un valor por defecto que no está en Git da 0;
  - un campo de Git con otro valor da 1;
  - un cliente, un client scope, un rol, un flujo o un usuario de Git que falta da 1 cada uno;
  - un cliente, un client scope, un rol o un flujo que sobra en Keycloak da 1 cada uno;
  - un campo con `$(env:…)` en Git y cualquier valor en Keycloak da 0;
  - el orden distinto de una lista de entidades da 0;
  - un secreto (por ejemplo, `secret` de un cliente o el valor de una credencial) distinto da 0.

  El número que se empuja como `vectra_realm_drift` es el total.
  ```bash
  uv run pytest identity-edge/tests/unit/test_realm_diff.py -q
  ```
  Esperado: pasa.
- [ ] **CA-3** — Los jobs contra un Keycloak y un Pushgateway falsos, sin red. Lectura de vuelta en `test_identity_jobs.py`:
  - `realm-drift` pide el token con una aserción ES256 de `vectra_common.service_token` cuyo `iss`/`sub` es `keycloak-reader`;
  - lee los usuarios uno a uno por `username` y nunca lista `/users` sin filtro;
  - hace `PUT /metrics/job/realm-drift` con `vectra_realm_drift`;
  - `signing-key-age` elige la llave correcta entre varias (una `PASSIVE`, otra de uso `ENC`, otra de otro algoritmo y otra de menor prioridad) y empuja su `notBefore` en `vectra_signing_key_created_timestamp_seconds{kid,algorithm}` con `PUT /metrics/job/signing-key-age`;
  - sin certificado, el job termina con código distinto de 0 y no empuja nada.
  ```bash
  uv run pytest identity-edge/tests/unit/test_identity_jobs.py -q
  ```
  Esperado: pasa.
- [ ] **CA-4** — Manifiestos de los dos CronJobs en los tres entornos. El render de `identity-edge/jobs/` y sus políticas, con objetivos nuevos `render-jobs` y `policy-jobs` en el `Makefile` de `identity-edge`, comprueban:
  - el conjunto exacto de documentos, cada uno comparado completo (lección de U02-T07);
  - horarios, `concurrencyPolicy`, cuentas de servicio, prioridad, recursos, imagen del repositorio con digest, URLs, Secrets montados y el ConfigMap del realm del entorno idéntico a `realm.<env>.yaml`;
  - ningún `Secret` plano.

  Los valores que fija el diseño se leen del diseño, y los que solo fija el chart se comparan con el render versionado. Otra prueba comprueba que el render de cada entorno falla sin digest.
  ```bash
  make -C identity-edge render-jobs policy-jobs && uv run pytest identity-edge/tests/unit/test_identity_jobs.py -q -k render
  ```
  Esperado: pasa, y cada regla tiene un caso que falla sobre un render alterado.
- [ ] **CA-5** — `keycloak-reader` con sus tres roles.
  - `realm-lint` acepta los tres realms con `view-realm`, `view-clients` y `view-users`;
  - rechaza cualquier rol de más, por ejemplo `manage-users`, `realm-admin` o `view-events`;
  - en kind, staging y prod, la cuenta de servicio y el `clientScopeMappings` tienen exactamente ese conjunto.
  ```bash
  uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml && uv run pytest identity-edge/tests/unit/test_realm_lint.py identity-edge/tests/unit/test_realm_files.py -q
  ```
  Esperado: pasa.
- [ ] **CA-6** — El `Dockerfile` de los jobs y las políticas de U1.
  ```bash
  platform/.tools/bin/hadolint identity-edge/jobs/Dockerfile && make -C identity-edge policy-jobs-u1
  ```
  Esperado: sin hallazgos. `policy-jobs-u1` aplica a `rendered/<env>/` las políticas de Kyverno y Rego de U1 que alcanzan a `vectra-identity`, y evalúa reglas: en U02-T07, `kyverno apply` sobre un directorio aplicaba 0 reglas. Si una política de U1 exige algo que el diseño de U2 no fija, detente y repórtalo.
- [ ] **CA-7** — Lo anterior sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check && make -C platform check-tools
  ```
  Esperado: todo pasa y termina en 0. `check` incluye `render-jobs` (el render coincide con `rendered/`), `policy-jobs` y `policy-jobs-u1`.

## Plan de pruebas

**Rojo primero:** escribe `test_realm_diff.py`, `test_realm_normalize.py` y `test_identity_jobs.py`, y registra en la bitácora que fallan antes de escribir `realm_diff.py`, los jobs y los values.

## Notas

- Implementa lo que define el diseño enmendado. Si falta un dato, detente y repórtalo.
- Las clases de entidades y los campos de secreto, ID y timestamp se definen por listas exactas en el código. No uses expresiones regulares sobre el texto. Las listas se leen del diseño cuando el diseño las fija.
- `identity-edge/jobs/rendered/` es salida generada. Versiónala como `identity-edge/keycloak/rendered/`.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker** (el proyecto los deniega por configuración). El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
