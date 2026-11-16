# U01-T16 — El kind sobrevive a un reinicio de la máquina: la siembra conserva las claves y el gateway se vuelve a encontrar

**Unidad:** U1 — `platform`
**Historias que implementa:** ninguna nueva; cierra lo medido en `kind-vectra` tras el reinicio de la máquina del 2026-11-16 (y las candidatas de `CANDIDATAS.md`, líneas 774, 805, 806, 824, 829 y 833).
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> La demo dura dos jornadas y la máquina se reinicia entre ellas. **Medido el 2026-11-16, dos minutos después de reiniciar** (solo lectura):
>
> - Los pods volvieron solos a `Running` (el límite de inotify ya es persistente).
> - La bóveda (Vault dev, en memoria) quedó vacía: los 71 `ExternalSecret` en `False` («could not get secret data from provider»). **Los 71 `Secret` destino siguen existiendo con los valores de antes** (`deletionPolicy: Retain`, `creationPolicy: Owner`), así que los servicios siguen funcionando.
> - `platform/kind/seed-vault.sh` «conserva lo que exista» **en la bóveda** (`vault_paths.py`, `plan` y `plan_identity`): con la bóveda vacía lo genera todo al azar. Las claves nuevas dejan de coincidir con las que guardan Keycloak (administrador de arranque, contraseñas y OTP de los usuarios, llaves de cliente registradas en el realm), MinIO, Grafana, PostgreSQL y Valkey. El runbook (`platform/runbooks/install.md`, «Vault reiniciado», pasos 4 a 8) lo arregla a mano, con pasos «no medidos» para Keycloak y PostgreSQL y un Job de MinIO que no está versionado.
> - Docker reasignó las direcciones: el contenedor del balanceador (`kindccm-…`) pasó de `172.18.0.7` a `172.18.0.2`; el Service `api-gateway` de `vectra-edge` siguió anunciando `172.18.0.7` y el balanceador conservó destinos viejos. `cloud-provider-kind` no estaba corriendo (se lanza con `--rm`, `install.md`, líneas 64 y 65). `https://vectra.localtest.me` no conecta.
>
> 1. **La siembra recupera antes de generar.** Para cada propiedad de cada ruta que falte en la bóveda, `vault_paths.py` (`seed` y `seed-identity`) busca primero su valor en el `Secret` de Kubernetes que el `ExternalSecret` correspondiente dejó en el clúster, y solo genera uno nuevo si no hay de dónde recuperarlo. El cruce ruta/propiedad → `Secret`/clave sale de los mismos `ExternalSecret` que el guion ya lee como `refs`; decide si lo lees de los manifiestos del repositorio o de los `ExternalSecret` vivos y di por qué. Cuidado con:
>    - los `ExternalSecret` con `target.template` (el valor del `Secret` es una transformación del de la bóveda: una DSN, un JWKS, un archivo): solo se recupera lo que es copia literal; lo demás se informa;
>    - una misma propiedad sembrada en varios `Secret`: si los valores difieren, no elijas en silencio: para y dilo;
>    - los pares de llaves de cliente (`identity/clients/*`): la privada y su `jwks` deben quedar del **mismo** par (`client_pair` «nunca regenera un par»);
>    - `grafana/folder-permissions` (`TOKEN_PENDING`) y los valores fijos de `fixed_value`.
> 2. **El guion dice qué hizo, sin secretos:** por cada ruta, cuántas propiedades conservó de la bóveda, cuántas recuperó del clúster y cuántas generó, con los nombres de las generadas (nunca los valores). Con todo recuperado, el operador no tiene que realinear nada; con algo generado, sabe exactamente qué.
> 3. **`seed-vault.sh identity` fuerza el refresco de los `ExternalSecret` de todos los namespaces** que leen rutas `identity/` (hoy solo tres: línea 38; los `*-client` de U3 a U11 tienen `refreshInterval: 1h`, `CANDIDATAS.md`, línea 824). Sácalos de los `refs`, no de una lista escrita a mano.
> 4. **`cloud-provider-kind` sobrevive al reinicio:** en `install.md` pasa a lanzarse con nombre, `-d` y `--restart=always`, como `kind-registry`. Di en la bitácora, leyendo su documentación o su código, si al volver corrige la dirección del Service y los destinos del balanceador; si no se puede saber sin clúster, queda como paso de comprobación del runbook.
> 5. **Un guion de solo lectura, `platform/kind/gateway-address.sh`**, que lee la dirección externa del Service del gateway en `vectra-edge`, comprueba que responde en el 443 (`curl --resolve`, sin credenciales) y compara con lo que resuelve `vectra.localtest.me` en la máquina. Sale 0 si coinciden y responde; si no, dice qué línea de `/etc/hosts` hace falta y sale distinto de 0. **No escribe `/etc/hosts`**: esa orden es del operador y va en el runbook. (Recomendación del orquestador, no objetada por el usuario: la máquina llega al gateway por `/etc/hosts` con la dirección del `LoadBalancer`; no se recrea el clúster ni se cambia `cluster.yaml`.)
> 6. **El runbook queda al día** (`install.md`, «Vault reiniciado» y «Tras reiniciar la máquina»): el orden nuevo (contenedores, `cloud-provider-kind`, `gateway-address.sh`, siembra con recuperación), qué pasos manuales **ya no hacen falta cuando todo se recuperó** y cuáles quedan para lo generado. No borres lo medido el 2026-11-14 y el 2026-11-15: márcalo como el camino para lo que no se pudo recuperar. Corrige de paso lo que hoy es falso en ese archivo: línea 18 («dos nodos», son tres), línea 33 (cifras de CPU y memoria frente a `platform/tests/test_kind_profile.py`), línea 178 («Keycloak no estaba instalado») y línea 205 («las cuatro imágenes propias»).

**Fuera:**

- Cambiar la bóveda de kind a almacenamiento persistente o quitar el modo dev.
- Versionar el Job que reescribe las claves de MinIO, y las órdenes de realineación de Keycloak: con el punto 1 dejan de hacer falta en el caso normal; siguen como candidatas.
- `platform/kind/cluster.yaml` y el Service del gateway (no se recrea el clúster).
- La guía de U12 (`system-verification/docs/paso-18-kind.md`) y su función `vv`: es de U12-T09, que corre en paralelo. Única excepción: si tu cambio en `install.md` rompe una cita por número de línea que comprueba `system-verification/tests/unit/test_kind_guide.py` o `test_kind_inventory.py`, corrige solo ese número y dilo.
- Cualquier orden contra el clúster.

---

## Archivos de contexto

- `platform/kind/seed-vault.sh`, `platform/kind/vault_paths.py`, `platform/kind/tests/test_vault_paths.py`, `platform/kind/tests/test_identity_seed.py`, `platform/kind/registry.md`, `platform/kind/cluster.yaml`
- `platform/runbooks/install.md` (líneas 60 a 66 y 165 a 195), `platform/tests/test_runbooks.py`, `platform/tests/test_links.py`
- `platform/secrets/` y los `external-secrets.yaml` que lista `vault_paths.py` (líneas 30 a 60); los `ExternalSecret` de U2 (`identity-edge/`) y los `service-identity.yaml` de los charts de U3 a U11
- `identity-edge/keycloak/values/common.yaml` (administrador de arranque, `keycloak-config-cli`), `identity-edge/docs/realm-importacion.md`
- `system-verification/docs/paso-18-kind.md`, sección «Después de reiniciar la máquina» (solo lectura: es lo que el operador sigue hoy)
- `CANDIDATAS.md` (líneas 774, 805, 806, 824, 829, 833), `DECISIONES-LOOP.md` §11

---

## Criterios de aceptación

- [ ] **CA-1** — Con la bóveda vacía y los `Secret` presentes, la siembra deja en la bóveda los mismos valores que había, y no genera ninguno.
  ```bash
  cd vectra-risk && uv run pytest platform/kind/tests -q -p no:cacheprovider -k "recover or recupera"
  ```
  Esperado: pasa, con pruebas nuevas sobre `plan` y `plan_identity` con un ejecutor falso (sin clúster). Comprueba con `--collect-only` que el filtro selecciona tus pruebas. Casos: bóveda vacía y todo recuperable; propiedad sin `Secret` (se genera y se informa); `target.template` (no se recupera, se informa); dos `Secret` con valores distintos (falla con mensaje); par de llaves de cliente (privada y `jwks` del mismo par). Mutación: sin la recuperación, la primera prueba falla.

- [ ] **CA-2** — El informe de la siembra no trae ningún valor secreto.
  ```bash
  cd vectra-risk && uv run pytest platform/kind/tests -q -p no:cacheprovider -k "report or informe"
  ```
  Esperado: pasa; la prueba busca en la salida cada valor sembrado y no encuentra ninguno.

- [ ] **CA-3** — `identity` refresca todos los namespaces que leen `identity/`.
  ```bash
  cd vectra-risk && uv run pytest platform/kind/tests -q -p no:cacheprovider -k "namespaces"
  ```
  Esperado: pasa; la lista sale de los `refs` y contiene `vectra-app`, `vectra-staging` y `vectra-mock` además de los tres de hoy (ajusta a lo que de verdad lean y dilo).

- [ ] **CA-4** — `gateway-address.sh` es de solo lectura y pasa el análisis estático.
  ```bash
  cd vectra-risk && shellcheck platform/kind/gateway-address.sh platform/kind/seed-vault.sh && ! grep -n -E 'kubectl[^|]*(apply|delete|patch|annotate|create|edit|replace|scale)|tee|>>? */etc' platform/kind/gateway-address.sh
  ```
  Esperado: rc 0. Además, una prueba con `kubectl` y `curl` sustituidos por falsos cubre los tres resultados (coincide y responde; no coincide; el Service no tiene dirección).

- [ ] **CA-5** — El runbook nombra el orden nuevo y pasa sus pruebas.
  ```bash
  cd vectra-risk && grep -n -E 'restart=always --name cloud-provider-kind|gateway-address.sh' platform/runbooks/install.md && uv run pytest platform/tests/test_runbooks.py platform/tests/test_links.py -q -p no:cacheprovider
  ```
  Esperado: las dos cadenas aparecen; las pruebas pasan.

- [ ] **CA-6** — El pytest completo de `platform` pasa **como lo corre la CI** (sin `platform/.tools` en el árbol ni en el PATH, con `platform/.charts`), y las pruebas de la guía de U12 que leen `install.md` siguen pasando.
  ```bash
  cd vectra-risk && uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q && uv run pytest system-verification/tests/unit/test_kind_guide.py system-verification/tests/unit/test_kind_inventory.py -q -p no:cacheprovider
  ```
  Esperado: pasan. (Mueve `platform/.tools` FUERA del árbol para esta corrida y devuélvelo.)

- [ ] **CA-7** — `platform` sigue en verde.
  ```bash
  cd vectra-risk && make -C platform check
  ```
  Esperado: rc 0. Una sola vez, al final.

---

## Plan de pruebas

Las de CA-1 a CA-4. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`**, ni lecturas: tus pruebas usan ejecutores falsos. El orquestador correrá la siembra en el clúster, con aprobación del usuario, cuando la tarea esté fusionada: deja en la bitácora la orden exacta y qué debe ver.
- La bóveda del clúster está vacía **ahora mismo** y nadie la ha resembrado: es el caso real que tu cambio debe resolver.
- `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`: cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts`. No van en el commit.
- Ningún valor secreto en la bitácora, en las pruebas ni en la salida: las pruebas usan valores de mentira.
- La máquina tiene poca memoria y un clúster de kind completo corriendo: una sola corrida pesada a la vez.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u01t16-`, y borra tus copias al terminar.
- En paralelo corren U01-T15 (`platform/policies/`) y U12-T09 (`system-verification/`): no toques esos archivos, salvo la excepción de «Fuera».
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes (uno por bloque terminado). No hagas push, no fusiones, no muevas el estado de la tarea.
