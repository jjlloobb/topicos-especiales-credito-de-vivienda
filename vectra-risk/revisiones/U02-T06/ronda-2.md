# Ronda 2 — U02-T06

VEREDICTO: NO-VERDE

Los seis criterios pasan con mi propia ejecución. F-03, F-06, F-07, F-08, F-09, F-10 y F-11 quedan cerrados, y las 37 mutaciones de la ronda 1 que tocan el código mueren todas. Lo que queda es R03 (un fixture extra que no está en SHA256SUMS), que no es defecto. El veredicto sigue NO-VERDE porque F-01, F-02, F-04 y F-05 quedan abiertos: las mutaciones nuevas contra el código nuevo vencen las cuatro reglas arbitradas. La causa es común: las reglas son expresiones regulares sobre texto crudo. No decodifican entidades XML ni escapes CSS, no normalizan URL y no tratan las instrucciones del Dockerfile como lo hace Docker, sin distinguir mayúsculas.

Contexto: tarea con hash `b034d158423deb1f751e9a42460685d12f32c11d` (coincide). Worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U02-T06`, HEAD `a3557fc` sobre `5047b3d`. `git status` está vacío antes y después de la revisión.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | hadolint | `platform/.tools/bin/hadolint identity-edge/keycloak/Dockerfile` | pasa: rc=0, sin salida |
| 2 | tema | `uv run pytest identity-edge/tests/unit/test_theme.py -q` | pasa: 78 passed |
| 3 | referencia | `... -q -k reference` | pasa: 8 passed |
| 4 | marca | `... -q -k brand` | pasa: 29 passed |
| 5 | imagen | `uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q` | pasa: 33 passed |
| 6 | regresión | `uv sync --frozen && make -C identity-edge check && make -C platform check-tools` | pasa: rc=0; ruff limpio, 733 passed, kyverno 38/0 y 239/0 |

Trivy 0.76.1 fuera de línea sobre una copia del Dockerfile:
- `trivy config --skip-check-update` sin filtro de severidad: solo `DS-0026 (LOW)`, la falta de HEALTHCHECK.
- Con `--severity CRITICAL,HIGH --exit-code 1`, el filtro de `supply-chain.yml`: rc=0.

Rojo de la ronda 2 reproducido con el tema y el `Dockerfile` de `50d97b4` bajo las pruebas nuevas: 4 FAILED, en `doClickHere`, `var()` y dos veces `USER`. Coincide con la bitácora.

## Estado de los hallazgos de la ronda 1
| Hallazgo | Estado | Evidencia |
|---|---|---|
| F-01 URL | **abierto, más acotado** | mueren T01–T07 y X04b; viven N01–N04b, N06 y N11 (F-01 abajo) |
| F-02 JS | **abierto, más acotado** | mueren T08–T11, N16 y N19; viven N13, N14 y N15; N12 muere solo por accidente |
| F-03 properties | cerrado | mueren T12, T13, X05 y N21–N26b, incluidos `\uXXXX` en la clave, comentario terminado en `\`, `\\` par y `\`+U+2028/VT |
| F-04 colores | **abierto, más acotado** | mueren T14–T16, T19, T20 y N32; viven N27, N27b, N28 y N30 |
| F-05 Dockerfile | **abierto, más acotado** | mueren D01–D07, N39 y N51; viven N37, N38, N49 y N50 |
| F-06 USER/Trivy | cerrado | `USER 1000`; Trivy HIGH rc=0. El hueco `user 0` en minúsculas va en F-05 |
| F-07 literales | cerrado | `reference_dir()` derivado de INF-U2-08; Y01 ahora da 18 failed |
| F-08 pase en vacío | cerrado | las tres pruebas afirman `theme_files` no vacío |
| F-09 herencia de `styles` | cerrado | T17 muere; queda la nota AMARILLO de F-13 |
| F-10 | cerrado | `import json` arriba; la bitácora corregida |
| F-11 | cerrado | sin `doClickHere` |

Transcripción completa: `.../rev-u02t06-r2/mutaciones.txt` (73 mutaciones). Las vivas las comprobé llamando directamente a los detectores: `.../rev-u02t06-r2/directas.txt`.

## Hallazgos

### F-01 · NARANJA · identity-edge/tests/strategies/theme_checks.py:201-230 · URL de otro origen que la regla no ve
Todas son URL que el navegador resuelve a otro origen y que `external_references` devuelve vacías:
- N01 `<use href="/\evil.example/x.svg#a"/>`: el parser WHATWG trata `\` como `/`, así que queda `//evil.example`.
- N02 `href="https:\\evil.example/…"`.
- N03 `href="http:/evil.example/…"`: un esquema distinto del de la base lo vuelve absoluto.
- N04b `url("/\\evil.example/a.png")` en CSS.
- N06 `href="/&#9;/evil.example/…"`: la entidad se decodifica a tab y el parser de URL la elimina.
- N11 `<use data-x=" xmlns='" href="https://evil.example/x.svg#a" z="'"/>`. Es XML válido con un `href` real, pero `_XMLNS_ATTR` toma la comilla simple dentro de `data-x` como apertura de un `xmlns` y borra el `href` verdadero. La exención «por posición» sigue siendo por regex y se engaña mezclando comillas.

Corrección de clase: parsear el SVG con un parser XML (entidades decodificadas, atributos reales; exentos solo los atributos cuyo nombre es `xmlns` o `xmlns:*`). Luego, en lista blanca, toda referencia (`href`, `xlink:href`, `src`, `url()`, `@import`) normalizada debe ser una ruta relativa sin esquema y sin `/` ni `\` inicial.

### F-02 · NARANJA · theme_checks.py:233-252 · JavaScript que la regla no ve
- N13 `<a href="javascript&#58;alert(1)">`: la entidad se decodifica a `javascript:`. No se detecta.
- N12 `&#106;avascript:`: la mutación muere, pero solo porque el detector de colores lee `#106` como un hex. La regla de JS no la ve.
- N14 `<foreignObject><iframe srcdoc="&lt;script&gt;alert(1)&lt;/script&gt;"/>`: JS dentro de `srcdoc` codificado con entidades.
- N15 `messages_es`: `loginTitleHtml=<script>alert(1)</script>`. Las reglas miran el texto crudo del `.properties` y no los valores ya decodificados que `parse_properties` sabe producir.
- Informativo, no lo exijo: N18 `<set attributeName="onclick" to="alert(1)"/>` (SMIL). Los navegadores actuales lo bloquean.

Corrección: aplicar las reglas al SVG ya parseado (entidades decodificadas; también `foreignObject`, `iframe` y `srcdoc`) y a los valores decodificados de `messages_es`.

### F-03 · NARANJA · theme_checks.py:265-330 · Colores distintos de los tres que pasan, pese al arbitraje «ningún color distinto»
- N27 `color: CanvasText;` y N27b `background: Highlight;`: colores de sistema de CSS fuera de la lista.
- N28 `color: r\65 d;`: un escape CSS de `red`.
- N30 `fill="CanvasText"` en el SVG: `svg_color_problems` devuelve `[]`. La mutación del arnés muere, pero solo porque `_replace` de los casos de color exige `fill="#0B3D5C"`. Es una muerte accidental.
- Incoherencia: se rechaza `currentcolor` (supuesto del codificador), pero se aceptan `inherit`, `initial`, `unset` y `revert`, que también traen un color de PatternFly.

Corrección de clase: lista blanca. Todo token de un valor en una propiedad que lleva color, tras decodificar escapes, es uno de los tres hex o una palabra clave sin color de una lista cerrada.

### F-04 · NARANJA · theme_checks.py:358-393 · El Dockerfile admite un segundo build, otra etapa final o root
- N37 `RUN ["/opt/keycloak/bin/kc.sh", "build", "--db=dev-file"]` en forma exec: `kc\.sh build\b` no lo cuenta.
- N38 `RUN /opt/keycloak/bin/kc.sh --verbose build --db=dev-file`: tampoco se cuenta.
- N50 `from busybox:1.36` en minúsculas al final: `^FROM` lo ignora y la imagen final deja de ser Keycloak. Docker no distingue mayúsculas en las instrucciones.
- N49 `user 0` en minúsculas antes de `ENTRYPOINT`: `^USER` lo ignora y la imagen corre como root. Rompe la regla arbitrada de F-06.
- N51 (`run` en minúsculas) sí muere, porque la regex de build no está anclada.

Corrección: tokenizar las instrucciones sin distinguir mayúsculas, con formas exec y shell, y reconocer `kc.sh` con cualquier opción antes de `build`.

### F-05 · AMARILLO · identity-edge/tests/unit/test_theme.py:155-162 · La regex heurística de claves usadas
`(?:msg\(|label=|")["']?([\w.-]+)` cuenta como usada cualquier palabra que siga a una comilla, y exime de forma literal `loginTotp.totp`/`hotp` y `doClickHere`. La medí: hoy no deja pasar ninguna clave de la referencia que no sea `msg`/`label` (`.../directas.txt` y la salida del cálculo en esta ronda). Es aceptable como guarda del arbitraje F-11. Lo mejor sería derivar `loginTotp.*` de `msg("loginTotp." + …)` y de la referencia, y restringir la regex a `msg(` y `label=`.

### F-06 · AMARILLO · test_theme.py:248-251 · Prueba tautológica
`test_brand_styles_without_parent_stylesheet_are_detected` comprueba su propio `replace` (`styles != [...]`), no una función de reglas. T17 sí muere, por `test_brand_styles_keep_the_parent_stylesheet`. Lo mismo vale para `test_theme_missing_directory_fails_the_checks`, que solo afirma que `theme_files` de un directorio inexistente da `[]`.

Nota: en este informe numeré los hallazgos de la ronda 2 desde F-01. La tabla de arriba usa la numeración de la ronda 1. Equivalencias: F-01 nuevo = F-01 viejo (URL), F-02 = F-02 (JS), F-03 = F-04 (colores), F-04 = F-05 y F-06 (Dockerfile). F-13, citado en la tabla, es este F-06.

## Juicio sobre los supuestos del codificador
- **`xmlns` solo en `.svg`:** correcto. Solo el SVG declara espacios de nombres. Un `@namespace` en CSS se marcaría, y esa estrictez es aceptable. El problema no es el alcance, es la implementación por regex (F-01, N11).
- **Rechazar `transparent` y `currentcolor`:** coherente con el arbitraje. Falta la misma lógica para `inherit` y similares (F-03).
- **Regex heurística de las claves usadas:** ver F-05; hoy no falla.
- **El rojo de la ronda 2:** reproducido y coincide.

## Alcance
`5047b3d..a3557fc` cambia 8 archivos: el `Dockerfile` (`USER 1000`), `vectra.css`, `messages_es` (sin `doClickHere`), `theme_checks.py`, las dos pruebas, la bitácora y `ronda-1-respuesta.md`. No hay desborde. El worktree queda limpio en `a3557fc`.

## Tareas candidatas
Ninguna nueva. Las tres de la ronda 1 las registra el orquestador.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r2/mutaciones.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r2/directas.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r2/mutate.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r2/ca6.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r2/trivy/out.txt`

No quedan procesos en segundo plano. Todas las mutaciones se hicieron sobre copias en `rev-u02t06-r2/`, con su propio venv.

NARANJA|identity-edge/tests/strategies/theme_checks.py:201|URL de otro origen sin detectar: /\host, https:\\host, http:/host, /&#9;/host, url("/\\host") y xmlns falso que borra un href real (N01-N06, N11)
NARANJA|identity-edge/tests/strategies/theme_checks.py:233|JS sin detectar: javascript&#58;, srcdoc con &lt;script&gt; y <script> en messages_es (N13-N15); N12 muere solo por accidente
NARANJA|identity-edge/tests/strategies/theme_checks.py:265|Colores fuera de los tres: colores de sistema (CanvasText, Highlight), escape CSS r\65 d y fill=CanvasText en el SVG (N27, N27b, N28, N30)
NARANJA|identity-edge/tests/strategies/theme_checks.py:358|Dockerfile: segundo build en forma exec o con flag antes de build, from/user en minúsculas (N37, N38, N49, N50)
AMARILLO|identity-edge/tests/unit/test_theme.py:155|Regex heurística de claves usadas y exenciones literales (hoy sin falsos aceptados)
AMARILLO|identity-edge/tests/unit/test_theme.py:248|Pruebas tautológicas: la de styles sin la hoja del padre y la de directorio inexistente
INFORME: revisiones/U02-T06/ronda-2.md
VEREDICTO: NO-VERDE
