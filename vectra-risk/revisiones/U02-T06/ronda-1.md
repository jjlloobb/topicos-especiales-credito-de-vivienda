# Ronda 1 — U02-T06

VEREDICTO: NO-VERDE

Los seis criterios pasan con mi propia ejecución. El alcance está limpio y el worktree queda limpio en `50d97b4`. El veredicto es NO-VERDE por seis hallazgos NARANJA. En cuatro de ellos, mis mutaciones demuestran que las reglas del tema y de la imagen dejan pasar casos reales: 23 de 37 mutaciones siguen vivas. Los otros dos son el Trivy de `supply-chain.yml` (DS-0002 HIGH), que pondrá en rojo el PR, y el `<script>` con prefijo que la prueba no ve.

Contexto: tarea `vectra-risk/tareas/U02-T06-tema-e-imagen-keycloak.md`, hash `b034d158423deb1f751e9a42460685d12f32c11d` (coincide). Worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U02-T06`, rama `tarea/U02-T06`, HEAD `50d97b4`, base `b06bc6f`. Diff: bitácora, `Dockerfile`, cuatro archivos del tema, se borra `themes/vectra/.gitkeep`, y `theme_checks.py`, `test_theme.py` y `test_keycloak_image.py`. No hay nada fuera de alcance. `git status` está vacío antes y después de la revisión.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | hadolint | `platform/.tools/bin/hadolint identity-edge/keycloak/Dockerfile` (v2.15.1) | pasa: rc=0, sin salida |
| 2 | tema | `uv run pytest identity-edge/tests/unit/test_theme.py -q` | pasa: 31 passed en 0,04 s |
| 3 | referencia | `... -q -k reference` | pasa: 7 passed |
| 4 | marca | `... -q -k brand` | pasa: 10 passed |
| 5 | imagen | `uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q` | pasa: 13 passed |
| 6 | regresión | `uv sync --frozen && make -C identity-edge check && make -C platform check-tools` | pasa: rc=0; ruff limpio, 666 passed, kyverno 38/0 y 239/0 |

El tiempo de 0,04 s tiene explicación: son pruebas puras sobre archivos, sin estado externo. Reproduje el rojo en una copia sin `Dockerfile` ni `themes/`. Sale lo mismo que en la bitácora: `7 failed, 12 passed, 12 errors` y `1 error` de colección.

## Hallazgos

### F-01 · NARANJA · identity-edge/tests/strategies/theme_checks.py:150-164 · La regla de URL deja pasar recursos de otro origen
- La excepción de `xmlns` se aplica al valor de la URL en todo el archivo, no a la posición del atributo. Por eso cualquier URL declarada como `xmlns` en cualquier parte queda permitida en el resto del archivo:
  - T03: `<use xmlns:e="https://evil.example/x.svg" href="https://evil.example/x.svg"/>` sigue viva.
  - T05: un comentario CSS `/* xmlns="https://evil…/f.css" */` con `@import url("https://evil…/f.css")` sigue viva.
- La expresión `xmlns(?::\w+)?\s*=` no tiene límite de palabra. T06: `data-notxmlns="https://evil…"` también exime, y la mutación sigue viva.
- X04b: `<use xlink:href="http://www.w3.org/2000/svg"/>` es una URL real que se descargaría, y sigue viva.
- Las URL sin esquema no se detectan:
  - T01: `@import url("//cdn.example.com/x.css")` sigue viva.
  - T02: `background: url(//cdn.example.com/a.png)` sigue viva.
- La nota de la tarea pide que la prueba distinga `xmlns` «de cualquier otra URL», y P-U2-08 exige «sin referencias de otro origen».
- Sí se detectan `url(https://…)` sin comillas (T07) y `<image href=https…>` (T18).

### F-02 · NARANJA · theme_checks.py:152,167-168; test_theme.py:50-51 · «Sin JavaScript propio» se reduce a `<script`
- T09: `<s:script xmlns:s="http://www.w3.org/2000/svg">alert(1)</s:script>` en el SVG sigue viva. Es un elemento `<script>` real, así que incumple CA-2 al pie de la letra.
- También siguen vivas:
  - T08: `onload="alert(1)"` en `<svg>`.
  - T10: `href="javascript:alert(1)"`.
  - T11: `scripts=js/v.txt` en `theme.properties` con JS en `resources/js/v.txt`. La plantilla lo carga como `text/javascript` (`template.ftl:91-93` del fixture).
- El Paso 4 y BR-U2-13 dependen justamente de que el tema no tenga JS.

### F-03 · NARANJA · theme_checks.py:108-123 · `parse_properties` no lee la sintaxis válida de `java.util.Properties`
Una línea con separador de espacio se ignora:
- T12: `claveInventadaVectra hola` sigue viva, así que entra una clave inventada.
- X05: `doLogIn ` deja `doLogIn` vacío en Keycloak y sigue viva.

La regla «toda clave existe y las exigidas están traducidas» se puede saltar con una sintaxis que Keycloak acepta. El separador `:` sí se detecta (T13).

### F-04 · NARANJA · theme_checks.py:183-199; test_theme.py:172-175 · «No otros colores» incompleto
En el CSS siguen vivas:
- T14: `color: darkred`. Para `\bred\b` no hay frontera de palabra dentro de `darkred`.
- T15: `color: rebeccapurple`.
- T16: `color: var(--pf-v5-global--danger-color--100)`.

En el logo, T20 (`fill="red"`) sigue viva, porque solo se miran hex de 6 dígitos. CA-4 exige «y no otros colores». La lista de nombres a mano cubre unos 30 de los 148 nombres de CSS.

### F-05 · NARANJA · theme_checks.py:227-234 · Las reglas del Dockerfile aceptan imágenes que no cumplen INF-U2-08
Siguen vivas:
- D01: `COPY … themes/vectra /tmp/themes/vectra`. El destino no se ancla a `/opt/keycloak/themes/vectra`.
- D02: `--db=postgres … --db=dev-file`.
- D04: `--health-enabled=true … --health-enabled=false`.
- D03: un segundo `RUN /opt/keycloak/bin/kc.sh build --db=dev-file`. Solo se mira el primer `RUN`.
- D07: `ENV KC_DB=dev-file`.

Los casos que lista CA-5 sí fallan como se pide: otro digest, sin digest, otro tag, sin cada opción, sin `--optimized` y sin COPY.

### F-06 · NARANJA · identity-edge/keycloak/Dockerfile:1-14 · El escaneo de `supply-chain.yml` rechazará este Dockerfile
- `platform.yml:28-29` llama a `supply-chain.yml` en cada PR.
- `supply-chain.yml` corre Trivy v0.76.1 con `scan-type: fs`, `misconfig`, `severity: CRITICAL,HIGH` y `exit-code: "1"`.
- Corrí la misma versión, fuera de línea, sobre una copia: `trivy config --skip-check-update ctx` da `DS-0002 (HIGH): Specify at least 1 USER command…` y rc=1. Salida en `.../rev-u02t06-r1/trivy/out.txt`.
- La tarea delega el escaneo en ese workflow, así que el PR saldrá en rojo.
- Comprobado en la copia: con `USER 1000` antes de `ENTRYPOINT` (el usuario que ya trae la imagen base, sin cambio funcional), Trivy da rc=0 sin HIGH y hadolint rc=0. La otra salida es una excepción en `.trivyignore` con motivo y vencimiento. Ninguna de las dos está en el diseño, así que la decisión es del orquestador o del usuario.

### F-07 · AMARILLO · theme_checks.py:18; test_theme.py:143-146,168; test_keycloak_image.py:212-215,239 · Valores del diseño repetidos como literales
- `REFERENCE_DIR` fija `keycloak-26.8.1` en vez de derivarlo del tag de INF-U2-08. P-U2-08 dice que la referencia es `keycloak-<versión>/` de esa misma versión.
- En Y01 (subir diseño y Dockerfile a 26.9.0 sin cambiar los fixtures), la deriva solo la detecta por casualidad el literal `":26.8.1@"` de `test_other_tag_is_detected`.
- Los conjuntos literales de colores, plantillas y opciones son anclas que fallan alto si el diseño cambia. Aceptable, pero repiten el diseño.

### F-08 · AMARILLO · test_theme.py:42-51 · Tres pruebas pasan en vacío sin tema
En mi rojo reproducido, `test_theme_has_no_external_urls`, `test_theme_has_no_script` y `test_theme_files_are_only_text_without_javascript` dan PASSED con el directorio ausente. Falta afirmar que `theme_files` no está vacío.

### F-09 · AMARILLO · test_theme.py:158-162 · La herencia de `css/styles.css` no está probada
T17 (`styles=css/vectra.css`, que quita PatternFly del padre) sigue viva. El supuesto 2 es correcto según la convención de Keycloak:
- un `styles` en el hijo reemplaza al del padre;
- `css/styles.css` se resuelve por la cadena hacia `keycloak.v2`;
- `stylesCommon` se hereda.

Lo que falta es que una prueba lo fije.

### F-10 · AMARILLO · theme_checks.py:133,236; bitácora, supuesto 6 · Detalles menores
- `import json` está dentro de la función.
- La bitácora dice «cierre inmediato», pero `_MSG_LITERAL` no exige `)`. Es lo correcto, porque así entra `msg("loginTitleHtml",(…))`, pero la bitácora no lo describe bien.
- Las reglas viven en `tests/strategies/`, que el conftest reserva para generadores.

### F-11 · AMARILLO · messages_es.properties:14 · `doClickHere` sin justificación
Las demás claves de más sí se usan en las plantillas de P-U2-08:
- `doSubmit` y `doCancel`: `buttons.button label=` en `login-update-password.ftl:21-24` y `login-config-totp.ftl:108-113`.
- `loginTotp.totp` y `loginTotp.hotp`: `msg("loginTotp." + totp.policy.type)` en `login-config-totp.ftl:33`.
- `showPassword` y `hidePassword`: `msg('…')` en `field.ftl:66-69`.

`doClickHere` no aparece en ninguna de las plantillas listadas. Existe en la referencia, así que no incumple el diseño.

## Juicio sobre los supuestos y el rojo
1. **Contexto `identity-edge/keycloak/`:** aceptable y documentado en el `Dockerfile`. Ningún workflow construye imágenes: `supply-chain.yml` solo escanea el sistema de archivos y `sign-image.yml` recibe un digest. No hay contexto que contradecir.
2. **`styles`:** correcto (ver F-09).
3. **Selectores CSS:**
   - `#kc-header-wrapper`, `.pf-v5-c-login__header` y `.pf-v5-c-brand` están verificados en `template.ftl:154-156` del fixture.
   - `.pf-v5-c-login`, `__main` y `.pf-m-primary` salen del `theme.properties` de `keycloak.v2`, que no está en los fixtures. No se pueden verificar aquí; los verifica el Paso 16.
4. **Claves de más:** ver F-11.
5. **Solo `msg("…")` con comillas dobles:** fiel al texto de P-U2-08.
6. **Rojo fuera de orden:** sin consecuencia sobre la evidencia, porque reproduje el mismo rojo. Matiz: el rojo de `test_keycloak_image.py` es un error de colección (`FileNotFoundError` al importar), no aserciones que fallan. Queda como incumplimiento de proceso declarado. No lo cuento como hallazgo.

## Tareas candidatas (defectos reales fuera de alcance)
- **CSP de BR-U2-13 frente a `keycloak.v2`:** el `template.ftl` del padre (líneas 61-133 del fixture) trae scripts en línea (`importmap` y `type="module"`). Una CSP estricta sin hashes ni nonce los rompe. La premisa «posible porque el tema no tiene JS propio» no basta.
- **Modo oscuro:** `keycloak.v2` aplica `kcDarkModeClass` según `prefers-color-scheme`. Con el fondo forzado a `#FFFFFF`, el texto claro de PatternFly en modo oscuro rompería WCAG AA. El diseño no lo fija (`darkMode`). Para el Paso 16 o el diseño.
- **Construcción de la imagen:** INF-U2-08 dice «construida en CI», pero ningún workflow construye la imagen de Keycloak.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r1/mutaciones.txt` (37 mutaciones, VIVA/MATADA)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r1/mutate.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r1/ca6.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r1/trivy/out.txt`

No quedan procesos en segundo plano. Todas las mutaciones se hicieron sobre copias en el scratchpad, con su propio venv.

NARANJA|identity-edge/tests/strategies/theme_checks.py:150|La excepción de xmlns va por valor y no por posición, y no se detectan URL //host: pasan URLs de otro origen (T01-T03, T05, T06, X04b)
NARANJA|identity-edge/tests/strategies/theme_checks.py:152|Sin JS propio reducido a <script: pasan <s:script>, onload=, javascript: y scripts= en theme.properties
NARANJA|identity-edge/tests/strategies/theme_checks.py:108|parse_properties ignora el separador de espacio: pasan una clave inventada y una traducción vacía
NARANJA|identity-edge/tests/strategies/theme_checks.py:183|No otros colores incompleto: pasan darkred, rebeccapurple, var(--pf-…) y fill=red en el SVG
NARANJA|identity-edge/tests/strategies/theme_checks.py:227|Reglas del Dockerfile: COPY a otra ruta, opciones contradictorias o duplicadas, segundo kc.sh build y ENV KC_DB
NARANJA|identity-edge/keycloak/Dockerfile:1|Trivy DS-0002 HIGH: supply-chain.yml fallará en el PR (falta USER)
AMARILLO|identity-edge/tests/strategies/theme_checks.py:18|Versión de la referencia y valores del diseño repetidos como literales
AMARILLO|identity-edge/tests/unit/test_theme.py:42|Tres pruebas pasan en vacío sin el directorio del tema
AMARILLO|identity-edge/tests/unit/test_theme.py:158|La herencia de css/styles.css en styles no está probada
AMARILLO|identity-edge/tests/strategies/theme_checks.py:236|import json local; la bitácora describe mal _MSG_LITERAL; reglas en strategies/
AMARILLO|identity-edge/keycloak/themes/vectra/login/messages/messages_es.properties:14|doClickHere no aparece en las plantillas de P-U2-08
INFORME: revisiones/U02-T06/ronda-1.md
VEREDICTO: NO-VERDE
