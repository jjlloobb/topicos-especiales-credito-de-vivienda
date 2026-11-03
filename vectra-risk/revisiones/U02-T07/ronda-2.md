# Ronda 2 — U02-T07

VEREDICTO: NO-VERDE

F-01 a F-05 están cerrados y las enmiendas D-1 a D-6 están aplicadas tal como dice el diseño. Queda un NARANJA nuevo, F-06: los volúmenes y montajes del contenedor de Keycloak no tienen lista blanca, y por ahí se puede meter la misma configuración que F-02 cerró en las variables de entorno. Es de la misma familia que F-02 y debí barrerlo en la ronda 1. Es un fallo de revisión mío, no del codificador.

Revisé `139f26c` sobre `764e60b`. El hash de la tarea coincide (`4826b291…`). El worktree estaba limpio antes y sigue limpio. Corrí todo sobre una copia hecha con `git archive HEAD`, en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r2/wt`, con su propio venv. No dejé procesos abiertos. Igual que en la ronda 1, `make -C platform check-tools` escribe en `platform/.tools/integration/` del repositorio principal, a través del enlace; es un directorio ignorado.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Políticas propias, por archivo y por entorno | `make -C identity-edge render-keycloak policy-keycloak` | pasa: 1755/1755 por archivo y 4/4 en cada entorno. Tras el render, la copia sigue limpia: lo versionado coincide con un render fresco. |
| 2 | Cada regla falla sobre un render alterado | `uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q -rs` | pasa: 162 en 14 s, 0 omitidas |
| 3 | Los valores salen del diseño | `... -q -k design -rs` | pasa: 40 en 1,2 s, 0 omitidas. Corre helm de verdad. |
| 4 | Políticas de U1 | `make -C identity-edge policy-keycloak-u1` | pasa: kyverno `pass: 13, fail: 0` en los tres entornos, Rego 91 y `hpa` 3 |
| 5 | Todo sigue cumpliendo | `uv sync --frozen && make -C identity-edge check && make -C platform check-tools` | pasa, rc=0: 1033 pruebas en `identity-edge`, kyverno de U1 67 + 38 + 239 |
| 6 | Enmiendas con lectura de vuelta | `uv run pytest .../test_keycloak_deploy.py .../test_keycloak_image.py -q -rs` | pasa: 246, 0 omitidas |

## Cierre de la ronda 1
- **F-01, `/auth`: cerrado.**
  - `kc.sh build` lleva `--http-relative-path=/auth`, y `design_build_options` lo lee de INF-U2-08.
  - La lista exacta de `dockerfile_problems` rechaza la opción ausente, duplicada, con otro valor o escrita como `--http-relative-path /auth`.
  - Otra instrucción, como un `ENV`, rompe la secuencia exacta de instrucciones.
  - La gestión hereda `/auth`, así que las sondas `/auth/health/*` quedan coherentes.
- **F-02, variables de entorno: cerrado.** Aplica el arbitraje: `{name, value}` exacto, y `secretKeyRef` exacto en las dos variables de `pg-role-keycloak`. En mi sonda fallan las variables tomadas de un ConfigMap, `value` junto con `valueFrom` y `KC_DB_PASSWORD` desde un ConfigMap.
- **F-03, Service: cerrado.** Hay una lista blanca exacta de los cuatro Service, que fija el tipo `ClusterIP`, el selector, las claves de `spec` y los puertos. En mi sonda fallan `externalIPs` y `keycloak-headless` como `NodePort`. Un duplicado de `keycloak-admin` en `vectra-edge` pasa, pero su selector no alcanza pods de `vectra-identity`, así que no tiene efecto.
- **F-04: cerrado** con la enmienda D-6 a CA-1.
- **F-05: cerrado** con `issuer-per-environment`.

## Enmiendas contra el diseño
- **D-2:** los dos SAN de INF-U2-05b, en orden.
- **D-4:** HPA al 70 %, leído de NFR-U2-01.
- **D-5:** nombres de los Secret leídos de INF-U2-01.
- **D-3:** `vectra-internal-ca` solo en kind; `banco-ca` en staging y prod.

Todas tienen un caso que falla sobre un render alterado.

## Supuestos del codificador
- **`issuer-per-environment` reconoce kind por `KC_HOSTNAME`.** Lo acepto. Conftest no sabe en qué entorno está. Si prod llevara el hostname y el emisor de kind, conftest pasaría (lo probé), pero `test_design_hostnames` lo para: compara el render de cada entorno con la tabla de INF-U2-01, y forma parte de `make check`.
- **Los Service del chart se aceptan tal cual.** Lo acepto. Ahora están en la lista blanca exacta y son `ClusterIP`. El puerto 80 de `keycloak-http` y `keycloak-headless` apunta al 8080, donde no escucha nada: es un puerto muerto, no un camino abierto.

## Hallazgos

### F-06 · NARANJA · `identity-edge/keycloak/policy/keycloak.rego:372-383` · Volúmenes y montajes sin lista blanca: la configuración entra por un archivo en vez de por el entorno
`tls-mount` solo exige que exista un volumen con el Secret `keycloak-tls`. No mira qué se monta ni dónde. Mi sonda está en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r2/probe/mut2.py` y `mut3.py`. Sobre el render de prod pasan las dos pasadas de conftest (rc=0) con estas alteraciones:
1. Un ConfigMap montado con `subPath` en `/opt/keycloak/conf/keycloak.conf`. Kubernetes lo acepta, y Keycloak lee ese archivo al arrancar, también con `--optimized`, para toda opción que no venga por variable de entorno. Una línea `db-url=jdbc:postgresql://…?sslmode=require` anula `KC_DB_URL_HOST` y `KC_DB_URL_PROPERTIES`: si `db-url` está fijado, las opciones de host y propiedades se ignoran. Se cae así el `verify-full` de NFR-U1-22 que F-02 había dejado blindado. Lo mismo vale para `http-enabled=true` y otras opciones de ejecución.
2. Un `quarkus.properties` montado en `/opt/keycloak/conf/`.
3. El volumen `internal-ca` apuntando a otro ConfigMap: Keycloak verifica PostgreSQL con una CA que no es el Bundle `vectra-internal-ca`.
4. `/etc/x509/https` montado desde otro Secret mientras el volumen de `keycloak-tls` sigue declarado sin usarse: Keycloak sirve en 8443 un certificado que no es `keycloak-tls`, contra INF-U2-05b.

Arreglo: una lista exacta de `volumes` (nombre y origen) y de `volumeMounts` (nombre, ruta y `readOnly`), igual que se hizo con el entorno y los Service.

## Notas sin severidad
- `no-gateway-route` es una lista negra que deja fuera `TCPRoute` y `UDPRoute`. Lo probé: pasa. Hoy no tiene efecto, porque el `Gateway` de INF-U2-02 solo tiene un listener HTTPS y no las admite.
- `theme_checks.py` cambió aunque la enmienda de alcance solo nombra el Dockerfile y `test_keycloak_image.py`. El cambio es el mínimo que pide CA-6 («leída de INF-U2-08»): `design_build_options` vive ahí. No lo cuento como desborde.

## Alcance
El diff de la ronda 2 toca el Dockerfile (solo la opción nueva), `policy/`, `values/common.yaml`, el render, las pruebas y sus utilidades, la bitácora y la respuesta. No toca realms, tema, `platform/`, `contracts/` ni workflows. El worktree queda limpio. Las cifras de la bitácora (1755, 162, 40, 246, 1033, `pass: 13`) coinciden con mis ejecuciones.

## Tareas candidatas
- Las de la ronda 1 siguen en pie: U1 no cubre los StatefulSet; las métricas de F60 deben leerse por HTTPS.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r2/ca5.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r2/probe/mut2.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t07-r2/probe/mut3.py`

NARANJA|identity-edge/keycloak/policy/keycloak.rego:372|volúmenes y montajes sin lista blanca: un keycloak.conf montado anula verify-full; otra CA u otro certificado montados pasan
INFORME: revisiones/U02-T07/ronda-2.md
VEREDICTO: NO-VERDE
