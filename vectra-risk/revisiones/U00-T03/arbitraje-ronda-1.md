# U00-T03 — Arbitraje de la ronda 1 (orquestador, 2026-11-10)

Informe: `ronda-1.md`. Veredicto NO-VERDE, sin ROJO.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: `read_wire` entrega el token a los validadores del modelo que le pasan | **Entra en la ronda 2** | El objetivo de la tarea es que el token no se pueda alcanzar. Con esta ruta abierta, R2-01 queda cerrada solo en el papel. |
| F-02 NARANJA: `model_copy` hereda el sello y se salta la capa 1 al anidar | **Entra en la ronda 2** | La regresión la trae el propio diff: en `main`, anidar la copia exigía el token. |
| F-03 AMARILLO: la reescritura de `test_private_token.py` afloja dos comprobaciones | **Entra en la ronda 2** | Restaurarlas cuesta poco, y la reescritura es de esta tarea. |
| F-04 AMARILLO: el grep de CA-6 se contradice | Se acepta la lectura sobre `*.py`. Pasa a `CANDIDATAS.md`, como defecto de la plantilla de la tarea. | — |
| F-05 AMARILLO: la semilla solo se imprime si la prueba falla | Pasa a `CANDIDATAS.md`, junto a la candidata «imprimir la semilla en verde» que ya existe. | — |
| F-06 AMARILLO: el desvío de P-1 (`wrap` cambiado por el sello) | **Se acepta.** | El revisor reprodujo que `wrap` rompe el JSON estricto. El límite de `__new__` no importa para la demo. |
| Candidatas del bench (`derive` y `outcome`) | Pasan a `CANDIDATAS.md`. | — |

## Lo que se espera de la ronda 2
- **F-01.**
  - `read_wire` deja de pasar el token por `info.context`. Puede usar una `ContextVar` privada que solo lea `_has_token`, o limitarse a una lista cerrada de contenedores.
  - El espía del revisor (`rev-u00-t03-r1/probes/robo.py`) se lleva a una prueba. Esa prueba tiene un rojo previo y luego un verde, los dos registrados en la bitácora.
  - El cierre de R2-01 en `CANDIDATAS.md` tiene que decir lo que de verdad cierra.
- **F-02.**
  - `model_copy` sobre una `Recommendation` falla o borra el sello, de modo que anidar la copia vuelva a exigir el token.
  - Una prueba lo demuestra con el caso del revisor: `registry_entry_id=""`.
- **F-03.** Se restauran:
  - la prueba negativa de que el contrato `private-token` queda BROKEN si otro módulo importa `outcome._internal`;
  - la comprobación `hasattr(views, "CONSTRUCTION_TOKEN")`;
  - la búsqueda del token dentro de contenedores.
- **Pruebas que se corren otra vez**, en serie:
  - CA-1 a CA-8;
  - `make -C contracts check` y `make -C case-management check`;
  - `make -C scoring-explainability check` y `make -C decision-registry check`, porque importan `outcome`.

  Si el bench o `test_f04` fallan por carga, se anotan con su causa.
