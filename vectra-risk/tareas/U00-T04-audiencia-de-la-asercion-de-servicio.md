# U00-T04 — La audiencia (`aud`) de la aserción de servicio: configurada con el emisor que Keycloak acepta, no la URL a la que se envía

**Unidad:** U0 `contracts` (`vectra_common.service_token`), con el ajuste mínimo en cada unidad que construye el proveedor o rinde `VECTRA_TOKEN_URL`: U2 (`identity-edge/jobs`), U4, U7, U9, U11, U8 si su chart ya está en `main`, y la prueba de mundo cerrado de `platform/tests/` (U1).
**Historias:** ninguna nueva. Sin este cambio ningún servicio obtiene token de servicio: se caen U8 → U7, U8 → U3, U7 → U4, U9 → U3, U11 → U3 y los Jobs de U2, es decir, las cuatro demos.
**Depende de:** **U02-T21 fusionada en `main`** (PR: _por completar al fusionar_; hash: _por completar al fusionar_). De ella salen `keycloak.issuer` con el emisor público en U3, U4, U7 y U9, `platform/tests/test_token_issuer.py`, `identity-edge/tools/measure_issuer.py` y `identity-edge/docs/emisor-de-tokens.md`. **No se despacha antes.**
**Se coordina con:** U08-T05 y U10-T05 (ver «Ramas en curso»). U12-T02 no depende de esta tarea.
**Rama:** `tarea/U00-T04`, desde `origin/main`.

**Por qué.** Resultado R2 de U02-T21 (`identity-edge/docs/emisor-de-tokens.md`, medidas M-b, M-c y M-e; pendiente de que su revisor lo reproduzca): Keycloak 26.8.1 con el `KC_HOSTNAME` de kind publica **un** emisor, el público, y responde 400 `invalid_client: Invalid token audience` a la aserción `private_key_jwt` cuya `aud` es la URL interna de token. Acepta como `aud` solo el emisor público o la URL pública de token. `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true` no lo cambia. Hoy:

- `ServiceTokenProvider._assertion` firma `"aud": self._token_url` (`contracts/python/vectra_common/src/vectra_common/service_token.py`, línea 60);
- los charts ponen `VECTRA_TOKEN_URL` con `keycloak-admin.vectra-identity.svc.cluster.local:8443`, que es el único camino que la red permite desde `vectra-app` (F50, `platform/network/flows.yaml`, línea 220).

El riesgo estaba anotado desde U02-T08 (`CANDIDATAS.md`, línea 65) y el plan de U0 decía que `service_token` nunca se probó contra un Keycloak real (`aidlc-docs/construction/plans/contracts-code-generation-plan.md`, línea 295).

**Se corrige el diseño, y por qué.** Ningún documento de diseño fija «`aud` = URL de token»: BR-U2-09 (`aidlc-docs/construction/identity-edge/functional-design/business-rules.md`, líneas 77-78) solo pide ES256, ≤ 60 s y `jti` único, e INF-U2-09 (`…/identity-edge/infrastructure-design/infrastructure-design.md`, línea 237) solo fija `VECTRA_TOKEN_URL`. La igualdad es una suposición del código de U0. RFC 7523 §3 dice que la `aud` de la aserción **identifica al servidor de autorización**; la URL de token «puede» usarse, pero Keycloak la compara con su emisor y con las URL que deriva de `KC_HOSTNAME`, no con la URL por la que le llegó la petición. La URL de envío (ruta de red) y la audiencia (identidad del servidor) son dos datos distintos, y esta tarea los separa.

Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Sin clúster (AUTONOMIA-01).

---

## Alcance

**Dentro**, en este orden:

1. **Verificar el inventario** de abajo contra el `main` de tu rama (U02-T21 mueve una línea en cuatro `values.yaml`). Lo que cambie va a la bitácora.
2. **U0, el cambio mínimo.** `ServiceTokenProvider` recibe un parámetro nuevo, **solo por nombre y sin valor por omisión**, `assertion_audience: str`; `_assertion` firma `"aud": self._assertion_audience`. La petición se sigue enviando a `token_url`. Una cadena vacía es `ValueError` al construir. `provider_from_env` lee `os.environ["VECTRA_ASSERTION_AUDIENCE"]` (el nombre: P-1), escrito así, literal, porque las pruebas de chart de U9 y U11 descubren las variables con una expresión regular sobre el código de `provider_from_env` (`bias-monitoring/tests/unit/test_chart.py`, línea 638; `product-metrics/tests/unit/test_chart.py`, línea 715). Si falta, falla al construir con un error que la nombra, como ya pasa con `VECTRA_TOKEN_URL`.
3. **Cada constructor directo** (inventario) pasa la audiencia, y cada lista de variables obligatorias que hoy trae `VECTRA_TOKEN_URL` gana la nueva.
4. **Charts.** Todo workload que rinde `VECTRA_TOKEN_URL` rinde `VECTRA_ASSERTION_AUDIENCE`, **derivada de `keycloak.issuer` en la plantilla** (P-3), con `required`. Los charts que piden token sin validar (`product-metrics`, `identity-edge/jobs`) ganan el valor `keycloak.issuer`, por la vía de U02-T21: producción por omisión en `chart/values.yaml`, kind y staging en `vectra-risk-gitops/values/<env>/product-metrics.yaml` (Applications regeneradas con `uv run python vectra-risk-gitops/generate.py`); en los jobs de U2, los tres entornos en `identity-edge/jobs/values/<env>.yaml` y el render regenerado con `make -C identity-edge render-jobs`.
5. **Pruebas** de «Criterios de aceptación»: unitarias en U0, medida contra un Keycloak real, mundo cerrado en `platform/tests/`, y los dobles de Keycloak de cada unidad exigiendo la `aud` configurada.
6. **Documentación:** `contracts/README.md` (línea 31) y `contracts/CHANGELOG.md` (entrada «Sin publicar», sin subir la versión: la línea base 0.1.0 sigue sin etiqueta y ningún esquema cambia); sub-viñeta `(U00-T04)` en §6 del plan de U0 junto a la línea 295; enmienda de una frase a INF-U2-09 (línea 237) con la variable nueva, porque `identity-edge/tests/strategies/jobs_design.py` lee el diseño; sección «Tras U00-T04» en `identity-edge/docs/emisor-de-tokens.md`; `CANDIDATAS.md`.

**Fuera** (recházalo aunque lo veas roto):

- El flujo de token: `grant_type`, el parámetro `audience` del formulario (la audiencia del **access token**, que no cambia), los scopes, la caché, `RENEW_BEFORE`, el candado, los reintentos y `deps.post_form_once`.
- `vectra_common.authn` (un solo emisor, `VECTRA_OIDC_ISSUER`) y cualquier valor de `keycloak.issuer`, `jwksUrl` o `tokenUrl` que ya esté en `main`.
- Keycloak y el gateway: `identity-edge/keycloak/`, `identity-edge/gateway/`, el realm. `platform/network/flows.yaml` y lo generado de la red.
- Pedir el token por la URL pública (no hay flujo de `vectra-app` a `api-gateway`).
- `identity-edge/tests/e2e/e2e_support.py` (línea 293) y `identity-edge/tests/load/identity.js` (línea 302): firman a mano con `aud` = URL **pública** de token, que Keycloak acepta (medido). Unificarlos con el emisor es candidata.
- Renombrar `VECTRA_TOKEN_AUDIENCE` del `model-validation-job` (ver P-1). OpenAPI, TypeScript y la versión de `contracts`.
- Desplegar, sincronizar o tocar el clúster.

---

## Inventario (comprobado al redactar sobre `065c284`; verifícalo)

**Quién firma aserciones y con qué `aud` hoy.**

| Quién | Cómo construye | `aud` hoy | ¿Tiene el emisor? | Ruta y línea |
|---|---|---|---|---|
| U0 `ServiceTokenProvider` | — | `token_url` | no lo recibe | `contracts/python/vectra_common/src/vectra_common/service_token.py` 60; envío en 73 |
| U0 `provider_from_env` | `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH`, `VECTRA_CLIENT_KEY_ID` | URL interna | — | mismo archivo, 91 a 100 |
| U2 `realm-drift`, `signing-key-age` | `provider_from_env("keycloak", ())` | URL interna | **no** (el chart solo trae `keycloak.tokenUrl`) | `identity-edge/jobs/keycloak_admin.py` 79; `jobs/chart/templates/identity-jobs.yaml` 7; `jobs/chart/values.yaml` 12 |
| U4 `governance-service` | **constructor directo**, `config.token_url` de `VECTRA_TOKEN_URL` | URL interna | sí (`VECTRA_OIDC_ISSUER`) | `governance/src/vectra_governance/service.py` 148 a 155; obligatorias en 64 a 72; `chart/templates/service.yaml` 73, 77 y 81 |
| U4 `model-validation-job` | **constructor directo**; el entorno se lo arma `governance-service` (`GOVERNANCE_JOB_TOKEN_URL` → `VECTRA_TOKEN_URL`) | URL interna | **no** | `governance/validation_job/vectra_validation/run.py` 96 a 103; `config.py` 71 y 75; `governance/src/vectra_governance/k8s_jobs.py` 110 y 130; `api.py` 356 |
| U7 `scoring-service`, `explainability-service` | `provider_from_env` como fábrica | URL interna | sí | `scoring-explainability/scoring/src/scoring/app.py` 178; `explainability/src/explainability/app.py` 169; `chart/templates/service.yaml` 75 y 77 |
| U8 `case-service`, `case-worker` | `provider_from_env` (cinco llamadas) | URL interna | `case-service` sí; **`case-worker` no** | `case-management/src/vectra_case/app.py` 89, 93 y 98; `worker.py` 147 y 153. Chart: solo en la rama `tarea/U08-T05` (`templates/_helpers.tpl` 59 a 65, ayudante `case-management.identity-env`) |
| U9 `bias-monitoring-service` | `provider_from_env` | URL interna | sí | `bias-monitoring/src/vectra_bias/app.py` 181; obligatorias en 51 a 58; `chart/templates/service.yaml` 61 y 64 |
| U9 `bias-monitoring-job` | `provider_from_env` (dos llamadas) | URL interna | **no** (el chart sí tiene `keycloak.issuer`) | `bias-monitoring/src/vectra_bias/run.py` 365-366; `chart/templates/cronjob.yaml` 61 |
| U11 `product-metrics` | `provider_from_env` | URL interna | **no** (el chart solo trae `keycloak.tokenUrl`) | `product-metrics/src/vectra_product/reader.py` 77; `chart/templates/deployment.yaml` 67; `chart/values.yaml` 13-14 |
| Operador y carga (fuera) | a mano, por el gateway | URL **pública** de token (aceptada) | — | `identity-edge/tests/e2e/e2e_support.py` 293; `identity-edge/tests/load/identity.js` 302 |

**No piden token de servicio** (comprobado con `grep` de `service_token` y `provider_from_env`): `decision-registry` (U3), `console/bff` (U10: solo valida, `console/bff/src/console_bff/app.py` 47), `model-serving`, `reference-model`, `core-banking-mock`, el `promotion-tool` de U4 (login de usuario con PKCE, `governance/promotion_tool/vectra_promotion/login.py`) y el Job `rt5-demo` de U8 (envía sin token; `templates/rt5-demo-job.yaml` en la rama de U08-T05).

**Por eso no vale reutilizar `VECTRA_OIDC_ISSUER`:** cinco workloads piden token sin validar (`bias-monitoring-job`, `product-metrics`, `model-validation-job`, los dos Jobs de U2) y `case-worker` tampoco la lleva.

**Choque de nombres.** `VECTRA_TOKEN_AUDIENCE` **ya existe** en `governance/validation_job/vectra_validation/config.py` (línea 75) y significa otra cosa: la audiencia del access token (por omisión `governance-service`). Nadie la fija en ningún chart. Por eso la variable nueva se llama `VECTRA_ASSERTION_AUDIENCE`.

**Dobles de Keycloak y pruebas que fijan la `aud` vieja.**

| Dónde | Qué hace hoy con la `aud` |
|---|---|
| `contracts/tests/unit/test_service_token.py` 87 y 90 | exige `aud == URL` (hay que invertirla) |
| `identity-edge/tests/unit/test_identity_jobs.py` 55 y 119 | exige `aud == design.token_url()` |
| `bias-monitoring/tests/doubles/http_doubles.py` 83 | exige `aud == <url>/token` |
| `bias-monitoring/tests/doubles/world.py` 76 | solo que haya aserción: **acepta cualquier `aud`** |
| `governance/tests/integration/test_service_build_app.py` 49 a 51; `test_container_start.py` 101-102; `tests/unit/test_validation_job_template.py` 174; `test_service_config.py` 119; `test_validation_job.py` 386 y 403 | **cualquier `aud`** |
| `product-metrics/tests/doubles/http_servers.py` 62 | **cualquier `aud`** |
| `scoring-explainability/tests/integration/test_app.py` 260 | **cualquier `aud`** |
| `case-management/tests/integration/test_service_shutdown.py` 55-56; `test_worker_shutdown.py` 66-67 | **cualquier `aud`** |
| `identity-edge/tests/strategies/fake_gateway_server.py` 209 | exige que termine en `/openid-connect/token` (camino del gateway: fuera) |

---

## Criterios de aceptación

Desde `vectra-risk/`. Guarda los logs con el prefijo `u00t04-`. Cada criterio de comportamiento lleva **rojo previo** en la bitácora, con su orden y su salida real.

- [ ] **CA-1 — U0: la aserción lleva la audiencia configurada y la petición va a la URL de token.** Pruebas nuevas o corregidas en `contracts/tests/unit/test_service_token.py`, con una URL de token y una audiencia **distintas**: (a) `aud` de la aserción == audiencia configurada y != URL de token; (b) el `poster` recibe la URL de token; (c) el conjunto de claims sigue siendo `iss`, `sub`, `aud`, `jti`, `iat`, `exp`, y el formulario conserva su `audience` (la del access token); (d) `provider_from_env` lee `VECTRA_ASSERTION_AUDIENCE`; (e) sin la variable, o vacía, falla **al construir** y el error la nombra; (f) `ServiceTokenProvider(...)` sin `assertion_audience` es `TypeError`.
  ```bash
  uv run pytest contracts/tests/unit/test_service_token.py -q -k "assertion_audience"
  ```
  Esperado: pasa, con al menos seis casos. **Rojo previo:** el commit de las pruebas va antes que el del arreglo; sobre ese commit la orden termina en 1.
- [ ] **CA-2 — Contra un Keycloak real (el criterio central).** `identity-edge/tools/measure_issuer.py` mide M-c dos veces con el `ServiceTokenProvider` de la rama, por el **host interno** desviado a `127.0.0.1:<puerto>`: con `assertion_audience` = emisor público → **200** y `iss` público; con `assertion_audience` = la URL interna de token (la `aud` vieja) → **400** `Invalid token audience`. El resultado va a la sección «Tras U00-T04» de la evidencia.
  ```bash
  mkdir -p platform/.tools/tmp
  uv run python identity-edge/tools/measure_issuer.py | tee platform/.tools/tmp/u00t04-medida.log
  grep -nE '^\| M-c \((aud configurada|aud antigua)' identity-edge/docs/emisor-de-tokens.md
  grep -cE 'eyJ[A-Za-z0-9_-]{20,}|PRIVATE KEY|client_assertion=' identity-edge/docs/emisor-de-tokens.md
  docker ps -a --format '{{.Names}}' | grep -ciE 'u02t21|u00t04'
  ```
  Esperado: dos filas, una con `200` y otra con `400`; `0`; `0`. El revisor repite la medida. Sin esta medida la tarea solo cambia una suposición por otra: **no se entrega sin ella**.
- [ ] **CA-3 — Mundo cerrado, rojo primero.** `platform/tests/test_token_issuer.py` ampliada: en cada entorno, todo contenedor que rinde `VECTRA_TOKEN_URL` o `GOVERNANCE_JOB_TOKEN_URL` rinde `VECTRA_ASSERTION_AUDIENCE`, y su valor es **igual** al emisor que Keycloak publica según su render (`KC_HOSTNAME` + `/realms/vectra`); uno que la rinde sin URL de token también es un fallo. Los workloads se descubren, no se listan.
  ```bash
  uv run pytest platform/tests/test_token_issuer.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -v
  ```
  Esperado: sobre el commit de la prueba y **sin** los charts, termina en 1 y nombra, por entorno, cada workload que pide token (como mínimo los ocho de `REQUESTERS`). Tras los charts, 0.
- [ ] **CA-4 — La prueba de mundo cerrado detecta cada desajuste.**
  ```bash
  uv run pytest platform/tests/test_token_issuer.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k "mutation and audience" -v
  ```
  Esperado: pasan, como mínimo: (i) audiencia = URL interna de token; (j) audiencia = emisor interno (`keycloak-admin…`); (k) la audiencia de staging en kind; (l) un workload con URL de token y sin audiencia; (m) audiencia = URL pública de token (Keycloak la acepta, pero aquí hay **un** valor: el emisor); (n) otro realm. Cada mensaje nombra el workload y el entorno. Las mutaciones (a) a (h) de U02-T21 siguen pasando.
- [ ] **CA-5 — Ningún workload ni constructor queda atrás.**
  ```bash
  mkdir -p platform/.tools/tmp
  grep -rlE 'VECTRA_TOKEN_URL' --include='*.yaml' --include='*.tpl' */chart identity-edge/jobs/chart identity-edge/jobs/rendered | sort > platform/.tools/tmp/u00t04-url.txt
  grep -rlE 'VECTRA_ASSERTION_AUDIENCE' --include='*.yaml' --include='*.tpl' */chart identity-edge/jobs/chart identity-edge/jobs/rendered | sort > platform/.tools/tmp/u00t04-aud.txt
  diff platform/.tools/tmp/u00t04-url.txt platform/.tools/tmp/u00t04-aud.txt
  grep -rnE '"aud": *self\._token_url|assertionAudience' contracts/python */chart identity-edge/jobs/chart
  grep -rn 'VECTRA_ASSERTION_AUDIENCE' governance/src/vectra_governance/k8s_jobs.py governance/validation_job/vectra_validation/config.py
  ```
  Esperado: `diff` sin salida; el segundo `grep` sin salida (ningún valor nuevo de chart: se deriva de `keycloak.issuer`); el tercero, una línea por archivo. `uv run mypy --strict contracts/python` y el `lint` de cada unidad tocada en 0: un constructor sin `assertion_audience` no pasa `mypy`.
- [ ] **CA-6 — Los dobles ya no esconden el defecto.** Cada doble de la tabla que responde `/token` a un `ServiceTokenProvider` real decodifica la aserción (basta sin verificar la firma donde hoy no se verifica) y **rechaza** la que no trae la audiencia configurada; en cada unidad, URL de token y audiencia son distintas en las pruebas. Cada unidad tiene al menos una prueba con `assertion_audience` en el nombre, fuera de las pruebas que necesitan una imagen.
  ```bash
  uv run pytest identity-edge/tests/unit/test_identity_jobs.py -q -k assertion_audience
  uv run pytest governance/tests -q -k assertion_audience
  uv run pytest bias-monitoring/tests -q -p no:cacheprovider -m "not simulation" -k assertion_audience
  uv run pytest product-metrics/tests/integration -q -p no:cacheprovider -m "not volume" -k assertion_audience
  uv run pytest scoring-explainability/tests -q -p no:cacheprovider --import-mode=importlib -k assertion_audience
  uv run pytest case-management/tests -q -p no:cacheprovider --rootdir=case-management -k assertion_audience
  ```
  Esperado: cada orden pasa con al menos un caso. **Rojo previo, por mutación:** con `service_token.py` devuelto a `"aud": self._token_url` (sin commit; se revierte), las seis órdenes terminan en 1. La bitácora trae las seis salidas.
- [ ] **CA-7 — El Job de U4 recibe la audiencia.** Una prueba de `governance/tests/unit/` comprueba que `job_manifest` pone `VECTRA_ASSERTION_AUDIENCE` con el valor de la configuración del servicio (P-2), y que `vectra_validation.config.from_env` falla con `missing_env:VECTRA_ASSERTION_AUDIENCE` si falta.
  ```bash
  uv run pytest governance/tests/unit -q -k "assertion_audience"
  ```
  Esperado: pasa, con los dos casos. `VECTRA_TOKEN_AUDIENCE` del Job conserva su significado y su valor por omisión.
- [ ] **CA-8 — Lo generado está al día.**
  ```bash
  uv run python vectra-risk-gitops/generate.py --check
  make -C identity-edge check-jobs-rendered policy-jobs policy-jobs-u1
  for u in governance scoring-explainability bias-monitoring product-metrics; do make -C $u policy-chart policy-chart-u1 || break; done
  git diff --exit-code origin/main -- contracts/openapi contracts/ts
  ```
  Esperado: todo en 0. El OpenAPI y el TypeScript no cambian.
- [ ] **CA-9 — Cambio mínimo.**
  ```bash
  git diff origin/main -- contracts/python/vectra_common/src/vectra_common/service_token.py | grep -E '^[+-] ' | grep -vE 'assertion_audience|ASSERTION_AUDIENCE|aud|"""|^\+ *#|ValueError'
  git diff --name-only origin/main | grep -E 'identity-edge/(keycloak|gateway)/|platform/network/|vectra_common/(authn|deps)\.py|contracts/(openapi|ts)/'
  ```
  Esperado: las dos sin salida.
- [ ] **CA-10 — `make check` (RL-4; ver P-4).** En serie, con `uptime` y la duración de cada uno:
  ```bash
  export TMPDIR=$PWD/platform/.tools/tmp
  for u in contracts platform identity-edge governance scoring-explainability bias-monitoring product-metrics case-management; do uptime; make -C $u check || break; done
  ```
  Esperado: rc 0 en los ocho. Para `traceability.py --all` rige `DECISIONES-LOOP.md` §6. Una prueba con límite de tiempo que falle por carga se repite una vez con la máquina más libre y se anota.
- [ ] **CA-11 — Documentación y candidatas.**
  ```bash
  grep -n "VECTRA_ASSERTION_AUDIENCE" contracts/README.md contracts/CHANGELOG.md aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md
  grep -n "U00-T04" aidlc-docs/construction/plans/contracts-code-generation-plan.md CANDIDATAS.md identity-edge/docs/emisor-de-tokens.md
  uv run python platform/tests/test_links.py
  ```
  Esperado: cada `grep` da al menos una línea por archivo; los enlaces en 0. En `CANDIDATAS.md`: la entrada de U02-T21 «U0, `vectra_common.service_token` y U2, `KC_HOSTNAME_BACKCHANNEL_DYNAMIC`» y la de la línea 65 quedan «Resuelta (U00-T04)».

---

## Cambios permitidos, archivo por archivo

| Archivo | Cambio |
|---|---|
| `contracts/python/vectra_common/src/vectra_common/service_token.py` | parámetro `assertion_audience`, `aud` de la aserción, lectura de la variable, docstrings |
| `contracts/tests/unit/test_service_token.py`, `contracts/README.md`, `contracts/CHANGELOG.md` | CA-1 y documentación. Si `contracts/tests/unit/test_cross_unit_contract.py` fija las variables de entorno, se añade la nueva |
| `governance/src/vectra_governance/service.py`, `api.py`, `k8s_jobs.py`; `governance/validation_job/vectra_validation/config.py`, `run.py` | la obligatoria nueva, el campo de configuración, el campo de `JobSpec` y el entorno del Job |
| `bias-monitoring/src/vectra_bias/app.py` (lista `REQUIRED` y su tabla), `run.py` (docstring) | la obligatoria nueva |
| `product-metrics/src/vectra_product/main.py`, `identity-edge/jobs/keycloak_admin.py` | solo docstrings que listan las variables |
| `governance/chart/templates/service.yaml`, `scoring-explainability/chart/templates/service.yaml`, `bias-monitoring/chart/templates/service.yaml` y `cronjob.yaml`, `product-metrics/chart/templates/deployment.yaml`, `identity-edge/jobs/chart/templates/identity-jobs.yaml` | una línea de entorno junto a `VECTRA_TOKEN_URL`, derivada de `keycloak.issuer` con `required` |
| `product-metrics/chart/values.yaml`; `vectra-risk-gitops/values/kind/product-metrics.yaml` y `values/staging/product-metrics.yaml` (nuevos); `vectra-risk-gitops/apps/` regenerado | `keycloak.issuer` |
| `identity-edge/jobs/values/kind.yaml`, `staging.yaml`, `prod.yaml`; `identity-edge/jobs/rendered/` regenerado | `keycloak.issuer` |
| `case-management/chart/templates/_helpers.tpl` | **solo si U08-T05 ya está en `main`** (ver «Ramas en curso») |
| Pruebas y dobles de la tabla de dobles, y los `test_chart.py` de cada unidad | exigir la audiencia; añadir la variable a los entornos de prueba |
| `platform/tests/test_token_issuer.py` | CA-3 y CA-4 |
| `identity-edge/tools/measure_issuer.py`, `identity-edge/docs/emisor-de-tokens.md` | M-c con el proveedor corregido; sección «Tras U00-T04». Las filas de U02-T21 no se reescriben |
| `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-09), `aidlc-docs/construction/plans/contracts-code-generation-plan.md` (§6) | una frase y una sub-viñeta, sin reescribir lo que hay |
| `bitacoras/U00-T04.md`, `CANDIDATAS.md` | bitácora y candidatas |

`src/` de `scoring-explainability`, `case-management` y `product-metrics` **no cambia**: usan `provider_from_env`.

---

## Ramas en curso

- **U08-T05** (`tarea/U08-T05`): su chart rinde `VECTRA_TOKEN_URL` para `case-service` y `case-worker` con el ayudante `case-management.identity-env`, y trae `keycloak.issuer`. **Si ya está en `main`** al crear tu rama, añades la línea al ayudante y entra en CA-5, CA-8 (`policy-chart` de U8) y CA-10. **Si llega después**, no la toques: la prueba de mundo cerrado pondrá `main` en rojo para `case-service` y `case-worker` hasta que el orquestador lo concilie al fusionar. Las pruebas de `case-management/tests/` (CA-6) se corrigen en los dos casos: ya están en `main`. Anota en la bitácora qué caso encontraste.
- **U10-T05:** `console-bff` no pide token de servicio. Nada que hacer; la prueba no lo alcanza porque no rinde `VECTRA_TOKEN_URL`.
- **U12-T02:** firma sus propias aserciones con `aud` = emisor. No depende de esta tarea ni se toca. La candidata de U02-T21 que le pide ejercer `vectra_common.service_token` por el host interno sigue abierta para U12 Paso 18.

---

## Preguntas abiertas

**P-1 — De dónde sale la `aud` de la aserción. NECESITA AL USUARIO** (U02-T21 la dejó como «decide el usuario»; corrige un supuesto de U0 y añade una variable a todo chart que pide token).
- **(a) Variable nueva, obligatoria donde hoy lo es `VECTRA_TOKEN_URL`, sin valor por omisión** (recomendada). Falla al arrancar, no con un 400 en tiempo de ejecución. Nombre: **`VECTRA_ASSERTION_AUDIENCE`**, porque `VECTRA_TOKEN_AUDIENCE` ya existe en el Job de U4 con otro significado (inventario). Si el usuario prefiere `VECTRA_TOKEN_AUDIENCE`, hay que renombrar antes la del Job.
- (b) Reutilizar `VECTRA_OIDC_ISSUER`. No hay variable nueva, pero seis workloads que piden token no la tienen (inventario) y tendrían que recibir una variable cuyo nombre dice «valido tokens» sin validarlos.
- (c) `aud` = URL de token si la variable falta. Compatible hacia atrás, y por eso mismo deja vivo el defecto en cualquier chart que la olvide. No recomendada.

**Recomendación: (a).** La tarea está escrita con (a); con otra respuesta se reescriben CA-1, CA-3 y CA-5 antes de despachar.

**P-2 — Cómo recibe la audiencia el `model-validation-job`.**
- **(i) `governance-service` le pasa la suya** (`VECTRA_ASSERTION_AUDIENCE` → `JobSpec` → entorno del Job) (recomendada): la audiencia identifica al realm, no al camino de red, y es la misma para los dos. Sin variable nueva en el chart.
- (ii) Una `GOVERNANCE_JOB_ASSERTION_AUDIENCE` aparte, como `GOVERNANCE_JOB_TOKEN_URL`.

**Recomendación: (i).** Si no hay respuesta, rige (i).

**P-3 — Charts: ¿derivar de `keycloak.issuer` o un valor propio?** Derivar deja un solo dato por entorno y hace imposible que emisor y audiencia diverjan; un `keycloak.assertionAudience` propio solo serviría si Keycloak aceptara una audiencia distinta de su emisor, y la medida dice que no hace falta. **Recomendación: derivar.** Si no hay respuesta, rige derivar (CA-5 lo comprueba).

**P-4 — Qué `make check` corre. DESVIARSE DE (a) NECESITA AL USUARIO.** RL-4 pide el `make check` de la unidad de la tarea y las pruebas de U1 que el diff toque; aquí el diff toca código, charts o pruebas de ocho unidades. Tiempos de `bitacoras/U11-T03.md` (líneas 274 a 287, carga 1 a 8): `contracts` 154 s, `platform` ≈ 330 s (`check-local` 200 s más `check-tools` 129 s), `identity-edge` 1 133 s, `governance` 607 s, `scoring-explainability` 393 s, `bias-monitoring` 1 306 s, `product-metrics` 526 s, `case-management` 241 s. **Total ≈ 4 700 s, unos 80 min en serie**; con la carga de hoy (al redactar, 16,9) cuenta con 2 a 2,5 h y con algún fallo por límite de tiempo.
- **(a) Los ocho en serie (CA-10)** (recomendada): U0 es código compartido y de este arreglo dependen las cuatro demos; es lo que hizo U00-T03 (su CA-9).
- (b) `contracts` y `platform` completos, más, de cada una de las otras seis, `lint`, `policy-chart`, `policy-chart-u1`, `test_chart.py` y las pruebas de configuración y de token (CA-6 sin `-k`): unos 25 min. Deja sin correr las suites de integración con imagen de U4, U9 y U11.

**Recomendación: (a).** Si no hay respuesta, rige (a).

**P-5 — Los firmantes a mano de U2** (`e2e_support.py` 293, `identity.js` 302). Funcionan (URL pública de token). **Recomendación: no tocarlos; candidata.** Si no hay respuesta, rige esto.

---

## Restricciones del entorno

Las de U02-T21, sin cambios:

- **`/tmp` es un tmpfs con cuota y suele estar casi lleno.** No copies el repositorio allí. Temporales en `platform/.tools/tmp` (`export TMPDIR=$PWD/platform/.tools/tmp`): sin esto `promtool` falla con `disk quota exceeded` en los `make check` de `platform` e `identity-edge`.
- **Máquina compartida y cargada** (al redactar: carga 16,9; 5 GiB disponibles de 14). `uptime` junto a cada medida y cada `make`. Los `make`, en serie.
- **Keycloak ocupa ≈ 1 GiB.** Antes de arrancarlo mira `free -g` y `docker ps`: si otro agente tiene un Keycloak arriba o quedan menos de 2 GiB, espera. Límite del contenedor: 1,5 GiB. La imagen ya está descargada y autorizada (`DECISIONES-LOOP.md` §10); se lee de la línea `FROM` de `identity-edge/keycloak/Dockerfile`.
- **Host dinámico:** `127.0.0.1:<puerto>` con un puerto libre al azar, publicado solo en `127.0.0.1`; nunca el 443, el 8080, el 8081 ni el 8443. **`vectra.localtest.me` es el kind de esta máquina: nunca es el host de una URL**, solo aparece en `KC_HOSTNAME`, en `X-Forwarded-Host` y en la `aud`. Nunca el clúster kind.
- **Docker se comparte.** El contenedor lo levanta y lo borra el guion (con sus volúmenes, también si falla). No borres la imagen ni toques los contenedores de kind (`vectra-*`, `kind-registry`) ni los de otros.
- **Sin clúster.** Nada de `kubectl`, `helm install`, `argocd` ni sync. `helm template` sí.
- **`platform/.tools` y `platform/.charts` no están versionados.** Crea `platform/.tools/` real en tu worktree y copia o enlaza **solo** `platform/.tools/bin`; llena `platform/.charts` con `make -C platform charts`. `node_modules` tampoco: `npm ci` antes de `make -C contracts check`.
- **No toques el árbol principal ni otros worktrees. No uses `git stash`** (la pila se comparte): para los rojos, ordena los commits o revierte a mano.

---

## Notas

- **Orden de commits:** (1) pruebas de U0 en rojo; (2) arreglo de U0 y constructores; (3) prueba de mundo cerrado en rojo; (4) charts, values y generados; (5) dobles y pruebas de cada unidad; (6) medida y documentación. Los hashes de los rojos van en la bitácora.
- **Bitácora:** `bitacoras/U00-T04.md`, con el acuse (hash de este archivo), el inventario verificado, cada rojo y cada verde con su salida, la medida de CA-2, la respuesta aplicada a cada P-n, el caso de U08-T05 y la carga de cada corrida.
- **Lo que esta tarea no demuestra:** que el flujo completo funcione en kind con el realm real (U12 Paso 18). Aquí queda medido que Keycloak 26.8.1 acepta la aserción de U0 por el host interno, y atado que cada workload la firma con el emisor de su entorno.
- **Si la medida de CA-2 no da 200**, para y reporta: la corrección sería otra y no es de esta tarea.
- Archivos que se **modifican en su sitio**. Nada de duplicados con sufijo. Otro defecto que veas va a `CANDIDATAS.md`, no al diff.
