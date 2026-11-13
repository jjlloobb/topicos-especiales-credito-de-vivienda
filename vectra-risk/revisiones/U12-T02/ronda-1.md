# Ronda 1 — U12-T02

VEREDICTO: NO-VERDE (un solo ROJO, F-01: un comentario en `pyproject.toml` hace fallar el comando literal de CA-1. Se arregla cambiando una línea. Todo lo demás sustantivo pasa.)

Base: rama `tarea/U12-T02` en 15e6f2f, diff medido con `065c284..HEAD`. El blob de la tarea es `facd438c…`, el pedido. Al terminar, `git status --short` sale vacío y HEAD sigue en 15e6f2f. Docker no tiene contenedores `keycloak`, `config-cli` ni `u12t02-*`, y `rev-u10t05-spa` sigue en marcha sin que lo tocara. No me conecté al kind ni a `vectra.localtest.me`: leí `keycloak_tc.py` y `conftest.py` antes de correr nada, y todo va a `127.0.0.1:<puerto aleatorio>`. Logs en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev/logs/`.

## Realm de kind (prioridad 1): los dos defectos se reproducen con una configuración fiel a kind

**Fidelidad.** Comparé la prueba con lo que usa kind:
- Keycloak usa el mismo digest, `quay.io/keycloak/keycloak:26.8.1@sha256:3f3c5f8e…`, el de la línea `FROM` del Dockerfile.
- config-cli usa el mismo digest, `sha256:0955d98c…`, el de `values/kind.yaml`. La etiqueta de la imagen es **`6.5.1-26.5.5`**: un config-cli hecho para Keycloak 26.5.5 aplicado sobre 26.8.1. Es lo mismo que hace kind.
- El YAML es el mismo y sin editar, con las mismas variables `IMPORT_VARSUBSTITUTION_*`, `KEYCLOAK_SSLVERIFY` y `JAVA_OPTS`. Las comprobé contra `values/common.yaml`, líneas 448 a 462.
- La única diferencia: kind usa la imagen construida (`--db=postgres --cache=ispn`, `start --optimized`), y la prueba usa la imagen base con `start` y base embebida. No afecta a ninguno de los dos defectos: uno es de enlace de la importación y el otro del perfil de usuario.

**Reproducción.** Usé un script propio, `scratchpad/rev/scripts/repro_realm.py`. Arranca el `keycloak_stack()` de la prueba con `repair_shared_authenticator_configs` y `complete_user_profiles` anuladas, y luego reaplica cada reparación por separado. Tardó 1 min 41 s, con carga entre 2.61 y 4.51.
- **(a) Confirmado.** Por la API de administración, en `vectra-browser` solo el primer subflujo tiene `authenticationConfig`. Las 15 ejecuciones siguientes (`conditional-level-of-authentication`, `auth-otp-form` y `webauthn-authenticator`) salen con `False`. El login de `analista-1` falla así:
  - en el formulario: «Unexpected error when handling authentication request to identity provider.»;
  - en el log de Keycloak: `KC-SERVICES0013: Failed authentication: java.lang.NullPointerException: Cannot invoke "org.keycloak.models.AuthenticatorConfigModel.getConfig()" because "loaConditionConfig" is null`;
  - y además `type="LOGIN_ERROR" … error="invalid_user_credentials"`. **Ese fallo cuenta para la fuerza bruta**: en kind, cinco intentos bloquean al usuario para siempre.
- **(b) Confirmado.** Con solo los alias reparados (15 ejecuciones), el login de `analista-2` termina en la página `Please specify this field.` con los campos `email:text,firstName:text,lastName:text`. La causa:
  - el usuario tiene `email`, `firstName` y `lastName` en `None`;
  - el perfil exige `email`, `firstName` y `lastName` para el rol `user`;
  - `VERIFY_PROFILE` está activa, y config-cli no la quita.
- Con las dos reparaciones (12 perfiles completados), `ingeniero-1` entra con `acr=mfa` y el rol `ingeniero_riesgo`.

**Severidad para U2:** ROJO para las demos D1 a D4. Con el realm actual nadie puede iniciar sesión en kind, y cada intento acerca el bloqueo permanente. Está fuera del alcance de U12-T02 y ya está en `CANDIDATAS.md` (líneas 644 y 645). Recomiendo una tarea de U2 antes de cualquier ensayo en kind. No lo comprobé en el kind real, porque estaba prohibido.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | El comando literal de CA-1 | `6 kept, 0 broken`, sin `FALTA`, pero **no imprime `OK`** (exit=1) → **falla** (F-01) |
| 2 | Arranque de Chromium + grep | `156.0.8078.4`, `limpio=0`: pasa |
| 3 | `test_oidc_headless.py` (dentro de `make check`) | 12 pasadas, contra Keycloak real en 127.0.0.1: pasa |
| 4 | `test_oidc_flow.py` | 20 pasadas. Mutaciones mías: no validar `nonce`, aceptar `acr=pwd` y reintentar tras un rechazo. **Las 3 mueren.** Pasa |
| 5 | `test_tokens_not_leaked.py` + grep | `sin_escritura=0`: pasa |
| 6 | `evidence`/`guard`/`credentials` (en `make check`) | pasa |
| 7, 8 | `test_clients.py` | 15 pasadas. Mutación `pod/`→`svc/`: mueren 2 pruebas. Pasa |
| 9 | Verbos + `test_k8s_read.py` | Pasa. Agregar `["kubectl","delete",…]` a `k8s_read.py` hace fallar `test_real_files_have_no_findings`, que nombra el archivo. El `--stat` sale vacío |
| 10–14, 16, 17 | En `make check` | Pasan. CA-11 y CA-14 corren contra las apps reales en proceso: `vectra_case.app` sobre PostgreSQL de Testcontainers y `console_bff.app.build` con los dobles de U10 |
| 12 | Mutación «por lotes» en `simulator.py` | Mueren `[30-300]` y `[10-100]` |
| 15 | PBT-U12-03 con perfil `ci` y semillas 1, 42, 20261113, 987654321 y 3141592653 | 7/7 pasadas en cada una (14 a 21 s). Mutaciones mías: `se_aparta` con el mismo resultado, justificación de 19 caracteres y más de 20 factores. Mueren todas |
| 18, 20 | `make -C system-verification check` | rc=0, **11 min 18 s** (cargas 4.27 → 3.62). Detalle abajo |
| 19 | Trazabilidad | `--unit`: solo INF-U12-04/05 y NFR-U12-31/42, dentro de lo permitido. `--all` en la rama, sin comparar con la base (ver nota) |
| 21 | `docker ps -a` | `restantes=1`: no queda ninguno |
| 22 | `uv lock --check` + diff | Lock en 0; `fuera=0` solo por `logic.md`, que la enmienda 3 permite. `uv.lock` solo gana playwright, pyarrow y pyjwt[crypto], sin versiones nuevas. `identity-edge/` sin cambios |
| 23 | Plan | Los Pasos 5 y 6 en `[x] (U12-T02)` con la nota de rt1/rt4. Solo cambian esas dos casillas |
| 24 | `test_links.py` | 541 archivos Markdown sin enlaces rotos |

Detalle de `make -C system-verification check`:
- ruff, mypy e import-linter: `6 kept`.
- Primera pasada: 408 pasadas, 0 omitidas, 92,35 % de ramas, semilla 166419279.
- Segunda pasada: 341 pasadas, 100 % en `report` y `sampler`, semilla 1225334034.

Nota sobre CA-19: no corrí `--all` en la base, porque habría tenido que copiar el repositorio. Por construcción no puede haber fallos nuevos en otras unidades: el diff solo **añade** texto en `system-verification/` y en docs, y el script busca citas, así que solo podría quitar fallos.

## Hallazgos
### F-01 · ROJO · system-verification/pyproject.toml:7 · CA-1 no imprime `OK`
La guarda `! grep -rqE "vectra[-_]common" pyproject.toml src` encuentra el comentario `` `jwt` directo, no por `vectra_common` ``, que añade este diff (en 065c284 no está). La salida que corrí: `Contracts: 6 kept, 0 broken.`, sin `OK`, `exit=1`. En sustancia no hay dependencia (el contrato «ningun modulo importa vectra_common» queda KEPT), pero el criterio no se cumple tal como está escrito. La bitácora pega CA-1 sin la línea del bucle ni el `OK`. Arreglo: reescribir el comentario sin ese nombre.

### F-02 · NARANJA (ya es candidata) · clients/oidc.py:20-21, 161, 219 · la confianza TLS del formulario no es la de P-2
Las navegaciones, y por tanto el POST con la contraseña y el TOTP, las hace `route.fetch` en Node. Node confía en sus CA públicas más `NODE_EXTRA_CA_CERTS`. La huella SPKI de Chromium solo protege los subrecursos. No se acepta cualquier certificado y no hay `ignore_https_errors`: lo probé dejando a Node sin la CA (prueba D) y falló con `self-signed certificate in certificate chain`. Pero el docstring (líneas 20 y 21) afirma «Chromium solo confía en el certificado del servidor del entorno», y eso no describe lo que pasa con las credenciales.

### F-03 · NARANJA · clients/oidc.py:271-275 · un fallo de TLS escapa como `playwright.Error` y tapa el `OidcError`
En la misma prueba D, `context.close()` del `finally` relanza `BrowserContext.close: Route.fetch: self-signed certificate…`. No es un `OidcError` con código estable, y el «Call log» trae la URL de autorización con `state`, `nonce` y `code_challenge`. El propio módulo trata el `nonce` como `Secret`.

### F-04 · NARANJA · driver.py:189-196 · el conductor no espera a que los casos lleguen a `listo`
La ingesta devuelve `en_evaluacion` (`intake.py:129`), y `_ready` lista la bandeja una sola vez, justo después del simulador. En kind, los últimos casos de los 2 000 de D4 pueden quedar en `not_ready` y sin decidir. Los dobles de `test_decisions_volume` los ponen en `listo` al instante, así que esto no se ve en las pruebas. El diseño (§2.2) tampoco pide esperar, así que propongo una candidata para U12-T03 o T04.

### F-05 · AMARILLO · evidence.py:42, 45 · huecos del filtro F-08
- Un objeto HAR con el orden `{"value":…, "name":"Cookie"}` sale sin limpiar.
- Un formulario que empieza por `code=SECRET&grant_type=…` no se limpia: el patrón exige `[?&#]` delante.
- Lo que sí funciona: tuplas, tuplas en bytes, HAR en orden normal y `?code=`/`&code=`. `{"code":"conflict_state"}` queda intacto.

Salida en `scratchpad/rev/logs/probe-barriers.out`.

### F-06 · AMARILLO · credentials.py:31, 60 · la lista de hosts de la bóveda es global, no por entorno
Staging con `http://vault.vault.svc:8200` se acepta. Lo que comprobé de F-04 y F-09 está bien:
- un `Environment` armado a mano se rechaza en `Credentials`, `check_section` y `check_token_issuer`;
- `127.0.0.1.evil.com` y `localhost@vault.prod` se rechazan;
- `root` en kind queda exento, pero `rootABCDEFGH1234`, `s.root`, `ROOT`, `root ` y `root` en staging siguen protegidos, igual que `hvs.…` en kind.

F-07 también está bien: una llave completa, una llave en JSON escapado y una sola línea del cuerpo siguen detectándose. La armadura sola y un certificado público pasan.

### F-07 · AMARILLO · pruebas débiles y evidencia vieja
- `test_oidc_headless.py:280`: la aserción con `or` es siempre verdadera.
- `test_driver_mix.py:128`: `max_examples=20` en la prueba de convergencia.
- `test_simulator.py:40`: la ventana se recorta en `1e-6`.
- `bitacoras/U12-T02.md:230`: el CA-2 pegado dice `limpio=1`; hoy da 0.
- `make check` tarda 11 min 18 s, por encima de los 10 esperados y por debajo del tope de 15.

El resto de lo que pedías está verificado:
- Las 20 filas con `default` que dan 422 son solo la prueba roja. El simulador quita `default` y `synthetic_id` (`simulator.py:84`), así que no afecta a D4 ni a D2.
- Lo de staging es coherente con BR-U12-06: 100 por omisión y 2 000 explícitos se niegan.

## Tareas candidatas (defectos reales fuera de alcance)
- U2 (urgente): alias de `authenticatorConfig` únicos por ejecución en `realm.kind.yaml`, y perfil de usuario o atributos de los usuarios semilla. Si no, ningún login en kind funciona y cada intento cuenta para el bloqueo.
- U12-T03/T04: esperar o sondear a que los casos lleguen a `listo` antes de conducir (F-04).
- U12-T04: cerrar la confianza en la CA de Node y de Chromium en la imagen (F-02).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev/logs/repro.out`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev/logs/keycloak-repro.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev/logs/make-check.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev/logs/probe-barriers.out`

```
VEREDICTO: NO-VERDE
ROJO|system-verification/pyproject.toml:7 (CA-1)|un comentario con `vectra_common` impide que CA-1 imprima OK
INFORME: revisiones/U12-T02/ronda-1.md
```
