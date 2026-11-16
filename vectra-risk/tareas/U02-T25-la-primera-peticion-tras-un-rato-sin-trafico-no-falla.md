# U02-T25 — La primera petición al gateway tras un rato sin tráfico no falla

**Unidad:** U2 — `identity-edge` (gateway)
**Historias que implementa:** ninguna nueva; cierra un defecto medido en `kind-vectra` el 2026-11-15, con el gateway ya sirviendo.
**Depende de:** U01-T14 (en `main`: el `Server` `api-gateway-10443` y su autorización por red)

---

## Alcance

**Dentro:**

> **Medido.** Con el gateway sano y sin tocar políticas, peticiones seguidas a `https://vectra.localtest.me/auth/realms/vectra/protocol/openid-connect/certs` responden 200 (40 de 40). Tras un rato sin tráfico, la **primera** falla y las siguientes pasan:
>
> ```
> tras 20 s sin trafico: primera=200 segunda=200 tercera=200
> tras 45 s sin trafico: primera=200 segunda=200 tercera=200
> tras 90 s sin trafico: primera=000 segunda=200 tercera=200
> ```
>
> El cliente ve un error de TLS justo tras el ClientHello, y el `linkerd-proxy` del pod del gateway registra, en ese instante:
>
> ```
> INFO  inbound:server{port=10443}: linkerd_app_inbound::policy::tcp: Connection denied server.group= server.kind=default server.name=deny tls=None(PortSkipped) client=172.18.0.7:…
> WARN  inbound: linkerd_app_core::serve: Server failed to become ready error=unauthorized connection on default/deny client.addr=172.18.0.7:…
> ```
>
> **Causa probable (a confirmar).** El pod del data plane de Envoy declara solo los puertos 19001 y 19003 en su contenedor, y el proxy de Linkerd recibe `LINKERD2_PROXY_INBOUND_PORTS=19001,19002,19003`: el 10443, que es por donde entra todo el tráfico externo, **no está entre los puertos que el proxy conoce de antemano**. Para un puerto no declarado, el proxy descubre la política al llegar la primera conexión y la olvida tras un tiempo sin uso; mientras la vuelve a pedir, aplica la política por omisión del pod (`deny`). Un login encadena varias peticiones y a veces empieza justo ahí: en la sesión del 2026-11-15 costó un login de `cro-2`.
>
> 1. Confirma la causa con la documentación de Linkerd de la versión que fija el repositorio (edge-26.10.2: cómo se calcula `LINKERD2_PROXY_INBOUND_PORTS` y qué hace el proxy con un puerto que no está en esa lista) y con el código o la documentación de Envoy Gateway v1.9.3 (qué puertos declara en el contenedor `envoy` y cómo se añaden). Si la causa es otra, dilo y **para**.
> 2. Haz que el 10443 sea un puerto que el proxy de la malla conoce desde el arranque del pod, en los tres entornos, por el camino que el diseño y las herramientas respalden: lo natural es que el contenedor `envoy` declare ese `containerPort` (el `EnvoyProxy` se genera con `route_gen`; ya lleva un `envoyDeployment.patch`), o la anotación de Linkerd equivalente si existe para esa versión. No se quita la malla del pod, no se excluye el puerto del proxy de entrada (`skip-inbound-ports`) y no se cambia `default-inbound-policy`.
> 3. Barrido de la clase: cualquier otro workload mallado que reciba tráfico en un puerto que su contenedor no declara (mira los `Server` de `platform/network/generated/` frente a los `containerPort` de los renders de U2 a U11, y los pods que crean los controladores: KServe, CNPG, Prometheus). Lista los casos; arregla los de U2; los de otras unidades van a `CANDIDATAS.md` con su evidencia.
> 4. Una prueba falla si el `EnvoyProxy` generado deja de declarar el puerto por el que entra el tráfico externo (el `target_port` de F01 en `platform/network/flows.yaml`), en los tres entornos.

**Fuera:**

- `platform/network/` (el generador y `flows.yaml` son de U1; si hace falta un cambio ahí, descríbelo y devuélvelo como pregunta).
- El realm, Keycloak, Valkey y ratelimit.
- El balanceador de `cloud-provider-kind` y `/etc/hosts`.

---

## Archivos de contexto

- `identity-edge/gateway/` (`routes.yaml`, `values/`, `generated/`, `policy/edge.rego`, `policy/set.rego`), el generador `route_gen` (búscalo: `identity-edge/tools/` o donde viva) y sus pruebas (`identity-edge/tests/unit/test_route_gen.py`, `test_data_plane_policies.py`), `identity-edge/Makefile` (`route-gen`, `check-route-gen`, `kubeconform-gateway`, `policy-gateway`, `xds-gateway`)
- `identity-edge/docs/adr-envoy-gateway.md` (decisiones sobre el pod del data plane y la malla)
- `platform/network/flows.yaml` (F01, `target_port: 10443`) y `platform/network/generated/kind/vectra-edge.yaml` (solo lectura)
- `platform/mesh/linkerd-values.yaml` y `linkerd-kind.yaml` (solo lectura)

---

## Criterios de aceptación

- [ ] **CA-1** — El `EnvoyProxy` generado hace que el contenedor `envoy` declare el puerto externo, en kind, staging y prod.
  ```bash
  cd vectra-risk && make -C identity-edge route-gen check-route-gen && grep -n -B2 -A6 '10443' identity-edge/gateway/generated/*/envoyproxies.yaml | head -40
  ```
  Esperado: rc 0 y el puerto en los tres. Ajusta los nombres de los objetivos si son otros y dilo.

- [ ] **CA-2** — Una prueba ata ese puerto al `target_port` de F01 y falla si se quita.
  ```bash
  cd vectra-risk && uv run pytest identity-edge/tests/unit -q -p no:cacheprovider -k "route_gen or data_plane"
  ```
  Esperado: pasa, con la prueba nueva; contra `main`, falla (rojo registrado). Comprueba con `--collect-only` que el filtro selecciona tu prueba.

- [ ] **CA-3** — Las políticas y validaciones del gateway siguen pasando.
  ```bash
  cd vectra-risk && make -C identity-edge kubeconform-gateway policy-gateway xds-gateway
  ```
  Esperado: rc 0.

- [ ] **CA-4** — El barrido está en la bitácora (workload, puerto con `Server`, declarado o no, quién crea el pod), y los casos ajenos a U2, en `CANDIDATAS.md`.
  ```bash
  cd vectra-risk && grep -n -i -c 'containerPort\|declarad' bitacoras/U02-T25.md
  ```
  Esperado: mayor que 0.

- [ ] **CA-5** — `identity-edge` sigue en verde.
  ```bash
  cd vectra-risk && uv run pytest identity-edge/tests --ignore=identity-edge/tests/e2e --ignore=identity-edge/tests/integration -q -p no:cacheprovider
  ```
  Esperado: pasa entero (≈ 14 min: una sola vez, al final).

---

## Plan de pruebas

La de CA-2. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`**, ni contra `vectra.localtest.me`: el efecto en el clúster lo mide el orquestador al sincronizar `gateway` (repetirá la medición de arriba).
- No descargues imágenes. `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`, cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts` (trae `envoy-gateway/gateway-helm`).
- La máquina tiene poca memoria y un clúster de kind completo corriendo: suites pesadas una sola vez.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u02t25-`.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
