# Ronda 1 — U02-T10

VEREDICTO: NO-VERDE

Revisé head d565da0 contra la base 87125f4. Corrí los seis criterios yo mismo, desde `vectra-risk/`, con CA-5 antes que CA-6 y nunca a la vez. Los seis comandos terminan en 0, pero dos simulaciones con `kyverno apply` muestran que **las políticas de U1 rechazarían el data plane**, y la evidencia de CA-5 en la bitácora está mal registrada. Al terminar, el worktree está limpio (`git status` vacío) y en d565da0.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `make -C identity-edge xds-gateway && uv run pytest …test_gateway_xds.py -q && test -s …adr…` | pasa: 46 condiciones por entorno, 0 sin aceptar; 28 pruebas en 73 s |
| 2 | `route_gen.py --check && make kubeconform-gateway policy-gateway && pytest test_route_gen.py` | pasa: 32 de 32 válidos en cada entorno (son todos los documentos); 12900 pasan en conftest y 42 en `--combine`; 420 pruebas en 81 s |
| 3 | `make render-envoy-gateway && pytest test_envoy_gateway_values.py` | pasa, 14 pruebas, pero el fijado de K14 pierde información (F-04) |
| 4 | `make -C identity-edge policy-gateway` | el comando pasa; **el criterio no**: el data plane no cumple U1 (F-01) |
| 5 | `install-tools.sh && check-tools && egctl version --remote=false` | pasa: `egctl.tar.gz: OK`, v1.9.3. Con el sha256 alterado en `tools.env` falla con rc=1 |
| 6 | `uv sync --frozen && make -C identity-edge check && make -C platform check-local` | pasa: 1984 pruebas, ninguna omitida; rc=0 en 8 min 25 s |

## Defectos del código o de la evidencia
### F-01 · ROJO · CA-4 / sidecar `shutdown-manager` · el pod del data plane no cumple `require-resources` (política estática de U1)
- En v1.9.3 el sidecar sale con requests 10m / 32Mi y **sin limits**: `api/v1alpha1/envoyproxy_helpers.go:176-183`, `proxy/resource.go:211`.
- Armé el pod como lo haría v1.9.3 con este `EnvoyProxy` y le apliqué siete políticas estáticas con `kyverno apply`: `require-resources … failed at path /spec/containers/1/resources/limits/`. Las otras seis pasan.
- La tarea pide que el sidecar cumpla las políticas, y CA-4 dice «si una política de U1 exige algo que el diseño no fija, detente y repórtalo». No se reportó: falta en la bitácora y en `CANDIDATAS.md`.
- La regla `envoy-resources` solo mira el contenedor de Envoy.
- **Necesita decisión del usuario:** qué recursos lleva el sidecar (INF-U2-06 no los fija). El único mecanismo de v1.9.3 es `envoyDeployment.patch` (`MergeWithPatch`, `resource_provider.go:572`).

### F-02 · ROJO · `bitacoras/U02-T10.md:42` y `:99` · la evidencia del sha256 alterado no sale de la orden registrada
- `install-tools.sh` hace `source tools.env`, que pisa la variable del entorno. Corrí la orden registrada, `EGCTL_SHA256=83b6… install-tools.sh`, sobre una copia: `egctl.tar.gz: OK`, rc=0.
- Con `tools.env` alterado, la misma copia da `FAILED`, rc=1, y no instala egctl.
- El comportamiento es correcto; lo falso es el registro. Hay que corregir la orden en la bitácora.

### F-04 · NARANJA · `tests/unit/test_envoy_gateway_values.py:100` · K14 no queda fijado exacto
- `grants()` junta en una línea por recurso todos los verbos y todos los ámbitos.
- Ejemplo: `core/configmaps … update … (cluster, envoy-gateway-system)` (ADR:31). En realidad `update` solo lo da el Role de leader election en `envoy-gateway-system`.
- Si un verbo pasara de un `Role` a un `ClusterRole`, la prueba no lo vería.
- Arreglo: una línea por regla (o por cada combinación de ámbito y verbos).

### F-05 · NARANJA · literales de decisión en el generador y el oráculo (barrido de clase)
- **Generador:** `"Terminate"` (`route_gen.py:565`), `"cpu"`/`"Utilization"` (`:623`), `"JSON"` y el sink `"File"` (`:630`), `"OpenTelemetry"` (`:633`).
- **Oráculo:** `"/dev/stdout"` y `"JSON"` (`gateway_expected.py:697`), aunque INF-U2-02 dice «JSON a stdout»; `maxSkew: 1` y `DoNotSchedule` (`:679`, `:681`), que el diseño fija como «los mismos valores que Keycloak».
- Ningún lector extrae «a stdout», así que cambiar ese texto en el diseño no hace fallar ninguna prueba.
- La bitácora (línea 74) dice «Ningún literal de decisión», y eso es inexacto.
- Menor: el digest está duplicado en `edge.rego:23` y `set.rego:410`.

### F-06 · NARANJA · `tests/unit/test_gateway_xds.py:230` · `except xg.TranslateError: return` cuenta una excepción como acierto
Es el patrón de la lección de U02-T09. Hoy no se dispara: corrí las 13 alteraciones y todas llegan a `problems()` con hallazgos. Pero una alteración futura podría «pasar» sin comprobar nada.

### F-10 · AMARILLO · huecos menores de `test_gateway_xds.py`
- Vuelve a traducir en vez de leer la salida de `make xds-gateway`, que es lo que pide la tarea.
- No comprueba en el xDS:
  - el puerto 4317 (en el EDS está bien);
  - el access log a nivel de listener (filtro `NR`; tiene los mismos campos);
  - que las rutas de `/auth/**` conserven el filtro de `edge-rate-limits` (lo conservan las 11).
- `test_main_fails_when_a_policy_is_not_accepted` no llama a `main`.

### F-11 · AMARILLO · `edge.rego:163-167` y `:400-404` · dos ramas `deny` solo disparan junto con otra
Todas las ramas nuevas fallan en algún caso; lo comprobé con los mensajes de conftest de cada mutación. Pero «registro no permitido» y «debía tener dos parches» solo disparan junto con otra rama de su misma regla: si se borran, no falla nada. Falta un caso propio, por ejemplo `otro.io/vectra/envoy@<digest>`.

## Puntos que necesitan decisión del usuario (no son defectos del codificador)
### F-03 · NARANJA · punto 1 · Kyverno rechazaría el Deployment del data plane
- Confirmado en v1.9.3: con `envoyHpa`, `replicas = nil` (`resource_provider.go:514-516`), y el apiserver lo deja en 1.
- `require-spread-and-pdb` (Enforce) solo exime con `serving-state: inactivo` y `hpa-exempt` juntos. `kyverno apply` falla en `/spec/replicas/` tanto con 1 como sin el campo.
- El `replicas: 2` del `EnvoyProxy` (y su regla de conftest) no tiene efecto con HPA.
- Opciones: eximir en U1 el Deployment con `owning-gateway-name`, como ya hace `require-pdb` (fuera del alcance de `platform/`), o renunciar al HPA de W5.
- Era una condición de «detente», y quedó anotada como candidata.

### F-07 · AMARILLO · punto 2 · falta la imagen del `shutdown-manager` para kind
X3 fija `kind-registry:5000/…`, pero hace falta un archivo nuevo y una entrada en `components.yaml`, y la cerca de alcance lo prohíbe. En kind la política pasa (acepta `registro.banco.internal/vectra/*`), pero la imagen no se podría bajar. El orquestador decide si amplía el alcance o lo difiere formalmente.

### AMARILLO · punto 3 · raíz de solo lectura sin `emptyDir` en Envoy
v1.9.3 escribe el log de admin a `/dev/null` y el access log a stdout, el admin es por TCP y el bootstrap no usa sockets UDS. Es probable que arranque. Comprobarlo en el Paso 16, como ya está anotado, es razonable.

### F-09 · AMARILLO · punto 4 · TLS mínimo de NFR-U2-22
El xDS que generé ya trae `tlsMinimumProtocolVersion: TLSv1_2` y `tlsMaximumProtocolVersion: TLSv1_3` por defecto de v1.9.3; las suites son las de Envoy. NFR-U2-22 se verifica con `testssl.sh` en el Paso 16. Decisión: fijarlo de forma explícita con `ClientTrafficPolicy.tls` y una aserción en el xDS. El texto de la candidata es inexacto.

### AMARILLO · K14 sin el ServiceAccount de certgen
X2 dice «exactamente el RBAC del chart», pero el ADR y la prueba excluyen el ServiceAccount `…-certgen`. Hay que decidir si entra en K14.

## Lo que pediste revisar y está bien
- **`EnvoyPatchPolicy`:** solo el filtro `envoy.filters.http.ratelimit/vectra-edge/auth-rate-limits` tiene `failureModeDeny` y `statusOnError: ServiceUnavailable`. Solo las rutas de auth lo usan, y conservan el filtro de `edge-rate-limits`.
- **IP real:** `useRemoteAddress: true` y sin `originalIpDetectionExtensions`. Las alteraciones con 1 y con 0 saltos hacen fallar la prueba.
- **Access log (P-U2-07):** exactamente los 9 campos, sin query ni cabeceras, a `/dev/stdout`, también a nivel de listener.
- **Tracing:** muestreo `random` y `overall` al 100, `authority otel-collector.vectra-observability.svc`, puerto 4317.
- **Imagen del `shutdown-manager` (X3):** la clave existe en v1.9.3 (`envoygateway_types.go:435`, `:1058`).
- **Alcance:** en `platform/` solo cambian los cuatro archivos permitidos, y el diseño solo lo tocó e9f510a (orquestador). El cambio en `crd_schemas.py` hace falta para que kubeconform valide `Certificate` (CA-2); no es un desborde.
- **U02-T09:** sin regresiones. La prueba de cambio en el diseño sigue sin contar excepciones como acierto, y el conjunto de documentos por entorno sigue siendo exacto.

## Tareas candidatas
- Eximir en U1 el Deployment de Envoy Gateway en `require-spread-and-pdb` (F-03).
- Añadir el values de kind del controlador (F-07).

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/`:
- Criterios: `ca1.txt`, `ca2.txt`, `ca3.txt`, `ca4.txt`, `ca5.txt`, `ca6.txt`.
- Mensajes de conftest por mutación: `rego_probe2.txt`.
- Simulaciones de Kyverno: `kyv/dep-1.yaml`, `kyv/dep-none.yaml`, `kyv2/pod.yaml`.
- Código de v1.9.3: `eg/`.

```
VEREDICTO: NO-VERDE
ROJO|CA-4 / sidecar shutdown-manager (envoyproxy_helpers.go:176 v1.9.3)|El pod del data plane no cumple require-resources: shutdown-manager sin limits, no reportado
ROJO|bitacoras/U02-T10.md:42,99|La evidencia del sha256 alterado no sale de la orden registrada (source tools.env pisa la variable)
NARANJA|tests/unit/test_envoy_gateway_values.py:100|K14 no queda fijado exacto: verbos y ámbitos juntados por recurso
NARANJA|tools/route_gen.py:565-633, tests/strategies/gateway_expected.py:679-700|Literales de decisión en el generador y el oráculo (JSON, OpenTelemetry, cpu, Terminate, /dev/stdout, maxSkew)
NARANJA|tests/unit/test_gateway_xds.py:230|Una excepción de egctl cuenta como acierto
NARANJA|decisión: require-spread-and-pdb frente a envoyHpa (resource_provider.go:514)|Kyverno rechaza el Deployment del data plane (replicas nil -> 1)
INFORME: revisiones/U02-T10/ronda-1.md
```
