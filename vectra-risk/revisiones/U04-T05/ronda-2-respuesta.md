# Respuesta del codificador a la ronda 1 — U04-T05 (ronda 2)

- F-01: Corregido: `initial_disparity` mide con el `outcome` de BR-U7-04/05 (`vectra_validation/outcome.py`, `confidence.py`); `revision_requerida` cuenta como no favorable. Oráculo a mano, incluida una prueba por cada causa; la mutación a `p < cutoff` hace fallar `test_the_job_gives_each_row_the_outcome_of_the_policy_and_not_the_score_below_the_cutoff`.
- F-02: Corregido solo lo que necesita F-01: el lanzador pasa la política activa completa en `VECTRA_POLICY` y el `cutoff` literal desapareció. `n_min`, umbral y `auc_target` quedan en `CANDIDATAS.md` (arbitraje).
- F-03: Corregido: el manifiesto monta `vectra-internal-ca` y fija `VECTRA_CA_BUNDLE`; la prueba usa el `ServiceTokenProvider` real contra un https local con el entorno del manifiesto.
- F-04: Corregido: `libgomp1=14.2.0-19`; `hadolint` v2.15.1 rc=0 y la imagen se construye.
- F-05: Corregido: NFR-U4-23 nombrado en la prueba que lo verifica; `--all` ya no lo lista.
- F-06: Fuera de alcance: ya en CANDIDATAS.md (arbitraje).
- F-07: Fuera de alcance: ya en CANDIDATAS.md (arbitraje).
- F-08: Fuera de alcance: ya en CANDIDATAS.md (arbitraje).
