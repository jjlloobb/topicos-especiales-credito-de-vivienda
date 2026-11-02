# Arbitraje del orquestador — U01-T04, antes de la revisión de la ronda 1

**Empujón del codificador** (commit `7477f42`, `bitacoras/U01-T04.md`): CA-2 no pasa porque `seed-vault.sh grafana-token` deja vivo el `port-forward`. `kill "$forward"` mata el subshell de la función `kube`, no a `kubectl`. La tarea deja `seed-vault.sh` fuera de alcance, así que el codificador no lo tocó y pidió decisión.

**Decisión: entra en el alcance.**
- La tarea lo prevé: «Cambiar `seed-vault.sh`, salvo que la prueba destape un defecto real: en ese caso, empuja de vuelta». El empujón llegó y se decide aquí.
- CA-2 es un criterio de esta tarea y prueba justo lo que el PR 19 decía corregir. Pasarlo a candidatas dejaría la tarea sin cumplir su criterio, o con una prueba en rojo en `main`.
- El arreglo propuesto es de una línea y no cambia otros modos del script.

**Condiciones:**
- El cambio en `seed-vault.sh` se limita al lanzamiento del `port-forward` de `grafana-token`.
- La bitácora registra el par falla-pasa de CA-2 sobre el script de `650823f` y sobre el corregido.
- El revisor comprueba que el defecto existe y que el arreglo no rompe los demás modos.

Lo que sigue sin probar: el comportamiento con un `kubectl` real, porque la tarea prohíbe correr nada contra un clúster.
