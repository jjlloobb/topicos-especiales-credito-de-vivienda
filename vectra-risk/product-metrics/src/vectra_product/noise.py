"""Dias consecutivos bajo el piso de la tasa de consulta (BR-U11-07, US-504). Funcion pura, sin E/S."""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from typing import NamedTuple


class DayWindow(NamedTuple):
    """La ventana movil de 7 dias que termina un dia UTC: decisiones atribuibles con la explicacion vista y todas las atribuibles."""

    viewed: int
    decisions: int


def days_below_floor(windows: Sequence[DayWindow], floor: float, min_decisions: int) -> int:
    """Cuenta hacia atras desde la ultima ventana (la que termina ayer; `windows` va de la mas vieja a la mas nueva).

    - menos de `min_decisions` decisiones: no suma ni reinicia, sigue con el dia anterior;
    - tasa < `floor`: suma uno y sigue;
    - tasa >= `floor`: para.

    El piso se compara como el decimal que el archivo de parametros declara (`0.6` es 3/5), no como el doble mas cercano: una tasa
    de exactamente F nunca cuenta como «bajo el piso».
    """
    limit = Fraction(repr(floor))
    count = 0
    for window in reversed(windows):
        if window.decisions < min_decisions:
            continue
        if Fraction(window.viewed, window.decisions) >= limit:
            break
        count += 1
    return count
