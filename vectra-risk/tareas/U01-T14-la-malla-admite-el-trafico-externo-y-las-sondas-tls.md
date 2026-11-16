# U01-T14 — La malla admite el tráfico externo del gateway y las sondas del kubelet en puertos TLS

**Unidad:** U1 — `platform-foundation` (generador de red; afecta a los workloads de U2)
**Historias que implementa:** ninguna nueva; cierra dos defectos medidos al desplegar U2 en `kind-vectra` el 2026-11-15, que nunca se habían visto porque U2 no había corrido en un clúster.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> El generador de red (`platform/network/generate.py`, a partir de `flows.yaml`) crea los `Server`, `AuthorizationPolicy` y autenticaciones de Linkerd. Todos los pods mallados llevan `config.linkerd.io/default-inbound-policy: deny`. Dos clases de tráfico legítimo quedan sin autorización en la malla:
>
> 1. **Tráfico que entra de fuera de la malla a un workload mallado.** Los flujos F01, F07 y F08 (`from: [external:…]`, `to: [api-gateway]`, `port: 443`, `target_port: 10443`) solo generan `NetworkPolicy`. El pod del gateway (data plane de Envoy, mallado) no tiene ningún `Server` para el 10443, así que cae en `default/deny`. **Medido:** `linkerd-proxy` del pod `api-gateway` registra `Connection denied server.kind=default server.name=deny tls=Some(Passthru { sni: … "vectra.localtest.me" }) client=172.18.0.7:…` (la IP es la del balanceador de `cloud-provider-kind`), y el cliente ve un error de TLS justo tras el ClientHello. El gateway no sirve nada. El generador debe autorizar en Linkerd el origen externo de esos flujos (un `Server` para el puerto de destino y una `NetworkAuthentication` con el rango de red del origen externo en cada entorno), o excluir ese puerto del proxy de entrada si esa es la decisión de diseño: **lee primero el diseño** (`aidlc-docs/construction/platform-foundation/` y `identity-edge/`, y `identity-edge/docs/adr-envoy-gateway.md`) y elige lo que el diseño respalde; si no lo decide, PARA y pregunta con las opciones. La autenticación de ese puerto la hace Envoy (TLS y JWT), no la malla.
> 2. **Sondas del kubelet a un puerto que no es HTTP en claro.** El generador ya autoriza las sondas en los `Server` con rutas HTTP (`probe_routes`, `_probes`, `NetworkAuthentication` `*-probes-nodes` con `node_cidr` y `pod_cidr`). Keycloak sondea por **HTTPS** en el puerto 9000 (`startupProbe`/`livenessProbe`/`readinessProbe` a `/auth/health`, `scheme: HTTPS`): el proxy no ve la ruta, el `Server` `keycloak-9000` es `deny` y solo autoriza a Prometheus (F60, mTLS). **Medido:** `Connection denied server.name=keycloak-9000 tls=None(NoClientHello) client=172.18.0.2:…` (la IP del nodo), `Startup probe failed: … EOF`, y el kubelet reinicia el contenedor en bucle aunque Keycloak arrancó bien. El generador debe autorizar el origen de las sondas (los mismos rangos `node_cidr` y `pod_cidr`) en los `Server` cuyo workload se sondea por TLS o TCP.
> 3. **Barrido de la clase.** Recorre todos los workloads de `flows.yaml` y los renders de las unidades (U2 a U11, en kind, staging y prod) y lista cada puerto con sondas del kubelet o con origen externo; di cuáles quedan cubiertos y cuáles no. Una prueba falla si un workload mallado tiene una sonda (de cualquier esquema) a un puerto cuyo `Server` no autoriza su origen, o un flujo externo sin autorización en la malla.
> 4. **Runbook** (`platform/runbooks/install.md`), lo medido el 2026-11-15 (ver «Notas»), sin inventar: reiniciar los pods con malla tras sincronizar `linkerd-control-plane`; las credenciales del plugin de Calico que dejan de refrescarse; el doble sync de `keycloak`; y que `vectra.localtest.me` (127.0.0.1) **no** llega al gateway.

**Fuera:**

- Cambiar cómo llega la máquina al gateway (el mapeo del puerto 443 de `platform/kind/cluster.yaml`, un `NodePort`, `/etc/hosts`): solo se documenta lo medido y queda como pregunta al usuario; no lo resuelvas.
- El realm de Keycloak (`identity-edge/keycloak/realm/`): es U02-T24, en paralelo.
- Los charts y el código de las unidades. Si una sonda debería cambiar de esquema, va a `CANDIDATAS.md`.
- Relajar `default-inbound-policy` o quitar la malla de ningún pod sin que el diseño lo respalde.

---

## Archivos de contexto

- `platform/network/` (`flows.yaml`, `generate.py`, `generated/`, sus pruebas en `platform/tests/` y `platform/network/tests/` si existen), `platform/Makefile`
- `identity-edge/gateway/generated/`, `identity-edge/keycloak/rendered/`, `identity-edge/docs/adr-envoy-gateway.md`, `identity-edge/docs/paso-16-kind.md`
- `platform/runbooks/install.md`, `platform/kind/cluster.yaml`
- `DECISIONES-LOOP.md` §11, `CANDIDATAS.md`

---

## Criterios de aceptación

- [ ] **CA-1** — En kind, lo generado autoriza en Linkerd el origen externo de F01, F07 y F08 hacia el 10443 del gateway (o lo excluye, según el diseño), y staging y prod quedan con su rango (o con `0.0.0.0/32` «hasta que el banco entregue el rango», como los demás rangos externos de `flows.yaml`).
  ```bash
  cd vectra-risk && uv run python platform/network/generate.py --check && grep -n -E '10443' platform/network/generated/kind/vectra-edge.yaml | head
  ```
  Esperado: rc 0 y los recursos nuevos. Una prueba nueva lo fija; contra `main`, falla.

- [ ] **CA-2** — En kind, lo generado autoriza las sondas del kubelet al 9000 de Keycloak.
  ```bash
  cd vectra-risk && grep -n -B2 -A12 'keycloak-9000' platform/network/generated/kind/vectra-identity.yaml | grep -E 'NetworkAuthentication|probes|cidr|name:'
  ```
  Esperado: una `NetworkAuthentication` con `node_cidr` y `pod_cidr` y su `AuthorizationPolicy` sobre el `Server` `keycloak-9000`, sin quitar la de Prometheus.

- [ ] **CA-3** — El barrido: ninguna sonda ni flujo externo queda sin autorización en la malla, en los tres entornos.
  ```bash
  cd vectra-risk && uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q -k "probe or external or sonda"
  ```
  Esperado: pasa, con la prueba nueva; la bitácora trae la tabla del barrido (workload, puerto, esquema de la sonda u origen externo, cubierto o no, cómo). Ajusta el filtro al nombre real y dilo. Mutación: quitar la autorización nueva hace fallar la prueba.

- [ ] **CA-4** — Todo `platform` en verde **como lo corre la CI**: sin `platform/.tools` en el árbol ni en el PATH.
  ```bash
  cd vectra-risk && uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q && make -C platform check-local
  ```
  Esperado: pasa. (Para la primera orden, mueve `platform/.tools` FUERA del árbol y devuélvelo.)

- [ ] **CA-5** — Las políticas de U2 siguen pasando sobre lo generado.
  ```bash
  cd vectra-risk && make -C identity-edge policy-gateway policy-keycloak check-keycloak-rendered
  ```
  Esperado: rc 0.

- [ ] **CA-6** — El runbook recoge lo medido y pasa sus comprobadores.
  ```bash
  cd vectra-risk && uv run python platform/tests/test_runbooks.py --operational && uv run python platform/tests/test_links.py
  ```
  Esperado: rc 0.

---

## Plan de pruebas

Las de CA-1 a CA-3. **Rojo primero** en cada una; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`.** El orquestador aplicó a mano, como arreglo TEMPORAL para seguir desplegando, cuatro recursos con la etiqueta `vectra.io/temporal: "true"`: en `vectra-identity`, `NetworkAuthentication/tmp-keycloak-9000-probes-nodes` (172.18.0.0/16 y 192.168.0.0/16) y `AuthorizationPolicy/tmp-keycloak-9000-probes` sobre el `Server` `keycloak-9000`; en `vectra-edge`, `Server/tmp-api-gateway-10443` (selector `gateway.envoyproxy.io/owning-gateway-name: api-gateway`, puerto 10443, `proxyProtocol: opaque`), `NetworkAuthentication/tmp-api-gateway-10443-externo` (0.0.0.0/0) y su `AuthorizationPolicy`. **Con ellos, medido:** Keycloak quedó `Ready` y el gateway respondió (`/auth/admin` 404, `…/protocol/openid-connect/certs` 200). Tu cambio debe hacer innecesarios esos cuatro; di en la bitácora con qué nombres salen los tuyos para que el orquestador retire los temporales al sincronizar `network`.
- Lo medido el 2026-11-15 para el runbook (no lo amplíes con suposiciones):
  1. Tras sincronizar `linkerd-control-plane` el 2026-11-15, los pods con malla creados antes siguieron en `Running`, pero su proxy rechazaba conexiones entrantes sin registrar nada: el proxy de `keycloak-db-1` dejó en su log `Unexpected policy controller response; retrying with a backoff … "initial item not received within timeout"` y Keycloak veía `Connection reset` al negociar TLS con PostgreSQL (métrica del proxy cliente: `outbound_tcp_errors_total{error="i/o"}`; del servidor: `inbound_tcp_errors_total{error="i/o",target_port="4143"}`, sin `authz_allow` ni `authz_deny`). Recrear el pod de la base lo arregló. Se recrearon después todos los pods con malla anteriores a ese sync (las cuatro bases, MinIO y los de observabilidad).
  2. Las credenciales del plugin de Calico (`/etc/cni/net.d/calico-kubeconfig`) dejaron de refrescarse en dos nodos (la fecha del archivo tenía 27 h en `vectra-worker`); los pods nuevos de ese nodo quedaban en `ContainerCreating` con `plugin type="calico" failed (add): error getting ClusterInformation: connection is unauthorized: Unauthorized`. Recrear el pod `calico-node` de cada nodo afectado lo arregló.
  3. El primer `argocd app sync keycloak` terminó en `Failed` («the HPA controller was unable to get the target's current scale: statefulsets.apps "keycloak" not found») y no corrió el hook `keycloak-config-cli`; el segundo sync terminó bien e importó el realm. Además, ese sync espera a `BackendTLSPolicy/keycloak`, que no está sano hasta sincronizar `gateway`.
  4. `https://vectra.localtest.me` (127.0.0.1:443, mapeado al nodo de control por `platform/kind/cluster.yaml`) **no** llega al gateway: nada escucha en el 443 del nodo. El gateway responde en la IP del `LoadBalancer` que asigna `cloud-provider-kind` (172.18.0.7 ese día), alcanzable desde la máquina en Linux: `curl --resolve vectra.localtest.me:443:<ip>`.
- `platform/.charts` y `platform/.tools` no están versionados: enlaza `platform/.tools` a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools` y copia `.charts` del worktree `u01-t13`. No descargues imágenes.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u01t14-`, y borra tus copias del repositorio al terminar.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
