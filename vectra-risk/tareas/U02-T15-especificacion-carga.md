# U02-T15 — Especificación de la prueba de carga de U2

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601 y US-611, en su parte de capacidad (NFR-U2-10..12). La ejecución es del Paso 16.
**Depende de:** U02-T14 en `main`, por el backend de eco (J4). No se despacha antes.

Paso 14 del plan de U2. El 2026-11-05 el orquestador comparó el paso con el diseño y con el código. Esto es lo que encontró:

- kind tiene 10 usuarios, todos con TOTP que no se puede reutilizar y bloqueo permanente;
- `/auth/**` limita a 600/min por IP;
- NFR-U2-11 y NFR-U2-12 no se pueden expresar como `thresholds` de una sola corrida;
- la consola no tiene backend;
- k6 no está instalado.

El usuario decidió J1–J7. Están en la nota del Paso 14 del plan, en la enmienda de NFR-U2-12 y en la excepción de k6 del Infrastructure Design de U12.

## Alcance

**Dentro:** todo el Paso 14 del plan. Texto del plan, sin recortes:

- [ ] **Paso 14 — Especificación de la prueba de carga**
  - Script k6: 200 usuarios concurrentes con login y token, 10 identidades de servicio renovando cada 5 min (incluidas `case-worker` y `bias-monitoring-job`), ráfagas contra la consola; umbrales de NFR-U2-10..12 como `thresholds`.
  - Nota del 2026-11-05 (J1–J7).
  - Diseño: NFR-U2-10..12.
  - **Aceptación** (estática): `k6 inspect identity-edge/tests/load/identity.js` muestra los umbrales p95 de login (500 ms), token (200 ms) y JWKS (50 ms). La ejecución es del Paso 16.

Precisiones del diseño que la tarea aplica. La fuente de cada una va entre paréntesis.

- **k6** (J2). Se pinnea en `platform/tools.env` y `platform/install-tools.sh`, como binario con el SHA-256 de `k6-v<versión>-checksums.txt`. La versión debe tener al menos dos semanas de publicada. Queda en `platform/.tools/bin/k6`.
  - Comprueba con esa versión qué imprime `k6 inspect`: dónde salen los `thresholds` en el JSON y si ejecuta el init context. Regístralo en la bitácora.
- **Escenarios de `identity-edge/tests/load/identity.js`.**
  - `users`: 200 VUs. Cada uno hace el login del navegador de `vectra-console` (PKCE S256: GET de autorización, POST de la contraseña, canje del código) y renueva el token.
    - Los usuarios son `load-001..200` (J1).
    - Los logins se escalonan por debajo de 10/s, y un 429 cuenta como fallo, con `checks` y `http_req_failed` (J5).
  - `services`: los 10 clientes de servicio, cada uno pidiendo token por `client_credentials` con `private_key_jwt` ES256 cada 300 s.
    - La lista sale de los 14 clientes con service account de `realm.kind.yaml`, menos `keycloak-config-cli`, `keycloak-reader`, `verification-reader` y `channel-simulator`.
    - `case-worker` y `bias-monitoring-job` están en ella.
    - Las llaves PEM se leen de `K6_CLIENT_KEYS_DIR`, una por `clientId` (J6). La firma usa la WebCrypto de k6.
  - `jwks`: lecturas del JWKS del realm.
  - `console-burst`: ráfagas de un mismo usuario contra `/api/console/**`, que llegan al eco del Paso 13 (J4). Por encima del límite de la consola, 20/s por `sub` en `routes.yaml`, se espera 429 con `Retry-After: 1`, con `checks`.
  - `overhead`: el mismo request al eco, a través del gateway y directo (`K6_ECHO_DIRECT_URL`, port-forward del operador). El umbral de NFR-U2-11 se aplica a la diferencia de los p95, calculada en `handleSummary`, que termina con error si se excede (J3).
- **Umbrales.**
  - `http_req_duration{flow:login}` p95 < 500;
  - `http_req_duration{flow:token}` p95 < 200;
  - `http_req_duration{flow:jwks}` p95 < 50;
  - `http_req_failed` < 1 % (J7).

  Perfil: 2 min de subida y 15 min sostenidos (J7).
- **NFR-U2-12** (J3). En `identity-edge/tests/load/README.md` va la consulta PromQL del p95 que agrega el rate limit, con la métrica real de `envoy-ratelimit` de v1.9.3. La corre el operador durante la carga en el Paso 16, junto con la CPU de Valkey de NFR-U2-30.
- **Usuarios de carga** (J1). `identity-edge/tests/load/seed_users.py` crea y borra por la Admin API los 200 usuarios de kind: sin OTP y con un rol al que BR-U2-03 no exige MFA.
  - Confirma en el realm que ese rol puede hacer login en `vectra-console` sin TOTP. Si ningún rol puede, **detente y repórtalo**.
  - El script no corre en esta tarea: se prueba contra un doble de la Admin API, como `tests/strategies/fake_keycloak.py`.
- **`k6 inspect` sin entorno.** El init context no falla si faltan variables: usa valores por defecto que no sirven para ejecutar. La falta de una variable se comprueba en `setup()`, que es lo que corre en el Paso 16.
- **Makefile.** El target `load-inspect` corre `k6 inspect` y entra en `check`. El target `load` es la corrida del Paso 16 y no entra en `check`.

**Fuera:**
- Ejecutar la carga, crear usuarios en kind o leer llaves de Vault: es del Paso 16.
- El backend de eco: es de U02-T14. Si falta o no sirve para `overhead` o `console-burst`, detente y repórtalo.
- La imagen `grafana/k6` de U12: la regla de U12 no cambia (J2).
- Cambiar `routes.yaml` o los realms.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Pasos 13, 14 y 16)
- `aidlc-docs/construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-10..12 con su enmienda, NFR-U2-30)
- `aidlc-docs/construction/identity-edge/functional-design/business-rules.md` (BR-U2-03, BR-U2-05, BR-U2-08)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (llaves de cliente en Vault)
- `aidlc-docs/construction/system-verification/infrastructure-design/infrastructure-design.md` (regla de k6 y excepción J2)
- `identity-edge/gateway/routes.yaml` (límites), `identity-edge/gateway/values/kind.yaml` (host)
- `identity-edge/keycloak/realm/realm.kind.yaml` (clientes, `vectra-console`, roles y flujo de MFA)
- `identity-edge/tests/e2e/echo/` (de U02-T14), `identity-edge/tests/strategies/fake_keycloak.py`
- `platform/tools.env`, `platform/install-tools.sh`, `identity-edge/Makefile`

## Criterios de aceptación

Corre los comandos desde `vectra-risk/`.

- [ ] **CA-1** — k6 está pinneado.
  ```bash
  bash platform/install-tools.sh && platform/.tools/bin/k6 version
  ```
  Esperado: imprime la versión de `tools.env`. Con un SHA-256 alterado en una copia, `install-tools.sh` falla.
- [ ] **CA-2** — Es la aceptación del Paso 14: los umbrales, sin variables de entorno.
  ```bash
  env -i PATH="$PATH" platform/.tools/bin/k6 inspect identity-edge/tests/load/identity.js
  ```
  Esperado: termina en 0 y muestra los umbrales p95 de login (500), token (200) y JWKS (50), más `http_req_failed`.
- [ ] **CA-3** — El script corresponde al diseño.
  ```bash
  uv run pytest identity-edge/tests/unit/test_load_spec.py -q
  ```
  Esperado: pasa. La prueba corre `k6 inspect` y comprueba:
  - los umbrales, leídos de NFR-U2-10 y J7 en el diseño, no de literales;
  - los 5 escenarios, con 200 VUs en `users`;
  - el perfil de J7;
  - que los clientes de `services` sean exactamente los de la regla de J6, leídos del realm, con `case-worker` y `bias-monitoring-job`;
  - que la tasa de `console-burst` supere el límite de la consola de `routes.yaml`;
  - que los logins de `users` queden por debajo de 10/s.

  Cada comprobación falla en una copia mutada. Por ejemplo: umbral de 600, sin `case-worker`, 9 clientes, ráfaga por debajo del límite.
- [ ] **CA-4** — El script de usuarios de carga.
  ```bash
  uv run pytest identity-edge/tests/unit/test_load_seed_users.py -q
  ```
  Esperado: pasa contra el doble de la Admin API. Crea 200 usuarios con el rol sin MFA y sin OTP, es idempotente y los borra. Falla si en una copia se usa un rol de BR-U2-03.
- [ ] **CA-5** — U2 sigue cumpliendo, y `check` incluye `load-inspect`.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: todo pasa y termina en 0, sin pruebas omitidas.
- [ ] **CA-6** — U1 sigue cumpliendo con la herramienta nueva.
  ```bash
  make -C platform check-local
  ```
  Esperado: termina en 0. Corre CA-5 y CA-6 en serie.

## Plan de pruebas

**Rojo primero:** escribe `test_load_spec.py`, `test_load_seed_users.py` y el target `load-inspect` antes que el script. Registra en la bitácora que fallan porque `identity.js` y `seed_users.py` no existen.

## Notas

- Implementa lo que define el diseño enmendado. Detente y repórtalo, sin sustituirlo por otro mecanismo, si pasa algo de esto:
  - falta un dato;
  - la versión de k6 no expone los umbrales en `inspect`;
  - la WebCrypto de k6 no firma ES256.
- Ninguna prueba de pytest fija con un literal propio un valor que el diseño fija (umbrales, límites, clientes): lo lee del diseño o del modelo.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker.** El destino es un pull request, y lo fusiona una persona.
- La red solo se usa para `install-tools.sh`, `charts.sh` y `gh api` de lectura.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
