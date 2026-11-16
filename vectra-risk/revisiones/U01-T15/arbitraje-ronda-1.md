# U01-T15 — Arbitraje de la ronda 1 (orquestador, 2026-11-16)

Informe: `ronda-1.md`. El revisor escribió NO-VERDE **sin ningún ROJO**: un NARANJA (F-01) y tres AMARILLO. El veredicto se conserva tal cual en el informe.

**Decisión: no hay ronda 2; la tarea pasa a pull request.** RL-2 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6) dice que solo un ROJO bloquea, y que NARANJA y AMARILLO van a `CANDIDATAS.md`. El revisor corrió los cinco criterios y pasan, confirmó la premisa en el código de KServe v0.21.0 y comprobó con mutaciones que la exención no alcanza a otros namespaces ni a Deployment sin la etiqueta.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: el mínimo de 2 del **explicador** activo queda sin regla de admisión (la regla del `InferenceService` solo mira el predictor) | `CANDIDATAS.md`, con aviso al usuario | Defecto real y de pocas líneas, pero no afecta a ninguna demo: el chart de U6 fija 2 en kind y el rego `active-min-replicas` lo vigila en cada PR. **Riesgo:** el README y el comentario de la política dicen «vigila el mínimo» sin el matiz del explicador hasta que se arregle |
| F-02 AMARILLO: la exención depende de una etiqueta que cualquiera puede poner en `vectra-serving` | `CANDIDATAS.md` | Mismo patrón aceptado para Envoy (Z2) |
| F-03 AMARILLO: el barrido sustituye el `apiCall` de `require-pdb` por 1 | `CANDIDATAS.md` | El revisor comprobó que el chart rinde el PDB y que Argo CD lo aplica antes; falta la aserción negativa |
| F-04 AMARILLO: el fixture no trae `app: isvc.<name>` en las etiquetas del Deployment; la versión del `storage-initializer` está incrustada | `CANDIDATAS.md` | No cambia ninguna regla; se compara con el objeto real en el primer despliegue de U6 |

Precisión sobre el criterio CA-2: lo escribió el orquestador solo para el predictor, y por eso pasa aunque el punto 3 del alcance pedía el modelo activo entero. El hueco del explicador viene de la tarea, no del codificador.
