# Ronda 4 — U02-T06

VEREDICTO: VERDE

Los seis criterios pasan con mi propia ejecución y Trivy no da HIGH. F-01 (CSS) y F-02 (Dockerfile) de la ronda 3 quedan cerrados. De 107 mutaciones, 102 mueren. Las 5 vivas no cumplen la regla de hallazgo: o el navegador o Docker no las aceptan con un efecto que viole P-U2-08, BR-U2-13 o INF-U2-08, o no son defecto. Quedan solo dos AMARILLO. El alcance es correcto y el worktree queda limpio en `859b373`.

Datos de la ronda: worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U02-T06`, HEAD `859b373` sobre `36a576f`. Hash de la tarea `b034d158423deb1f751e9a42460685d12f32c11d` (coincide).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | hadolint | `platform/.tools/bin/hadolint identity-edge/keycloak/Dockerfile` | pasa: rc=0, sin salida |
| 2 | tema | `uv run pytest identity-edge/tests/unit/test_theme.py -q` | pasa: 165 passed |
| 3 | referencia | `... -q -k reference` | pasa: 7 passed |
| 4 | marca | `... -q -k brand` | pasa: 44 passed |
| 5 | imagen | `uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q` | pasa: 81 passed |
| 6 | regresión | `uv sync --frozen && make -C identity-edge check && make -C platform check-tools` | pasa: rc=0; ruff limpio, 868 passed, kyverno 38/0 y 239/0 |

Trivy 0.76.1 fuera de línea sobre una copia del Dockerfile (`trivy config --skip-check-update --severity CRITICAL,HIGH --exit-code 1`): rc=0.

## Estado de F-01 y F-02 de la ronda 3

**F-01 CSS: cerrado.**
- Mueren C1, C2, C3 y C4. Llamando directamente a `theme_problems`, C1 da `color: palabra no permitida en color: red` y C3 da `url: 'https://evil.example/a.png'`.
- Mutaciones nuevas contra el tokenizador y las listas blancas, todas muertas:
  - E01: `url(//host)` sin comillas.
  - E02: `content:url("https://…")`.
  - E03: `url(  https://…  )`.
  - E04: `URL(` en mayúsculas.
  - E05: CDO/CDC con un color.
  - E06: escape de comilla dentro de una cadena que esconde un color.
  - E07: salto de línea escapado dentro de una cadena.
  - E08: `col/**/or: red`.
  - E10: `#FFF`.

**F-02 Dockerfile: cerrado.**
- Mueren D10–D15. En el detector directo, D12 da «heredoc no permitido» y D14 da «directiva de parser no permitida».
- Mutaciones nuevas, todas muertas:
  - F01: comentario al final del `RUN`.
  - F02: `ARG` antes de `FROM`.
  - F03: BOM.
  - F05: `USER \` con una línea en blanco y luego `0`.
  - F06: espacios dentro del JSON.
  - F07: escape `\u` dentro de `CMD`.
  - F08: `MAINTAINER`.
  - F09: `--chmod`.
  - F10: directiva.
- Las mutaciones de las rondas 1 a 3 también mueren todas: D01–D07, N37–N51, T, N, X, Y y R01–R02.

**Mutaciones vivas, que no son hallazgo** (`directas.txt`):
- **R03** (fixture extra) y **N52** (`db=` en `keycloak.conf`, donde gana la opción de la línea de comandos): ya juzgadas en las rondas 2 y 3.
- **C6** `href="http:evil…"` en un mensaje: `kcSanitize` lo filtra. Informativa.
- **E09** `url(..//evil.example/a.png)`: es una ruta relativa dentro del mismo origen, no un host. Aceptarla es correcto.
- **E11** `a { color: #FFFFFF; }` y **E12** `#kc-form-login { display: none; }`: solo usan colores y palabras permitidos. El emparejamiento de roles y contraste y la visibilidad de etiquetas los verifican Playwright y axe-core en el Paso 16, según la línea «Verificación» de P-U2-08. No son parte de CA-4 ni del arbitraje. Los dejo como nota, no como defecto.
- **F04** (continuación sin sangría): el `\` original va precedido de espacio, así que Docker obtiene los mismos tokens. Es benigna y se acepta con razón. Si no hubiera espacio antes de `\`, Docker uniría las opciones (`--db=postgres--health-enabled=true`) y `kc.sh build` fallaría: no llega a ser una imagen aceptada.

## Juicio sobre los supuestos del codificador
- **`\` fuera de cadenas y `@` (también `@media`) siempre rechazados:** rechazo de más, coherente con el CSS tokenizado del arbitraje. No es defecto.
- **Selectores sin restricción, salvo que sus cadenas sean vacías:** aceptable. Un selector no carga recursos ni fija colores. El único vector, `content`, solo admite `""` o un `url()` relativo.
- **Unidades: ninguna, `px`, `rem`, `em` y `%`:** aceptable. Es lista blanca, y por ejemplo `10vw` y `1e3px` se rechazan.

## Las tres pruebas que cambiaron de sentido
Las tres corresponden al arbitraje:
1. `test_env_even_equal_to_the_option_is_not_in_the_whitelist`: `ENV KC_DB=postgres` ahora se rechaza, por la secuencia exacta.
2. `test_kc_build_in_exec_form_is_not_the_whitelisted_form`: un `RUN` en forma exec se rechaza, porque la secuencia fija la forma shell.
3. `test_css_escape_outside_a_string_does_not_tokenize_cleanly`: el CSS tokenizado no admite `\` fuera de una cadena.

Se agrega `test_build_options_in_any_order_are_accepted`. Es correcto: el diseño no fija el orden de las opciones.

## Hallazgos

### F-01 · AMARILLO · vectra-risk/bitacoras/U02-T06.md (Ronda 4, «Cambio») · Recuento inexacto
Dice que «dos pruebas» cambiaron de sentido, pero enumera tres, y son tres.

### F-02 · AMARILLO · identity-edge/tests/unit/test_theme.py (`test_css_escape_inside_a_string_url_is_decoded`) · Prueba que no aísla lo que dice probar
Agrega a la vez una URL relativa válida (`\2e\2e/img/…`) y una inválida (`\2f \2f evil…`), y solo afirma que hay algún problema. No demuestra que la válida se decodifique y se acepte, ni que el problema venga de la inválida. La cobertura existe por otras pruebas: E01–E04 mueren.

## Alcance
- `36a576f..859b373` cambia `theme_checks.py`, las dos pruebas, la bitácora y `ronda-3-respuesta.md`.
- El tema y el `Dockerfile` no cambian desde la ronda 2.
- El diff total contra `b06bc6f` queda en el alcance del Paso 4, más las bitácoras y las revisiones del loop. No hay desborde.
- `git status` está vacío antes y después de la revisión.

## Tareas candidatas
Ninguna nueva. Las de la ronda 1 (CSP de `keycloak.v2`, modo oscuro y construcción de la imagen en CI) ya las registra el orquestador. E11 y E12 quedan cubiertas por el Paso 16.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r4/mutaciones.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r4/directas.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r4/mutate.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r4/ca6.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t06-r4/trivy/out.txt`

No quedan procesos en segundo plano. Todas las mutaciones se hicieron sobre copias en `rev-u02t06-r4/`, con su propio venv.

AMARILLO|vectra-risk/bitacoras/U02-T06.md:Ronda 4|La bitácora dice «dos pruebas» cambiaron de sentido, pero son tres
AMARILLO|identity-edge/tests/unit/test_theme.py:test_css_escape_inside_a_string_url_is_decoded|La prueba mezcla una URL válida y una inválida y no aísla cuál produce el problema
INFORME: revisiones/U02-T06/ronda-4.md
VEREDICTO: VERDE
