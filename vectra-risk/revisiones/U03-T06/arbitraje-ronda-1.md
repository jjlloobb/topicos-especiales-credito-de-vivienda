# U03-T06 — Arbitraje de la ronda 1 (orquestador, 2026-11-11)

Informe: `ronda-1.md` y su anexo de cierre. El veredicto es NO-VERDE, sin ROJO ni NARANJA. CA-2 y CA-4 quedaron sin confirmar porque la máquina no dejó terminar los `check`: la primera vez hubo SIGTERM externo, y la segunda la corrida se colgó 25 h después de una suspensión.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| CA-2 y CA-4 sin confirmar | No se repiten los `check` de todas las unidades en esta tarea | El diff toca solo documentación (4 archivos) y no puede cambiar el resultado de ninguna suite. La única F que se observó, `test_f04`, falla igual en la base y la corrige U03-T07. U12 Paso 18 corre la verificación completa. |
| F-06 AMARILLO: el cierre cita como pendiente el fallo de identity-edge que resolvió U02-T20 | **Entra en la ronda 2** | El cierre quedó desactualizado con el merge y corregirlo es barato |
| F-07 AMARILLO: el cierre cita la base `fe0c9f3` | **Entra en la ronda 2** | Hay que decir sobre qué base se midió y que no se volvió a correr después del merge |
| F-08 AMARILLO: P-1 aparece como pendiente | **Entra en la ronda 2** | U03-T07 ya está abierta; el cierre debe apuntar a ella |
| F-02 a F-05 AMARILLO (ronda 1) | **Entran en la ronda 2** | Son ajustes de texto del mismo documento |
| Contenedores de Testcontainers huérfanos | Pasan a `CANDIDATAS.md` | — |

## Lo que se espera de la ronda 2
- Solo documentación:
  - `cierre-demo.md`, por F-02 a F-08;
  - la bitácora, con una nota de que las líneas 70 a 80 son históricas;
  - una entrada en `CANDIDATAS.md`.
- Hay que volver a correr CA-1, CA-3 y CA-5, que son baratos: trazabilidad, secciones y plan.
