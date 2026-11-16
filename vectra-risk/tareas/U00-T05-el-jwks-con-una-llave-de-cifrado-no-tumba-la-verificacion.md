# U00-T05 — Una llave de cifrado en el JWKS no tumba la verificación de tokens

**Unidad:** U0 — `contracts` (`vectra_common`)
**Historias que implementa:** ninguna nueva; cierra un defecto medido al desplegar en `kind-vectra` el 2026-11-15 que deja **todos** los servicios respondiendo 503 a cualquier solicitud con token.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> El JWKS del realm de Keycloak (`…/protocol/openid-connect/certs`) trae dos llaves: la de firma (`RS256`, `use: sig`) y una de cifrado (`RSA-OAEP`, `use: enc`), que Keycloak genera por omisión en todo realm. `vectra_common/jwks_cache.py` (`JwksCache.get_key`) convierte **todas** las llaves del documento con `jwt.PyJWK.from_dict(item)`; PyJWT 2.15.1 no conoce `RSA-OAEP` y lanza `PyJWKError` («Unable to find an algorithm for key»), que es un `PyJWTError`: el refresco entero se cuenta como error, la caché nunca llega a ser válida y `_from_cache` responde `DependencyUnavailable` (503).
>
> **Medido en el clúster** (dentro del pod de `decision-registry-service`, con su propia librería y el JWKS real):
> ```
> pyjwt 2.15.1
> ERR RSA-OAEP enc PyJWKError Unable to find an algorithm for key: {'kid': '…', 'kty': 'RSA', 'alg': 'RSA-OA…
> ok  RS256 sig
> ```
> Efecto: `POST /v1/entries` del registro con un token de servicio válido (`iss`, `aud`, `scope` correctos) responde 503 `dependency_unavailable` en ≈ 70 ms sin tocar la base; `POST /v1/policies` de governance con el token de `cro-2` responde 503. Sin token, 401. Las conexiones a PostgreSQL, a Keycloak y el token de servicio funcionan.
>
> 1. La caché de JWKS **ignora las llaves que no son de firma** (`use` distinto de `sig`, cuando `use` viene) y **no deja que una llave que la librería no sabe leer invalide las demás**: una llave ilegible se salta y se cuenta (métrica o log, sin secretos), y las de firma legibles se cargan. Si ninguna llave de firma es legible, sigue siendo un error del refresco, como hoy.
> 2. La verificación del token no cambia: un `kid` que no está entre las llaves de firma cargadas sigue siendo 401; el algoritmo aceptado sigue siendo el que la verificación ya fija (no se amplía la lista de algoritmos; una llave `enc` nunca verifica una firma).
> 3. **Barrido de la clase:** busca en todo `vectra-risk/` cualquier otro sitio que lea un JWKS o construya llaves a partir de él (`PyJWK`, `PyJWKSet`, `PyJWKClient`, `jwks`): el BFF de la consola, `system-verification/src/vectra_verification/clients/oidc.py`, los jobs de identidad, las pruebas e2e y sus dobles. Arregla los que tengan el mismo defecto y sean código de producto; di cuáles son y cuáles no lo tienen.
> 4. **Por qué no lo vieron las pruebas:** los dobles de JWKS de las pruebas solo traen llaves de firma. Añade al doble (o a un caso de prueba) un JWKS con la forma real de Keycloak 26 (una `RS256`/`sig` y una `RSA-OAEP`/`enc`), y que las pruebas con Keycloak real que existan (`identity-edge/tests/integration`, `system-verification/tests/integration`) incluyan, si es barato, una verificación de token con `vectra_common` contra el JWKS real.

**Fuera:**

- El realm de Keycloak (quitar la llave de cifrado del realm no es el arreglo: cualquier Keycloak la trae).
- Cambiar de librería JWT o de versión.
- Reconstruir imágenes, digests y cualquier cosa del clúster: lo hace el orquestador después.
- El documento de descubrimiento OIDC (500) y la SPA: es U10-T06.

---

## Archivos de contexto

- `contracts/python/vectra_common/src/vectra_common/` (`jwks_cache.py`, `authn.py`, `deps.py`, `errors.py`, `metrics.py`) y sus pruebas (`contracts/python/vectra_common/tests/` o donde vivan: búscalas)
- `contracts/Makefile` y cómo corre `check` de U0
- Consumidores: `decision-registry/`, `governance/`, `scoring-explainability/`, `case-management/`, `bias-monitoring/`, `console/bff/`, `product-metrics/`, `model-serving/`, `system-verification/src/vectra_verification/clients/oidc.py`, `identity-edge/jobs/`
- `revisiones/U00-T04/` y `bitacoras/U00-T04.md` (el arreglo anterior de la misma librería, y cómo se probó)

---

## Criterios de aceptación

- [ ] **CA-1** — Con un JWKS que trae una llave `RS256`/`sig` y una `RSA-OAEP`/`enc`, un token firmado con la primera se verifica; la caché queda válida.
  ```bash
  cd vectra-risk && uv run pytest contracts -q -p no:cacheprovider -k "jwks"
  ```
  Esperado: pasa, con pruebas nuevas; contra `main`, la nueva falla con `DependencyUnavailable` (rojo registrado). Comprueba con `--collect-only` que el filtro selecciona tus pruebas nuevas; ajusta la ruta si las pruebas de `vectra_common` viven en otro sitio y dilo.

- [ ] **CA-2** — Negativos: un `kid` de la llave `enc` no verifica nada (401); un JWKS sin ninguna llave de firma legible sigue siendo error del refresco (503 sin caché); un token firmado con un algoritmo no aceptado sigue rechazado.
  ```bash
  cd vectra-risk && uv run pytest contracts -q -p no:cacheprovider -k "jwks or authn"
  ```
  Esperado: pasa.

- [ ] **CA-3** — El barrido: ningún otro lector de JWKS de producto cae con una llave de cifrado.
  ```bash
  cd vectra-risk && grep -rn -E 'PyJWK|PyJWKSet|PyJWKClient' --include='*.py' . | grep -v -E '/tests/|\.venv' 
  ```
  Esperado: la bitácora explica cada aparición (cubierta, arreglada, o por qué no aplica), con su prueba si se arregló.

- [ ] **CA-4** — U0 y los consumidores siguen en verde.
  ```bash
  cd vectra-risk && make -C contracts check && for u in decision-registry governance scoring-explainability case-management bias-monitoring product-metrics; do uv run pytest $u/tests/unit -q -p no:cacheprovider -x 2>&1 | tail -1; done
  ```
  Esperado: `check` rc 0 y cada unidad «passed». (Solo pruebas unitarias de las unidades: sin contenedores.) Ajusta el nombre del objetivo de U0 si es otro y dilo.

---

## Plan de pruebas

Las de CA-1 y CA-2, con el JWKS de la forma real de Keycloak. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`**, ni contra `vectra.localtest.me`.
- No descargues imágenes de contenedor nuevas. La máquina tiene poca memoria y un clúster de kind completo corriendo: suites pesadas una sola vez.
- `platform/.tools`: si lo necesitas, enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`. No va en el commit.
- En cada criterio, comprueba que el comando ejecuta de verdad tus pruebas nuevas.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u00t05-`.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
