# `vectra-nota-de-voz`: la nota de voz del revisor humano

Una orden de consola para **la persona que revisa un pull request**. Graba su voz, la transcribe en su propia máquina con Whisper (pesos abiertos), le muestra el texto para que lo corrija y, solo si responde «s» a una pregunta explícita, lo publica como comentario de revisión del PR. Queda escrito por qué se aprobó: «el agente propone, un humano aprueba», con la traza del humano.

Los agentes del loop no la usan: no está en el `tools:` de ningún agente, ni en `permissions.allow`, ni en `.mcp.json` (una prueba lo comprueba).

## Uso

Desde `vectra-risk/`, en una terminal:

```bash
uv run --group voz vectra-nota-de-voz 247                      # graba, transcribe, deja corregir y pregunta
uv run --group voz vectra-nota-de-voz 247 --dry-run            # todo menos publicar: no pregunta y no escribe en GitHub
uv run --group voz vectra-nota-de-voz 247 --as joseluisjedi    # publica con otra cuenta que ya tiene sesión en `gh`
uv run --group voz vectra-nota-de-voz 247 --as joseluisjedi --approve   # además ofrece aprobar (confirmación aparte)
uv run --group voz vectra-nota-de-voz 247 --audio nota.wav     # usa una grabación existente en vez del micrófono
```

Lo que hace, en orden:

1. **Comprueba** (solo lecturas): que `gh` tiene sesión y con qué cuenta se publicaría (la muestra), que el PR existe y está abierto, que hay grabador y que el transcriptor está instalado. Si falta algo lo dice y sale con código 2, sin haber grabado ni escrito nada.
2. **Graba** del micrófono hasta que se pulsa Enter, o hasta `--max-seconds` (120 por omisión, 600 como máximo).
3. **Transcribe en local** y borra el audio en cuanto tiene el texto.
4. **Muestra** la transcripción y la abre en `$VISUAL` o `$EDITOR` para corregirla. Sin editor, la deja como está y lo avisa.
5. **Pregunta**: `¿Publicar esta nota en el PR #247 como joseluisjedi? (como comentario, sin aprobar) [s/N]`. Solo `s`, `si` o `sí` publican; Enter, cualquier otra cosa o la falta de terminal no publican.
6. **Publica** con `gh pr review 247 --comment --body-file <archivo>`.
7. **Borra** el directorio temporal, también si algo falla o se interrumpe con Ctrl-C.

Códigos de salida: 0 publicado (o `--dry-run`), 1 no se confirmó, 2 falta algo o un argumento se rechazó, 130 interrumpido.

| Opción | Por omisión | Qué hace |
|---|---|---|
| `--dry-run` | no | Nunca publica ni cambia de cuenta; tampoco pregunta |
| `--approve` | no | Pregunta aparte si además se aprueba el PR; hay que escribir la palabra `aprobar`. Nunca aprueba por omisión |
| `--as USUARIO` | la cuenta activa de `gh` | Publica con otra cuenta que ya tiene sesión en `gh` |
| `--audio archivo.wav` | micrófono | WAV PCM de 16 kHz, mono y 16 bits. El archivo es suyo: no se borra |
| `--max-seconds N` | 120 | Duración máxima de la grabación (5 a 600) |
| `--recorder` | `auto` | `arecord` o `pw-record`; `auto` usa el primero que encuentre |
| `--model` | `base` | `tiny`, `base` o `small` |
| `--model-path DIR` | ninguno | Directorio local de un modelo de faster-whisper: no toca la red |
| `--language` | `es` | Código de idioma, o `auto` para que el modelo lo detecte |
| `--repo DUEÑO/NOMBRE` | el del directorio actual | Repositorio del PR |

## Cómo queda el comentario en el PR

```markdown
**Nota de voz del revisor humano**, transcrita en local con Whisper (`base`) y revisada y confirmada por la persona antes de publicarla. El audio no se conserva.

Apruebo porque el diff solo toca el chart de la consola, las pruebas de contrato pasan y el rollback es un revert más sync manual.
```

La cabecera es fija y el resto es el texto que la persona confirmó; no hay firma ni nada más. Con `--audio` la última frase de la cabecera no se escribe, porque ese archivo es de la persona y la herramienta no lo borra. El comentario aparece a nombre de la cuenta de GitHub que lo publica: lo publica una persona.

## El transcriptor: qué se instala, qué se descarga y de dónde

- **Motor**: [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) 1.2.1 (licencia MIT), que ejecuta Whisper sobre CTranslate2 en CPU con cuantización `int8`. No usa GPU y no instala torch.
- **Opcional**: es el extra `transcriptor` del paquete, y el grupo `voz` de la raíz del workspace lo pide. `uv sync --frozen` (lo que hace la CI) no lo instala; `uv run --group voz ...` sí, la primera vez: ocho paquetes de PyPI (`faster-whisper`, `ctranslate2`, `av`, `tokenizers`, `huggingface-hub`, `hf-xet`, `filelock`, `fsspec`), unos 90 MB de descarga. `numpy`, `onnxruntime` y `tqdm` ya estaban en el workspace. Las versiones y los hashes están en `uv.lock`.
- **Sin `ffmpeg`**: el grabador escribe directamente WAV de 16 kHz, mono y 16 bits, que es lo que Whisper espera. La herramienta lo lee con la biblioteca estándar (`wave`) y entrega las muestras al modelo, así que no hay conversión de formato. (El paquete `av`, dependencia de faster-whisper, trae sus propias bibliotecas de FFmpeg y aquí no se usa para decodificar.)
- **El modelo se descarga de internet la primera vez**, y la orden lo avisa antes de hacerlo. Viene de huggingface.co, de los repositorios `Systran/faster-whisper-tiny`, `-base` o `-small` (los pesos de OpenAI convertidos a CTranslate2), y queda en `~/.cache/huggingface`. Tamaño de `model.bin`: `tiny` 76 MB, `base` 145 MB, `small` 484 MB. Con el modelo ya descargado la orden lo carga con `local_files_only`: no abre ninguna conexión.
- **Sin red**: `--model-path /ruta/al/modelo` usa un directorio que ya tenga `model.bin`, `config.json`, `tokenizer.json` y `vocabulary.txt`.
- **Por qué `base` por omisión**: `tiny` se equivoca demasiado en español para un texto que hay que corregir a mano, y `small` transcribe mejor pero pesa el triple y pide bastante más memoria (el README de faster-whisper mide 1 477 MB de RAM con `small` en `int8` para 13 minutos de audio, con 8 hilos en un i7-12700K). `base` cabe con holgura en una máquina con 2 GiB libres y la persona revisa el texto de todos modos. Con memoria de sobra, `--model small` da menos que corregir.
- Se usa el filtro de silencios de faster-whisper (`vad_filter`), que evita frases inventadas en los tramos sin voz.

## Privacidad

La voz es un dato personal. El audio se graba en un directorio `0700` bajo `$XDG_RUNTIME_DIR` (memoria, no disco), en un archivo `0600`; se borra justo después de transcribir y el directorio entero al terminar, pase lo que pase. No se sube a ningún sitio: la transcripción ocurre en esta máquina y lo único que sale por la red es la descarga de los pesos (la primera vez) y, al final, el texto confirmado hacia GitHub. La telemetría de `huggingface_hub` se desactiva.

Lo que no se puede garantizar: un `kill -9` impide el borrado (lo que quede está en `$XDG_RUNTIME_DIR`, que el sistema vacía al cerrar la sesión), y el editor puede dejar copias de seguridad del texto, no del audio, donde tenga configurado.

## La cuenta con la que se publica

La orden usa la sesión de `gh` y nunca lee ni imprime tokens: quita `GH_TOKEN`, `GITHUB_TOKEN`, `GH_HOST` y `GH_REPO` del entorno de `gh` para que la cuenta sea la que `gh auth status` muestra.

Con `--as USUARIO`:

- Si esa cuenta no tiene sesión en `gh`, la orden explica cómo iniciarla y sale sin hacer nada:
  ```bash
  gh auth login --hostname github.com --web        # entre en el navegador como esa cuenta
  gh auth switch --hostname github.com --user jjlloobb   # `gh auth login` deja activa la cuenta nueva: vuelva a la de antes
  ```
- Si la tiene, la cuenta activa de `gh` **solo se cambia durante la publicación**, después de la confirmación: `gh auth switch`, comprobación con `gh auth status`, `gh pr review`, y `gh auth switch` de vuelta, también si la publicación falla o se interrumpe. Si la restauración falla, la orden lo dice en mayúsculas con la orden exacta para arreglarlo.
- `gh auth switch` cambia la cuenta de `gh` para toda la máquina. Durante esos segundos, otro proceso que use `gh` (un agente abriendo un PR, por ejemplo) actuaría con la cuenta del revisor. Publique la nota cuando no haya un agente a punto de usar `gh`.

GitHub no deja aprobar un PR propio: `--approve` con la cuenta que abrió el PR se rechaza antes de grabar.

## Seguridad y límites del diseño

**Lista cerrada de órdenes externas.** Todas se lanzan desde un único archivo ([`commands.py`](src/vectra_nota_de_voz/commands.py)), como lista de argumentos, sin `shell=True` y sin intérprete de órdenes:

| Orden | Para qué | Escribe |
|---|---|---|
| `arecord` o `pw-record` | Grabar al archivo del directorio privado | Solo ese archivo |
| `gh auth status` | Saber qué cuentas tienen sesión y cuál está activa (sin `--show-token`) | No |
| `gh pr view` | Comprobar que el PR existe y está abierto | No |
| `gh auth switch` | Con `--as`: cambiar de cuenta para publicar y restaurarla | La cuenta activa de `gh` |
| `gh pr review` | Publicar la nota, con `--comment` o con `--approve` | **La única escritura en GitHub** |
| El editor de `$VISUAL` o `$EDITOR` | Corregir el texto | El borrador, en el directorio privado |

No existen en el código `--request-changes`, `gh pr merge`, `gh api`, `gh pr comment` ni ninguna otra orden. El editor es el que la persona eligió en su entorno, y es la única orden que no es un literal del código.

**Argumentos validados.** El número de PR es un entero positivo de hasta siete cifras; el usuario de `--as` casa con el patrón de nombres de GitHub (letras, cifras y guiones sueltos, 39 como máximo); el repositorio es `dueño/nombre`; el idioma es un código de dos o tres letras; el modelo y el grabador salen de listas cerradas. Lo demás se rechaza sin lanzar ninguna orden.

**El texto transcrito es contenido no confiable.** No se ejecuta ni se interpreta: la herramienta no busca instrucciones en él y nunca llega a una línea de órdenes, porque viaja en un archivo (`--body-file`). Se le quitan los caracteres de control (secuencias de escape de terminal y marcas de dirección de texto) y se recorta a 4 000 caracteres, con aviso; el límite se aplica otra vez después de editar. GitHub lo muestra como Markdown, igual que un comentario escrito a mano: una `@mención` notifica a esa cuenta. Por eso la persona lo lee antes de confirmar.

**Sin confirmación explícita no hay escritura en GitHub.** Antes de la pregunta final solo se han lanzado `gh auth status` y `gh pr view`.

**Lo que la herramienta no hace**: no fusiona, no pide cambios, no aprueba por omisión, no guarda el audio, no guarda un historial de notas y no resume ni reescribe lo que la persona dijo (un modelo de voz a texto transcribe; no es un asistente). Whisper puede equivocarse o inventar una frase: lo publicado es lo que la persona confirmó, no lo que el modelo oyó.

## Pruebas

```bash
make -C loop/nota-de-voz check     # ruff, mypy y pytest
```

Sin micrófono, sin red y sin GitHub: el grabador, el transcriptor y `gh` son dobles. Las pruebas cubren que el flujo publica exactamente una vez y con el cuerpo esperado; que sin un «s» no se llama a `gh pr review`; que `--dry-run` nunca publica; que `--approve` exige su confirmación; los errores de las comprobaciones previas; el borrado en éxito, en error y en interrupción; los argumentos hostiles; el recorte del texto; y, leyendo el código fuente (AST), que solo existen las órdenes de la lista cerrada. La CI las corre en el job `tests-nota-de-voz` de `.github/workflows/platform.yml`.

### La prueba manual con el modelo real

Una prueba marcada `manual` transcribe un WAV con el modelo de verdad. La suite normal la omite, porque instala el transcriptor, descarga el modelo y lo carga en memoria. Para correrla, con unos 2 GiB de memoria libres y sin otro proceso pesado:

```bash
cd vectra-risk
# 1. Una grabación de prueba de 10 s, fuera del repositorio (diga una frase que contenga las palabras que va a comprobar):
arecord -q -t wav -f S16_LE -r 16000 -c 1 -d 10 "$XDG_RUNTIME_DIR/prueba-voz.wav"
# 2. La prueba (la primera vez instala el grupo `voz`, unos 90 MB, y descarga el modelo `base`, 145 MB):
VECTRA_NOTA_DE_VOZ_MANUAL=1 VECTRA_NOTA_DE_VOZ_WAV="$XDG_RUNTIME_DIR/prueba-voz.wav" VECTRA_NOTA_DE_VOZ_ESPERA="pruebas,rollback" \
  uv run --group voz pytest loop/nota-de-voz --rootdir=loop/nota-de-voz --import-mode=importlib -p no:cacheprovider -m manual -s
# 3. Borre la grabación:
rm "$XDG_RUNTIME_DIR/prueba-voz.wav"
```

`VECTRA_NOTA_DE_VOZ_MODEL` (`tiny`, `base` o `small`) y `VECTRA_NOTA_DE_VOZ_IDIOMA` cambian el modelo y el idioma. Para dejar el entorno como antes, `uv sync --frozen` quita los ocho paquetes; el modelo se borra con `rm -r ~/.cache/huggingface/hub/models--Systran--faster-whisper-base`.

Después, el flujo entero sin publicar: `uv run --group voz vectra-nota-de-voz <PR> --dry-run`.
