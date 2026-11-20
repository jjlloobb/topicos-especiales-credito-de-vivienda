# U02-T28 — Los jobs de identidad obtienen su token aunque no pidan ningún scope

**Unidad:** U2 — `identity-edge` (jobs `realm-drift` y `signing-key-age`), con el cliente de token de U0 (`vectra_common`)
**Historias que implementa:** ninguna nueva; corrige un defecto medido en `kind-vectra` el 2026-11-19.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> **Medido por el orquestador el 2026-11-19 en `kind-vectra`** (03:00 UTC del 2026-11-20), con Keycloak, el gateway y los demás servicios arriba y sus tokens de servicio funcionando (`case-service`, `product-metrics`: `CLIENT_LOGIN` correcto en el log de Keycloak):
>
> - Los CronJob `signing-key-age` (cada hora) y `realm-drift` (03:00 UTC) de `vectra-identity` **nunca han terminado bien**: `status.lastSuccessfulTime` vacío en los dos; los Job `…-29919060` terminaron `Failed` a los 33 s.
> - En el log de los dos: `POST https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra/protocol/openid-connect/token "HTTP/1.1 400 Bad Request"` y después `vectra_common.errors.DependencyUnavailable: dependency_unavailable`.
> - En el log de Keycloak, a la misma hora: `type="CLIENT_LOGIN_ERROR" … clientId="keycloak-reader" … error="invalid_request" … reason="Invalid scopes: " … grant_type="client_credentials" … client_auth_method="client-jwt"`.
> - `identity-edge/jobs/keycloak_admin.py:79` crea el proveedor con `provider_from_env("keycloak", ())`: sin scopes. `contracts/python/vectra_common/src/vectra_common/service_token.py` (método `token`) envía siempre `"scope": " ".join(self._scopes)`, es decir, `scope=` vacío.
> - `keycloak-reader` no tiene `optionalClientScopes` en el realm; sus permisos son roles de `realm-management` (`view-realm`, `view-clients`, `view-users`).
>
> **Causa probable (a confirmar, no medida con una petición real):** Keycloak 26.8.1 rechaza un parámetro `scope` presente y vacío. Los demás clientes piden scopes y por eso funcionan.
>
> Lo que se quiere:
>
> 1. **Confirma la causa** con el Keycloak real del arnés de integración (`identity-edge/tests/integration`, realm de kind): la petición de `keycloak-reader` con `scope=` vacío da 400 `Invalid scopes`, y sin el parámetro da 200. Si no es la causa, dilo y **para**.
> 2. **`vectra_common.service_token` no envía `scope` cuando no hay scopes.** Con scopes, la petición no cambia.
> 3. **Pruebas:** en `vectra_common`, que el formulario no lleva `scope` con `()` y lo lleva igual que hoy con uno o más; en `identity-edge/tests/integration`, que el lector de `realm-drift` y de `signing-key-age` obtiene su token contra el Keycloak real con la llave de `keycloak-reader`.
> 4. **Qué imágenes hay que reconstruir** para que el arreglo llegue al clúster (la de los jobs de identidad seguro; las de las demás unidades que empaquetan `vectra_common` no lo necesitan para este defecto, pero dilo), y **las órdenes para el orquestador**: publicar, fijar el digest por PR, sincronizar `identity-jobs` y leer de vuelta `kubectl get cronjob -n vectra-identity -o custom-columns=N:.metadata.name,OK:.status.lastSuccessfulTime`.

**Fuera:**

- Lo que `realm-drift` informe una vez que consiga el token: el lector no ve los subflujos y marca 35 diferencias (candidata de U02-T27). Si con el token arreglado el Job termina en fallo por esa deriva falsa, anótalo y no lo arregles aquí.
- El realm (`keycloak-reader` no recibe scopes nuevos para esquivar el defecto).
- `restore-drill` (falla por otra causa: `FileNotFoundError: 'vectra-registry'`, ya en `CANDIDATAS.md`).
- Reintentos o tolerancia al 400 en los jobs.
- Cualquier orden contra el clúster.

---

## Archivos de contexto

- `contracts/python/vectra_common/src/vectra_common/service_token.py`, `deps.py` (`post_form_once`) y sus pruebas en `contracts/python/vectra_common/tests/`
- `identity-edge/jobs/keycloak_admin.py`, `realm_drift.py`, `signing_key_age.py`, `identity-edge/jobs/Dockerfile`, `identity-edge/jobs/chart/`
- `identity-edge/tests/integration/realm_stack.py`, `test_realm_import.py`
- `identity-edge/keycloak/realm/realm.kind.yaml` (cliente `keycloak-reader`, `clientScopeMappings`)
- `CANDIDATAS.md` (entradas de `realm-drift` de U02-T22 y U02-T27)

---

## Criterios de aceptación

- [ ] **CA-1** — Sin scopes, el formulario del token no lleva `scope`; con scopes, no cambia.
  ```bash
  cd vectra-risk && uv run pytest contracts/python/vectra_common/tests -q -p no:cacheprovider -k "service_token"
  ```
  Esperado: pasa. **Rojo primero**, pegado en la bitácora. Comprueba con `--collect-only` qué selecciona el filtro y ajústalo si no recoge las pruebas nuevas.

- [ ] **CA-2** — El lector de los jobs obtiene su token contra el Keycloak real.
  ```bash
  cd vectra-risk && uv run pytest identity-edge/tests/integration -q -p no:cacheprovider -k "reader_token"
  ```
  Esperado: pasa; con el `service_token` de `main`, la misma prueba falla con 400 `Invalid scopes` (rojo primero). Mide la carga antes: levanta Keycloak con Testcontainers.

- [ ] **CA-3** — Ningún otro servicio cambia su petición de token.
  ```bash
  cd vectra-risk && make -C contracts check
  ```
  Esperado: rc 0.

- [ ] **CA-4** — La unidad sigue en verde.
  ```bash
  cd vectra-risk && make -C identity-edge check
  ```
  Esperado: rc 0. Una sola vez, al final.

---

## Plan de pruebas

- Unitarias de `service_token`: formulario sin `scope` con `()`, con `scope` con uno y con varios scopes.
- Integración con el Keycloak real: token de `keycloak-reader` y una lectura de `/admin/realms/vectra` con él.

**Rojo primero:** la prueba de integración contra el `service_token` de `main` debe dar el 400 `Invalid scopes` medido en kind.

---

## Notas

- Archivos que se **modifican en su sitio**: `contracts/python/vectra_common/src/vectra_common/service_token.py` y sus pruebas; las pruebas de `identity-edge/tests/integration`. Nada de duplicados.
- `vectra_common` es de U0 y lo usan todas las unidades: el cambio es solo omitir un parámetro vacío. Si ves otra cosa que cambiar ahí, es candidata.
- No bloquea la demo: son el monitor de deriva del realm y la métrica de edad de la llave de firma.
