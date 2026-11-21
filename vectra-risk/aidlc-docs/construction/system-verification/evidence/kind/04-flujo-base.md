# 04 — Flujo base (puerta de las cuatro demos)

**Estado: completa.** Llenada el 2026-11-20 con lo que se obtuvo contra `kind-vectra`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F4 (Flujo base (puerta de las cuatro demos)).
- Fecha: 2026-11-20 (jornada 1), entre las 12:27 y las 13:00 UTC.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: 9dc027f.
- Duración real de la fase: unos 5 min (estimada: 15 min; la guía pide anotarla).

Entradas de esta fase: K-38.

### K-38 — Humo de punta a punta

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:40`, `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:73`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:52-71`.

**Resultado esperado.** Humo de punta a punta: una solicitud por el gateway llega a listo con registry_entry_id; la explicacion por el BFF; una decision de analista-1; el append con ack

**Comando.** Previsto: `humo flujo --delivery /verification/reference-model/.out`.

```bash
humo flujo --delivery /verification/reference-model/.out
```

**Salida.**

```text
solicitud aceptada: caso 6a33a846-04bf-4f4e-b919-69bfa73d2390 (la cabecera de escenario se acepto: K-36)
OK   caso listo con registry_entry_id 30
OK   decision registrada con ack: registry_entry_id 32
OK   /api/console/models con ingeniero-1: 1 versiones
OK   /api/console/freezes con cumplimiento-1
estado HTTP de cada llamada:
  200 GET /api/console/cases/{id} x2
  200 GET /api/console/freezes
  200 GET /api/console/models
  200 POST /api/console/cases/{id}/decision
  204 POST /api/console/cases/{id}/explanation-views
  200 POST /api/intake/v1/intake/applications
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Humo de punta a punta: una solicitud por el gateway llega a listo con registry_entry_id; la explicacion por el BFF; una decision de analista-1; el append con ack | caso 6a33a846 listo con registry_entry_id 30; decision con ack (registry_entry_id 32); explicacion 204; ningun 401 ni 429 | si |

## Hallazgos

_Ninguno._ `humo modelos` da una sola version: `mv-2026-01-01-8a98ab02`, `activo` (el modelo de referencia; F10 lo compara).
