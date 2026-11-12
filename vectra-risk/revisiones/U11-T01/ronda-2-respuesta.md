# U11-T01 — respuesta del codificador a la ronda 1 (ronda 2)

Código en `65f3f5a`. Evidencia en `bitacoras/U11-T01.md` (sección «Ronda 2»).

- F-01: Corregido en 65f3f5a: PBT-U11-01 tiene un oráculo por definición de la tasa de consulta (total, por canal y ventanas diarias); las dos mutaciones del revisor (ventana diaria y semana publicada de 8 días) quedan en rojo; `compute` no cambió (el oráculo no encontró defecto).
- F-02: Corregido en 65f3f5a: NFR-U11-21 (docstring de `model.py`) y NFR-U11-10 (`config.py`) citados y trazados; NFR-U11-02, 03 y 13 no se escriben en `product-metrics/`, como manda el arbitraje.
- F-03: Corregido en 65f3f5a: los rangos de BR-U11-09 son constantes con nombre en `config.py` y `params.parse` y sus mensajes las usan.
- F-04: Corregido en 65f3f5a: PBT-U11-02 exige que una pasada con fallo en una página termine en `ReadError` y deje el estado anterior; la mutación `try/except ReadError: pass` queda en rojo.
- F-05: Corregido en 65f3f5a: el comentario explica el 2 esperado.
- F-06: Corregido en 65f3f5a: `channel` vacío y `model_version_id` sin tope se aceptan (el contrato de U0 no los limita), con prueba; `"human_decision"` usa `EntryType`.
- Candidata de `test_traceability.py` (archivos sin sufijo): registrada en `CANDIDATAS.md`.
