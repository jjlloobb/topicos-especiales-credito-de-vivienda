# Ronda 1 — U02-T22

VEREDICTO: VERDE

No hay ningún ROJO. Los 12 criterios se cumplen en mis propias corridas. Encontré un NARANJA y varios AMARILLO; según RL-2 no bloquean y van a `CANDIDATAS.md`. También hay tres tareas candidatas de fondo, fuera de alcance.

## Medido contra Keycloak real
Imagen `quay.io/keycloak/keycloak:26.8.1@sha256:3f3c5f8e…`, leída del `FROM` del Dockerfile. config-cli `adorsys/keycloak-config-cli@sha256:0955d98c…`, leída de `values/kind.yaml`. Las variables `IMPORT_*` salen de `common.yaml` y coinciden con las del Job; el YAML va sin editar. Todo el tráfico va a `https://127.0.0.1:<puerto aleatorio>`: el `HostGuard` está en el cliente de administración y en el de login, y el puerto se publica solo en 127.0.0.1. El grep de CA-9 no da salida.
- **Rojo sobre la base** (los tres realms restaurados con `git checkout 23e8d73 -- …/realm`; `uptime` con carga 10,9 → 11,2): 11 fallan y 1 pasa, la de fuerza bruta. El caso de las ejecuciones da `11 de 26 … sin ella: 15`. El login devuelve la página «Unexpected error when handling authentication request to identity provider.» y el log `KC-SERVICES0013 … NullPointerException … "loaConditionConfig" is null`. La unitaria cae con 10 fallos y nombra `loa-mfa`, `amr-otp` y `amr-hwk` con sus ejecuciones y a los usuarios atrapados (los 10 sintéticos y `break-glass`). Después restauré con `git checkout HEAD`.
- **Verde**: `make -C identity-edge integration` da 12 passed en 3 min 53 s (carga 10,9 → 15,5). Lo corrí una vez y pasó una de una.
- **Migración, con mi propio sondeo** (`scripts/probe.py`): importé el realm viejo (fixture idéntico byte a byte a `23e8d73`, comprobado con `cmp`), que deja 11 de 26, y encima el corregido, que deja **26 de 26 con los valores del YAML**. Quedan **0 huérfanas** `loa-mfa`, `amr-otp` y `amr-hwk`, y `VERIFY_PROFILE` queda en `(enabled=False, default=False, 100)`. Los 10 usuarios que ya existían conservan su id y su credencial de contraseña, no tienen `requiredActions`, siguen `enabled` y tienen `numFailures 0`. **Los 10 entran.**

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Rojo, integración | `make integration` con los realms de la base | falla (11/12) con el texto y la línea del log esperados |
| 2 | Rojo, unitaria | `pytest test_realm_importable.py` con los realms de la base | 10 failed, nombra los alias y los usuarios |
| 3 | Verde unitaria y mutaciones | importable + files + lint + diff + identity_jobs; `-k mutation` | 1037 passed; 9 passed |
| 4 | Cambio mínimo | script de CA-4 contra `23e8d73` | `compartidos: 0 citados: 26 declarados: 26 iguales: True` ×3, sin AssertionError; los valores por ejecución son idénticos a la base en las 26 de los tres entornos |
| 5 | Login por rol | integración y sondeo con los **10** sintéticos | ana/ing/cro/cum: `acr=mfa`, `amr=[pwd,otp]`, `roles=[rol]`, `aud` con `console-bff`, sin PII. `operacion`: `acr=mfa`, `roles` ausente |
| 6 | 26/26 y `VERIFY_PROFILE` | integración y sondeo por la API | pasa |
| 7 | Step-up, TOTP reusado, fuerza bruta | integración y sondeo | pasa. Bloqueo en el fallo 5, no antes; `failedLoginNotBefore = lastFailure + 60 s` exacto; se levanta a los 60 s |
| 8 | Idempotencia y migración | integración y sondeo | pasa (ver más abajo) |
| 9 | Nada en Docker, imágenes intactas | grep; `docker ps -a`; `image inspect` | sin salida; `0`; `presente` ×2 |
| 10 | Renders | `make check-keycloak-rendered check-jobs-rendered` | rc 0. Con un alias mutado en el realm, los dos dan rc 2. Las 4 ConfigMaps son idénticas byte a byte a su realm. `keycloak.yaml` no cambia. El grep de nombres no da salida |
| 11 | Documento y candidatas | los tres grep | 5 secciones; `0` y `0` secretos; 9 menciones en CANDIDATAS y 1 en paso-16 |
| 12 | RL-4 | `make -C identity-edge check` (TMPDIR por omisión) | rc 0, 38 min 10 s (carga 17,5 → 9,8), 2799 passed, `collect-integration` colecta 12. `test_links`: 558 archivos sin enlaces rotos. `test_token_issuer`: 69 passed. Traceability `--all`: rc 1, solo por líneas de U12 |

No corrí `make -C platform check-local`: la orden no lo incluía en el punto 7.

**Guarda rápida.** Las 4 clases de mutación las apliqué sobre los YAML reales y las deshice con `git checkout`. Las cuatro caen y el fallo nombra el realm (en el id de la prueba o en el mensaje) y la ejecución:
- M1, prod: `alias loa-mfa-cumplimiento citado por 2 ejecuciones: vectra-mfa-cro#10, vectra-mfa-cumplimiento#10`.
- M2, staging: `cita a amr-otp-nadie … (vectra-mfa-analista factor#10)`.
- M3a, kind: `VERIFY_PROFILE` quitada, y M3b, prod: `enabled: true`. Las dos dan «usuario … atrapado» y «requiredActions de X difiere».
- M4a y M4b: el flujo de staging y la configuración de prod distintos de kind.

**`collect-integration`.** Tarda 4,7 s y `docker events` no registra ningún evento de contenedor durante la colecta. Con un error de sintaxis da Error 2; con un import roto en `realm_stack` da Error 4.

**Idempotencia.** Las dos lecturas dan 26/26. En `partial-export`, `authenticationFlows`, `authenticatorConfig` y `requiredActions` quedan idénticos. Hay 30 configuraciones = 26 + 4 predefinidas (`browser-conditional-credential`, `create unique user config`, `first-broker-login-conditional-credential`, `review profile config`), y las mismas 4 aparecen tras una importación limpia. Lo que el log dice y lo que no:
- La segunda pasada tiene 7 líneas, ninguna de actualización, y tarda 1,67 s frente a los 29,2 s de la primera.
- El realm guarda el atributo `de.adorsys.keycloak.config.import-checksum-default`.
- Ninguna línea dice «se omitió por suma de control». Es compatible con que la omitiera, pero no queda afirmado.

**H12.** Confirmo lo que dice el codificador: config-cli no borra las acciones que Git no declara. Tras importar siguen las 14 de Keycloak, incluidas `UPDATE_PROFILE` y `VERIFY_EMAIL` activas, `delete_credential`, `idp_link` y otras que Git no declara. Sin declararla, `VERIFY_PROFILE` queda `enabled`. Desactivarla solo cambia esa acción: `UPDATE_PASSWORD` (57), `CONFIGURE_TOTP` y `webauthn-register` siguen activas.

**`operacion` sin `roles` y `name`.** No los causa esta tarea. `scopeMappings` y los usuarios no cambian (lo prueba la igualdad de núcleo de CA-4). El claim `name` del ID token sale **ausente** (`None`), no vacío.

## Hallazgos
### F-01 · NARANJA · `identity-edge/docs/realm-importacion.md:12,23,29` y `CANDIDATAS.md` (líneas nuevas) · Dos afirmaciones de la migración que lo medido desmiente o deja incompletas
(a) El documento dice «Cada login fallido por (a) cuenta para la fuerza bruta», y la candidata de U12 dice «cada fallo contó». Medido con el realm viejo: 3 logins de `cro-1` con NPE dejan `numFailures: 0`, y los `LOGIN_ERROR` llevan `userId="null"`. El NPE **no** cuenta para el bloqueo. El desbloqueo del paso 3 sigue siendo una precaución válida, porque pudo haber contraseñas mal tecleadas, pero no por esa razón.
(b) Falta un efecto de la migración. config-cli registra 10 veces `Password policy violation … Password was NOT updated` (por `passwordHistory(5)`) y **añade una segunda credencial OTP** a cada usuario: `cro-1` pasa de `[password, otp]` a `[password, otp, otp]`. El login sigue funcionando, porque es la misma semilla. Pero el operador verá el WARNING, y si rota la semilla en ESO la vieja sigue válida. Esto también responde a la mitad de la candidata de U02-T05 que el diff marca «no se midió».

Evidencia: `scratchpad/rev-u02t22/probe/probe2.log` y `cli-migracion.log`.

### F-02 · AMARILLO · `tests/integration/test_realm_import.py:111` · El step-up no prueba la reautenticación
`ingeniero-2` no tiene sesión SSO previa, así que `auth_time ≤ 900 s` se cumple siempre. Faltaría un login previo y comprobar que `auth_time` avanza.

### F-03 · AMARILLO · `test_realm_import.py:142` · El efímero de la fuerza bruta nunca podría entrar
Ni siquiera con la contraseña correcta (ver la candidata 1). El bloqueo se lee bien por la API, pero la prueba no distingue entre «bloqueado» y «falla igual».

### F-04 · AMARILLO · bitácora · Imprecisiones menores
- Traceability `--all` da hoy 6 líneas, no 4: además de las NFR salen `INF-U12-04/05`. No son de esta tarea: ninguna línea que el diff quita contiene `U12`, `INF-` ni `NFR-`, y añadir texto no puede quitar trazabilidad.
- «claim `name` vacío» es en realidad «ausente».

## Tareas candidatas (defectos reales fuera de alcance)
1. **`analista` sin factor no puede entrar** (BR-U2-03 dice que solo pide MFA si ya tiene el factor). Un efímero `analista` con solo contraseña obtiene HTTP 400, «Invalid username or password.» y `AuthenticationFlowException`. Lo mismo pasa con `cro` y `operacion` sin factor. Es la estructura del subflujo (`conditional-user-configured` sobre un subflujo), que está fuera de alcance y que esta tarea no toca. Los sintéticos tienen todos OTP, así que la demo no se ve afectada (`probe3.log`).
2. **`realm-drift` contra un Keycloak real da deriva falsa siempre.** `KeycloakReader._flows` solo ve los flujos de primer nivel (`GET /authentication/flows`), así que todo subflujo y toda `authenticatorConfig` salen `missing-in-keycloak`. Son 43 diferencias con el realm de la base y 58 con el corregido, igual en la importación limpia que en la migrada (sin ninguna diferencia propia de la migración). Los alias nuevos no crean una clase nueva de deriva, solo 15 entradas más de la misma (`probe4b.log`).
3. config-cli duplica la credencial OTP en cada reimportación que cambie el realm (F-01 b), y no aplica contraseñas rotadas mientras rija `passwordHistory`.

## Rutas de transcripciones largas
Todas bajo `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u02t22/`:
- `verde-1.log`, `rojo-base.log`, `mutaciones.log`, `collect.log`, `renders-unit.log`, `static.log`, `trace.log`, `check.log`
- `probe/probe.log`, `probe/probe2.log`, `probe/probe3.log`, `probe/probe4b.log`, `probe/cli-*.log`
- los scripts de sondeo, en `scripts/`

**Estado final:** `git status --short` vacío y HEAD en 391b9bb. No queda ningún contenedor `u02t22` ni de config-cli, y las dos imágenes siguen presentes. No toqué contenedores ajenos.

```
VEREDICTO: VERDE
NARANJA|identity-edge/docs/realm-importacion.md:12,23,29|El fallo por NPE no cuenta para la fuerza bruta y la migración duplica la OTP y no reaplica contraseñas: el documento lo omite o lo contradice
AMARILLO|identity-edge/tests/integration/test_realm_import.py:111|El step-up no prueba la reautenticación sobre una sesión previa
AMARILLO|identity-edge/tests/integration/test_realm_import.py:142|El efímero de la fuerza bruta no podría entrar ni con la contraseña correcta
AMARILLO|vectra-risk/bitacoras/U02-T22.md|Traceability da 6 líneas de U12, no 4; «name vacío» es «ausente»
INFORME: revisiones/U02-T22/ronda-1.md
```
