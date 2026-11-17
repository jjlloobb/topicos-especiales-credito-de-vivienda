# U04-T12 — El Job de validación lee su llave, y su fallo se detecta sin esperar el plazo

**Unidad:** U4 — `governance`
**Historias que implementa:** ninguna nueva; cierra un defecto medido al validar el modelo de referencia en `kind-vectra` el 2026-11-17 y la candidata de `CANDIDATAS.md`, línea 838.
**Depende de:** ninguna (continúa U04-T11)

---

## Alcance

**Dentro:**

> Con el arreglo de U04-T11 el Job de validación ya pasa la admisión y tiene pod. **Medido el 2026-11-17 a las 03:56 UTC** (`POST /v1/models/mv-2026-01-01-8a98ab02/validations` → 200, `state: lanzado`, Job `validation-4c52bae4-43e9`): el contenedor murió a los pocos segundos y el Job quedó `Failed` en 59 s.
>
> ```
> File "/usr/local/lib/python3.12/site-packages/vectra_validation/run.py", line 99, in token_provider
>     Path(config.key_path).read_text(encoding="utf-8"),
> PermissionError: [Errno 13] Permission denied: '/var/run/vectra/client/private-key'
> ```
>
> El pod del Job (leído del clúster): `securityContext` de pod `{runAsNonRoot: true, seccompProfile: RuntimeDefault}`, sin `runAsUser`, `runAsGroup` ni `fsGroup`; volumen `client-key` con `secret.defaultMode: 256` (`0o400`, `governance/src/vectra_governance/k8s_jobs.py`, ≈ línea 193). La imagen corre como `USER 65532:65532` (`governance/validation_job/Dockerfile`, línea 26). El archivo queda de root con modo `0400` y el usuario 65532 no puede leerlo. El Deployment del servicio monta su llave con `defaultMode: 292` (`0o444`) y `runAsUser`/`runAsGroup` 65532 (`governance/chart/templates/service.yaml`, líneas 36, 37 y 108) y no tiene el problema.
>
> Después del fallo, `GET /v1/models/{id}` siguió dando `en_validacion`, sin informe: el barrido (`background.py`, `sweep_validations_once`, ≈ líneas 134 a 150) solo reclama las corridas con `deadline_at` vencido (2 horas). El modelo queda bloqueado dos horas por un Job que falló en un minuto (candidata de la línea 838).
>
> 1. **El pod del Job puede leer su llave.** Decide la forma (por ejemplo `runAsUser`, `runAsGroup` y `fsGroup` 65532 en el pod, con el modo del volumen que corresponda) y di por qué esa y no otra. Condiciones: el modo no se abre más de lo necesario (la llave no queda legible para «otros» si hay una forma de evitarlo); sigue cumpliendo PodSecurity `restricted` y las políticas de Kyverno (las pruebas de U04-T11 y `make -C governance policy-job` deben seguir pasando); y el uid no se escribe en dos sitios sin una prueba que los ate: una prueba lee el `USER` del `Dockerfile` y lo compara con lo que fija el manifiesto.
> 2. **Una prueba que habría visto el defecto sin clúster.** Hoy ninguna lo ve: di por qué (`governance/tests/unit/test_validation_job_template.py` comprueba campos, no que el usuario pueda leer). La prueba nueva razona sobre el manifiesto real de `k8s_jobs.py`: para cada volumen de `Secret` montado, el usuario y los grupos efectivos del contenedor pueden leer los archivos con el modo declarado (dueño root, grupo `fsGroup` si lo hay, reglas de Kubernetes para `defaultMode` y `fsGroup`). Rojo primero contra el manifiesto de `main`, con el mismo motivo que el clúster. Mira también el `ConfigMap` de la CA y el `emptyDir` de `/tmp` (¿puede escribir el usuario?).
> 3. **Barrido de la clase.** Los demás pods del repositorio que montan un `Secret` como archivo y corren como no-root: los Jobs y CronJobs de los charts de U3, U8, U9 y U11 y de `identity-edge` (`helm template` con los values de kind). Di cuáles hay, con qué modo y con qué usuario, y si alguno tiene el mismo defecto. Arregla los de U4; los demás, a `CANDIDATAS.md` con el detalle para reproducirlo.
> 4. **El fallo del Job se detecta pronto.** El barrido reclama también las corridas `lanzado` en modo `validacion` cuyo Job ya terminó en `Failed` (o cuyo Job ya no existe pasado un margen razonable), sin esperar a `deadline_at`, y pasa la versión a `validacion_fallida` con el motivo (`failed`) en la evidencia, como hace hoy al vencer el plazo. Condiciones:
>    - un Job que **sigue corriendo** no se toca; un Job recién creado que el API todavía no devuelve no se da por perdido (di el margen y de dónde sale);
>    - un Job `Complete` cuyo informe todavía no llegó no se marca como fallido antes de su plazo (el informe lo trae el propio Job por `PUT`; di qué pasa si no llega);
>    - la carrera con el informe: si el informe llega mientras el barrido reclama la corrida, gana uno solo y el estado final es coherente (mira el `FOR UPDATE SKIP LOCKED` y la máquina de estados, `model_fsm.py`);
>    - el modo `source_comparison` no cambia;
>    - el número de lecturas del API de Kubernetes por barrido está acotado (el barrido corre cada 60 s en cada réplica).
>    Con sus pruebas (unitarias y, si la unidad ya tiene de integración con PostgreSQL para el barrido, también ahí) y la mutación que demuestre cada condición.
> 5. **El runbook queda al día:** `governance/docs/paso-20-kind.md`, §5.2 «Si el Job no arranca»: hoy dice que hay que esperar a `deadline_at`. Escribe lo que pasa ahora (cuánto tarda el modelo en pasar a `validacion_fallida`, cómo se lee el motivo, cuándo se puede volver a pedir la validación) y añade el síntoma medido (`PermissionError … private-key`) con su causa.

**Fuera:**

- Relajar PodSecurity, Kyverno o las etiquetas del namespace.
- El contenido del Job (`governance/validation_job/`), salvo que el punto 1 no se pueda resolver desde el manifiesto: en ese caso, dilo y para.
- Reintentar el Job de forma automática: un fallo sigue pidiendo una validación nueva del operador.
- Reconstruir imágenes, fijar digests y el clúster: lo hace el orquestador.

---

## Archivos de contexto

- `governance/src/vectra_governance/k8s_jobs.py` (manifiesto, `JobReader`, `JobInfo`, `reason_of`), `background.py`, `model_fsm.py`, `api.py` (el `PUT` del informe y el `POST` de la validación), `service.py`
- `governance/tests/unit/test_validation_job_template.py`, `test_validation_job.py`, `validation_support.py`; las pruebas del barrido (búscalas: `sweep_validations_once`); `governance/Makefile` (`policy-job`, `policy-chart-u1`, `check`)
- `governance/validation_job/Dockerfile`, `governance/validation_job/vectra_validation/run.py` (qué archivos lee)
- `governance/chart/templates/service.yaml`, `migration-job.yaml` (cómo lo resuelve el Deployment)
- `governance/docs/paso-20-kind.md` §5.2; `CANDIDATAS.md`, líneas 838 a 841; `revisiones/U04-T11/`
- `platform/policies/kyverno/` y `platform/namespaces/` (lo que el pod debe seguir cumpliendo)

---

## Criterios de aceptación

- [ ] **CA-1** — El usuario del contenedor puede leer cada `Secret` montado, y el uid del manifiesto es el del `Dockerfile`.
  ```bash
  cd vectra-risk && KUBECONFIG=/nonexistent uv run pytest governance/tests/unit -q -p no:cacheprovider -k "validation_job_template or readable or legible"
  ```
  Esperado: pasa, con una prueba nueva que falla contra `main` con el motivo del clúster (el usuario 65532 no puede leer un archivo `0400` de root). Mutaciones que deben fallar: quitar `fsGroup` (o lo que elijas), devolver el modo a `0o400` sin grupo, cambiar el `USER` del `Dockerfile`. Comprueba con `--collect-only` que el filtro selecciona tus pruebas.

- [ ] **CA-2** — El pod sigue cumpliendo PodSecurity `restricted` y las políticas de Kyverno.
  ```bash
  cd vectra-risk && KUBECONFIG=/nonexistent make -C governance policy-job
  ```
  Esperado: rc 0, con la evaluación del Job en `fail: 0`.

- [ ] **CA-3** — Una corrida cuyo Job terminó en `Failed` pasa a `validacion_fallida` en el barrido siguiente, sin esperar `deadline_at`; una que sigue corriendo, o `Complete` sin informe antes de su plazo, no se toca.
  ```bash
  cd vectra-risk && KUBECONFIG=/nonexistent uv run pytest governance/tests -q -p no:cacheprovider -k "sweep"
  ```
  Esperado: pasa, con casos nuevos: Job `Failed` antes del plazo; Job corriendo; Job `Complete` sin informe; Job recién creado que el API no devuelve; informe que llega a la vez (un solo ganador); `source_comparison` sin cambio. Rojo primero: el caso «`Failed` antes del plazo» falla contra `main`. Si alguna de estas pruebas necesita PostgreSQL (Testcontainers) y Docker se te deniega, corre las demás y di exactamente cuáles quedaron sin correr: el revisor las completa.

- [ ] **CA-4** — El barrido de la clase está en la bitácora y el runbook dice lo que pasa ahora.
  ```bash
  cd vectra-risk && grep -n -c 'defaultMode' bitacoras/U04-T12.md && grep -n -E 'PermissionError|validacion_fallida' governance/docs/paso-20-kind.md | head -3 && KUBECONFIG=/nonexistent uv run python platform/tests/test_links.py
  ```
  Esperado: al menos 1; las dos cadenas aparecen en §5.2; enlaces en rc 0.

- [ ] **CA-5** — `governance` sigue en verde, y el pytest de `platform` también (sin clúster y sin `platform/.tools`).
  ```bash
  cd vectra-risk && KUBECONFIG=/nonexistent make -C governance check && KUBECONFIG=/nonexistent uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q
  ```
  Esperado: rc 0. `make check` una sola vez, al final (levanta contenedores; si `test_service_build_app.py` falla con `XMinioServerNotInitialized` por la carga de la máquina, es el fallo conocido de `CANDIDATAS.md`: corre aparte lo que no llegó a correr y dilo). Para el pytest de `platform`, mueve `platform/.tools` FUERA del árbol y devuélvelo.

---

## Plan de pruebas

Las de CA-1 y CA-3. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`, ni lecturas.** Corre TODO con `KUBECONFIG=/nonexistent` y con un `PATH` sin el `kubectl` real (está en `/snap/bin`; compruébalo con `which`). En el clúster hay ahora un Job `Failed` (`validation-4c52bae4-43e9`) y el modelo `mv-2026-01-01-8a98ab02` en `en_validacion` hasta las 05:56 UTC: no los toques.
- Ninguna prueba ejecuta `kubectl`, `docker` ni `argocd` reales fuera de lo que ya hace `make check` con Testcontainers, y ninguna ejecuta con `bash` o `subprocess` texto sacado de un documento.
- `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`: cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts`. No van en el commit.
- No descargues imágenes. La máquina tiene poca memoria, un clúster de kind completo corriendo y otros dos codificadores: una sola corrida pesada a la vez.
- En cada criterio, comprueba que el comando ejecuta de verdad tus pruebas nuevas.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u04t12-`, y borra tus copias al terminar.
- En paralelo corren U12-T09 (`system-verification/`) y U01-T17 (`platform/kind/`, `platform/secrets/`, `vectra-risk-gitops/`): no toques esos archivos.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes (uno por bloque: la llave; el barrido; el runbook). No hagas push, no fusiones, no muevas el estado de la tarea.
