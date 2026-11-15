# U12-T07 — La puerta de la bóveda se puede pasar tras resembrar, y la guía remite al runbook de U1

**Unidad:** U12 — `system-verification`
**Historias que implementa:** ninguna nueva; cierra los hallazgos de la ronda 2 de U12-T06 (`revisiones/U12-T06/ronda-2.md`), cuyo PR se fusionó antes de terminar la revisión.
**Depende de:** U12-T06 y U01-T10 (las dos en `main`)

---

## Alcance

**Dentro:**

> 1. **`arranque.sh` distingue una bóveda vacía de una ya resembrada (F-01, ROJO).** Hoy marca el pod de la bóveda siempre que `restartCount > 0` (`system-verification/docs/kind/arranque.sh:42-46`), y el contador no baja nunca: tras un reinicio de la máquina la puerta del paso 7 de «Después de reiniciar la máquina», K-05 y la puerta de F0 quedan en 1 para siempre, aunque el operador ya haya resembrado. **Medido el 2026-11-14 en `kind-vectra`:** `vault-0` está `Running` con `restartCount` 21, los 58 `ExternalSecret` están sincronizados, y el guion saldría 1. El guion pasa a fallar solo si la bóveda se reinició **después** de la última siembra, comparando con lecturas (`kubectl get`) el arranque del contenedor de la bóveda con la sincronización de los `ExternalSecret` (por ejemplo `state.running.startedAt` frente a `status.refreshTime` y la condición `Ready`), o con otra lectura que demuestres equivalente. Un pod reiniciado y ya resembrado es un AVISO que sale 0.
> 2. **La guía remite al runbook de U1 (F-02).** `paso-18-kind.md:96` y `:108` dicen «pregunta abierta». La decisión es: las órdenes de la recuperación que la lista cerrada no admite son del operador y están en `platform/runbooks/install.md`, secciones «Vault reiniciado» y «Tras reiniciar la máquina» (U01-T10, ya en `main`); la lista cerrada no se amplía. La guía lo dice así, con enlace a esas secciones, en cada paso de la sección del reinicio: inotify (el valor que aplica es el del runbook: léelo y que la guía no lo contradiga), recrear los pods con malla, claves de MinIO, Grafana. El operador debe saber qué ejecutar en cada paso.
> 3. **Menores (F-03, F-04, F-05):** «la lista de abajo» → la de arriba; las cuatro cifras que sobrevivieron a las mutaciones quedan atadas a su origen (`rt2_latency ≤ 1 800 s`, el divisor de `2 000 / 10`, «≈ 150 s» del lote, «bias cada 15 min»); el texto de ayuda de `humo.py` nombra `--delivery`.

**Fuera:**

- `src/`, `demos/`, `Dockerfile`, el README de system-verification, `seccomp/` y `platform/` (incluido el runbook: si le falta algo, va a `CANDIDATAS.md`).
- Ampliar la lista cerrada de verbos de la guía.
- El valor por omisión de `--delivery` en `humo.py` (cambia el comportamiento; candidata).

---

## Archivos de contexto

- `revisiones/U12-T06/ronda-2.md` y `arbitraje-ronda-1.md`
- `system-verification/docs/paso-18-kind.md`, `system-verification/docs/kind/` (`arranque.sh`, `lib.sh`, `humo.py`, `inventario.yaml`)
- `system-verification/tests/unit/test_kind_scripts.py`, `test_kind_guide.py`, `test_kind_inventory.py`, `tests/doubles/kind_kubectl_bin.py`
- `platform/runbooks/install.md` (solo lectura)
- `bitacoras/U12-T06.md`

---

## Criterios de aceptación

- [ ] **CA-1** — Con el doble: bóveda con `restartCount` 21 y `ExternalSecret` sincronizados después del arranque del contenedor → `arranque.sh vault` sale 0 con un aviso; bóveda cuyo contenedor arrancó después de la última sincronización, o con algún `ExternalSecret` sin sincronizar → sale 1; lectura fallida → sale 2.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests/unit/test_kind_scripts.py -q -p no:cacheprovider -k "vault"
  ```
  Esperado: pasa, con las tres pruebas nuevas; contra `main`, la primera falla (sale 1).

- [ ] **CA-2** — La guía no dice «pregunta abierta» y cada paso de la sección del reinicio remite al runbook de U1 con un enlace que resuelve.
  ```bash
  cd vectra-risk && ! grep -n -i 'pregunta abierta' system-verification/docs/paso-18-kind.md && grep -c 'runbooks/install.md' system-verification/docs/paso-18-kind.md && uv run python platform/tests/test_links.py
  ```
  Esperado: el primer `grep` no encuentra nada; el conteo es mayor que 0; enlaces en rc 0. Una prueba de `test_kind_guide.py` falla si la sección del reinicio deja de remitir al runbook o si contradice su valor de inotify.

- [ ] **CA-3** — Las cuatro mutaciones de F-04 mueren.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests/unit/test_kind_guide.py -q -p no:cacheprovider
  ```
  Esperado: pasa; la bitácora muestra cada mutación fallando.

- [ ] **CA-4** — Todo sigue en verde.
  ```bash
  cd vectra-risk && make -C system-verification check
  ```
  Esperado: rc 0. Una sola vez, al final, con la imagen desde la caché.

---

## Plan de pruebas

- Tres casos del doble para la bóveda (CA-1), más el caso real medido como dato de entrada.
- Prueba de la remisión al runbook (CA-2).
- Cuatro cifras atadas (CA-3).

**Rojo primero** en cada una; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`.** No toques contenedores ajenos. La máquina tiene poca memoria.
- Los guiones de `docs/kind/` siguen siendo de solo lectura.
- El scratchpad es compartido: prefijo `u12t07-` en tus temporales.
- `CANDIDATAS.md`: solo añadir al final (el inventario apunta a líneas).
- Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
