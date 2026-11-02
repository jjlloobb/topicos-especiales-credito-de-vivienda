# Respuesta a la ronda 1 — U01-T02

F-01: Corregido en el commit de la ronda 2: `ilm_idempotente.sh` recorre dos renders (values.yaml, y values.yaml + values-kind.yaml con sus 5 buckets lock) y `test_minio_ilm_rules_are_replaced_not_accumulated` esta parametrizado base/kind. M2, M3, M4 y M6 sobre values-kind.yaml ahora mueren en script y en pytest (bitacora, Ronda 2).
F-02: Corregido en el commit de la ronda 2: la prueba filtra las lineas `ilm rule` de cada bucket y exige exactamente `[rm, add]` en ese orden, con el `rm` literal `... || true`. M5 ahora muere tambien en pytest.
F-03: Aceptado como limitacion: con `customCommands` no se puede distinguir el error del `rm`; el porque queda en el comentario de `platform/data/minio/values.yaml`.
F-04: No es un defecto del diff: la nota de la tarea ("sin shell") es un error de especificacion; el Job corre `/bin/sh /config/custom-command` y el verde lo confirma. No edito el archivo de la tarea.
