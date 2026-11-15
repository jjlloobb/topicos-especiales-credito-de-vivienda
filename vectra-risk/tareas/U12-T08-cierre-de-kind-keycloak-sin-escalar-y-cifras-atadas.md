# U12-T08 — Cierre del perfil de kind: Keycloak sin escalar, presupuesto final y cifras de la guía atadas

**Unidad:** U12 — `system-verification` (con la política y los values de kind de Keycloak, U2, y la prueba del presupuesto, U1)
**Historias que implementa:** ninguna nueva; cierra lo que dejaron abierto las revisiones de U12-T07 (`revisiones/U12-T07/ronda-1.md`) y de U01-T13 (`revisiones/U01-T13/ronda-1.md`).
**Depende de:** U01-T13, U02-T23 y U12-T07 (las tres en `main`)

---

## Alcance

**Dentro:**

> **A. Keycloak no escala en kind (U2 y U1).**
> 1. En kind, el HPA de Keycloak queda con `maxReplicas` igual a su `minReplicas` (1). Hoy es 1-4: si subiera a 4, el pico de la demo D2 pasaría a 16,79 GiB, unos 2 GiB por encima de la máquina (14,82 GiB). Es el único HPA de kind que puede crecer sin estar contado (`PENDING_UNBOUNDED` en `platform/tests/test_kind_profile.py`). Staging y prod siguen en 2-4, sin cambiar un byte.
> 2. La política de Keycloak (`identity-edge/keycloak/policy/keycloak.rego:123-125,146` fija `maxReplicas` en 4) se vuelve sensible al entorno **con la misma señal `is_kind` y el mismo sitio (`set.rego`, evaluación con `--combine`) que U02-T23 usó para el mínimo** (regla `hpa-min-replicas`): máximo 1 en kind, 4 en los demás; exacta en los dos casos. Mutaciones por entorno, como las de U02-T23.
> 3. `PENDING_UNBOUNDED` queda vacío (o desaparece), y `BUDGET_GIB` y `CPU_BUDGET` bajan a lo medido con Keycloak en 1 (el revisor midió 13,7344 GiB y 10,665 CPU). De paso, los AMARILLO de la revisión de U01-T13: el comentario de `MACHINE_GIB` (14,8157, no 14,8166), el nombre de `test_kind_serving_render_passes_the_kyverno_hpa_bounds_policy` (ya no ejecuta Kyverno: que el nombre diga lo que hace), y el literal `"kind-registry:5000/"` duplicado en `identity-edge/gateway/policy/edge.rego:349` (que salga de un solo sitio, si se puede sin tocar el comportamiento).
>
> **B. Las cifras de memoria de U12 dicen el presupuesto y están atadas a él.**
> 4. La guía, el inventario y las plantillas siguen diciendo 11,8 GiB en siete sitios (`paso-18-kind.md:39,163,243`; `docs/kind/inventario.yaml:47`; `evidence/kind/00-prerrequisitos.md:17,33`; `evidence/cierre-demo.md:33`; verifica con `grep -rn '11,8'`), y la línea 163 cita una línea de `test_kind_profile.py` que ya no es. Todas pasan a la cifra de `BUDGET_GIB` que fijes en el punto 3, y una prueba las ata (como la del README): cambiar `BUDGET_GIB` sin cambiarlas la hace fallar. La frase del README que anuncia el presupuesto (`system-verification/README.md:50`, «suman 14,8 GiB») se actualiza igual.
> 5. **No toques la frase «14 GiB como mínimo, 16 recomendados»** del README ni lo que la guía diga del mínimo de la máquina: es una decisión del usuario que sigue abierta. Si alguna de las siete apariciones mezcla las dos cosas («11,8 GiB de requests en una máquina de 14 GiB»), cambia solo la cifra de requests y dilo.
>
> **C. Lo que dejó la revisión de U12-T07.**
> 6. F-02: la prueba que impide pedir componentes que kind no instala (`absent_component_findings` en `tests/unit/test_kind_guide.py`) comprueba el marcador histórico por mención, no por línea, y trata como petición cualquier forma de orden (`svc/X`, `deploy/X`, `app wait X`, `logs … X`, `port-forward … X`). Las tres mutaciones que sobrevivieron (`port-forward … svc/alloy 12345`, `logs -n vectra-observability deploy/tempo`, `argocd app wait loki --health`, inyectadas en la línea del paso 13) deben morir.
> 7. F-03: `arranque.sh` compara el arranque del contenedor de la bóveda con la sincronización de los `ExternalSecret` **siempre**, no solo con `restartCount > 0`: un pod de la bóveda recreado (0 reinicios) y vacío, con `ExternalSecret` `Ready=True` de antes del arranque, sale 1.
> 8. F-04, F-05 y F-06: R-7 (`paso-18-kind.md:42`) dice lo que el guion hace ahora; el mensaje de la lista vacía no dice «1 ExternalSecret»; los números de paso del runbook que cita la guía quedan atados (una prueba falla si la guía cita un paso que en `platform/runbooks/install.md` no es el que dice).
> 9. Una prueba falla si aparece en el repositorio un `ExternalSecret` con `refreshPolicy: CreatedOnce` u `OnChange` (la puerta de la bóveda no tendría salida), o el guion los excluye de la comparación; elige y dilo.

**Fuera:**

- La frase del mínimo de memoria del README y de la guía (punto 5).
- `src/`, `demos/`, `Dockerfile`, `seccomp/`; el runbook de U1 y `seed-vault.sh` (lo que falte va a `CANDIDATAS.md`).
- Cualquier otro recurso de Keycloak; el mínimo de réplicas de ninguna unidad; staging y prod.
- La prueba `console/bff/tests/unit/test_chart.py::test_flows_f10…`, rota en `main` desde U01-T09 (candidata).

---

## Archivos de contexto

- `revisiones/U12-T07/ronda-1.md`, `revisiones/U01-T13/ronda-1.md`, `revisiones/U02-T23/ronda-1.md`
- `identity-edge/keycloak/` (`values/kind.yaml`, `values/common.yaml`, `policy/keycloak.rego`, `policy/set.rego`, `rendered/`), `identity-edge/tests/unit/test_keycloak_deploy.py`, `identity-edge/gateway/policy/` (`edge.rego`, `set.rego`), `identity-edge/Makefile`
- `platform/tests/test_kind_profile.py`, `platform/runbooks/install.md` (solo lectura)
- `system-verification/README.md`, `system-verification/docs/paso-18-kind.md`, `system-verification/docs/kind/` (`arranque.sh`, `inventario.yaml`), `system-verification/tests/unit/` (`test_kind_guide.py`, `test_kind_inventory.py`, `test_kind_scripts.py`, `test_demos_closed_world.py`), `tests/doubles/kind_kubectl_bin.py`
- `aidlc-docs/construction/system-verification/evidence/`
- `bitacoras/U02-T23.md`, `bitacoras/U01-T13.md`, `bitacoras/U12-T07.md`

---

## Criterios de aceptación

- [ ] **CA-1** — El HPA de Keycloak de kind es 1-1; staging y prod, 2-4, con el render idéntico al de `main`.
  ```bash
  cd vectra-risk && make -C identity-edge render-keycloak && git diff --stat origin/main -- identity-edge/keycloak/rendered && grep -n -E 'minReplicas|maxReplicas' identity-edge/keycloak/rendered/*/keycloak.yaml
  ```
  Esperado: solo cambia `rendered/kind/`.

- [ ] **CA-2** — La política acepta máximo 1 solo en kind y 4 solo en staging y prod.
  ```bash
  cd vectra-risk && make -C identity-edge policy-keycloak policy-keycloak-u1 check-keycloak-rendered policy-gateway && uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q -p no:cacheprovider
  ```
  Esperado: rc 0, con mutaciones nuevas: kind con máximo 2 o 4 falla; staging y prod con máximo 1 fallan; un HPA sin `maxReplicas` falla en los tres.

- [ ] **CA-3** — Ningún HPA de kind queda pendiente, y los topes son los medidos.
  ```bash
  cd vectra-risk && uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q
  ```
  Esperado: pasa entero **sin `platform/.tools` en el árbol ni en el PATH** (así lo corre la CI: muévelo fuera para esta corrida y devuélvelo). `PENDING_UNBOUNDED` vacío. La bitácora da el pico de D2 y el margen frente a la máquina.

- [ ] **CA-4** — Ninguna cifra de memoria desfasada, y todas atadas a `BUDGET_GIB`.
  ```bash
  cd vectra-risk && ! grep -rn '11,8' system-verification/docs system-verification/README.md aidlc-docs/construction/system-verification/evidence && uv run pytest system-verification/tests/unit/test_kind_guide.py system-verification/tests/unit/test_kind_inventory.py system-verification/tests/unit/test_demos_closed_world.py -q -p no:cacheprovider
  ```
  Esperado: el `grep` no encuentra nada; las pruebas pasan; cambiar `BUDGET_GIB` en una copia hace fallar la prueba nueva por cada sitio.

- [ ] **CA-5** — Las tres mutaciones de F-02 mueren, y las de la ronda anterior siguen muriendo.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests/unit/test_kind_guide.py -q -p no:cacheprovider
  ```
  Esperado: pasa; la bitácora muestra cada mutación fallando.

- [ ] **CA-6** — La bóveda recreada y vacía sale 1; los casos de U12-T07 no cambian.
  ```bash
  cd vectra-risk && uv run pytest system-verification/tests/unit/test_kind_scripts.py -q -p no:cacheprovider -k vault
  ```
  Esperado: pasa, con el caso nuevo (0 reinicios, `refreshTime` anterior al arranque → 1) y el de la lista vacía con su mensaje corregido.

- [ ] **CA-7** — Todo en verde.
  ```bash
  cd vectra-risk && make -C system-verification check && uv run python platform/tests/test_links.py
  ```
  Esperado: rc 0. Una sola vez, al final, con la imagen desde la caché y con `platform/.tools/bin` disponible (helm): si falta en el worktree, enlázalo desde otro worktree; no es parte del commit.

---

## Plan de pruebas

Las de CA-2 a CA-6. **Rojo primero** en cada una; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`.** No toques contenedores ajenos. La máquina tiene poca memoria.
- `platform/.charts` y `platform/.tools` no están versionados: cópialos o enlázalos del worktree `u01-t13` (tiene el juego completo, incluidos `envoy-gateway/gateway-helm` y `keycloakx`). No descargues imágenes.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u12t08-`, y borra tus copias del repositorio al terminar.
- `CANDIDATAS.md`: solo añadir al final (el inventario apunta a líneas); marca como resueltas, añadiendo una línea, las candidatas que esta tarea cierra.
- Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
