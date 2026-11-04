# Ronda 2 — U02-T10

VEREDICTO: NO-VERDE

Revisé head bdabd36 contra la base 87125f4. Los seis criterios pasan en mi propia corrida, y F-01 a F-11 y Y1 a Y4 están corregidos en el código. Pero al leer el código de v1.9.3 para juzgar el modelo de `test_data_plane_policies.py` encontré un defecto que **ya existía en la ronda 1 y no vi**: el apiserver rechazaría el Deployment del data plane, porque su selector no coincide con las etiquetas de su template (F-12). Al terminar, el worktree está limpio (`git status` vacío) y en bdabd36.

## Criterios de aceptación, verificados por mí
| # | Resultado |
|---|---|
| 1 | pasa: 46 condiciones por entorno, 0 sin aceptar; `test_gateway_xds.py` 33 pruebas en 106 s |
| 2 | pasa: kubeconform 32 de 32 (×3); conftest 13674 y 42 (×3); `test_route_gen.py` 443 pruebas |
| 3 | pasa, 17 pruebas |
| 4 | `policy-gateway` pasa y `test_data_plane_policies.py` da 10 pruebas; **el criterio de fondo no** (F-12) |
| 5 | pasa: `egctl.tar.gz: OK`, v1.9.3; `kyverno test` 72 de 72; integración de U1 `pass: 239, fail: 0`. Con el sha256 alterado en una copia de `tools.env`: `FAILED`, rc=1, y no instala egctl |
| 6 | pasa, en serie después de CA-5: `identity-edge check` 2025 pruebas, `platform check-local` 619, rc=0, ninguna omitida |

## Hallazgos
### F-12 · ROJO · `routes.yaml` `envoy_proxy.pod_labels` / regla `envoy-identity` · el selector del Deployment no selecciona su template
La cadena en el código de v1.9.3:
- `stableSelector()` (`proxy/resource_provider.go:468-476`) arma el selector con `envoyLabels(...)`. Ahí `EnvoyAppLabel()` (`resource.go:53-58`) pone `app.kubernetes.io/name: envoy`.
- `getPodLabels()` (`:812-816`) copia `pod.labels` encima, así que el template sale con `app.kubernetes.io/name: api-gateway`.
- `validatePodSpec` no lo impide, y el CRD tampoco valida `pod.labels`.
- El apiserver rechaza un Deployment cuyo selector no selecciona su template («`selector` does not match template `labels`»). El data plane no se crearía.
- Además, el PDB y el HPA usan ese mismo selector, así que no cubrirían ningún pod.

El modelo del propio codificador lo reproduce: `selector {'app.kubernetes.io/name': 'envoy'}`, template `api-gateway`, `selector matches template: False`. Lo comprobé con `scratchpad/probe/sel.py`. Kyverno no valida esa coincidencia, por eso la prueba pasa.

La etiqueta la exige el plan (`envoyDeployment.pod.labels: {app.kubernetes.io/name: api-gateway}`) y la usa `flows.yaml` (identidad `name: api-gateway`, línea 80). **Necesita decisión del usuario:**
- (a) que las NetworkPolicies del Paso 10 seleccionen el data plane por `gateway.envoyproxy.io/owning-gateway-name: api-gateway`;
- (b) usar otra clave de etiqueta para la identidad.

`restrict-loadbalancer` mira las etiquetas del Service, no el selector, así que no se ve afectada. La prueba del modelo debería exigir que el selector coincida con el template. Mi revisión de la ronda 1 lo pasó por alto.

### F-13 · NARANJA · `platform/policies/kyverno/require-spread-and-pdb.yaml` · la exención por etiqueta vale en cinco namespaces y la regla de reparto solo en uno
- La exclusión por `owning-gateway-name` aplica en `vectra-app`, `vectra-identity`, `vectra-serving` y `vectra-mock` además de `vectra-edge`.
- `require-spread-gateway` solo cubre `vectra-edge`.
- Probé un Deployment `impostor` en `vectra-app` con esa etiqueta, 1 réplica y sin reparto: `kyverno apply` da `pass: 0, fail: 0`. Ninguna regla lo frena.
- Arreglo: acotar la exclusión a `namespaces: [vectra-edge]`.

### F-14 · AMARILLO · comentario de `require-spread-and-pdb.yaml` y texto de Y2 · `require-hpa-bounds` no vigila `minReplicas`
El comentario y Y2 dicen que `require-hpa-bounds` vigila el mínimo de 2. No es así: solo comprueba `minReplicas` del InferenceService (`require-hpa-bounds.yaml:74`), y `hpa.rego` tampoco lo mira. Hoy el mínimo del data plane lo vigila solo `envoy-scaling` de U2. El texto de Y2 lo escribió el orquestador.

### F-15 · AMARILLO · fidelidad de `test_data_plane_policies.py`
Es fiel en lo que importa a las políticas:
- etiquetas del Deployment (`getLabels`) y del pod, con `pod.labels` ganando;
- `replicas` en 1;
- contexto de seguridad: `DefaultSecurityContext` con la raíz de solo lectura en nil y luego mezcla;
- sidecar con requests 10m / 32Mi y sin limits;
- patch mezclado por nombre de contenedor (equivale al `StrategicMerge` en este caso).

Lo que no modela fielmente:
- el selector real tiene más etiquetas (simplificado; no cambia F-12);
- falta `gateway.networking.k8s.io/gateway-name`;
- la imagen del sidecar sale del diseño y no de `platform/operators/*.yaml`, aunque CA-3 la cubre;
- no comprueba que el selector coincida con el template (F-12).

Con el patch, mi simulación del pod da 7 de 7 en las políticas estáticas.

## F-01 a F-11 y Y1 a Y4, contra el código
- **F-01 / Y1:** corregido. Sin el patch, la prueba ve fallar `require-resources`; con él, pasa.
- **F-02:** la bitácora quedó bien. Lo comprobé otra vez sobre la copia.
- **F-03 / Y2:** corregido. Mis Deployments con 1 réplica y sin `replicas` pasan; sin reparto, falla `require-spread-gateway`. Quedan F-13 y F-14.
- **F-04:** una línea por ServiceAccount, ámbito y regla, incluido `certgen`. La prueba detecta que un verbo pase de un `Role` a un `ClusterRole`.
- **F-05:** los literales salen de `routes.yaml` y del diseño, con 12 alteraciones nuevas.
- **F-06:** ya no se atrapa `TranslateError`.
- **F-07 / Y3:** ver la última sección.
- **F-09 / Y4:** `tls` 1.2 / 1.3 en la `ClientTrafficPolicy`, la regla `client-tls` y la aserción en el xDS.
- **F-10:** corregido. Menor: el control del access log del listener quedó dentro de `tls_problems`.
- **F-11:** `registry-only` y `three-patches`.

## `require-spread-gateway` (decisión del usuario, no la pidió nadie)
- **Se necesita:** la regla 1 junta réplicas y reparto en un solo patrón, así que eximirla deja sin reparto al data plane.
- **Es correcta para `vectra-edge`:** caso que falla y casos que pasan en `kyverno test`. No toca nada fuera de los Deployments con esa etiqueta en ese namespace.
- **Alternativa más simple para decidir:** partir `require-spread-and-pdb` en una regla de réplicas, eximida y acotada a `vectra-edge`, y otra de reparto para todos. Eso también cierra F-13.
- El cambio de `exclude: all` a `any` no altera la exención del InferenceService inactivo: sigue siendo un solo filtro con selector y anotación.

## `components.yaml` y `apps/kind/`
- `generate.py --check` da rc=0, y solo cambia `apps/kind/envoy-gateway.yaml`.
- La integración de U1 (239 pasan, 0 fallan) y `check-local` pasan.
- La integración no renderiza envoy-gateway porque es OCI. Lo cubre `test_kind_values_set_the_kind_registry_for_the_sidecar`.

## Transcripciones
En `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/`:
- criterios: `r2/ca1.txt` … `r2/ca6.txt` y `r2/dp.txt`;
- simulaciones de Kyverno: `kyv/` (`dep-impostor.yaml`) y `kyv2/pod.yaml`;
- selector frente a template: `probe/sel.py`;
- código de v1.9.3: `eg/`.

```
VEREDICTO: NO-VERDE
ROJO|routes.yaml envoy_proxy.pod_labels (resource_provider.go:468-476, 812-816 v1.9.3)|El selector del Deployment (app.kubernetes.io/name: envoy) no selecciona su template (api-gateway): el apiserver lo rechaza; necesita decisión del usuario
NARANJA|platform/policies/kyverno/require-spread-and-pdb.yaml|La exención por owning-gateway-name vale en cinco namespaces y require-spread-gateway solo en vectra-edge: un Deployment ajeno escapa a réplicas y reparto
INFORME: revisiones/U02-T10/ronda-2.md
```
