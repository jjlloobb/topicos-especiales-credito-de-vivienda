# Arranque (P-7): política de referencia activa

**Estado: pendiente del operador.** Plantilla de U04-T07: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada sección con lo que obtuvo y cambia este estado a `completa` (o `fallida`, con el hallazgo).

- Guía: `governance/docs/paso-20-kind.md`, §4 y `governance/runbooks/kind-politica-de-referencia.md`.
- Fecha y operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.

## Resultado esperado

`cro-2` propone (200, `propuesta`), `cro-1` aprueba (204), `GET /v1/policies` con la política `activa` y la misma `policy_version_id` en `governance-db`; vigencia normativa de `reference-policy.json` cubre la fecha de la demo.

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
| `cro-2` propone (200, `propuesta`), `cro-1` aprueba (204), `GET /v1/policies` con la política `activa` y la misma `policy_version_id` en `governance-db` | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Un defecto del chart o de las imágenes se reporta como defecto de U04-T06, no se arregla aquí.
