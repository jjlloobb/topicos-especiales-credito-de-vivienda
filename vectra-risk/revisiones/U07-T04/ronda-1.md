# Ronda 1 — U07-T04

VEREDICTO: VERDE

Hay 0 ROJO y 0 NARANJA. Quedan 3 AMARILLO, que no bloquean. Los hallazgos están más abajo.

Ejecuté yo mismo todos los criterios, en el worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u07-t04`, sobre HEAD `a8604b5`. Los diff son contra `10e8f6a`. El blob de la tarea es `1f0330332e6e16e93f239a3635f4296c8e3404a7` y coincide. Al terminar, el worktree está limpio (`git status --short` vacío). Los renders que pedía `/tmp/u7-<env>` los escribí en mi carpeta: es el mismo comando con otra salida.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Imágenes | `hadolint` 2.15.1, `make image-scoring image-explainability`, `inspect`, `pip list`, `find` de plantillas, `grep FROM` | pasa: hadolint rc 0, build rc 0, `65532:65532` y `OK` en las dos imágenes, `OK-plantillas`, 4 `FROM` por digest |
| 1b | Arranque con `--read-only` | `docker run --rm --read-only --user 65532:65532`, con el entorno del chart, una llave y una CA de prueba montadas en ro, y la sonda dentro del contenedor | **sí pude correrlo.** Los dos procesos siguen vivos; `/healthz` 200, `/readyz` 200, `/livez` 404 |
| 2 | Render, kubeconform, conftest y `test_chart.py` | los 4 comandos | pasa: `Valid: 14` ×3, `756 passed` ×3; `test_chart.py` corre dentro de `coverage` (276 passed) |
| 3 | `make -C platform check-chart` | el de la tarea | rc 2 por `panic: poddisruptionbudgets.policy "scoring-service" already exists`, que es la candidata conocida de U03-T04 y U04-T05. Para ese caso la tarea autoriza un respaldo, y el respaldo `policy-chart-u1` dio `pass: 20, fail: 0` ×3 y rego en 0. Pasa por la vía prevista |
| 4 | Cuota y flujos | el comando completo | rc 0: `1 passed`, `211 passed`, ninguna línea «falta», `4`. `quotas.yaml:9` dice `U7: { requests: [6.37, 4.91], limits: [27.3, 11.38] }` |
| 5 | Application | `generate.py --check`, `test_waves.py`, `kyverno` ×3, `grep sync-wave` | rc 0: 53/50/52 en orden, `pass: 1, fail: 0` ×3, `'5'` ×3, sin `automated` |
| 6 | Trazabilidad | `test_traceability.py --all` y el `git grep` de BR-U7 | rc 0, `32 identificadores`, ningún BR «sin prueba». Los 7 nombres de prueba citados en los docstrings existen |
| 7 | Presupuesto | `pytest test_kind_profile.py` y mi script de `requested_gib(pico)` | `6 passed`; pico = **10,3438 GiB**, tope 10,4, umbral 10,58 |
| 8 | Sin migraciones ni frontend | `test ! -d …` | rc 0 |
| 9 | Cierre | `make -C scoring-explainability check`, `make -C platform check`, `grep` de secciones, `test -s` | U7 rc 0 (846 s, carga 16,7→16,9; 276 passed; cobertura 99 % en los dos servicios). platform rc 0 (1214 s, carga 16,9→13,7; Kyverno `pass: 392`) |
| 10 | RL-4 | solo U7 y platform (arriba), más las 3 pruebas de decision-registry | `git diff 10e8f6a HEAD -- decision-registry contracts identity-edge governance reference-model model-serving bias-monitoring case-management` está vacío. `test_aggregator`: las 3 aisladas pasan (`3 passed` en 10,8 s) y el archivo completo también (`22 passed`, carga 14 a 19). Como el código es idéntico al de la base, la corrida en la rama vale también para la base. Las demás cifras de la bitácora cuadran |
| 11 | Plan | `git diff 10e8f6a -- plan` | pasa: 14, 15, 17 y 20 en `[x] (U07-T04, acotado a la demo)`; 19 en `[x] (U07-T04)`; 16 y 18 en `[ ]` con su nota; no hay otro cambio |
| 12 | Candidatas | las 8 órdenes, contra `10e8f6a` | pasa: la primera no imprime nada; NFR-U7-41 aparece en las líneas 27 y 56; `2`/`2`/`2`; imagenes.md:41,45,46; read-serving en las líneas 26 y 70; `2` «cerrada»; el diff del realm y de U6 está vacío |

## Tus siete puntos
1. **Presupuesto.** La subida la manda la tarea («Esta tarea **sube `BUDGET_GIB`** a la cifra que dé `requested_gib()`… redondeada hacia arriba a 0,1»), así que no es un desvío. El umbral queda en 9,3 + 1,08 + 0,2 = 10,58. `test_the_profile_requests_fit_the_budget` usa `requested_gib([*declared, *PEAK_INFERENCE_SERVICES])`, es decir, el pico, y yo medí 10,3438 GiB. El diff de `test_kind_profile.py` cambia solo `BUDGET_GIB` y dos líneas de comentario.
2. **`/healthz`.** `ops_server.py:42` solo tiene `/metrics`, `/healthz` y `/readyz`, y el contenedor real devuelve 404 en `/livez`. Probé cuatro mutaciones con el script `scripts/mut.py`, sin tocar el worktree, y la prueba falla en todas: liveness cambiada a `/livez` en el render (fallan `test_probes_…` y `test_each_service_…`), U0 sin `/healthz` y U0 con `/livez`.
3. **`EXPECTED_WAVES`.** Es una sola palabra y es el mínimo necesario: sin ella `make -C platform check` falla. Es fuera de alcance según el texto de la tarea, pero tiene el precedente de U09-T04 (F-04, AMARILLO aceptado en el arbitraje). Lo dejo en F-01.
4. **KServe.** Bajé la fuente de la v0.21.0: `constants.go:400` define `CommonDefaultHttpPort = 80`, `service_reconciler.go:122` lo publica y los nombres siguen `name+"-predictor"` y `name+"-explainer"`. Los valores de los cuatro values coinciden con el namespace de `model-serving` en `components.yaml` (`vectra-serving`). `test_kserve_the_url_templates_…` lee la combinación real (env + `values/<env>`) y falla con el namespace cambiado a `vectra-app` o a `vectra-staging`, con el host sin sufijo, con `-explainer` cambiado a `-predictor` y con `:8080` explícito.
5. **C-1 a C-4.** C-1 y C-2 quedaron tachadas. C-3 tiene la parte de U7 cerrada y sigue abierta para U8. C-4 quedó decidida (a) y sigue abierta. Es lo que pide la tarea, y el conteo de CA-12 da 2.
6. **CA-10.** Ver la fila 10: el diff no toca decision-registry ni contracts, y las 3 pruebas pasan aisladas.
7. **`CANDIDATAS.md`.** `numstat` da 10+ y 4−. Las 4 líneas que se quitan son exactamente C-1, C-2, C-3 y C-4, reescritas con su marca. No se perdió ninguna línea ajena; las 6 nuevas se agregan al final.

## Hallazgos
### F-01 · AMARILLO · `platform/tests/test_platform.py:285` · `EXPECTED_WAVES` fuera de la lista de excepciones de U1
Es el mínimo necesario y tiene precedente (U03-T05, U04-T06, U09-T04). Es la tercera vez que una tarea de chart choca con esto, así que conviene que la plantilla de tareas de despliegue lo nombre entre las excepciones de U1.

### F-02 · AMARILLO · `cierre-demo.md:45` y `CANDIDATAS.md` (última entrada de U7) · el arranque con raíz de solo lectura sí se puede comprobar
La bitácora y el cierre dicen que el sandbox no dejaba hacer `docker run --read-only`, y lo dejan «Pendiente en U12». Yo lo corrí en esta máquina: los dos servicios arrancan con `--read-only`, con usuario 65532 y sin `emptyDir`, y responden en 8081. Esa fila de U12 y la candidata pueden pasar a «Comprobado».

### F-03 · AMARILLO · `cierre-demo.md:54` · NFR-U7-02 en la lista de diferidos aunque el Paso 8 lo cita
El plan, en la línea 146 (Paso 8, que entra), lista NFR-U7-02 en «Diseño». Una lectura literal de la regla de CA-6 («la lista no contiene identificadores de los Pasos 1 a 15 que entran») lo sacaría de la lista. Pero la propia tarea dice, en el Paso 17, «NFR-U7-01, 02, 03… la medición de carga de los tres se difiere; NFR-U7-03 queda trazado por el Paso 9»: solo excluye NFR-U7-03 de la lista, así que el codificador siguió la instrucción más específica. La herramienta lo acepta. Lo dejo para que decida el orquestador: si se quiere tratar igual que NFR-U7-03, NFR-U7-02 se traza en el handler de `explain` y su p95 pasa a «no comprobado».

Nota sin severidad: `kserve.*UrlTemplate` aparece cuatro veces, en el chart y en los tres `values/<env>`. Está justificado por el defecto de `render_env`, y esa candidata ya está registrada.

## Tareas candidatas (defectos reales fuera de alcance)
- U1 `render_env` sin los `value_files` de la unidad. Ya está en `CANDIDATAS.md`.
- `platform check-chart` sigue entrando en pánico con los charts que tienen PDB. Ya es candidata.

## Rutas de transcripciones largas
Todas están en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u07-t04-r1/`:
- `checks.summary`
- `check-scoring-explainability.log`
- `check-platform.log`
- `ca1.log`
- `ca3.log`
- `ca4.log`
- `ca7.log`
- `scripts/mut.py`
- `scripts/budget.py`
- `kserve/constants.go`
- `kserve/svc.go`

```
VEREDICTO: VERDE
AMARILLO|platform/tests/test_platform.py:285|EXPECTED_WAVES fuera de la lista de excepciones de U1 (mínimo necesario, con precedente)
AMARILLO|aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:45|El arranque con --read-only sí se comprobó; deja de estar pendiente en U12
AMARILLO|aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:54|NFR-U7-02 en diferidos aunque el Paso 8 lo cita; decide el orquestador
INFORME: revisiones/U07-T04/ronda-1.md
```
