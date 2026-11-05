# Ronda 2 — U02-T12

VEREDICTO: VERDE

F-01 y F-02 están corregidos en el código, y lo comprobé con mis propias mutaciones. Los cinco criterios pasan con mi propia ejecución, CA-4 y CA-5 en serie, sin pruebas omitidas. Lo generado cambia solo en los selectores de `envoy-gateway`. Queda un AMARILLO que no bloquea.

Datos de partida:
- sha revisado: 9f946e0 (código en 3483401);
- hash de la tarea: `405276e2…`, coincide;
- `git status --short` al terminar: vacío.

## Criterios de aceptación, verificados por mí (desde `vectra-risk/`)
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `generate.py --check && pytest platform/network/tests -q` | pasa: 211 passed en 11,8 s, exit 0 |
| 2 | `pytest platform/network/tests/test_edge_selectors.py -q` | pasa: 48 passed en 1,8 s, exit 0. El tiempo cuadra: no depende de estado externo, solo de `helm template` local. Ver las mutaciones más abajo |
| 3 | `make -C identity-edge check-valkey-rendered policy-valkey policy-valkey-u1 && pytest …/test_valkey_chart.py -q` | pasa: conftest con 3072, 3×(9, 112 y 3) y 3×40 sin fallos; 174 passed en 23,9 s, exit 0 |
| 4 | `pytest platform/tests/test_integration.py -q && make -C platform check-local` | pasa: 56 passed; ruff «All checks passed»; 745 passed; helm lint de 2 charts; 227 archivos Markdown sin enlaces rotos. exit 0 |
| 5 | `uv sync --frozen && make -C identity-edge check`, en serie después de CA-4 | pasa: 2367 passed en 697 s, exit 0. Cero omitidas (las únicas líneas «Skipped» son `Skipped: 0` de kubeconform) |

## Verificación de F-01 contra el código, con mis propias mutaciones
Usé un script fuera del worktree que importa `test_edge_selectors.problems()` y altera solo copias en memoria. Así se comporta, en los tres entornos:
- **Línea base:** 0 problemas para `envoy-gateway`.
- **Volver al selector de la ronda 1 (`name: envoy-gateway`):** 3 problemas por entorno («no selecciona un pod que lleva {control-plane…, app.kubernetes.io/name: gateway-helm…}»).
- **`control-plane: otro`:** 3 problemas. **SA `otra`:** 1. **ns `vectra-edge`:** 4.
- **El pod cambia en el render y `flows.yaml` queda intacto.** Envolví `ratelimit.render` con `--set nameOverride=otro-chart` y salen 3 problemas por entorno. Esto demuestra que el pod real sale del render de `gateway-helm` v1.9.3 (`platform/.charts/envoy-gateway/gateway-helm`, `version: v1.9.3`, con `platform/operators/envoy-gateway.yaml`) y no de un literal.
- **Literales en la prueba:** en `platform/network/tests/*.py`, `gateway-helm` y `control-plane` solo aparecen en docstrings.
- **Quitar una de las tres etiquetas:** sigue seleccionando. Es correcto, porque un subconjunto de `matchLabels` selecciona el pod.
- **`controller_deployment()`:** comprueba que `matchLabels` está contenido en las etiquetas de la plantilla, y usa `matchLabels` como etiquetas del pod, como pide el arbitraje.
- **Cobertura:** `envoy-gateway` está en `EDGE_WORKLOADS`, con su caso contrario en `MUTATIONS`. La candidata del selector salió de `CANDIDATAS.md`.

## Verificación de F-02
Con `F61.unmeshed_source` modificado en copias, en los tres entornos:
- `['otel-collector']` (el destino), `['rate-limit','rate-limt']` y `['ns:vectra-app']`: `SystemExit` con el id, los nombres sobrantes y los orígenes válidos;
- `[]` y `['rate-limit']`: construye.

Con `check_unmeshed_sources` anulada, la errata pasa en silencio: no se genera ninguna `NetworkAuthentication` de F61 en `vectra-observability`. La defensa es la función nueva. `f61_without_limiter` deja ahora la lista vacía, y con eso la mutación sigue teniendo efecto.

## Lo generado solo cambia donde debe
`git diff -U0 8cfb7ef..3483401 -- platform/network/generated` toca exactamente 6 archivos: `envoy-gateway-system.yaml` y `vectra-edge.yaml` de cada entorno. Todas las líneas son el cambio del selector `app.kubernetes.io/name: envoy-gateway` por las tres etiquetas del chart, en tres sitios por entorno:
- el `podSelector` de `allow-f95-to-envoy-gateway-ingress`;
- el de `allow-k8s-api-k14`;
- el destino del egress de F95 desde `api-gateway`.

`connectivity-suite.yaml` no cambia, y en `generated/` no queda ninguna aparición del selector viejo.

Comparé los AST de 8cfb7ef y 3483401. Solo cambian en su semántica:
- `build`, por la llamada a `check_unmeshed_sources`;
- `check_unmeshed_sources`, que es nueva;
- `f61_without_limiter` y las dos pruebas de F-02;
- `EDGE_WORKLOADS`, `controller_deployment` y `real_pods`, además del docstring.

En el conjunto `4e1c702..9f946e0` no hay nada roto: CA-1 a CA-5 pasan sobre él.

## Hallazgos

### F-01 · AMARILLO · `platform/network/generate.py`, `tests/test_flows.py`, `tests/test_edge_flows.py`, `tests/test_edge_selectors.py` · reformateo masivo sin cambio de comportamiento
El commit 3483401 vuelve a formatear con ruff los cuatro archivos:
- `test_flows.py`: unas 273 líneas cambiadas, con cero cambios de AST;
- `generate.py`: unas 200 líneas, cuando el cambio real son unas 15.

Ni `platform/Makefile` ni `identity-edge/Makefile` exigen `ruff format`. No es un desborde, porque los archivos están dentro del alcance, y no cambia la salida (`--check` pasa). Pero mete ruido en el diff de U1 y complica revisar y hacer `blame`. No bloquea.

## Juicio sobre el arbitraje
- F-03, F-04, F-05 y mi candidata de `-LOADING` están en `CANDIDATAS.md` con su origen, sin cambios de código.
- Lo ratificado (`unmeshed_ports: [5432]`, la lista en F61, `opaque` en el 6379 y Z1) no se tocó esta ronda.

## Evidencia del codificador
Las cifras de la bitácora (211, 48, 174 y 2367 passed) coinciden con las mías, y sus transcripciones son posteriores a 3483401. No hay evidencia antigua.

## Tareas candidatas
- Ninguna nueva.

## Transcripciones (scratchpad propio)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/rev-r2/rev-ca1.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/rev-r2/rev-ca2.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/rev-r2/rev-ca3.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/rev-r2/rev-ca4.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/rev-r2/rev-ca5.txt
- Scripts de mutación: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/rev-r2/scripts/mut_f01.py, /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/rev-r2/scripts/mut_f02.py, /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/rev-r2/scripts/astdiff.py

No tengo herramienta de escritura, así que no escribí `revisiones/U02-T12/ronda-2.md`. Este mensaje es el informe y le toca al orquestador versionarlo.

```
VEREDICTO: VERDE
AMARILLO|platform/network/generate.py, tests/test_flows.py|reformateo ruff masivo sin cambio de AST ni de salida
INFORME: revisiones/U02-T12/ronda-2.md
```
