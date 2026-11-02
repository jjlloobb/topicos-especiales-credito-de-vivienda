# Respuesta a la ronda 1 — U01-T07

F-01: Corregido: test_postgres_requires_tls exige ahora `hostnossl all all all reject` en el render; con la mutación M1 (quitar esa línea) falla 3 de 3 (kind, staging, prod).
F-02: Corregido: el comentario de clusters.yaml ya no afirma el orden del operador, dice que está POR VERIFICAR en el Paso 19; las comprobaciones (a)-(d) quedan en la bitácora como pendientes del Paso 19.
F-03: Corregido: la prueba toma `INTERNAL_CA` de drill.py y exige que `mountPath + "/" + clave del Bundle vectra-internal-ca` (leída de mesh/certificates.yaml) sea igual a esa ruta.
Candidata (Cluster efímero sin reject): Corregido en esta tarea por arbitraje: restore-cluster.sh lleva el mismo `pg_hba` y test_the_ephemeral_cluster_rejects_plain_text_connections lo cubre (falla al quitar el reject).
