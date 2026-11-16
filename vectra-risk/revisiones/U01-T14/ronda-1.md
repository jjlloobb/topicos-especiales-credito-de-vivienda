VEREDICTO: VERDE

# Ronda 1 — U01-T14

Rama `tarea/U01-T14`, punta 18f0b06. Todo se corrió en copias (`git archive` más `.charts`); el worktree quedó intacto. El PR #185 se fusionó en `main` (20f305e) mientras se revisaba.

**Nota del orquestador (2026-11-15):** tras la fusión se sincronizó `network` en `kind-vectra` y se retiraron los cinco recursos temporales; con los permanentes, 40 de 40 peticiones al gateway respondieron 200 y Keycloak siguió listo. Eso mide en el clúster lo que el codificador y el revisor no pudieron: `opaque` con `NetworkAuthentication` en 172.18.0.0/16 basta para el origen real (172.18.0.7).

## Criterios de aceptación, verificados por el revisor (ejecutados)

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | Autorización externa al 10443 | `generate.py --check` y `grep 10443 .../kind/vectra-edge.yaml` | pasa: rc 0, con `Server`, `NetworkAuthentication` y `AuthorizationPolicy` `api-gateway-10443[-external]` |
| 1b | La prueba nueva falla contra main | `test_mesh_admission.py` con el `generate.py` de `origin/main` | pasa: 11 failed, 8 passed |
| 2 | Sondas de Keycloak en el 9000 | el grep de CA-2 | pasa: `keycloak-9000-probes-nodes` (172.18.0.0/16 y 192.168.0.0/16) y `keycloak-9000-probes`; `f60-keycloak-9000(-mtls)` sigue |
| 3 | Barrido | pytest con `-k "probe or external or sonda"` | pasa: 31 passed; los 19 casos de `test_mesh_admission.py` entran en el filtro |
| 4a | pytest de `platform` como la CI | sin `platform/.tools` en el árbol ni en el PATH | pasa: 971 passed en 382 s |
| 4b | `make -C platform check-local` (una vez) | con `.tools` enlazado | pasa: rc 0 |
| 5 | Políticas de U2 | `make -C identity-edge policy-gateway policy-keycloak check-keycloak-rendered` | pasa: rc 0 |
| 6 | Runbook | `test_runbooks.py --operational` y `test_links.py` | pasa: rc 0 |

## Lo generado, en los tres entornos (comparado por tipo y nombre contra `origin/main`)
- Solo adiciones: en `vectra-edge`, `Server/api-gateway-10443` (opaque), `NetworkAuthentication` y `AuthorizationPolicy` `api-gateway-10443-external`; en `vectra-identity`, `NetworkAuthentication/keycloak-9000-probes-nodes` y `AuthorizationPolicy/keycloak-9000-probes`. Las `NetworkPolicy` no cambian.
- El selector `gateway.envoyproxy.io/owning-gateway-name: api-gateway` es un subconjunto de las etiquetas medidas del pod.
- Con `externalTrafficPolicy: Local` no hay SNAT: el origen que ve el proxy es el del balanceador (172.18.0.7), dentro de 172.18.0.0/16.
- **Staging y prod** quedan en `0.0.0.0/32`: el gateway no admite tráfico externo y las sondas de Keycloak se rechazan hasta que se pongan los rangos. No es una regresión (en `main` el 10443 ya caía en `default/deny`) y es coherente con `pod_cidr` y `api_server_cidr`. Falta un sitio único que liste los rangos que hay que poner antes de un despliegue real: candidata.

## Seguridad (leído, salvo lo marcado)
- Al 10443 en kind entran los nodos, el balanceador, la máquina y cualquier contenedor de la red de Docker; **no** los pods (192.168.0.0/16).
- Solo el 10443 del gateway y el 9000 de Keycloak tienen autorización por red (ejecutado). El 19001 sigue con mTLS; el 8443 y el 7800 de Keycloak, sin autorización por red.

## Mutaciones (en una copia)
Anular `external_origin_policy`: 7 failed. Anular `probed_port_policy`: 4 failed. Flujo `external:` a un namespace o a otro workload sin `Server`: 3 failed. `tcpSocket` en Keycloak 8443 o en Sentinel 6379 sin `probed_ports`: 2 failed. `probed_ports` con un puerto que nadie sondea: 1 failed. `scheme: HTTPS` en una plantilla de chart propio: 1 failed. **No se detecta:** un `httpGet` en claro sobre un `Server` `opaque` (F-03).

**Pods de controladores, uno a uno:** data plane de Envoy (`/ready` en 19003, HTTP, sin `Server`: riesgo bajo); Prometheus y Alertmanager (HTTP, sin `tlsConfig`: riesgo bajo); CNPG (8000 con `skip-inbound-ports`: cubierto); KServe en `RawDeployment` (sondas HTTP de la plantilla propia: cubierto); MinIO (el chart no define sondas). No se ve un riesgo real al desplegar U6 a U11.

## Hallazgos
### F-01 · AMARILLO · `platform/network/flows.yaml:20-24` · La autorización por red del 9000 de Keycloak abre más que `/auth/health` y no está dicho
El 9000 también sirve `/auth/metrics` (`KC_METRICS_ENABLED`). El proxy no puede limitar rutas porque es TLS. Antes: solo Prometheus con mTLS. Ahora: además, procesos de la red del host del nodo. Los pods siguen limitados a Prometheus por la `NetworkPolicy` (leído, no medido).

### F-02 · AMARILLO · `platform/network/generate.py:343-354` · `opaque` fijo para todo flujo `external:`, que chocaría en silencio con `merged()` si el puerto ya tuviera un `Server` HTTP. Hoy no ocurre.

### F-03 · AMARILLO · `platform/network/tests/test_mesh_admission.py:186-188` · Una sonda HTTP en claro sobre un `Server` `opaque` se da por cubierta. Hoy no hay ninguna.

### F-04 · AMARILLO · `test_mesh_admission.py:298` · `deepcopy` sin uso; la bitácora atribuye un `Server` inexistente al 13133.

## Tareas candidatas
- Una comprobación previa al despliegue de staging y prod que falle mientras algún `*_cidr` de `flows.yaml` valga `0.0.0.0/32`.
- Que `test_mesh_admission` compruebe el protocolo único por `Server` (F-02) y las sondas HTTP sobre `Server` opacos (F-03).

```
VEREDICTO: VERDE
AMARILLO|platform/network/flows.yaml:20-24|La autorización por red del 9000 de Keycloak abre más que /auth/health y no está dicho
AMARILLO|platform/network/generate.py:343-354|opaque fijo para todo flujo external:
AMARILLO|platform/network/tests/test_mesh_admission.py:186-188|Una sonda HTTP en claro sobre un Server opaque se da por cubierta
AMARILLO|platform/network/tests/test_mesh_admission.py:298|deepcopy sin uso
INFORME: revisiones/U01-T14/ronda-1.md
```
