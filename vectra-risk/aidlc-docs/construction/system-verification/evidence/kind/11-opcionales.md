# 11 — Opcionales

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F11 (Opcionales).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: 30 min; la guía pide anotarla).

Entradas de esta fase: K-66.

### K-66 — (a) El login de la herramienta con Keycloak caido a mitad

- Demo: ninguna. Fuentes: `CANDIDATAS.md:684`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:77`, `CANDIDATAS.md:625`, `CANDIDATAS.md:613`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:71`.

**Resultado esperado.** (a) El login de la herramienta con Keycloak caido a mitad: se cuelga o termina con error. (b) El apagado del worker con trabajo en vuelo (34 s frente a 40 s de gracia). (c) PBT-U8-07 abreviado contra el registro real

**Comando.** Previsto: `kubectl --context kind-vectra get pods -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-worker`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| (a) El login de la herramienta con Keycloak caido a mitad: se cuelga o termina con error. (b) El apagado del worker con trabajo en vuelo (34 s frente a 40 s de gracia). (c) PBT-U8-07 abreviado contra el registro real | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
