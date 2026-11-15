# 04 — Flujo base (puerta de las cuatro demos)

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F4 (Flujo base (puerta de las cuatro demos)).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: 15 min; la guía pide anotarla).

Entradas de esta fase: K-38.

### K-38 — Humo de punta a punta

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:40`, `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:73`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:52-71`.

**Resultado esperado.** Humo de punta a punta: una solicitud por el gateway llega a listo con registry_entry_id; la explicacion por el BFF; una decision de analista-1; el append con ack

**Comando.** Previsto: `humo flujo --delivery /verification/reference-model/.out`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Humo de punta a punta: una solicitud por el gateway llega a listo con registry_entry_id; la explicacion por el BFF; una decision de analista-1; el append con ack | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
