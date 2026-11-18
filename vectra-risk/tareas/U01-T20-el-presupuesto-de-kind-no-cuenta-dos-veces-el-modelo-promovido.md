# U01-T20 — El presupuesto de kind no cuenta dos veces el modelo promovido

**Unidad:** U1 — `platform` (pruebas del perfil de kind)
**Historias que implementa:** ninguna nueva; desbloquea el PR de promoción #209.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> **Medido por el orquestador el 2026-11-18.** El PR #209 es la primera promoción real en kind: `promotion-tool` añade a `vectra-risk-gitops/values/kind/model-serving.yaml` la entrada
>
> ```yaml
> inferenceServices:
>   - modelVersionId: mv-2026-01-01-8a98ab02
>     storageUri: s3://model-store/mv-2026-01-01-8a98ab02/
>     profile: prod
> ```
>
> y con ella fallan `tests` y `policies` de la CI. Reproducido en local sobre el commit del PR (`753e479`):
>
> ```
> FAILED platform/tests/test_kind_profile.py::test_the_profile_requests_fit_the_budget          assert 14.8125 <= 13.8
> FAILED platform/tests/test_kind_profile.py::test_the_profile_cpu_requests_fit_the_budget_at_the_d2_peak   assert 11.145 <= 10.7
> 2 failed, 28 passed
> ```
>
> **Causa.** Las pruebas calculan el pico como `[*declared_inference_services(), *PEAK_INFERENCE_SERVICES]`. `PEAK_INFERENCE_SERVICES` **proyecta** el peor momento de U6 (M1 y M2 en `prod` y el predictor de staging) porque, como dice su comentario, «los PR de `promotion-tool` aún no lo agregan a los values de kind». Ahora que un PR sí declara M1, la suma cuenta M1 dos veces (el declarado y el proyectado): tres modelos en `prod` en lugar de dos. El estado real tras fusionar el #209 es **menor** que el pico proyectado (un modelo en `prod`), y cabe.
>
> Lo que se quiere:
>
> 1. **El pico no cuenta dos veces.** El peor momento que el presupuesto protege es el que define DECISIONES-LOOP §7 (dos versiones en `prod` y el predictor de staging). Lo declarado en kind forma parte de ese pico, no se suma a él. Decide y justifica la regla en la bitácora: por ejemplo, que lo declarado ocupe los huecos de la proyección perfil por perfil y solo cuente de más lo que la exceda (un tercer `prod`, un segundo `staging`), de modo que **declarar más de lo que el pico prevé siga poniendo la prueba en rojo**. Aplícala igual en las tres pruebas que hoy suman (`test_the_profile_requests_fit_the_budget`, `test_the_peak_fits_the_machine`, `test_the_profile_cpu_requests_fit_the_budget_at_the_d2_peak`) y en cualquier otra que sume igual (mira también `kind_serving_kyverno.py`).
> 2. **Las cifras del presupuesto no cambian** (`BUDGET_GIB`, `CPU_BUDGET`, `MACHINE_GIB`): no es un recorte ni una ampliación.
> 3. **Pruebas de la regla, rojo primero**, con listas de `inferenceServices` fabricadas en la prueba (sin tocar el archivo de values): nada declarado → el pico es el de hoy (misma cifra); un `prod` declarado → la misma cifra; dos `prod` y un `staging` declarados → la misma cifra; tres `prod` → rojo; un `inactive` declarado además del pico → cuenta de más (di cuánto y si cabe).
> 4. **Comprueba el caso real:** con el contenido de `values/kind/model-serving.yaml` del PR #209 (la entrada de arriba; cópiala en una prueba o aplícala en una copia en el scratchpad, **no** en el archivo del repositorio), el `pytest` de `platform` pasa entero.

**Fuera:**

- `vectra-risk-gitops/values/kind/model-serving.yaml`: `inferenceServices` solo lo edita `promotion-tool` por PR. No lo toques.
- Las cifras del presupuesto y los perfiles de kind.
- `promotion-tool`, la guía de U4 y el PR #209.
- Cualquier orden contra el clúster.

---

## Archivos de contexto

- `platform/tests/test_kind_profile.py` (`PEAK_INFERENCE_SERVICES`, `declared_inference_services`, `requested_gib`, `requested_cpu`, y las tres pruebas), `platform/tests/kind_serving_kyverno.py`
- `vectra-risk-gitops/values/kind/model-serving.yaml` (solo lectura), `model-serving/chart/values.yaml`, `model-serving/docs/values.md`
- `DECISIONES-LOOP.md` §7 (el perfil de kind y su pico)

---

## Criterios de aceptación

- [ ] **CA-1** — La regla nueva, con sus pruebas.
  ```bash
  cd vectra-risk && uv run pytest platform/tests/test_kind_profile.py --rootdir=platform --import-mode=importlib -q -p no:cacheprovider
  ```
  Esperado: pasa. **Rojo primero, pegado en la bitácora:** las pruebas nuevas del punto 3 contra el código de `main`. Mutación que debe fallar: volver a sumar lo declarado a la proyección.

- [ ] **CA-2** — Con la entrada del PR #209 el `pytest` de `platform` pasa entero; sin ella, también.
  ```bash
  cd vectra-risk && NOKUBE="$(echo "$PATH" | tr ':' '\n' | grep -v -E '^/snap/bin$' | paste -sd:)" && PATH="$NOKUBE" KUBECONFIG=/nonexistent uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q
  ```
  Esperado: pasa en los dos casos (el caso «con la entrada» en una copia del árbol en el scratchpad, o con el archivo modificado y **devuelto** antes del commit; di cuál). Con `platform/.tools` fuera del árbol.

- [ ] **CA-3** — Lo que corre el job `policies` de la CI también pasa con la entrada del PR #209. Busca qué orden corre ese job (`.github/workflows/`), córrela una vez en los dos casos y pega el resultado. Si falla por otra razón distinta del presupuesto, dilo y **para**: sería otro defecto.

- [ ] **CA-4** — `KUBECONFIG=/nonexistent make -C platform check` rc 0. Una sola vez, al final.

---

## Plan de pruebas

Las del punto 3. **Rojo primero.**

---

## Notas

- **Nada contra el clúster `kind-vectra`, ni lecturas.** Corre TODO con `KUBECONFIG=/nonexistent` y con un `PATH` sin `/snap/bin`. No uses `~/.kube/config` ni `~/.kube/kind-vectra-readonly`.
- `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`: cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts`. No van en el commit.
- No uses `git stash` (la pila es compartida entre worktrees).
- La máquina es un portátil que se satura: una sola corrida pesada a la vez; anota la carga (`uptime`) junto a cada corrida larga.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u01t20-`, y borra tus copias al terminar.
- `CANDIDATAS.md`: solo añadir al final. Añade estas tres, medidas por el orquestador el 2026-11-18, si no están: (a) U4, `governance/docs/paso-20-kind.md` §5.4: `--repo ..` falla (`helm_template_failed … path not found`) porque `promotion-tool` ejecuta con `cwd` en el repositorio y une la ruta relativa otra vez; solo funciona con ruta absoluta; (b) U4, `promotion-tool`: el cuerpo del PR que crea no trae la sección `## Rollback` que exige el check `rollback-note` de la CI; (c) U4, `promotion-tool` (`gitops.py`): si `git commit -S` falla, deja el cambio en el índice de `main` y la rama `promotion/…` creada, y la siguiente corrida se niega por árbol sucio; debería deshacer lo que hizo.
- Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
