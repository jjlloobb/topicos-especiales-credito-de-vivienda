# Ronda 1 — U02-T14

VEREDICTO: NO-VERDE

Corrí los siete criterios y todos pasan. El veredicto es NO-VERDE porque tres casos e2e no podrían observar su comportamiento en kind: lo prueba el código de Keycloak 26.8.1 y la configuración del repo. La tarea manda parar en ese caso, y no se paró. Además una de las candidatas del codificador dice algo falso, y quedan varios defectos NARANJA. El worktree quedó limpio (`git status --short` vacío). Las mutaciones las hice en una copia dentro del scratchpad.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|
| 1 | `uv sync --frozen && uv run ruff check identity-edge/tests/e2e` | pasa, exit 0 |
| 2 | `env -u VECTRA_E2E_BASE_URL uv run pytest identity-edge/tests/e2e --collect-only -q`, sin ninguna `VECTRA_E2E_*` ni `SYNTH_*` en el entorno | pasa: 25 casos, 0 errores |
| 3 | `uv run pytest identity-edge/tests/unit/test_e2e_inventory.py -q` | pasa, 6 casos. Mutación: renombré `test_auth_admin_is_not_routed` en la copia y falla, como debe |
| 4 | `uv run pytest identity-edge/tests/unit/test_e2e_echo.py -q` | pasa, 37 casos en 31 s |
| 5 | `make -C identity-edge collect-e2e && make -C identity-edge check` | pasa, exit 0: 2457 casos, ninguno omitido. La salida de `test` no lista ningún archivo de `tests/e2e` (0 apariciones después de la orden con `--ignore`). `check-jobs-rendered` pasa con los ConfigMaps regenerados |
| 6 | `make -C platform check-local && uv run pytest contracts/tests -q`, en serie después de CA-5 | pasa: platform 745 casos, exit 0; contratos 502 casos, exit 0 |
| 7 | `realm_lint.py` sobre los 3 realms `&& pytest test_realm_lint test_realm_diff test_bruteforce_model` | pasa, 784 casos. El Makefile no invoca `realm_lint.py`, así que usé la forma de la tarea |

Sin clúster, las e2e fallan con un error explícito y no se saltan: en la copia, con todo el suite y sin variables, salen «2 failed, 23 errors», 0 skipped.

Mutaciones que sí fallan, como deben:
- Modelo: espera LINEAR desplazada en uno, intentos que cuentan durante el bloqueo, `>=` en lugar de `>` para el permanente, un acierto que no reinicia.
- Realms: `MULTIPLE`, el campo ausente y `maxTemporaryLockouts: 3` hacen fallar a la CLI de `realm_lint` con exit 1.
- `realm_exports` con `MULTIPLE` hace fallar `test_realm_diff`.

## Hallazgos

### F-01 · ROJO · `tests/e2e/test_e2e_bruteforce.py`, `test_e2e_a11y.py` · Tres casos que no observarían su comportamiento en kind; se debía parar
Las Notas de la tarea dicen: «un caso del plan no se puede observar con lo que da kind / Keycloak no se comporta como asume el diseño → detente y repórtalo». Son tres casos:

**a) Bloqueo rápido.** Afecta a `test_five_failures_lock_the_user` y a PBT-U2-08.
- Los valores por defecto del realm son `quickLoginCheckMilliSeconds=1000` y `minimumQuickLoginWaitSeconds=60` (`RealmManager.java` 278-280, ref 26.8.1). El realm no fija ninguno de los dos.
- En `DefaultBruteForceProtector.java` 121-127 y 136-142, un fallo con espera ≤ 0 que llega a menos de 1 s del anterior deja al usuario bloqueado 60 s y emite el evento temporal.
- `lock()` (líneas 134-139) lanza los 5 intentos seguidos, cada uno con un `Flow` nuevo y sin pausa. Lo esperable es que el 2.º fallo active el bloqueo rápido, que los fallos 3 a 5 no cuenten y que `assert status["numFailures"] == FAILURE_FACTOR` falle con 2.
- La máquina de PBT-U2-08 tampoco espera entre fallos, y el modelo no contempla este bloqueo.
- El codificador lo vio y lo dejó como candidata en lugar de parar.

**b) El evento del bloqueo no llega a Loki.** Afecta a `test_lockout_event_has_user_id_and_no_username`.
- `sendEvent` termina en `builder.success()` (`DefaultBruteForceProtector.java` 206).
- `JBossLoggingEventListenerProvider.java` 90-92 registra los eventos de éxito con `successLevel`, que por defecto es `debug` (`JBossLoggingEventListenerProviderFactory.java` 56).
- `keycloak/values/*.yaml` no configura `success-level` ni el nivel de log de `org.keycloak.events`. Así el evento `USER_DISABLED_BY_TEMPORARY_LOCKOUT` no se escribe y `loki.wait_for` devuelve vacío.
- El análisis H9 de la bitácora cita `sendEvent` pero no menciona el nivel de log.

**c) `UPDATE_PASSWORD` no está registrado.** Afecta a `test_password_change_page_has_no_serious_accessibility_violations`.
- El realm solo registra `CONFIGURE_TOTP` y `webauthn-register` (`realm.kind.yaml` 297-308).
- Al importar un realm con `requiredActions`, Keycloak no añade las acciones por defecto (`DefaultExportImportManager.java` 366-376).
- Ante una acción sin registrar, Keycloak la ignora con el aviso «did you forget to register it?» (`AuthenticationManager.java` 1472-1479). El login termina sin la página `password-new` y `wait_for_selector` vence.
- Un matiz: el mecanismo real de import es `keycloak-config-cli`. Con su `managed` por defecto el resultado debería ser el mismo, pero eso no lo verifiqué contra su código.

Los tres necesitan una decisión del usuario sobre el realm, la configuración de Keycloak o el diseño, igual que B-1 y H10.

### F-02 · NARANJA · `CANDIDATAS.md` (última entrada), `bitacoras/U02-T14.md` línea 164 · La candidata «contraseña vacía cuenta como fallo» es falsa
- Con contraseña vacía, `badPasswordHandler(..., isEmptyPassword=true)` llama a `context.forceChallenge` (`AbstractUsernameFormAuthenticator.java` 243-244), no a `failureChallenge`.
- `DefaultAuthenticationFlow.java` 558-561 trata `FORCE_CHALLENGE` sin llamar a `logFailure`. Solo `FAILURE_CHALLENGE` (562-566) y `FAILED` (546-548) llegan a la protección de fuerza bruta.
- Así que una contraseña vacía no cuenta como fallo. La entrada debe corregirse o retirarse, y la bitácora también.
- La candidata del bloqueo rápido, en cambio, es correcta: es el caso F-01a.

### F-03 · NARANJA · `test_e2e_authz.py:34` · «`x-vectra-sub` inyectada → sin efecto» no comprueba lo que fija el diseño
La «Verificación» de P-U2-06 (`nfr-design-patterns.md`, línea 83) dice: «un cliente que manda `x-vectra-sub: otro` no cambia su contador». La prueba solo comprueba que esa cabecera no autentica y que no llega al backend. No mira el contador de rate limit de `console`, por ejemplo con 429 a `limit+1` solicitudes llevando valores de `x-vectra-sub` distintos.

### F-04 · NARANJA · `test_e2e_zlast_forwarded.py:31-52` · El contador de `/auth` supone una ventana deslizante
- `envoy-ratelimit` cuenta en ventanas fijas, alineadas al minuto.
- La prueba manda 630 solicitudes a 15 por segundo, unos 42 s. Si cruza el cambio de minuto antes de llegar a 600, no hay 429.
- Eso ocurre cuando el arranque cae después del segundo 20 del minuto, que es más o menos 2 de cada 3 corridas. Hay que alinear el arranque al minuto o subir el ritmo.

### F-05 · NARANJA · `tests/e2e/echo/manifests.yaml`, governance-service · Las sondas HTTP del eco darían 403 en Linkerd
- `platform/network/generated/kind/vectra-app.yaml` 549-563: el `Server` `governance-service-8080` tiene HTTPRoutes, incluida `governance-catch-all` sobre `/` sin `AuthorizationPolicy`.
- `generate.py` 317 lo dice: «En un `Server` con rutas, Linkerd deja de autorizar solo las sondas del kubelet», y flows no declara `_probes` para governance-service.
- Las sondas `httpGet /` del eco darían 403: los pods nunca quedarían Ready y la `livenessProbe` los reiniciaría.
- Pasa las políticas de U1 en estático, pero no la malla de U1.

### F-06 · NARANJA · Clase de literales usados como valores esperados (barrido completo)
- `test_e2e_mfa.py:175`: `MAX_AUTH_AGE = 900`. Ya existe `vectra_contracts.routes.MFA_MAX_AGE`.
- `test_e2e_zlast_forwarded.py:52`: `time.sleep(61)`. La ventana es la `unit: Minute` de `routes.yaml`.
- `test_e2e_zlast_forwarded.py:36`: `pace = 15`, con «200/s» en el comentario.
- `test_e2e_headers.py:143`: `time.sleep(2)`.

La tarea pide que los valores esperados salgan del diseño o del modelo.

### F-07 · AMARILLO · `e2e_echo_checks.structure_problems` · Mutaciones que la comprobación no detecta
En la copia, ninguna comprobación (estructura, Kyverno, Rego ni kubeconform) detecta dos mutaciones:
- un `labelSelector` del `topologySpreadConstraints` con otro nombre;
- un `targetPort` del Service que no existe.

El selector del PDB solo lo detecta Rego.

### F-08 · AMARILLO · PBT-U2-08 · El invariante no mira `numTemporaryLockouts`
El endpoint `attack-detection` devuelve `numTemporaryLockouts`, que es la magnitud central de H10. La invariante compara solo `numFailures` y `disabled`.

### F-09 · AMARILLO · `test_e2e_mfa.py:185` · Comprobación de página débil
`re.search(r"totp|otp")` no identifica la página de configurar el TOTP. Sería mejor buscar el formulario o el campo propio de esa página.

## Arbitrajes del orquestador
- ConfigMaps de `jobs/rendered` regenerados: bien hechos. `check-jobs-rendered` pasa en CA-5.
- Línea «Campos de Keycloak» de BR-U2-05: concuerda con la enmienda H10 y con `realm_lint`.

## Dependencias
- Todas exactas en `pyproject.toml`, y todas anteriores al 2026-10-22, es decir, con dos semanas o más:
  - playwright 1.64.0 (2026-10-13)
  - pytest-playwright 0.10.0 (2026-10-08)
  - pyotp 2.10.0 (2026-06-14)
  - axe-playwright-python 0.1.8 (2026-07-24)
  - httpx 0.28.1
- Las transitivas también: greenlet 3.5.6 (2026-09-14), pyee 14.0.0 (2026-08-13), python-slugify 9.1.3 (2026-10-07) y text-unidecode 1.3 (2019).

## Tareas candidatas (fuera de alcance)
- Sin `UPDATE_PASSWORD` registrado en los realms, una contraseña temporal que fija un administrador (`UserResource.java` 339 y 827) no obligaría a cambiarla. Es un defecto del producto, no solo de la prueba.
- Si se quiere que `AuthDeniedBurst` o la auditoría usen los eventos de éxito, como el bloqueo, Keycloak necesita `success-level` en info.

## Rutas de transcripciones
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/ca5.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/ca6a.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/ca6b.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/ca2.txt
- Fuentes de Keycloak 26.8.1: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/kc/

No tengo Write, así que no escribí el archivo del informe: este mensaje es el informe completo.

```
VEREDICTO: NO-VERDE
ROJO|identity-edge/tests/e2e/test_e2e_bruteforce.py, test_e2e_a11y.py|Tres casos no observables en kind (bloqueo rápido, evento en DEBUG, UPDATE_PASSWORD sin registrar); la condición de parada no se aplicó
NARANJA|CANDIDATAS.md, bitacoras/U02-T14.md:164|La candidata de contraseña vacía es falsa (forceChallenge no llama a logFailure)
NARANJA|identity-edge/tests/e2e/test_e2e_authz.py:34|x-vectra-sub inyectada: no comprueba el contador, como pide P-U2-06
NARANJA|identity-edge/tests/e2e/test_e2e_zlast_forwarded.py:31|Contador de /auth con ventana fija: prueba inestable
NARANJA|identity-edge/tests/e2e/echo/manifests.yaml|Las sondas httpGet del eco de governance-service dan 403 en Linkerd
NARANJA|identity-edge/tests/e2e/test_e2e_mfa.py:175 y otros|Literales como valores esperados (MFA_MAX_AGE, ventanas, ritmo)
INFORME: revisiones/U02-T14/ronda-1.md
```
