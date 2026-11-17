# Ronda 2 — U12-T09

VEREDICTO: NO-VERDE

Un ROJO, G-01: la comprobación previa de `tests/doubles/safe_shell.py` se burla, y lo demostré ejecutando un binario real con la lista más estricta. Con los textos que hoy ejecutan las pruebas no ocurre nada, pero ese camino existe y cae bajo la regla de esta ronda: cualquier camino por el que una prueba pueda ejecutar un binario real contra el clúster es ROJO. Lo demás está cerrado: F-01 a F-06, M-01, M-02, M-03 y CA-1 a CA-5. CA-6 da rc 2 por una sola prueba de tiempo de CPU (G-02); esa prueba es anterior a la tarea y pasa 2 de 2 sola.

Todo lo corrí con `PATH` sin `/snap/bin` y `KUBECONFIG=/nonexistent`. Antes de la suite leí qué ejecutan las pruebas (punto 1 abajo): nada lanza herramientas reales fuera de los Testcontainers, salvo el camino latente de G-01.

## Criterios de aceptación, verificados por mí (sha 78ca83c)
| # | Resultado |
|---|---|
| CA-1 `-k "transient or transitorio"` | pasa, 18 passed |
| CA-2 `-k "resend or reenvi"` | pasa, 18 passed |
| CA-3 `-k sincronizacion` | pasa, 6 passed |
| CA-4 y CA-5 (pruebas) | pasan dentro de check-fast: solo falla la de G-02. Los grep de CA-5 dan rc 0 (RT3-c aparece 3 veces y no hay frases falsas) |
| CA-6 `check-fast` | **rc 2**. Pasan lint, mypy y los 11 contratos. La etapa 1 da 1329 passed y **1 failed** (G-02), cobertura 95,86 %. Los tres archivos de Testcontainers pasan. Como make se detuvo, corrí aparte el resto: etapa 2 con 1057 passed y 100 %; shellcheck, links y traceability sin error (659 Markdown, 22 identificadores). `test_links.py` y `make -C model-serving lint` dan rc 0. `test_traceability.py --all` da rc 0, sin fallos nuevos |

## Estado de F, M y R
- **F-01: cerrado.** Las plantillas y `cierre-demo.md` se copian en F0 paso 11 a `$VERIF_HOME/plantillas` y F10 las copia, junto con `$EVID`, a la rama del clon. La línea del informe ahora dice `$EVID/verification-report.md`.
- **F-02: cerrado.** Repetí mis mutaciones (las dos de la ronda 1 y una tercera para la exclusión de `idempotency_key_invalid`) y las tres mueren:

| Mutación | Resultado |
|---|---|
| Lista de lectura con 400/401/403/409/422 | 5 failed |
| `set_decisions` anticipado suprimido | 1 failed (`test_decisions_transient_errors_that_never_stop…`) |
| Exclusión de `idempotency_key_invalid` quitada (reescribiendo `Simulator.run` en el plugin) | 1 failed |

- **F-03: cerrado.** La guía da `mv "$VERIF_HOME/evid" …`, el `git pull` y repetir el bloque, y dice qué commit nombra el directorio.
- **F-04: cerrado.** Guía y README leen `get svc api-gateway -n vectra-edge` con la causa (`GatewayNamespace`). La candidata nueva corrige la anterior sin editarla, y `CANDIDATAS.md` solo crece al final.
- **F-05: cerrado.** La rama local se borra con `branch -D` y la remota queda nombrada como orden del operador.
- **F-06: cerrado.**
- **F-07:** sigue como candidata, según el arbitraje.
- **M-01: cerrado** en el texto.
- **M-02: cerrado.** `PENDING` ya no está.
- **M-03: cerrado.**
  - Los 16 recursos de `identity-edge/tests/e2e/echo/manifests.yaml` llevan `part-of: identity-edge-e2e`, en `vectra-app` y `vectra-edge`, y son de los tipos deploy, svc, sa y pdb.
  - Rendí sin clúster `helm template` de los cuatro charts con los values de kind: governance (13 documentos), case-management (22), console-bff (7) y console-spa (5). Cero llevan `identity-edge-e2e`; su `part-of` es `governance`, `case-management` o `console`. La etiqueta solo aparece en el archivo del eco.
  - La orden está anclada con `^…$`: tipos fijos, namespace fijo y sin `-A`. `test_kubectl_verbs.py` rechaza la forma vieja, sin etiqueta, con otra etiqueta, con otro namespace y con `-A`.
  - El orden es correcto: el eco se retira en el paso 1 de F2, antes de las cuatro Applications, y el paso 10 queda de solo lectura.
  - Para quien ya sincronizó: si el eco se aplicó encima de los reales, estos llevan la etiqueta y el borrado los quita. La guía lo cubre con la comprobación de los cuatro Deployment y la resincronización.
- **R-01: parcial. Ver G-01.**
  - `tests/unit/conftest.py` pone centinelas para `kubectl`, `docker`, `argocd` y `gh` delante del `PATH` y `KUBECONFIG=/nonexistent` en toda prueba unitaria.
  - Por eso los sitios que construyen el entorno con `{**os.environ}` heredan la guarda: `test_kind_scripts`, `test_demos_closed_world`, `test_rt5_job_script` y `test_prepared_prs`. Los dobles se instalan dentro de la prueba.
  - Sitios con el entorno armado desde cero:
    - `integration/test_cli.py:176`, con `PATH=""`.
    - `test_cli.py:1187`, con `PATH=/usr/bin:/bin`. Corre `journey-7-3.sh 4`, que solo lee el manifiesto.
  - `k8s_read` solo usa `SubprocessRunner` en `live.py`. Las pruebas inyectan dobles; `test_live` construye uno pero no lo llama.

## Hallazgos nuevos
### G-01 · ROJO · tests/doubles/safe_shell.py (`command_words`, `HARMLESS`) · La comprobación previa se burla y el `PATH` aislado se escapa
Probé textos adversos contra una copia del módulo, llamando solo a `disallowed()`. Pasan sin una sola orden rechazada:

| Texto | Lista con la que pasa |
|---|---|
| `{ /snap/bin/kubectl delete ns x; }` | `VV_ALLOWED`, la más estricta |
| `( /snap/bin/kubectl delete ns x )` | `VV_ALLOWED` |
| `{ env PATH=/usr/bin docker exec vectra-control-plane kubectl delete ns x; }` | `VV_ALLOWED` |
| `` echo `/snap/bin/kubectl …` `` | `EVID_ALLOWED` |
| `cat <(…)` | `EVID_ALLOWED` |
| `$( (…) )` | `EVID_ALLOWED` |
| `export PATH="/usr/bin:$PATH"` y después `` echo `docker exec …` `` | `EVID_ALLOWED` |
| `printf() { …; }; printf` | `EVID_ALLOWED` |
| `then …` | `EVID_ALLOWED` |

Las causas:
1. `command_words` **descarta** toda orden cuya primera palabra sea `{`, `(`, `then` o `do`, en vez de mirar la palabra siguiente.
2. No mira las comillas invertidas ni `<(…)`.
3. `export` está permitido.
4. `env`, `bash` y `sh` están enlazados en el `PATH` aislado.

Ejecución demostrada con un binario inocuo: `run_script("{ env PATH=/usr/bin:/bin uname -s; }", VV_ALLOWED, …)` dio rc 0 y `Linux`, es decir, se ejecutó un binario real fuera de la lista y del `PATH` aislado. Con `docker` en su lugar, el socket de Docker no necesita `HOME` ni `KUBECONFIG`, y `docker exec` sobre un nodo de kind alcanza el clúster.

Hoy no se activa: los dos bloques que se ejecutan (`EVID` y `vv`) no tienen esas formas; las comillas invertidas solo aparecen en comentarios. Es exactamente la clase de R-01: un recorte futuro mal hecho de un documento.

Arreglo mínimo:
- Mirar la palabra que sigue a `{ ( then do else`, o rechazarlas.
- Rechazar las comillas invertidas, `<(` y `>(`.
- Rechazar asignaciones de `PATH`, en `export` o como prefijo.
- No enlazar `env`, `bash` ni `sh`.
- Una prueba roja por cada texto de esta tabla.

### G-02 · AMARILLO · tests/unit/test_evidence_filter.py::test_f07_a_megabyte… · Prueba de tiempo inestable con carga, que hizo fallar CA-6
Dio `9,14 s de CPU < 8,0` con un load average de 11,4 (otros agentes corriendo a la vez). Sola pasa 2 de 2, en unos 3 s. El archivo no cambia entre 6cf06e1 y 78ca83c: no es de esta tarea. La propongo como candidata para la unidad dueña (U12): no es un ROJO de este diff.

### G-03 · AMARILLO · tests/unit/conftest.py y tests/integration · Huecos de la guarda
`TOOLS` no incluye `helm`, que sí está en `/usr/bin` en esta máquina; `KUBECONFIG=/nonexistent` lo contiene igual. `tests/integration` no tiene guarda, y sus pruebas heredan el `PATH` y el `KUBECONFIG` reales. Hoy no lanzan herramientas fuera de Docker y Testcontainers. Es candidata: centinelas de `kubectl` y `argocd` más `KUBECONFIG=/nonexistent` también allí.

### G-04 · AMARILLO · docs/paso-18-kind.md F0 paso 9 y README «Red» · Falta un dato medido
Siguen diciendo «No está medido que Docker aplique `--add-host` con `--network host`». Es compatible con lo que midió el orquestador: con `--network host` el contenedor usa el `/etc/hosts` de la máquina y `humo login` pasó sin `--add-host`. Pero conviene escribir ese dato, porque `vv` se niega a arrancar sin `GATEWAY_ADDRESS`, aunque la línea de `/etc/hosts` basta.

## Tareas candidatas
- U5 y U6: la orden `mc` de `reference-model/docs/release.md` (y la de `model-serving/docs/paso-11-kind.md`) necesita `--tmpfs /tmp` y `--config-dir /tmp/mc` (medido por el orquestador).
- G-02 y G-03.

## Estado final
- El worktree quedó limpio (`git status --short` vacío) y HEAD sigue en 78ca83c.
- Borré las copias `rev-u12t09-*` del scratchpad.
- No toqué el clúster ni construí imágenes.

```
VEREDICTO: NO-VERDE
ROJO|tests/doubles/safe_shell.py (command_words, HARMLESS)|la comprobación previa se burla con { } ( ) then, comillas invertidas, <( ) y export PATH; env enlazado deja ejecutar binarios reales (demostrado con uname)
AMARILLO|tests/unit/test_evidence_filter.py::test_f07_a_megabyte…|tiempo de CPU inestable con carga: CA-6 rc 2 (anterior a la tarea; sola pasa 2/2)
AMARILLO|tests/unit/conftest.py, tests/integration|helm fuera de los centinelas; integration sin guarda
AMARILLO|docs/paso-18-kind.md F0 paso 9, README «Red»|falta el dato medido: --network host usa el /etc/hosts de la máquina
INFORME: revisiones/U12-T09/ronda-2.md
```
