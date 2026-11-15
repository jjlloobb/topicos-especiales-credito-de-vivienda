# 10 — Informe y estado final

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F10 (Informe y estado final).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: 30 min; la guía pide anotarla).

Entradas de esta fase: K-64, K-65.

### K-64 — El informe lista cada RT, demo e historia; salen no ejecutado US-106, …

- Demo: Base. Fuentes: `CANDIDATAS.md:641`, `tareas/U12-T05-imagen-y-documentacion.md:113`, `aidlc-docs/construction/plans/system-verification-code-generation-plan.md:209`.

**Resultado esperado.** El informe lista cada RT, demo e historia; salen no ejecutado US-106, 109, 603, 305, 604, 608, 609 y 610, RT3-b y 'a y d desplegados'; ninguno sale pasa sin evidencia

**Comando.** Previsto: `vectra-verification report`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| El informe lista cada RT, demo e historia; salen no ejecutado US-106, 109, 603, 305, 604, 608, 609 y 610, RT3-b y 'a y d desplegados'; ninguno sale pasa sin evidencia | _pendiente_ | _pendiente_ |

### K-65 — El cluster queda como estaba

- Demo: D1, D2. Fuentes: `aidlc-docs/construction/system-verification/functional-design/business-rules.md:130`, `tareas/U12-T04-demos-cli-y-manifiesto.md:587`.

**Resultado esperado.** El cluster queda como estaba: modelo de referencia activo, ninguna version congelado, sin InferenceService de staging, F22 encendido

**Comando.** Previsto: `estado-final.sh`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| El cluster queda como estaba: modelo de referencia activo, ninguna version congelado, sin InferenceService de staging, F22 encendido | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
