# U02-T24 — El documento de descubrimiento OIDC del realm responde

**Unidad:** U2 — `identity-edge`
**Historias que implementa:** ninguna nueva; cierra un defecto medido al desplegar U2 en `kind-vectra` el 2026-11-15.
**Depende de:** U02-T22 (en `main`)

---

## Alcance

**Dentro:**

> Con el realm de Git importado en el Keycloak real de kind (imagen `vectra/keycloak`, Keycloak 26.8.1), `GET /auth/realms/vectra/.well-known/openid-configuration` responde **500** (`{"error":"unknown_error",…}`). El log de Keycloak:
>
> ```
> ERROR [org.keycloak.services.error.KeycloakErrorHandler] Uncaught server error: java.lang.IllegalStateException: Duplicate key 2 (attempted merging values 36000 and 36000)
>     at java.base/java.util.stream.Collectors.duplicateKeyException(Collectors.java:135)
>     …
>     at org.keycloak.authentication.authenticators.util.LoAUtil.getLoaMaxAgesConfiguredInRealmFlow(LoAUtil.java:109)
>     at org.keycloak.authentication.authenticators.util.LoAUtil.getLoaMaxAgesConfiguredInRealmBrowserFlow(LoAUtil.java:90)
> ```
>
> Keycloak arma un mapa «nivel de LoA → max-age» recorriendo el flujo de navegador, y el flujo del realm tiene **varias** condiciones con `loa-condition-level: '2'` (una configuración por rol: `loa-mfa-ingeniero_riesgo`, `loa-mfa-cro`, `loa-mfa-cumplimiento`, `loa-mfa-operacion`, `loa-mfa-break-glass`, `loa-mfa-analista`; `identity-edge/keycloak/realm/realm.kind.yaml` ≈ líneas 390 a 660). U02-T22 separó los alias porque compartirlos rompía el login; ahora el nivel 2 aparece repetido y el descubrimiento falla. **Medido además:** `…/protocol/openid-connect/certs` da 200 y `…/protocol/openid-connect/auth?...` da 200 (la página de login se pinta): lo roto es, hasta donde se midió, el documento de descubrimiento.
>
> 1. Reproduce el 500 con el Keycloak real de las pruebas de integración (`identity-edge/tests/integration/`, que ya importan el realm con la misma imagen y el mismo `keycloak-config-cli` por digest), con una prueba que pida el documento de descubrimiento. **Rojo primero.**
> 2. Corrige el realm (los tres: kind, staging y prod, si comparten el defecto) de modo que el descubrimiento responda 200 **y el login siga funcionando para cada rol** con su LoA (`acr`, `amr`), que es lo que U02-T22 arregló. Si las dos cosas no caben a la vez con la forma actual del flujo (un nivel de LoA por rama de rol), elige la forma que el diseño respalde (`aidlc-docs/construction/identity-edge/`, BR-U2-* del login por rol y MFA); si exige cambiar una regla de negocio (por ejemplo, qué roles piden MFA o con qué factor), **PARA y pregunta** con las opciones.
> 3. La prueba de integración queda comprobando, contra el Keycloak real: descubrimiento 200 con el `issuer` esperado; `acr_values_supported` coherente; login de un usuario de cada rol con su `acr` y `amr`; y que ninguna respuesta del realm da 500.
> 4. Mira si algún consumidor del repositorio usa el documento de descubrimiento (BFF, SPA, U12, `promotion-tool`, pruebas e2e): di cuáles, para saber qué estaba roto en la práctica.

**Fuera:**

- La malla y la red (sondas del kubelet al 9000, el puerto externo del gateway): es U01-T14, en paralelo.
- La imagen de Keycloak, el chart, el HPA y la política Rego del despliegue.
- Cambiar usuarios, clientes, scopes o audiencias del realm que no tengan que ver con el flujo de LoA.

---

## Archivos de contexto

- `identity-edge/keycloak/realm/` (`realm.kind.yaml`, `realm.staging.yaml`, `realm.prod.yaml` y de dónde se generan, si se generan), `identity-edge/docs/realm-importacion.md`
- `identity-edge/tests/integration/` (`realm_stack.py`, `test_realm_import.py`, `conftest.py`), `identity-edge/tests/unit/` (pruebas del realm), `identity-edge/Makefile` (`integration`, `collect-integration`)
- `revisiones/U02-T22/` y `bitacoras/U02-T22.md` (por qué se separaron los alias y qué se midió)
- `aidlc-docs/construction/identity-edge/` (diseño del login, LoA y MFA por rol)
- `system-verification/src/vectra_verification/clients/oidc.py` y `tests/doubles/keycloak_tc.py` (cómo hace login U12: solo lectura)

---

## Criterios de aceptación

- [ ] **CA-1** — Contra el Keycloak real con el realm de kind importado, el descubrimiento responde 200 con el `issuer` del realm.
  ```bash
  cd vectra-risk && uv run pytest identity-edge/tests/integration -q -p no:cacheprovider -k "discovery or well_known or descubrimiento"
  ```
  Esperado: pasa; contra `main`, falla con 500 (rojo registrado). Ajusta el filtro al nombre real y dilo.

- [ ] **CA-2** — El login por rol sigue funcionando con su LoA.
  ```bash
  cd vectra-risk && uv run pytest identity-edge/tests/integration -q -p no:cacheprovider
  ```
  Esperado: pasa entero, incluidas las pruebas de U02-T22 (un usuario de cada rol, `acr` y `amr`, sin `VERIFY_PROFILE`).

- [ ] **CA-3** — Los tres realms quedan coherentes y sus pruebas unitarias y políticas pasan.
  ```bash
  cd vectra-risk && uv run pytest identity-edge/tests/unit -q -p no:cacheprovider -k "realm" && make -C identity-edge render-keycloak check-keycloak-rendered policy-keycloak
  ```
  Esperado: rc 0; si el render de kind cambia (el realm viaja en un ConfigMap), va en el commit.

- [ ] **CA-4** — Lo que consume U12 sigue funcionando.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests/integration -q -p no:cacheprovider -k "oidc or keycloak or login"
  ```
  Esperado: pasa (usa el Keycloak de Testcontainers con el realm de kind).

---

## Plan de pruebas

La de descubrimiento contra el Keycloak real (CA-1) y las de login por rol. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`**, ni contra `vectra.localtest.me` ni la IP de su balanceador: en kind hay un Keycloak real con usuarios que se bloquean por fuerza bruta. Trabaja con el Keycloak de Testcontainers (host dinámico), como U02-T22.
- Las imágenes de Keycloak y de `keycloak-config-cli` para las pruebas ya están en la máquina (autorizadas el 2026-11-13). No descargues otras.
- La máquina tiene poca memoria y otro codificador trabaja en paralelo: un solo Keycloak de pruebas a la vez; no corras `make -C identity-edge check` entero más de una vez.
- `platform/.charts` y `platform/.tools`: enlaza `platform/.tools` a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools` y copia `.charts` del worktree `u01-t13`.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u02t24-`.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
