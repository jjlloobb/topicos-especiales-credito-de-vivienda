# Ronda 5 — U02-T07

VEREDICTO: VERDE

F-09 quedó cerrado: mis once sondas de la ronda 4 fallan todas contra este código, incluidas las seis anotaciones de hook. El diff de esta ronda solo toca F-09, los seis criterios pasan con mi propia ejecución y el worktree queda limpio. No queda ningún ROJO ni NARANJA. La fusión es de la persona.

Revisé `f2071fa` sobre `c173afa`. El hash de la tarea coincide (`4826b291…`). El worktree estaba limpio antes y sigue limpio. Corrí todo sobre una copia de `git archive HEAD`, en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r5/wt`, con su propio venv; esa copia también quedó limpia tras el render.

La herramienta pasó a segundo plano mi ejecución de los criterios, que superó los 180 s, y también la espera que lancé después. No las relancé: las dos terminaron con rc=0 antes de esta entrega y no queda ningún proceso abierto. Como en rondas anteriores, `make -C platform check-tools` escribe en `platform/.tools/integration/` del repositorio principal a través del enlace; es un directorio ignorado.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Políticas propias | `make -C identity-edge render-keycloak policy-keycloak` | pasa: 2418/2418 por archivo y 9/9 en cada entorno. El render reproduce lo versionado. |
| 2 | Cada regla falla sobre un render alterado | `uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q -rs` | pasa: 274, 0 omitidas |
| 3 | Los valores salen del diseño | `... -k design -rs` | pasa: 49, 0 omitidas |
| 4 | Políticas de U1 | `make -C identity-edge policy-keycloak-u1` | pasa: kyverno `pass: 13, fail: 0` en los tres entornos, rc=0 |
| 5 | Todo sigue cumpliendo | `uv sync --frozen && make -C identity-edge check && make -C platform check-tools` | pasa, rc=0: 1145 en `identity-edge`, kyverno de U1 67 + 38 + 239 |
| 6 | Enmiendas con lectura de vuelta | `uv run pytest ...test_keycloak_deploy.py ...test_keycloak_image.py -q -rs` | pasa: 358, 0 omitidas |

## Cierre de F-09
La regla nueva `metadata-annotations` está en `set.rego:131-138`. Rechaza cualquier documento con `metadata.annotations`, igual que el render versionado, que no tiene ninguna. El pod template conserva su regla de las dos claves de checksum.

Volví a correr la sonda de la ronda 4 (`/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r4/probe/mut4.py`). Ahora fallan sus once casos, incluidos estos:
- `argocd.argoproj.io/hook: Skip` en el `StatefulSet`, el PDB, `keycloak-tls` e `identity-ca`;
- `PostSync` con `HookSucceeded` en el `BackendTLSPolicy`;
- `helm.sh/hook: test` en el HPA;
- una anotación de Linkerd en un Service.

Las demás sondas de esa ronda siguen fallando.

## Hallazgos
Ninguno.

Una nota: un `annotations: {}` vacío también se rechaza. Es rechazar de más, y eso no es un defecto.

## Alcance
El diff de `c173afa..f2071fa` solo toca `set.rego` (9 líneas), `test_keycloak_deploy.py` (22 líneas, casos de `metadata-annotations`), la bitácora y la respuesta. Todo es F-09. No toca values, render, Dockerfile, realms, tema, `platform/`, `contracts/` ni workflows.

## Tareas candidatas
- Siguen en pie las de rondas anteriores: U1 no cubre los StatefulSet, y las métricas de F60 deben leerse por HTTPS. No abrí clases nuevas.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/tasks/bg0uelj1u.output`

INFORME: revisiones/U02-T07/ronda-5.md
VEREDICTO: VERDE
