# Escenario 4: rollback a la versión `inactivo` (US-208)

**Estado: pendiente del operador.** Plantilla de U04-T07: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada sección con lo que obtuvo y cambia este estado a `completa` (o `fallida`, con el hallazgo).

- Guía: `governance/docs/paso-20-kind.md`, §6.
- Fecha y operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.

## Resultado esperado

M1 pasa a `inactivo` al activar M2; `rollback-pr` abre un PR de un commit; tras merge, sync y `mark-active`, M1 vuelve a `activo` y M2 queda `inactivo`.

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
| M1 pasa a `inactivo` al activar M2 | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Un defecto del chart o de las imágenes se reporta como defecto de U04-T06, no se arregla aquí.
