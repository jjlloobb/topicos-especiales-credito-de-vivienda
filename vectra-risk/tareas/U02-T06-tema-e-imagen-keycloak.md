# U02-T06 — Tema `vectra` e imagen de Keycloak

**Unidad:** U2 `identity-edge`
**Historias que implementa:** las del tema de login de P-U2-08 (NFR-USA-01) y la cadena de suministro de NFR-U2-25
**Depende de:** U02-T04 (realm como código), en `main`

Paso 4 del plan de U2. Los datos que el plan no fijaba los decidió el usuario al preparar la tarea (2026-11-02, decisiones P1 a P4) y están en el diseño enmendado: versión y digest de la imagen en INF-U2-08, marca y referencia de claves en P-U2-08, y `hadolint` en las herramientas de `platform/`.

## Alcance

**Dentro:** todo el Paso 4 del plan. Texto del plan, sin recortes:

- [ ] **Paso 4 — Tema `vectra` e imagen de Keycloak**
  - Tema hijo de `keycloak.v2` con `messages_es.properties`, logo y colores; sin JavaScript propio ni recursos de otro origen.
  - `Dockerfile`: imagen oficial 26.x pinneada por digest + tema + `kc.sh build` (`db=postgres`, `health-enabled`, `metrics-enabled`, `cache=ispn`).
  - Diseño: BR-U2-13 (CSP estricta en `/auth/**`, posible porque el tema no tiene JavaScript propio); P-U2-08; INF-U2-08; NFR-U2-25.
  - **Aceptación**: `hadolint identity-edge/keycloak/Dockerfile`; `uv run pytest identity-edge/tests/unit/test_theme.py` (ningún archivo del tema referencia `http(s)://` externos ni `<script>` propio; todas las claves de `messages_es` existen). La construcción, el escaneo y la firma los hace `supply-chain.yml` de U1.

Precisiones del diseño enmendado que la tarea aplica:
- Tema en `identity-edge/keycloak/themes/vectra/login/`, con la estructura estándar de temas de Keycloak (`theme.properties` con `parent=keycloak.v2`, `messages/messages_es.properties`, `resources/`).
- Marca Vectra de P-U2-08: `vectra-logo.svg`, primario `#0B3D5C`, acento `#C2410C`, fondo `#FFFFFF`.
- Imagen base exacta de INF-U2-08: `quay.io/keycloak/keycloak:26.8.1@sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332`. Arranque `start --optimized`.
- Referencia de claves de P-U2-08: `identity-edge/tests/fixtures/keycloak-26.8.1/` (ya está en el repo, con `SHA256SUMS` y un `README.md`).

**Fuera:**
- Activar el tema en los realms (`loginTheme`, locales). Ningún paso del plan lo incluye; está en `CANDIDATAS.md`.
- Sesiones persistentes (D6, candidata para los Pasos 4 y 5): el diseño no fija sus opciones de `kc.sh build`. No se agregan.
- Las pruebas con Playwright y axe-core de P-U2-08 (Paso 16, contra kind).
- Construir, escanear o firmar la imagen. Cambios en `contracts/`, `platform/`, `.github/workflows/` y los realms.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Paso 4)
- `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-08)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-08)
- `aidlc-docs/construction/identity-edge/functional-design/business-rules.md` (BR-U2-13)
- `identity-edge/tests/fixtures/keycloak-26.8.1/README.md`

## Criterios de aceptación

- [ ] **CA-1** — Aceptación del Paso 4, parte del `Dockerfile`.
  ```bash
  platform/.tools/bin/hadolint identity-edge/keycloak/Dockerfile
  ```
  Esperado: sin hallazgos, sale en 0.
- [ ] **CA-2** — Aceptación del Paso 4, parte del tema: ningún archivo del tema referencia `http(s)://` ni tiene `<script>`; toda clave de `messages_es.properties` existe en la referencia; están traducidas las claves que fija P-U2-08. Lectura de vuelta: un caso que falla por cada regla (una URL `https://` en el CSS, otra en el SVG, un `<script>` en el SVG, una clave inventada en `messages_es`, una clave de TOTP sin traducir), hecho sobre una copia del tema.
  ```bash
  uv run pytest identity-edge/tests/unit/test_theme.py -q
  ```
  Esperado: pasa.
- [ ] **CA-3** — La referencia no cambió y las claves exigidas salen de las plantillas, no de una lista escrita a mano: la prueba verifica `SHA256SUMS` de los fixtures y extrae de las plantillas listadas en P-U2-08 las claves literales `msg("…")` que existen en la referencia.
  ```bash
  uv run pytest identity-edge/tests/unit/test_theme.py -q -k reference
  ```
  Esperado: pasa; un fixture alterado en una copia hace fallar la prueba.
- [ ] **CA-4** — Marca de P-U2-08: el CSS del tema usa `#0B3D5C`, `#C2410C` y `#FFFFFF`, y no otros colores; el contraste de primario y acento sobre el fondo es ≥ 4,5:1, calculado por la prueba; `theme.properties` declara `parent=keycloak.v2` y el CSS propio. Los colores los lee la prueba de P-U2-08, no de una constante.
  ```bash
  uv run pytest identity-edge/tests/unit/test_theme.py -q -k brand
  ```
  Esperado: pasa.
- [ ] **CA-5** — El `Dockerfile` cumple INF-U2-08: `FROM` con la imagen y el digest exactos de INF-U2-08 (leídos del diseño), el tema copiado, `kc.sh build` con `--db=postgres`, `--health-enabled=true`, `--metrics-enabled=true` y `--cache=ispn`, y arranque `start --optimized`. Lectura de vuelta: casos que fallan con otro digest, sin digest, sin cada una de las cuatro opciones y sin `--optimized`.
  ```bash
  uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q
  ```
  Esperado: pasa.
- [ ] **CA-6** — Lo anterior sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check && make -C platform check-tools
  ```
  Esperado: todo pasa y termina en 0.

## Plan de pruebas

**Rojo primero:** escribe `test_theme.py` y `test_keycloak_image.py` y registra que fallan sin el tema ni el `Dockerfile`.

## Notas

- Implementa lo que define el diseño enmendado. Si falta un dato, detente y repórtalo.
- Los URI de espacio de nombres XML (atributos `xmlns`, por ejemplo `http://www.w3.org/2000/svg`) no son recursos de otro origen; la prueba los distingue de cualquier otra URL.
- No edites `identity-edge/tests/fixtures/`.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker** (el proyecto los deniega por configuración; no hagas `docker build`). El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. Sin red.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
