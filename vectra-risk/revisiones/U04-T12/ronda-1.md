# Ronda 1 — U04-T12

VEREDICTO: VERDE

Base `3193a71` (merge-base con `origin/main`), cabeza `fc9d247`. Todo se corrió con `PATH` sin `/snap/bin` y con `KUBECONFIG=/nonexistent`. No usé el clúster ni `argocd`. Docker solo lo usó Testcontainers. Las versiones base y mutadas de los módulos las cargué en el scratchpad con un plugin de pytest (`-p`) que las sustituye en `sys.modules`. No toqué ningún archivo del worktree.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Llave legible, uid igual al del Dockerfile | `pytest governance/tests/unit -k "validation_job_template or readable or legible"` (con `--collect-only` antes: 26+1 pruebas, incluidas las nuevas) | pasa: 27 passed, 0 skipped |
| 1r | Rojo contra la base | lo mismo, con el `k8s_jobs.py` de la base inyectado | 5 failed. Mismo motivo que el clúster: `/var/run/vectra/client (modo 0o400, dueno 0:0, proceso 65532 grupos [65532])` |
| 2 | PodSecurity y Kyverno | `make -C governance policy-job` | rc 0. `pass: 16, fail: 0`, conftest 14/14 |
| 3 | Barrido | `pytest governance/tests -k sweep` | 24 passed en 13 s: 12 unitarias y 12 de integración con PostgreSQL real (3,5 s de arranque del contenedor). No se saltó nada |
| 4 | Bitácora y runbook | la orden de CA-4 | `defaultMode` aparece 4 veces. `PermissionError` y `validacion_fallida` están en §5.2 (líneas 150 y 155). `test_links.py` da rc 0 (659 archivos) |
| 5a | `make -C governance check` (una sola vez) | con `HYPOTHESIS_STORAGE_DIRECTORY` nuevo, como en la CI | **rc 0**. 655 passed, cobertura 97,28 %, núcleo al 100 %, policy-chart/u1/job en verde, trazabilidad bien. `policy-runbook` se omitió porque no hay `kubectl` en el PATH, que es lo que hace el Makefile |
| 5b | pytest de `platform` | con `platform/.tools` movido fuera del árbol y `.charts` presente | 1021 passed, rc 0. El enlace quedó devuelto igual que estaba |
| — | `test_traceability.py --all` | — | rc 0. No hay fallos nuevos |

## Lo que pidió el orquestador
1. **La llave.**
   - Con `fsGroup`, el kubelet hace `chown :fsGroup` a los archivos del Secret. Como el volumen es de solo lectura, también les suma `0440` al modo.
   - Queda `root:65532 0440`. El proceso 65532 tiene grupo primario 65532 y `fsGroup` como suplementario, así que lee el archivo; «otros» no lo lee. Con `fsGroup` bastaba incluso `0400`, porque el kubelet lo eleva a `0440`; la prueba es más estricta a propósito.
   - **La malla:** el `runAsUser` a nivel de pod no rompe el proxy:
     - Linkerd fija su propio `runAsUser` (2102) en el contenedor del proxy, y eso pesa más que lo del pod.
     - Aquí se usa `linkerd-cni` (no hay init con `NET_ADMIN`) y sidecar nativo.
     - El token proyectado de identidad queda `root:65532 0640`, y el proxy lo lee porque `fsGroup` se aplica a todos los contenedores.
     - Hay precedentes en el repositorio. `service.yaml` de governance fija `runAsUser`/`runAsGroup` **a nivel de pod**, en un namespace con malla, y ya corre en kind. Los CronJobs de `identity-jobs` (con la anotación de sidecar nativo) usan exactamente `runAsUser`/`runAsGroup`/`fsGroup` 65532 a nivel de pod.
   - CA-2 en verde. No hay ROJO.
2. **La prueba de legibilidad sí habría visto el defecto.** La corrí contra la base: falla con el motivo del clúster. Además hice mutaciones propias:

   | Mutación | Resultado | ¿Correcto? |
   |---|---|---|
   | `runAsGroup` 1000 en el pod | la legibilidad pasa; falla solo la prueba del uid | sí: `fsGroup` da la lectura |
   | `fsGroup` 1000 ≠ `runAsGroup` | igual que la anterior | sí |
   | `runAsUser` 1000 en el contenedor y sin `fsGroup` | 4 failed | sí |
   | `0400` con `fsGroup` | 2 failed | conservador, documentado |

   Modela bien la ausencia de `fsGroup`, los `supplementalGroups` y el caso `runAsGroup` ≠ `fsGroup`.
3. **El barrido.**
   - (a) **El interbloqueo era real en la base.** Prueba de carrera mía con la corrida vencida y el `background.py`/`evidence.py` de la base: `DeadlockDetected: Process 96 waits for ShareLock…; Process 95 waits for ExclusiveLock on advisory lock`. El `PUT` respondería 500. Con el código nuevo, la misma prueba termina con un solo ganador coherente: el informe, con la corrida en `informe_recibido`.
   - (b) **Ninguna intercalación deja un estado incoherente.** La decisión ocurre bajo el candado global: FSM, luego `_require_run`, luego `_ensure_free`.
     - Informe y barrido a la vez: el segundo recibe `ConflictState`.
     - Dos réplicas barriendo: `_ensure_free` y `_require_run` dejan pasar solo una.
     - Caída del servicio entre leer y cerrar: no se retuvo nada. Una TX1 confirmada sin publicar la recoge `reconcile_once` en 10 s.
     - `model_fsm.py` no está en el diff: no hay transiciones nuevas.
   - (c) **No se cierra nada antes de tiempo:**
     - Job que corre o `Complete` sin informe: es `JobInfo()` y no se toca hasta el plazo.
     - Job recién creado: tiene margen.
   - (d) **El margen de 5 min es coherente.** `started_at` se fija en la TX2 de `start_validation`, y el Job se crea después (`api.py`, `launch`, timeout de 5 s). Una prueba ata el margen a `K8S_TIMEOUT` y al plazo.
   - (e) **`source_comparison` queda intacto:** se filtra en la consulta y su Job ni se lee.
   - (f) **Lecturas acotadas:** `LIMIT BATCH` (20) por barrido y réplica, con prueba.
   - Mutaciones mías: X1 (quitar `after_check`) da 1 failed; X2 (`run_state` siempre `timeout`) da 3 failed; X3 sobrevive, ver G-03.
4. **CA-5 y la prueba PBT:**
   - **El fallo existe en `main`, el diff no lo causa.** Reproduje el ejemplo guardado (`@reproduce_failure('6.170.14', b'AXicY3BUdWRx…eA==')`), con `HYPOTHESIS_PROFILE=ci`:
     - con el código nuevo: `UniqueViolation "policies_one_active"`;
     - con `k8s_jobs`/`evidence`/`background` de la base inyectados: el **mismo** fallo.
     - La secuencia solo toca políticas. El diff no cambia esa ruta: solo quita `conn` de `_begin` y añade el `after_check` de la validación fallida.
   - **Pero no es determinista:** depende de `.hypothesis/` de este worktree, que está ignorado por git. Con una base de ejemplos nueva pasa 3/3 con la base y 3/3 con el diff, y `make check` completo dio rc 0.
   - Conclusión: es un defecto real de `main` que la CI encuentra solo por azar. Es candidata grave (ver abajo). No hay ROJO.
5. **Barrido de la clase y runbook.**
   - Muestra con `helm template` y los values de kind para `bias-monitoring` (Deployment y CronJob), `governance` y `case-management` (service y worker): todos `0444`, pod 65532:65532, sin `fsGroup`. Coincide con la tabla de la bitácora.
   - §5.2 dice lo que hace el código: menos de 2 min para un Job `Failed`, 5 min de margen, 20 lecturas, el motivo en `details.reason`, y que el Job sin pod sigue esperando a `deadline_at`.

## Hallazgos
### G-01 · AMARILLO · `background.py:173` · Si la API de Kubernetes falla a mitad del barrido, quedan transiciones sin publicar
Si `jobs.get` lanza `DependencyUnavailable` a mitad del bucle, las TX1 ya confirmadas en `created` no se publican en ese barrido. Antes, la transacción externa lo deshacía todo. Ahora las recoge el reconciliador en unos 10 s; mientras tanto la entidad está bloqueada (`_ensure_free`), así que un informe en vuelo recibiría 409. Se arreglaría capturando el error por corrida. No tiene prueba.

### G-02 · AMARILLO · `paso-20-kind.md` §5.2 · «Borrar el Job libera el modelo en unos 6 minutos» es ambiguo
El margen cuenta desde `started_at`, no desde el borrado. Un Job borrado a la hora libera el modelo en el barrido siguiente, en menos de 1 min. Por la misma razón, en el caso 2 (Job sin pod) borrar el Job libera el modelo sin esperar las 2 h, y el procedimiento no lo aprovecha.

### G-03 · AMARILLO · `background.py:166` · El orden de las corridas en curso no tiene prueba
Mutación X3: cambiar `started_at` por `started_at DESC` sobrevive a las 24 pruebas. Solo está probado que las vencidas van primero.

### G-04 · AMARILLO · `test_validation_job_template.py` · `test_the_readability_check_follows_the_dockerfile_user` es casi tautológica
Cambia el Dockerfile a 1000 y comprueba que el manifiesto difiere. La prueba que de verdad ata el uid es `test_the_manifest_uid_is_the_one_of_the_dockerfile`.

### G-05 · AMARILLO · `CANDIDATAS.md` (PBT u4_07) · La reproducción solo funciona en esta máquina
`-k u4_07` reproduce solo con la base de ejemplos local. Hay que poner el blob `@reproduce_failure` de arriba y decir que con una base nueva pasa.

No hay ROJO ni NARANJA. `MISSING_JOB_GRACE` es una constante con nombre, una prueba lo ata y sigue la convención de `BATCH` y `ABANDON_AFTER`, así que no lo cuento como literal incrustado.

## Tareas candidatas
- **Grave, de `main`:** `test_pbt_u4_07` encuentra `UniqueViolation "policies_one_active"`: con el ack perdido, la segunda activación de una política choca con el índice único. Es determinista con el blob de arriba sobre el código de la base. La CI lo encuentra solo por azar (con una base de ejemplos nueva pasó 6 de 6).
- El interbloqueo de la base (evidencia arriba) queda cerrado por este diff. Hay que revisar si `send`/`reconcile_once` retienen filas mientras llaman a servicios externos (ya anotado por el codificador).

## Estado final
- `git status --short` del worktree: vacío. `HEAD` sigue en `fc9d247`.
- Borré mis copias del scratchpad (`rev-u04t12-*`).
- Un `mkdir -p` mío creó por error un directorio vacío `revisiones/` en la raíz del checkout principal. Lo borré en el acto (`rmdir`).
- `policy-job` escribe en `platform/.tools/integration/` del checkout principal a través del enlace; esa ruta está ignorada por git.

VEREDICTO: VERDE
AMARILLO|background.py:173|si la API de Kubernetes falla a mitad del barrido, quedan TX1 sin publicar hasta el reconciliador
INFORME: revisiones/U04-T12/ronda-1.md
