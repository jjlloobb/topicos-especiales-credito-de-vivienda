# Ronda 1 — U11-T03

VEREDICTO: VERDE

Hice todas las comprobaciones en el worktree `.claude/worktrees/u11-t03`, sobre HEAD `a741f27` y contra la base `origin/main` `210da56`. El hash de la tarea es `4f8f4d4e…b0b6f` y coincide con el despachado. No hay ROJO. Los dos NARANJA y los AMARILLO no bloquean según RL-2 y van a `CANDIDATAS.md`.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Imagen | `hadolint`; conteo de `FROM` (2 y 2); `make image` + `image-test` dentro de `make check` | pasa (`7 passed in 25.11s`) |
| 2 | Render, kubeconform y conftest | `integration.py` ×3 (salida en el worktree, no en `/tmp`) + kubeconform + conftest | pasa: `Valid: 9`, `540 passed` y `21 passed` en cada entorno; 9 documentos: Deployment, Service, PDB, SA, ExternalSecret, ServiceMonitor, PrometheusRule y 2 ConfigMap |
| 3 | Identidad, variables, parámetros | `vault_paths` → `OK-boveda`; `clientId` en la línea 1246; `! grep "hours <= 0"` rc 0; `test_chart.py` dentro de `coverage` | pasa |
| 4 | Contenedor real | `make check` → `image-test` | pasa |
| 5 | Admisión de U1 | `policy-chart-u1` (`pass: 10, fail: 0` ×3, rego 63 y 3 ×3); `kyverno test` | pasa: `81 passed, 0 failed` |
| 6 | Cuota, flujos, CODEOWNERS | `quotas/render.py --check`, `network/generate.py --check`, los grep (salen `3` y `U11: {…}`), `quota-flows` (`211 passed`, `11 passed`), `git diff --exit-code` sobre U1 | pasa; el diff de U1 está vacío |
| 7 | Reglas generadas | `gen-rules` y `rules` en `make check` («al dia»; `SUCCESS: 24 rules found`) | pasa |
| 8 | Alertas con promtool | `promtool test rules` 5 veces seguidas: rc 0 ×5; conteo `[4 alertname] 6` | pasa |
| 9 | Dashboard | `test_dashboards.py` 39 passed; 4 mutaciones reales de `product.json` (abajo) | pasa |
| 10 | Runbooks | target `runbooks` y `forbidden_phrases` sin salida | pasa |
| 11 | Application | `generate.py --check`; `test_waves` 54/51/53; `kyverno apply` `pass: 1` ×3; wave `'5'` ×3; ningún `automated`; `values-kind.yaml` 1/0/0 | pasa |
| 12 | Trazabilidad | `--unit product-metrics --all` → 36, rc 0; las 14 BR con prueba; `--all \| grep -c U11-` = 0; diferidos exactamente NFR-U11-02 y 03; `grep NFR-U11-0(2\|3)` rc 1 | pasa. Los fallos de `--all` en la rama (solo U8 y U10) son un subconjunto de los de la base, que medí con un `git archive` |
| 13 | Memoria de kind | lo explico debajo de la tabla | pasa |
| 14 | Candidatas C-1 a C-7 | mutaciones (abajo); `capture_signals` ausente; `add_signal_handler` en `process.md`; 7 «Atendida» | pasa |
| 15 | README | `test -s`, `[INTERNO]` = 2, ninguna línea «falta», `test_links --root product-metrics`: 7 archivos | pasa |
| 16 | Cierre | `make -C product-metrics check` **RC=0 en 596 s** (21:19:56, carga 4,04 → 21:29:52, carga 3,19); las 4 secciones del cierre | pasa |
| 17 | `make check` (muestra) | `make -C platform check-local` RC 0, 203 s, `802 passed` (21:37:34, carga 1,60); `check-tools` RC 0, 184 s, con `TMPDIR` en el worktree (termina 21:44:01, carga 10,09) | pasa |
| 18 | Plan | grep del diff: 10, 11, 12, 13, 15, 17 y 18 en `[x]`; 14 y 16 en `[ ]` con su nota; conteo 18 | pasa |

**CA-13, memoria de kind (prioridad 1).**
- Con el render de HEAD, `requested_gib` da **10.632812** con `BUDGET_GIB` en 10.7.
- Quitando la línea `product-metrics` de `components.yaml` (y restaurándola después) da **10.34375**.
- La diferencia es 0,289062 GiB = 296 MiB = 2 × (128 + 20) MiB, así que las cifras del codificador cuadran.
- El render de kind difiere del de staging solo en `memory: 128Mi` (y en el registro de la imagen). Staging y prod quedan en 256Mi con limit 512Mi.
- El diff de `test_kind_profile.py` solo toca `BUDGET_GIB` y su comentario, con la cita de §7 y de P-1 (b).
- 10,7 es 10,6328 redondeado hacia arriba a 0,1: la holgura es de 0,067 GiB y no hay holgura injustificada.
- La proyección (12,52 GiB) queda por debajo de 13,0.
- `test_kind_profile.py`: `6 passed in 69.16s`.
- La decisión de P-1 queda anotada en `values-kind.yaml`, `components.yaml`, el plan, el README y el cierre.

**Mutaciones de las candidatas.** Cada una la deshice con `git checkout`.
- **C-2** (el planificador cancela la página: `full_pass` corre en una tarea que se cancela al activarse `stop`): `assert completed_at_exit == [1]` falla. Sin la mutación, `1 passed`.
- **C-3**:
  - plazo a 90 min: falla `[justo-por-encima-de-75-min-vence]`;
  - plazo a 60 min: falla el caso de «por debajo»;
  - sin el reinicio diario de `_retries`: `test_a_second_daily_pass…` cae en `AssertionError`.
- **C-4** (sin `loop.add_signal_handler`): la suite de `test_main_process.py` muere después de `FF..`. La propiedad del código 0 la sostiene ese manejador, no el override quitado.
- **C-6** (sin subir los loggers a WARNING): `test_no_log_line…` falla.
- **Dashboard:**
  - una serie que ninguna regla graba, una serie cruda y `period="dia"`: 5 failed cada una;
  - renombrar `north_star_decisions:dedup` no mutó nada: esa serie no aparece en `product.json`, así que no prueba nada.
- **Chart:** `values-kind.yaml` con 96Mi da 3 failed; `values.yaml` con request de 200Mi da 2 failed (`kind` y `quota`).

## Hallazgos

### F-01 · NARANJA · CANDIDATAS.md (entrada nueva de `test_waves.py`) y bitácora, «Lo que no cumplí», punto 1 · candidata falsa sobre `FIXED_WAVES`
`platform/tests/test_waves.py:35` ya tiene `"product-metrics": 5`, y está en la base: la tarea tenía razón. Mi mutación:
- con `wave: 4` solo en `components.yaml`, `test_waves.py` da rc 0, porque las Applications no se regeneraron (eso lo atrapa `generate.py --check`);
- con `generate.py` corrido, `test_waves.py` da rc 1 con `product-metrics: wave 4, se esperaba 5` ×3, y `test_platform` también falla.

La bitácora atribuye el defecto a U1 y deja en `CANDIDATAS.md` una candidata que no existe. Hay que retirarla o corregirla. No rompe ningún CA, porque CA-11 pasa.

### F-02 · NARANJA · `observability/rules/tests/alerts-product.yaml:49-52` · la corrección del caso intermitente afloja el borde de `for: 1h`
Al pasar las evaluaciones a 58 y 62 min, la mutación `for: 59m` de `ProductMetricsDegraded` **sobrevive**: todos los archivos dan `SUCCESS`. Lo probé en una copia de las reglas. `for: 61m` solo lo atrapa `degraded-dos-replicas…` a los 61 min. La causa es que la alerta lee una `:dedup` de otro grupo; poner la `:dedup` y la alerta en el mismo grupo, o leer la serie cruda con `max without`, devolvería el borde exacto. No afecta a D1–D4.

### F-03 · AMARILLO · bitácora, punto 2 · `promtool` no «rechaza» sin la etiqueta `branch`
Sin `branch`, `promtool check rules` imprime `lint error 2 duplicate rule(s) found` pero sale con rc 0 (el lint no es fatal por omisión). Con `branch` puesta, el enrutado no se ve afectado: Alertmanager no tiene rutas propias en `kube-prometheus-stack.yaml`. Siguen siendo 4 `alertname` y 6 reglas, y los runbooks explican la etiqueta. La desviación es aceptable; solo el texto exagera.

### F-04 · AMARILLO · resto de desviaciones declaradas, juzgadas
- **Cuota:** `platform/policies/quotas/` no tiene `.rego`, así que `render.py --check` junto con `test_every_workload…` es la verificación real y la tarea la autoriza.
- **`coverage`:** los tests ignorados en el segundo comando ya corren en el primero (`tests/unit`, perfil `ci`). El 100 % de `compute` y `noise` sale de ese primero (`358 passed`). El segundo llega a 98,64 %. No esconde nada exigido.
- **`http_servers.py`:** el `host` nuevo es un parámetro de un doble de pruebas con valor por omisión `127.0.0.1`. Es inocuo.
- **`check-chart`:** también entra en pánico con `bias-monitoring/chart` (`panic: poddisruptionbudgets.policy "bias-monitoring-service" already exists`). Es la candidata previa de las líneas 345 y 400, no un defecto de este chart.

## Alcance
Fuera de `product-metrics/`, el diff solo toca los 12 archivos que nombra la tarea. `platform/network`, `platform/policies` y `CODEOWNERS` no tienen diff. Ninguna Application lleva `automated`. Los Pasos 14 y 16 siguen en `[ ]`. `test_links.py` de todo el repositorio: `511 archivos Markdown sin enlaces rotos`, rc 0.

## Tareas candidatas
- F-01: retirar o corregir la candidata errónea de `FIXED_WAVES`.
- F-02: devolver el borde exacto de `for: 1h` en el caso de promtool.
- Entorno: con `TMPDIR` dentro del worktree, `make -C platform check-local` da falsos rojos: `test_identity_seed` rechaza claves dentro del repo y `test_traceability` salta `.tools`. `check-tools` necesita lo contrario porque `/tmp` está lleno. Conviene separar los dos temporales en `platform/Makefile`.

## Notas del entorno
- Mi primera corrida de `make -C platform check` dio 25 failed y 14 errors **por mi propio `TMPDIR`**, no por el diff. La repetí con `/tmp` para `check-local` y con `TMPDIR` en el worktree para `check-tools`: las dos en verde.
- La copia de la base para la trazabilidad (`.hypothesis/revisor-base`) y `platform/.tools/tmp-revisor` están borradas.
- `git status --short` del worktree sale **vacío** al terminar. HEAD sigue en `a741f27`. No toqué el árbol principal ni otros worktrees.

```
VEREDICTO: VERDE
NARANJA|vectra-risk/CANDIDATAS.md (entrada test_waves.py) y bitacoras/U11-T03.md|candidata falsa: FIXED_WAVES sí fija product-metrics (test_waves.py:35)
NARANJA|product-metrics/observability/rules/tests/alerts-product.yaml:49-52|el ajuste 58/62 min deja vivir la mutación for: 59m de ProductMetricsDegraded
AMARILLO|bitacoras/U11-T03.md (punto 2)|promtool no rechaza sin branch: lint con rc 0
INFORME: revisiones/U11-T03/ronda-1.md
```
