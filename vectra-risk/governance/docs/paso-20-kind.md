# Guía del operador: Paso 20 de U4 `governance` en kind

Paso 20 del plan de U4 (`aidlc-docs/construction/plans/governance-code-generation-plan.md`), acotado a la demo (`demo-recorte-funcional.md` §3 U4; `demo-kind-alcance.md` §6, RL-1 a RL-5). Lo ejecuta **un operador** (una persona) después de que el PR de U04-T07 esté aprobado (AUTONOMIA-01): el codificador escribió esta guía, los scripts de `governance/docs/kind/` y las plantillas de evidencia, y **no tocó ningún clúster**. Nada de lo de abajo se ha ejecutado todavía.

Todos los comandos corren desde `vectra-risk/`, con el contexto `kind-vectra`. Cada sección dice el comando, la salida esperada y el archivo de evidencia, que sale de la plantilla de `aidlc-docs/construction/governance/evidence/kind/` (comando, salida y resultado esperado contra el obtenido).

Entra el **arranque** (P-7: política activa y modelo de referencia activo) y los escenarios **2** (validación de referencia), **3** (promoción), **4** (rollback) y **7** (propagación del `freeze`, hasta `serving-config`). **Se difieren** el 1 (k6, T3), el 5 (`governance-db` pausada), el 6 (registro caído), el 8 (`branch-protection-check`, Paso 14) y el 9 (US-306).

## 1. Requisitos previos y orden (RL-5)

| Qué | Por qué | Quién |
|---|---|---|
| U04-T06 y **U04-T08** fusionados | El chart y el punto de entrada `vectra_governance.service`: sin él el pod no arranca (`revisiones/U04-T06/ronda-1.md`, F-01) | Ya en `main` |
| U1, U2 y U3 sanos en kind | Postgres (`governance-db`), MinIO, Vault, Keycloak, el registro de decisiones | Operador (`platform/runbooks/install.md`) |
| `make -C reference-model release` y `verify-release` | El paquete base, el dataset y `reference-policy.json` (U5, `reference-model/docs/release.md` pasos 1 y 2) | Operador |
| U6 C+D fusionado | La plantilla del `InferenceService` y el esquema de values de `promotion-tool` (escenarios 3 y 4) | Ya en `main` si el PR de U6 lo está |
| `source "${VECTRA_E2E_KEYS_DIR:-${XDG_RUNTIME_DIR:-/tmp}/vectra-e2e-keys}/env"` | Deja `SYNTH_*`, `VECTRA_E2E_BASE_URL`, `VECTRA_E2E_CA_BUNDLE` y `VECTRA_E2E_CLIENT_KEYS_DIR` (`platform/kind/seed-vault.sh identity`) que usa `token.sh` | Operador |
| `argocd login` y la función `sync` de `platform/runbooks/install.md` §7 | El sync manual de la wave 5 | Operador |
| Firma de commits configurada (`git commit -S`) y `gh` autenticado | `promotion-tool` abre PR de un solo commit firmado (BR-U4-09) | Operador |
| Árbol de trabajo limpio y en una rama basada en `main` | `promotion-tool` falla con `working_tree_dirty` | Operador |

Orden de la ruta crítica: (1) imágenes, (2) sync de la wave 5, (3) política activa, (4) modelo de referencia, que cubre los escenarios 2 y 3 y deja el arranque listo **antes de U6 Paso 11**, (5) escenario 4, (6) escenario 7.

Lo que esta guía **no pudo comprobar** (se verifica por primera vez al ejecutarla): que `kubectl run -i --rm` con `--override-type=strategic` entregue el stdin al pod antes de que el cliente lo lea, que la malla acepte las llamadas del pod `console-bff` y que `kubectl exec` a cada réplica funcione con la raíz de solo lectura. Si algo de eso falla, es un hallazgo: anótalo en la evidencia y repórtalo, no lo rodees con un Secret ni con un archivo temporal.

## 2. Imágenes

Evidencia: `evidence/kind/01-imagenes.md`.

Mide la memoria de `vectra-app` **antes** de instalar governance (DD-3 b):

```bash
governance/docs/kind/memoria.sh antes > aidlc-docs/construction/governance/evidence/kind/09-memoria.md
```

Build y push a `kind-registry` de `governance` y de `model-validation-job`, con el digest real de cada una (sin firma, SBOM ni attestation: T1):

```bash
governance/docs/kind/imagenes.sh
```

Esperado: `make -C governance image` y `image-validation` terminan en 0, los dos `docker push` terminan con `digest: sha256:...`, y al final imprime el trozo de values:

```text
image:
  digest: sha256:<64 hex>
validation:
  image:
    digest: sha256:<64 hex>
```

**PR de digests (T1: sin firma).** Con ese trozo crea `vectra-risk-gitops/values/kind/governance.yaml`, regenera la Application y comprueba:

```bash
uv run python vectra-risk-gitops/generate.py
uv run python vectra-risk-gitops/generate.py --check
git diff --stat
```

Esperado: el diff trae `values/kind/governance.yaml` (nuevo) y `apps/kind/governance.yaml` (una línea `valueFiles`), y `--check` termina en 0. Abre el PR, fusiónalo (lo revisa una persona) y sigue con el sync. Si el digest que publica `docker push` no es el que quedó en el archivo, el pod queda en `ImagePullBackOff`.

## 3. Sync de la wave 5 y comprobación

Evidencia: `evidence/kind/02-sync.md`.

```bash
argocd app sync governance && argocd app wait governance --health --timeout 900
kubectl --context kind-vectra -n vectra-app get job governance-migration
kubectl --context kind-vectra -n vectra-app rollout status deploy/governance-service --timeout=180s
kubectl --context kind-vectra -n vectra-app get pods -l app.kubernetes.io/name=governance-service
```

Esperado: la Application `Healthy`; el Job `governance-migration` con `COMPLETIONS 1/1`; el `rollout` termina con `successfully rolled out`; 2 pods `Running` con `READY 2/2` (servicio y proxy de Linkerd). Si la migración no terminó, el servicio no está listo: mira `kubectl logs job/governance-migration -n vectra-app`.

Mide la memoria **después**:

```bash
governance/docs/kind/memoria.sh despues >> aidlc-docs/construction/governance/evidence/kind/09-memoria.md
```

## 4. Arranque (P-7): política activa

Evidencia: `evidence/kind/03-arranque-politica.md`.

Sigue **`governance/runbooks/kind-politica-de-referencia.md`** de punta a punta: `cro-2` propone y `cro-1` aprueba (P-9), con los tokens por stdin y sin Secrets. Cada comando está completo ahí. Pega en la evidencia la salida de los pasos 2 y 3 y de la verificación. La vigencia normativa de `reference-policy.json` debe cubrir la fecha de la demo (enmienda §5.3): si no, se reporta como hallazgo.

Esperado al final del runbook: `GET /v1/policies` con la política en `"state":"activa"`.

La lectura de vuelta de `serving-config` con `policy_version_id` solo existe cuando hay también una versión `activa` del modelo, así que se hace al final del escenario 3 (sección 6.4).

## 5. Arranque (P-7): modelo de referencia, escenarios 2 y 3

Cubre a la vez el escenario 2 (validación) y el 3 (promoción de punta a punta). Define una vez el identificador del modelo base:

```bash
MV="$(python3 -c 'import json; print(json.load(open("reference-model/.out/package/manifest.json"))["model_version_id"])')"
echo "$MV"
```

### 5.1 Subir y registrar (US-201)

Evidencia: `evidence/kind/04-arranque-modelo.md`.

Sube el paquete y el dataset al MinIO de kind con `reference-model/docs/release.md`, **pasos 3** (y los de la verificación 1 a 3). El paquete queda en `s3://model-store/<model_version_id>/<archivo>`.

**Convención de rutas (candidata de U05-T04, [PENDIENTE U4]).** Del lado de U4 está confirmada por código: `S3PackageStore` lee `s3://model-store/<model_version_id>/<archivo>` y rechaza otro bucket (`governance/src/vectra_governance/s3_store.py`), y el registro vuelve a calcular el SHA-256 de lo que lee. Al registrar, comprueba que coincide con lo que subió `release.md` y anótalo en la evidencia: el `POST` responde 200 con `state: registrado` si coincide, y 422 `validation_error` con el motivo (`codigo:archivo`) si no. Si da 422 por una ruta distinta, es un defecto de `release.md` (se corrige ese documento, no el paquete) y se registra aquí.

El registro lo hace `ingeniero-1` (rol `ingeniero_riesgo`, con MFA); el cuerpo lo arma `registro-cuerpo.sh` con esa convención:

```bash
{ governance/docs/kind/token.sh ingeniero-1; governance/docs/kind/registro-cuerpo.sh reference-model/.out/package; } | governance/docs/kind/llamar.sh modelo-registra POST /v1/models
```

Esperado: `200` y un JSON con `"model_version_id":"<MV>"` y `"state":"registrado"`.

### 5.2 Escenario 2: validación con el modelo de referencia (US-202)

Evidencia: `evidence/kind/05-escenario-2-validacion.md`. Requisito: la política `activa` (sección 4), si no la respuesta es 409.

Pide la validación y guarda el nombre del Job; el tiempo corre desde aquí:

```bash
date -u +%FT%TZ
JOB="$(governance/docs/kind/token.sh ingeniero-1 | governance/docs/kind/llamar.sh modelo-valida POST "/v1/models/$MV/validations" | sed -E 's/^[0-9]{3} //' | python3 -c 'import json, sys; print(json.load(sys.stdin)["job_name"])')"
echo "$JOB"
```

Esperado: un `validation-...` y el estado del modelo en `en_validacion`. Espera al Job y comprueba que terminó `Complete` **con el proxy de Linkerd detenido** (Paso 13: sidecar nativo):

```bash
kubectl --context kind-vectra -n vectra-staging wait --for=condition=complete "job/$JOB" --timeout=1800s
kubectl --context kind-vectra -n vectra-staging get job "$JOB"
kubectl --context kind-vectra -n vectra-staging get pods -l "job-name=$JOB"
date -u +%FT%TZ
```

Esperado: `condition met`; el Job con `COMPLETIONS 1/1`; el pod en `Completed` (no `NotReady` ni `Running` por el proxy). La diferencia entre las dos horas es **menor de 30 minutos** (NFR-U4-12).

Lee el informe:

```bash
governance/docs/kind/token.sh ingeniero-1 | governance/docs/kind/llamar.sh modelo-lee GET "/v1/models/$MV" | sed -E 's/^[0-9]{3} //' | python3 -c 'import json, sys; m = json.load(sys.stdin); r = m["validation_report"]; print(m["state"], r["auc_roc"], r["sync_check"]["passed"], len(r["initial_disparity"]["attributes"]))'
```

Esperado: `lista_para_aprobacion`, un AUC (`0.xxxx`), `True`, y un número de atributos **mayor que 0** (`initial_disparity` no vacía). Si el Job falla al hablar con MinIO, la firma SigV4 de `vectra_validation/s3.py` solo se había probado contra un doble (candidata de U04-T05 en `CANDIDATAS.md`): anótalo como hallazgo. Si el estado es `validacion_fallida`, mira el informe (`sync_check.failure_reason`) y los logs del Job: `kubectl -n vectra-staging logs job/$JOB -c model-validation-job`.

### 5.3 Aprobación

El CRO aprueba el modelo (rol `cro`, con MFA; distinto de quien lo registró, BR-U4-10):

```bash
{ governance/docs/kind/token.sh cro-1; printf '%s\n' '{"decision":"aprobado"}'; } | governance/docs/kind/llamar.sh modelo-aprueba POST "/v1/models/$MV/approval"
```

Esperado: `204` y el estado `aprobado` (`GET /v1/models/$MV`).

### 5.4 Escenario 3: promoción de punta a punta (US-204)

Evidencia: `evidence/kind/06-escenario-3-promocion.md`. `promotion-tool` entra por el login OIDC con PKCE del cliente `promotion-tool` (abre el navegador; entra como `ingeniero-1` con su TOTP). El token vive solo en memoria. Las variables de abajo no son secretos:

```bash
API=https://vectra.localtest.me/api/promotion
ISS=https://vectra.localtest.me/auth/realms/vectra
DIFF='kubectl --context kind-vectra diff -f -'
export SSL_CERT_FILE="$VECTRA_E2E_CA_BUNDLE"
uv run promotion-tool --issuer "$ISS" --api "$API" list-promotable
```

Esperado: una línea `<MV> aprobado isvc-<8 hex>`.

**PR 1 (promoción, un solo commit firmado, con la evidencia del `helm template` y del `kubectl diff` en el cuerpo):**

```bash
uv run promotion-tool --issuer "$ISS" --api "$API" --repo .. --env kind --diff-command "$DIFF" create-promotion-pr "$MV"
```

Esperado: la URL de un PR que agrega la entrada `prod` de `<MV>` en `values/kind/model-serving.yaml`. Una persona lo revisa y lo fusiona. Después, el sync manual del serving (wave 6) y la espera de los pods:

```bash
argocd app sync model-serving && argocd app wait model-serving --health --timeout 900
kubectl --context kind-vectra -n vectra-serving get inferenceservice
```

Esperado: un `isvc-<8 hex>` en `READY True`. Marca la versión activa (`mark_active`: la entrada ya debe estar declarada en `prod`, si no `not_promoted_in_values`):

```bash
uv run promotion-tool --issuer "$ISS" --api "$API" --repo .. --env kind --diff-command "$DIFF" mark-active "$MV" --evidence "arranque de la demo en kind: modelo de referencia validado y aprobado"
```

Esperado: imprime el `isvc-<8 hex>` y el modelo pasa a `activo`. Comprueba:

```bash
governance/docs/kind/token.sh cro-1 | governance/docs/kind/llamar.sh modelo-lee GET "/v1/models/$MV" | sed -E 's/^[0-9]{3} //' | python3 -c 'import json, sys; m = json.load(sys.stdin); print(m["state"], m["inference_service"])'
```

Esperado: `activo isvc-<8 hex>`. **Lectura de vuelta de `serving-config`** (P-7), por loopback en una réplica con un token de servicio de `scoring-service` (la malla solo admite esa ruta a scoring y a case, que todavía no existen; el servicio valida el token, no la identidad del pod):

```bash
POD="$(kubectl --context kind-vectra -n vectra-app get pods -l app.kubernetes.io/name=governance-service -o jsonpath='{.items[0].metadata.name}')"
governance/docs/kind/token.sh --servicio scoring-service governance:read-serving | kubectl --context kind-vectra -n vectra-app exec -i "$POD" -c governance-service -- python -c 'import sys, urllib.request; r = urllib.request.Request("http://127.0.0.1:8080/v1/serving-config", headers={"Authorization": "Bearer " + sys.stdin.readline().strip()}); print(urllib.request.urlopen(r, timeout=5).read().decode())'
```

Esperado: un JSON con `model_version_id` igual a `$MV`, `state: activo`, el `policy_version_id` de la sección 4, `inference_service` y un `etag`.

Cuando el modelo ya sirve y no hay versión anterior, no hay PR 2 (`post-activation-pr` baja a la anterior, y aquí no la hay).

## 6. Escenario 4: rollback a la versión `inactivo` (US-208)

Evidencia: `evidence/kind/07-escenario-4-rollback.md`. Necesita una segunda versión que pase el registro: usa la corrida 1 de la variante `rt2-demo` de U5 (`reference-model/.out/proxy/run-1`, solo en kind; `release.md` paso 5 ya la subió). Llámala M2; el modelo base `$MV` es M1.

```bash
MV2="$(python3 -c 'import json; print(json.load(open("reference-model/.out/proxy/run-1/manifest.json"))["model_version_id"])')"
echo "$MV2"
{ governance/docs/kind/token.sh ingeniero-1; governance/docs/kind/registro-cuerpo.sh reference-model/.out/proxy/run-1; } | governance/docs/kind/llamar.sh modelo2-registra POST /v1/models
```

Valida y aprueba M2 como en 5.2 y 5.3 (con `$MV2`). Promuévela como en 5.4 (PR 1, merge, sync, `mark-active "$MV2"`): al activarse M2, governance deja a M1 `inactivo` en la misma transacción (BR-U4-02). Después, el PR 2 baja a M1 a 1 réplica:

```bash
uv run promotion-tool --issuer "$ISS" --api "$API" --repo .. --env kind --diff-command "$DIFF" post-activation-pr "$MV"
```

Merge y `argocd app sync model-serving`. Confirma `inactivo`:

```bash
governance/docs/kind/token.sh cro-1 | governance/docs/kind/llamar.sh modelo-lee GET "/v1/models/$MV" | sed -E 's/^[0-9]{3} //' | python3 -c 'import json, sys; print(json.load(sys.stdin)["state"])'
```

Esperado: `inactivo`. **El rollback** (US-208): el PR que devuelve a M1 a los mínimos de producción **antes** de activarla, el merge, el sync y `mark-active`:

```bash
uv run promotion-tool --issuer "$ISS" --api "$API" --repo .. --env kind --diff-command "$DIFF" rollback-pr "$MV"
```

Esperado: la URL de un PR de un commit que cambia la entrada de `<MV>` de `inactive` a `prod`. Fusiónalo, `argocd app sync model-serving`, espera los pods de M1 en `READY` y:

```bash
uv run promotion-tool --issuer "$ISS" --api "$API" --repo .. --env kind --diff-command "$DIFF" mark-active "$MV" --evidence "rollback a la version inactiva (US-208)"
```

Esperado: `$MV` pasa a `activo` y `$MV2` a `inactivo` (`GET /v1/models/<id>`); `serving-config` (la lectura por loopback de 5.4) trae `model_version_id` igual a `$MV` y un `etag` distinto. Cierra con el PR 2 de M2 (`post-activation-pr "$MV2"`), merge y sync, para dejar el entorno sin una versión inactiva a 2 réplicas.

## 7. Escenario 7: propagación del `freeze` en 6 s como máximo (hasta `serving-config`)

Evidencia: `evidence/kind/08-escenario-7-freeze.md`. Con U7 y U9 ausentes se mide solo hasta `serving-config`: el `etag` y el estado cambian en las 2 réplicas. **El escenario queda pendiente hasta U7 Paso 18** (la primera `FailClosed(model_frozen)` de scoring), y la prueba de extremo a extremo la mide U12 (NFR-U4-06, NFR-U4-02).

```bash
governance/docs/kind/medir-freeze.sh "$MV"
```

El script sondea `serving-config` en cada réplica (`kubectl exec` por loopback, token de servicio de `scoring-service`), dispara el `freeze` por la misma vía con un token de `bias-monitoring-job` (la malla solo lo admite a esa identidad, y el servicio exige su scope `governance:freeze`) y un `FreezeContext` válido de `freeze-cuerpo.sh`, y mide cuánto tarda cada réplica en ver otro `etag`. Los tokens entran por stdin. Esperado:

```text
governance-service-<a> cambio_en=<s>
governance-service-<b> cambio_en=<s>
maximo=<s>
```

Con `maximo` de **6 o menos**. `$MV` debe estar `activo` (el `freeze` solo alcanza a la versión activa). Reactiva el modelo después (`cumplimiento-1`, rol `cumplimiento`, con MFA, BR-U4-03):

```bash
{ governance/docs/kind/token.sh cumplimiento-1; printf '%s\n' '{"action":"reactivar","justification":"fin de la prueba de propagacion del freeze en kind"}'; } | governance/docs/kind/llamar.sh modelo-reactiva POST "/v1/models/$MV/frozen-resolution"
```

Esperado: `204` y el modelo de vuelta en `activo`.

## 8. Memoria (DD-3 b)

Evidencia: `evidence/kind/09-memoria.md` (lo escribieron las secciones 2 y 3). Con governance ya instalado y los modelos servidos, vuelve a medir y compara con la medición de antes:

```bash
governance/docs/kind/memoria.sh con-modelos >> aidlc-docs/construction/governance/evidence/kind/09-memoria.md
```

Anota en la evidencia la suma de memoria de los pods de `vectra-app` antes y después, y si el perfil de kind (`memoria requests` de `values/kind/model-serving.yaml`) sigue cabiendo en los nodos.

## 9. Evidencia y cierre

Cada archivo de `aidlc-docs/construction/governance/evidence/kind/` pasa de «pendiente del operador» a lo que se obtuvo (comando, salida, esperado contra obtenido). El PR del cierre (U04-T07) puede fusionarse con la guía y la evidencia pendiente, como hizo U2. Al adjuntarla:

- el Paso 20 del plan pasa de `[ ]` («guía lista, pendiente del operador») a `[x] (U04-T07, acotado a la demo)`;
- las filas de `evidence/cierre-demo.md` pasan de «pendiente del operador» a un enlace a su evidencia;
- el escenario 7 sigue **pendiente de U7 Paso 18** aunque la parte de `serving-config` esté adjunta.

Si algo falló por un defecto del chart o de las imágenes (un value de kind que falta, un pod que no arranca), **detente y repórtalo**: es un defecto de U04-T06, no de esta guía.
