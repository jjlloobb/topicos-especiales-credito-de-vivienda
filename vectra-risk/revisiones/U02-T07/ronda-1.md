# Ronda 1 — U02-T07

VEREDICTO: NO-VERDE

Revisé `ca7f425` sobre la base `ca29712`. El hash de la tarea coincide (`c245f180…`). El worktree estaba limpio antes de empezar y sigue limpio. Ejecuté todo sobre una copia hecha con `git archive HEAD`, en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r1/wt`, con su propio venv. No dejé procesos abiertos.

`make -C platform check-tools` escribe en `platform/.tools/integration/`. En la copia, `platform/.tools` es un enlace al repositorio principal, así que esa escritura cayó allí. Es un directorio ignorado y `git status` del repositorio principal no cambió.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Render y políticas propias | `make -C identity-edge render-keycloak && conftest test --policy identity-edge/keycloak/policy identity-edge/keycloak/rendered/` | pasa: 1560/1560, rc=0. El render reproduce lo versionado. Las reglas de presencia no corren con este comando (ver F-04). |
| 2 | Cada regla falla sobre un render alterado | `uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q` | pasa: 133, 10,2 s, 0 omitidas |
| 3 | Los valores salen del diseño | `... -q -k design -rs` | pasa: 34, 0,94 s, 0 omitidas. Corre helm de verdad: incluye los casos sin digest y sin `issuerRef`. |
| 4 | Políticas de U1 | el `kyverno apply ...` literal y luego `conftest ... platform/policies/rego` | pasa sin evaluar nada: kyverno aplica 0 reglas a 13 recursos (`pass: 0`); Rego 91/91. Lo que sí evalúa es `policy-keycloak-u1`: `pass: 13, fail: 0` en los tres entornos, Rego 91 y `hpa` 3. Las 8 alteraciones de U1 hacen fallar a kyverno. |
| 5 | Todo sigue cumpliendo | `uv sync --frozen && make -C identity-edge check && make -C platform check-tools` | pasa, rc=0, 1 min 24 s. `check` incluye el render, las dos pasadas de `policy-keycloak` y `policy-keycloak-u1`. |

**Decisión sobre CA-4.** Lo doy por cumplido en sustancia. El comando literal pasa en vacío, cosa que demostré con mi propia ejecución, y eso no prueba nada. El codificador lo detectó y lo registró, y su objetivo `policy-keycloak-u1` usa el mismo subconjunto `STATIC_POLICIES` de `platform/Makefile`. Ese objetivo ve recursos y falla con las alteraciones. Las políticas que deja fuera no dejan nada sin revisar:
- `require-spread-and-pdb` (líneas 16 y 39), `require-hpa-bounds` (14 y 42), `add-criticality-to-generated` y `hpa.rego` (24, 35 y 58) solo miran `Deployment`. Confirmo la afirmación del codificador.
- `verify-images` necesita firmas reales.

El hueco de U1 con los StatefulSet queda como candidata.

## Hallazgos

### F-01 · NARANJA · `identity-edge/keycloak/values/common.yaml:73` con `Dockerfile:7-10` · Keycloak no servirá en `/auth` porque la ruta se fija al construir la imagen
El render pone `KC_HTTP_RELATIVE_PATH=/auth` en tiempo de ejecución y arranca con `start --optimized`. En Keycloak, `http-relative-path` y `http-management-relative-path` son opciones de build (`buildTime(true)` en `HttpOptions` y `ManagementOptions`). El `kc.sh build` del Dockerfile de U02-T06 no lleva `--http-relative-path=/auth`. Con `--optimized`, Keycloak ignora un valor de build distinto y sigue usando `/`.

Efectos:
- Las sondas `/auth/health/live` y `/auth/health/ready` en el puerto 9000 darán 404: reinicios en bucle y ningún pod `Ready`.
- La JWKS interna `https://keycloak.vectra-identity.svc:8443/auth/realms/vectra/...` (`shared-infrastructure.md` §4) no responderá.
- El hostname con `/auth` de INF-U2-01 tampoco se cumple.

No pude comprobarlo ejecutando, porque no hay Docker ni red. La conclusión sale del modelo de opciones de Keycloak. El README del chart (sección «Changing the Context Path») da por hecho un arranque sin `--optimized`, que reconstruye la imagen sola.

El arreglo está en el Dockerfile, fuera del alcance de esta tarea. Ante un dato que faltaba, el codificador tenía que detenerse y avisar. Ver D-1.

### F-02 · NARANJA · `identity-edge/keycloak/policy/keycloak.rego:63-67, 205-210, 213-256` · Las comparaciones exactas se esquivan con `valueFrom`
`env_of` solo lee `.value`. Si una variable de `fixed_env` viene de `valueFrom.configMapKeyRef`, `env_of` queda indefinido y ni `!=` ni la regla dedicada se disparan. Lo probé sobre el render de prod (`/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r1/probe/mut.py`): con `KC_HOSTNAME_ADMIN`, `KC_CACHE_STACK`, `KC_PROXY_HEADERS`, `KC_DB_URL_PROPERTIES` y `KC_HTTP_RELATIVE_PATH` sacadas de un ConfigMap, las dos pasadas de conftest terminan en rc=0.

Kubernetes acepta esas variables, y el ConfigMap puede poner el `hostname-admin` público o `sslmode=disable`. Afecta a las 16 entradas de `fixed_env`; solo `KC_HOSTNAME` resiste, porque usa `not ... in`. Hace falta exigir `object.keys(e) == {"name","value"}` en las fijas.

### F-03 · NARANJA · `keycloak.rego:480-495` · Los Service no tienen lista blanca de tipo, nombre ni selector
`service-ports` solo mira los puertos de `keycloak` y `keycloak-admin`. Pasan conftest:
- `keycloak-admin` con `type: NodePort`;
- un Service extra `NodePort` que apunta a 8443 de los pods de Keycloak;
- `keycloak` con otro selector.

`restrict-loadbalancer` de U1 solo bloquea `LoadBalancer`. El efecto es la consola de administración alcanzable desde fuera del clúster, contra X10, SECURITY-09, NFR-U2-26 e INF-U2-01 («no va en el gateway»).

`keycloak-http` y `keycloak-headless`, que el chart siempre genera, no los vigila ninguna regla, así que `service.type: NodePort` en los values pasaría. Su puerto 80 apunta al 8080, donde no escucha nada. Eso por sí solo no abre ningún camino, pero sí son superficie que no se vigila.

### F-04 · AMARILLO · CA-1 · El comando literal no evalúa la presencia de las piezas
Quité `BackendTLSPolicy`, `Certificate` y `PodDisruptionBudget` del render de prod: el comando literal da 400/400. La pasada `--combine --namespace keycloak_set` sí falla. La cubren `make policy-keycloak` (dentro de CA-5) y CA-2. El defecto está en la redacción del criterio. Ver D-6.

### F-05 · AMARILLO · `keycloak.rego:436-440` · En staging y prod se acepta el emisor de kind
Con `issuerRef.name: vectra-internal-ca` en prod, conftest pasa, y las pruebas solo fijan el emisor de kind. Kubernetes lo aceptaría, y F05 fallaría: `identity-ca` lleva la CA del banco. Se arregla con una comparación exacta por entorno cuando D-3 fije el nombre.

## Supuestos del codificador, contra el diseño
- **`hostname` y `hostname-admin` como URL completas.** Salen de cómo funciona Keycloak: el hostname v2 exige URL cuando hay path y para `hostname-admin`. El `:8443` sale del puerto que el codificador eligió para el Service `keycloak-admin`, coherente con `flows.yaml`. Es aceptable.
- **Puerto de gestión en HTTPS.** Sale de Keycloak: la gestión hereda el TLS de 8443 si HTTP está apagado. La consecuencia, que Prometheus debe leer las métricas de F60 por HTTPS, queda como candidata.
- **`verify-full` con el ConfigMap `vectra-internal-ca`.** Sale de U1: NFR-U1-22, el Bundle de `platform/mesh/certificates.yaml`, el SAN `*.vectra-data.svc` de `postgres-server-tls` y el precedente de `restore-drill`. `vectra-identity` está en la malla.
- **Criticidad `high`.** Sale del diseño: NFR-U1-01, la tabla de P-U1-09 (Keycloak en `vectra-high`) y RESILIENCY-01 de U2.
- **HPA al 80 % de CPU.** Es una invención: es el valor por defecto del chart y el diseño de U2 no fija objetivo. Las demás unidades fijaron 70 % cada una. Ver D-4.
- **Nombres de los Secret** (`identity-ca`, `keycloak-config-cli-client`, `keycloak-reader-client`). Son invenciones inevitables y no chocan con nada existente. Ver D-5.
- **Digests de ejemplo.** Salen de la decisión Q2 y de INF-U2-08.
- **`banco-ca`.** Es un marcador inventado. Ver D-3.

## Decisiones para el usuario
- **D-1.** Para que Keycloak sirva en `/auth`, ¿se agrega `--http-relative-path=/auth` al `kc.sh build` del Dockerfile en una tarea de seguimiento de U02-T06? La alternativa es servir en `/`, reescribir el prefijo en el gateway y cambiar la URL de la JWKS en `shared-infrastructure.md`. Sin esto, F-01 no tiene arreglo dentro de esta tarea.
- **D-2.** INF-U2-05b fija un único SAN en `keycloak-tls`, `keycloak.vectra-identity.svc`. ¿Se agrega `keycloak-admin.vectra-identity.svc.cluster.local`? Sin él, quien entre por `hostname-admin` recibe un certificado que no corresponde al nombre.
- **D-3.** ¿Cómo se llama el `ClusterIssuer` de la CA del banco en staging y prod? ¿Se acepta `banco-ca` como marcador hasta el paso de integración?
- **D-4.** ¿Qué objetivo de CPU lleva el HPA de Keycloak: 80 %, como trae el chart, o 70 %, como el resto de servicios?
- **D-5.** ¿Se confirman los nombres `identity-ca`, `keycloak-config-cli-client` y `keycloak-reader-client`? La tarea del Job y `realm-drift` dependerán de ellos.
- **D-6.** ¿Se enmiendan los comandos de CA-1 y CA-4, que pasan sin evaluar parte de lo que prometen, para que usen `make policy-keycloak` y `make policy-keycloak-u1`?

## Alcance
El diff solo toca `identity-edge/keycloak/{policy,rendered,values}`, el `Makefile` y las pruebas de `identity-edge`, `CANDIDATAS.md` y la bitácora. No toca realms, tema, Dockerfile, `platform/`, `contracts/` ni workflows. No hay desborde de alcance. Las cifras de la bitácora (1560, 133, 34, `pass: 13`, 91) coinciden con mis ejecuciones.

## Tareas candidatas
- U1 no cubre reparto, PDB ni HPA de los StatefulSet: la de Keycloak y la de Valkey de U2.
- `kyverno apply platform/policies/kyverno` sobre un directorio aplica 0 reglas.
- La lectura de métricas de Keycloak (F60) debe ir por HTTPS al puerto 9000.
- Los Service `keycloak-http` y `keycloak-headless` del chart no se pueden apagar desde los values.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r1/ca5.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r1/ca4-kyverno.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r1/probe/mut.py`

NARANJA|identity-edge/keycloak/values/common.yaml:73|`/auth` es opción de build; con `--optimized` y el Dockerfile actual Keycloak sirve en `/` y las sondas dan 404
NARANJA|identity-edge/keycloak/policy/keycloak.rego:63|las comparaciones exactas de `fixed_env` se esquivan con `valueFrom` (16 variables)
NARANJA|identity-edge/keycloak/policy/keycloak.rego:480|Service sin lista blanca: `keycloak-admin` NodePort o un Service extra exponen la consola de administración
AMARILLO|CA-1|el comando literal no evalúa la presencia de piezas (lo cubre `make policy-keycloak`)
AMARILLO|identity-edge/keycloak/policy/keycloak.rego:436|staging y prod aceptan el `ClusterIssuer` interno de kind
INFORME: revisiones/U02-T07/ronda-1.md
VEREDICTO: NO-VERDE
