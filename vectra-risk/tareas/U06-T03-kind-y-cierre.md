# U06-T03 — Verificación en kind y cierre acotado de `model-serving`

**Unidad:** U6 `model-serving`
**Historias que verifica:** US-111, US-204 y US-609, en kind. Ninguna nueva.
**Depende de:**
- U06-T02 (PR #104, en `main`);
- **U01-T08** (credencial S3 de KServe): sin ella ningún predictor llega a Ready;
- **la decisión del usuario sobre el presupuesto de memoria de kind** (ver «Presupuesto»), registrada en `DECISIONES-LOOP.md` antes del despacho;
- para la parte del operador: U1–U4 instalados en kind (U04-T07 hace el arranque de la política y del modelo de referencia, P-7) y U04-T05b (`promotion-tool`).

**Se despacha** cuando U01-T08 esté fusionada y el usuario haya decidido el presupuesto. La parte del operador sigue la ruta crítica (RL-5).
**Rama:** `tarea/U06-T03`, desde `origin/main`.

Bloques E y F del plan de U6, fusionados como «E+F (11–13)» (`demo-recorte-funcional.md` §4):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 11 Verificación en kind | **E\*F** | Entran los escenarios 1 (promoción con 0 `version_mismatch`), 2 (rollback, el activo nunca baja de 2 réplicas) y 3 (RT3-a/d no listos, b listo). Se difieren el 4 (saturación), 5 (drenado) y 6 (carga) | Enmienda §3 U6 |
| 12 N/A | **N/A** | — | — |
| 13 Cierre | **E\*** | Cierre acotado, sin benchmark | Enmienda §3 U6 |

Rige RL-1 a RL-5. **AUTONOMIA-01:** el codificador no toca el clúster. Escribe la guía, los scripts y las plantillas de evidencia; el operador ejecuta tras el PR aprobado y adjunta la evidencia.

---

## Alcance

**Dentro:**

### Presupuesto de memoria de kind

Cifras del revisor de U06-T02 (`revisiones/U06-T02/ronda-1.md`, punto 5), con 532 MiB por pod (512 + 20 de proxy):

| Momento | Pods de U6 | Memoria pedida por U6 | Total en kind |
|---|---|---|---|
| M1 activa (`prod`) | 4 | +2,08 GiB | ≈ 8,09 GiB |
| Promoción (M1 y M2 en `prod`) | 8 | +4,16 GiB | ≈ 10,17 GiB |
| Tras la post-activación (M2 `prod`, M1 `inactive`) | 6 | +3,12 GiB | ≈ 9,13 GiB |

Más 0,27 GiB del predictor de staging. Además, `platform/tests/test_kind_profile.py` no cuenta los `InferenceService`.

Esta tarea:
1. **Amplía `requested_gib()`** de `test_kind_profile.py` para contar los `InferenceService` declarados en los values de kind de `model-serving` (réplicas mínimas por componente × requests + proxy), con su prueba (U1, autorizado por esta tarea).
2. **Aplica la decisión del usuario** registrada en `DECISIONES-LOOP.md` (subir `BUDGET_GIB` a la cifra decidida, o reducir el perfil en kind según DD-3 a). Si la decisión no está registrada, **detente y repórtalo**: no la tomes tú.

### Guía del operador (Paso 11)

`model-serving/docs/paso-11-kind.md`, con el formato de `identity-edge/docs/paso-16-kind.md` y de `governance/docs/paso-20-kind.md` (U04-T07). Para cada sección: comando, salida esperada y ruta de evidencia (`aidlc-docs/construction/model-serving/evidence/kind/<escenario>.md`).

1. **Imágenes:** build y push a `kind-registry` del predictor y del explicador, y el digest real en `vectra-risk-gitops/values/kind/model-serving.yaml` por PR (T1: sin firma).
2. **Paquetes en el model-store:** los de U5 (base, una segunda versión para la promoción y RT3-a/b/d) subidos por el procedimiento de `reference-model/docs/release.md` y registrados en governance (U04-T07 hace el registro del base). Una «M2» para la promoción: usa un paquete de U5 que pase el registro; regístralo en la bitácora.
3. **Escenario 1:** promoción M1 → M2 con tráfico continuo usando los cuatro PR de `promotion-tool` (U04-T05b): promoción, merge, sync manual, `mark_active`, post-activación. Evidencia: 0 respuestas `version_mismatch` durante la ventana. El tráfico lo genera un script de esta tarea (`model-serving/docs/kind/traffic.sh` o `.py`) contra `scoring-service` si U7 existe, o directo contra `:predict` de los dos `InferenceService` si no; en ese caso el escenario mide que cada respuesta trae el `model_version_id` del `InferenceService` que la sirvió, y la parte con U7 queda pendiente de U7 Paso 18.
4. **Escenario 2:** rollback a M1 (`rollback_pr`, `mark_active`): el activo nunca baja de 2 réplicas (muestreo de `kubectl get` durante el cambio).
5. **Escenario 3:** RT3-a y RT3-d en staging → componentes no listos; RT3-b → listo. Confirma aquí `/mnt/models/manifest.json` (riesgo `MODEL_DIR` de U06-T02), que el storage initializer se inyecta también en el explicador y que KServe propaga `vectra.io/serving-state` y `vectra.io/hpa-exempt` al `Deployment` (candidatas de U06-T02).
6. **Memoria:** `kubectl top` antes, durante y después de la promoción, contra la cifra del presupuesto (DD-3 b).

### Scripts

Lo repetible va en `model-serving/docs/kind/`, sin credenciales en el código. `shellcheck` en 0 y una prueba con `--dry-run` o dobles. No ejecutan `kubectl apply`, `helm install` ni `argocd app sync`: esas órdenes las escribe la guía para el operador.

### Cierre (Paso 13)

- `aidlc-docs/construction/model-serving/evidence/cierre-demo.md` completo, con el formato del de U5: lo comprobado (con enlace a cada evidencia), lo diferido (la sección que dejó U06-T02) y lo pendiente (escenarios con U7). Las filas de kind quedan «pendiente del operador» hasta que se adjunte.
- Plan: Paso 11 `[x] (U06-T03, acotado a la demo)` solo cuando el operador adjunte la evidencia; hasta entonces `[ ]` con «guía lista, pendiente del operador». Paso 12 `[x]`. Paso 13 `[x] (U06-T03, acotado a la demo)`.

**Fuera:**

- Escenarios 4, 5 y 6.
- Cualquier orden contra el clúster por parte del codificador.
- Cambios al chart o a las imágenes de U6, salvo un defecto que la guía revele: va a `CANDIDATAS.md` o se reporta.
- La credencial S3 (U01-T08).

---

## Archivos de contexto

- `aidlc-docs/construction/plans/model-serving-code-generation-plan.md` (Pasos 11 a 13) y `aidlc-docs/construction/model-serving/` (INF-U6-02; P-U6-02..05).
- `revisiones/U06-T02/ronda-1.md` y `ronda-2.md`, y `CANDIDATAS.md` (entradas de U6 y de kind).
- `model-serving/docs/values.md`, `model-serving/chart/` y `governance/promotion_tool/` (U04-T05b).
- `identity-edge/docs/paso-16-kind.md`, `tareas/U04-T07-kind-y-cierre.md` y `aidlc-docs/construction/reference-model/evidence/cierre-demo.md`.
- `platform/tests/test_kind_profile.py` y `demo-kind-alcance.md` §5 (DD-3).

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster.

- [ ] **CA-1** — Presupuesto: `uv run pytest platform/tests/test_kind_profile.py -v` en verde, con un caso que demuestra que los `InferenceService` de kind se cuentan (rojo primero: un `InferenceService` en los values de kind no cambiaba `requested_gib()`), y `BUDGET_GIB` o el perfil según la decisión registrada.
- [ ] **CA-2** — Guía: `test -s model-serving/docs/paso-11-kind.md`, con comando, salida esperada y ruta de evidencia para los escenarios 1, 2 y 3 y la memoria.
- [ ] **CA-3** — Scripts: `shellcheck model-serving/docs/kind/*.sh` en 0, su prueba en 0 y `! grep -rnE "kubectl apply|helm (install|upgrade)|argocd app sync" model-serving/docs/kind/`.
- [ ] **CA-4** — N/A: `test ! -d model-serving/migrations && test ! -d model-serving/frontend`.
- [ ] **CA-5** — Cierre: `make -C model-serving check` y `make -C platform check` en 0; `cierre-demo.md` con sus tres secciones; `--all` sin fallos nuevos.
- [ ] **CA-6** — Evidencia del operador (fuera del codificador): un archivo por escenario en `evidence/kind/`.

---

## Notas

- **Bitácora:** `bitacoras/U06-T03.md`.
