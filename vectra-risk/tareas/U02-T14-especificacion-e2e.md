# U02-T14 — Especificación de las pruebas de extremo a extremo de U2

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601 (aprobador con MFA, fuerza bruta) y US-611 (cabeceras, 429, error genérico), en su especificación ejecutable. La ejecución es del Paso 16.
**Depende de:** ninguna tarea abierta. Se puede despachar en paralelo con U02-T13, porque no comparten archivos.

Paso 13 del plan de U2. El 2026-11-05 el orquestador comparó el paso con el diseño y con el código. Esto es lo que encontró:

- no hay backend de eco ni servicios destino en kind;
- el realm no tiene ningún aprobador sin TOTP;
- el gateway responde 403, no 401, a un token de otro servicio;
- `make check` ejecutaría las e2e sin clúster;
- faltan las dependencias de Playwright, pyotp y axe.

El usuario decidió H1–H9. Están en la nota del Paso 13 del plan.

## Alcance

**Dentro:** todo el Paso 13 del plan. Texto del plan, sin recortes:

- [ ] **Paso 13 — Especificación de las pruebas de extremo a extremo**
  - Playwright + `httpx` + `pyotp` + `axe-core`:
    - aprobador sin TOTP → no obtiene token;
    - step-up sin SPA: flujo OIDC con `acr_values=mfa` y TOTP hasta el token con `acr = mfa`; el diálogo en la consola se prueba en U10, que se construye después (seguimiento de la quinta revisión de coherencia, 2026-10-31). El comportamiento en ventana emergente que U10 debe cubrir no es de esta tarea;
    - 5 fallos → bloqueo, con el evento con `userId` y sin `username`;
    - refresh reusado → sesión revocada;
    - cabeceras (CSP, HSTS, `nosniff`, `DENY`, `Referrer-Policy`); la CSP de `spa` y `api` incluye `require-trusted-types-for 'script'` y `trusted-types 'none'` (NFR Requirements de U10, 2026-10-10, Q7);
    - 429 con `Retry-After`; cuerpo mayor que el límite → 413 `payload_too_large` (seguimiento de la quinta revisión de coherencia, 2026-10-31); `/auth/admin` → 404;
    - token de otro servicio → 401. **H2:** en el gateway se espera **403**; el 401 por audiencia es de U8;
    - `X-Forwarded-For` falso no cambia la IP registrada;
    - cabecera interna `x-vectra-sub` inyectada → sin efecto;
    - backend de eco: `Idempotency-Key` (en `/api/intake/**` y `/api/console/**`) y `X-Test-Scenario` (en `/api/intake/**`) llegan intactas, y ninguna `x-vectra-*` entrante llega (P-U2-06; precisado el 2026-10-06, revisión del FD de U8);
    - accesibilidad del login.
  - PBT-U2-08: modelo de estados de la fuerza bruta contra el Keycloak de kind.
  - Nota del 2026-11-05 (H1–H9).
  - Diseño: PBT-10; NFR-U2-42; BR-U2-03..08, 10, 13, 16; P-U2-06, 08. Historias: US-601, US-611.
  - **Aceptación** (estática): `uv run ruff check identity-edge/tests/e2e` y `uv run pytest identity-edge/tests/e2e --collect-only` lista todos los casos nombrados. La ejecución es del Paso 16.

Precisiones del diseño que la tarea aplica. La fuente de cada una va entre paréntesis.

- **Casos.** Cada viñeta del Paso 13 tiene al menos una prueba con un id estable. Los valores esperados se leen del diseño o del modelo, no de literales propios:
  - límites, `max_body`, `Retry-After` y perfiles de cabeceras: `identity-edge/gateway/routes.yaml`, con `tests/strategies/gateway_design.py`;
  - campos de la fuerza bruta y clientes: `identity-edge/keycloak/realm/realm.kind.yaml`, con `tests/strategies/realm_builders.py`;
  - host: `identity-edge/gateway/values/kind.yaml`.

  La accesibilidad cubre login, TOTP y cambio de contraseña con `axe-core`, sin violaciones `serious` ni `critical`. Además hay una prueba de que el tema no carga recursos de otro origen (P-U2-08).
- **Backend de eco** (H1). En `identity-edge/tests/e2e/echo/` van:
  - un servidor mínimo con la biblioteca estándar, que devuelve en el cuerpo las cabeceras y el tamaño recibidos;
  - su `Dockerfile`;
  - los manifiestos de kind: Deployment y Service para `console-spa` (`vectra-edge`) y para `console-bff`, `case-service` y `governance-service` (`vectra-app`), con el nombre, la SA, las etiquetas y el puerto que fijan `platform/network/flows.yaml` y `routes.yaml`.

  La imagen va a `kind-registry:5000/` (`platform/policies/kyverno/restrict-registries.yaml`). La construye y la aplica el operador en el Paso 16. Los manifiestos pasan kubeconform y las políticas de U1. Para `console-spa`, el eco devuelve las cabeceras del perfil `spa` que pone el gateway, no las suyas.
- **Exclusión de `check`** (H3). Tres cambios en `identity-edge/Makefile`:
  - el target `test` pasa `--ignore=identity-edge/tests/e2e`;
  - `collect-e2e` corre `pytest identity-edge/tests/e2e --collect-only -q` y entra en `check`;
  - `e2e` corre la suite contra kind y **no** entra en `check`.

  Cierra la candidata de `CANDIDATAS.md` sobre e2e en `check`.
- **Configuración por entorno.** `conftest.py` lee del entorno:
  - `VECTRA_E2E_BASE_URL` y `VECTRA_E2E_CA_BUNDLE` (nada de `verify=False`, por S501);
  - `SYNTH_*_PASSWORD` y `SYNTH_*_TOTP_SEED`;
  - la URL y las credenciales de la Admin API, por port-forward (BR-U2-12);
  - `VECTRA_E2E_LOKI_URL`.

  Si falta una variable al **ejecutar**, la prueba falla con un error explícito; nunca se salta con `skip`. La colección no necesita ninguna variable.
- **Aprobador sin TOTP** (H5): una fixture crea por la Admin API un usuario con un rol de aprobador y `CONFIGURE_TOTP` pendiente, y lo borra al terminar.
- **Evento e IP** (H6, BR-U2-16, NFR-U2-23):
  - el evento del bloqueo se consulta en Loki con LogQL: tiene `userId` y no tiene `username` ni `email`;
  - la IP registrada es `client_ip` del access log en Loki, y además se comprueba con el contador de `/auth`.
- **Tipo de evento del bloqueo** (H9): se fija contra el código de Keycloak 26.8.1, con ruta y línea en la bitácora.
- **PBT-U2-08** (H8): una máquina de estados de Hypothesis con el modelo de BR-U2-05, que lee del realm los contadores, las esperas y `maxTemporaryLockouts`. Usa un perfil `kind-e2e` registrado en el `conftest.py` de e2e, con pocos ejemplos y un usuario efímero por ejemplo, creado y borrado por la Admin API.
- **Dependencias** (H4). Al grupo `dev` de `pyproject.toml` se agregan `playwright`, `pytest-playwright`, `pyotp`, `axe-playwright-python` y `httpx`, en versiones exactas con al menos dos semanas de publicadas, y se actualiza `uv.lock`. Los navegadores (`playwright install`) solo se instalan en el Paso 16.

**Fuera:**
- Ejecutar algo contra kind o Docker, incluido construir la imagen del eco: es del Paso 16.
- El step-up en ventana emergente y BR-U2-07 (tokens en memoria): son de U10.
- Los casos de PBT-10 sobre `governance:freeze` y `core:read-credit` (H7): van a `CANDIDATAS.md`.
- La prueba de carga (Paso 14) y las alertas (Paso 11).
- Cambiar `routes.yaml`, los realms o `flows.yaml`. Si un caso no se puede escribir sin cambiarlos, detente y repórtalo.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Pasos 13 y 16)
- `aidlc-docs/construction/identity-edge/functional-design/business-rules.md` (BR-U2-03..08, 10, 12, 13, 14, 16)
- `aidlc-docs/construction/identity-edge/functional-design/business-logic-model.md` (PBT-06, PBT-10)
- `aidlc-docs/construction/identity-edge/functional-design/domain-entities.md` (límites, perfiles de cabeceras)
- `aidlc-docs/construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-23, NFR-U2-42)
- `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-06, P-U2-07, P-U2-08)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (secretos de usuarios sintéticos y llaves de cliente)
- `aidlc-docs/inception/user-stories/stories.md` (US-601, US-611)
- `identity-edge/gateway/routes.yaml`, `identity-edge/gateway/values/kind.yaml`, `identity-edge/keycloak/realm/realm.kind.yaml`
- `identity-edge/tests/strategies/gateway_design.py`, `realm_builders.py`, `identity-edge/tests/conftest.py`
- `identity-edge/Makefile`, `pyproject.toml`, `uv.lock`
- `platform/network/flows.yaml` (identidades de los servicios del eco), `platform/policies/` (políticas de U1)
- `CANDIDATAS.md`

## Criterios de aceptación

Corre los comandos desde `vectra-risk/`.

- [ ] **CA-1** — Es la aceptación del Paso 13: lint.
  ```bash
  uv sync --frozen && uv run ruff check identity-edge/tests/e2e
  ```
  Esperado: termina en 0.
- [ ] **CA-2** — Es la aceptación del Paso 13: la colección lista todos los casos nombrados, sin variables de entorno.
  ```bash
  env -u VECTRA_E2E_BASE_URL uv run pytest identity-edge/tests/e2e --collect-only -q
  ```
  Esperado: 0 errores de colección. Aparecen todos los ids de CA-3.
- [ ] **CA-3** — Cada viñeta del Paso 13 tiene su prueba.
  ```bash
  uv run pytest identity-edge/tests/unit/test_e2e_inventory.py -q
  ```
  Esperado: pasa. La prueba hace tres cosas:
  - asocia cada id de prueba a un fragmento literal del texto del Paso 13 del plan;
  - corre `pytest --collect-only` como subproceso;
  - falla si un fragmento ya no está en el plan, si una viñeta no tiene id o si un id no aparece en la colección.

  Tiene un caso que falla con una prueba e2e quitada en una copia.
- [ ] **CA-4** — El eco es válido sin clúster.
  ```bash
  uv run pytest identity-edge/tests/unit/test_e2e_echo.py -q
  ```
  Esperado: pasa. Hace dos cosas:
  - levanta el servidor del eco en el proceso y comprueba que devuelve byte a byte `Idempotency-Key` y `X-Test-Scenario`;
  - valida los manifiestos con kubeconform y con las políticas Kyverno y Rego de U1: nombres, SA, etiquetas y puertos leídos de `flows.yaml` y `routes.yaml`, e imagen de `kind-registry:5000`.

  Cada comprobación falla en una copia mutada.
- [ ] **CA-5** — U2 sigue cumpliendo. `check` incluye `collect-e2e` y `test` no ejecuta las e2e.
  ```bash
  make -C identity-edge collect-e2e && make -C identity-edge check
  ```
  Esperado: todo pasa y termina en 0, sin pruebas omitidas. La salida de `test` no lista ningún archivo de `tests/e2e`.
- [ ] **CA-6** — U1 y los contratos siguen cumpliendo con el lock nuevo.
  ```bash
  make -C platform check-local && uv run pytest contracts/tests -q
  ```
  Esperado: termina en 0. Corre CA-5 y CA-6 en serie.

## Plan de pruebas

**Rojo primero:**
1. Escribe `test_e2e_inventory.py` y `test_e2e_echo.py`, y registra en la bitácora que fallan: `tests/e2e/` solo tiene `.gitkeep`.
2. Escribe el `--ignore` y `collect-e2e`.
3. Escribe los módulos e2e y el eco hasta que CA-2, CA-3 y CA-4 pasen.

## Notas

- Implementa lo que define el diseño enmendado. Detente y repórtalo, sin sustituirlo por otro mecanismo, si pasa algo de esto:
  - falta un dato;
  - un caso del plan no se puede observar con lo que da kind;
  - Keycloak 26.8.1 o Envoy Gateway v1.9.3 no se comportan como asume el diseño.
- Comprueba los nombres de eventos y de campos contra el código de los tags, con `gh api repos/keycloak/keycloak/contents/<ruta>?ref=26.8.1 -H "Accept: application/vnd.github.raw"`.
- Ruff selecciona `S`: nada de `verify=False`, y nada de secretos en literales.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker.** El destino es un pull request, y lo fusiona una persona.
- La red solo se usa para `uv lock` y `uv sync` (H4), `install-tools.sh`, `charts.sh` y `gh api` de lectura.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
