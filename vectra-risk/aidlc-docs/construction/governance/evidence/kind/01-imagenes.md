# Imágenes de `governance` y `model-validation-job` en kind-registry

**Estado: pendiente del operador.** Plantilla de U04-T07: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada sección con lo que obtuvo y cambia este estado a `completa` (o `fallida`, con el hallazgo).

- Guía: `governance/docs/paso-20-kind.md`, §2.
- Fecha y operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.

## Resultado esperado

`governance/docs/kind/imagenes.sh` termina en 0; los dos `docker push` dan un digest; el PR de digests (`values/kind/governance.yaml` y `apps/kind/governance.yaml`) está fusionado y `generate.py --check` termina en 0.

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
| `governance/docs/kind/imagenes.sh` termina en 0 | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Un defecto del chart o de las imágenes se reporta como defecto de U04-T06, no se arregla aquí.
