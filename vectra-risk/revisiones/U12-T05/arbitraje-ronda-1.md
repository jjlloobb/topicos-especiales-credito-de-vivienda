# U12-T05 — Arbitraje de la ronda 1 (orquestador, 2026-11-14)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con un ROJO (F-01). La imagen funciona como dice el README en todo lo demás. Es la última ronda (RL-2).

El usuario pidió que la demo final pueda ejecutarse **en otra máquina con kind** (memoria `demo-portable-a-otra-maquina`; `DECISIONES-LOOP.md`). Por eso entran en la ronda 2 los NARANJA y el AMARILLO que tocan justo eso.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: `decisions` y `rt2-setup` terminan en una traza con código 1 cuando Chromium no arranca o la bóveda no responde | **Entra en la ronda 2**, y se generaliza | CA-4 y el README prometen un error claro y código 2. El código 1 significa «algún elemento falla»: el operador lo confundiría con un fallo del sistema |
| F-02 NARANJA: el perfil seccomp es más permisivo que el de Docker y el README dice que es equivalente | **Entra en la ronda 2** | Es un hueco real en hosts sin AppArmor, y la demo va a otra máquina. Se arregla sin descargar nada |
| F-03 NARANJA: `hatchling` y sus dependencias sin hash; `apt.lock` dejará de construir cuando Debian actualice | **Entra en la ronda 2** | La construcción en otra máquina es el caso de uso; el README debe decir cuál es el camino fiable |
| F-04 NARANJA: la prueba del README no exige `readonly` por montaje | **Entra en la ronda 2** | CA-6 pide los dos montajes de solo lectura; dos mutaciones sobreviven |
| F-05 AMARILLO: lo que le falta al README para otra máquina (contexto `kind-vectra`, prerrequisitos, Docker Desktop en Linux, Ctrl-C en D2) | **Entra en la ronda 2** | Es el requisito del usuario |
| Candidata: `verify/rt-5.sh:13` informa un error de `kubectl` como «no existe» | **Entra en la ronda 2** | Una línea, y en otra máquina (otro contexto) es lo primero que confunde |
| N-1 de la revisión de U12-T04 (el guardado por fase de `rt2` llega una fase tarde: con `docker stop` se reenvía el lote) | **Entra en la ronda 2** | La imagen es lo que hace probable un `docker stop`; el arreglo es mover una línea |
| La prueba `test_f07_a_megabyte…` (de U12-T04) con límite de reloj de pared, que falla con la máquina cargada | **Entra en la ronda 2** | Hace fallar `make check` al azar; se mide de forma robusta a la carga |

## Lo que se espera de la ronda 2

- **F-01.** Todo fallo de infraestructura (`INFRA_ERRORS`: `K8sError`, `OidcError`, bóveda inalcanzable, `port-forward` caído) en **cualquier** sección de la CLI termina como `no ejecutado`, código 2, con un código estable y sin traza: `decisions`, `rt2-setup`, `u11`, `rt5` y `prepare` incluidos, no solo `rt3` y `rt2`. Lo razonable es tratarlo una vez en `_execute`. Prueba por sección con un `Backend` que lance cada error, y la sonda del revisor dentro del contenedor (Chromium sin perfil seccomp → código 2). El README y la bitácora dicen lo que se midió.
- **F-02.** El perfil `seccomp/chrome.json` se recorta, sin descargar nada, a: el perfil por omisión de Docker más lo que el sandbox de Chromium necesita (`clone`, `unshare`, `setns` y lo que se demuestre necesario). Prueba dentro del contenedor: el sandbox sigue funcionando; y `keyctl`, `mount` y `pivot_root` devuelven EPERM. El README dice de dónde sale el perfil, qué añade al de Docker y en qué entorno está probado (kernel, Docker, AppArmor), sin afirmar equivalencias no medidas.
- **F-03.** Las dependencias de construcción (`hatchling` y las suyas) con versión y hash, sin índice propio (`--no-build-isolation` con un segundo archivo de requisitos, o lo equivalente). Para `apt.lock`: el README dice con claridad que el camino fiable hacia otra máquina es **llevar la imagen construida** (`docker save` y `docker load`, o publicarla en el registro de kind), y que `make image` en una máquina limpia puede fallar cuando Debian retire una versión fijada; si fijar un espejo con fecha (`snapshot.debian.org`) es de pocas líneas y no exige descargas no autorizadas al construir aquí, hazlo; si no, déjalo dicho y como candidata.
- **F-04.** La prueba exige `readonly` en cada montaje que debe serlo (kubeconfig, CA, values, entrega); las dos mutaciones del revisor mueren.
- **F-05.** El README, para una máquina limpia: el contexto de `kubectl` que la herramienta y los `verify` esperan (`kind-vectra`) y cómo cambiarlo (`KUBE_CONTEXT`); `make`, `python3` y `git` entre los prerrequisitos (o una orden que no los necesite); Docker Engine en Linux, no Docker Desktop (tampoco en Linux); D2 se interrumpe con Ctrl-C, no con `docker stop`. Con otro contexto, la herramienta da un error claro y código 2 (lo cubre F-01), no una traza.
- **`verify/rt-5.sh`:** un error de `kubectl` en el paso 1 sale con código 2 («no se pudo leer»), no como «no existe».
- **N-1:** `rt2` guarda el estado **después** de marcar la fase como terminada; prueba: el estado guardado tras el lote ya lo marca hecho, y una retoma desde ese archivo no reenvía.
- **`test_f07…`:** deja de depender del reloj de pared con la máquina cargada (tiempo de CPU del proceso, o un margen que no falle con carga 10) sin dejar de detectar el coste cuadrático (la mutación al recorrido viejo debe seguir fallando).
- Reconstruye la imagen y repite `test-image`. Nada más cambia.
- **Se vuelven a correr:** CA-2 a CA-6, CA-9, CA-10, CA-12 (`make -C system-verification check`, con las semillas) y CA-13; `forbidden_steps.py --dockerfiles` y `trivy` en local.
