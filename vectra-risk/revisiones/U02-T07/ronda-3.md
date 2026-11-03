# Ronda 3 — U02-T07

VEREDICTO: NO-VERDE

F-06 está cerrado: el pod template del StatefulSet ya se compara contra una lista exacta, y mis sondas de la ronda 2 fallan todas. Los seis criterios pasan con mi propia ejecución. Quedan dos NARANJA, y los dos están fuera del pod template, en las zonas que pediste atacar: los tipos de documento admitidos en el render (F-07) y los campos del HPA, el PDB, el reparto, el `Certificate` y el `BackendTLSPolicy` (F-08). Hice el barrido completo en esta ronda, así que no espero abrir otra clase en la 4.

Revisé `129df8e` sobre `4ce4b55`. El hash de la tarea coincide (`4826b291…`). El worktree estaba limpio antes y sigue limpio. Corrí todo sobre una copia de `git archive HEAD`, en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r3/wt`, con su propio venv. No dejé procesos abiertos. `make -C platform check-tools` vuelve a escribir en `platform/.tools/integration/` del repositorio principal a través del enlace; es un directorio ignorado.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Políticas propias | `make -C identity-edge render-keycloak policy-keycloak` | pasa: 2418/2418 por archivo y 5/5 en cada entorno. El render reproduce lo versionado. |
| 2 | Cada regla falla sobre un render alterado | `uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q -rs` | pasa: 230 en 20 s, 0 omitidas |
| 3 | Los valores salen del diseño | `... -k design -rs` | pasa: 46 en 1,5 s, 0 omitidas, con helm de verdad |
| 4 | Políticas de U1 | `make -C identity-edge policy-keycloak-u1` | pasa: kyverno `pass: 13, fail: 0` en los tres entornos, Rego 91 y `hpa` 3 |
| 5 | Todo sigue cumpliendo | `uv sync --frozen && make -C identity-edge check && make -C platform check-tools` | pasa, rc=0: 1101 en `identity-edge`, kyverno de U1 67 + 38 + 239 |
| 6 | Enmiendas con lectura de vuelta | `uv run pytest ...test_keycloak_deploy.py ...test_keycloak_image.py -q -rs` | pasa: 314, 0 omitidas |

## Cierre de F-06
Volví a correr mis sondas de la ronda 2 contra este código. Ahora fallan todas: un `keycloak.conf` o un `quarkus.properties` montados, otra CA, otro Secret de TLS, el montaje de la CA quitado, un `initContainer`, las variables desde un ConfigMap y los cambios en los Service.

Fuera del pod template, el StatefulSet también queda cubierto: sus claves de `spec` son exactas (sin `volumeClaimTemplates`, `replicas` ni `minReadySeconds`), y `updateStrategy`, `podManagementPolicy`, `serviceName` y `selector` son exactos.

## Supuesto del codificador sobre las constantes del chart
Lo acepto. La afinidad, los tiempos de las sondas, la gracia de 60 s y las claves de las anotaciones de checksum vienen del render versionado. `check-keycloak-rendered` obliga a que render y chart cambien juntos. Si el chart cambia, el desajuste sale como fallo, no pasa en silencio. Las rutas de las sondas (`/auth/health/*`) y el esquema HTTPS sí salen del diseño (INF-U2-08) y del comportamiento de Keycloak.

## Hallazgos

### F-07 · NARANJA · `identity-edge/keycloak/policy/keycloak.rego` y `set.rego`, sin regla de tipos · El render admite cualquier tipo de documento
Solo `ExternalSecret`, `Certificate`, `Service` y `Secret` tienen lista blanca o prohibición. `is_keycloak_statefulset` solo mira el objeto llamado `keycloak`. Mi sonda (`/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r3/probe/mut3.py`) añade documentos al render de prod, y las dos pasadas de conftest dan rc=0. Kubernetes los acepta todos, y `policy-keycloak-u1` tampoco los para:
- **Un `Deployment` `kc-extra`** con las etiquetas de los pods de Keycloak y `args: [start-dev]`. Los Service `keycloak` y `keycloak-admin` le mandan tráfico a pods en modo desarrollo, contra NFR-U2-26 y toda la lista exacta de F-06.
- **Un `StatefulSet` `keycloak-b`** igual, con el mismo efecto.
- **Una `NetworkPolicy` que lo permite todo** en `vectra-identity`. Las políticas de red se suman, así que abre 8443 y 9000 a cualquier origen, contra `flows.yaml`.
- **Un `RoleBinding`** que da el `ClusterRole` `admin` a la cuenta `keycloak`.

Arreglo: una lista exacta de pares (tipo, nombre) en `set.rego`. La lista `required` ya existe; basta con exigir además «nada fuera de ella».

### F-08 · NARANJA · `keycloak.rego:130-159, 609-690` · Fuera del pod template, las comparaciones no son exactas
Con la misma sonda, cada una de estas alteraciones pasa conftest (rc=0), la acepta la API y viola el diseño:
- **Reparto por zona.** Con `labelSelector.matchExpressions: [{key: app.kubernetes.io/name, operator: DoesNotExist}]` el selector no casa con ningún pod y la restricción queda vacía. Las réplicas pueden caer en una sola zona, contra NFR-U2-01. `zone_spread` comprueba unos campos sueltos, no la restricción completa.
- **HPA.** Con `behavior.scaleUp.selectPolicy: Disabled` nunca escala por encima de 2, contra «HPA de 2 a 4» de NFR-U2-01. `behavior` no se compara: el chart lo genera, así que va contra el render.
- **PDB.** Con un `selector.matchExpressions` que no casa, el PDB no protege a ningún pod, contra el PDB `minAvailable: 1`. `pdb_ok` solo mira `matchLabels`.
- **`Certificate` `keycloak-tls`.** Las claves de `spec` no son exactas:
  - `isCA: true`: el `ClusterIssuer` de tipo CA lo firma, y la llave de Keycloak queda capaz de emitir certificados en los que confía la cadena. En kind es la misma CA que firma `postgres-server-tls`.
  - `ipAddresses` y `uris` añaden SAN, contra los «exactamente los dos SAN» de INF-U2-05b (D-2).
  - `usages: [client auth]` deja el certificado sin uso de servidor.
  - `issuerRef.group` lo desvía a otro tipo de emisor con el mismo nombre.
- **`BackendTLSPolicy`.** `validation.subjectAltNames` sustituye la validación por `hostname` (en Gateway API v1, cuando hay SAN declarados se ignora el hostname). El gateway valida contra otra identidad, contra INF-U2-05b y F05. Las claves de `validation` y de `spec` no son exactas.

Arreglo, del mismo tipo que el de F-06: comparar el `spec` completo de HPA, PDB, `Certificate` y `BackendTLSPolicy` y cada restricción de reparto entera. Lo que fija el diseño se lee del diseño; lo demás va contra el render.

## Notas sin severidad
- `TCPRoute` y `UDPRoute` siguen fuera de `no-gateway-route`. No tienen efecto con el listener HTTPS único de INF-U2-02. La lista exacta de tipos de F-07 las cerraría de paso.
- Un Service duplicado en otro namespace no tiene efecto, porque su selector no alcanza pods de `vectra-identity`. F-07 también lo cerraría.
- Con el hostname de kind y el emisor de kind en prod, conftest pasa, pero `test_design_hostnames` lo para dentro de `check`. El supuesto de la ronda 2 sigue siendo aceptable.
- Las anotaciones del StatefulSet y los valores de las anotaciones de checksum no se comparan. No encontré un efecto que viole el diseño.

## Alcance
El diff de la ronda 3 solo toca `policy/`, `test_keycloak_deploy.py`, la bitácora y la respuesta. No toca values, render, Dockerfile, realms, tema, `platform/`, `contracts/` ni workflows. El worktree queda limpio. Las cifras de la bitácora (2418, 230, 46, 314, `pass: 13`) coinciden con mis ejecuciones.

## Tareas candidatas
- Siguen en pie las de las rondas anteriores: U1 no cubre los StatefulSet, y las métricas de F60 deben leerse por HTTPS.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r3/ca5.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r3/probe/mut3.py`

NARANJA|identity-edge/keycloak/policy/set.rego:26|sin lista exacta de tipos de documento: un Deployment o StatefulSet extra con las etiquetas de Keycloak, una NetworkPolicy que lo permite todo o un RoleBinding pasan
NARANJA|identity-edge/keycloak/policy/keycloak.rego:130|fuera del pod template no hay comparación exacta: reparto vaciable, HPA con scaleUp Disabled, PDB que no casa, Certificate con isCA, IPs o URIs extra, BackendTLSPolicy con subjectAltNames
INFORME: revisiones/U02-T07/ronda-3.md
VEREDICTO: NO-VERDE
