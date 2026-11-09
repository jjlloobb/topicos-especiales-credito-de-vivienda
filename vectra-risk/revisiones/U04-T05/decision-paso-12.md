# Decisión sobre el Paso 12 — U04-T05

Orquestador, 2026-11-09. En la ronda 1 el codificador se detuvo en el Paso 12 (`promotion-tool`), en el punto de detención de la tarea: el diseño de U6 no fija las claves de `vectra-risk-gitops/values/<env>/model-serving.yaml` (raíz, perfil, `model_version_id`, `storageUri`, réplicas, HPA, PDB, recursos, `priorityClassName`, ni cómo se representan el alta, el retiro o el perfil `prod`). El plan de U6 asigna ese esquema a su Paso 7 (bloque C+D), que todavía no existe. El codificador no escribió nada de `governance/promotion_tool/`.

## Decisión (del usuario, 2026-11-09)

- **U04-T05 queda con el Paso 13** (`model-validation-job`, modo `validacion`). Se revisa y se fusiona así.
- **El Paso 12 pasa a una tarea nueva, U04-T05b**, que se despacha después de que U6 cierre sus Pasos 6 y 7 (plantilla del `InferenceService` y esquema de values de `promotion-tool`). Su alcance y su aceptación son los del Paso 12 de `tareas/U04-T05-promotion-tool-y-validation-job.md` (CA-1 y los pares rojo-verde del Paso 12), sobre el esquema que fije U6.
- La ruta crítica no cambia: U04-T06 no usa `promotion-tool`, y U04-T07 (kind) ya dependía de U6 C+D. U4 pasa de 7 a 8 tareas.

## Efecto en los criterios de U04-T05

- CA-1 sale de esta tarea y pasa a U04-T05b.
- CA-6: el Paso 12 sigue `[ ]` en el plan, con la nota «pasa a U04-T05b (esquema de U6 Paso 7)». El Paso 13 en `[x] (U04-T05, acotado a la demo)`; 14 y 15 `[ ]` con su nota de diferido.
