# system-verification (U12): verificación del sistema en kind

`vectra-verification` verifica que Vectra Risk funciona de punta a punta en kind y deja un informe con evidencias. Corre **fuera del clúster**, en la estación del operador, en una imagen de contenedor: la imagen lleva la herramienta, los guiones y los `verify` de las demos, `report/story-map.yaml`, `python3`, `sh`, `kubectl` y el Chromium sin interfaz del login. No necesita un clon de este repositorio en la máquina donde corre; solo lo que el operador monta de forma explícita (kubeconfig, certificado raíz, directorio de evidencias y, cuando hace falta, la entrega del modelo de referencia y el archivo de values).

Es de **solo lectura sobre el clúster**: lee con `kubectl` (solo `get`, `auth can-i`, `logs` y `port-forward` a un pod), llama a la API del sistema por el gateway como lo haría una persona (login OIDC con usuarios sintéticos) y escribe únicamente en el directorio de evidencias. Los cambios que las demos necesitan (un PR, una sincronización en Argo CD) los hace una persona; la herramienta los espera y los verifica. Los pasos de cada demo están en `demos/`; esta guía dice cómo correr la herramienta.

## Qué entra y qué no (demo en kind)

Las ocho secciones, en el orden en que se corren (`vectra-verification <sección>`; también `all --from <sección>`):

| Orden | Sección | Qué hace | Demo |
|---|---|---|---|
| 1 | `prepare` | genera el `runId` (`AAAAMMDD-HHMM`), el manifiesto y el parche de `values/kind/case-management.yaml`; **ninguna solicitud** | todas |
| 2 | `decisions` | 2 000 solicitudes `normal`, espera a `listo`, el conductor y `SIM-NORMAL` | D4 (día D) |
| 3 | `rt5` | el Job `rt5-demo-<runId>` y la alerta `CoreWriteAttempt` | D3 |
| 4 | `rt3` | RT-3 (a, c, d y F22) y la escalada | D1 |
| 5 | `rt2-setup` | registra, valida y aprueba la versión del proxy | D2 |
| 6 | `rt2` | RT-2, latencia de detección y reactivación | D2 |
| 7 | `u11` | las cuatro series de los paneles y la alerta `ProductMetricsStale`, el día D + 1 | D4 (día D + 1) |
| 8 | `report` | `verification-report.md`, en cualquier momento | todas |

`rt2` tiene dos modos de reactivación, `--reactivation tool` (por omisión: la herramienta hace el step-up de `cumplimiento-1` y reactiva) y `--reactivation presenter` (el presentador reactiva en la consola con `cumplimiento-2` y la herramienta espera y verifica).

**Diferidas por la demo** (responden `no ejecutado`, código 2, sin hacer ninguna solicitud, y dejan una línea con su cita en el manifiesto): `network`, `rt1`, `rt4`, `load`, `pii` y `resilience`. Las cita la enmienda del recorte funcional de la demo; `aidlc-docs/construction/system-verification/evidence/cierre-demo.md` lista lo que se difiere.

### Códigos de salida

| Código | Significado |
|---|---|
| 0 | la sección terminó y todo lo suyo es `pasa` |
| 1 | algún elemento `falla` |
| 2 | `no ejecutado`: faltó un prerrequisito, o la sección es una de las diferidas. La sección queda `interrumpida` y se retoma al volver a correrla |
| 3 | la herramienta se negó: barrera (entorno, hora, volumen), uso incorrecto, `prepare` ausente o repetido, un directorio de evidencias que no se puede escribir o un archivo que el filtro de evidencias no deja escribir |

`falla` y `no ejecutado` nunca comparten código ni texto. Una sección terminada no se repite sin `--redo`; `rt2` retoma en la fase donde paró.

## Prerrequisitos del operador

**En la máquina** (una máquina limpia; Linux con Docker; ver «Red» para macOS y Windows):

| Qué | Versión | Para qué |
|---|---|---|
| Docker Engine | 24 o posterior (probado con 29.9.2) | construir y correr la imagen; es también lo que corre kind |
| kind | v0.33.0 | el clúster (`platform/kind/cluster.yaml`, Kubernetes 1.37) |
| `kubectl` | cliente 1.37.x | reenviar la bóveda y exportar el kubeconfig; la imagen trae el suyo para las secciones |
| `helm` | v4.3.0 | instalar las unidades (U1 a U11) |
| Memoria | **14 GiB como mínimo, 16 recomendados** | los requests del perfil de kind suman 11,8 GiB (`platform/tests/test_kind_profile.py`, `BUDGET_GIB`); la herramienta usa 1 GiB más (`--memory 1g`) y Chromium corre dentro de ese límite |
| Kernel | espacios de nombres de usuario sin privilegios (`kernel.unprivileged_userns_clone=1`, `user.max_user_namespaces` > 0) | el sandbox de Chromium |

**En el clúster:**

- U1 a U11 instaladas con digests reales; la política y el modelo de referencia activos; los paquetes proxy y RT-3 en el model-store (`model-serving/docs/paso-11-kind.md`).
- K16, el acceso de solo lectura del grupo `vectra-verification-operators` (`platform/rbac/verification-operator/k16.yaml`), o un kubeconfig de administrador de kind: **en kind el operador usa su kubeconfig de administrador, no K16**; K16 se comprueba en U12-T06.
- **El camino a la bóveda** (no lo da K16): el operador reenvía la bóveda con su kubeconfig, por ejemplo `kubectl -n vault port-forward svc/vault 18200:8200`, y pasa `VAULT_ADDR=http://127.0.0.1:18200`. La herramienta solo acepta `127.0.0.1`, `localhost` y `vault.vault.svc` como bóveda. El token va **solo como variable de entorno** (`VAULT_TOKEN`), nunca en un archivo.
- El **certificado raíz** del gateway exportado a un archivo `vectra-ca.pem` (se monta de solo lectura).
- Las semillas TOTP que el presentador necesita en su teléfono: `analista-2` o `cro-2` en D1 y `cumplimiento-2` en D2 (modo `presenter`); la herramienta usa los usuarios `-1` y no toca los `-2`.
- La cuenta `grafana-admin` y un `port-forward` al pod de Grafana de `vectra-observability` para D4 (Grafana no tiene OIDC).
- El eco de U2 y la `ServiceAccount` temporal de U4 retirados antes del sync de U10.
- `CASE_ALLOW_TEST_SCENARIOS` activo (`allowTestScenarios: true`, ya en los values de kind).
- La entrega del modelo de referencia (`reference-model/.out`, de `make -C reference-model release`): `decisions`, `rt3`, `rt2-setup` y `rt2` la leen. Se copia a la máquina de la demo y se monta de solo lectura en `/verification/reference-model/.out`. `prepare`, `rt5`, `u11` y `report` no la necesitan. `prepare --delivery <ruta>` guarda la ruta (la de **dentro** del contenedor) en el manifiesto (`paths.delivery`) y las demás secciones la toman de ahí; cada una acepta también `--delivery`. `--packages-dir`, `--proxy-root` y `--reference-dir` cuelgan de la entrega: sin ninguna ruta, la sección termina con código 3 y `ruta_faltante`.
- Para `prepare` con parche: el archivo `vectra-risk-gitops/values/kind/case-management.yaml` del commit que se verifica, montado de solo lectura (`--values-file`).
- Los PR de las demos (`runId`, apagar y revertir F22, proxy, promoción) los abre una persona con el repositorio; sus parches están en la imagen (ver «Los guiones, los `verify` y los PR»).

## La imagen

Etiqueta local: `localhost:5001/vectra/system-verification:dev`. La imagen se construye desde la raíz de `vectra-risk/` del repositorio (el contexto lleva solo lo que el `Dockerfile` copia):

```sh
make -C system-verification image
```

Sin `make`, la misma construcción: `docker build -f system-verification/Dockerfile -t localhost:5001/vectra/system-verification:dev .` desde `vectra-risk/`. Comprobar que arranca: `docker run --rm --read-only localhost:5001/vectra/system-verification:dev --help`.

**Llevarla a otra máquina o al registro de kind** (publicar es cosa del operador; esta guía no lo hace):

```sh
# opción 1: sin registro, de una máquina a otra
docker save localhost:5001/vectra/system-verification:dev | gzip > system-verification.tar.gz
gunzip -c system-verification.tar.gz | docker load

# opción 2: por el registro de kind (kind-registry, 127.0.0.1:5001), con el digest que imprime `docker push`
docker push localhost:5001/vectra/system-verification:dev
docker pull localhost:5001/vectra/system-verification@sha256:<digest>
```

La herramienta corre en la estación del operador, no en el clúster: no hace falta cargar la imagen en los nodos de kind.

**Qué trae y qué descargó la construcción** (cada descarga con versión fija y SHA-256 comprobado en el `Dockerfile`: cambiar un dígito de la suma rompe la construcción):

| Componente | Versión | SHA-256 |
|---|---|---|
| Base de Python | `python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159` | por digest |
| Paquetes del sistema de Chromium (81 `.deb`) | `image/apt.lock`: versión y suma de cada uno | una por paquete |
| Chromium headless shell (Playwright 1.64.0, revisión 1248, Chrome for Testing 156.0.8078.4) | `chrome-headless-shell-linux64.zip` | `c3e50596aef52c58f8fda3c6b3411c33d34c88b177b3ed1c2243359fd3b8ba20` |
| `kubectl` | v1.37.0 (la del nodo de kind) | `6129359f4e1f3848a5572ccb0b26cf28b8ca08cef38c95a765b2f64a2c961a2f` (la que publica dl.k8s.io) |
| Dependencias de Python | `image/requirements.txt`, con hashes (`uv export` del `uv.lock`) | por paquete |

La imagen no trae el binario de Argo CD, `helm`, `git`, `curl` ni manifiestos de Kubernetes. Sin escaneo, SBOM ni firma (diferido por la demo).

**Perfil `seccomp` de Chromium.** El sandbox de Chromium necesita crear espacios de nombres de usuario, que el perfil por omisión de Docker bloquea. La imagen se corre con `--security-opt seccomp=chrome.json` y **nunca** con `--no-sandbox`. El sandbox solo se garantiza ejecutando desde la imagen (`VERIFICATION_CHROMIUM_SANDBOX=1`): fuera de ella, `HeadlessForm._launch` arranca Chromium sin sandbox. El archivo está en la imagen y en `seccomp/chrome.json` del repositorio:

```sh
docker run --rm --entrypoint cat localhost:5001/vectra/system-verification:dev /opt/system-verification/seccomp/chrome.json > chrome.json
```

<!-- seccomp/chrome.json
     Origen: /usr/share/containers/seccomp.json (paquete containers-common de Debian/Ubuntu), perfil de Docker/Podman que ya admite `clone`, `unshare` y `setns`.
     SHA-256: 886ae167646b7e5db381ecf7c31e6de720a8e8da15cf3202fe1f67f424af2b75
     Es una copia sin cambios. NO es el perfil que publica Playwright: ese habria exigido una descarga que no estaba autorizada. Sustituirlo por el de Playwright queda pendiente (U12-T06). -->

Origen y suma del perfil: copia sin cambios de `/usr/share/containers/seccomp.json` (paquete `containers-common`), SHA-256 `886ae167646b7e5db381ecf7c31e6de720a8e8da15cf3202fe1f67f424af2b75`. **No es el archivo que publica Playwright** (`chrome.json`): ese exigía una descarga que no estaba autorizada para esta construcción; con él, el resultado esperado es el mismo y queda pendiente comprobarlo en U12-T06. Si el host no permite espacios de nombres de usuario o se omite el perfil, la sección que necesita login termina con un error claro (`browser_launch_error`, código 2) y no con Chromium sin protección.

## Cómo correrla: la orden `docker run`

Una sola orden, con una función de shell para no repetirla. Se corre desde un directorio de trabajo que tenga `chrome.json`, `vectra-ca.pem`, `case-management.yaml` (el de `vectra-risk-gitops/values/kind/` del commit que se verifica), `reference-model-out/` (la entrega del modelo de referencia) y la carpeta `evidence/`. Los montajes son `--mount type=bind`, no `-v`: si falta un archivo, Docker se niega en vez de crear en su lugar un directorio de root.

```sh
mkdir -p evidence && chmod 755 evidence
export VAULT_ADDR=http://127.0.0.1:18200   # la bóveda, reenviada por el operador
export VAULT_TOKEN=...                      # la sesión del operador: solo como variable
vv() {
  docker run --rm --read-only --tmpfs /tmp --network host \
    --user "$(id -u):$(id -g)" --memory 1g \
    --security-opt seccomp=chrome.json \
    --mount type=bind,source="$HOME/.kube/config",target=/kube/config,readonly -e KUBECONFIG=/kube/config \
    --mount type=bind,source="$PWD/vectra-ca.pem",target=/certs/ca.pem,readonly -e VERIFICATION_CA_FILE=/certs/ca.pem \
    --mount type=bind,source="$PWD/evidence",target=/verification/evidence \
    --mount type=bind,source="$PWD/case-management.yaml",target=/values/case-management.yaml,readonly \
    --mount type=bind,source="$PWD/reference-model-out",target=/verification/reference-model/.out,readonly \
    -e VAULT_ADDR -e VAULT_TOKEN \
    localhost:5001/vectra/system-verification:dev "$@"
}
```

| Opción | Para qué |
|---|---|
| `--read-only` y `--tmpfs /tmp` | sistema de archivos de solo lectura; lo único escribible es `/tmp` (en RAM, donde van `HOME` y el perfil de Chromium) y el directorio de evidencias. Sin `--tmpfs /tmp` Chromium no arranca |
| `--user "$(id -u):$(id -g)"` | el usuario del host, sin root: los archivos de `evidence/` quedan con su dueño y se pueden borrar. La imagen funciona con cualquier uid sin root (por omisión, 65532) |
| `--network host` | en Linux, `vectra.localtest.me`, la API de Kubernetes del kubeconfig y los `port-forward` son `127.0.0.1` del host: el contenedor tiene que compartir su red |
| `--memory 1g` | límite de memoria de la herramienta con su Chromium (valor de partida; U12-T06 lo mide) |
| `--security-opt seccomp=chrome.json` | el perfil del sandbox de Chromium (arriba) |
| `--mount` del kubeconfig (`readonly`) y `-e KUBECONFIG` | el kubeconfig, de solo lectura, sin copiarlo a la imagen ni a disco |
| `--mount` de `vectra-ca.pem` (`readonly`) y `-e VERIFICATION_CA_FILE` | el certificado raíz, de solo lectura. Lo reciben los **dos** caminos TLS: Node por `NODE_EXTRA_CA_CERTS` y Chromium por la huella SPKI del certificado que verifica esa CA. Nada más: sin `ignore_https_errors`, sin `--ignore-certificate-errors`, sin instalar la CA en el almacén del sistema |
| `--mount` de `evidence` en `/verification/evidence` | el único directorio donde la herramienta escribe (`--dir` por omisión). Sin este montaje, `prepare` termina con código 3 y `store_unwritable` |
| `--mount` de `case-management.yaml` (`readonly`) | el archivo de values que `prepare` parchea (`--values-file /values/case-management.yaml`) |
| `--mount` de `reference-model-out` (`readonly`) | la entrega del modelo de referencia (solo `decisions`, `rt3`, `rt2-setup` y `rt2`); `prepare --delivery /verification/reference-model/.out` guarda esa ruta en el manifiesto |
| `-e VAULT_ADDR -e VAULT_TOKEN` | sin valor: Docker toma las variables del entorno del proceso. El token no es un archivo ni va en la línea de órdenes |

El emisor del login es solo el público: `https://vectra.localtest.me/auth/realms/vectra` (`--issuer`, `--gateway-host`).

### Red: Linux, macOS y Windows

- **Linux (probado):** `--network host` comparte la red del host: el contenedor ve `127.0.0.1:<puerto>` de cada `port-forward` y de la API del kubeconfig, y `vectra.localtest.me` (que resuelve a `127.0.0.1`) llega al gateway de kind.
- **macOS y Windows con Docker Desktop (no probado):** `--network host` comparte la red de la **máquina virtual** de Docker, no la del Mac o del Windows; `127.0.0.1` dentro del contenedor no es el `127.0.0.1` del equipo y ni el gateway de kind ni los `port-forward` llegan. Con esta orden no hay camino comprobado; el operador debe correr la demo en una máquina Linux (o en una VM Linux con Docker y kind). Comprobar una alternativa queda **pendiente en U12-T06**.

### Los guiones, los `verify` y los PR

Todo está en la imagen, en `/opt/system-verification`: `demos/*.md` (los guiones), `demos/verify/*.sh`, `demos/prs/` (los parches de los PR y `entrada.py`, que arma el parche de la entrada `staging` de D1 y D2 con el `python3` de la imagen) y `report/story-map.yaml`. Para leerlos o sacarlos:

```sh
docker run --rm --entrypoint cat localhost:5001/vectra/system-verification:dev /opt/system-verification/demos/rt-5.md
docker run --rm --entrypoint cat localhost:5001/vectra/system-verification:dev /opt/system-verification/demos/prs/f22-apagado/apagar.patch > apagar.patch
```

Los `verify` corren en la misma imagen y con los mismos montajes del kubeconfig y de las evidencias (leen el `manifest.json` y las evidencias del directorio de la verificación):

```sh
docker run --rm --read-only --tmpfs /tmp --network host --user "$(id -u):$(id -g)" --memory 1g \
  --mount type=bind,source="$HOME/.kube/config",target=/kube/config,readonly -e KUBECONFIG=/kube/config \
  --mount type=bind,source="$PWD/evidence",target=/verification/evidence,readonly \
  --entrypoint sh localhost:5001/vectra/system-verification:dev /opt/system-verification/demos/verify/rt-5.sh 1
```

Salida de cada `verify`: 0 el estado esperado, 1 no lo es, 2 no se pudo leer. `journey-7-4.sh 5` y `dashboard.sh 5` leen además del `manifest.json` (`manifest_value`).

`entrada.py` lee los values que se le pasan y escribe el diff por la salida estándar; no escribe ningún archivo, así que corre con el sistema de archivos de solo lectura:

```sh
docker run --rm --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,source="$PWD/model-serving.yaml",target=/work/model-serving.yaml,readonly --workdir /work \
  --entrypoint python3 localhost:5001/vectra/system-verification:dev /opt/system-verification/demos/prs/entrada.py \
  --values /work/model-serving.yaml --version mv-AAAA-MM-DD-xxxxxxxx --storage-uri s3://model-store/<ruta>/ > entrada.patch
```

## Cómo correr cada sección

Con `vv` definido (arriba). Cada sección escribe en `evidence/`; `report` se puede correr en cualquier momento.

```sh
vv prepare --commit "$(git rev-parse --short HEAD)" --operator "su-nombre" --values-file /values/case-management.yaml \
    --delivery /verification/reference-model/.out
vv decisions                                  # D4, día D: antes de las 22:18 UTC
vv rt5                                        # D3
vv rt3                                        # D1
vv rt2-setup
vv rt2 --reactivation presenter               # D2; sin la opción, `tool`
vv u11                                        # D4, día D + 1, después de las 02:40 UTC
vv report
```

`prepare` pide `--commit` y `--operator` (no hay `git` en la imagen: se pasan por parámetro) y escribe `manifest.json` y `case-management-runid.patch` en `evidence/`; el operador abre con el parche el PR del `runId` (ver `demos/rt-5.md`) antes de `rt5`. `prepare` otra vez termina con código 3: para otra verificación, un directorio nuevo. Las barreras (emisor y host conocidos, `decisions` antes de las 23:00 UTC) se comprueban antes de la primera solicitud.

### Presupuesto de tiempo

Tiempos reales por demo (las esperas de los PR y de las sincronizaciones van aparte):

| Demo | Secciones | Tiempo real |
|---|---|---|
| D1 (`journey-7-3`) | `rt3` | 12,4 a 19,3 min hasta `no_disponible`; la herramienta espera hasta 25 min; `FailClosedPersistente` llega a `firing` unos minutos después y se sondea hasta 5 min tras la escalada. Aparte: dos PR con su sync (apagar y revertir F22) y el cierre `rt3 --closing` (≤ 15 min) |
| D2 (`journey-7-4`) | `rt2-setup`, `rt2` | más de 75 min con 1 versión del proxy, en 9 pasos (≈ 30 min más por las 2 corridas de bias de `no_recongela`). Aparte: 4 PR de promoción y 2 del proxy |
| D3 (`rt-5`) | `rt5` | segundos el Job; la alerta `CoreWriteAttempt` se ve ≈ 5 min en `firing` y se apaga sola |
| D4 (`dashboard`) | `decisions`, `u11` | `decisions` ≈ 42 min, el día D antes de las 22:18 UTC (barrera de las 23:00 UTC); `u11` el día D + 1, después de las 02:40 UTC (la pasada de U11 es a las 02:30 UTC más hasta 10 min). Aparte: Grafana por `port-forward` |

Son cifras de los guiones, no medidas en kind: U12-T06 las ensaya con reloj.

## Cómo leer el informe y su límite

`vv report` escribe `verification-report.md` con tres resultados por elemento y por historia: `pasa`, `falla` y `no ejecutado`. Una historia pasa si pasan **todas** sus evidencias, falla si alguna falla y queda `no ejecutado` en otro caso. US-304, US-503, US-504 y US-505 no son de U12: el informe las marca `demostrada`, no verificada. Cada línea trae el comando, lo esperado, lo obtenido y el hash de su archivo de evidencia.

**El límite:** el manifiesto (`manifest.json`) detecta alteraciones accidentales y archivos faltantes, pero no a quien edite la evidencia y el manifiesto a la vez. Esa protección la da la revisión del PR de verificación: `.github/CODEOWNERS` pide la revisión de dos personas para `system-verification/evidence/` (los equipos de calidad y de cumplimiento, cuando existan). El informe no sustituye a esa revisión.

### Qué saldrá `no ejecutado` y por qué

Con el recorte de la demo, el informe marcará `no ejecutado` lo siguiente, y es lo correcto según BR-U12-13:

| Qué | Por qué |
|---|---|
| US-106, US-109, US-604, US-608, US-609 y US-610 | sus evidencias (`RT-4`, `RT-1`, `X02`, `LOGS-NO-PII`, `RESTORE-DRILL`, `LOAD`, `READINESS`) son de secciones diferidas (`rt4`, `rt1`, `pii`, `resilience`, `load`) |
| US-603 | falta `X01`, aunque `RT-5` y `rt-5` pasen |
| US-305 | falta `X03`, aunque `RT-2` y `journey-7-4` pasen |
| `RT3-b` y «a y d desplegados» (de `rt3`) | se informan, pero no bajan el resultado de la sección |
| `RT2-LATENCY` con una sola medición | pasa con el máximo de las corridas hechas y el informe dice que fue una (una versión del proxy en la demo): no es una distribución |
| `X01` a `X10`, `CASE-SIZE` | son de las secciones diferidas |

## Trazabilidad y revisión

La tabla de BR-U12 a prueba está en `aidlc-docs/construction/system-verification/code/cli.md`; lo diferido por la demo, en `aidlc-docs/construction/system-verification/evidence/cierre-demo.md` (`make -C system-verification traceability`). `make -C system-verification check` corre todo, incluida la construcción de la imagen y su prueba (`check-fast` omite la imagen).

Quién revisa hoy: `.github/CODEOWNERS` nombra a dos personas, no a los equipos `calidad` y `cumplimiento` que pide el diseño.

## Pendiente en U12-T06 (solo se comprueba en kind)

El camino a la bóveda y K16 de verdad; el perfil `seccomp` que publica Playwright en vez de la copia de `containers-common`; las alternativas de red en macOS y Windows; el `--memory` de la imagen medido con 2 000 decisiones; los tiempos de las demos ensayados con reloj; el modo `presenter` con `cumplimiento-2`; las secciones contra el clúster real (`live.py`, que aquí solo se prueba con dobles dentro del contenedor).
