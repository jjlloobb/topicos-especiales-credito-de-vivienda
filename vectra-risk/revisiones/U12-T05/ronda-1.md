# Ronda 1 — U12-T05

VEREDICTO: NO-VERDE

Hay un ROJO: CA-4 y lo que dice el README sobre el código de salida cuando Chromium no arranca. Todo lo demás de la imagen funciona como dice el README. `make check` terminó en rc 0.

## Probado dentro del contenedor (orden `vv` del README, sin cambios)
Imagen `sha256:26a9b41a…`, salió entera de la caché: `make image` tardó 0,3 s y no bajó nada.

La función `vv` la saqué tal cual de las líneas 121 a 132 del README. Cambié tres cosas para no tocar el clúster:
- `HOME` apunta a un directorio propio con un kubeconfig falso, con el servidor en `https://127.0.0.1:1`;
- `VAULT_ADDR=http://127.0.0.1:9`;
- la CA la generé con openssl.

Para los casos con dobles, las opciones extra van en una copia de `vv` que solo añade montajes o `--entrypoint`. Logs en /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u12t05-r1/ (`manual1.log` a `manual6.log`, `seccomp.log`, `content.log`, `ci.log`, `docs.log`, `readme-mut.log`, `check.log`).

- **`--help`** y el `--help` de las 10 secciones: rc 0, stderr vacío, `evidence/` sigue vacío.
- **`prepare --delivery /verification/reference-model/.out --values-file …`**: rc 0. Los archivos quedan con dueño uid/gid 1000, el del host.
  - Repetido: rc 3, `prepare_manifest_exists`.
  - Sin el montaje de evidencias: rc 3, `store_unwritable:evidence:EROFS`, sin traza.
- **`rt5` contra el doble de `kubectl` por el `live.py` real**: «RT-5: pasa / rt-5: pasa / seccion rt5: pasa (0)» en 12 s. Escribe `RT-5.json` y `demo-rt-5.json` con dueño 1000. El doble solo recibió `get`, `logs` y `port-forward`.
- **`rt3` sin entrega**: rc 3, `ruta_faltante:--packages-dir`. Con la entrega vacía: rc 3, `rt3_paquete_inexistente`.
- **`report`**: rc 0, 41 `no ejecutado`.
- **`network`**: rc 2, con su cita.
- **`entrada.py`** con la orden del README: rc 0; no escribe nada salvo stdout. Con el marcador literal `mv-AAAA-MM-DD-xxxxxxxx` sale `model_version_id_invalid` (rc 2), que es lo esperado.
- **`verify/rt-5.sh 1|2|3`** con el `sh` y el `python3` de la imagen: corren (rc 1, 2 y 2; el kubeconfig es falso).
- **Sandbox con la orden del README**: 7 procesos de Chromium, ninguno con `--no-sandbox`. Tres tienen su propio espacio de nombres de usuario (`user:[4026537095]` frente a `4026531837`) y `NoNewPrivs=1`; el entorno trae `VERIFICATION_CHROMIUM_SANDBOX=1`.
  - Sin el perfil seccomp: `browser_launch_error` en 0,9 s.
  - Sin `--tmpfs /tmp`: `browser_launch_error`.
- **TLS**: la prueba `-k tls` es la misma orden con `--network host` contra el servidor HTTPS de prueba, y sus 9 casos pasan dentro de `test-image` (30 passed).
  - Con la CA correcta cargan los dos caminos: Node para la navegación y Chromium, por la huella, para el subrecurso.
  - Con otra CA, sin CA o con un certificado de otro nombre fallan los dos, con `OidcError`, 0 subrecursos y 0 POST.
  - El almacén de CA del sistema no cambia entre corridas.
  - No hay Keycloak de prueba para la imagen: es el doble `tls_server.py`. El login contra Keycloak real corre en el host dentro de `make test` y pasó.
- **Contenido de la imagen**:
  - No están `argocd`, `helm`, `k6`, `git`, `curl`, `wget` ni `node`.
  - `kubectl` v1.37.0, con el SHA-256 del binario igual al ARG.
  - Playwright 1.64.0; `browsers.json` da chromium y headless-shell en la revisión 1248 (156.0.8078.4). En la imagen solo está `chromium_headless_shell-1248`.
  - Python 3.12.16.
  - No hay `tests/` propios (solo los de certifi, greenlet y pyarrow), ni parquet de la entrega, ni claves privadas, ni kubeconfig.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `test ! -d chart … components.yaml` | pasa (rc 0) |
| 2 | `hadolint`, `FROM` sin digest, grep de opciones prohibidas, `make image`, `-k content` dentro de `test-image` | pasa |
| 3 | `-k run` dentro de `test-image` y a mano con `vv` | pasa |
| 4 | `-k sandbox` (pasa) y la sección con login sin perfil, a mano | **falla** (F-01) |
| 5 | `-k tls` (9 casos) | pasa |
| 6 | `-k readme` (9) y `test_kubectl_verbs.py` | pasa; dos mutaciones sobreviven (F-04) |
| 7 | `grep CODEOWNERS`; `git diff da7358c..HEAD --stat` del archivo | pasa: línea 9, diff vacío |
| 8 | `test_traceability --unit system-verification --all` y `--all` | pasa: rc 0, 22 identificadores, solo INF-U12-05 en la lista; `cli.md` trae BR-U12-01 a 13 con 05, 08, 08b y 12 diferidas |
| 9 | `test_links.py` (594 archivos) y `forbidden_phrases.py` | pasa |
| 10 | dentro de `make check` | pasa: 95,78 % de cobertura; `report` y `sampler` al 100 %; 11 contratos de imports |
| 11 | greps del plan | pasa: 14, 15 y 17 en `[x] (U12-T05)`; 16 en `[ ]` con la nota; el diff solo toca esas casillas |
| 12 | `make check`, `uptime` 11:00:30 (carga 2,06) a 11:25:26 (2,68) | pasa: rc 0 en 24:48. Primera pasada 998 passed en 14:23 (semilla 3414958307); segunda 798 passed en 9:03 (semilla 2696928765; F07 pasó); `test-image` 30 passed en 69,5 s. No corrí `check-fast`: son los mismos objetivos menos `image` y `test-image`, y todos pasaron en `check` |
| 13 | `uv lock --check`; filtro de archivos fuera de alcance | pasa: `fuera=1`; `uv.lock`, `demos/` y `docs` sin cambios; `evidence/` solo con `.gitkeep` |

También pasaron, fuera de los criterios:
- `forbidden_steps.py --dockerfiles .`: rc 0.
- `trivy fs … system-verification`: rc 0, sin hallazgos.
- Los cambios de `src/` son mínimos y cada uno tiene su prueba en rojo según la bitácora. Lo que cerró la ronda 2 de U12-T04 sigue verde: `test_cli`, `test_live`, RT-2, RT-3, RT-5 y Keycloak están dentro de los 998.
- El README sí dice que fuera de la imagen Chromium corre sin sandbox (línea 100).

## Hallazgos

### F-01 · ROJO · CA-4 y `README.md:111` · `decisions` y `rt2-setup` terminan en una traza con código 1 cuando Chromium no arranca
El README promete «`browser_launch_error`, código 2» y CA-4 pide «la sección que necesita login termina con un error claro y código 2». No es así para dos de las cuatro secciones con login:
- `cli.py:670` (`_decisions` → `backend.bff()`) y `rt2.rt2_setup` no capturan `INFRA_ERRORS`. Solo `rt3` (línea 514) y `rt2` lo hacen.
- `_execute` (`cli.py:493`) vuelve a lanzar todo lo que no sea `ScenarioError` ni `SimulatorError`.

Cómo lo comprobé: dentro del contenedor, con la orden del README sin `--security-opt` y una sonda de 6 líneas que solo cambia la bóveda y la huella (`$S/probe/launch_probe.py`); el arranque de Chromium es el real.
- `decisions` → `Traceback … OidcError: browser_launch_error`, rc=1.
- `rt2-setup` → lo mismo, rc=1.
- Sin sonda, con la bóveda inalcanzable: `vv decisions` y `vv rt2-setup` → `Traceback … OidcError: vault_unreachable`, rc=1.

Código 1 es «algún elemento falla»: el operador lo confundiría con un fallo del sistema.

La bitácora (CA-4, «Matiz del código 2») da por cubierto este caso con la regla `INFRA_ERRORS` y lo deja para U12-T06 sin haberlo corrido. Es una afirmación sin verificar, y es falsa.

Arreglo: tratar `INFRA_ERRORS` en `_execute` (resultado `no ejecutado`, código 2) y probarlo con la sonda, o con un `Backend` falso que lance `OidcError`.

### F-02 · NARANJA · `seccomp/chrome.json` · el perfil es más permisivo que el de Docker, y el README dice que es equivalente
Fuera de condiciones, el perfil permite `keyctl`, `mount`, `umount2`, `pivot_root`, `fsopen`, `open_tree`, `move_mount`, `syslog`, `reboot`, `name_to_handle_at`, `fanotify_init`, `mbind`, `set_mempolicy` y `get_mempolicy`. A Chromium solo le hacen falta `clone`, `unshare` y `setns`.

Medido con uid 4242 (`seccomp.log`):
- `keyctl(GET_KEYRING_ID, @u)` devuelve un id con `chrome.json` y EPERM con el perfil por omisión. Con `--user "$(id -u)"` da acceso al llavero del usuario del host, por ejemplo al ccache `KEYRING:` de Kerberos en Fedora.
- `unshare -Urm` + `mount`: aquí lo frena el AppArmor `docker-default`. En hosts sin AppArmor (SELinux, Docker Desktop) el único freno sería seccomp, y este perfil no lo pone.

Lo que no se puede afirmar:
- que el sandbox funcione igual con otros kernels;
- que funcione en rootless o en Docker Desktop.

Solo está probado en Ubuntu 26.04, kernel 7.0, Docker Engine 29.9.2 con `apparmor_restrict_unprivileged_userns=1`.

La frase del README «el resultado esperado es el mismo» no es cierta. Arreglo sin descargar nada: recortar la copia hasta dejar solo lo que Chromium necesita, o al menos decirlo en el README.

### F-03 · NARANJA · `Dockerfile`, etapas `build` y `debs` · dos puntos débiles de la cadena de suministro al construir en otra máquina
- `pip install` de los dos paquetes del workspace baja `hatchling==1.27.0` y sus dependencias (`packaging`, `pathspec`, `pluggy`, `trove-classifiers`) sin hash. Las dependencias ni siquiera tienen versión fija, y ese código corre durante la construcción. La bitácora dice que fijarlas exigiría un índice propio; basta con un segundo requirements con hashes y `--no-build-isolation`.
- `apt.lock` fija 81 versiones `+deb13uN`. Cuando Debian publique una actualización, la versión anterior sale del espejo y la construcción falla en otra máquina. `docker save` y `load` lo evita (está en el README), pero el README presenta `make image` como el camino desde una máquina limpia. Falta decirlo, o usar `snapshot.debian.org`.

### F-04 · NARANJA · `tests/unit/test_demos_closed_world.py:1061` · `readonly` no está cubierto por montaje
La comprobación es `"readonly" in block`. De mis mutaciones del README:
- mueren 9: la opción inexistente, quitar `--read-only`, renombrar una sección, quitar `--security-opt`, `--tmpfs`, `--network host` o `--user`, cambiar `--memory`, y montar el token como archivo;
- sobreviven 2: quitar `readonly` del montaje del kubeconfig (M5) y del de la CA (M10).

CA-6 pide los dos de solo lectura.

### F-05 · AMARILLO · `README.md` · lo que falta para otra máquina
- La herramienta y los `verify` usan el contexto `kind-vectra` (`live.py:35`, con `KUBE_CONTEXT`). El README no lo dice. Con otro contexto, `u11` da `Traceback K8sError … context "kind-vectra" does not exist` (rc 1), y `verify/rt-5.sh 1` dice «NO ES LO ESPERADO: no existe job» (rc 1) en vez de «no se pudo leer».
- En los prerrequisitos faltan `make`, `python3` (los usa `make image`) y `git` (`--commit "$(git rev-parse …)"`), aunque el README dice que no hace falta un clon.
- «Linux con Docker» no avisa de que Docker Desktop **en Linux** tiene el mismo problema con `--network host` que en macOS. Esta máquina tiene el contexto `desktop-linux`. Lo de macOS y Windows sí está dicho, pronto (líneas 39 y 151 a 154).
- No dice que D2 se interrumpe con Ctrl-C y no con `docker stop` (N-1 de U12-T04).

## Tareas candidatas (defectos reales fuera de alcance)
- U12-T04, `cli.py:493`: cualquier `K8sError` u `OidcError` fuera de `rt3` y `rt2` termina en traza con rc 1 (`u11` y `rt5` con el `port-forward` caído, `decisions` con la bóveda caída). Va con F-01.
- U12-T04, `verify/rt-5.sh:13`: un error de `kubectl` en el paso 1 se informa como «no existe» (rc 1) y no como rc 2.

## Notas del entorno
- Las tres pruebas de `test-image` que cambian un dígito de una suma vuelven a bajar `kubectl`, Chromium y los `.deb` autorizados, porque es lo que comprueban; `trivy` consultó su versión. No bajé nada nuevo.
- No toqué el clúster ni `vectra.localtest.me`. No publiqué ni borré ninguna imagen.
- No quedan contenedores míos. `u12t02-keycloak-08fb3e94` (arrancado a las 11:22) no es mío y no lo toqué.
- Mutaciones deshechas con `git checkout`. Borré mi directorio `platform/.tools/tmp/rev-u12t05-r1`. `git status --short` está vacío y HEAD sigue en c1e80db.

```
VEREDICTO: NO-VERDE
ROJO|cli.py:670 / rt2.rt2_setup; README.md:111; CA-4|decisions y rt2-setup terminan en traza con rc 1 (no código 2) cuando Chromium no arranca o la bóveda no responde
INFORME: revisiones/U12-T05/ronda-1.md
```
