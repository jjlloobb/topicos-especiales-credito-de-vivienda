# Ronda 1 — U00-T03

VEREDICTO: NO-VERDE (no hay ningún ROJO. Quedan dos NARANJA. Según RL-x solo un ROJO bloquea, así que el orquestador puede fusionar y dejar los NARANJA como candidatas.)

Base `7d4e5e6` (`git merge-base HEAD origin/main`), HEAD `1525bf7`. El hash del blob de la tarea es `6606d212…`, como se esperaba. El worktree quedó limpio al terminar (`git status --short` sin salida).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Anidar sin token | `uv run pytest contracts/tests/unit/test_outcome.py -v -k nest` | pasa: 4 de 4 |
| 2 | La capa 2 sigue cerrada | `uv run pytest contracts/tests/unit/test_outcome.py -v` | pasa: 27 de 27, con `direct_construction_forbidden` y `violation_messages` incluidas |
| 3 | `read_wire` y `from_wire` | `… -k "read_wire or from_wire"` | pasa: 8 de 8 |
| 4 | PBT-U0-01 con `CaseDetail` | `HYPOTHESIS_PROFILE=ci uv run pytest contracts/tests/property/test_logic.py -v` | pasa: 15 de 15. La semilla solo se imprime si algo falla (`print_blob`), ver F-05 |
| 5 | Token cerrado en el workspace (AST) | `uv run pytest contracts/tests/unit/test_token_privado_workspace.py -v` | pasa: 16 de 16, con 13 raíces y 545 de 548 archivos `.py`. El rojo lo confirmé yo: el detector, aplicado al `views.py` y al `test_private_token.py` de la base, marca las líneas 106 y 108 y las líneas 12, 19 y 51 |
| 6 | U8 sin token | grep sobre `*.py`, `lint-imports --config case-management/.importlinter`, `make -C case-management check` | pasa con la lectura sobre `*.py` (ver el dictamen 1): grep rc=1, 4 contratos KEPT, `make` rc=0 con 189 pruebas |
| 7 | La sonda del revisor ya no funciona | `uv run python -I …/scripts/probe.py case-management/tests/doubles` | pasa: `ImportError: _CONTEXT`, rc=1 |
| 8 | Documentación y plan | los tres grep | pasa: los tres encuentran líneas |
| 9 | Sin regresiones | `make check` en serie, uno por unidad (`serie.txt`, con `uptime` antes y después) | ver abajo |

CA-9, unidad por unidad (todas corridas, ninguna quedó sin correr):
- **contracts:** el `make check` dio rc=2 en `bench_gate`. Falló `test_bench_derive` con p99 de 5,1 ms frente al límite de 2 ms, con carga de 12 a 14. `derive` no toca `outcome`. Volví a correr el bench con carga de 3 a 6, dos veces sobre la rama y dos sobre la base: los 8 pasan (derive en la rama 0,34 y 1,56 ms; en la base 0,40 y 0,35 ms). También corrí a mano los pasos que el `make` no llegó a ejecutar, y todos dieron rc=0: openapi, la generación de TS y su `git diff --exit-code`, typecheck, lint y test de TS, y las comprobaciones finales. Tests 527/527, cobertura y trazabilidad: bien. **Dictamen: pasa por partes, y el fallo es carga.**
- **case-management:** rc=0.
- **scoring-explainability:** rc=0. El bulkhead pasó dentro del `make`, y aislado pasó 3 de 3 en la rama y 3 de 3 en la base.
- **decision-registry:** rc=2, solo por `test_f04_300_mil…`. Aislada falla en la rama (2,23 s) **y también en la base** (3,01 s), y `vectra_registry/src` no importa `outcome`. No depende del diff. Es la candidata que corrige U03-T07.
- **governance, model-serving, reference-model, platform, bias-monitoring:** rc=0.

## Dictámenes que pediste
1. **El grep de CA-6 sobre `*.py`: lo acepto.** El criterio se contradice solo: pide que el contrato prohíba `vectra_contracts.outcome._internal`, y para eso el contrato tiene que nombrarlo. El grep sin filtro solo encuentra `.importlinter:7` (un comentario) y `.importlinter:74` (el contrato). Es un defecto de la especificación (F-04).
2. **El mecanismo de P-1.**
   - **Es verdad que `wrap` rompe la lectura de JSON.** Corrí `m.py` con pydantic 2.14.2: con `wrap` y con `before`, la validación llega en modo json con un dict, y falla con `Input should be a valid datetime`. La espiga del orquestador no lo detectó porque solo usaba un `int`.
   - **El sello `_born_with_token` con un validador `after` cumple las cuatro pruebas de la tarea.** Las comprobé con `probes/sello.py`:
     - anidar devuelve la misma instancia (`is rec`);
     - un dict o un JSON sin token lanzan `ContractViolation`;
     - una subclase sin token también falla;
     - `read_wire` rechaza `Ready`, también dentro de `list`, `Optional` y `dict`.
   - **Pero no conserva del todo P-U0-03.** Ver F-01 y F-02.
   - **El límite `rec._born_with_token = True` no importa para la demo.** Solo sirve sobre una instancia que no salga de una fábrica, y eso exige `Recommendation.__new__`, que es un ataque deliberado. `copy`, `pickle` y `model_copy` heredan el sello, porque ya parten de una instancia sellada.
3. **La reescritura de `test_private_token.py`.** Es el único archivo de `case-management/tests/` que cambia, y ninguna otra aserción de U8 se tocó. Aun así, la reescritura pierde dos cosas, ver F-03:
   - la prueba negativa de que el contrato `private-token` se rompe si otro módulo importa el token;
   - la búsqueda recursiva del token en contenedores.

   La prueba de AST de U0 compensa la detección en todo el workspace, así que no se pierde ninguna garantía del workspace.
- **El token por rutas de import (F-01, R2-01, R2-02 de U08-T02):** está cerrado. `hasattr(outcome, "CONSTRUCTION_TOKEN")` da False, `views` no lo importa, y la prueba que escribía en `src/` ya no existe. Pero hay una ruta que **no es de import** y que sigue abierta, ver F-01.
- **`CANDIDATAS.md`:** el diff solo tacha las cuatro entradas y les añade «Cerrada en U00-T03». Es correcto en forma, pero el cierre de R2-01 dice más de lo que se cumple (F-01).

## Hallazgos
### F-01 · NARANJA · `outcome/__init__.py` (`read_wire`) · `read_wire` entrega el token a cualquier modelo que le pasen
`read_wire(model, data)` llama a `model.model_validate_json(data, context={"token": …})` con un `model` que elige quien llama. Un validador de ese modelo lee `info.context` y se queda con el token, sin importar `_internal`. Con el token en la mano se puede fabricar un `Ready` y una `Recommendation` con cualquier `registry_entry_id`. Eso anula el rechazo de `Ready` que hace `read_wire`.

La prueba de AST no lo ve. Además, R2-01 nombraba la ruta del «espía» como una de las que alcanzan el token, y esa ruta sigue viva: basta un espía sobre el `model_validate_json` de cualquier contenedor que se lea con `read_wire`. Por eso marcar R2-01 como «Cerrada» dice más de lo que se cumple.

Evidencia: `rev-u00-t03-r1/probes/robo.py` y su salida `robo.out`: `token robado via read_wire (sin importar _internal): True`, `Ready fabricado…`, `Recommendation fabricada: inventado`.

Arreglos posibles:
- que `_has_token` mire una `ContextVar` privada en lugar de `info.context`;
- o que `read_wire` acepte solo una lista cerrada de contenedores;
- y, en cualquier caso, reabrir esa parte de R2-01.

### F-02 · NARANJA · `outcome/__init__.py` (`_Guarded`) · `model_copy` hereda el sello y salta la capa 1 al anidar
`rec.model_copy(update={"registry_entry_id": ""})` devuelve una instancia sellada. Al anidarla en `CaseDetail.model_validate(...)` no se exige el token, y pydantic no vuelve a validar los campos, solo los validadores `after`. El resultado es un `CaseDetail` con una `Recommendation` cuyo `registry_entry_id` está vacío.

Evidencia: `probes/sello.out`, en la línea `nest model_copy id vacio: OK`. La capa 1 sí se aplica a lo que comprueba `_structural`: con `model_version_id` distinto, falla.

`model_copy` ya existía en `main`, pero antes anidar la copia exigía el token. Arreglo: prohibir `model_copy`, igual que `model_construct`, o hacer que borre el sello.

### F-03 · AMARILLO · `case-management/tests/unit/test_private_token.py` · La reescritura afloja dos comprobaciones
- Se quitó la comprobación negativa de que import-linter da BROKEN si otro módulo importa el token. Ninguna prueba verifica `forbidden_modules`.
- Se quitó `hasattr(views, "CONSTRUCTION_TOKEN")`.
- La comparación `type(value).__name__ == "_Token"` no entra en contenedores.

La prueba de AST de U0 cubre la detección.

### F-04 · AMARILLO · CA-6 · El criterio se contradice
El grep sin filtro no puede quedar vacío si el contrato nombra el módulo. La lectura sobre `*.py` es correcta. Hay que corregir la plantilla de la tarea.

### F-05 · AMARILLO · CA-4 · «Semilla impresa»
El perfil `ci` usa `print_blob`, que solo imprime la semilla cuando algo falla. El codificador pasó `--hypothesis-seed=12345` a mano. Es un desajuste menor entre el criterio y la configuración.

### F-06 · AMARILLO · P-1 · Desvío aceptado
El desvío está bien documentado en el código, en `nfr-design-patterns.md` y en la bitácora. El límite `__new__` más `_born_with_token` es aceptable para la demo.

## Tareas candidatas (defectos reales fuera de alcance)
- U3: `test_f04_300_mil…` falla también en la base (3,01 s). Ya está asignada a U03-T07.
- U0: `bench_gate` de `test_bench_derive` excede el p99 con carga de 12 o más. Es intermitente y no tiene que ver con este diff.
- U0: `test_bench_outcome` p99 sube de unos 0,025 ms en la base a unos 0,032 ms en la rama, muy lejos del límite de 1 ms. Solo para tenerlo anotado.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u00-t03-r1/`:
- `serie.txt`: rc, duración y `uptime` de cada `make check`. Los logs completos están en `make-<unidad>.log`.
- `ca1-8.log`, `ca6.log`, `contracts-resto.log` (bench rama y base, openapi y TS) y `aislados.log` (f04 y bulkhead, rama y base).
- `probes/sello.py` y `sello.out`, `probes/robo.py` y `robo.out`.

```
VEREDICTO: NO-VERDE
NARANJA|contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py:read_wire|read_wire entrega el token a validadores de cualquier modelo: se fabrican Ready y Recommendation sin importar _internal (R2-01 mal cerrada)
NARANJA|contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py:_Guarded|model_copy hereda el sello: se anida una Recommendation con registry_entry_id vacío en CaseDetail
AMARILLO|case-management/tests/unit/test_private_token.py|la reescritura quita la prueba negativa del contrato y hasattr(CONSTRUCTION_TOKEN)
AMARILLO|CA-6|el grep literal contradice el contrato de import-linter; la lectura sobre *.py es correcta
AMARILLO|CA-4|la semilla solo se imprime si falla (print_blob)
AMARILLO|P-1|el desvío wrap→sello está bien justificado (wrap rompe JSON estricto, reproducido); el límite __new__ no importa para la demo
INFORME: revisiones/U00-T03/ronda-1.md
```
