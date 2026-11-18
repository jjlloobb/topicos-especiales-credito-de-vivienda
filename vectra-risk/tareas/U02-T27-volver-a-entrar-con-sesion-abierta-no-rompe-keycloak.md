# U02-T27 — Volver a entrar con una sesión abierta no rompe Keycloak, y el descubrimiento de OpenID responde

**Unidad:** U2 — `identity-edge` (realm)
**Historias que implementa:** ninguna nueva; corrige un defecto conocido desde el 2026-11-15 que el 2026-11-18 bloqueó un login real.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> **Lo que ya se sabía (`CANDIDATAS.md`, entrada de U2 del 2026-11-15; causa reproducida en U02-T24 con el Keycloak real):** `GET /auth/realms/vectra/.well-known/openid-configuration` responde 500 con Keycloak 26.8.1 (`IllegalStateException: Duplicate key 2 (attempted merging values 36000 and 36000)`), porque el flujo de login del realm declara varias condiciones de nivel de autenticación con el **mismo nivel 2**, una por rol (`loa-mfa-ingeniero_riesgo`, `loa-mfa-cro`, `loa-mfa-cumplimiento`, `loa-mfa-operacion`, `loa-mfa-break-glass`, `loa-mfa-analista`; todas `loa-condition-level: '2'`, `loa-max-age: '36000'`), y Keycloak falla al juntarlas en una tabla nivel → vigencia. El usuario decidió entonces no tocar el realm; la SPA dejó de depender del descubrimiento (U10-T06).
>
> **Lo nuevo, medido por el orquestador el 2026-11-18 en `kind-vectra`:** el mismo error rompe **el login**. Con `promotion-tool` (cliente `promotion-tool`, PKCE, navegador), el primer login de `ingeniero-1` pasó; los siguientes, desde el mismo navegador, mostraron «We are sorry… Unexpected error when handling authentication request to identity provider», y Keycloak registró en cada uno:
>
> ```
> WARN [org.keycloak.services] KC-SERVICES0013: Failed authentication: java.lang.IllegalStateException: Duplicate key 2 (attempted merging values 36000 and 36000)
> WARN [org.keycloak.events] type="LOGIN_ERROR", realmName="vectra", clientId="promotion-tool", error="invalid_user_credentials", …
> ```
>
> con `400` en `/auth/realms/vectra/protocol/openid-connect/auth`. Los logins de los guiones (`token.sh`, `e2e_support.py`), que nunca llevan cookie de sesión, pasan. **Hipótesis del orquestador, no probada:** Keycloak solo recorre esa tabla cuando la petición llega con una sesión SSO abierta (para decidir si el nivel alcanzado sigue vigente). Si es así, le pasa a cualquier persona que vuelva a entrar con el navegador que ya usó, también en la consola. **El usuario levantó el 2026-11-18 la decisión de no tocar el realm.**
>
> Lo que se quiere:
>
> 1. **Reprodúcelo primero, con el Keycloak real** (el arnés de `identity-edge/tests/integration/realm_stack.py` y la imagen fijada en `tests/fixtures/keycloak-26.8.1`): (a) el descubrimiento responde 500; (b) un segundo login con la cookie de sesión del primero falla con `Duplicate key 2`. Si (b) no se reproduce así, encuentra qué lo dispara y dilo; no sigas a ciegas.
> 2. **Arregla el flujo en los tres realms** (`realm.kind.yaml`, `realm.staging.yaml`, `realm.prod.yaml` y lo rendido): que el flujo no declare dos condiciones con el mismo nivel de autenticación de forma que Keycloak no pueda construir la tabla. **La regla de negocio no cambia:** el MFA sigue siendo obligatorio para los mismos roles y con la misma vigencia (BR-U2-03 y las que cite el diseño funcional), el TOTP repetido sigue rechazándose, y `break-glass` sigue como está. Di en la bitácora qué forma tenía el flujo, cuál tiene ahora y por qué es equivalente, rol por rol.
> 3. **Pruebas con el Keycloak real, rojo primero:** el descubrimiento responde 200 y trae `acr_values_supported` coherente; un segundo login con sesión abierta pasa (y pide o no pide MFA según el nivel y la vigencia, como dicta el diseño); un usuario de cada rol con MFA obligatorio no puede entrar sin TOTP; un usuario sin MFA obligatorio (si lo hay) entra como antes.
> 4. **El realm ya importado:** di cómo llega el cambio a un Keycloak que ya tiene el realm (el Job de `keycloak-config-cli`, el de `identity-jobs`, lo que corresponda) y si las sesiones abiertas o los TOTP ya registrados se ven afectados. `realm_drift` no debe quedar marcando diferencia.

**Fuera:**

- El gateway y el límite de peticiones (U02-T26).
- Cambiar qué roles exigen MFA, la vigencia, o el algoritmo del TOTP.
- La versión de Keycloak.
- `promotion-tool`, la SPA y el BFF. Si conviene que alguno vuelva a usar el descubrimiento, a `CANDIDATAS.md`.
- Cualquier orden contra el clúster.

---

## Archivos de contexto

- `identity-edge/keycloak/realm/realm.{kind,staging,prod}.yaml` (los flujos, las condiciones `loa-*` y sus `authenticatorConfig`), `identity-edge/keycloak/rendered/`, `identity-edge/jobs/` (`rendered/*/realm-configmap.yaml`, `realm_drift.py`, `chart`)
- `identity-edge/tests/integration/` (`realm_stack.py`, `test_realm_import.py`), `identity-edge/tests/fixtures/keycloak-26.8.1/README.md`, `identity-edge/tests/e2e/e2e_support.py` (`Flow`, `totp_code`)
- `CANDIDATAS.md` (la entrada de U2 del 2026-11-15 sobre el descubrimiento), `tareas/U10-T06-la-spa-no-depende-del-descubrimiento-oidc.md`, `tareas/U02-T22-login-con-el-realm-importado.md` y su bitácora
- El diseño funcional de U2 en `aidlc-docs/` (las reglas del MFA por rol y de los niveles de autenticación)
- `.github/workflows/supply-chain.yml` (`skip-files` nombra los realms rendidos: si cambias rutas, se desfasa; mira U02-T20)

---

## Criterios de aceptación

- [ ] **CA-1** — Con el Keycloak real, el descubrimiento responde y el segundo login con sesión abierta pasa.
  ```bash
  cd vectra-risk && uv run pytest identity-edge/tests/integration -q -p no:cacheprovider -k "discovery or sesion_abierta or loa"
  ```
  Esperado: pasa. **Rojo primero, pegado en la bitácora:** con el realm de `main` fallan nombrando `Duplicate key 2` (o lo que hayas encontrado en el punto 1). Comprueba con `--collect-only` qué selecciona el filtro.

- [ ] **CA-2** — El MFA por rol no cambió.
  Las pruebas del punto 3 (una por rol con MFA obligatorio, y la del TOTP repetido), con el Keycloak real. Esperado: pasan. Mutación que debe fallar: quitar del flujo la exigencia de MFA de un rol.

- [ ] **CA-3** — Los tres realms y sus renders son coherentes.
  El objetivo del `Makefile` de `identity-edge` que rinde y comprueba el realm (búscalo y nómbralo). Esperado: rc 0 y sin diferencias sin commitear tras rendir.

- [ ] **CA-4** — La unidad sigue en verde.
  ```bash
  cd vectra-risk && make -C identity-edge check
  ```
  Esperado: rc 0. Una sola vez, al final.

---

## Plan de pruebas

Las de CA-1 y CA-2, con el Keycloak real por Testcontainers. **Rojo primero.**

---

## Notas

- **Nada contra el clúster `kind-vectra`, ni lecturas.** Corre TODO con `KUBECONFIG=/nonexistent` y con un `PATH` sin `/snap/bin`. Docker solo a través de Testcontainers. No uses `~/.kube/config` ni `~/.kube/kind-vectra-readonly`.
- Ninguna contraseña, semilla de TOTP ni token en pruebas, bitácora ni salidas: usa los usuarios y secretos sintéticos del arnés.
- Lo que no puedes medir sin clúster dilo como «no medido». Deja en la bitácora las órdenes para el orquestador: qué Applications sincronizar y en qué orden, qué Job aplica el realm, cómo comprobar el descubrimiento (`curl` a `/.well-known/openid-configuration`, esperado 200) y el segundo login con sesión abierta, y qué hacer si el realm queda a medias.
- Keycloak en Testcontainers pesa: la máquina es un portátil con un clúster completo corriendo. Una sola corrida pesada a la vez, y anota la carga (`uptime`) junto a cada una.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u02t27-`, y borra tus copias al terminar.
- `CANDIDATAS.md`: solo añadir al final (la entrada del 2026-11-15 no se edita: añade una nueva que la cierre). Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
