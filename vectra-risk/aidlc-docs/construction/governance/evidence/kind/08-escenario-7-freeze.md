# Escenario 7: propagación del `freeze` hasta `serving-config` (pendiente de U7 Paso 18 para el extremo a extremo)

**Estado: pendiente del operador.** Plantilla de U04-T07: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada sección con lo que obtuvo y cambia este estado a `completa` (o `fallida`, con el hallazgo).

- Guía: `governance/docs/paso-20-kind.md`, §7.
- Fecha y operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.

## Resultado esperado

`medir-freeze.sh` imprime `maximo` de 6 o menos en las 2 réplicas; reactivación con `cumplimiento-1` (204). La parte de scoring (`FailClosed(model_frozen)`) sigue pendiente de U7.

## Comando

```bash
_pendiente: el comando exacto que se ejecutó_
```

## Salida

```text
_pendiente: la salida real, sin tokens_
```

## Esperado contra obtenido

| Esperado | Obtenido | Cumple |
|---|---|---|
| `medir-freeze.sh` imprime `maximo` de 6 o menos en las 2 réplicas | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Un defecto del chart o de las imágenes se reporta como defecto de U04-T06, no se arregla aquí.
