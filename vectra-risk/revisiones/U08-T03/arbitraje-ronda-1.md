# U08-T03 — Arbitraje de la ronda 1 (orquestador, 2026-11-11)

Informe: `ronda-1.md`. Veredicto NO-VERDE, sin ningún ROJO. Los 9 criterios pasan; el `bench_gate` de contracts falla por la carga de la máquina, con el código de contracts idéntico al de la base.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: el arrendamiento de 30 s dura menos que un lote, y el envío inmediato también se puede reclamar | **Entra en la ronda 2** | Es la propiedad «cada evidencia se reintenta una sola vez por ciclo con 2 réplicas», que el diff afirma y no cumple. Es un defecto del propio diff |
| F-02 NARANJA: PBT-U8-07 no recorre el camino abandono → decisión nueva y sobrevive a una mutación | **Entra en la ronda 2** | La tarea pide la PBT entera, y el diseño nombra ese escenario dentro de ella |
| F-03 NARANJA: el 401 sin `acr`/`auth_time` no tiene prueba | **Entra en la ronda 2** | El comportamiento existe pero nada lo fija, y el arreglo es barato |
| F-04 AMARILLO: la consulta que se reabre pisa `created_at` | Pasa a `CANDIDATAS.md` | Arreglarlo toca la migración de U08-T01 |
| F-05 AMARILLO: constantes fuera de `config.py`, con `LEASE` y `BACKOFF_JITTER` duplicados | **Entra en la ronda 2** | El nombre duplicado confunde a U08-T04, y el arreglo es acotado |
| F-06 AMARILLO: falta la salida roja de PBT-U8-07 y el mensaje del commit no coincide | **Entra en la ronda 2** (solo la bitácora) | El commit ya está hecho: basta con una nota en la bitácora |
| F-07 AMARILLO: parámetro `clock` sin usar | **Entra en la ronda 2** | Es trivial |

## Lo que se espera de la ronda 2
- **F-01:**
  - el arrendamiento cubre el peor lote, o se renueva por fila;
  - el envío inmediato inserta con `next_attempt_at = now + LEASE`;
  - una prueba con el registro lento (2 s) y 2 réplicas, la segunda arrancando a mitad del lote, comprueba que ninguna llave se envía dos veces en el ciclo. Se registra el rojo previo; el experimento E1 del revisor sirve de base.
- **F-02:**
  - PBT-U8-07 recorre de forma forzada la secuencia `lose_ack` → decisión → más de 24 h → decisión nueva, por ejemplo con `@precondition`;
  - el invariante compara el payload del registro con el de la fila `confirmada` (por `registry_entry_id`) y mide el momento por `evidence_id`;
  - la bitácora registra la mutación del revisor (en `_resolve_conflict`, confirmar la decisión nueva) en rojo con la PBT nueva, y el contador del recorrido en más de 0.
- **F-03:** pruebas para `acr=None` y `auth_time=None` en la decisión y en la consulta: 401, 0 filas en el outbox, 0 envíos y la métrica `unauthenticated`.
- **F-05:** las constantes pasan a `config.py` sin nombres repetidos. Las del reconciliador y las del worker se distinguen.
- **F-06:** una nota en la bitácora con la salida roja (o, si ya no se tiene, que lo diga) y la aclaración del commit.
- **F-07:** se quita el parámetro.
- **Se vuelven a correr:** CA-1 a CA-8 y `make -C case-management check`. `contracts` no cambia.
