# Ronda 3 — U02-T10

VEREDICTO: VERDE

Revisé el head f5943fb contra la base 87125f4 (merge-base confirmado). El hash del archivo de la tarea es 11e1dc6e…, el esperado. Corrí yo mismo los seis criterios, en serie y nada contra un clúster ni contra Docker: todos pasan. F-12 a F-15 están corregidos en el código, y Z1 y Z2 se aplicaron como dice el plan enmendado. Al terminar, `git status --short` sale vacío y el worktree sigue en f5943fb. Quedan tres AMARILLOS que no bloquean y una tarea candidata.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | xDS offline y ADR | el de CA-1 | pasa: 33 pruebas en 150 s (corre `egctl` de verdad), rc=0 |
| 2 | generado contra el oráculo, kubeconform, conftest | el de CA-2 | pasa: kubeconform 32 de 32 (×3), conftest 13803 y 42 (×3), `test_route_gen.py` 446 pruebas, rc=0 |
| 3 | values del controlador y RBAC K14 | el de CA-3 | pasa: 17 pruebas, rc=0 |
| 4 | data plane contra las políticas de U1 | `make -C identity-edge policy-gateway` y además `test_data_plane_policies.py` | pasa: conftest como en CA-2, 18 pruebas con `kyverno apply` real, rc=0 |
| 5 | herramienta egctl | el de CA-5 | pasa: `egctl.tar.gz: OK` y `v1.9.3`. `kyverno test` da 79 de 79 e integración de U1 `pass: 239, fail: 0`. Con el sha256 alterado en una copia de `tools.env` (en el scratchpad): `FAILED`, rc=1, y no instala egctl |
| 6 | todo lo anterior sigue cumpliendo | el de CA-6, después de CA-5 | pasa: `identity-edge check` 2036 pruebas en 647 s, `platform check-local` 619, rc=0, ninguna omitida |

## Hallazgos de la ronda 2, contra el código
- **F-12 / Z1: corregido.**
  - `pod_labels` en `routes.yaml` y en `generated/*/envoyproxies.yaml` ya solo lleva `vectra.io/criticality: high`.
  - El reparto por zona selecciona los pods por `owning-gateway-name: api-gateway`.
  - Contrasté el modelo con v1.9.3: `stableSelector` (l. 468-476), `envoyLabels` con `gateway-name = r.Name()` en modo GatewayNamespace (l. 291-297), `getPodLabels` (l. 812-816) y el selector del Service sobre `infraLabels` (l. 367). El selector del Deployment y el del PDB seleccionan el template en los tres entornos.
  - `flows.yaml` no se toca. La nota del Paso 10 lo deja a ese paso.
- **F-13 / Z2: corregido.**
  - `require-min-replicas` exime `owning-gateway-name` solo en `[vectra-edge]`, y `require-zone-spread` no tiene esa exención.
  - `require-spread-gateway` ya no existe.
  - El `impostor` en `vectra-app` falla las dos reglas, tanto en `kyverno test` (79 de 79) como en la prueba con `kyverno apply`.
  - El `panic` de `require-pdb` que el codificador encontró por su cuenta está bien resuelto: la regla se quita de la copia y la prueba exige el nombre de la regla en la salida.
- **F-14: corregido.** El comentario de la política y el ADR atribuyen el mínimo a `envoy-scaling` de U2.
- **F-15: corregido.** La imagen del sidecar sale de `platform/operators/envoy-gateway*.yaml`, `listener_access_log_problems` es una función aparte y el selector ya tiene todas sus claves.

## Hallazgos
### F-16 · AMARILLO · `identity-edge/gateway/policy/edge.rego:146-162` · `envoy-identity` cubre 3 de las 6 claves del selector (código)
- **El hueco:** en v1.9.3 `pod.labels` también puede sobrescribir `gateway.envoyproxy.io/owning-gateway-name`, `owning-gateway-namespace` y `gateway.networking.k8s.io/gateway-name`. `getPodLabels` copia `pod.labels` encima de `ProxyMetadata.Labels`, y `envoyLabels` deja ganar a las `extra`.
- **Prueba en conftest:** las tres sobrescrituras pasan, `107 tests, 107 passed`. Solo `app.kubernetes.io/name` falla.
- **Por qué es AMARILLO:** el modelo de `test_data_plane_policies.py` sí las detecta (`selecciona: False` para las tres, en `scratchpad/probe/model.py`), y esa prueba corre en `check`. Con Z1, `owning-gateway-name` pasa a ser la identidad de `flows.yaml`, así que conviene que la regla la cubra.

### F-17 · AMARILLO · `identity-edge/tests/unit/test_data_plane_policies.py` · dos detalles del modelo que no son los de v1.9.3 (código, clase F-12)
- **Precedencia de etiquetas:** en `buildIR` (`gatewayapi/translator.go:759-770`) las etiquetas del owning gateway ganan a `infrastructure.labels`. En `proxy_metadata_labels` gana `infrastructure.labels`. Hoy no cambia nada, porque ninguna etiqueta de infraestructura usa esas claves.
- **Nombres:** el modelo nombra el Deployment y el HPA `envoy-vectra-edge-api-gateway`. En modo GatewayNamespace, v1.9.3 usa `r.Name()` = `api-gateway` (l. 228-231 y `scaleTargetRef`, l. 728). Además, la aserción de que «el HPA apunta al Deployment» compara dos literales del propio modelo, así que no prueba nada.

### F-18 · AMARILLO · Z2 en infrastructure-design §INF-U2-02 y en la enmienda de la tarea · «reparto por zona para todos, sin exención» (especificación)
- **La ambigüedad:** `require-zone-spread` conserva la exención del InferenceService inactivo (`vectra.io/serving-state: inactivo` más la anotación `hpa-exempt`), como la regla original de la base. Solo quitó la exención por la etiqueta del gateway.
- **Lectura del codificador:** que «sin exención» se refiere a la del gateway. Es razonable y conserva el comportamiento de U6. El texto literal admite las dos lecturas, y debería precisarlo el orquestador.

## Barrido
- **Literales nuevos de la ronda:** el oráculo toma el valor `api-gateway` de `gd.gateway_ref()`. La clave `owning-gateway-name` es una constante de v1.9.3 (`OwningGatewayNameLabel`), no un valor de diseño visible para el usuario. Los literales `api-gateway` de `edge.rego` siguen el estilo ya aceptado del archivo.
- **Alcance:** en `platform/` solo cambian los archivos autorizados por Y2, Y3 y Z2, más `tools.env`, `install-tools.sh` y `check-tools` del Makefile. Ni `flows.yaml` ni `components.yaml` reciben entradas de lo generado.
- **Diseño:** los cambios de diseño de la ronda los hizo el orquestador (02d1a2b), no el codificador.

## Tareas candidatas (defectos reales fuera de alcance)
- `require-pdb`, en `platform/policies/kyverno/require-spread-and-pdb.yaml`, exime `owning-gateway-name` en los cinco namespaces. Es la misma clase de F-13, pero ya estaba en la base 87125f4 y no lo introduce este diff. Debería acotarse a `vectra-edge`.
- El `kyverno test` de U1 no tiene un Deployment con `vectra.io/serving-state: inactivo` que ejercite la exención de `require-min-replicas`, `require-zone-spread` y `require-pdb`. Solo hay InferenceServices. Ya pasaba en la base.

## Rutas de transcripciones largas
En `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/239312a8-5a57-4075-b645-53f0500660f2/scratchpad/`:
- criterios: `r3/ca1.txt` … `r3/ca6.txt`;
- sha256 alterado: `shaalt/out.txt`;
- sondas de F-16: `probe/ep.yaml` y `probe/model.py`;
- código de v1.9.3: `eg/`.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/gateway/policy/edge.rego:146-162|envoy-identity no prohíbe sobrescribir owning-gateway-name, owning-gateway-namespace ni gateway-name en pod.labels (el modelo sí lo detecta)
AMARILLO|identity-edge/tests/unit/test_data_plane_policies.py|Precedencia de infrastructure.labels invertida y nombre de Deployment/HPA inventado; la aserción del HPA es tautológica
AMARILLO|infrastructure-design INF-U2-02 / enmienda Z2|«sin exención» en require-zone-spread es ambiguo frente a la exención del InferenceService inactivo (especificación)
INFORME: revisiones/U02-T10/ronda-3.md
```
