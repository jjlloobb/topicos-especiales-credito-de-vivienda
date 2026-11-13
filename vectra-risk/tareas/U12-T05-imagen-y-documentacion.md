# U12-T05 — Imagen, README y trazabilidad de `system-verification`

**Unidad:** U12 `system-verification`
**Historias que implementa:** ninguna propia. Empaqueta la herramienta de U12-T04 para que el operador la ejecute fuera del clúster (INF-U12-01) y documenta cómo. La usa el operador en kind (Paso 18, U12-T06).
**Depende de:**
- **U12-T04 fusionada en `main`** (PR #___, commit de fusión `_______`: **por completar al fusionar**). Su contrato es `tareas/U12-T04-demos-cli-y-manifiesto.md`, sección «Lo que U12-T05 y U12-T06 necesitan de esta tarea». **Al empezar, lee `aidlc-docs/construction/system-verification/code/cli.md`**: las opciones reales rigen sobre lo que esta tarea supone. Lo que se da por sentado:
  - el punto de entrada `vectra-verification`, con `--help` sin efectos, `prepare` sin solicitudes y los códigos de salida 0, 1, 2 y 3;
  - `store.py` como único escritor de `evidence/`;
  - `tests/unit/test_kubectl_verbs.py` ya ampliado (F-06): acepta el binario como ruta en un `Dockerfile` y recorre `README.md` y `Dockerfile` cuando existen;
  - `tests/unit/test_demos_closed_world.py` y los cuatro guiones con sus tiempos;
  - `Makefile` con `check: lint types imports test shellcheck links`.
- **U12-T02** (PR #___, **por completar**): `clients/oidc.py` con `ca_file`, `NODE_EXTRA_CA_CERTS` para Node y la huella SPKI para Chromium (líneas 113 a 178, leídas en `.claude/worktrees/u12-t02`, `639a22f`); Playwright 1.64.0 con Chromium revisión 1248 (`pyproject.toml` de la unidad; `clients.md`).
- **No depende** de U02-T22 ni de U00-T04.

Es una imagen, documentación y pruebas **sin clúster** (RL-5). Usa Docker local para construir y arrancar la imagen.
**Rama:** `tarea/U12-T05`, desde `origin/main` **después** de fusionar U12-T04.

Bloque F del plan de U12 (`aidlc-docs/construction/plans/system-verification-code-generation-plan.md`, Pasos 14, 15 y 17). La enmienda (`aidlc-docs/construction/plans/demo-recorte-funcional.md` §4, fila U12) juntaba «E+F (12, 13, 15, 17)». **El usuario la partió en dos el 2026-11-13** (P-1). U12 queda en **6 tareas**: T01 A+B (1–4) · T02 C (5–6) · T03 D (8, 10) · T04 E (12, 13) · **T05 F (14 N/A, 15, 17)** · T06 G+H (18–19). Esta es la quinta, la última antes de kind.

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 14 N/A | **N/A** | Se comprueba aquí (necesita la imagen) | Enmienda §3 U12, fila «14 · 15: N/A · E\*» |
| 15 Imagen | **E\*** | Se difieren escaneo, SBOM y firma | Alcance §3 U12, fila «14 N/A · 15 Imagen: N/A · E\*, T1»; T1: «Firma Cosign, SBOM y attestations de imágenes y paquetes. Las imágenes se construyen y se publican **por digest** en `kind-registry`» |
| 16 Workflow de CI | **D** | No entra | Enmienda §3 U12, fila «16: D, D»; alcance: T4 |
| 17 Documentación y trazabilidad | **E\*F** | README de lo que entra; trazabilidad con lista | Enmienda §3 U12, fila «17: E, E\*F, README de lo que entra; trazabilidad con lista» |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6. No hay PBT nuevas.

**Decisiones del usuario que rigen** (`DECISIONES-LOOP.md` §9 y §10, y las del 2026-11-13 sobre esta tarea):
- **Descargas autorizadas (P-8, 2026-11-13):** los paquetes del sistema para Chromium, el Chromium de la revisión que espera Playwright y `kubectl` de la versión fijada, **cada una con versión y SHA-256 comprobado**.
- **Emisor:** solo el público (`https://vectra.localtest.me/auth/realms/vectra`).
- **Memoria de kind:** `BUDGET_GIB = 11.8` (`platform/tests/test_kind_profile.py`, línea 34), con todo menos U12.
- **Grafana en D4** por `port-forward` con `grafana-admin` (P-2): el README lo dice entre los prerrequisitos.

**U12 no suma memoria al clúster.** Comprobado: no hay entrada de U12 en `vectra-risk-gitops/components.yaml` ni chart en `system-verification/`; el Paso 14 es N/A. La imagen **no** corre como Job: corre en la estación del operador (`deployment-architecture.md` §1). `BUDGET_GIB` no cambia. Sí usa memoria **del host**, que kind comparte (14 GiB): Chromium y Python. El README fija un límite (`--memory`, P-9) y U12-T06 lo mide.

**Lección que esta tarea aplica** (CA-4 de U11-T03): un `Dockerfile` que construye no prueba que el contenedor funcione. Aquí el contenedor real arranca con lo que el README manda (solo lectura, uid arbitrario, sandbox de Chromium, la CA montada) y ejecuta una sección contra dobles.

---

## Alcance

**Dentro:** los Pasos 15 y 17 del plan, y la comprobación del 14. Texto del plan, sin recortes salvo lo que el recorte difiere, que va ~~tachado~~ con su cita y en «Fuera»:

### Bloque F — Imagen, CI y documentación

- [ ] **Paso 14 — Repositorio, migraciones, frontend y despliegue en el clúster: N/A** (N/A; se comprueba aquí, CA-1)
  - U12 no tiene base de datos, interfaz ni recursos de Kubernetes.
  - **Aceptación**: `test ! -d system-verification/chart && test ! -d system-verification/migrations`; la imagen no contiene manifiestos de Kubernetes.

- [ ] **Paso 15 — Imagen** (E\*)
  - Python oficial por digest, sin privilegios; incluye `kubectl`, Playwright y su Chromium por versión fijada (el Chromium sin interfaz del login del Paso 5). **k6 no va en esta imagen** (pendientes posteriores al cierre, 2026-10-10): corre en su propio contenedor (`grafana/k6` por digest), con límites de 2 CPU y 2 GiB, que **el operador** lanza en la red de kind con el comando que imprime la sección `load` (Paso 11, INF-U12-05; pendientes consolidados, segunda tanda, 2026-10-10);
  - **sandbox de Chromium** (pendientes posteriores al cierre, 2026-10-10): el contenedor corre como usuario no root con el perfil `seccomp` que publica Playwright para Chromium (`chrome.json`) y espacios de nombres de usuario sin privilegios; **nunca** con `--no-sandbox`. Si el host no los permite, la sección que necesita login termina con un error claro;
  - la imagen se construye, ~~se escanea, lleva SBOM y se firma con `sign-image.yml` de U1~~ (frase separada, pendientes consolidados, 2026-10-10). **(Diferido por la demo, T1: alcance §3 U12, fila «14 N/A · 15 Imagen: N/A · E\*, T1»; T1: «Firma Cosign, SBOM y attestations de imágenes y paquetes». El escaneo se difiere con el mismo criterio que en U11-T03, U08-T05 y U10-T05; ver «Contradicciones» 14.)**
  - Diseño: INF-U12-01.
  - **Aceptación**: `hadolint system-verification/Dockerfile`; ~~el SBOM lista `kubectl`, Playwright y Chromium con su versión y **no** `k6`;~~ prueba de humo: Chromium arranca con el sandbox activo bajo el perfil `seccomp` (`chrome://sandbox` sin errores). **(Sin SBOM, T1. Las versiones y la ausencia de `k6` se comprueban dentro de la imagen, CA-2, como «sin numpy» en U9: enmienda §3 U9, fila «11».)**

- [ ] ~~**Paso 16 — Workflow de CI**~~ **(Diferido por la demo: enmienda §3 U12, fila «16: D, D»; T4. No entra; ver «Fuera».)**

- [ ] **Paso 17 — Documentación y trazabilidad** (E\*F)
  - `system-verification/README.md`: cómo ejecutar cada sección, requisitos (K16, PRs preparados, `runId` de los Jobs en formato `AAAAMMDD-HHMM` y el sync manual de las ~~**tres Applications** `bias-monitoring`, `decision-registry-rebuild` y~~ `case-management`; pendientes consolidados, 2026-10-10), presupuesto de tiempo (con las esperas de PRs aparte), cómo leer el informe y su límite. **(Solo `case-management`: enmienda §3 U12, fila «13». «README de lo que entra»: enmienda §3 U12, fila «17».)**
  - El README dice también cómo llegan al contenedor el kubeconfig, el certificado raíz y la sesión de Vault **sin escribirse en disco** (montajes de solo lectura del kubeconfig y del certificado; token de Vault como variable de entorno; sistema de archivos de solo lectura salvo el directorio de evidencias y un `tmpfs`; deployment-architecture §2b),~~ y cómo lanzar el contenedor de k6 con sus límites~~ (pendientes posteriores al cierre, 2026-10-10). **(k6 es de la sección `load`, Paso 11, diferido: enmienda §3 U12, filas «8b · 9 · 11: D» y «17: README de lo que entra».)**
  - Trazabilidad de cada BR-U12 a una prueba. **(Con la lista «Diferido por la demo»: enmienda §3 U12, fila «17»: «trazabilidad con lista»; §2, regla 4.)**
  - **Aceptación**: `test -s system-verification/README.md`; `uv run python platform/tests/test_traceability.py --unit system-verification --all`.

### Estructura de destino (§1 del plan): lo que esta tarea crea o llena

```text
vectra-risk/system-verification/
|-- Makefile                                         # se modifica: `image`, `test-image`, `traceability`, `check-fast`
|-- Dockerfile  Dockerfile.dockerignore  README.md   # nuevos (Pasos 15 y 17)
|-- seccomp/chrome.json                              # nuevo: el perfil que publica Playwright, con su origen y su SHA-256
`-- tests/
    |-- unit/   test_demos_closed_world.py           # se amplia: el README
    `-- image/  test_image.py                        # fuera de `make test`: lo corre `make test-image`

vectra-risk/aidlc-docs/construction/system-verification/code/cli.md                  # se amplia: tabla BR-U12-01 a 13 -> prueba, completa
vectra-risk/aidlc-docs/construction/system-verification/evidence/cierre-demo.md      # nuevo, SOLO la seccion «Diferido por la demo» (CA-8)
```

**No** se crean: `chart/` ni `migrations/` (Paso 14); `.github/workflows/system-verification.yml` (Paso 16). `src/` solo cambia si la imagen revela un defecto (uid arbitrario, `HOME`, rutas): anótalo.

### Cambios permitidos fuera de `system-verification/`

Uno por uno. Cualquier otro archivo fuera del directorio es un hallazgo.

1. `aidlc-docs/construction/plans/system-verification-code-generation-plan.md`: solo las casillas de los Pasos 14, 15, 16 y 17 (CA-11).
2. `aidlc-docs/construction/system-verification/code/cli.md`: la tabla de trazabilidad completa y la sección de la imagen.
3. `aidlc-docs/construction/system-verification/evidence/cierre-demo.md`: nuevo, con el encabezado «en curso; lo completa U12-T06» y **solo** la sección `## Diferido por la demo`. La necesita la aceptación del Paso 17.
4. `.github/CODEOWNERS`: **no cambia** (P-7).
5. `CANDIDATAS.md` y `bitacoras/U12-T05.md` (nuevo).
6. `uv.lock` y `pyproject.toml` raíz: no cambian.

Todo lo demás **se lee, no se edita**: `platform/`, `vectra-risk-gitops/`, `case-management/`, `identity-edge/` y `contracts/`. **Publicar la imagen (push y digest) es del operador** (U12-T06).

### Precisiones

**Paso 15 — imagen** (INF-U12-01; NFR-U12-01, 04)

- `system-verification/Dockerfile`, multi-etapa, contexto en la raíz de `vectra-risk/`; cada `FROM` por digest (el de los demás: `docker.io/library/python:3.12-slim@sha256:aa943ce4…`, `product-metrics/Dockerfile`, línea 6). Sin `vectra_common`.
- **Usuario sin root y uid arbitrario.** `USER 65532:65532`, pero el operador la corre con `--user "$(id -u):$(id -g)"` para poder escribir en el directorio de evidencias de su checkout. La imagen debe funcionar con **cualquier** uid sin root: `HOME` en el `tmpfs`, y los navegadores en una ruta legible por todos (`PLAYWRIGHT_BROWSERS_PATH`).
- **Sistema de archivos de solo lectura:** `--read-only`, con el directorio de evidencias montado y un `tmpfs`.
- **Playwright 1.64.0 con el Chromium de su revisión (1248)**, instalado en la construcción; ningún otro navegador.
- **Descargas de la construcción** (P-8, autorizadas por el usuario el 2026-11-13): los paquetes del sistema que Chromium necesita, con versión fija; Chromium 1248 para Linux; y el binario de `kubectl`. **Cada una con su SHA-256 comprobado en el `Dockerfile`** (los paquetes, por versión exacta del repositorio de la imagen base, que ya va por digest). La suma de `chrome.json` va en el README. La base de Python ya está en el Docker local.
- **Sandbox:** perfil `seccomp/chrome.json` y espacios de nombres de usuario; **nunca** `--no-sandbox`. Sin ellos, error claro.
- **CA para los dos caminos TLS** (F-02 de `revisiones/U12-T02/ronda-1.md`): el archivo montado se pasa como `ca_file`; Node lo recibe por `NODE_EXTRA_CA_CERTS` y Chromium por la huella SPKI que U12-T02 calcula con esa CA. **Nada más:** sin `ignore_https_errors`, sin `--ignore-certificate-errors` a secas, sin `NODE_TLS_REJECT_UNAUTHORIZED`, sin instalar la CA en el almacén del sistema.
- **`kubectl` de la versión del clúster** (`platform/kind/cluster.yaml`, línea 18: `kindest/node:v1.37.0`), con su SHA-256 verificado en la construcción. **Sin** el binario de Argo CD, sin `helm`, sin `k6`, sin `git`, sin manifiestos de Kubernetes.
- **Red:** en kind, `vectra.localtest.me`, la API de Kubernetes del kubeconfig y los `port-forward` son `127.0.0.1` del host: el contenedor corre con `--network host`. El README lo dice.
- `docs` de la imagen dentro del README: construir, comprobar y la orden `docker run` completa. **Publicarla (push y digest) es del operador** (U12-T06); aquí no se hace.

**Paso 17 — README y trazabilidad**

- `README.md` de lo que entra: las 8 secciones con su orden y sus códigos de salida, y la opción `--reactivation` de `rt2` con sus dos modos (P-12); las 6 diferidas; prerrequisitos del operador (abajo); la orden `docker run`; **los tiempos reales de cada demo**; cómo leer el informe y su límite; y **qué marcará `no ejecutado` y por qué**: US-106, 109, 604, 608, 609 y 610 (secciones diferidas), US-603 (falta `X01`) y US-305 (falta `X03`) aunque RT-5 y `journey-7-4` pasen, RT3-b y «a y d desplegados», y `RT2-LATENCY` con 1 medición (`CANDIDATAS.md`, línea 641).
- **Prerrequisitos del operador:** U1 a U11 instalados con digests reales; política y modelo de referencia activos; paquetes proxy y RT-3 en el model-store (`model-serving/docs/paso-11-kind.md`, línea 55); K16; **el camino a la bóveda** (P-9); el certificado raíz exportado; las semillas TOTP que el presentador necesita en su teléfono (`analista-2` o `cro-2` en D1 y `cumplimiento-2` en D2; P-11); la cuenta `grafana-admin` y el `port-forward` a Grafana para D4 (P-2); el eco de U2 y la `ServiceAccount` temporal de U4 retirados; `CASE_ALLOW_TEST_SCENARIOS` (`allowTestScenarios: true`, ya en los values de kind).
- **Trazabilidad:** tabla BR-U12-01 a 13 → prueba, en `cli.md`. La lista «Diferido por la demo» en `evidence/cierre-demo.md`, con el formato de `platform/tests/test_traceability.py` (líneas 13 y 14): identificador, paso del plan, cita, qué falta. Tras U12-T04 queda sin trazar INF-U12-05 (Paso 11, diferido): **va en la lista**. INF-U12-04 y NFR-U12-31 los trazó U12-T04. Comprueba el conjunto en tu rama.
- **`Makefile`:** `check: lint types imports test shellcheck image test-image links traceability` (`links` y `shellcheck` vienen de U12-T04). `test` ignora `tests/image/`. Se agrega `check-fast` (sin `image` ni `test-image`) para el ciclo corto; el revisor corre `check`.

**Plan.** Marca `[x]` con `(U12-T05)` los Pasos 15 y 17, con sus notas (15: «sin escaneo, SBOM ni firma (T1)»; 17: «README de lo que entra; trazabilidad con lista»). El 14, `[x]` con `(U12-T05)` y «N/A comprobado». El 16 sigue en `[ ]` con «(diferido por la demo: enmienda §3 U12)» antes del título, como hace el plan de U6 con su Paso 9.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Escaneo, SBOM y firma de la imagen**, y la línea de aceptación del SBOM. T1; alcance §3 U12, fila «14 N/A · 15 Imagen: N/A · E\*, T1».
- **k6:** ni en la imagen ni en el README. Paso 11, diferido (enmienda §3 U12, filas «8b · 9 · 11: D» y «17: README de lo que entra»).
- **Las Applications `bias-monitoring` y `decision-registry-rebuild` en el README.** Enmienda §3 U12, fila «13»: «El parche de `prepare` solo toca `case-management` (sin `bias-monitoring` ni `decision-registry-rebuild`)».
- **Paso 16** (workflow de CI) y `mutmut`. T4 y T3.
- **Pasos 12 y 13:** guiones, `verify`, PR preparados, CLI y manifiesto. Son de U12-T04; si la imagen revela un defecto suyo, se corrige lo mínimo y se anota.
- **Publicar la imagen** (push y digest) y **ejecutar una sección contra kind.** U12-T06 y el operador.
- **Editar otras unidades:** no se amplía K16 para la bóveda, no se configura el OIDC de Grafana.
- **Pasos 18 y 19:** la verificación en kind, el resto de `cierre-demo.md` y el cierre.
- **Cualquier llamada a un clúster.**

---

## Candidatas (`CANDIDATAS.md`)

Números de línea de `main` (`8dc7499`); las de la rama `tarea/U12-T02` se citan por su hallazgo.

**Se atienden aquí:**

| Dónde | Candidata | Qué se hace |
|---|---|---|
| Rama T02, F-02 de la ronda 1 | La CA para Node y para Chromium en la imagen, «y nada más» | CA-5 |
| Línea 641 | El informe marcará `no ejecutado` varias historias | La tabla del README (CA-6) |
| Línea 640 | K16 y el camino a la bóveda de kind | Solo el README (P-9): cómo lo hace el operador en kind y que no es K16. La candidata de U1 sigue abierta |
| Línea 520 | Arrancar un contenedor con `--read-only` | Aquí se hace para U12 (CA-3) |

**Para U12-T06** (no las atiendas; van en «Lo que U12-T06 necesita»):

- Línea 640 y rama T02 (F-06 de la ronda 1): K16 y el camino a la bóveda; la lista de hosts de la bóveda es global.
- Líneas 684 y 615, y `case-management/docs/imagenes.md`: digests de ejemplo e `ImagePullBackOff`.
- Rama T02: selectores y puertos de Prometheus y Loki, sin comprobar.
- Líneas 402 y 412: el eco de U2 y la `ServiceAccount` temporal `console-bff` de U4.
- Línea 598: `product-metrics` arranca antes que el registro.
- Líneas 619 y 679: memoria real de U8 y del BFF con 2 000 decisiones.
- Líneas 631, 659 y 675: CSP real, `/callback` y el `iss` de cada destino.
- Línea 689: las etiquetas reales de la serie del proxy de Linkerd.
- Línea 634: las constantes de la estimación de `decisions` (1 s por caso, 300 s).

**Se quedan:** líneas 636, 638 y 642 (textos del diseño), 579 (`channel: "chromium"`, de U10), 40, 47 y 48 (OIDC de Grafana, U1).

---

## Contradicciones entre plan, recorte, diseño y `main`

Las de los guiones y la CLI están en U12-T04. Deja en `CANDIDATAS.md` las que no estén ya.

1. **La imagen no alcanza nada sin `--network host`, ni escribe evidencias con el uid 65532.** `deployment-architecture.md` §2b habla de montajes y variables, no de la red ni del uid. En kind, el gateway (`vectra.localtest.me`), la API de Kubernetes del kubeconfig y la bóveda reenviada son `127.0.0.1` del host, y el checkout es del uid del operador. Sin esto, la herramienta falla en el primer paso delante del público.
2. **K16 no da camino a la bóveda** (`CANDIDATAS.md`, línea 640). `credentials.ALLOWED_VAULT_HOSTS` admite `127.0.0.1` (`credentials.py`, línea 31), pero K16 no da `port-forward` en `vault`. En kind el kubeconfig del operador es de administrador y funciona; no por K16. P-9.
3. **El detector de verbos recorre el `Dockerfile` y el `README.md`.** `kubectl version --client` dentro del `Dockerfile` sería un hallazgo (el verbo no está permitido): la comprobación de la versión va en `tests/image/`, que el detector no recorre. El nombre del binario de Argo CD no puede aparecer en el README seguido de texto: se escribe «Argo CD».
4. **T1 no nombra el escaneo.** Dice «Firma Cosign, SBOM y attestations». Las tareas de despliegue fusionadas (U11-T03, U08-T05 y U10-T05) difirieron también el escaneo con esa cita. Aquí se sigue el precedente.
5. **`CODEOWNERS`: el plan (INF-U12-04) pide los equipos `calidad` y `cumplimiento`; `main` tiene dos personas** (`.github/CODEOWNERS`, línea 9). El README dice quién revisa hoy. P-7.
6. **NFR-U12-31 presupuesta «6 a 8 h»** con 5 corridas y carga. Con el recorte: D1 ≈ 25 min, D2 > 75 min, D4 ≈ 42 min más el día siguiente. El README da las cifras reales, tomadas de los guiones.
7. **El Paso 17 y `deployment-architecture.md` §2 hablan de tres Applications**; con el recorte es una, y `decision-registry-rebuild` no existe en `components.yaml`.
8. **INF-U12-01 dice «publicada en el registro del banco; el operador la ejecuta por digest».** En kind se publica en `kind-registry` (T1) y eso lo hace el operador en U12-T06: esta tarea solo la construye con la etiqueta local `localhost:5001/vectra/system-verification:dev`, como las demás unidades.
9. **El plan no dice qué versión de `kubectl`.** «Por versión fijada» sin número. Aquí: la del nodo de kind (`platform/kind/cluster.yaml`, línea 18: v1.37.0); `platform/tools.env` no trae `kubectl`.

---

## Preguntas

**Todas resueltas. No queda ninguna que necesite al usuario.** La numeración es la de la versión única (PR #165).

- **P-1 — ¿Se parte la tarea?** **Decidido por el usuario (2026-11-13): sí.** Esta es la mitad del Bloque F.
- **P-8 — Descargas para construir la imagen.** **Autorizadas por el usuario (2026-11-13):** paquetes del sistema para Chromium, Chromium de la revisión 1248 y `kubectl` de la versión fijada, cada una con versión y SHA-256 comprobado. `hadolint` sale de `platform/install-tools.sh`; `shellcheck`, de `uvx --from shellcheck-py`, como en `governance/Makefile`, línea 83.
- **P-2 — Grafana en D4.** **Decidido por el usuario (2026-11-13):** `port-forward` con `grafana-admin`. Aquí solo afecta a los prerrequisitos del README.
- **P-12 — Reactivación de D2.** **Decidido por el usuario (2026-11-13):** opción de la herramienta (U12-T04). Aquí solo afecta al README.
- **P-7 — `CODEOWNERS`.** Rige la recomendación: no tocarlo.
- **P-9 — Camino a la bóveda y límite de memoria.** Rige la recomendación: en kind el operador reenvía la bóveda con su kubeconfig de administrador y pasa `VAULT_ADDR=http://127.0.0.1:<puerto>`; el README dice que no es K16. `--memory 1g` como valor de partida, a medir en U12-T06.
- **P-10 — `commit` y operador.** Rige la recomendación: por parámetro; la imagen no trae `git`.
- **P-11 — Usuarios del presentador.** Rige la recomendación: los «-2». Aquí, en los prerrequisitos del README.
- P-3, P-4, P-5, P-6 y P-13 son de U12-T04.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/system-verification-code-generation-plan.md` (§1, Bloque F, y los Pasos 18 y 19)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2, §3 U12, §8) y `demo-kind-alcance.md` (§2 con T1 a T6, §3 U12, §6)
- `DECISIONES-LOOP.md` (§6, §9 y §10)
- `aidlc-docs/construction/system-verification/`: `infrastructure-design.md` (INF-U12-01, 03 y 04), `deployment-architecture.md` (§1, §2 y §2b), `nfr-requirements.md` (NFR-U12-01, 04, 10, 20, 21, 31) y `tech-stack-decisions.md`
- `aidlc-docs/construction/system-verification/code/`: `cli.md`, `clients.md` y `scenarios.md`
- `tareas/U12-T04-demos-cli-y-manifiesto.md`; para la imagen, `tareas/U11-T03-despliegue-y-cierre.md` (CA-4), `product-metrics/Dockerfile` y `product-metrics/tests/integration/test_image.py`
- `revisiones/U12-T02/ronda-1.md` (F-02) y `system-verification/src/vectra_verification/clients/oidc.py`
- `system-verification/demos/*.md` (los tiempos y prerrequisitos que el README resume)
- Los «Pendiente en U12» de `aidlc-docs/construction/{case-management,console,product-metrics}/evidence/cierre-demo.md` y `platform-foundation/evidence/cierre-acotado.md`
- `platform/tests/test_traceability.py` (líneas 13, 14 y 49 a 60: el formato de la lista)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`. Ninguno usa un clúster. Ninguno admite pruebas omitidas ni `xfail`: sin Docker, la prueba **falla**. `H=platform/.tools/bin` (tras `bash platform/install-tools.sh`).

### Bloque F (Pasos 14, 15 y 17)

- [ ] **CA-1** — Paso 14, N/A.
  ```bash
  test ! -d system-verification/chart && test ! -d system-verification/migrations && ! grep -n "system-verification" vectra-risk-gitops/components.yaml; echo "rc=$?"
  ```
  Esperado: `rc=0`. «La imagen no contiene manifiestos de Kubernetes» lo comprueba CA-2.

- [ ] **CA-2** — La imagen: `hadolint`, base por digest y contenido.
  ```bash
  $H/hadolint system-verification/Dockerfile && ! grep -nE "^FROM " system-verification/Dockerfile | grep -v "@sha256:" && ! grep -rnE "no-sandbox|ignore_https_errors|ignore-certificate-errors([^-]|$)|NODE_TLS_REJECT_UNAUTHORIZED" system-verification/Dockerfile system-verification/src && make -C system-verification image && docker image inspect localhost:5001/vectra/system-verification:dev --format '{{.Id}} {{.Size}}' && uv run pytest system-verification/tests/image/test_image.py -v -k content
  ```
  Esperado: código 0. Dentro de la imagen: Python 3.12; `playwright` 1.64.0 y **solo** Chromium, revisión 1248; `kubectl` v1.37.x; `vectra_verification` y `vectra_contracts` instalados y **no** `vectra_common`; **no** existen los binarios de Argo CD, `helm`, `k6`, `git` ni `curl`; ningún archivo con `apiVersion:` y `kind:` (manifiestos); usuario por omisión 65532; ningún archivo con permisos de escritura para otros fuera de `/tmp`. Cada descarga de la construcción (paquetes del sistema de Chromium por versión, Chromium 1248, `kubectl` v1.37.x) lleva versión fija y **SHA-256 comprobado en el `Dockerfile`** (P-8, usuario, 2026-11-13): una prueba cambia un dígito de cada suma y la construcción debe fallar. **Rojo primero:** un `FROM` por etiqueta falla la segunda orden.

- [ ] **CA-3** — El contenedor real arranca (lección de CA-4 de U11-T03).
  ```bash
  uv run pytest system-verification/tests/image/test_image.py -v -k run
  ```
  Esperado: pasan, con `docker run --rm --read-only --tmpfs /tmp --user 12345:12345 --memory 1g` y el directorio de la verificación montado desde el worktree:
  - `--help` → 0, y el directorio montado sigue vacío;
  - `prepare` → 0: `manifest.json` y el parche aparecen en el directorio montado, con dueño 12345, y pasan el filtro;
  - `prepare` otra vez → 3;
  - sin el montaje de evidencias → error claro, no una traza;
  - `rt5` contra dobles (un `kubectl` de doble montado por delante en el `PATH` y un Prometheus de doble en un puerto libre) → escribe `RT-5` y `rt-5`; el `kubectl` real de la imagen responde a `version --client`;
  - el contenedor no deja ningún archivo fuera del montaje y del `tmpfs`.

  Registra la orden `docker run` exacta y la memoria del contenedor. **Rojo primero:** con `--user 12345` y `HOME` sin definir en el `tmpfs`, Playwright no arranca; regístralo.

- [ ] **CA-4** — Chromium con el sandbox activo (aceptación del Paso 15).
  ```bash
  uv run pytest system-verification/tests/image/test_image.py -v -k sandbox
  ```
  Esperado: pasan: con `--security-opt seccomp=system-verification/seccomp/chrome.json`, Chromium arranca sin interfaz, `chrome://sandbox` no informa errores y la línea de órdenes del proceso no trae `--no-sandbox`; **sin** el perfil, la sección que necesita login termina con un error claro y código 2, no colgada. `seccomp/chrome.json` lleva en un comentario del README su origen y su SHA-256.

- [ ] **CA-5** — La CA en los dos caminos TLS, y nada más (F-02 de U12-T02).
  ```bash
  uv run pytest system-verification/tests/image/test_image.py -v -k tls
  ```
  Esperado: pasan, con un servidor HTTPS de prueba cuyo certificado firma una CA generada en la prueba, y el formulario de login de U12-T02 corriendo **dentro del contenedor**:
  - con esa CA montada: la navegación (Node) y un subrecurso (Chromium) cargan;
  - con **otra** CA montada: fallan los dos, con `OidcError`;
  - sin CA: fallan los dos;
  - un certificado válido para otro nombre: fallan los dos;
  - el almacén de CA del sistema de la imagen no cambia entre corridas.

  **Rojo primero:** pasar solo `NODE_EXTRA_CA_CERTS` (sin la huella de Chromium) hace fallar el subrecurso; regístralo.

- [ ] **CA-6** — README (Paso 17).
  ```bash
  test -s system-verification/README.md && uv run pytest system-verification/tests/unit/test_demos_closed_world.py -v -k readme && uv run pytest system-verification/tests/unit/test_kubectl_verbs.py -v
  ```
  Esperado: pasan. El README tiene: las 8 secciones en orden y las 6 diferidas; la orden `docker run` con `--read-only`, `--tmpfs`, `--network host`, `--user`, `--security-opt seccomp=`, `--memory`, el kubeconfig y el certificado en solo lectura, y el token de la bóveda **como variable, no como archivo**; los tiempos reales de las cuatro demos; los prerrequisitos de Precisiones; «cómo leer el informe» con su límite; y la tabla «Qué saldrá `no ejecutado` y por qué». La prueba comprueba que cada opción de la orden existe en la CLI, que la orden es la misma que usa `test_image.py`, y que no aparece `k6` ni las Applications diferidas. La prueba de verbos de U12-T04 recorre ya el `README.md` y el `Dockerfile` reales y pasa (la prosa nombra el binario solo, en código en línea).

- [ ] **CA-7** — `CODEOWNERS`.
  ```bash
  grep -n "vectra-risk/system-verification/evidence/" ../.github/CODEOWNERS && git diff origin/main...HEAD --stat -- ../.github/CODEOWNERS
  ```
  Esperado: una línea, y el `--stat` vacío (P-7 (a)). El encabezado del informe ya nombra `CODEOWNERS` (CA-13 de U12-T04).

- [ ] **CA-8** — Trazabilidad con la lista (Paso 17; `DECISIONES-LOOP.md` §6).
  ```bash
  uv run python platform/tests/test_traceability.py --unit system-verification --all; echo "rc=$?"; grep -n "^## Diferido por la demo" -A8 aidlc-docs/construction/system-verification/evidence/cierre-demo.md; uv run python platform/tests/test_traceability.py --all
  ```
  Esperado: `rc=0`. La lista trae INF-U12-05 (Paso 11) y solo identificadores sin código ni prueba, cada uno con su paso y su cita. INF-U12-04 y NFR-U12-31 quedan **trazados**, no en la lista. El segundo `--all` da, para las demás unidades, el mismo conjunto que en la base. `cli.md` trae la tabla BR-U12-01 a 13 → prueba, y las BR diferidas (05, 08, 08b y 12) dicen «diferida» con su cita.

- [ ] **CA-9** — Enlaces y frases prohibidas.
  ```bash
  uv run python platform/tests/test_links.py && uv run python contracts/tools/forbidden_phrases.py system-verification/README.md system-verification/demos/*.md
  ```
  Esperado: los dos en 0.

### Comunes

- [ ] **CA-10** — Cobertura al umbral del plan (NFR-U12-40).
  ```bash
  uv run pytest system-verification/tests --ignore=system-verification/tests/image --cov=vectra_verification --cov-branch --cov-fail-under=85 && uv run pytest system-verification/tests/unit system-verification/tests/property --cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100 && uv run lint-imports --config system-verification/.importlinter
  ```
  Esperado: los tres en 0; los contratos de imports, los mismos que dejó U12-T04. Sin `# pragma: no cover` nuevos.

- [ ] **CA-11** — Plan.
  ```bash
  grep -nE "^- \[x\] \*\*Paso (12|13|14|15|17) " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; grep -nE "^- \[ \] .*\*\*Paso 16 " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; git diff origin/main...HEAD -- aidlc-docs/construction/plans/system-verification-code-generation-plan.md | grep -E "^[-+]- \["
  ```
  Esperado: cinco líneas marcadas (12 y 13 con `(U12-T04)`, ya en `main`; 14, 15 y 17 con `(U12-T05)` y sus notas); el 16 sin marcar, con su nota de diferido; el diff muestra solo las casillas de los Pasos 14, 15, 16 y 17.

- [ ] **CA-12** — `check` de la unidad, con su tiempo, y sin contenedores huérfanos (RL-4).
  ```bash
  uptime; time make -C system-verification check; uptime; time make -C system-verification check-fast; docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' | grep -iE "u12t05|keycloak|prometheus|postgres"; echo "restantes=$?"
  ```
  Esperado: los dos en 0 y `restantes=1` (o solo los que ya estaban: lístalos antes). `check` es `lint types imports test shellcheck image test-image links traceability`; `check-fast`, lo mismo sin `image` ni `test-image`. Referencia: ≈ 10 a 11 min en U12-T02; menos de 17 esperados tras U12-T04. **Esta tarea añade** (estimación, sin medir): construir la imagen, 5 a 8 min sin caché y ≈ 1 min con ella; `test-image`, 2 a 3 min. Total esperado de `check`: **≈ 20 min** con caché, hasta 30 sin ella y con carga. Anota los tiempos reales y los `uptime`.

- [ ] **CA-13** — Lock y alcance del diff.
  ```bash
  uv lock --check && git diff --name-only origin/main...HEAD | grep -vE "^vectra-risk/(system-verification/|CANDIDATAS\.md$|bitacoras/U12-T05\.md$|aidlc-docs/construction/system-verification/code/|aidlc-docs/construction/system-verification/evidence/cierre-demo\.md$|aidlc-docs/construction/plans/system-verification-code-generation-plan\.md$)"; echo "fuera=$?"; git diff origin/main...HEAD --stat -- vectra-risk/uv.lock vectra-risk/system-verification/demos vectra-risk/system-verification/src; ls system-verification/evidence
  ```
  Esperado: `uv lock --check` en 0; `fuera=1`; `uv.lock` sin cambios; `demos/` y `src/` sin cambios, o los mínimos que la imagen exigió, explicados en la bitácora; `evidence/` solo con `.gitkeep`.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/image/test_image.py` (CA-2 a CA-5).
- `tests/unit/test_demos_closed_world.py`, ampliada al README (CA-6).
- **Rojo primero:** antes de cada arreglo, reproduce el fallo y regístralo en `bitacoras/U12-T05.md`; como mínimo los nombrados en CA-2, CA-3 y CA-5. Las mutaciones nombradas son un mínimo: el revisor traerá otras.
- **Lo que el revisor suele encontrar en las imágenes** (U11-T03, U08-T05, U10-T05): una prueba que pasa con una imagen vieja (`check` construye **antes** de `test-image`); un contenedor que arranca como root sin que nadie lo mire; una orden del README que no es la que la prueba ejecuta.

---

## Restricciones del entorno

Las de U12-T02 y U12-T03, más las de la imagen:

- **No copies el repositorio a `/tmp`.** Es un tmpfs con cuota. Temporales dentro del worktree, en una carpeta sin versionar (`platform/.tools/tmp/u12t05/`): `TMPDIR`, el directorio de verificación de las pruebas y el contexto de Docker.
- **Máquina compartida y muy cargada.** Al redactar: `load average: 11.95, 15.42, 15.07` y ≈ 4 GiB disponibles de 14. Anota `uptime` con cada medida. **Las esperas usan el reloj inyectado, nunca `sleep` real.** Una prueba que falla por tiempo se repite en frío antes de darla por rota. No corras `make -C platform check` ni las suites de otras unidades: ninguna.
- **Docker es compartido** con kind (`vectra-control-plane`, `vectra-worker`, `vectra-worker2`, `kind-registry` en `127.0.0.1:5001`) y con otros codificadores. Contenedores con el prefijo `u12t05-`, puertos al azar, `--memory` siempre. **Bórralos al terminar**, también tras una corrida interrumpida. Nada de `docker system prune`. **No publiques la imagen** en `kind-registry`.
- **Las pruebas de la imagen usan `--network host`** solo si el doble lo exige; aun así, puertos libres pedidos al sistema. Nunca 443, 8080, 8081, 8443, 8200 ni 9090.
- **Sin clúster.** Hay un kubeconfig que funciona: **no lo uses**. Ninguna prueba ejecuta el `kubectl` del host ni llama a `vectra.localtest.me`. El `kubectl` de la imagen solo corre `version --client`.
- **Descargas:** solo las autorizadas en P-8 (usuario, 2026-11-13): paquetes del sistema para Chromium, Chromium de la revisión 1248 y `kubectl` v1.37.x, cada una con versión y SHA-256 comprobado. Ninguna otra. Las imágenes de Keycloak, config-cli, PostgreSQL y Prometheus ya están.
- **Navegadores del host:** `make test` sigue usando `~/.cache/ms-playwright` (revisión 1248). No los borres ni reinstales; nada de `sudo`. La imagen instala los suyos en la construcción.
- **No toques el árbol principal ni otros worktrees.** No uses `git stash` sin etiqueta.
- **Otros codificadores en paralelo:** U02-T22 (`identity-edge/`) y U00-T04 (`contracts/`). Esta tarea no toca ninguno de los dos. **U12-T04 debe estar en `main`** antes de crear la rama. Si otra tarea toca `uv.lock`, el orquestador fusiona `origin/main`.

---

---

## Notas

- **Orden sugerido:** (1) leer `cli.md`; (2) prueba de concepto: Chromium con sandbox, uid arbitrario y solo lectura, **antes** de escribir nada más (es lo de más riesgo); (3) `Dockerfile` con las descargas verificadas; (4) `test_image.py`: contenido, arranque, sandbox y TLS; (5) README y su prueba; (6) lista «Diferido por la demo», tabla de trazabilidad, `Makefile`, plan y bitácora.
- Archivos que se **modifican en su sitio**: `Makefile`, `test_demos_closed_world.py`, `cli.md`, el plan y `CANDIDATAS.md`. Nada de duplicados con sufijo.
- **Etiqueta local:** `localhost:5001/vectra/system-verification:dev`. `check` construye la imagen **antes** de `test-image`. No se publica.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` dentro de `system-verification/`.
- **Enlaces:** `test_links.py` lee como enlace un corchete cerrado seguido de un paréntesis. Cuidado con los patrones de `grep` en el README y la bitácora.
- **Candidatas nuevas** que esta tarea deja, si no están ya: «Contradicciones» 1, 2, 8 y 9; y lo que la imagen revele.
- **Bitácora** `bitacoras/U12-T05.md`: la salida real de cada comando; los pares falla-pasa; **la versión y el SHA-256 de cada descarga**, con su origen; el digest local y el tamaño de la imagen; la orden `docker run` exacta y la memoria del contenedor; el tiempo de cada `make check` con sus `uptime`; los contenedores antes y después. **Ningún secreto.**
- U12 no tiene datos propios ni recursos en el clúster: no hay migraciones, chart ni nada que limpiar en kind.

### Lo que U12-T06 necesita

U12-T06 (Pasos 18 y 19) es la verificación consolidada (enmienda §8). Recibe de U12-T04 la CLI, los guiones con sus `verify` y los PR preparados, y de esta tarea la imagen y el README. Esta es la lista completa; U12-T04 remite aquí. **Lo que solo se puede comprobar en kind**, reunido de los cierres y de las candidatas:

- **Antes de nada**
  - U02-T22 en `main` y el realm reimportado; la reparación de `keycloak_tc.py` retirada si no lo hizo U12-T04 (su CA-15); desbloquear a los usuarios que hayan fallado un login.
  - U00-T04 en `main`: sin la `aud` corregida ningún servicio obtiene token y ninguna demo arranca.
  - Publicar las imágenes de U3 a U11 y fijar los digests reales (hoy, de ejemplo: `ImagePullBackOff`); crear `values/kind/product-metrics.yaml`; construir en un mismo commit las de governance, scoring y casos.
  - Retirar el eco de U2 y la `ServiceAccount` temporal `console-bff` de U4 antes del sync de U10.
  - Política activa, modelo de referencia `activo`, y los paquetes proxy y RT-3 en el model-store.
  - Publicar la imagen de U12 y correrla por digest; medir su memoria en el host.
- **Acceso del operador**
  - El camino a la bóveda (P-9) y la lectura de las 5 credenciales y las 2 llaves; las semillas del presentador (P-11).
  - K16 de verdad: que cada `verify` funcione con el grupo `vectra-verification-operators`, y qué pasa en `vectra-staging`.
  - Los selectores y puertos de Prometheus y del registro; el certificado raíz exportado; el login por el gateway real, con el emisor público y los `redirect_uri` reales.
  - `CASE_ALLOW_TEST_SCENARIOS` activo y los límites del gateway (`auth-login`, `auth-token`, `console`) con 2 000 casos.
- **U1:** la suite de conectividad; `Watchdog` recibido; el target `linkerd-proxy` de `vectra-mock` en `up == 1`; la serie `inbound_http_authz_deny_total` con `namespace` y `route_name` reales.
- **U8:** el Job `rt5-demo-<runId>` con el `runId` de `prepare`; `CoreWriteAttempt` en `firing` y cuánto dura; el valor real de `l5d-proxy-error`; las dos llaves por ESO; `sslmode=verify-full`; `vectra_cases_failclosed_persistent` raspado; memoria con 2 000 decisiones; el apagado del worker.
- **U10:** login, `/callback` y recarga con `prompt=none`; la CSP real; el step-up de `cumplimiento-1` y `ResolveFrozenDialog`; F03, F10, F11 y F14; el `iss` en cada destino; la cookie de afinidad; memoria del BFF.
- **U11:** las métricas del día D + 1; la `PrometheusRule` cargada y el `ConfigMap` del dashboard descubierto en `Vectra / Producto`; la llave por ESO; memoria con 2 000 decisiones; y **el orden de arranque** (dashboard vacío hasta 30 min).
- **U2:** los tokens reales (`acr`, `amr`, `aud`), y Grafana por `port-forward` con `grafana-admin` (P-2): dónde está esa credencial y que el dashboard «Producto» cargue.
- **Las cuatro demos, ensayadas con reloj:** D1 (qué `last_cause` da F22 apagado; los 19,3 min; que la reversión devuelva el flujo a `listo`; los casos `no_disponible` que quedan); D2 (los dos modos de reactivación, y el de `presenter` con `cumplimiento-2` y sus credenciales en la bóveda; que U3 no dé 504 al cron; las métricas de bias por el Pushgateway; más de 75 min; el rollback); D3 (que el PR de `runId` fusionado deje `make -C case-management policy-chart` en verde; la ventana de 5 min de la alerta; la retención de 3 días); D4 (lanzar `decisions` antes de las 22:18 UTC; leer tras las 02:40 UTC; el día 1 del mes).
- **Medir y corregir:** las constantes de `guard` (1 s por caso, 300 s); los plazos por omisión de cada espera; el `--memory` de la imagen.
- **Cierre:** el resto de `evidence/cierre-demo.md` (esta tarea deja solo «Diferido por la demo»), `make -C system-verification check` y el PR de verificación.
