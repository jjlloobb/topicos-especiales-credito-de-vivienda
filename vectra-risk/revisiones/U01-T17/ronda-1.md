# Ronda 1 — U01-T17

VEREDICTO: NO-VERDE

Hay un solo ROJO y no viene del código: la verificación final de la bitácora cita para CA-1 un resultado que el diff actual no puede producir. El RBAC no deja ningún camino para leer un `Secret` ni para escribir. Corrí yo los seis criterios y pasan los seis.

Revisé la rama `tarea/U01-T17` en `06f9a02`, contra la base `2445c37`. Todo corrió con `KUBECONFIG=/nonexistent` y con un `PATH` sin `/snap/bin` (`which kubectl` sale vacío). No hubo ninguna orden contra el clúster.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `pytest platform -k readonly` (con `--collect-only` y sin él) y `make -C platform check-tools` | pasa: 36 pasan. El filtro selecciona 15 de `test_readonly_agent.py`, 19 de `test_readonly_kubeconfig.py` y 2 de minio. En `check-tools` sale 0, con la fila `disallow-rbac-wildcards / ClusterRole vectra-readonly-agent  Pass` y `89 tests passed and 0 tests failed` |
| 2 | `generate.py --check && ls apps/kind \| grep -c readonly && ! ls apps/staging apps/prod \| grep readonly && test_waves.py` | pasa: sale `1`; kind 56, prod 54 y staging 56 Applications en orden. `grep -rn readonly apps/staging apps/prod` no encuentra nada |
| 3 | `pytest platform/kind/tests -k readonly_kubeconfig` y `shellcheck` | pasa: 19 pasan; `shellcheck` sale 0 |
| 4 | `! grep -n -E 'kubectl[^\|#]*\b(apply\|delete\|…\|exec)\b' readonly-kubeconfig.sh` | pasa: sale 0 |
| 5 | `grep -c`, `test_links.py` y `test_runbooks.py` | pasa: 1 aparición en `registry.md` y 1 en `loop/README.md`; 658 Markdown sin enlaces rotos; 56 alertas con su runbook |
| 6 | pytest completo de `platform` (con `.tools` fuera del árbol y `.charts` dentro) y `make -C platform check` una sola vez | pasa: `1055 passed in 390.39s`, sin ninguna prueba omitida. `make check` sale 0 (`pass: 450, fail: 0`). `.tools` quedó devuelto, el mismo enlace |
| — | `test_traceability.py --all` en la rama | sale 0: no hay fallos, así que no hace falta comparar con la base |

## Hallazgos

### F-01 · ROJO · `bitacoras/U01-T17.md`, «Verificación final», CA-1 · La evidencia de CA-1 no pudo salir del diff final
La bitácora dice `-k readonly → 17 passed (collect-only: 14 + 3)`. Con el diff final, ese mismo filtro selecciona y pasa **36**, porque `readonly` también casa con los 19 casos de `test_readonly_kubeconfig.py`. Lo comprobé con mi propia corrida: `36/1055 tests collected` y `36 passed`. El 17 es la cifra del Bloque 1, de antes de que existiera el guion, copiada como verificación final. El código pasa CA-1 por mérito propio; lo que está mal es la evidencia. Arreglo: volver a correr CA-1 sobre `06f9a02` y pegar la salida real.

### F-02 · NARANJA · `platform/tests/test_readonly_agent.py:14,28-43,69-72` y `readonly-kubeconfig.sh:77-98` · El validador es una lista de prohibidos y deja pasar `nodes/proxy`
Hice mis propias mutaciones con el validador del codificador (`problems_in` y `test_readonly_agent_never_mentions_secrets_or_the_pod_doors`), añadiendo una regla `get, list, watch` cada vez:
- **Las detecta:** `serviceaccounts/token` (las dos pruebas) y `pods/proxy` (solo la segunda).
- **No las detecta:** `nodes/proxy`, `services/proxy` y `nodes/log`. Tampoco detecta un nombre mal escrito (`podz`).

`get` sobre `nodes/proxy` abre la API del kubelet, y con ella las variables y los logs de cualquier pod. Hay además un camino conocido de ejecución por WebSocket con `GET`. Una mutación así pasaría todas las pruebas.

La tabla de `check` tiene el mismo hueco: no pregunta por `get nodes/proxy`, `get pods/proxy`, `get services/proxy`, `create serviceaccounts/token`, `escalate`/`bind` ni `get nodes/log`.

El manifiesto **actual no concede ninguno de esos recursos**, así que no es un camino real hoy; es cobertura ausente. Propongo dos cosas:
1. Que la prueba prohíba cualquier subrecurso salvo `pods/log` (`"/" in r and r != "pods/log"`).
2. Que fije cada par `(apiGroup, resource)` contra los CRD de `.charts` y el núcleo.

Comprobé a mano que hoy todos los pares existen. Por ejemplo `wgpolicyk8s.io/policyreports`, `kyverno.io/policyexceptions`, `policy.linkerd.io/httproutes` y `serverauthorizations`, `serving.kserve.io/inferencegraphs`, `postgresql.cnpg.io/poolers` y `gateway.networking.k8s.io/grpcroutes` están en los charts.

### F-03 · AMARILLO · `components.yaml:42`, `readonly-kubeconfig.md` y la bitácora · «Wave 1: Kyverno y sus políticas ya están activas» es falso
`kyverno-policies` está en la misma wave 1 (`EXPECTED_WAVES`). La Application puede sincronizar antes que las políticas. No hace daño, porque esas políticas la admiten igual, pero la frase debe decir «misma wave».

### F-04 · AMARILLO · `readonly-kubeconfig.sh:120` · `check` toma un «no» con motivo como «sin respuesta»
`kubectl auth can-i` imprime `no - <motivo>` cuando el SAR trae `reason`. Con un falso que contesta `no - RBAC: denied`, `check` sale **3**, no 0. El fallo es en el lado seguro (nunca da un falso «todo bien»), pero en el clúster real podría dar un 3 inútil. No está medido; conviene comparar solo la primera palabra.

Además probé `check` con un falso que contesta `yes` a todo, que es el caso del kubeconfig de administrador: sale **1** y dice «NO es de solo lectura». Correcto.

### F-05 · AMARILLO · `readonly-kubeconfig.sh:60-71` · `write` tiene dos bordes sin cubrir
- No hay `trap`: si el proceso se corta entre `mktemp` y `mv`, queda `ruta.XXXXXX` (0600) con el token dentro.
- `write ~/.kube/config` sobrescribe el kubeconfig de administrador sin negarse.

Del resto de `write` comprobé: el token no aparece en argv ni en el entorno de ningún hijo (pasa por `printf` integrado y por la entrada de `base64`), el temporal se crea 0600 y la escritura es atómica. Con mi falso, el token no salió en stdout ni en stderr.

### F-06 · AMARILLO · `readonly-kubeconfig.md` · La documentación se queda corta en tres puntos
- **Revocar.** Dice que «la Application lo vuelve a crear», pero no hay sincronización automática (`disallow-argocd-auto-sync`); solo pasa tras una sincronización manual.
- **Lo que la identidad sí lee.** Lee la spec de los pods y `pods/log`, no solo `configmaps`. Por ejemplo, el pod de Vault lleva el token raíz de desarrollo `root` (ya está en Git, `vault-kind.yaml:8`, y Vault no está expuesto al host: sin `portforward` ni `proxy` no se llega). Un log que imprima un valor queda legible. Debe ir en «Qué NO resuelve».
- **Lo de `argocd`.** Lo afirmado está marcado como no medido, y bien. Lo de `docker` va bajo «Investigado sin ejecutar»: aceptable.

## Respuestas puntuales
- **ClusterRole, regla por regla:** sin comodines, solo `get/list/watch`. No hay `secrets`, ni subrecursos salvo `pods/log`, ni `proxy`, ni `serviceaccounts/token`, ni `certificatesigningrequests`, ni `tokenreviews` o `subjectaccessreviews`, ni `impersonate`, ni `escalate`/`bind`. Ningún ConfigMap del repositorio lleva valores secretos: valkey y la consola los documentan sin secretos, y el realm usa `$(env:…)`. Las plantillas de `ExternalSecret`, los `Cluster` de CNPG y las Applications llevan referencias, no valores en claro.
- **Secret del token en `argocd`:**
  - Ninguna política lo rechaza: `disallow-plain-secrets` solo mira `vectra-*`, y las reglas rego de `platform.rego` no tocan los `Secret`.
  - Pueden leerlo el administrador y los componentes de Argo CD; la UI de Argo CD enmascara `data`.
  - Lo que espero es **Synced**. Con `ServerSideApply=true`, la comparación no cuenta como deriva los campos que el controlador de tokens añade (`data`) y que no están en Git. Sin el `last-applied`, el diff de dos vías tampoco ve los campos de más. El repositorio no tiene `ignoreDifferences` ni personalizaciones (`argo-cd*.yaml`). Queda «no medido».
- **Commit `wip` (`ee78a05`):** **no** queda cubierto por los siguientes. Trae el guion y sus pruebas completos, y `a3596a1` solo cambia una línea de las pruebas. El guion entra a `main` con un mensaje `wip`: conviene fusionar con squash.
- **Pruebas:** usan un `PATH` con un solo directorio (el `kubectl` falso más enlaces a binarios inofensivos) y `env` desde cero. `shutil.which` solo sirve para enlazar esos binarios. El falso deja constancia de cualquier verbo inesperado y `run()` lo comprueba. La salvaguarda `autouse` sigue en pie.
- **Worktree:** `git status --short` sale vacío al terminar. Las copias de mis mutaciones (`rev-u01t17-*`) ya están borradas.

## Tareas candidatas (defectos reales fuera de alcance)
- Una regla de permisos que rechace `KUBECONFIG=~/.kube/config` y `--kubeconfig` en las órdenes de los agentes (decisión del usuario; ya está en CANDIDATAS (c)).
- Revisar si algún pod o Job imprime valores sensibles en sus logs, ahora que `pods/log` es legible para los agentes.

```
VEREDICTO: NO-VERDE
ROJO|bitacoras/U01-T17.md «Verificación final» CA-1|evidencia de CA-1 (17 passed) imposible con el diff final (36)
NARANJA|platform/tests/test_readonly_agent.py:14,28-43|validador por lista de prohibidos: no detecta nodes/proxy, services/proxy, nodes/log ni nombres mal escritos; check no los pregunta
AMARILLO|vectra-risk-gitops/components.yaml:42|«Kyverno y sus políticas ya activas» en wave 1: kyverno-policies es la misma wave
AMARILLO|platform/kind/readonly-kubeconfig.sh:120|un «no - motivo» cuenta como sin respuesta (sale 3, en el lado seguro)
AMARILLO|platform/kind/readonly-kubeconfig.sh:60-71|sin trap el temporal con token puede quedar; write no se niega a sobrescribir ~/.kube/config
AMARILLO|platform/kind/readonly-kubeconfig.md|revocar exige sincronización manual; falta decir que la spec y los logs de los pods son legibles
INFORME: revisiones/U01-T17/ronda-1.md
```
