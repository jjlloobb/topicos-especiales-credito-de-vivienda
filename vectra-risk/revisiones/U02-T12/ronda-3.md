# Ronda 3 — U02-T12

VEREDICTO: VERDE

CI-01 queda cerrado y no veo regresiones. Corrí yo mismo todos los criterios de la ronda y todos pasan. No queda ningún ROJO ni NARANJA. Hay un AMARILLO que no bloquea.

## Criterios de la ronda (los de `ci-ronda-2.md`), verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | `test_edge_selectors.py` pasa en el entorno de CI de `platform`, sin `platform/.tools` y con el helm de `tools.env` en el PATH | Moví `platform/.tools` al scratchpad. El helm del PATH es `/usr/sbin/helm`, que es `v4.3.0+gbec5b06`, igual a `HELM_VERSION=v4.3.0`. Corrí `make -C platform charts render` y luego `HYPOTHESIS_PROFILE=ci uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider --hypothesis-seed=42056600314`, que es lo mismo que hace `tests.yml` | pasa: `745 passed in 114.93s`, sin omitidas |
| 1b | El fallback de verdad llama a helm del PATH, no a otra cosa | Mismo entorno, con un `helm` envoltorio primero en el PATH que anota cada llamada | pasa: `48 passed`, con 6 llamadas `helm template envoy-gateway .../gateway-helm ...` por el PATH. Los 1,3 s se explican: son 6 renders y el resto es en memoria |
| 2 | Las pruebas de `identity-edge` siguen pasando | Con `.tools` restaurado, `make -C identity-edge check` | pasa: exit 0, `2367 passed in 655.32s`, conftest 9/112/3 sin fallas |
| 3 | `platform` local sin regresión | `make -C platform check-local`, en serie después del anterior | pasa: exit 0, `745 passed`, ruff limpio, `2 chart(s) linted, 0 failed`, trazabilidad, runbooks, waves y links en orden |
| 4 | Resultado de CI sobre el commit nuevo | `gh run view 42056600314` y `42056600777` | pasa: los dos tienen `headSha c542776`, `success`, y todos los jobs en success (`tests`, `evidence`, `policies`, `supply-chain`, `forbidden`, `rollback-note`, `checks`). En el log del job `tests`: `Installing v4.3.0` y `745 passed in 158.37s`, con `test_edge_selectors.py` ejecutado |
| 4b | CI sobre el HEAD del PR | `gh run list --branch tarea/U02-T12` | pasa: los runs 42057886312 (contracts) y 42057886666 (platform) sobre `d005363`, que solo cambia la bitácora, terminaron en `success` |
| 5 | El pin de helm no se pierde | Leí `.github/actions/setup-helm/action.yml`, `platform/tests/test_ci.py:1003-1011` y el job `policies` | pasa en CI: `setup-helm` instala la `HELM_VERSION` de `tools.env`, `test_ci.py` exige que use esa versión, y el job `policies` corre `check-tools` con `helm version --short \| grep ^$HELM_VERSION`. En local gana `platform/.tools/bin/helm` si existe |

**Alcance.** El diff de código de c542776 cambia 3 líneas de `identity-edge/tests/unit/test_ratelimit_deployment.py`, que ya estaba en el PR. Es un cambio mínimo y no hay nada fuera de alcance. d005363 solo toca la bitácora.

**Evidencia del codificador.** Su ronda 3 en la bitácora coincide con lo que reproduje: 33 failed antes y 745 passed después, con los mismos run ids y el mismo SHA. Es coherente con el diff actual.

## Hallazgos
### F-01 · AMARILLO · identity-edge/tests/unit/test_ratelimit_deployment.py:34 · El fallback al PATH no comprueba la versión de helm
Cuando no existe `platform/.tools`, `HELM` toma el `helm` del PATH sin mirar su versión. Lo comprobé con un envoltorio que responde `version` con `v3.0.0+fake`: `test_edge_selectors.py` pasó igual (`48 passed`), así que nada en la prueba lo detecta.

No bloquea por tres razones:
- en CI la versión la fijan `setup-helm` y `check-tools`;
- en local gana el binario fijado;
- es el mismo criterio que ya usan las pruebas de U1 (`platform/tests/test_platform.py`, `integration.py`), que llaman a `helm` del PATH.

El hueco que queda es solo el de un desarrollador sin `.tools` y con otro helm instalado. Como mejora opcional, la prueba podría verificar `helm version --short` contra `tools.env` una vez por sesión.

## Barrido de clase
`test_valkey_chart.py` (HELM, CONFTEST) y `test_ratelimit_deployment.py` (CONFTEST, KYVERNO) siguen fijando `platform/.tools/bin`. Ninguno lo necesita la suite de `platform`: sin `.tools` pasa 745/745 en mi ejecución y en CI. Los usa el workflow `contracts` (identity-edge), que está en verde, así que no hay hallazgo.

## Tareas candidatas
- Opcional: un helper común para resolver herramientas fijadas que verifique la versión contra `tools.env`, en lugar de repetir `ROOT/"platform"/".tools"/"bin"/X` en cada módulo de prueba.

## Estado del worktree
`platform/.tools` está restaurado (8 binarios). `git status --short` sale vacío: el worktree está limpio y no toqué fuentes.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/`:
- `ci-sim.log`: la suite de `platform` en el entorno simulado de CI.
- `charts.log`: el `charts render` de ese mismo entorno.
- `ie-check.log`: `make -C identity-edge check`.
- `pl-check.log`: `make -C platform check-local`.
- `helm-calls.log`: las llamadas a helm por el PATH.

Nota: mis herramientas son de solo lectura, así que no escribí `revisiones/U02-T12/ronda-3.md`. Lo tiene que guardar el orquestador con este contenido.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tests/unit/test_ratelimit_deployment.py:34|El fallback al PATH no comprueba la versión de helm (en CI la fijan setup-helm y check-tools)
INFORME: revisiones/U02-T12/ronda-3.md
```
