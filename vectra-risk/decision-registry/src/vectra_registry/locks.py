"""Llaves de *advisory lock* (domain-entities §6; BR-U3-04, 17).

Son constantes de la unidad: el append toma `pg_advisory_xact_lock(APPEND_LOCK)` y la reconstruccion del agregador
`pg_try_advisory_lock(REBUILD_LOCK)`. Deben ser distintas: una prueba lo verifica.
"""

from typing import Final

#: `0x56520001`: serializa los appends (BR-U3-04).
APPEND_LOCK: Final = 1448214529
#: `0x56520002`: reconstruccion del agregador (BR-U3-17).
REBUILD_LOCK: Final = 1448214530
