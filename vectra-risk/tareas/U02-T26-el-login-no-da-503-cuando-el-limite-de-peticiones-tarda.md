# U02-T26 — El login no da 503 cuando la consulta al límite de peticiones tarda unos milisegundos de más

**Unidad:** U2 — `identity-edge` (gateway)
**Historias que implementa:** ninguna nueva; corrige un defecto medido en `kind-vectra` el 2026-11-18.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> **Medido por el orquestador el 2026-11-18 en `kind-vectra`**, con el gateway, Valkey, los sentinel y las dos réplicas de `envoy-ratelimit` arriba y sin reinicios recientes:
>
> - Cuatro logins fallaron con `503 urn:vectra:problem:dependency_unavailable` (10:45, 10:46, 11:04 y 11:15 UTC), sobre un puñado de intentos. Los siguientes intentos pasaron sin tocar nada.
> - El registro de acceso del gateway, en cada fallo: `GET`, ruta `httproute/vectra-edge/auth/rule/0/match/4` (es `/auth/realms/vectra/protocol/openid-connect/auth`), `status 503`, `response_flags: RLSE`, `duration_ms` 21 y 56.
> - `envoy-ratelimit`, en sus dos réplicas, a esas horas: `rate limit call failed with a Redis error: waiting for response from Conn: context canceled` y `… context deadline exceeded`.
> - Solo las rutas de login y de token pasan por el límite global (`auth-rate-limits`); `…/certs` no, y nunca falló (seis de seis en 50 ms).
> - El 503 lo pone el `EnvoyPatchPolicy` `auth-fail-closed` (`failure_mode_deny: true`, `status_on_error: 503`), que es decisión de diseño (P-U2-01, NFR-U2-21) y **no se toca**.
> - El `EnvoyGateway` no declara plazo para el servicio de límites (`rateLimit.timeout` ausente en `envoy-gateway-config`).
>
> **Causa probable (a confirmar, no medida):** el plazo que el filtro `envoy.filters.http.ratelimit` da al servicio de límites es el de fábrica, muy corto (el primer fallo se cortó a los 21 ms), y con Valkey detrás de la malla una consulta a veces tarda más. Como `/auth/**` cierra el paso ante un fallo del servicio, un retraso de milisegundos se convierte en un 503 de login. No tiene que ver con U02-T25 (la primera conexión tras un rato sin tráfico), que era de la malla y ya está cerrada.
>
> Lo que se quiere:
>
> 1. **Confirma la causa** con el render de xDS del repositorio (`make -C identity-edge xds-gateway` o el objetivo que corresponda): qué `timeout` lleva hoy el filtro de límites del dominio de `/auth/**`, y qué valor de fábrica documenta Envoy Gateway v1.9.3 y Envoy. Si el plazo no es la causa, dilo y **para**.
> 2. **Da margen al plazo, por el camino que el generador ya usa.** `route_gen` ya parchea ese mismo filtro (`fail_closed` en `gateway/routes.yaml`). El plazo debe ser un dato de `routes.yaml` (por entorno si hace falta) y salir en lo generado. Justifica el valor en la bitácora: lo bastante holgado para un portátil con el clúster completo, y acotado, porque mientras espera el gateway retiene la petición de login. Di qué pasa con staging y prod: si el valor de fábrica también es el suyo, propón el valor y márcalo como decisión de diseño a confirmar; no lo dejes distinto sin decirlo.
> 3. **Una prueba que lo fije:** falla si lo generado para kind deja de llevar el plazo, y si `failure_mode_deny` o `status_on_error` cambian (siguen como están).
> 4. **El runbook** `identity-edge/runbooks/rate-limit-backend-down.md` distingue los dos casos: servicio de límites caído (503 sostenido) y consulta lenta (503 suelto con `RLSE` y `context canceled` en `envoy-ratelimit`), y cómo verlo en el registro de acceso.

**Fuera:**

- `failure_mode_deny` y `status_on_error` de `/auth/**`: no se relajan.
- Reintentos en el cliente (`e2e_support.py`, `token.sh`, `promotion-tool`): no esconden el defecto.
- Los límites y recursos de Valkey y de los sentinel (los `sentinel` tienen 100m de CPU y son los contenedores más estrangulados del clúster: anótalo en `CANDIDATAS.md` si no está, con tu opinión sobre si contribuye).
- `platform/operators/envoy-gateway*.yaml` (son de U1): si el único camino correcto es `rateLimit.timeout` del `EnvoyGateway`, descríbelo y devuélvelo como pregunta en vez de editarlo.
- El realm y Keycloak (U02-T27).
- Cualquier orden contra el clúster.

---

## Archivos de contexto

- `identity-edge/gateway/routes.yaml` (`fail_closed`), `identity-edge/tools/route_gen.py` (`fail_closed_domain` y el parche), `identity-edge/gateway/generated/*/envoypatchpolicies.yaml` y `backendtrafficpolicies.yaml`
- `identity-edge/tests/unit/test_route_gen.py`, `test_data_plane_policies.py`, `identity-edge/Makefile`
- `identity-edge/docs/adr-envoy-gateway.md`, `identity-edge/runbooks/rate-limit-backend-down.md`
- `tareas/U02-T25-la-primera-peticion-tras-un-rato-sin-trafico-no-falla.md` y su bitácora (otro defecto, misma zona)

---

## Criterios de aceptación

- [ ] **CA-1** — Lo generado lleva el plazo en el filtro de `/auth/**`, y sigue cerrando el paso con 503.
  ```bash
  cd vectra-risk && make -C identity-edge route-gen check-route-gen && grep -n -A6 -E 'timeout|failure_mode_deny|status_on_error' identity-edge/gateway/generated/kind/envoypatchpolicies.yaml
  ```
  Esperado: rc 0; el plazo, `failure_mode_deny: true` y `code: 503`. Ajusta los nombres de los objetivos si son otros y dilo.

- [ ] **CA-2** — Una prueba lo fija.
  ```bash
  cd vectra-risk && uv run pytest identity-edge/tests/unit -q -p no:cacheprovider -k "fail_closed or ratelimit_timeout"
  ```
  Esperado: pasa. **Rojo primero**, pegado en la bitácora. Mutaciones que deben fallar: quitar el plazo de `routes.yaml`; poner `failure_mode_deny: false`. Comprueba con `--collect-only` qué selecciona el filtro.

- [ ] **CA-3** — El xDS rendido acepta el parche (el campo existe en esa versión de Envoy y queda donde debe).
  El objetivo de xDS del `Makefile` de `identity-edge` (`xds-gateway` o el que sea). Esperado: rc 0 y el `timeout` visible en el filtro del dominio de `/auth/**`. Si ese objetivo necesita herramientas que no están, dilo como «no medido».

- [ ] **CA-4** — La unidad sigue en verde.
  ```bash
  cd vectra-risk && make -C identity-edge check
  ```
  Esperado: rc 0. Una sola vez, al final. Si `check` lanza Testcontainers con Keycloak, dilo y mide la carga antes.

---

## Plan de pruebas

Las de CA-2. **Rojo primero.**

---

## Notas

- **Nada contra el clúster `kind-vectra`, ni lecturas.** Corre TODO con `KUBECONFIG=/nonexistent` y con un `PATH` sin `/snap/bin`. No uses `~/.kube/config` ni `~/.kube/kind-vectra-readonly`.
- Lo que no puedes medir sin clúster dilo como «no medido». Deja en la bitácora las órdenes para el orquestador: qué Application sincronizar (`gateway`), qué leer después (el `EnvoyPatchPolicy` aceptado: `status.conditions`), y cómo comprobar que el 503 suelto deja de salir (N logins seguidos con `token.sh` y cero `RLSE` en el registro de acceso).
- Busca si alguna prueba de otra unidad fija literales de lo que tocas (pasó en U00-T06 con `platform/tests/test_ci.py`) y corrígela si tu cambio la rompe, diciéndolo.
- La máquina es un portátil que se satura: una sola corrida pesada a la vez; anota la carga (`uptime`) junto a cada corrida larga.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u02t26-`, y borra tus copias al terminar.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
