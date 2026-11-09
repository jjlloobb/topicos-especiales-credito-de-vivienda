"""Tablas de conteo (`CountTable`) a partir de registros etiquetados o de marginales de un rango (domain-entities 2.1).

Los tipos llevan los mismos nombres de campo que los de U0 §9.4 (`CountTable`, `CountCell`), pero esta libreria no
importa `vectra_contracts` (P-U9-05): las entradas llegan como mapeos o como objetos con atributos.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

ATTRIBUTES: Final = ("sexo", "rango_edad", "region", "estrato")
BANDS: Final = ("lt_20", "20_30", "gt_30")
UNINFORMED: Final = "no_informado"
FAVORABLE: Final = "favorable"  # BR-U9-01: `revision_requerida` y `desfavorable` cuentan como NO favorables.
BAND_KEY: Final = "banda"  # clave de la banda en las etiquetas de monitoreo (U0 §2.2)


@dataclass(frozen=True)
class CountCell:
    group: str
    band: str
    favorable: int
    total: int

    def __post_init__(self) -> None:
        if self.band not in BANDS:
            raise ValueError(f"band_unknown:{self.band}")
        if self.favorable < 0 or self.total < 0 or self.favorable > self.total:
            raise ValueError(f"invalid_cell:{self.favorable}/{self.total}")


@dataclass(frozen=True)
class CountTable:
    attribute: str
    cells: tuple[CountCell, ...]


def _field(item: Any, name: str) -> Any:
    return item[name] if isinstance(item, Mapping) else getattr(item, name)


def _tables(accumulated: Mapping[str, Mapping[tuple[str, str], list[int]]]) -> dict[str, CountTable]:
    return {
        attribute: CountTable(
            attribute,
            tuple(
                CountCell(group, band, favorable, total)
                for (group, band), (favorable, total) in sorted(
                    accumulated[attribute].items(), key=lambda kv: (kv[0][0], BANDS.index(kv[0][1]))
                )
            ),
        )
        for attribute in ATTRIBUTES
    }


def counts_from_records(records: Iterable[Mapping[str, str]]) -> dict[str, CountTable]:
    """Una `CountTable` por atributo a partir de filas etiquetadas.

    Cada registro lleva `sexo`, `rango_edad`, `region`, `estrato`, `banda` y el `outcome` de BR-U7-04/05. Solo
    `favorable` cuenta como favorable (BR-U9-01).
    """
    accumulated: dict[str, dict[tuple[str, str], list[int]]] = {
        a: defaultdict(lambda: [0, 0]) for a in ATTRIBUTES
    }
    for record in records:
        favorable = int(record["outcome"] == FAVORABLE)
        for attribute in ATTRIBUTES:
            cell = accumulated[attribute][(record[attribute], record[BAND_KEY])]
            cell[0] += favorable
            cell[1] += 1
    return _tables(accumulated)


def counts_from_marginals(marginals: Iterable[Any]) -> dict[str, CountTable]:
    """Una `CountTable` por atributo a partir de los `MonitoringMarginalCount` de un rango (mapeos u objetos).

    Usa `attribute`, `group`, `band`, `result` y `count`; el campo `decision` no cambia el total. Es favorable el
    `result` `favorable` (BR-U9-01).
    """
    accumulated: dict[str, dict[tuple[str, str], list[int]]] = {
        a: defaultdict(lambda: [0, 0]) for a in ATTRIBUTES
    }
    for marginal in marginals:
        count = int(_field(marginal, "count"))
        cell = accumulated[_field(marginal, "attribute")][
            (_field(marginal, "group"), _field(marginal, "band"))
        ]
        cell[0] += count if _field(marginal, "result") == FAVORABLE else 0
        cell[1] += count
    return _tables(accumulated)
