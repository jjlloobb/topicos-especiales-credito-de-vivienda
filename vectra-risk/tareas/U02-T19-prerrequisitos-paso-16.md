# U02-T19 — Requisitos del Paso 16: importación del realm en kind, secretos `identity/` y eco con 503

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601 y US-611, en su parte de instalación en kind. Ninguna historia nueva.
**Depende de:** U02-T18 (PR 82), ya en `main`.

Resuelve los bloqueos B-1, B-2 y B-4 de `identity-edge/docs/paso-16-kind.md` §1, que impiden ejecutar el Paso 16. Rige el ritmo RL-1 a RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6: máximo 2 rondas, y solo un ROJO bloquea.

**Nada de esta tarea toca el clúster** (AUTONOMIA-01). Todo se comprueba con renders, políticas y pruebas con dobles. El operador lo ejecuta en el Paso 16.

## Alcance

### B-1 — `keycloak-config-cli` y administrador de arranque, solo en kind

Decisión del usuario del 2026-11-08 (opción a). Está escrita en INF-U2-05a (`aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md`, «Excepción solo en kind») y en la nota del Paso 5 del plan.

1. **Administrador de arranque** en los values de Keycloak, **solo kind**:
   - variables `KC_BOOTSTRAP_ADMIN_USERNAME` y `KC_BOOTSTRAP_ADMIN_PASSWORD`, tomadas de un Secret `keycloak-bootstrap-admin`;
   - ese Secret lo crea un `ExternalSecret` desde la ruta `identity/keycloak-admin` de la bóveda (propiedades `username` y `password`);
   - con los values de staging y prod no se renderiza nada de esto.
2. **Job de `keycloak-config-cli` v6.5.1**, como hook `PostSync` de Argo CD sobre la Application `keycloak`, con `hook-delete-policy: BeforeHookCreation` (INF-U2-05a). **Solo kind.**
   - Imagen: la de `keycloak-config-cli` 6.5.1 compatible con Keycloak 26.8.1, fijada por digest. Antes de elegirla, comprueba en el repositorio o en el registro del proyecto qué tag corresponde a la línea 26 de Keycloak. Cita la fuente en la bitácora. Si no hay ninguna compatible con 26.x, **detente y repórtalo**. En kind se publica en `kind-registry:5000` (mirror); la guía del Paso 16 §3 suma esta imagen.
   - Entrada: `realm.kind.yaml`, del ConfigMap que ya renderiza `identity-edge/jobs/` o de uno propio, con la sustitución de variables activa (`IMPORT_VARSUBSTITUTION_ENABLED=true` o la opción que corresponda en 6.5.1; verifícalo).
   - Variables del contrato del realm (INF-U2-01): `PUBLIC_HOSTNAME`, cada `CLIENT_<ID>_JWKS` y cada `SYNTH_<USUARIO>_*`. Salen de `ExternalSecret`s sobre `identity/clients/<clientId>` (propiedad `jwks`) y `identity/synthetic-users`. El realm de kind también usa `$(env:NOMBRE)`: averigua qué es. Si es un error del realm, va a `CANDIDATAS.md` y no lo corriges aquí.
   - Conexión: a `https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth`, con la CA del Secret `identity-ca`.
   - Seguridad: `runAsNonRoot`, `readOnlyRootFilesystem`, recursos, prioridad, sidecar nativo de Linkerd y sin Secret plano. Las políticas de U1 y de U2 tienen que pasar.
   - El flujo de red de `keycloak-config-cli` hacia Keycloak (F94) ya existe en `platform/network/flows.yaml`. Verifica que cubre a este Job con sus etiquetas reales. Si no lo cubre, detente y repórtalo; no lo cambies.
3. **Renders y políticas.** Regenera `identity-edge/keycloak/rendered/` (y `jobs/rendered/` si lo usas). Agrega a `identity-edge/keycloak/policy/` las reglas `conftest` que exijan:
   - el Job y el administrador de arranque presentes en kind y **ausentes** en staging y prod;
   - el hook `PostSync` con `BeforeHookCreation`;
   - la imagen fijada por digest;
   - la sustitución de variables activa.

   Haz el rojo de cada regla.
4. **Diseño de Argo:** la Application `keycloak` sigue en la wave 3. El hook corre cuando la wave está sana.

### B-2 — Secretos `identity/` en la bóveda de kind

`platform/kind/seed-vault.sh` y `platform/kind/vault_paths.py` solo cubren `platform/secrets/`. Hay que extenderlos, sin romper lo que ya hacen, con un modo para U2: `seed-vault.sh identity`.

1. **Rutas:**
   - `vault_paths.py` también lee los `ExternalSecret` renderizados de U2: `identity-edge/keycloak/rendered/kind/`, `identity-edge/jobs/rendered/kind/`, `identity-edge/charts/valkey/rendered/kind/` e `identity-edge/ratelimit/external-secret.yaml`;
   - `uv run python platform/kind/vault_paths.py list` muestra las rutas `identity/…` y `edge/valkey`.
2. **Valores con forma real** (no al azar):
   - `identity/clients/<clientId>`: un par ES256 por cliente (los 14 con cuenta de servicio de `realm.kind.yaml`), con la propiedad `private-key` (PEM PKCS#8) solo para los clientes cuyo pod firma aserciones (INF-U2-01) y `jwks` (JWKS público) para todos;
   - `identity/ca`, propiedad `ca.crt`: el certificado público de `vectra-internal-ca`, leído del Secret de cert-manager en el clúster;
   - `identity/synthetic-users`: una propiedad por variable `SYNTH_<USUARIO>_PASSWORD` y `SYNTH_<USUARIO>_TOTP_SEED` (base32 válido para `pyotp`);
   - `identity/break-glass` (`BREAK_GLASS_PASSWORD`);
   - `identity/keycloak-admin` (`username` y `password`);
   - `edge/valkey` puede seguir al azar.
3. **Idempotencia:** igual que hoy, conserva lo que ya existe. **Nunca** regenera un par de llaves existente, porque rompería los tokens vigentes.
4. **Llaves para e2e:** el modo `identity` también escribe las llaves privadas y la CA en un directorio local fuera del repositorio (por omisión `${XDG_RUNTIME_DIR:-/tmp}/vectra-e2e-keys`, con permisos 0700/0600). Es el que usan `VECTRA_E2E_CLIENT_KEYS_DIR` y `K6_CLIENT_KEYS_DIR`. Al final imprime los `export` de `VECTRA_E2E_*` y `SYNTH_*`, sin valores secretos en el log: solo las rutas, o un archivo `env` con permisos 0600 en ese mismo directorio.
5. **Pruebas sin clúster:**
   - `platform/kind/tests/`, con un doble de `vault` y de `kubectl`;
   - el par ES256 se puede leer con `cryptography`, el JWKS valida contra él y el `kid` es estable;
   - una segunda corrida no cambia nada;
   - las semillas TOTP son base32 válido;
   - ningún secreto aparece en la salida estándar.

### B-4 — Eco con 503 para el ítem 8 (P-U2-02)

1. `identity-edge/tests/e2e/echo/server.py` agrega un modo que responde **503** y cuenta las llamadas por clave, por ejemplo un path o una cabecera de prueba solo de kind. El contador se puede leer por un endpoint del propio eco.
2. Hay un caso e2e nuevo en `identity-edge/tests/e2e/`, que solo se colecta: un `POST` por el gateway a una ruta que llega al eco en modo 503 → **exactamente 1** llamada al backend (sin reintento de Envoy, P-U2-02). Un `GET` idempotente puede reintentarse según P-U2-02; compruébalo en el diseño.
3. Los manifiestos del eco siguen validando en estático (H1).

### Comunes

- La guía `identity-edge/docs/paso-16-kind.md` se actualiza:
  - B-1, B-2 y B-4 pasan a «resueltos por U02-T19»;
  - §3 suma la imagen de `keycloak-config-cli`;
  - §4 usa el modo `identity` real;
  - §5 dice que la importación la hace el hook `PostSync`;
  - §6, ítem 8, usa el eco nuevo.
- **Plan:** la casilla del Paso 16 no se marca. Esta tarea solo prepara.

**Fuera:**
- Ejecutar nada contra el clúster.
- Staging y prod: siguen bloqueados.
- Las imágenes de U2 y sus digests (B-3) los resuelve el operador con un PR propio.
- La salud de U1 en kind (B-5).

## Archivos de contexto

- `identity-edge/docs/paso-16-kind.md` (bloqueos y pasos)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-01, 05a con la excepción de kind, 05b)
- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Pasos 5, 13 y 16)
- `aidlc-docs/construction/identity-edge/nfr-design/` (P-U2-02)
- `identity-edge/keycloak/` (values, policy, rendered, realm), `identity-edge/jobs/`, `identity-edge/tests/e2e/` (incluido `echo/`), `identity-edge/Makefile`
- `platform/kind/seed-vault.sh`, `platform/kind/vault_paths.py`, `platform/runbooks/install.md` §8
- `platform/network/flows.yaml` (F94)
- `CANDIDATAS.md`

## Criterios de aceptación

- [ ] **CA-1** — Renders y políticas de Keycloak con el Job y el administrador de arranque, solo en kind.
  ```bash
  make -C identity-edge check-keycloak-rendered policy-keycloak policy-keycloak-u1
  grep -c "keycloak-config-cli" identity-edge/keycloak/rendered/kind/*.yaml
  grep -c "KC_BOOTSTRAP_ADMIN" identity-edge/keycloak/rendered/staging/*.yaml identity-edge/keycloak/rendered/prod/*.yaml
  ```
  Esperado: el `make` da código 0. Kind tiene el Job con `argocd.argoproj.io/hook: PostSync`. Staging y prod dan 0 coincidencias. **Rojo primero:** con el Job en los values comunes, la política falla en staging y prod.

- [ ] **CA-2** — Rutas `identity/` en la lista de la bóveda.
  ```bash
  uv run python platform/kind/vault_paths.py list | grep -E "^identity/|^edge/valkey"
  ```
  Esperado: aparecen `identity/ca`, `identity/clients/<cada cliente>`, `identity/synthetic-users`, `identity/break-glass`, `identity/keycloak-admin` y `edge/valkey`.

- [ ] **CA-3** — El modo `identity`, probado con dobles.
  ```bash
  uv run pytest platform/kind/tests -v
  ```
  Esperado:
  - el par ES256 se puede leer y el JWKS valida;
  - la segunda corrida no cambia nada;
  - TOTP en base32;
  - sin secretos en la salida;
  - archivos con permisos 0600.

- [ ] **CA-4** — Eco con 503 y caso e2e.
  ```bash
  uv run pytest identity-edge/tests/unit -k echo -v && make -C identity-edge collect-e2e | grep -i "503\|single_call\|una_llamada"
  ```
  Esperado: el modo 503 y su contador probados en unidad, y el caso e2e nuevo en la colección.

- [ ] **CA-5** — `check` de U2 y de U1.
  ```bash
  make -C identity-edge check && make -C platform check
  ```
  Esperado: código 0 en los dos.

## Plan de pruebas

Rojo primero de:
- cada regla `conftest` nueva;
- la idempotencia del seed: una versión que regenera las llaves hace fallar la prueba;
- el modo 503: un eco sin el modo hace fallar el caso de unidad.

Registra todo en `bitacoras/U02-T19.md`.

## Notas

- Archivos que se modifican en su sitio:
  - `identity-edge/keycloak/values/{common,kind}.yaml` y `rendered/`;
  - `identity-edge/keycloak/policy/`;
  - `platform/kind/seed-vault.sh` y `vault_paths.py`;
  - `identity-edge/tests/e2e/echo/` y la guía del Paso 16.
- Hay dos codificadores en paralelo, en `decision-registry/` y `reference-model/`. No toques esos directorios.
