# U04-T07 — Verificación en kind y cierre acotado de `governance`

**Unidad:** U4 `governance`
**Historias que verifica:** US-201, US-202, US-204, US-206 y US-208, en kind. Ninguna nueva.
**Depende de:**
- U04-T06 fusionado (chart, Application e imágenes);
- U1, U2 y U3 instalados en kind;
- para los escenarios 2 y 3: U5 (paquete de referencia, ya cerrado) y **U6 C+D** fusionado (plantilla del `InferenceService` y esquema de values de `promotion-tool`);
- para el escenario 7 completo: U7 y U9. Hasta entonces queda **pendiente**, como manda el plan.

**Se despacha** cuando U04-T06 esté fusionado. La parte del operador sigue el orden de la ruta crítica (RL-5).
**Rama:** `tarea/U04-T07`, desde `origin/main`.

Bloques H e I del plan de U4, fusionados como «H+I (20–22)» (`demo-recorte-funcional.md` §4).

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 20 Verificación en kind | **E\*F** | Entran los escenarios 2 (validación de referencia), 3 (promoción), 4 (rollback) y 7 (freeze ≤ 6 s), más el **arranque** de la política y del modelo de referencia (P-7). Se difieren el 1 (k6), 5, 6, 8 y 9 | Enmienda §3 U4; P-7 |
| 21 Frontend | **N/A** | — | — |
| 22 Cierre | **E\*** | Cierre acotado a la demo, con `evidence/cierre-demo.md` | Alcance §2.4 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6). **AUTONOMIA-01:** el codificador no toca el clúster. Escribe la guía, los scripts y las plantillas de evidencia. El operador (una persona) ejecuta en kind después de que el PR esté aprobado, y adjunta la evidencia.

---

## Alcance

**Dentro:**

### Guía del operador (Paso 20)

`governance/docs/paso-20-kind.md`, con el formato de `identity-edge/docs/paso-16-kind.md`. Para cada sección: el comando exacto, la salida esperada y dónde se guarda la evidencia (`aidlc-docs/construction/governance/evidence/kind/<escenario>.md`).

1. **Imágenes.** Build y push a `kind-registry` de `governance` y `model-validation-job`, y el digest real en `vectra-risk-gitops/values/kind/governance.yaml` por PR (T1: sin firma).
2. **Sync** manual de la wave 5 (`governance`) y comprobación de que la migración terminó y el servicio está `Ready`.
3. **Arranque (P-7)**, antes de U6 Paso 11:
   - **Política activa**: el runbook `governance/runbooks/kind-politica-de-referencia.md` de U04-T06 (`cro-2` propone y `cro-1` aprueba, P-9). Lectura de vuelta: `GET /v1/serving-config` con `policy_version_id`.
   - **Modelo de referencia**: registro del paquete de U5 (`reference-model/docs/release.md`, paso 4) → `…/validations` → informe → `…/approval` → `promotion-tool` (`create_promotion_pr`, revisión y merge, sync manual, `mark_active`). Esto cubre a la vez los escenarios 2 y 3. Confirma aquí la convención de rutas `<bucket>/<model_version_id>/<archivo>` del `release.md` (candidata de U05-T04, **[PENDIENTE U4]**) y regístrala.
   - La vigencia normativa de `reference-policy.json` cubre la fecha de la demo (enmienda §5.3). Si no, se reporta.
4. **Escenario 2**: validación con el modelo de referencia → informe en ≤ 30 min, con `initial_disparity` no vacía. El Job termina `Complete` con el proxy de Linkerd detenido (Paso 13).
5. **Escenario 3**: promoción de punta a punta (PR de un commit, merge, sync, `mark_active`).
6. **Escenario 4**: rollback a la versión `inactivo` (US-208), con `rollback_pr` y `mark_active`. Requiere una segunda versión: usa uno de los paquetes de U5 que pase el registro.
7. **Escenario 7**: propagación del `freeze` en ≤ 6 s. Con U7 y U9 ausentes, se mide solo hasta `serving-config` (el `etag` y el estado cambian en ≤ 6 s en las 2 réplicas) y el escenario queda **pendiente** hasta U7 Paso 18.
8. **Memoria**: `kubectl top` de `vectra-app` antes y después de governance (DD-3 b).

### Scripts

Lo repetible de la guía va en `governance/docs/kind/*.sh`, sin credenciales en el código: tokens por variable de entorno o por el login del usuario sintético. Cada script se comprueba con `shellcheck` y con una prueba que corre `--dry-run` (o equivalente) contra dobles. No ejecutan `kubectl apply`, `helm install` ni `argocd app sync`: esas órdenes las escribe la guía para el operador.

### Cierre (Paso 22)

- `aidlc-docs/construction/governance/evidence/cierre-demo.md` completo, con el formato de `aidlc-docs/construction/reference-model/evidence/cierre-demo.md`: lo comprobado (con enlace a cada evidencia), lo diferido (la sección que dejó U04-T06) y lo pendiente de otras unidades (escenario 7). Las filas de evidencia de kind quedan como «pendiente del operador» hasta que se adjunte.
- `aidlc-docs/construction/governance/code/` con el resumen final de la unidad, si el plan lo pide.
- Plan: Paso 20 `[x] (U04-T07, acotado a la demo)` **solo cuando el operador adjunte la evidencia**; hasta entonces, `[ ]` con la nota «guía lista, pendiente del operador». Paso 21 `[x]`. Paso 22 `[x] (U04-T07, acotado a la demo)`.

**Fuera:**

- Escenarios 1 (k6, T3), 5 (`governance-db` pausada), 6 (registro caído), 8 (`branch-protection-check`, Paso 14 en D) y 9 (US-306).
- Cualquier orden contra el clúster por parte del codificador.
- Cambios de código del servicio. Si la guía revela un defecto, va a `CANDIDATAS.md` o se reporta al orquestador.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/governance-code-generation-plan.md`: Pasos 20 a 22.
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §1.0 (flujo base y arranque), §3 U4, §5.3 y §6 (P-7, P-9).
- `identity-edge/docs/paso-16-kind.md` (formato de guía del operador).
- `aidlc-docs/construction/reference-model/evidence/cierre-demo.md` y `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md`.
- `reference-model/docs/release.md` y `CANDIDATAS.md` (entradas de U5 sobre rutas y registro).
- `governance/runbooks/`, `governance/promotion_tool/` y `governance/validation_job/`.

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster.

- [ ] **CA-1** — Guía completa: `test -s governance/docs/paso-20-kind.md` y cada escenario que entra (2, 3, 4, 7) y el arranque tienen comando, salida esperada y ruta de evidencia. Lectura: `grep -nE "^## " governance/docs/paso-20-kind.md`.
- [ ] **CA-2** — Scripts: `shellcheck governance/docs/kind/*.sh` en 0, la prueba `governance/tests/unit/test_kind_scripts.py` en 0 y `! grep -rnE "kubectl apply|helm (install|upgrade)|argocd app sync" governance/docs/kind/`.
- [ ] **CA-3** — Frontend N/A: `test ! -d governance/frontend`.
- [ ] **CA-4** — Cierre: `make -C governance check` en 0, `uv run python platform/tests/test_traceability.py --unit governance --all` en 0 y `cierre-demo.md` con las tres secciones (comprobado, diferido, pendiente).
- [ ] **CA-5** — `make -C platform check` en 0 (RL-4).
- [ ] **CA-6** — Evidencia del operador (fuera del codificador): un archivo por escenario en `evidence/kind/`, con comando, salida y resultado esperado contra el obtenido. El revisor del PR la lee cuando el operador la adjunta; el PR puede fusionarse con la guía y la evidencia pendiente, como hizo U2.

---

## Notas

- Si al escribir la guía algo del chart o de las imágenes impide el arranque (por ejemplo, falta un value de kind), **detente y repórtalo**: es un defecto de U04-T06, no se arregla aquí.
- **Bitácora:** `bitacoras/U04-T07.md`.
