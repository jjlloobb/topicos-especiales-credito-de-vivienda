# Arbitraje de la ronda 3 — U09-T01

Orquestador, 2026-11-09. Informe: `revisiones/U09-T01/ronda-3.md`. NO-VERDE por un ROJO (F-01, `--all`). Los CA-1 a CA-10 pasan, y el F-01 de la ronda 1 quedó cerrado conforme al arbitraje de la ronda 2.

## Decisiones (del usuario, 2026-11-09)

1. **Enmienda a la regla «sin fallos nuevos»** (`DECISIONES-LOOP.md` §6). Tal como estaba, ninguna unidad que empieza a tener código podía cumplirla. Desde ahora `--all` cuenta como pasado si **cada** identificador que falla en la rama cumple una de estas dos condiciones:
   - ya fallaba en main, en la base de la rama, y es de una unidad sin `evidence/cierre-demo.md`;
   - es **nuevo**, es de la unidad de la tarea, esa unidad no tiene `evidence/cierre-demo.md` y **no** pertenece a un paso que la tarea cubre.

   Un identificador de un paso que la tarea cubre debe quedar trazado. El revisor lo comprueba corriendo `--all` en la base y en la rama, y cruzando cada fallo nuevo con los pasos de la tarea. El orquestador escribe la enmienda en `DECISIONES-LOOP.md` §6 cuando la rama tenga integrado `origin/main`.
2. **Ronda 4 autorizada por el usuario**, por encima de RL-2. Su alcance es cerrado; ver abajo.
3. **F-03 (R4 solo sobre el atributo disparador)** queda como pregunta de diseño abierta. Se decide antes del Bloque C de U9 y no se toca en esta tarea.

## Qué entra en la ronda 4

1. **Integrar `origin/main`.** Hay conflictos en `CANDIDATAS.md` y `aidlc-docs/audit.md` (conservar las entradas de los dos lados) y en `pyproject.toml` y `uv.lock`: conservar los dos lados en `pyproject.toml` y regenerar `uv.lock` con `uv lock`, sin cambiar versiones a mano.
2. **F-01 (ROJO), la parte del alcance:** trazar `NFR-U9-30` (contratos de import-linter, Paso 1) y `NFR-U9-54` (SemVer, Paso 5) en el código o en las pruebas de `bias-monitoring/`, donde está implementado lo que exigen.
3. **F-02 (NARANJA):** el diagrama (`business-logic-model.md:35`) y el pseudocódigo (`:70`) de la BLM pasan a R4, igual que BR-U9-11 y la §3.
4. **F-06 (AMARILLO):** el orden de imports de `test_disparity_examples.py:16-18`.

Nada más. F-03, F-04 y F-05 van a `CANDIDATAS.md`.

## Qué comprueba el revisor en la ronda 4

- Que la integración de `origin/main` no cambió nada de lo revisado en la ronda 3: el diff de `bias-monitoring/` frente a la ronda 3 es solo F-01, F-02 y F-06.
- `--all` con la regla enmendada: en la rama, ningún fallo de un paso cubierto por la tarea (Pasos 1 a 5 de U9, bloques A+B), y en particular ni `NFR-U9-30` ni `NFR-U9-54`.
- `make -C bias-monitoring check` y `make -C platform check`.
