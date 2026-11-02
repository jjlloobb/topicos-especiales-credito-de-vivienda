# Loop de agentes de Vectra Risk

Contratos del módulo 6: el orquestador despacha y arbitra, el codificador implementa, el revisor juzga y **una persona fusiona**. Un agente nunca fusiona ni aplica cambios a un clúster.

- `orquestador.md`: contrato de la sesión principal.
- `.claude/agents/`, en la raíz del repositorio: codificador y revisor.
- `plantilla-tarea.md`: plantilla de los archivos de `tareas/`.

En este proyecto, `tareas/` reemplaza a `unidades-y-tareas.md`. Las tareas `U01-*` salen de los pendientes de U1, ya cerrada para kind; las `U02-*` salen del plan de U2.

## Orden de despacho

| Paso | Tareas | Por qué |
|---|---|---|
| 1 | `U01-T01`, sola y observada | Para ver una ronda completa |
| 2 | Ola en paralelo: `U01-T03`, `U01-T05`, `U01-T06` | No comparten archivos |
| 3 | `U01-T04` y `U01-T02` | `U01-T02` es la más difícil y puede tomar varias rondas |
| 4 | `U02-T01`, sola | Primer paso de U2: el esqueleto de `identity-edge/` |
| 5 | `U02-T02`, sola | Completa el Paso 1 con los directorios de §1 que faltaron |
| 6 | `U00-T01`, `U00-T02` y `U01-T07` | Desvíos frente al diseño hallados en la revisión de conformidad del 2026-11-02. `U00-T01` y `U00-T02` tocan `contracts/`: van en serie |

Máximo 3 en paralelo, y no más de 5 PR esperando revisión. Si una tarea llega a 4 rondas, se para y se lleva a la persona.

## Lo que falta generar con el loop

`bitacoras/`, `revisiones/U0X-T0N/ronda-N.md`, los PR y `DECISIONES-LOOP.md`.
