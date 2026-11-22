# 11 — Opcionales

**Estado: no ejecutado.** F11 es opcional y no se corrio en esta verificacion (2026-11-20 y 2026-11-21, `kind-vectra`).

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F11 (Opcionales).
- Fecha: no aplica.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: no aplica.
- Duración real de la fase: 0 min, no ejecutada (estimada: 30 min; la guía pide anotarla).

Entradas de esta fase: K-66.

### K-66 — (a) El login de la herramienta con Keycloak caido a mitad

- Demo: ninguna. Fuentes: `CANDIDATAS.md:684`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:77`, `CANDIDATAS.md:625`, `CANDIDATAS.md:613`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:71`.

**Resultado esperado.** (a) El login de la herramienta con Keycloak caido a mitad: se cuelga o termina con error. (b) El apagado del worker con trabajo en vuelo (34 s frente a 40 s de gracia). (c) PBT-U8-07 abreviado contra el registro real

**Comando.** Previsto: `kubectl --context kind-vectra get pods -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-worker`.

```bash
no ejecutado
```

**Salida.**

```text
no ejecutado
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| (a) El login de la herramienta con Keycloak caido a mitad: se cuelga o termina con error. (b) El apagado del worker con trabajo en vuelo (34 s frente a 40 s de gracia). (c) PBT-U8-07 abreviado contra el registro real | no ejecutado: opcional; se priorizaron las cuatro demos | no ejecutado |

## Hallazgos

_Ninguno: la fase no se ejecuto._ Queda para una pasada posterior si se quiere medir el login con Keycloak caido y el resto de K-66.
