# U01-T21 — El presupuesto de memoria de kind cuenta el modelo inactivo donde de verdad existe

**Unidad:** U1 — `platform` (perfil de kind), con los values de U6
**Historias que implementa:** ninguna nueva; resuelve una candidata del revisor de U01-T20 (2026-11-18) con la decisión del usuario del 2026-11-19.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> **Lo que hay** (`platform/tests/test_kind_profile.py`):
>
> - `PEAK_INFERENCE_SERVICES` proyecta el peor momento de D2 que el presupuesto protege (`DECISIONES-LOOP.md` §7): la promoción, con 2 `prod` y 1 `staging`.
> - `peak_with_declared` (U01-T20) mete lo declarado en `vectra-risk-gitops/values/kind/model-serving.yaml` en los huecos de esa proyección, perfil por perfil; lo que no tiene hueco cuenta de más. Un `inactive` nunca tiene hueco, así que **siempre** se suma encima del pico.
> - Medido por el revisor de U01-T20: con un `inactive` declarado el total da 14,27 GiB frente a `BUDGET_GIB` = 13,8, y `test_the_profile_requests_fit_the_budget` queda en rojo.
> - El `post-activation-pr` de `promotion-tool` (escenario 4 de `governance/docs/paso-20-kind.md`, la demo D2) declara justo eso: la versión anterior pasa de `prod` a `inactive`. Ese PR rompería `tests` y `policies` en la CI.
>
> **Decisión del usuario (2026-11-19):** los dos estados no ocurren a la vez. Durante la promoción hay dos versiones en `prod` y ninguna `inactive`; después de la activación queda una en `prod` y la anterior `inactive`. El presupuesto debe comparar contra el límite **el mayor de los estados reales**, no la suma del pico más el inactivo. El inactivo se sigue contando, donde existe.
>
> Lo que se quiere:
>
> 1. **Mide primero** con el chart de U6 rendido para kind: cuánto piden (memoria y CPU, con proxies) una versión `prod`, una `inactive` y el predictor de `staging`. Pégalo en la bitácora. Si una `inactive` pide **más** que una `prod`, la regla de abajo no vale: dilo y **para**.
> 2. **La regla nueva de `peak_with_declared`:** una versión `inactive` declarada es una versión que dejó de estar en `prod`; ocupa un hueco `prod` libre de la proyección si lo hay (no coexiste con dos `prod`), y solo cuenta de más si no queda hueco (por ejemplo, 2 `prod` + 1 `inactive` declarados a la vez). Lo demás no cambia: un tercer `prod` o un segundo `staging` siguen contando de más y poniendo el presupuesto en rojo.
> 3. **Los estados de D2 quedan fijados por pruebas**, con los números medidos: (a) `1 prod` (hoy); (b) `2 prod` (promoción); (c) `1 prod + 1 inactive` (tras `post-activation-pr`); (d) `2 prod + 1 inactive` y `1 prod + 2 inactive`, que deben contar el exceso (di si caben o no y que la prueba lo fije). El presupuesto que se compara nunca baja del pico proyectado.
> 4. **`DECISIONES-LOOP.md` §7** gana una enmienda corta con la decisión y la regla.
> 5. Si otras piezas repiten la cuenta (`platform/tests/kind_serving_kyverno.py`, que según la candidata ya prevé el `inactive`, o `test_kind_serving_*`), dilas y alinéalas solo si la regla cambia lo que comprueban.

**Fuera:**

- `BUDGET_GIB` y `MACHINE_GIB`: no se suben.
- Los requests de los pods de serving, réplicas, HPA y PDB (`DECISIONES-LOOP.md` §7, opción c).
- `vectra-risk-gitops/values/kind/model-serving.yaml`: no declares versiones; lo edita `promotion-tool`.
- `promotion-tool` (U04-T13 va aparte) y cualquier orden contra el clúster.

---

## Archivos de contexto

- `platform/tests/test_kind_profile.py` (`PEAK_INFERENCE_SERVICES`, `peak_with_declared`, las pruebas de U01-T20 al final)
- `platform/tests/kind_serving_kyverno.py` y las pruebas que lo usan
- `model-serving/chart/` (plantilla `inferenceservice.yaml`, perfiles) y `vectra-risk-gitops/values/kind/model-serving.yaml`
- `DECISIONES-LOOP.md` §7; `bitacoras/U01-T20.md` y `revisiones/U01-T20/ronda-1.md`
- `governance/docs/paso-20-kind.md`, escenarios 3 y 4

---

## Criterios de aceptación

- [ ] **CA-1** — Los estados de D2 caben y el exceso sigue contando.
  ```bash
  cd vectra-risk && uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q -k "kind_profile and (inactive or declared or peak or budget)"
  ```
  Esperado: pasa. **Rojo primero**, pegado en la bitácora: la prueba del estado `1 prod + 1 inactive` falla con el `test_kind_profile.py` de `main`. Comprueba con `--collect-only` qué selecciona el filtro y ajusta los nombres de las pruebas para que las recoja.

- [ ] **CA-2** — El PR que la demo va a abrir no rompe la CI: con los values de kind mutados a `1 prod + 1 inactive` (en una copia o restaurando después; no lo commitees), el archivo entero pasa.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py --rootdir=platform --import-mode=importlib -p no:cacheprovider -q
  ```
  Esperado: pasa con los values de `main` y con la mutación. Pega los dos resultados.

- [ ] **CA-3** — `platform` sigue en verde, como la CI.
  ```bash
  cd vectra-risk && uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q
  ```
  Esperado: rc 0. Una sola vez, al final.

---

## Plan de pruebas

- Los estados (a) a (d) de arriba, con memoria y CPU.
- Mutación: si `peak_with_declared` vuelve a sumar el `inactive` encima del pico, la prueba de (c) falla.

**Rojo primero:** (c) contra el archivo de `main`.

---

## Notas

- Estas pruebas rinden charts con `helm`: el worktree no tiene `platform/.tools` ni `platform/.charts`. El despacho dice cómo conseguirlos.
- Archivos que se **modifican en su sitio**: `platform/tests/test_kind_profile.py`, `DECISIONES-LOOP.md`. Nada de duplicados.
- No afirmes que algo «cabe en la máquina» sin el número: da los GiB de cada estado.
