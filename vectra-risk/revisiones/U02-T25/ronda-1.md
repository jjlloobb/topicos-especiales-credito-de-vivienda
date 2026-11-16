VEREDICTO: NO-VERDE

# Ronda 1 — U02-T25 (punta b67cddd)

**[ejecutado]**: lo corrió el revisor. **[leído]**: solo lo leyó. Todo en copias (`git archive`); nada contra `kind-vectra`.

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | Puerto 10443 en el `EnvoyProxy` de los 3 entornos | `make -C identity-edge route-gen check-route-gen` + grep | pasa: rc 0, `containerPort: 10443` en kind, staging y prod |
| 2 | La prueba ata el puerto a F01 y falla si se quita | `uv run pytest identity-edge/tests/unit -q -p no:cacheprovider -k "route_gen or data_plane"` y `--collect-only` | pasa: 486 passed. El filtro selecciona las 11 pruebas nuevas. Rojo propio con el generado de `main`: 7 failed. Con F01 en 10444: 4 failed |
| 3 | kubeconform, conftest y xds | `make -C identity-edge kubeconform-gateway policy-gateway xds-gateway` | pasa: rc 0 |
| 4 | Barrido en la bitácora | grep | el grep da más de 0, **pero el contenido es falso para U3–U11 y KServe** (F-02) |
| 5 | `identity-edge` en verde | pytest completo sin e2e ni integración | pasa: 2880 (9 fallos de entorno de la copia, sin `.github/`, que pasan al añadirlo) |

## Hallazgos

### F-01 · ROJO · `platform/tests/test_kind_profile.py:151-163` · El parche nuevo rompe la prueba de presupuesto de kind de U1, y con ella la CI
**[ejecutado]** Sin `platform/.tools` y con `.charts`: rama, 16 failed y 13 passed (`KeyError: 'resources'`); `origin/main`, 29 passed. La prueba arma el Deployment del data plane con `c["resources"]` de todos los contenedores del parche, y la entrada `- name: envoy` solo trae `ports`. Único lector del `EnvoyProxy` fuera de `identity-edge`. El codificador declaró verde sin correr la suite de `platform`.

### F-02 · ROJO · CA-4 / `bitacoras/U02-T25.md:72-75`, `CANDIDATAS.md:835-836` · El barrido afirma «sin render» de cosas que sí se renderizan
**[ejecutado]** `helm template` de todos los `Application` de `vectra-risk-gitops/apps/kind`, cruzado con los `Server` de `platform/network/generated/kind`: los charts de U3–U11 declaran 8080 y 8081; el `InferenceService` declara 8080 y 8081 en `kserve-container`. La candidata del `metrics-8081` («ningún render declara 8081») es falsa en `vectra-app` y `vectra-mock`; solo es cierta en `vectra-edge`. No revela defectos nuevos, pero el barrido pedido no se hizo.

### F-03 · NARANJA · `identity-edge/tests/unit/test_route_gen.py:1449-1491` · Ninguna prueba aplica el parche al Deployment que crea Envoy Gateway
**[ejecutado]** A mano, con `kubectl patch --local --type strategic` sobre el fixture de EG v1.9.3: `envoy` queda con los puertos 10443, 19001 y 19003 y conserva imagen, args, sondas y recursos; `shutdown-manager` recibe sus `limits`. **El orden importa:** con el parche invertido, el Deployment reordena los contenedores; nada lo fija. Con `JSONMerge` el resultado es destructivo; la regla `envoy-resources` ya exige `StrategicMerge`. **[leído]** EG v1.9.3 usa `strategicpatch.StrategicMergePatch`.

### F-04 · AMARILLO · `edge.rego:313`, `route_gen.py:591-593` · 10443, 10000 y 1024 escritos a mano, sin cruce con el listener de `egctl`
### F-05 · AMARILLO · `test_route_gen.py:1486-1491` · `test_dropping_the_declared_port_is_seen` es tautológica
### F-06 · AMARILLO · `edge.rego:292-300` · La regla acepta un `envoy` duplicado sin puertos, `protocol: UDP` y un puerto extra

## La causa
**[leído, en las etiquetas fijadas]**
- EG v1.9.3 (`resource.go:89-102`): `envoy` declara solo 19001 y 19003.
- Linkerd edge-26.10.2 (`inject.go`): `getPodInboundPorts` junta los `containerPort` y las sondas HTTP; `GetPodPatch` sobrescribe `PodInboundPorts` después de aplicar las anotaciones: la anotación `pod-inbound-ports` no surte efecto.
- linkerd2-proxy `v2.372.0` (la versión exacta de edge-26.10.2): política permanente para los puertos de la lista; los demás parten de `deny`. `DEFAULT_INBOUND_DISCOVERY_IDLE_TIMEOUT = 90s` (`env.rs:353`), y el chart fija `inboundDiscoveryCacheUnusedTimeout: "90s"`: encaja con lo medido.

Sin verificar: el efecto en el clúster.

## Barrido por unidad (`Server` en kind frente a puerto declarado)

| Workload | Puertos con `Server` | ¿Declarado? | Cómo |
|---|---|---|---|
| U2 api-gateway | 10443, 19001 | 10443 solo con este cambio | render y EG |
| U2 keycloak, valkey, sentinel | 7800, 8443, 9000; 6379, 9121; 26379 | sí | render |
| U10 console-spa | 8080 | sí | render |
| U3, U4, U5, U8, U9, U10 (bff), U11 en `vectra-app`; core-banking-mock | 8080, 8081 | sí, todos | render |
| U6 predictor y explainer | 8080 | sí, en el `InferenceService`; que KServe los copie al Deployment, sin verificar | render |
| CNPG | 5432, 8000, 9187 | sí | leído (CNPG v1.30.1) |
| restore-cluster | 5432, 8000 | sí; **sin verificar** que el selector `app.kubernetes.io/name: restore-cluster` seleccione algo (CNPG fija `postgresql`) | leído |
| Prometheus, Alertmanager, config-reloader | 9090; 9093, 9094; 8080 | sí | leído (prometheus-operator v0.94.2) |
| grafana, kube-state-metrics, operador, pushgateway, otel, minio | — | sí | render |

Conclusión: aparte del 10443 del gateway, ningún puerto con `Server` y tráfico real queda sin declarar.

## Alcance
El diff no toca `platform/`, el realm ni la malla; sin `skip-inbound-ports`; `default-inbound-policy` no cambia.

## Tareas candidatas
- U1/U6: verificar los labels de los pods de `restore-cluster` frente al selector de sus `Server`.
- U1: una prueba que renderice el Deployment del data plane aplicando el `envoyDeployment.patch`.

```
VEREDICTO: NO-VERDE
ROJO|platform/tests/test_kind_profile.py:151-163|El parche nuevo rompe la prueba de presupuesto de kind: 16 failed (main: 29 passed); rompe la CI
ROJO|CA-4 / bitacoras/U02-T25.md:72-75, CANDIDATAS.md:835-836|El barrido dice «sin render» de U3-U11 y KServe, que sí se renderizan
NARANJA|identity-edge/tests/unit/test_route_gen.py:1449-1491|Ninguna prueba aplica el StrategicMerge al Deployment de EG ni fija el orden de los contenedores
AMARILLO|edge.rego:313, route_gen.py:591-593|puertos escritos a mano, sin cruce con el listener de egctl
AMARILLO|test_route_gen.py:1486-1491|prueba tautológica
AMARILLO|edge.rego:292-300|la regla acepta un envoy duplicado y protocol UDP
INFORME: revisiones/U02-T25/ronda-1.md
```
