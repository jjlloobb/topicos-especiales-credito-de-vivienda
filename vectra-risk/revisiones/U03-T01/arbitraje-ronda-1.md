# Arbitraje de la ronda 1 — U03-T01

Orquestador, 2026-11-08. Informe: `revisiones/U03-T01/ronda-1.md`. El veredicto literal es NO-VERDE, por un solo NARANJA y ningún ROJO.

## Regla

RL-2 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6: solo un ROJO bloquea. NARANJA y AMARILLO van a `CANDIDATAS.md`, salvo que rompan una de las cuatro demos.

## Decisión: la tarea pasa y se abre el PR

- **F-01 (NARANJA):** la protección de solo-anexar de `registry_idempotency_keys` existe, porque la sonda del revisor la confirmó, pero no tiene prueba. No rompe ninguna demo: la demo no prueba la mutación de esta tabla. Pasa a `CANDIDATAS.md` como **prioritaria**, para que entre en la tarea del Bloque C o D de U3, que toca el append.
- **F-02 a F-05 (AMARILLO):** van a `CANDIDATAS.md`. F-04, sobre el formato de los sellos de la génesis, se anota para la tarea del Paso 3 (`chain.canonicalize`), porque esa sí la necesita.
- **Las dos candidatas de diseño del revisor** (índices de `model_version_id` y `policy_version_id`; `idempotency_key UNIQUE` en domain-entities §1) van a `CANDIDATAS.md`. La segunda la decide el usuario.
- **Los desvíos 1 a 6 del codificador:** el revisor confirma que 1, 2 y 3 son necesidades técnicas reales, y que 4 y 6 no son desvíos. El 5, la imagen de las pruebas, queda en candidatas para el Paso 18.

**Limpieza pendiente:** al revisor se le negó detener un contenedor `postgres:17.9-trixie` que levantó él. El orquestador no lo detiene en su nombre. Se lo informa al usuario.
