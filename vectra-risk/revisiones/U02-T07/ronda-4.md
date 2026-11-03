# Ronda 4 — U02-T07

VEREDICTO: NO-VERDE

F-07 y F-08 quedaron cerrados, y los seis criterios pasan con mi propia ejecución. La clase del render entero no está cerrada del todo: queda un NARANJA en `metadata`. Las anotaciones de Argo CD no se comparan en ningún documento, y una de ellas hace que Argo CD no aplique o borre un recurso del diseño (F-09).

Revisé `a302ab2` sobre `4a9bf49`. El hash de la tarea coincide (`4826b291…`). El worktree estaba limpio antes y sigue limpio. Corrí todo sobre una copia de `git archive HEAD`, en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r4/wt`, con su propio venv. No dejé procesos abiertos. Como en rondas anteriores, `make -C platform check-tools` escribe en `platform/.tools/integration/` del repositorio principal a través del enlace; es un directorio ignorado.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Políticas propias | `make -C identity-edge render-keycloak policy-keycloak` | pasa: 2418/2418 por archivo y 8/8 en cada entorno. El render reproduce lo versionado. |
| 2 | Cada regla falla sobre un render alterado | `uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q -rs` | pasa: 265 en 27 s, 0 omitidas |
| 3 | Los valores salen del diseño | `... -k design -rs` | pasa: 49 en 1,8 s, 0 omitidas, con helm de verdad |
| 4 | Políticas de U1 | `make -C identity-edge policy-keycloak-u1` | pasa: kyverno `pass: 13, fail: 0` en los tres entornos; Rego y `hpa` también pasan |
| 5 | Todo sigue cumpliendo | `uv sync --frozen && make -C identity-edge check && make -C platform check-tools` | pasa, rc=0: 1136 en `identity-edge`, kyverno de U1 67 + 38 + 239 |
| 6 | Enmiendas con lectura de vuelta | `uv run pytest ...test_keycloak_deploy.py ...test_keycloak_image.py -q -rs` | pasa: 349, 0 omitidas |

## Cierre de F-07 y F-08
Volví a correr la sonda de la ronda 3 (`/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r3/probe/mut3.py`) contra este código. Ahora fallan todos los casos con efecto:
- **F-07:** el `Deployment` y el `StatefulSet` extra, la `NetworkPolicy` que lo permitía todo, el `RoleBinding` y un `ConfigMap` suelto. `documents-exact` fija los 13 documentos por tipo, nombre y namespace, sin sobrantes, faltantes ni repetidos.
- **F-08:** el reparto vaciado, el HPA con `scaleUp` desactivado y con `averageValue` extra, el PDB que no casa, el `Certificate` con `isCA`, `ipAddresses`, `uris`, `commonName`, `usages` o `issuerRef.group`, y el `BackendTLSPolicy` con `subjectAltNames`.

El HPA, el PDB y el reparto se comparan ya enteros. El `Certificate` y el `BackendTLSPolicy` tienen claves exactas y valores exactos o leídos del diseño. También fallan ahora una `TCPRoute`, una `UDPRoute` y un Service en otro namespace.

## `metadata`: los casos con efecto real
Mi sonda está en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r4/probe/mut4.py`.
- **Etiquetas del pod: cerrado.** Las etiquetas del pod template son exactamente las del selector; una etiqueta extra falla.
- **Anotaciones del pod: cerrado.** Solo admite las dos claves de checksum, así que `linkerd.io/inject: disabled` falla.
- **`namespace`: cerrado.** Lo fija `documents-exact`; un PDB en otro namespace falla.
- **`apiVersion`: cerrado.** Un `BackendTLSPolicy` en `v1alpha3` falla.
- **Etiquetas de los objetos, fuera del pod: sin efecto.** No intervienen en ningún selector; la única que importa, `vectra.io/criticality`, ya se compara.
- **`config.linkerd.io/opaque-ports: 8443` en el Service: sin efecto.** El tráfico a 8443 ya es TLS de extremo a extremo; marcarlo opaco no cambia nada.
- **Anotaciones de Argo CD en los documentos: abierto.** Es F-09.

## Hallazgos

### F-09 · NARANJA · `identity-edge/keycloak/policy/keycloak.rego` y `set.rego`, sin regla sobre `metadata.annotations` · Las anotaciones de hook de Argo CD pueden dejar sin aplicar o borrar piezas del diseño
Ningún documento compara sus anotaciones, salvo el pod template. Sobre el render de prod, las dos pasadas de conftest dan rc=0 con:
- `argocd.argoproj.io/hook: Skip` en el `StatefulSet`, el `PodDisruptionBudget`, el `Certificate` `keycloak-tls` o el `ExternalSecret` `identity-ca`;
- `argocd.argoproj.io/hook: PostSync` con `hook-delete-policy: HookSucceeded` en el `BackendTLSPolicy`;
- `helm.sh/hook: test` en el HPA.

Argo CD lo acepta. Con `Skip` no aplica ese manifiesto. Con el hook `PostSync` y `HookSucceeded`, lo crea como hook y lo borra en cuanto el sync termina bien. El resultado es un Keycloak sin StatefulSet, sin PDB, sin `keycloak-tls` o sin la `BackendTLSPolicy` de F05: viola NFR-U2-01 e INF-U2-05b.

Se puede llegar desde los values, sin tocar la política: el chart expone `statefulsetAnnotations` y `service.annotations`, y en `extraManifests` el texto es libre.

Arreglo, de la misma clase que lo ya cerrado: comparar `metadata.annotations` de cada documento con el render versionado. Hoy ningún documento lleva anotaciones salvo el pod template, así que basta con exigir que no haya ninguna.

## Alcance
El diff de la ronda 4 solo toca `policy/`, `test_keycloak_deploy.py`, la bitácora y la respuesta. No toca values, render, Dockerfile, realms, tema, `platform/`, `contracts/` ni workflows. El worktree queda limpio. Las cifras de la bitácora (2418, 8 por entorno, 265, 49, 349, `pass: 13`) coinciden con mis ejecuciones.

## Tareas candidatas
- Siguen en pie las de las rondas anteriores: U1 no cubre los StatefulSet, y las métricas de F60 deben leerse por HTTPS.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r4/ca5.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r4/probe/mut4.py`

NARANJA|identity-edge/keycloak/policy/set.rego:94|metadata.annotations sin comparar: `argocd.argoproj.io/hook: Skip` o un hook PostSync con borrado dejan sin aplicar o eliminan el StatefulSet, el PDB, `keycloak-tls` o la BackendTLSPolicy
INFORME: revisiones/U02-T07/ronda-4.md
VEREDICTO: NO-VERDE
