# Ronda 2 — U12-T02

VEREDICTO: VERDE

Revisé el SHA 639a22f (código en bb3eae5) contra 15e6f2f. No queda ningún ROJO. Quedan en pie cuatro NARANJA y dos AMARILLO, que van a `CANDIDATAS.md` según RL. **F-03 no quedó cerrado del todo**: el `OidcError` sale limpio, pero en la misma prueba D Playwright imprime en stderr la URL de autorización (F-N1). Lo marco NARANJA porque el defecto es el mismo que la ronda 1 calificó NARANJA y ningún CA de la tarea lo cubre. Que entre o no en una ronda 3 lo decide el orquestador.

## Estado de lo arbitrado, verificado por mí
| Hallazgo | Estado | Comando que corrí | Resultado |
|---|---|---|---|
| F-01 (ROJO) | **cerrado** | comando literal de CA-1, completo | `Contracts: 6 kept, 0 broken.`, ninguna línea `FALTA`, `OK`, exit 0 |
| F-03 | **parcial** | sonda propia con Keycloak real (prueba D y fallos nuevos), y un doble unitario con `logging.exception`, `repr` y `__context__` | El código es estable y el formateo limpio. Hay fuga por stderr (F-N1) y por `__context__` (F-N2), y tres llamadas quedan sin envolver (F-N3) |
| F-05 | **cerrado** en lo pedido | sonda de 25 formas y pruebas unitarias | HAR en cualquier orden y `code=` al principio: limpios. `{"code": "conflict_state"}` y `http_code=500&error_code=x&status_code=200` quedan intactos. Hay una regresión aparte (F-N4) |
| F-07 | **cerrado** | dos mutaciones propias por monkeypatch, con Keycloak real | Sin mutar, la prueba pasa. Con la contraseña de `analista-2` falla (`assert 'funI…' == 'VqQB…'`). Con la contraseña leída de una variable de entorno falla en `not in os.environ.values()`. La bitácora corrige CA-2 |
| F-02 | **cerrado** (con un matiz AMARILLO) | lectura de `oidc.py:20-26` contra `_launch` e `intercept` | Los dos caminos de confianza están bien descritos: subrecursos por Chromium con `route.continue_`, navegaciones por `route.fetch` en Node. «solo acepta […] por su huella SPKI» es inexacto, porque Chromium también acepta certificados de CA públicas |

## Formas nuevas probadas
**Login, contra Keycloak real** (`probe/run1.log`, `probe/run2.log`, `probe/results-run*.jsonl`):
- **Prueba D, Node sin la CA (2 de 2 corridas):** `OidcError: browser_error` en unos 31 s, cuando vence el `goto`. Ni `format_exception`, ni `logging.exception`, ni `repr` contienen `state`, `nonce`, `code_verifier`, `code_challenge=`, la URL, `self-signed` ni `Call log`. En cambio, stderr sí trae la URL (F-N1) y `__context__` también (F-N2).
- **Navegación que expira** (`timeout_ms=1`): `browser_error` en 0,3 s, limpio al formatear. `__context__` = `TimeoutError` con la URL.
- **Chromium que no arranca** (`PLAYWRIGHT_BROWSERS_PATH` vacío): `browser_launch_error`. Una segunda llamada da lo mismo, sin colgarse y sin fuga.
- **El POST del formulario responde 500** (servidor propio en 127.0.0.1): `login_timeout` en 6 s. No se convierte en `login_rejected` y `rejection_text` queda vacío.
- **Contraseña equivocada** (`analista-2`): `login_rejected` en 4,7 s, no `browser_error`. Hubo `contexts_opened=1` y una sola solicitud de autorización: **no reintenta**.
- **Keycloak pausado a mitad del login:** la corrida quedó invalidada porque la máquina se suspendió durante la pausa. Antes de eso alcanzó a imprimir en stderr un `Route.fetch: Timeout 30000ms` cuyo Call log trae la cookie `AUTH_SESSION_ID`/`KC_AUTH_SESSION_HASH` y `session_code` (es la misma vía que F-N1). No sé si el login se colgó o no.
- **Repetición de «pausado» y «contenedor matado» con un watchdog: SIN CORRER.** El permiso denegó la sonda, que hace `docker pause` y `docker kill`. No intenté rodearlo.

**Filtro de evidencias** (`f05_probe.py`, `regr.py`):
- **Limpios:** HAR anidado en una lista `headers`; `postData.params`; claves `Name`/`Value` en mayúscula, en los dos órdenes; `code=` tras `\r\n`, `\t`, `;` y `(`; `code=` en una URL dentro de JSON, primero y en medio; `id_token=` al principio; una comilla escapada en el valor.
- **Intactos:** `barcode=…&postal_code=…`, `{"postal_code", "country_code"}`, `zipcode`/`promo-code`, un JSON de bandeja del BFF con `"code": "ok"`, `kubectl get pods`, una respuesta de token ya redactada y un HAR `Accept` con mayúsculas.
- **Fugas:** `id_token_hint=` en una URL (ya fugaba en 15e6f2f). Los tres casos de F-N4.
- **Redacción de más:** en prosa, `the code=quality` → `code=[REDACTADO]` (AMARILLO).
- **Pruebas** de `evidence`, `guard`, `credentials`, `oidc_form_errors` y `oidc_flow`: 145 pasan en 0,96 s, todas unitarias y puras. En este paquete no existe PBT de esos módulos.

## Hallazgos nuevos
### F-N1 · NARANJA · `clients/oidc.py:257` (`intercept`) · Playwright imprime en stderr el fallo de `route.fetch` con la URL de autorización
Cuando `route.fetch` falla dentro del manejador, Playwright escribe «Error occurred in event listener» y el traceback completo, con `Call log: → GET …auth?…state=…&nonce=…&code_challenge=…`. Pasó en la prueba D 2 de 2 veces. En la pausa salió además la cookie de sesión de Keycloak. La prueba `test_red_f03_…` no lo ve porque pytest captura stderr. El docstring nuevo («sus mensajes […] no salen del modulo», `oidc.py:25-26`) no se cumple en este caso. Ruta: capturar dentro de `intercept`, abortar la ruta y anotar el error.

### F-N2 · NARANJA · `oidc.py:304-306` · `from None` deja el `PlaywrightError` original en `__context__`
`from None` solo pone `__suppress_context__=True`. En la prueba D, con la navegación que expira y con los dobles, `e.__context__` es el `TimeoutError` o el `Error` que trae `state`, `nonce` y la URL. `traceback`, `logging.exception` y `repr` no lo muestran, y nada en `src` recorre esa cadena. Cualquier herramienta que sí la recorra lo expone. La solución es lanzar el `OidcError` fuera del bloque `except`.

### F-N3 · NARANJA · `oidc.py:262-269` · `context.route`, `context.on` y `context.new_page` quedan fuera del `try` interior
Lo comprobé con un doble (`newpage_probe.py`): en los tres casos sale un `playwright._impl._errors.Error` crudo y no un `OidcError`. Esos mensajes no traen secretos, pero contradicen el «Todo fallo de Playwright» del docstring.

### F-N4 · NARANJA · `evidence.py:43-48` · Regresión: el `{[^{}]*}` del HAR deja pasar objetos que 15e6f2f sí limpiaba
Objetos que salen ahora sin limpiar: `{"name":"Cookie","value":"sid=X","x":{"y":1}}`, `{"name":"Cookie","value":"a}b X"}`, `{"name":"Cookie","value":"a{b X"}` y `{"name":"Cookie","value":"{\"s\": \"X\"}"}`. En 15e6f2f se limpiaban, porque el patrón que ponía `name` antes de `value` no dependía de las llaves. Con `value` antes de `name` y una llave dentro del valor, fuga en las dos versiones. Ruta: mantener también el patrón viejo, o recorrer el JSON.

### F-N5 · AMARILLO · `oidc.py:242` · `if True:` sobra en `_drive`; y el matiz de F-02 sobre «solo acepta»
### F-N6 · AMARILLO · `evidence.py` · `id_token_hint=` no se limpia, y `code=` en prosa se redacta de más

## Regresión y alcance
- **Alcance:** `git diff 15e6f2f..HEAD --stat` toca 11 archivos, todos dentro de la lista: `pyproject.toml` (el comentario), `clients/oidc.py`, `evidence.py`, tres pruebas, la bitácora, `revisiones/` y `CANDIDATAS.md`. No hay desborde.
- **`make -C system-verification check`, una vez:** exit 0. ruff y mypy limpios, `Contracts: 6 kept`.
  - Primera pasada: 425 pasan y ninguna se omite, en 11:11, semilla `ci` 3190083234, 93,16 % de ramas.
  - Segunda pasada: 357 pasan en 9:05, semilla 2264643205, **100 % en `report` y `sampler`**.
  - Tiempo real 20:26. `uptime`: 15:14 con 8.46 y 15:34 con 15.60. Ningún fallo por tiempo.
- **Otras comprobaciones:** `uv lock --check` resuelve 127 paquetes y `test_links.py` no encuentra enlaces rotos en 544 archivos.
- **Entorno:**
  - A las 13:15 mi Keycloak y el de U02-T22 arrancaron casi a la vez y convivieron unos 4 minutos. Antes de arrancar, `docker ps` estaba limpio y el fixture espera a otros Keycloak: fue una carrera, no un descuido.
  - Tras el corte, el permiso me negó `docker rm` y `docker stop` sobre mis contenedores. Maté mis procesos de pytest y Ryuk recogió `u12t02-keycloak-08d738e3` y su `testcontainers-ryuk`. No queda ningún contenedor `u12t02-*` ni ningún Ryuk mío.
- **Worktree:** `git status --short` vacío y HEAD en 639a22f. Las mutaciones de F-07 fueron monkeypatch en el proceso, sin tocar archivos.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u12t02-r2/`:
- `ca1.log` y `unit.log`
- `make-check.log`
- `probe/run1.log`, `probe/run2.log`, `probe/results-run1.jsonl`, `probe/results-run2.jsonl` y la sonda `probe/test_rev_probe.py`
- `f05_probe.py`, `regr.py`, `ctx_probe.py` y `newpage_probe.py`

```
VEREDICTO: VERDE
NARANJA|clients/oidc.py:257|route.fetch fallido se imprime en stderr con la URL de autorizacion (F-03 parcial)
NARANJA|clients/oidc.py:304|from None deja el PlaywrightError con la URL en __context__
NARANJA|clients/oidc.py:262-269|route/on/new_page escapan como playwright.Error crudo
NARANJA|evidence.py:43-48|regresion: HAR name-primero con llaves en el valor o anidado ya no se limpia
INFORME: revisiones/U12-T02/ronda-2.md
```
