# U08-T02 — Arbitraje de la ronda 1 (orquestador, 2026-11-10)

Informe: `ronda-1.md`, NO-VERDE, sin ningún ROJO. Los ocho criterios de aceptación pasan con la ejecución del revisor.

RL-2 (`demo-kind-alcance.md` §6) manda los NARANJA a `CANDIDATAS.md`. F-01 se trató aparte y se llevó al usuario, por dos razones: rompe una garantía central de U0 (P-U0-03, capa 3; AUTONOMIA-06), y la introduce este mismo diff (precedente: `revisiones/U02-T13/arbitraje-ronda-1.md`). **Decisión del usuario (2026-11-10): ronda 2 de contención más una tarea de U0.**

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: `views.py` expone `CONSTRUCTION_TOKEN` y permite fabricar una `Recommendation` con un `registry_entry_id` inventado | **Entra en la ronda 2 (contención)** y **se abre una tarea de U0** (vía pública de lectura) | Decisión del usuario. La contención evita que el atajo se propague; la tarea de U0 lo elimina antes de U08-T03 |
| F-02 AMARILLO: la dimensión «anonimizado» de PBT-U8-04 no prueba `identifiers` | Pasa a `CANDIDATAS.md` | RL-2. La cubre un ejemplo |
| F-03 AMARILLO: ninguna prueba exige jitter | Pasa a `CANDIDATAS.md` | RL-2 |
| F-04 AMARILLO: razones fuera de `ProblemReason` y `NO_FACTORS` mutable | Pasa a `CANDIDATAS.md` | RL-2. Hay que decidirlo antes del Bloque D |
| F-05 AMARILLO: `persistent_failure` trata dos anomalías de forma distinta | Pasa a `CANDIDATAS.md` | RL-2 |
| F-06 AMARILLO: conteo mal escrito en la bitácora | **Entra en la ronda 2** | Es una corrección de evidencia, de una línea |

## Lo que se espera de la ronda 2

- **F-01, contención en U8 (sin tocar U0):**
  - `CONSTRUCTION_TOKEN` deja de estar accesible a nivel de módulo en `views.py`: no hay `_CONTEXT` ni ningún otro nombre importable que lo contenga. Una prueba lo comprueba sobre el módulo cargado.
  - `case-management/.importlinter` prohíbe `vectra_contracts.outcome._internal` a todo `vectra_case`, con una única excepción, documentada, para `vectra_case.views`, que cita la tarea de U0 que la retira.
  - Una prueba con rojo previo demuestra que, si otro módulo de `vectra_case` lo importa, `lint-imports` falla.
  - La sonda del revisor (`Recommendation.model_validate_json(..., context=vectra_case.views._CONTEXT)`) deja de funcionar.
  - `logic.md` y `CANDIDATAS.md` registran que es un rodeo temporal hasta la tarea de U0.
- **F-06:** se corrige el conteo de CA-3 en la bitácora, sin borrar la línea original.
- **F-02 a F-05:** quedan registrados en `CANDIDATAS.md`, cada uno citando `ronda-1.md`.
- **CA-1 a CA-8** se vuelven a correr con sus comandos literales.
