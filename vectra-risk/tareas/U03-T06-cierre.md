# U03-T06 — Cierre acotado a la demo de `decision-registry`

**Unidad:** U3 `decision-registry`
**Historias que implementa:** ninguna nueva. Cierra lo que implementaron U03-T01 a U03-T05 (Pasos 1 a 13, 15 y 16).
**Depende de:** U03-T05 (#94), ya en `main`. El código de U3 está completo para la demo.

**Se despacha** ya. Es solo documentación y verificación, y puede correr en paralelo con cualquier tarea de otra unidad (RL-5).
**Rama:** `tarea/U03-T06`, desde `origin/main`.

Bloque I del plan de U3 (`aidlc-docs/construction/plans/decision-registry-code-generation-plan.md`), Pasos 19 y 20, más la nota de consolidación del Paso 18. La enmienda §8 de `demo-recorte-funcional.md` dice: «Para U3, cuyo código ya está en `main`, el cierre es una tarea corta de documentación».

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 14 Alertas y runbooks | **D** | Ya está `[ ]` con «diferido por la demo: T2». No cambia | Enmienda §3 U3, fila 14; T2 |
| 17 Benchmarks y carga | **D** | Ya está `[ ]` con «diferido por la demo: T3». No cambia | Enmienda §3 U3, fila 17; T3 |
| 18 Verificación en kind | — | Queda `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». Su escenario de demo lo verifica U12 Paso 18: wave 5, readiness, appends del flujo base, agregador con atraso 0 y `daily:query` > 0 tras los 2 000 casos. Se difieren los escenarios 1–7 y 9, y del 8 la suspensión de 35 min, el rebuild y los silencios | Enmienda §3 U3, fila 18, y §8 |
| 19 Frontend: N/A | **N/A** | — | Enmienda §3 U3, fila «19 N/A · 20 Cierre» |
| 20 Cierre de la unidad | **E\*** | Cierre acotado, con `evidence/cierre-demo.md` completo | Enmienda §3 U3 y §8; alcance §2.4 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda.

---

## Alcance

**Dentro:**

### Paso 18 — Consolidado en U12

- En el plan, queda `[ ]` con la nota «consolidado en U12 Paso 18 (enmienda §8)». Esta tarea no lleva guía de kind ni scripts.
- Si `test_traceability.py --unit decision-registry --all` marca identificadores que **solo** verifica el Paso 18 (por ejemplo, el atraso del agregador, NFR-U3-24), van a la lista «Diferido por la demo» con la cita «Enmienda §8; consolidado en U12 Paso 18». No se agregan pruebas ni código para trazarlos.

### Paso 19 — N/A

- U3 no tiene interfaz de usuario: el expediente lo muestra la SPA (U10) vía el BFF.

### Paso 20 — Cierre acotado (E\*)

- `make -C decision-registry check` corre en orden las verificaciones estáticas y de integración (Testcontainers) de los Pasos 2 a 16 que entran, y termina en 0. No se cambia el `Makefile` salvo que falte un objetivo de un paso que entra. Si falta, **repórtalo** antes de agregarlo.
- `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md` completo. Hoy solo tiene «Diferido por la demo», la que escribió U03-T05. Usa el formato de `aidlc-docs/construction/model-serving/evidence/cierre-demo.md` y, si ya está fusionada, el de governance (U04-T07, `aidlc-docs/construction/governance/evidence/cierre-demo.md`). Lleva estas secciones:
  - **Comprobado:** cada paso que entra (1 a 13, 15 y 16), con la tarea que lo hizo, su comando de aceptación y el resultado que obtienes **ahora** en `main`. No copies el de la bitácora vieja;
  - **Diferido por la demo:**
    - la lista que ya existe, conservada; solo se le agregan filas;
    - más los Pasos 14 (T2) y 17 (T3);
    - del Paso 11: `verify`, `checkpoint`, `archive`, `aggregator reset` y `--until-head`. Nota de §7 de la enmienda: `verify` y `archive` ya tienen código de U03-T04, que se queda;
    - del Paso 12: los 5 CronJobs restantes, `test_ondemand.py`, `chart-rebuild/` y las políticas HCL nuevas (P-6);
    - del Paso 13: los values de buckets y de Transit;
    - del Paso 15: `decision-registry-rebuild`, `rebuild-history.yaml`, `rebuild-runid-check.yml` y la wave 6;
    - la mutación del Paso 16 (T3);
    - los escenarios diferidos del Paso 18;
    - cada uno con su destino;
  - **Pendiente en U12:** el escenario del Paso 18 que entra, con lo que debe verse: wave 5 `Synced`/`Healthy`, `/readyz` en 200, appends del flujo base con ack, `registry-aggregator` con atraso 0 y `POST /v1/monitoring/daily:query` > 0 tras los 2 000 casos. Lo verifica U12 Paso 18 (enmienda §8);
  - **Candidatas abiertas de U3 más relevantes:** las de `CANDIDATAS.md` que afectan a la demo, con su línea, como mínimo:
    - la prioritaria de `test_queries.py` y `daily:query` sin tope por solicitud (U03-T03 ronda 2, F-01), según P-1;
    - la firma de `checkpoint` sobre `recorded_at` (U03-T03 y U03-T04);
    - `fail_closed` en 403 frente a 422 (U03-T03, F-03);
    - los `inconsistente` de `incremental` y `nightly` sin guardar (U03-T03);
    - `pools.py` sin vida máxima (U03-T03);
  - **Quién ejecutó:** el codificador de esta tarea, con la fecha y el sha de `main` sobre el que corrió.
- RL-4: al cerrar la unidad, el `make check` de todas las unidades corre una vez (CA-4).

### Plan

- Paso 18: `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)».
- Paso 19: `[x] (U03-T06)`.
- Paso 20: `[x] (U03-T06, acotado a la demo)`.
- Los Pasos 14 y 17 no cambian.

**Fuera** (rechazar aunque se vea roto o tentador):

- Cualquier cambio en `decision-registry/src/`, `migrations/`, `chart/` o `tests/`. Esto incluye el arreglo de la candidata prioritaria de `test_queries.py` (ver P-1).
- Guía, scripts o escenarios de kind (Paso 18: van en U12).
- Alertas, runbooks, benchmarks, k6 y mutación (Pasos 14, 16 y 17, T2 y T3).
- Cambios en U0 o en U1, incluido `test_traceability.py`.
- Cualquier `kubectl`, `helm install`, `argocd` o sync (AUTONOMIA-01).

---

## Archivos de contexto

- `aidlc-docs/construction/plans/decision-registry-code-generation-plan.md`: Pasos 11 a 20 y §3.
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §2, §3 U3, §6 (P-4, P-6), §7 (U03-T04) y §8.
- `aidlc-docs/construction/plans/demo-kind-alcance.md`: §2 (T1 a T6), §3 U3 y §6.
- `DECISIONES-LOOP.md` §6 y §8.
- `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md`: la sección que ya existe.
- `aidlc-docs/construction/model-serving/evidence/cierre-demo.md` y `aidlc-docs/construction/reference-model/evidence/cierre-demo.md`: el formato.
- `tareas/U03-T01` a `tareas/U03-T05`, `bitacoras/U03-T0*.md` y `revisiones/U03-T0*/`: qué hizo cada tarea.
- `decision-registry/Makefile`.
- `CANDIDATAS.md`: las entradas «U3, …».

---

## Criterios de aceptación

Desde `vectra-risk/`, con las herramientas de `platform/install-tools.sh`. Ninguno toca el clúster.

- [ ] **CA-1** — Paso 19: N/A.
  ```bash
  test ! -d decision-registry/frontend
  ```
  Esperado: código 0.

- [ ] **CA-2** — Paso 20: `check` de la unidad y de platform, sobre `main` sin cambios de código.
  ```bash
  make -C decision-registry check && make -C platform check
  git diff --stat origin/main -- decision-registry/
  ```
  Esperado: código 0 en los dos `make`, y el `git diff` vacío. Registra en la bitácora el número de pruebas, la cobertura y el tiempo de cada uno.

- [ ] **CA-3** — Trazabilidad y `cierre-demo.md`.
  ```bash
  uv run python platform/tests/test_traceability.py --unit decision-registry --all
  grep -nE "^## (Comprobado|Diferido por la demo|Pendiente en U12|Candidatas abiertas|Quién ejecutó)" aidlc-docs/construction/decision-registry/evidence/cierre-demo.md
  git diff origin/main -- aidlc-docs/construction/decision-registry/evidence/cierre-demo.md | grep -E "^-\|" || echo "sin filas quitadas"
  ```
  Esperado: código 0 en la trazabilidad, las cinco secciones y «sin filas quitadas»: la lista de U03-T05 se conserva y solo se le agregan filas. Cada fila nueva de «Diferido por la demo» lleva identificador, paso y cita del recorte. Ninguna es de un paso que entra.

- [ ] **CA-4** — RL-4: el `make check` de todas las unidades, una vez al cerrar U3.
  ```bash
  for u in contracts platform identity-edge decision-registry governance reference-model model-serving; do make -C $u check || echo "FALLA $u"; done
  ```
  Esperado: ninguna línea «FALLA». Si una unidad ajena falla y el fallo también ocurre en `origin/main`, regístralo con la salida: no es de esta tarea.

- [ ] **CA-5** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/decision-registry-code-generation-plan.md | grep -E "^[-+]- \[.\]"
  ```
  Esperado: solo cambian las líneas de los Pasos 18 (sigue `[ ]` y gana la nota «consolidado en U12 Paso 18 (enmienda §8)»), 19 (`[x] (U03-T06)`) y 20 (`[x] (U03-T06, acotado a la demo)`). Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

No hay código nuevo. Sí hay un rojo: antes de escribir la lista nueva, corre `test_traceability.py --unit decision-registry --all` y registra en `bitacoras/U03-T06.md` qué identificadores marca. Justifica cada fila nueva con esa salida.

---

## Preguntas abiertas

**P-1 — Candidata prioritaria de U3 antes de kind.** `CANDIDATAS.md` tiene una entrada **«Prioritaria (U3, antes de la verificación en kind)»** (revisor, U03-T03 ronda 2, F-01). Dice dos cosas:
- `test_queries.py` da por buena la aserción del peor caso de `daily:query` tomando el mínimo de 3 medidas;
- la consulta no tiene tope por solicitud, así que una consulta sin versión puede retener la única conexión del pool `projections` y dejar sin conexión a `explanation`.

La forma que usa U9, con versión, tarda 0,14–0,21 s. La verificación en kind ahora es U12 Paso 18. Hay tres opciones:
- (a) dejarla nombrada en «Candidatas abiertas» de este cierre y abrir una tarea corta de código, `U03-T07`, antes de U12;
- (b) meter el arreglo en esta tarea;
- (c) dejarla para el cierre completo.

**Recomendación: (a).** Esta tarea es de documentación (enmienda §8). La forma que usan las demos (U9 con versión) no está afectada, pero el pool compartido sí puede tocar el flujo base durante la demo. Por eso conviene un arreglo propio y revisado antes de U12, no mezclado con el cierre. Si el usuario no responde, rige la recomendación para esta tarea. La decisión sobre `U03-T07` la toma el usuario.

---

## Notas

- Archivos que se modifican en su sitio: el plan de U3, `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md` y `CANDIDATAS.md` (solo si una candidata cambia de estado). Ningún archivo nuevo, salvo la bitácora.
- **Otros codificadores en paralelo:** no toques directorios de otras unidades.
- **Bitácora:** `bitacoras/U03-T06.md`, con la salida de CA-2 a CA-4, la salida previa de la trazabilidad y la justificación de cada fila nueva.
