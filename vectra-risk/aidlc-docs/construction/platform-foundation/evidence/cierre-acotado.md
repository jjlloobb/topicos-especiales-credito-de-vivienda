# Propuesta de cierre de U1 con alcance acotado (issue 7)

**Estado: propuesta.** Rebaja criterios de aceptación de los Pasos 19 y 20, así que solo vale con la aprobación de un revisor humano en su PR. Los Pasos 19, 20 y 23 siguen sin marcar hasta entonces.

## Comprobado en `kind-vectra` (perfil de 14 GiB)

| Punto | Resultado |
|---|---|
| Conformidad de NetworkPolicy | 51 pruebas superadas, 0 fallidas |
| Instalación, waves 0 a 5 | 41 aplicaciones `Healthy` |
| `network` | Argo CD, Kyverno y Linkerd siguen vivos |
| `make -C platform check` | Termina en 0 |
| Restore parcial | `registry-db` 144 s y `case-db` 110 s, con `registry_verifier` y lectura del LSN |
| Rechazos | `latest` por Kyverno; borrado de un objeto bloqueado por WORM |
| Réplica síncrona | `join` termina con el 4143 abierto; `expected` vale 1 |

## No comprobado o incompleto

| Punto | Situación | Destino propuesto |
|---|---|---|
| `linkerd check` (Paso 19) | Sin ejecutar: falta la CLI en la máquina | **Condición de cierre**: lo ejecuta el operador |
| 5 aplicaciones `OutOfSync` (Paso 19) | Linkerd: certificados distintos en cada render. `kyverno`: `labels: {}`. `kyverno-policies`, `postgres` y `observability-monitors`: sin causa identificada; `argocd app diff` no muestra diferencias | Aceptar con esta nota |
| Suite X01–X10 (Paso 20.1) | Solo verificada de forma estática en `flows.yaml`; no hay suite que corra contra el clúster | U12 |
| Pod sin firma (20.2) | `verify-images` no se instala en kind | Staging, con la llave real |
| Autorización de Linkerd entre ServiceAccounts (20.3) | Sin cargas de negocio con las que probar | U3 y U12 |
| Failover de zona (20.4, 4b) | **Inconcluso**, ver `simulacro-failover-reducido.txt`. NFR-U1-03 y NFR-U1-08 quedan parcialmente comprobados | Máquina de al menos 32 GiB, u Operations |
| `Watchdog` recibido (20.7) | Dispara en Prometheus; falta comprobar la recepción | U12 |
| Regla `ilm` repetida | Se acumula, sin corregir | Corregir antes de staging |
| `grafana-folder-check` | Falla por tiempo de espera con la máquina cargada y pasó a las 03:30Z con carga menor; causa sin confirmar. Grafana lleva 11 reinicios e intenta instalar plugins de Internet | Revisar antes de staging |
| Causa del cambio de IP de origen de `kubelet` tras reiniciar un nodo | Sin identificar; se aceptan sondas desde la red de pods | Revisar antes de staging |

Los puntos 20.5, 20.6 y 20.8 ya están asignados a U12 en el plan.

## Bloqueos para staging y prod

- **K11:** ESO necesita leer todos los `Secret`, concedido solo en kind. Decide cumplimiento.
- **AGPL-3.0 de MinIO:** sin revisar. La versión reporta `DEVELOPMENT.GOGET`.
- **Digests:** apuntan a compilaciones locales de kind.
- **CloudNativePG 1.31.0:** elimina el soporte nativo de Barman usado aquí.

## Quién ejecutó

AUTONOMIA-01 preveía un operador humano. Los tramos B, C y D los ejecutó el agente a pedido explícito del responsable, dentro de la aprobación del issue 7 y solo en `kind-vectra`. Los cambios al repositorio pasaron por PR con revisión humana. Aprobar este PR también acepta esa desviación para el ensayo.
