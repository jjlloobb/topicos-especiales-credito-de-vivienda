# Ronda 3 — U02-T06

VEREDICTO: NO-VERDE

Los seis criterios pasan con mi propia ejecución y Trivy no da HIGH. La corrección de clase queda **cerrada para SVG, `.properties`, JavaScript y claves**: todas las mutaciones vivas de la ronda 2 en esas áreas mueren, y también las nuevas contra la lista blanca de SVG. **No queda cerrada en dos sitios**, con casos que un navegador o Docker aceptan de verdad:
- **CSS:** la lista blanca se aplica sobre texto que no se tokeniza respetando las cadenas, y no limita las propiedades.
- **Dockerfile:** el tokenizador separa la instrucción solo por espacio y no reconoce heredocs, `sh -c`, variables ni la directiva `escape`.

Datos de la ronda: worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U02-T06`, HEAD `94d4b33` sobre `6cc126a`. Hash de la tarea `b034d158423deb1f751e9a42460685d12f32c11d` (coincide). `git status` está vacío antes y después de la revisión.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | hadolint | `platform/.tools/bin/hadolint identity-edge/keycloak/Dockerfile` | pasa: rc=0 |
| 2 | tema | `uv run pytest identity-edge/tests/unit/test_theme.py -q` | pasa: 140 passed |
| 3 | referencia | `... -q -k reference` | pasa: 7 passed |
| 4 | marca | `... -q -k brand` | pasa: 44 passed |
| 5 | imagen | `uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q` | pasa: 57 passed |
| 6 | regresión | `uv sync --frozen && make -C identity-edge check && make -C platform check-tools` | pasa: rc=0; ruff limpio, 819 passed, kyverno 38/0 y 239/0 |

Trivy 0.76.1 fuera de línea sobre una copia del Dockerfile (`trivy config --skip-check-update --severity CRITICAL,HIGH --exit-code 1`): rc=0. El Dockerfile y el tema no cambiaron en esta ronda.

## Estado de los hallazgos de la ronda 2
| Hallazgo r2 | Estado | Evidencia (`mutaciones.txt`, 85 mutaciones) |
|---|---|---|
| F-01 URL | cerrado en SVG y `.properties`; **abierto en CSS** (C3) | mueren N01–N08, N04b, N11, S1 (`font-family="url(…)"`) y S6 (`xi:include`) |
| F-02 JS | cerrado | mueren N12–N16, N18 y N19 |
| F-03 colores | cerrado en SVG; **abierto en CSS** (C1, C2, C4) | mueren N27, N27b, N28, N30, N31 y N32 |
| F-04 Dockerfile | **abierto** (D10–D15) | mueren N37, N38, N39, N49, N50 y N51 |
| F-05 claves usadas | cerrado | `used_keys` sin exenciones literales; las claves esperadas salen de `label=`, `msg('…')` y `msg("loginTotp." + …)` |
| F-06 pruebas tautológicas | cerrado | sustituidas por `structure_problems` y sus casos (`test_theme.py:44-70`) |

Siguen vivas tres mutaciones que no son defecto:
- R03: un fixture extra que no se usa.
- N52: `db=` en `keycloak.conf`; la opción de la línea de comandos tiene precedencia.
- C6: `href="http:evil…"` en un mensaje, que `kcSanitize` filtra. Es informativa.

## Hallazgos

### F-01 · NARANJA · identity-edge/tests/strategies/theme_checks.py (`_css_unescape` y `css_problems`) · El CSS no se tokeniza respetando cadenas, y la lista blanca no limita propiedades
Todas pasan la suite y `theme_problems` las devuelve vacías (`directas.txt`). Las cuatro las acepta un navegador:
- **C1** `.x { content: "/*"; color: red; content: "*/"; }`: `_css_unescape` borra `/*…*/` sin respetar cadenas y se lleva `color: red`. En el navegador `"/*"` es una cadena y el rojo se aplica. Viola la marca de P-U2-08.
- **C2** `.x { content: "}"; color: red; }`: `\{([^{}]*)\}` corta en la llave de la cadena y `color: red` queda fuera de todo bloque revisado.
- **C3** `.x { content: "/*"; background: url(https://evil.example/a.png); content: "*/"; }`: el mismo truco oculta una **URL externa**. Viola P-U2-08 («sin recursos externos») y BR-U2-13 (CSP).
- **C4** `.pf-v5-c-button.pf-m-primary { opacity: 0.2; }`: los números pasan siempre. El botón queda con un color efectivo distinto de los tres y un contraste < 4,5:1, contra el compromiso de contraste de P-U2-08.

Corrección de clase:
- Tokenizar el CSS como lo hace el navegador: las cadenas son tokens, los comentarios se quitan solo fuera de ellas y las llaves solo cuentan fuera de cadenas.
- Lista blanca también de **propiedades**: las que usa `vectra.css`, que son `background-color`, `color`, `content`, `display`, `width`, `height`, `margin`, `background`, `outline` y `outline-offset`.
- Rechazar todo lo que no tokenice limpio.

### F-02 · NARANJA · theme_checks.py (`_instructions`, `_argv` y `_kc_invocations`) · El Dockerfile admite otra etapa final, root o un segundo `kc.sh build`
Todas pasan la suite y `dockerfile_problems` las devuelve vacías:
- **D10** `USER<tab>0`: `partition(" ")` solo separa por espacio; BuildKit separa por `[\t\v\f\r ]+`. La imagen corre como root.
- **D11** `FROM<tab>busybox:1.36` al final: la imagen final deja de ser Keycloak.
- **D12** heredoc `RUN <<EOF` / `/opt/keycloak/bin/kc.sh build --db=dev-file` / `EOF`. El frontend por omisión de BuildKit lo soporta. Las líneas del heredoc se leen como instrucciones desconocidas y se ignoran.
- **D13** `RUN sh -c "/opt/keycloak/bin/kc.sh build --db=dev-file"`: el token es la cadena entera y `rsplit("/")` da `kc.sh build --db=dev-file`, no `kc.sh`.
- **D15** `RUN K=/opt/keycloak/bin/kc.sh; $K build --db=dev-file`.
- **D14** `# escape=\`` en la primera línea, seguido de `RUN echo x \` y `USER 0`. Para Docker, `\` deja de continuar la línea y `USER 0` es una instrucción. El detector lo absorbe en el `RUN` y no ve nada. La suite muere solo por accidente: otras pruebas reemplazan texto que el reescrito ya no contiene.

Corrección de clase, la lista blanca que pidió el arbitraje aplicada a instrucciones:
- Rechazar directivas de parser y heredocs.
- Separar por cualquier blanco.
- Exigir exactamente la secuencia de instrucciones del diseño (FROM, COPY, RUN, USER, ENTRYPOINT, CMD), con un único `RUN` cuyo argv sea `/opt/keycloak/bin/kc.sh build` más las cuatro opciones.
- Rechazar cualquier otro `RUN`.

Así ningún `sh -c`, variable ni heredoc puede esconder un segundo build.

## Juicio sobre los supuestos del codificador
- **La lista cerrada de palabras CSS igual a la que usa `vectra.css`:** correcto como lista blanca. Un rechazo de más no es defecto. Le falta limitar propiedades y tokenizar cadenas (F-01).
- **`xmlns` comprobado por el espacio de nombres del elemento:** correcto. `ElementTree` resuelve los prefijos. Los elementos fuera de SVG (S6, T09) y los atributos con espacio de nombres (`xlink:href`, X04b) caen por la lista blanca, y N11 muere. La regla del SVG queda cerrada.

## Alcance
`6cc126a..94d4b33` cambia `theme_checks.py`, las dos pruebas, la bitácora y `ronda-2-respuesta.md`. El tema y el `Dockerfile` no cambian. No hay desborde. El worktree queda limpio en `94d4b33`.

## Tareas candidatas
Ninguna nueva.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r3/mutaciones.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r3/directas.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r3/mutate.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r3/ca6.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r3/trivy/out.txt`

No quedan procesos en segundo plano. Todas las mutaciones se hicieron sobre copias en `rev-u02t06-r3/`, con su propio venv.

NARANJA|identity-edge/tests/strategies/theme_checks.py:css_problems|CSS sin tokenizar cadenas ni lista de propiedades: color rojo y URL externa ocultos tras "/*" o "}" dentro de cadenas, y opacity 0.2 que baja el contraste (C1-C4)
NARANJA|identity-edge/tests/strategies/theme_checks.py:_instructions|Dockerfile: USER<tab>0, FROM<tab>busybox, heredoc, sh -c, $K build y # escape=` evaden las reglas de FROM único, USER 1000 y kc.sh build único (D10-D15)
INFORME: revisiones/U02-T06/ronda-3.md
VEREDICTO: NO-VERDE
