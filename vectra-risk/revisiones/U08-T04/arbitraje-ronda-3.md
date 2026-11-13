# U08-T04 — Arbitraje de la ronda 3 (orquestador, 2026-11-12)

Informe: `ronda-3.md`. Veredicto NO-VERDE. Los cuatro hallazgos de la ronda 2 quedaron cerrados y el diff de la ronda 3 no desborda. El ROJO es otro: `make -C case-management check` falló en la corrida del revisor (`1 failed, 393 passed`) por PBT-U8-01, con una semilla que las corridas anteriores no habían tocado.

**El usuario autorizó el 2026-11-12 una ronda 4 acotada** al modelo de la PBT. Es la cuarta ronda, el límite del contrato del loop (`loop/README.md`).

| Hallazgo (ronda 3) | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: el modelo de PBT-U8-01 ignora la caché de `serving-config`; falla con algunas semillas | **Entra en la ronda 4** | Una PBT que falla según la semilla haría fallar `make check` y el CI de `main` de forma intermitente. El código de producción es correcto (NFR-U8-15) |
| F-02 AMARILLO: la frase del reloj de BR-U8-08 se pasa un poco | **Entra en la ronda 4** | Una frase |

## Lo que se espera de la ronda 4 (y nada más)
- **F-01:**
  - rojo primero: la reproducción del revisor (`@reproduce_failure('6.170.14', b'AABBBwBBAUEBAUEBQQABQQQAAAAAAQEBAEEJQRlBAQ==')`, en `ronda-3.md`) falla sobre la PBT actual; se registra la salida y el decorador **no** queda en el commit;
  - el modelo de referencia tiene en cuenta la caché de `serving-config` (TTL de 5 s, `SERVING_CONFIG_CACHE_TTL`): con governance caído y la caché fresca, el resultado esperado es el que da la configuración en caché; con la caché vencida, `serving_config_unavailable`. El modelo lleva su propio reloj de la caché: no lee el estado interno del cliente bajo prueba. No se resuelve quitando el comando `cfg_down` ni dejando de explorar el caso;
  - barrido de clase: los guiones forzados que terminan en `_late` sin avanzar el reloj (`late_after_thaw`, `late_after_retake`, `late_after_retry`) y cualquier otro comando cuyo resultado dependa de la caché quedan revisados con el mismo criterio;
  - las dos ramas quedan ejercidas: un contador de recorrido nuevo, «governance caído con la caché fresca», y otro con la caché vencida, los dos > 0 con el perfil `ci`;
  - estabilidad: PBT-U8-01 pasa con el perfil `ci` en **8 corridas con semillas distintas**, anotadas en la bitácora, más la reproducción del revisor ya en verde;
  - la propiedad no se afloja: `git diff` de la PBT solo cambia el modelo de la caché, los generadores y los contadores. La mutación de la ronda 2 (guarda de toma anulada) sigue muriendo con la PBT, y la bitácora lo registra.
- **F-02:** BR-U8-08 dice que la condición es suficiente y que el reloj que cuenta es el de las tomas.
- **No se toca código de producción** (`src/`). Si al corregir el modelo aparece un defecto real del código, el codificador para y lo reporta con su rojo.
- **Se vuelven a correr:** CA-2, CA-6 y `make -C case-management check` una vez.

Si queda un ROJO tras esta ronda, la tarea se para y va al usuario.
