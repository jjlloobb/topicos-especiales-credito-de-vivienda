# U02-T17 — Arbitraje de la ronda 1 (orquestador, 2026-11-07)

Informe: `ronda-1.md`, NO-VERDE.

| Hallazgo | Decisión |
|---|---|
| F-01 NARANJA: el runbook `rate-limit-backend-down` sugiere que falta un solo StatefulSet de Valkey | **Ronda 2.** El runbook dice que la rama por ausencia de Valkey dispara solo si faltan las series de los dos StatefulSets, y que la pérdida de uno solo no la cubre ninguna alerta hoy, con un enlace a la candidata |
| F-03 AMARILLO: comentario engañoso en `identity-edge-rules-b12-b14-test.yaml:159` | **Ronda 2**, porque es de una línea: el comentario dice lo que espera el caso `7x40` |
| F-02 AMARILLO: `hardening_problems` busca subcadenas y no ve el operador | `CANDIDATAS.md`. Promtool ya atrapa las dos mutaciones |
| Candidata: si desaparece un solo StatefulSet de Valkey, ninguna alerta avisa | `CANDIDATAS.md`. Es una decisión de diseño (P-U2-09) y no cabe en B13 |

## Lo que se espera de la ronda 2

- Solo F-01 y F-03. No cambia ninguna expresión de regla.
- Si el texto nuevo del runbook lo puede vigilar la prueba de contenido de runbooks que agregaste en la ronda 1, agrégalo y registra su rojo.
- CA-1 a CA-5, con CA-5 en serie después de CA-4.
