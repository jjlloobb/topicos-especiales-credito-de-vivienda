# Ronda 3 — U01-T03

VEREDICTO: VERDE

Worktree `wt-U01-T03`, rama `tarea/U01-T03`, sha `93bcca9`, base `f44ba83`. Nada se ejecutó contra un clúster. El efecto real (que los targets dejen de dar 504) sigue sin comprobar.

Los dos criterios pasan, `pytest platform` con charts pasa entero y F-03 queda cerrado. Quedan dos AMARILLO nuevos y un residuo de F-05 que no bloquean. La decisión de fusionar es del humano.

## Criterios de aceptación, verificados por mí
Desde `vectra-risk/`, con `UV_FROZEN=1 UV_OFFLINE=1`. A pytest le añadí `-p no:cacheprovider`, y `-rs` en las corridas de esta tabla.

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | NetworkPolicy de ingress y egress de F130 en los 3 entornos, con esos puertos y sin 4143 | `uv run pytest platform/network/tests -q -k f130` | pasa: `3 passed, 85 deselected in 0.14s`; `--collect-only` da una prueba por entorno (kind, staging, prod) |
| 2 | Lo generado coincide y el inventario está al día | `uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -q` | pasa: gen rc=0, `88 passed in 2.79s`, rc=0 |
| extra | Pedido por el orquestador | `uv run pytest platform -q`, con `platform/.charts` del worktree | pasa: `597 passed in 107.08s`, rc=0, sin omisiones |

**Tiempos:** 0.14 s y 2.79 s no indican pruebas saltadas. La suite de red es pura, y las mutaciones de abajo demuestran que falla cuando debe.

**Comparación con la base:** `pytest platform` en un clon de `f44ba83` con los mismos charts da `593 passed`. HEAD suma 4 pruebas y no pierde ninguna. Tres son las de F130. La cuarta sería el parámetro nuevo de `test_flow_ports_are_really_open` para el operator, una inferencia que no aislé.

**Charts:** `diff -rq` del `platform/.charts` del worktree contra el del repositorio principal no da diferencias.

## Hallazgos de la ronda 2, comprobados
Mutaciones en un clon privado, con venv propio, regenerando `generated/` cuando la mutación toca `flows.yaml` o `generate.py`. Tabla completa en la transcripción.

| Mutación | `--check` | `-k f130` | `network/tests` | `test_integration` |
|---|---|---|---|---|
| B0, sin mutar | 0 | 3 passed | 88 passed | 56 passed |
| F3a, `OPERATOR_PORTS` como en la base | 0 | 3 passed | 88 passed | **1 failed** |
| F3b, F130 a alertmanager en 8081 | 0 | 3 failed | 3 failed | **1 failed** |
| F3c, `OPERATOR_PORTS` sin 9093 | 0 | 3 passed | 88 passed | **1 failed** (F64) |
| F5a, ref `ghost` al final | 0 | 3 failed | 3 failed | 56 passed |
| F5b, ref `ghost` al inicio | 0 | 3 failed | 3 failed | 56 passed |
| F5c, `ghost` solo en grafana | 0 | 3 failed | 3 failed | 56 passed |
| F5d, refs vacías | 0 | 3 failed | 3 failed | 56 passed |
| **F5e, `kind` de la ref errado** | 0 | **3 passed** | **88 passed** | 56 passed |
| F6a, `F130_TARGETS` con grafana en 3100 | 0 | 3 failed | 3 failed | 56 passed |
| F6b, `F130_TARGETS` sin operator | 0 | 3 failed | 3 failed | 56 passed |
| M1, puertos cruzados | 0 | 3 failed | 3 failed | 2 failed |
| M2, origen `loki` | 0 | 3 failed | 3 failed | 56 passed |
| M3, destinos `loki, tempo` | 0 | 3 failed | 3 failed | 2 failed |
| M4, grafana en 3100 | 0 | 3 failed | 3 failed | 1 failed |
| M5, 4143 añadido | 0 | 3 failed | 3 failed | 1 failed |
| M6, sin F130 | 0 | 3 failed | 4 failed | 55 passed |
| M7, puerto extra 9090 en grafana | 0 | 3 failed | 3 failed | 1 failed |
| T1, `generated/kind` editado a mano | **1** | 3 passed | 1 failed (`test_generated_check_matches`) | 56 passed |

**F-03: cerrado.**
- F3a reproduce el fallo original: `AssertionError: ('alertmanager', 'F130', (8080,), {9093, 9094})`.
- F3b y F3c muestran que la prueba sigue atando puertos: ampliar el conjunto no la dejó sin efecto.
- `make check-local` y `evidence.yml:46` corren `pytest platform` con `--rootdir=platform --import-mode=importlib`. Con esos argumentos también dio `597 passed` en un clon completo.

**El 8080 de Alertmanager es real, con un límite.** Corrí `helm template` de kube-prometheus-stack 92.17.0 con `platform/observability/values/kube-prometheus-stack.yaml`, y también con el overlay de kind. Salida en ambos:
- `Service kube-prometheus-stack-alertmanager`: `('http-web', 9093, 9093)` y `('reloader-web', 8080, 'reloader-web')`, con selector `app.kubernetes.io/name: alertmanager`.
- `ServiceMonitor kube-prometheus-stack-alertmanager`: endpoints `http-web` y `reloader-web`, ambos en `/metrics`. Prometheus sí raspa ese puerto.

También corrí el comando de la bitácora y da lo mismo: `port: 8080`, `targetPort: reloader-web`.

**Límite:** el `targetPort` es un nombre, y el contenedor lo crea el operador, fuera del render. Así que `helm template` demuestra el 8080 del `Service`, no el número del contenedor, que es el que aplica la NetworkPolicy. Lo respalda `templates/alertmanager/networkpolicy.yaml:64` del propio chart, que abre 8080 para las métricas del config-reloader. No lo comprobé con un pod real.

**F-04:** aceptado fuera de alcance por el arbitraje. No lo exijo.

**F-05: cerrado en lo pedido, con residuo (ver F-07).** La prueba compara la lista completa, y F5a a F5d fallan. Se reproduce el `3 failed` de la respuesta del codificador.

**F-06: cerrado, con un resto cosmético (ver F-08).** `F130_TARGETS` es `{target: puerto}`. F6a y F6b muestran que la tabla sigue mandando.

## Hallazgos
No hay ROJO ni NARANJA en pie.

### F-07 · AMARILLO · `platform/network/tests/test_flows.py:458` · La prueba compara solo el nombre de la referencia, no su `kind`
En F5e, `generate.py:289` emite `kind: NetworkAuthentication` para las autorizaciones de F130, conservando el nombre de `MeshTLSAuthentication`. Confirmé el cambio en `generated/`: 3 líneas por archivo de `vectra-observability`. Toda la suite de red pasa (`88 passed`) y `--check` da rc=0.

Es AMARILLO por la misma razón que F-05 en la ronda 2: solo se alcanza cambiando `generate.py`, que este diff no toca. Se arregla comparando la lista completa de referencias, no solo `name`.

### F-08 · AMARILLO · `platform/network/tests/test_flows.py:444` · Queda `label = target`, un alias sin función
Es el resto de F-06: la duplicación pasó de la tupla a una variable. Basta usar `target`.

### F-09 · AMARILLO · `bitacoras/U01-T03.md:74` · La cita de `reloaderWebPort` no es de Alertmanager
En el chart, `reloaderWebPort: 8080` (`values.yaml:4062`) solo lo usa `templates/prometheus/service.yaml`. El 8080 de Alertmanager es un literal en `templates/alertmanager/service.yaml:51`. La conclusión de la bitácora es correcta, pero esa línea no la sustenta. La otra evidencia que cita sí se reproduce.

## Comprobado sin hallazgo
- **Alcance del retrabajo:** `8012ef5..3e810b1` toca solo `test_flows.py`, `test_integration.py` y `ronda-2.md`. `3e810b1..93bcca9` toca solo la bitácora y la respuesta. El diff total no toca `generate.py` ni `tareas/`. `test_integration.py` entra por el arbitraje de F-03.
- **Evidencia de la bitácora y la respuesta:** el `597 passed` y el `3 failed` de F-05 se reproducen. El `1 failed, 596 passed` lo reproduje solo en `test_integration` (F3a), no en la corrida completa. La cronología del rojo no se puede demostrar, pero el fallo sí se reproduce. No afirma nada sobre el clúster.
- **Hash de la tarea:** `ca0a613…` coincide con `git hash-object`.
- **`make -C platform generate` en el clon:** rc=0 y `git status` con 0 líneas.
- **Resto de `check-local`, paso a paso en el clon:** `render`, `ruff check platform vectra-risk-gitops`, los tres `--check` (red, gitops, quotas), `helm lint`, `test_traceability`, `test_runbooks` y `--operational`, `test_waves` y `test_links`. Todos rc=0, y tras el `render` `git status` siguió vacío.

## Corrección a mis informes anteriores
La candidata «`test_traceability` falla en la base (NFR-U1-40)» de las rondas 1 y 2 **no se sostiene y debe retirarse**. Da rc=0 en el worktree, en un clon de HEAD y en un clon de la base. Si quito `.github` del clon, aparece exactamente el mensaje `NFR-U1-40: solo en code/README.md…` con rc=1. Eso apunta a un artefacto de mis copias anteriores, que no incluían `.github`. La afirmación de la bitácora de que pasó es correcta.

## Sin ejecutar
- `make check-tools` y `check-integration` (kyverno, conftest, promtool, actionlint).
- El objetivo `make check-local` como tal, ni su paso `charts`: corrí sus demás pasos por separado, con charts copiados.
- Los workflows de CI, incluido `evidence.yml`.
- Nada contra un clúster.

## Tareas candidatas (defectos reales fuera de alcance)
- F-04, por el arbitraje: una prueba genérica que ate cada flujo a sus destinos declarados. Sigue en pie la señal de la mutación N17 de la ronda 2.
- F-07 como clase, si se prefiere no tocarlo aquí: ninguna prueba de red detectó el `kind` errado de `requiredAuthenticationRefs` en F5e. No probé esa mutación en otros flujos.
- **Señal sobre la especificación:** CA-2 solo cubre `platform/network/tests`, así que F3a cumple ambos criterios y rompe `test_integration`. Las tareas de flujos deberían incluir esa prueba con charts. Viene de la ronda 2.
- prometheus→prometheus en 8080 y 9090 sin declarar. Viene de la ronda 1, sin comprobar.

## Notas sobre mi ejecución
- **Worktree:** `git status --short` da 0 líneas y HEAD sigue en `93bcca9`. Allí solo corrí criterios, `pytest`, `ruff`, `test_traceability`, `helm template` y lecturas. El render se escribió fuera, en el directorio temporal.
- **Clones:** las mutaciones van en `mono/` y la comparación con la base en `base/`, ambos clones con venv propio. Al terminar, `mono/` quedó con 0 líneas en `git status`.
- **Repositorio principal:** solo lo leí con `diff -rq`. No lo modifiqué.
- **No guardé el informe:** este revisor no escribe. El orquestador lo guarda en la ruta indicada abajo.
- **Orden del bloque final:** el contrato pone el veredicto al inicio del bloque y tú pediste terminar en él, así que dejo esa línea al final.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t03-r3-OsPATL/matrix.out` (matriz de mutaciones)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t03-r3-OsPATL/matrix.py` (script de la matriz)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t03-r3-OsPATL/kps-prod.yaml` (render con valores de producción)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t03-r3-OsPATL/kps-kind.yaml` (render con el overlay de kind)

AMARILLO|platform/network/tests/test_flows.py:458|La prueba compara solo el nombre de la referencia, no su kind
AMARILLO|platform/network/tests/test_flows.py:444|Queda label = target, un alias sin función
AMARILLO|bitacoras/U01-T03.md:74|La cita de reloaderWebPort no es de Alertmanager
INFORME: revisiones/U01-T03/ronda-3.md
VEREDICTO: VERDE
