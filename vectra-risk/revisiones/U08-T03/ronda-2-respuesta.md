# U08-T03 — respuesta del codificador a la ronda 1

F-01: Corregido en 7ad2c89: el arrendamiento del reconciliador es `RECONCILER_LEASE` (125 s, cubre el peor lote) y el envío inmediato de la decisión y de la consulta inserta con `next_attempt_at = now + RECONCILER_LEASE`; pruebas con 2 réplicas y registro de 2 s (rojo previo 3 failed, verde 3 passed, en la bitácora).
F-02: Corregido en 7ad2c89: PBT-U8-07 recorre de forma forzada `lose_ack` → decisión → 25 h → decisión nueva (31 recorridos en la corrida registrada), compara el payload del registro con el de la fila `confirmada` por `registry_entry_id` y mide el momento por evidencia; la mutación del revisor queda en rojo (1 failed, en la bitácora).
F-03: Corregido en 7ad2c89: pruebas con `acr=None` y `auth_time=None` en decisión y consulta (401, 0 filas, 0 envíos, métrica `unauthenticated` +2); rojo previo con el guard quitado (500 en lugar de 401).
F-04: Fuera de alcance: ya pasó a `CANDIDATAS.md` por el arbitraje (guardar el plazo de abandono en otra columna toca la migración de U08-T01).
F-05: Corregido en 7ad2c89: las constantes pasan a `config.py` sin nombres repetidos; las del reconciliador llevan el prefijo `RECONCILER_` y se distinguen de `LEASE` y `BACKOFF_*` del worker; pruebas en `tests/unit/test_config.py`.
F-06: Corregido en la bitácora (sección «F-06»): la salida del primer rojo de CA-2 se sobrescribió y se dice así; el mensaje de `520741a` es inexacto (solo añade la bitácora) y no se reescribe la historia.
F-07: Corregido en 7ad2c89: `handlers()` ya no recibe el parámetro `clock`.
