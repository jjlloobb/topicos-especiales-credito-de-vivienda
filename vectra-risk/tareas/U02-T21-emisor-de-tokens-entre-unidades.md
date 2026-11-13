# U02-T21 — El emisor (`iss`) de los tokens entre unidades: medirlo con un Keycloak real, corregir los values y atarlo con una prueba

**Unidad:** U2 `identity-edge` (la prueba vive en `platform/tests/`, de U1; los values que cambian son de U3, U4, U7 y U9).
**Historias:** ninguna nueva. Corrige un desajuste de configuración entre unidades que impediría cualquier flujo autenticado en kind (las cuatro demos).
**Depende de:** nada. Todo lo que toca está en `main` (comprobado al redactar, sobre `72260a6`).
**Se coordina con:** U08-T05 y U10-T05 (ramas en curso; ver «Ramas en curso») y U12-T02 (también levanta un Keycloak en Docker; ver «Restricciones del entorno»).
**Rama:** `tarea/U02-T21`, desde `origin/main`.

**Por qué.** Decisión del usuario del 2026-11-13 (`DECISIONES-LOOP.md` §10, «Emisor de los tokens entre unidades»). Al redactar U10-T05 apareció que:

- Keycloak se rinde con `KC_HOSTNAME=https://<hostname público>/auth` y `KC_HOSTNAME_ADMIN=https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth`, sin `KC_HOSTNAME_BACKCHANNEL_DYNAMIC` (`identity-edge/keycloak/values/common.yaml`, líneas 138 a 141; `identity-edge/keycloak/rendered/kind/keycloak.yaml`, líneas 246-247 y 266 a 269). El diseño lo fija así: INF-U2-01 (`aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md`, línea 20) y, para el gateway, la línea 67: «el `issuer` es `https://<hostname público>/auth/realms/vectra`». El diseño **no dice nada** del emisor que validan los servicios ni del backchannel.
- Los charts de U3, U4, U7 y U9 validan `iss` contra `https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra`, y `vectra_common` solo acepta **un** emisor (`contracts/python/vectra_common/src/vectra_common/authn.py`, línea 69).

**Hipótesis (a medir, no un hecho):**

- **H1.** Con `KC_HOSTNAME` fijado como URL completa, **todo** token sale con `iss = https://<hostname público>/auth/realms/vectra`, también el que un servicio pide por el host interno. Entonces los servicios responden 401 a todo: al token del navegador que reenvía el BFF (F10 a F14) y a los tokens de servicio (F16, F24 a F28, F103, F104).
- **H1-bis (la contraria).** El token pedido por el host interno sale con el emisor interno: circulan **dos** emisores y un servicio que recibe a usuarios y a servicios no puede validar los dos.
- **H2 (hallada al inventariar).** `vectra_common.service_token` firma la aserción `private_key_jwt` con `aud` = la URL de token que usa, la interna (`service_token.py`, línea 60). Si Keycloak solo acepta como `aud` las URL que deriva de `KC_HOSTNAME`, rechaza la aserción y **ningún** servicio obtiene token, tampoco `realm-drift` ni `signing-key-age` de U2. La prueba e2e de U2 no lo cubre: pide el token por el gateway, con `aud` = URL pública (`identity-edge/tests/e2e/e2e_support.py`, líneas 288 a 302).

Nada de esto se probó nunca: en kind no hay nada desplegado en `vectra-app`, las evidencias de kind de U4 siguen en «pendiente del operador» (`aidlc-docs/construction/governance/evidence/kind/03-arranque-politica.md`, línea 3) y en el repositorio no hay ninguna prueba que lea el `iss` de un token de un Keycloak real (las de `identity-edge/tests/` usan `fake_keycloak.py` o corren solo contra kind).

Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Sin clúster (AUTONOMIA-01).

---

## Alcance

**Dentro**, en este orden:

1. **Medir** con un Keycloak real en Docker (ver «La medición») y dejar la evidencia en `identity-edge/docs/emisor-de-tokens.md`.
2. **Verificar el inventario** de abajo, fila por fila, contra el `main` de tu rama. Corrige en la bitácora lo que haya cambiado.
3. **Escribir la prueba de mundo cerrado** `platform/tests/test_token_issuer.py` y **verla fallar** sobre `main` (rojo primero).
4. **Corregir** con el cambio mínimo, solo values, según la tabla «Qué hacer según lo medido». En tres de los cuatro resultados posibles hay que **parar y reportar** antes de corregir.
5. **`CANDIDATAS.md`:** una entrada de este hallazgo, «Resuelta (U02-T21)» o «Abierta», según el resultado.

**Fuera** (recházalo aunque lo veas roto):

- `src/` de cualquier servicio y todo `contracts/` (U0). Una lista de emisores en `vectra_common.authn` o un `aud` configurable en `service_token` son P-1 y P-2: **no los toques**.
- La configuración de Keycloak y del gateway: `identity-edge/keycloak/` (values, realm, render, Dockerfile, políticas), `identity-edge/gateway/`, `identity-edge/jobs/`.
- Las plantillas de los charts (`chart/templates/`). Solo cambian values.
- `platform/network/flows.yaml` y lo generado de la red. Si la corrección pide un flujo nuevo, **para y reporta**.
- `platform/tests/integration.py` (`render_env` no pasa los values de cada unidad: `CANDIDATAS.md`, líneas 466 y 512). La prueba nueva lo rodea usando `chart_renders`.
- `keycloak.caConfigMap` en staging y prod (`CANDIDATAS.md`, líneas 286 y 300): es la CA, no el emisor.
- El `aud` de los **access tokens** (los mapeadores de audiencia del realm): lo ejerce U12-T02.
- Desplegar, sincronizar o tocar el clúster. Los diseños y los planes.

---

## Inventario (comprobado al redactar sobre `72260a6`; verifícalo)

Ningún archivo de `vectra-risk-gitops/` fija `keycloak.*`: **los tres entornos** rinden el valor por omisión de cada chart. El defecto, si H1 se confirma, es de kind, de staging y de prod.

| Quién | Valida `iss` contra | JWKS | Pide token en | Ruta y línea |
|---|---|---|---|---|
| U2, gateway | `https://<hostname público>/auth/realms/vectra` | `https://keycloak.vectra-identity.svc:8443/…/certs` | — | `identity-edge/gateway/routes.yaml` 59-60; `identity-edge/tools/route_gen.py` 314; `identity-edge/gateway/generated/kind/securitypolicies.yaml` 39, 87 y 142 |
| U2, `realm-drift` y `signing-key-age` | no valida | — | `keycloak-admin…:8443` | `identity-edge/jobs/chart/values.yaml` 12; `identity-edge/jobs/rendered/kind/identity-jobs.yaml` 67 y 138 |
| U3, `decision-registry-service` | `keycloak-admin…:8443` (interno) | `keycloak-admin…:8443` | no pide | `decision-registry/chart/values.yaml` 40-41; `chart/templates/service.yaml` 93-94 |
| U4, `governance-service` | interno | `keycloak-admin…:8443` | `keycloak-admin…:8443`; la misma URL va al `model-validation-job` como `GOVERNANCE_JOB_TOKEN_URL` | `governance/chart/values.yaml` 25 a 27; `chart/templates/service.yaml` 73, 77, 81 y 82 |
| U6, `model-serving` | no usa JWT (mTLS de Linkerd) | — | — | sin `keycloak` en `model-serving/chart/`; su `values.schema.json` tiene `additionalProperties: false` |
| U7, `scoring-service` y `explainability-service` | interno | `keycloak-admin…:8443` | `keycloak-admin…:8443` | `scoring-explainability/chart/values.yaml` 21 a 23; `chart/templates/service.yaml` 75, 77 y 78 |
| U8, `case-service`, `case-worker` y `core-banking-mock` (rama `tarea/U08-T05`, sin fusionar) | interno (`case-service` y el mock) | `keycloak-admin…:8443` | `keycloak-admin…:8443` (`case-service` y `case-worker`) | `case-management/chart/values.yaml` 36 a 38; `templates/case-service.yaml` 71-72; `templates/core-banking-mock.yaml` 59-60; `templates/_helpers.tpl` 63 |
| U9, `bias-monitoring-service` | interno | `keycloak-admin…:8443` | `keycloak-admin…:8443` | `bias-monitoring/chart/values.yaml` 16 a 18; `chart/templates/service.yaml` 61, 64 y 65 |
| U9, `bias-monitoring-job` | no valida | — | `keycloak-admin…:8443` | `bias-monitoring/chart/templates/cronjob.yaml` 61 |
| U10, `console-bff` | aún sin chart (`console/chart/templates/` está vacío). Exige `VECTRA_OIDC_ISSUER` y `VECTRA_JWKS_URL` | — | no pide | `console/bff/src/console_bff/app.py` 47; `tareas/U10-T05-despliegue-y-cierre.md`, P-4: emisor público y JWKS de `routes.yaml` |
| U11, `product-metrics` | **no valida** (solo `provider_from_env`: `product-metrics/src/vectra_product/reader.py` 77) | — | `keycloak-admin…:8443` | `product-metrics/chart/values.yaml` 14; `chart/templates/deployment.yaml` 67 |
| U0, `vectra_common` | **un** emisor, de `VECTRA_OIDC_ISSUER`; `aud` = nombre del servicio | `VECTRA_JWKS_URL` | `VECTRA_TOKEN_URL`; la aserción lleva `aud` = esa URL | `authn.py` 69 y 78 a 87; `service_token.py` 60 y 91 a 99 |
| Operador (guías de kind) | — | — | por el gateway, URL pública | `identity-edge/tests/e2e/e2e_support.py` 288 a 302; `governance/docs/kind/token.sh` |

Red: F50 permite a todos esos orígenes llegar al workload `keycloak` por el 8443 (`platform/network/flows.yaml`, línea 220), y F05 al gateway (línea 153). Los Services `keycloak` y `keycloak-admin` seleccionan los mismos pods y abren el 8443 (`identity-edge/keycloak/rendered/kind/keycloak.yaml`, líneas 52 a 92). **Ningún flujo** lleva de un servicio de `vectra-app` a `api-gateway` (líneas 149 a 158: solo orígenes externos): un JWKS o una URL de token por el nombre público no tiene camino.

---

## La medición

- **Imagen:** la de la línea `FROM` de `identity-edge/keycloak/Dockerfile` (línea 3: `quay.io/keycloak/keycloak:26.8.1`, por digest), leída del archivo, no copiada. Descargarla está autorizado (`DECISIONES-LOOP.md` §10).
- **Igual que el render de kind** (léelo de `identity-edge/keycloak/rendered/kind/keycloak.yaml`): `KC_HOSTNAME`, `KC_HOSTNAME_ADMIN`, `KC_PROXY_HEADERS` y la ruta `/auth`, con sus valores exactos; orden `start`, no `start-dev`, si arranca.
- **Diferencias permitidas, cada una anotada en la evidencia:** base de datos y caché locales; certificado desechable con los SAN del `Certificate` `keycloak-tls`; administrador de arranque con contraseña al azar; un realm `vectra` mínimo creado para la medición (un usuario y un cliente público desechables con *direct grant* para M-a; un cliente `client-jwt` ES256 con una llave generada al momento para M-b y M-c). El realm real no hace falta: el `iss` no depende de él.
- **Host dinámico:** el contenedor publica un puerto libre en `127.0.0.1`. **La URL de toda orden es `127.0.0.1:<puerto>`, o el nombre interno desviado con `curl --connect-to` (o un transporte de `httpx`) a `127.0.0.1:<puerto>`.** `vectra.localtest.me` es el kind de esta máquina: ese nombre solo aparece en `KC_HOSTNAME` y en la cabecera `X-Forwarded-Host`, **nunca** como host de una URL.

| Id | Qué se mide | Cómo |
|---|---|---|
| M-a | `iss` de un token de usuario pedido «por el gateway» | `POST …/token` a `127.0.0.1:<puerto>` con `X-Forwarded-Proto: https` y `X-Forwarded-Host: vectra.localtest.me` |
| M-b | `iss` de un token de servicio pedido por el host interno | `client_credentials` con `private_key_jwt`, a `https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra/protocol/openid-connect/token` desviado al contenedor, sin cabeceras `X-Forwarded-*` |
| M-c | H2: si Keycloak acepta la aserción de U0 | la aserción de M-b la construye `vectra_common.service_token.ServiceTokenProvider` (importado, no reimplementado), con `aud` = esa URL interna. Anota el HTTP y el `error_description` |
| M-d | Lo que Keycloak anuncia | `issuer`, `token_endpoint` y `jwks_uri` de `/.well-known/openid-configuration`, pedido de las dos formas (como M-a y como M-b) |

**Evidencia:** `identity-edge/docs/emisor-de-tokens.md`, con una fila por medida, la orden exacta, el HTTP, la cabecera y el cuerpo del token **decodificados** (nunca el token, la aserción, la llave ni la contraseña), la versión y el digest de la imagen, cada diferencia con kind y el `uptime`. Si usas un guion, es `identity-edge/tools/measure_issuer.py` y pasa `make -C identity-edge lint`; no entra en `make check` ni en `identity-edge/tests/`.

### Qué hacer según lo medido

| Resultado | Qué significa | Qué haces |
|---|---|---|
| **R1** — M-a y M-b dan el emisor público; M-c da 200 | H1 cierta, H2 falsa | Corriges los values (abajo) y cierras |
| **R2** — M-a y M-b dan el emisor público; M-c rechaza la aserción | H1 y H2 ciertas | Corriges el emisor en los values, **paras y reportas** H2 (P-2). No toques U0 ni Keycloak |
| **R3** — M-b da el emisor interno | H1-bis: dos emisores | **Paras y reportas** (P-1), con la evidencia y la prueba en rojo. No corrijas nada |
| **R4** — M-a no da el emisor público, o Keycloak no arranca con esas variables | El render de U2 o el gateway están mal | **Paras y reportas** |

**La corrección (R1 y R2), según P-3:**

- `keycloak.issuer` de cada chart que valida = el emisor medido, por entorno: `https://<hostname del entorno>/auth/realms/vectra`, con el hostname de `identity-edge/keycloak/values/<env>.yaml` (igual al de `identity-edge/gateway/values/<env>.yaml`).
- `keycloak.jwksUrl` y `keycloak.tokenUrl` **no cambian**: siguen por `keycloak-admin…:8443`, que es lo que F50 permite.
- `product-metrics`, `bias-monitoring-job` e `identity-jobs` no validan: no cambian.

---

## Criterios de aceptación

Desde `vectra-risk/`. Guarda los logs con el prefijo `u02t21-`.

- [ ] **CA-1 — La medición existe, está completa y no trae secretos.**
  ```bash
  grep -cE '^\| M-[abcd] ' identity-edge/docs/emisor-de-tokens.md
  grep -cE 'eyJ[A-Za-z0-9_-]{20,}|PRIVATE KEY|client_assertion=' identity-edge/docs/emisor-de-tokens.md
  grep -nE 'R[1-4]' identity-edge/docs/emisor-de-tokens.md | head -3
  ```
  Esperado: `4`; `0`; y una línea que declara cuál de R1 a R4 se obtuvo. Cada fila trae su orden, el HTTP y los claims `iss`, `azp` y `aud` decodificados (o el error). El revisor repite la medición con las órdenes del archivo.
- [ ] **CA-2 — Ninguna orden de la evidencia ni del guion apunta al kind de la máquina, y no queda nada en Docker.**
  ```bash
  grep -nE 'https?://vectra\.localtest\.me' identity-edge/docs/emisor-de-tokens.md identity-edge/tools/measure_issuer.py 2>/dev/null | grep -vE 'KC_HOSTNAME|iss|issuer|X-Forwarded|token_endpoint|jwks_uri'
  docker ps -a --format '{{.Names}} {{.Image}}' | grep -ciE 'u02t21'
  ```
  Esperado: sin salida; `0`.
- [ ] **CA-3 — El inventario está verificado.** La bitácora trae la tabla con cada fila marcada «igual» o corregida, y la salida de:
  ```bash
  grep -rnE 'VECTRA_OIDC_ISSUER|VECTRA_JWKS_URL|VECTRA_TOKEN_URL|GOVERNANCE_JOB_TOKEN_URL' --include='*.yaml' --include='*.tpl' decision-registry/chart governance/chart scoring-explainability/chart bias-monitoring/chart product-metrics/chart model-serving/chart identity-edge/jobs/chart case-management/chart console/chart
  grep -rnE 'issuer|jwksUrl|tokenUrl' vectra-risk-gitops/values vectra-risk-gitops/envs
  ```
  Esperado: toda línea de la primera orden corresponde a una fila de la tabla. La segunda no da nada sobre `origin/main` y, tras la corrección, solo los `keycloak.issuer` nuevos.
- [ ] **CA-4 — Rojo primero.** Con la prueba escrita y **sin** la corrección (haz el commit de la prueba antes que el de los values):
  ```bash
  uv run pytest platform/tests/test_token_issuer.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib
  ```
  Esperado en R1 y R2: termina en 1 y falla el caso del emisor de cada workload que valida, en los tres entornos; los casos de JWKS, URL de token y flujos pasan. La salida va en la bitácora con el hash del commit. En R3 queda en rojo y así se entrega.
- [ ] **CA-5 — Verde tras la corrección** (R1 y R2). La misma orden termina en 0 con `-v`, y la salida muestra, por entorno, al menos estos workloads: `decision-registry-service`, `governance-service`, `scoring-service`, `explainability-service` y `bias-monitoring-service` (validan), más `bias-monitoring-job`, `product-metrics`, `realm-drift` y `signing-key-age` (solo piden). La prueba **descubre** los workloads en los renders; no los lista. Un mínimo de casos por entorno impide que pase en vacío.
- [ ] **CA-6 — La prueba detecta cada desajuste.** Sobre copias de los renders o con values de más (nunca editando los archivos reales), cada mutación falla con un mensaje que nombra el workload y el entorno:
  ```bash
  uv run pytest platform/tests/test_token_issuer.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k "mutation" -v
  ```
  Esperado: pasan, como mínimo, estos casos: (a) emisor con `keycloak-admin`; (b) el emisor de staging en kind; (c) emisor sin `/realms/vectra` o con otro realm; (d) JWKS por el hostname público; (e) URL de token al puerto 443; (f) un workload que pide token y no es origen de ningún flujo hacia `keycloak`; (g) un host que no es SAN de `keycloak-tls`; (h) el `issuer` del gateway distinto de `KC_HOSTNAME` + `/realms/vectra`.
- [ ] **CA-7 — Cambio mínimo.**
  ```bash
  git diff --name-only origin/main | grep -vE '^vectra-risk/((decision-registry|governance|scoring-explainability|bias-monitoring|case-management)/chart/values\.yaml|vectra-risk-gitops/(values|apps)/(kind|staging|prod)/[a-z-]+\.yaml|platform/tests/test_token_issuer\.py|identity-edge/docs/emisor-de-tokens\.md|identity-edge/tools/measure_issuer\.py|bitacoras/U02-T21\.md|CANDIDATAS\.md)$'
  git diff origin/main -- '*/chart/values.yaml' vectra-risk-gitops/values | grep -E '^[+-] ' | grep -vE 'issuer|^\+ *#|^\+keycloak:'
  ```
  Esperado: las dos sin salida. Solo cambia `keycloak.issuer` (y sus comentarios).
- [ ] **CA-8 — Lo generado y los charts siguen en verde.**
  ```bash
  uv run python vectra-risk-gitops/generate.py --check
  for u in decision-registry governance scoring-explainability bias-monitoring; do make -C $u policy-chart policy-chart-u1 || break; done
  make -C platform check-local
  ```
  Esperado: todo en 0. Además, `test_chart.py` de cada una de las cuatro unidades, con las opciones de la receta `test` de su `Makefile`, en 0. En serie; anota `uptime` y la duración. El `make check` completo: P-4.
- [ ] **CA-9 — `CANDIDATAS.md`.** `grep -n "U02-T21" CANDIDATAS.md` devuelve la entrada de este hallazgo, con el resultado (R1 a R4), y cada desvío abierto (P-1, P-2) como candidata con su unidad.

---

## La prueba de mundo cerrado

`platform/tests/test_token_issuer.py`. Va en `platform/tests/` porque ahí están las pruebas entre unidades (`test_integration.py`, `test_kind_profile.py`) y `integration.chart_renders`, que da los values que Argo CD pasa a cada chart (`envs/<env>/values.yaml` más `generate.value_files`). Corre con `make -C platform check-local`. Sin clúster y sin Docker.

Para cada entorno (kind, staging, prod):

1. **Fuentes, leídas y no copiadas:**
   - emisor de Keycloak = `KC_HOSTNAME` del StatefulSet de `identity-edge/keycloak/rendered/<env>/keycloak.yaml` + `/realms/vectra`;
   - emisor del gateway = el `issuer` de cada proveedor JWT de `identity-edge/gateway/generated/<env>/securitypolicies.yaml`;
   - Services y `Certificate` `keycloak-tls` del mismo render de Keycloak;
   - flujos de `platform/network/flows.yaml`, con `envs` y `enabled`;
   - componentes de `vectra-risk-gitops/components.yaml`, rendidos con `chart_renders`, y `identity-edge/jobs/rendered/<env>/`.
2. **Emisor:** todo contenedor con `VECTRA_OIDC_ISSUER` lo tiene **igual** al emisor de Keycloak, y este es igual al de todos los proveedores del gateway.
3. **JWKS y URL de token** (`VECTRA_JWKS_URL`, `VECTRA_TOKEN_URL`, `GOVERNANCE_JOB_TOKEN_URL`):
   - el host es el nombre DNS de un Service del render de Keycloak que selecciona sus pods y abre ese puerto;
   - el host es SAN de `keycloak-tls`;
   - el esquema es `https` y la ruta es la del realm `vectra` (`…/protocol/openid-connect/certs` o `…/token`);
   - el workload, hallado por su ServiceAccount en `workloads` de `flows.yaml`, es origen de un flujo habilitado en ese entorno hacia `keycloak` por ese puerto. Para `GOVERNANCE_JOB_TOKEN_URL` el origen es `model-validation-job`.
4. **Coherencia:** un workload con `VECTRA_OIDC_ISSUER` tiene también `VECTRA_JWKS_URL`.

Cuando U8 y U10 lleguen a `main`, la prueba los cubre sin cambios, porque descubre los workloads.

---

## Ramas en curso

- **U08-T05** (`tarea/U08-T05`): su chart nace con el emisor interno (`case-management/chart/values.yaml`, línea 36, en su worktree). Si **ya está en `main`** cuando crees tu rama, lo corriges como a los demás (por eso CA-7 lo admite). Si no, no lo toques: el orquestador lo concilia al fusionar, y la prueba de esta tarea lo pondrá en rojo en `main` hasta entonces. Anota en la bitácora cuál de los dos casos encontraste.
- **U10-T05:** su P-4 ya elige el emisor público y el JWKS de `routes.yaml` (`keycloak.vectra-identity.svc:8443`) en `vectra-risk-gitops/values/<env>/console-bff.yaml`. No hay nada que corregir. La prueba acepta los dos Services (`keycloak` y `keycloak-admin`). Si U10-T05 dejó en `CANDIDATAS.md` la candidata de «las cinco rutas de los `values.yaml`», márcala «Resuelta (U02-T21)».
- **U12-T02:** fija el emisor de kind en `guard.KIND` y lo ata al realm y al gateway. No se toca. Si al empezar ya existe en `main` su arranque de Keycloak (`system-verification/tests/doubles/keycloak_tc.py`), puedes reutilizarlo; esta tarea no depende de él.

---

## Preguntas abiertas

**P-1 — Si circulan dos emisores (R3).**
- (a) `vectra_common.authn` acepta una lista de emisores (`VECTRA_OIDC_ISSUER` separado por comas). Es U0 y amplía lo que cada servicio acepta.
- (b) Cambiar el modo de hostname de Keycloak (`KC_HOSTNAME_BACKCHANNEL_DYNAMIC` u otro). Toca INF-U2-01 y las políticas del render.
- (c) Los servicios piden su token por la URL pública. Pide un flujo nuevo de cada servicio a `api-gateway` y pasar por el límite de tasa.

**Recomendación del orquestador: (a)**, en una tarea de U0 aparte, tras medir qué emisor trae cada token. **En R3 el codificador para y reporta; no elige.**

**P-2 — Si Keycloak rechaza la aserción con `aud` interno (R2).**
- (a) `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true`, para que Keycloak acepte las URL del host por el que llega la petición. Toca U2 y hay que volver a medir M-b, porque puede cambiar el `iss` o lo que anuncia M-d.
- (b) `service_token` firma con `aud` = el emisor (una variable nueva, por ejemplo `VECTRA_TOKEN_AUDIENCE`). Toca U0 y cada chart que pide token.

**Recomendación: medir (a) en el mismo contenedor, como medida extra M-e en la evidencia, y parar.** La medida es barata y le da al usuario el dato para decidir. No cambies ningún archivo de U2 ni de U0.

**P-3 — Dónde vive el emisor de cada entorno.** El hostname público cambia por entorno y hoy ningún chart lo recibe.
- (a) **`chart/values.yaml` con el emisor de producción por omisión, y `vectra-risk-gitops/values/<env>/<componente>.yaml` con el de kind y el de staging** (recomendada). `generate.py` añade ese archivo a la Application si existe (`value_files`, líneas 90 a 94), y es la convención de U7 y de U10-T05 (P-1 a). Hay que regenerar `apps/` con `uv run python vectra-risk-gitops/generate.py`.
- (b) Un `publicHostname` en `envs/<env>/values.yaml` y el emisor compuesto en las plantillas. Toca `generate.py`, las plantillas de cuatro charts y el esquema cerrado de `model-serving`.

**Recomendación: (a).** Si no hay respuesta, rige (a).

**P-4 — Qué `make check` corre (RL-4).** La tarea es de U2 pero no cambia nada que `make -C identity-edge check` (≈ 25 min) ejerza, salvo un Markdown y, si acaso, un guion.
- (a) **`make -C platform check-local`, los `policy-chart` y `test_chart.py` de las cuatro unidades (CA-8), y de U2 solo `make -C identity-edge lint runbooks`** (recomendada).
- (b) Además, `make -C identity-edge check` completo.

**Recomendación: (a).** Si no hay respuesta, rige (a).

---

## Restricciones del entorno

- **`/tmp` es un tmpfs con cuota y está casi lleno.** No copies el repositorio allí. Los renders y los temporales van a `platform/.tools/integration/u02t21/` o a `platform/.tools/tmp` (`export TMPDIR=$PWD/platform/.tools/tmp`).
- **Máquina compartida y cargada** (al redactar: carga 7,4; 5 GiB disponibles de 14). Anota `uptime` junto a cada medida y cada `make`. Corre los `make` en serie.
- **Keycloak ocupa ≈ 1 GiB de RAM.** Antes de arrancarlo, mira `free -g` y `docker ps`: si U12-T02 tiene su Keycloak arriba o quedan menos de 2 GiB disponibles, espera. Límite de memoria al contenedor: 1,5 GiB.
- **Docker se comparte con kind y con otros agentes.** Nombre del contenedor con el prefijo `u02t21-` y un sufijo al azar; puerto libre al azar, publicado **solo** en `127.0.0.1`; nunca el 443, el 8080, el 8081 ni el 8443 del host. **Borra el contenedor y sus volúmenes al terminar**, también si falla (CA-2). No borres la imagen: la usa U12-T02. No toques los contenedores de kind (`vectra-*`, `kind-registry`) ni los de otros.
- **Sin clúster.** Nada de `kubectl`, `helm install`, `argocd` ni sync. `helm template` sí.
- **`platform/.tools` y `platform/.charts` no están versionados.** En tu worktree, crea `platform/.tools/` real y copia o enlaza **solo** `platform/.tools/bin`; llena `platform/.charts` con `make -C platform charts` o cópialo del árbol principal. No enlaces los directorios enteros.
- **No toques el árbol principal ni otros worktrees** (el de U08-T05 es de solo lectura). **No uses `git stash`**: la pila se comparte entre worktrees. Para el rojo de CA-4, ordena los commits.

---

## Notas

- **Bitácora:** `bitacoras/U02-T21.md`, con el acuse de lectura (hash de este archivo), el inventario verificado, el resultado R1 a R4, el rojo de CA-4 con su hash, los rojos de CA-6, la respuesta aplicada a cada P-n y la carga de cada corrida.
- **Corrección a la decisión de `DECISIONES-LOOP.md` §10:** dice «los charts de U3 y U4». También U7 y U9 traen el emisor interno por omisión (sus plantillas usan `required`, pero el `values.yaml` ya da el valor).
- **Lo esperado, sin haberlo medido:** la documentación del modo de hostname de Keycloak 26 dice que, con `hostname` fijado como URL completa, el emisor es siempre esa URL. Por eso se espera R1 o R2. No lo des por cierto: mídelo.
- **Lo que esta tarea no demuestra:** que el flujo completo funcione en kind. Eso sigue en U12 Paso 18. Aquí quedan atados el emisor, el JWKS, la URL de token y los flujos, y medido lo que Keycloak hace con ellos.
- Archivos que se **modifican en su sitio**: los `chart/values.yaml` y `CANDIDATAS.md`. Nada de duplicados con sufijo.
