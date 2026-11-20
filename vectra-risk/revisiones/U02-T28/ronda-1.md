# Ronda 1 — U02-T28

VEREDICTO: NO-VERDE

Worktree `.claude/worktrees/u02-t28` en HEAD `91a9ece`, base `origin/main` = `ec06d8b`, tarea con hash `7ae7af5cd0f2c74eaa5e81cc48d99e5f8e729eca` (coincide). Todo corrió con `KUBECONFIG=/nonexistent`, sin `/snap/bin` y con un solo Keycloak a la vez. Al terminar, `git status --short` está vacío.

El código está bien: los cuatro criterios pasan con mis propias corridas y el rojo primero se reproduce. Lo único que impide el verde es un entregable del alcance que falta en la bitácora (F-01).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Sin scopes, el formulario no lleva `scope`; con scopes, no cambia | El literal `uv run pytest contracts/python/vectra_common/tests -q -p no:cacheprovider -k service_token` | rc 4, «no tests ran in 0.10s». La ruta no existe: es un defecto de la tarea, ver F-03 |
| 1 | (sobre la ruta real) | `uv run pytest contracts/tests -q -p no:cacheprovider -k service_token --no-cov` | **pasa**: 29 passed, 585 deselected, 1,79 s. `--collect-only`: el filtro recoge las 28 de `test_service_token.py` (incluidas las 3 nuevas) y `test_import_isolation[...service_token]` |
| 1 | Rojo primero | Lo mismo, con `service_token.py` de `origin/main` (copiado con `git show` y restaurado con `git checkout`) | **falla** como se espera: 1 failed (`test_without_scopes_the_form_carries_no_scope_parameter`), 28 passed |
| 2 | El lector obtiene su token contra el Keycloak real | `uv run pytest identity-edge/tests/integration -q -p no:cacheprovider -k reader_token -s` (carga 0,61 antes) | **pasa**: 4 passed, 29 deselected, 57,4 s. Realm importado en 17 s; `realm-drift` informa 35 diferencias. `--collect-only` selecciona exactamente las 4 de `test_reader_token.py` |
| 2 | Rojo primero | Lo mismo, con `service_token.py` de `main` (carga 3,58) | **falla** como se espera: 3 failed con `400 Bad Request` en `/protocol/openid-connect/token`. La prueba hecha a mano (`scope=` vacío da 400 con `Invalid scopes`, sin el parámetro da 200) pasa: confirma la causa con Keycloak 26.8.1 |
| 3 | Ningún otro servicio cambia su petición | `make -C contracts check`, con `node_modules` enlazado temporalmente | **pasa**: rc 0 en 1 min 58 s. 614 passed; cobertura total 98 %, `service_token.py` 100 % (incluidas las ramas); `git diff --exit-code` limpio; TS: 8 passed |
| 4 | La unidad sigue en verde | `make -C identity-edge check`, con `platform/.tools/bin` enlazado y `platform/.charts` copiado de `u01-t13` | **pasa**: rc 0, de 22:40:49 a 22:56:25 (carga 1,78 → 4,27). pytest: 2908 passed en 896 s, ninguna omitida; conftest y kubeconform todo en verde. La prueba de k6 pasó a la primera |

Sobre CA-4 hay dos cosas que conviene saber:
- Hubo un intento previo que terminó con rc 2 a los 7 s en `kubeconform-gateway`, porque a `platform/.charts` del árbol principal le falta `envoy-gateway`. Era un problema de herramientas, no llegó a correr pruebas. Con los charts de `u01-t13` fue la corrida única que cuenta.
- Durante unos 3 minutos de esa corrida dejé corriendo por error un bucle de espera activa que ocupó un núcleo; lo maté. La carga de 4,27 al final se debe en parte a eso.

**Quién pide token sin scopes.** Revisé todas las llamadas a `provider_from_env` y a `ServiceTokenProvider` fuera de las pruebas:
- La única que pide token con `()` es `identity-edge/jobs/keycloak_admin.py:79`.
- Las de `scoring/app.py:103` y `explainability/app.py:104` también pasan `()`, pero con audiencia `""`, así que no crean `token_source`.
- Todas las demás llevan al menos un scope: bias-monitoring, product-metrics, case-management (app y worker), governance (service y validation_job) y `measure_issuer` (`("openid",)`).
- Con scopes, el conjunto de claves y el valor de `scope` no cambian; lo fija la prueba existente `test_the_request_is_exactly_client_credentials_with_assertion`. Solo cambia el orden de los campos en el cuerpo (F-04).

**La llave privada en `realm_stack.py`.** No llega a ningún sitio que no deba:
- `client_keys` vive solo en memoria. No se imprime: `measure` no la recibe y `Stack` no tiene `__repr__`.
- Tampoco entra en `variables`, que es lo que recibe config-cli.
- El único archivo que se escribe es `keycloak-reader.key`, dentro de `stack.workdir` (`platform/.tools/tmp/u02t22/kc-<hex>`, ignorado por git), y `shutil.rmtree` lo borra en el `finally`.
- `measurements.log` no tiene `PRIVATE` ni `BEGIN`, y el diff tampoco trae PEM ni secretos.
- Después de mis corridas no quedan contenedores `u02t22`.

**Alcance.** El diff solo toca `service_token.py`, sus pruebas, `realm_stack.py`, la prueba nueva, la bitácora y `CANDIDATAS.md`. No toca el realm ni `restore-drill`, no añade reintentos ni da órdenes contra el clúster. No hay desborde.

## Hallazgos
### F-01 · NARANJA · `bitacoras/U02-T28.md`, punto 4 del alcance · Faltan las órdenes para el orquestador
El punto 4 del «Dentro» pide las órdenes: publicar, fijar el digest por PR, sincronizar `identity-jobs` y leer de vuelta `kubectl get cronjob … lastSuccessfulTime`. La bitácora solo trae la sección «Imágenes» y remite a un «informe» que no está en el repositorio, así que no hay órdenes que revisar. Según el repositorio, las correctas son:
1. **Construir y publicar a mano.** `supply-chain.yml` no construye: solo escanea con Trivy, y `sign-image.yml` firma una imagen ya publicada. Desde `vectra-risk/`:
   - `docker build -t localhost:5001/vectra/identity-jobs:dev -f identity-edge/jobs/Dockerfile .`
   - `docker push localhost:5001/vectra/identity-jobs:dev`
   - `docker inspect --format '{{index .RepoDigests 0}}' …`

   Así lo dice `identity-edge/docs/paso-16-kind.md` §3.
2. **Dónde se fija el digest.** En `identity-edge/jobs/values/kind.yaml`, clave `image.digest`; hoy vale `sha256:a7e5f1f0…2045aab`.
   - Hay que regenerar con `make -C identity-edge render-jobs`. Eso reescribe `identity-edge/jobs/rendered/kind/identity-jobs.yaml`, líneas 62 y 134, que es lo que lee la Application (`path: vectra-risk/identity-edge/jobs/rendered/kind`).
   - Si solo se cambia `values`, `check-jobs-rendered` falla.
   - El repositorio se refiere a la imagen como `kind-registry:5000/vectra/identity-jobs`.
3. **Sincronizar** la Application `identity-jobs`, que sigue `main`, después de fusionar el PR.
4. **Lanzar una corrida y leerla de vuelta.** Ojo, esto no lo he medido: un Job creado con `kubectl create job --from=cronjob/signing-key-age` no está en `.status.active` del CronJob, y el controlador v2 probablemente no actualiza `lastSuccessfulTime` con él. La lectura de vuelta de esa corrida manual es `.status.succeeded` del Job. `lastSuccessfulTime` debería llenarse con la siguiente corrida programada: `signing-key-age` corre cada hora (`0 * * * *`) y `realm-drift` a las 03:00.

### F-02 · AMARILLO · `test_reader_token.py:57` · La prueba pone una variable que el chart no pone
El docstring de `reader_env` dice «las mismas variables que le pone el chart», pero fija `VECTRA_CLIENT_KEY_ID` y el chart renderizado no la define. Lo medí con un plugin temporal que quita esa variable antes de cada prueba: las 3 pasan igual (57,4 s). El comportamiento es correcto, pero la prueba no reproduce el entorno del Job tal cual.

### F-03 · AMARILLO · CA-1 de la tarea · El comando literal no corre ninguna prueba
Responde «no tests ran in 0.10s» con rc 4. La ruta real es `contracts/tests/unit/test_service_token.py`. Es un defecto de la especificación, no del codificador, que ya lo anotó en `CANDIDATAS.md`.

### F-04 · AMARILLO · `service_token.py:80-88` · Cambia el orden de los campos
Con scopes, `scope` ahora va después de `audience` en el cuerpo `x-www-form-urlencoded`. Las claves y los valores son los mismos y OAuth no depende del orden, pero los bytes ya no son idénticos a los de `main`.

### F-05 · AMARILLO · `test_reader_token.py:107` · Una aserción que no puede fallar
`assert drift >= 0` siempre se cumple con un `len()`. La prueba depende de que `run_from_env` no lance excepción y de que `_PUSHED` tenga un elemento. Conviene afirmar el cuerpo de la métrica, como ya hace la prueba de `signing-key-age`.

## Tareas candidatas (defectos reales fuera de alcance)
- `identity-edge/jobs/Dockerfile:4` dice «La construye, escanea y firma supply-chain.yml», pero `supply-chain.yml` solo escanea. Corregir el comentario o añadir la construcción.
- A `platform/.charts` del árbol principal le falta `envoy-gateway`, así que `make -C identity-edge check` no pasa de `kubeconform-gateway` si se usan esos charts.
- (Sin medir) `lastSuccessfulTime` y las corridas manuales `create job --from=cronjob`: medirlo en kind antes de usarlo como lectura de vuelta.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/631da295-76b2-4d7b-8ebf-d66239b9cb1a/scratchpad/contracts-check.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/631da295-76b2-4d7b-8ebf-d66239b9cb1a/scratchpad/ie-check2.log (y `ie-uptime2.txt`)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/631da295-76b2-4d7b-8ebf-d66239b9cb1a/scratchpad/ie-check.log (el intento sin `envoy-gateway`)

```
VEREDICTO: NO-VERDE
NARANJA|bitacoras/U02-T28.md, punto 4 del alcance|Faltan las órdenes para el orquestador (publicar, digest en jobs/values/kind.yaml + render-jobs, sync, lectura de vuelta)
AMARILLO|identity-edge/tests/integration/test_reader_token.py:57|La prueba pone VECTRA_CLIENT_KEY_ID y el chart no (medido: pasa sin ella)
AMARILLO|CA-1 de la tarea|El comando literal no corre ninguna prueba (rc 4); la ruta real es contracts/tests
AMARILLO|contracts/python/vectra_common/src/vectra_common/service_token.py:80|Con scopes, scope va después de audience en el cuerpo
AMARILLO|identity-edge/tests/integration/test_reader_token.py:107|assert drift >= 0 no puede fallar
INFORME: revisiones/U02-T28/ronda-1.md
```
