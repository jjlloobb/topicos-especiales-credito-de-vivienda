# U12-T04 — Arbitraje de la ronda 1 (orquestador, 2026-11-13)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con cuatro ROJO: tres en los guiones y los PR preparados, que fallarían o mentirían delante del público, y uno de un criterio. Es la última ronda (RL-2).

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: el paso 6 de D1 dice que la alerta se apaga al revertir F22, y no se apaga | **Entra en la ronda 2**, con la decisión de abajo | El `verify` del paso fallaría siempre |
| F-02 ROJO: las plantillas de `proxy-staging` y `rt3-staging` no aplican con el modelo de referencia ya promovido | **Entra en la ronda 2** | El estado de la demo es justo ese |
| F-03 ROJO: el cierre de D2 no es ejecutable y su `verify` da OK sin serlo | **Entra en la ronda 2** | `rt2` se quedaría una hora esperando y el proxy sesgado seguiría activo |
| F-04 ROJO: dos `# pragma: no cover` nuevos; la bitácora dice que no hay | **Entra en la ronda 2** | CA-16. Y la bitácora se corrige |
| F-05 NARANJA: `journey-7-3` lee `FailClosedPersistente` antes de que cumpla su `for: 1m` (≈ 14 % `no ejecutado`) | **Entra en la ronda 2** | D1 saldría `no ejecutado` una de cada siete veces |
| F-06 NARANJA: `rt3 --closing` sin prueba, y reescribe el registro de `rt3` | **Entra en la ronda 2** | Es un paso del guion de D1; un cierre `no ejecutado` haría repetir RT-3 entero |
| F-08 NARANJA: `PresenterReactivation` acepta una reactivación de un ensayo anterior | **Entra en la ronda 2** | Daría por buena una reactivación que el presentador no hizo |
| F-10 NARANJA: `rt2` interrumpida por una excepción pierde la retoma | **Entra en la ronda 2** | D2 dura más de 75 min; un Ctrl-C reenviaría el lote |
| F-09 NARANJA: `live.py` con 0 %, cita una prueba que no existe, deja backends sin cerrar, pierde la ventana TOTP y usa una ruta literal | **Entra en la ronda 2** | Es lo primero que corre en kind, y la ruta literal choca con el requisito de que la demo corra en otra máquina |
| F-07 NARANJA: el filtro no limpia un HAR dentro de una cadena JSON, que es como `Store` escribe; y coste cuadrático | **Entra en la ronda 2** (lo que `Store` escribe y el coste) | La enmienda del despacho pedía proteger lo que de verdad se escribe |
| AMARILLO: la prueba de mundo cerrado no ve el orden de los pasos | **Entra en la ronda 2** | Dos de las mutaciones del revisor (secciones en orden imposible) sobreviven |
| AMARILLO: D2-2 y D4-1 dicen «no observable» y están en `manifest.json` | **Entra en la ronda 2** | Los `verify` ya leen ese archivo |
| Los demás AMARILLO (cabecera `++` en el detector, `scrub` borra `"name"`, `open` con modo variable, un comentario de prueba desfasado, el README de `promocion`, la estimación de `decisions`) | `CANDIDATAS.md` | No cambian un resultado |

## Decisiones del orquestador para la ronda 2

- **F-01, qué dice el paso 6 de D1.** Lo que ocurre en el sistema es lo correcto: los casos de la sonda quedaron en `no_disponible`, que es «escalado como incidente técnico», y la alerta sigue mientras nadie los reintente. El guion y su `verify` se corrigen para decir **lo que pasa**: al revertir F22 vuelven los cinco recursos y un caso **nuevo** recorre el flujo y termina en `listo`; `FailClosedPersistente` **sigue** en `firing` por los casos de la sonda. Si el reintento del CRO existe de extremo a extremo en `main` (ruta del BFF y vista de la consola para el rol), se añade como paso **opcional** que apaga la alerta, con su `verify`; si no existe (la vista de fallos está diferida), no se inventa: la sección «Qué deja sucio» lo dice, y dice que no afecta a D2, D3 ni D4.
- **F-02.** Las plantillas no llevan como contexto el estado vacío de `inferenceServices`. El parche se genera sobre el archivo de values **tal como esté** (con la misma función que usa `promotion-tool`, o una plantilla sin ese contexto). La prueba lo aplica sobre los dos estados: lista vacía y modelo de referencia promovido.
- **F-03.** El guion de D2 sigue la secuencia real de `promotion-tool` (léela en `governance/docs/` y en el código de `vectra_promotion`): incluye `post-activation-pr` tras activar, y en el cierre el `rollback-pr` y el `mark-active` del modelo de referencia, en el orden en que la herramienta los admite. `rt2` no se queda esperando una hora por un paso que el guion no nombra: el texto al operador dice qué falta. El `verify` del cierre comprueba que el modelo de referencia está `activo` en governance (por el manifiesto o la lectura que K16 permita), no solo que el `InferenceService` esté `Ready`.

## Lo que se espera de la ronda 2

- **F-01, F-02, F-03:** lo de arriba, cada uno con su prueba y su rojo. La prueba de mundo cerrado comprueba además el **orden** de las secciones dentro de cada guion (`prepare` antes de `rt5`; `rt2-setup` antes de `rt2`; `decisions` antes de `rt2`), y las mutaciones del revisor que sobrevivían mueren.
- **F-04:** sin `pragma: no cover` nuevos; la bitácora dice lo que hay.
- **F-05:** `journey-7-3` sondea la alerta durante un plazo tras la escalada (reloj inyectado en la prueba), en vez de leerla una vez.
- **F-06:** `rt3 --closing` con prueba; su resultado se registra aparte y no reescribe el de `rt3`.
- **F-08:** `PresenterReactivation` mira desde el `recorded_at` del congelamiento actual, como `verify_reactivation`; prueba con una reactivación de un ensayo anterior, que no debe contar. La prueba no debe poder colgarse: plazo con reloj inyectado.
- **F-10:** el estado de `rt2` se guarda al terminar cada fase, no solo al final; una interrupción retoma en la fase donde paró.
- **F-09:** el armado de `LiveBackend` se prueba sin clúster (con `runner=` y `vault_transport=`); `all` cierra el backend anterior; la ventana TOTP se conserva entre clientes del mismo usuario; ninguna ruta literal del repositorio: la ruta de los datos llega por opción o por el manifiesto. El docstring cita pruebas que existen.
- **F-07:** el filtro limpia las cabeceras sensibles también cuando el HAR va dentro de una cadena JSON (lo que `Store` escribe con `json.dumps`); y el recorrido tiene coste acotado (16 KB de `\"` en milisegundos, no en segundos). Sin romper lo que ya pasaba.
- **AMARILLO:** D2-2 y D4-1 ganan su `verify` contra `manifest.json`.
- `cli.md` y la bitácora recogen los cambios. Nada más cambia.
- **Se vuelven a correr:** CA-2, CA-3, CA-5, CA-6 a CA-14, CA-16, CA-20 (`make -C system-verification check`, con las semillas) y CA-18.
