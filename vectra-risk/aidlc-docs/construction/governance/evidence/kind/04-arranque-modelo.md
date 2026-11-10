# Arranque (P-7): registro del modelo de referencia (US-201)

**Estado: pendiente del operador.** Plantilla de U04-T07: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada sección con lo que obtuvo y cambia este estado a `completa` (o `fallida`, con el hallazgo).

- Guía: `governance/docs/paso-20-kind.md`, §5.1.
- Fecha y operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.

## Resultado esperado

`POST /v1/models` responde 200 con `state: registrado`; la convención `s3://model-store/<model_version_id>/<archivo>` de `release.md` se confirma (o se registra la diferencia).

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
| `POST /v1/models` responde 200 con `state: registrado` | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Un defecto del chart o de las imágenes se reporta como defecto de U04-T06, no se arregla aquí.
