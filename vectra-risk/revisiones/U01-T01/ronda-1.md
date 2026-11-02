# Ronda 1 — U01-T01

VEREDICTO: VERDE

Revisé `f5d52c6fe330548c899ccdc70067e886de2a4732` contra la base `737b456`. Corrí todo yo mismo desde `vectra-risk/`. No hay ROJO ni NARANJA; quedan dos AMARILLO que no bloquean y dos tareas candidatas.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | El Deployment renderizado define `GF_PLUGINS_PREINSTALL_DISABLED=true` en el contenedor `grafana` | `uv run pytest platform/tests/test_upstream_charts.py -q -k grafana_does_not_preinstall_plugins` | pasa: `1 passed, 19 deselected in 0.71s` |
| 2 | Nada más cambió en el comportamiento de los charts | `uv run pytest platform/tests/test_upstream_charts.py -q && uv run ruff check platform` | pasa: `20 passed in 109.92s (0:01:49)`, `All checks passed!`, ambos con salida 0 |

## Comprobaciones adversariales

**El tiempo de 0.71 s no es un salto (invariante 7).** El archivo no tiene `skip` ni `xfail`. Con `--durations`, la prueba reporta `1.73s call` y `PASSED`. Las mutaciones de abajo fallan en cerca de 1 s, así que `helm template` sí corre.

**La prueba lee el render, no los values.** Pasa por `render("kube-prometheus-stack")`, que ejecuta `helm template`, y lee `spec.template.spec.containers[name=grafana].env`.

**La prueba falla si se quita el cambio.** Lo demostré en una copia temporal hecha con `git archive`, fuera del worktree, con el `.venv` y los charts del worktree:
```
control (sin mutar)                                 1 passed
M1 se quita la línea del cambio                     assert None == 'true'    1 failed
M2 valor "false"                                    assert 'false' == 'true' 1 failed
M3 clave grafana.envX (el chart la ignora)          assert None == 'true'    1 failed
M4 nombre mal escrito (..._DISABLE)                 assert None == 'true'    1 failed
M5 env en la raíz del values, fuera de grafana      assert None == 'true'    1 failed
```

**El valor llega al contenedor correcto.** Con mi propio `helm template`, chart 92.17.0 y subchart grafana 14.3.0, Deployment `kube-prometheus-stack-grafana`:
- Contenedor `grafana`, imagen `docker.io/grafana/grafana:13.3.0-distroless@sha256:540b8afb…`: tiene `('GF_PLUGINS_PREINSTALL_DISABLED', 'true')`.
- Sidecars `grafana-sc-dashboard` y `grafana-sc-datasources`: no lo tienen.
- No hay `initContainers`, y tampoco `GF_INSTALL_PLUGINS`.

**El alcance «todos los entornos» se cumple, y el diff del render es mínimo.** Los Application de staging y prod usan solo `kube-prometheus-stack.yaml`, sin `valuesObject` que lo pise. Kind añade `kube-prometheus-stack-kind.yaml`, cuya sección `grafana` solo toca `resources`. Comparé el render de base y head en ambas variantes:
```
$ diff base.yaml head.yaml            # staging/prod
1084a1085,1086
>             - name: "GF_PLUGINS_PREINSTALL_DISABLED"
>               value: "true"
$ diff base-kind.yaml head-kind.yaml  # kind
1084a1085,1086
>             - name: "GF_PLUGINS_PREINSTALL_DISABLED"
>               value: "true"
```
El render es determinista: una repetición dio 0 líneas de diferencia. `platform/rendered/*` no contiene este chart (`render.sh` no lo renderiza), así que no había snapshot que actualizar.

**La variable tiene efecto real en Grafana 13.3.0.** Arranqué la imagen local `grafana/grafana:13.3.0` con `docker run --rm --pull never --network none`, sin clúster y sin red, una vez sin la variable y otra con ella. Es una comprobación adicional a lo pedido; los contenedores ya no existen. Las líneas de `plugin.backgroundinstaller` en cada log:
```
sin: 28 líneas; "Installing plugins", "Failed to install plugin ... grafana.com/api/plugins/..."
con: 0 líneas; "Config overridden from Environment variable" var="GF_PLUGINS_PREINSTALL_DISABLED=true"
```
Limitación: la imagen local es la variante no distroless de la misma versión, no el digest desplegado.

**La bitácora es coherente.**
- El hash de la tarea coincide: `git hash-object` da `161b93bb…`.
- Su rojo (`assert None == 'true'`) es idéntico al que reproduje en M1.
- Sus cifras en verde son consistentes con las mías.

**Cerca de alcance.** El diff toca solo tres archivos: la bitácora, los values (+1 línea) y la prueba (+7 líneas). No hay desborde. El literal está en el archivo de values, que es su punto de configuración, así que no aplica la invariante 8.

**Worktree al terminar.** `git status --short` da 0 líneas y HEAD sigue en `f5d52c6`. Solo quedan archivos ignorados: `.venv`, cachés y `platform/.charts`.

**No corrido.** No ejecuté `test_platform.py` ni `test_waves.py`, que mencionan este chart, porque están fuera de CA-2. El diff del render de arriba limita el riesgo, pero no los cubre.

## Hallazgos

### F-01 · AMARILLO · platform/tests/test_upstream_charts.py:75 · La prueba no cubre el overlay de kind
`render()` solo aplica `component["values"]`, no `kind_values`. Hoy el overlay no afecta al valor, como muestra el diff de kind. Pero un `grafana.env` futuro en el overlay de kind se combinaría sin que esta prueba lo vea.

### F-02 · AMARILLO · platform/tests/test_upstream_charts.py:76 · Selección del Deployment por sufijo
`endswith("grafana")` hoy encuentra un único Deployment, pero `next()` tomaría el primero si aparece otro con ese sufijo. Es menor, y la prueba hermana del archivo merece la misma mirada si esto se toca.

## Tareas candidatas (defectos reales fuera de alcance)
- **Grafana sigue saliendo a Internet al arrancar.** Con la variable puesta, el log sin red aún registra dos intentos: `grafana.update.checker` hacia `https://grafana.com/api/grafana/versions/stable` y `plugin.angulardetectorsprovider.dynamic` hacia `https://grafana.com/api/plugins/angular_patterns`. No instalan plugins, así que no incumplen esta tarea. Sí contradicen el motivo que da («dentro del banco nada debe salir a Internet»).
- **Falta una prueba de render con overlay.** Cubriría `kind_values` en los charts que los tienen (ver F-01).

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/u01t01/`:
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/u01t01/grafana-sin.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/u01t01/grafana-con.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/u01t01/head.yaml`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/u01t01/base.yaml`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/u01t01/head-kind.yaml`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/u01t01/base-kind.yaml`

Nota de formato: el contrato pone la línea de veredicto al inicio del bloque final, pero el encargo pide terminar exactamente en ella. Dejé el veredicto como última línea y antes los hallazgos y la ruta del informe. No escribí ese archivo; lo guarda el orquestador.

AMARILLO|platform/tests/test_upstream_charts.py:75|La prueba no cubre el overlay de kind
AMARILLO|platform/tests/test_upstream_charts.py:76|Selección del Deployment por sufijo
INFORME: revisiones/U01-T01/ronda-1.md
VEREDICTO: VERDE
