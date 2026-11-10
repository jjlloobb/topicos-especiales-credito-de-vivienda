# Arbitraje de la ronda 1 — U04-T05 (Paso 13)

Orquestador, 2026-11-09. Informe: `revisiones/U04-T05/ronda-1.md`. El revisor dio NO-VERDE sin ningún ROJO; los CA-2 a CA-6 pasan. Por RL-2, un NARANJA va a `CANDIDATAS.md` **salvo que rompa una de las cuatro demos**. Aplicado hallazgo por hallazgo:

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-03 · el Job no monta `vectra-internal-ca` ni `VECTRA_CA_BUNDLE` y nunca envía el informe | **Entra en la ronda 2** | Rompe D2: `rt2-setup` se queda en `en_validacion` hasta el timeout. También el escenario 2 de U04-T07 |
| F-05 · NFR-U4-23 sin trazar | **Entra** | La regla enmendada de `--all` (`DECISIONES-LOOP.md` §6) exige trazar los ids de los pasos que la tarea cubre |
| F-04 · hadolint DL3008 (`libgomp1` sin versión) | **Entra** | Una línea; la regla de admisión de imágenes del repo usa `hadolint` |
| F-01 · `initial_disparity` con `p < cutoff` en vez del `outcome` de BR-U7-04/05 | **Entra** | No rompe D2 (el oráculo solo pide `initial_disparity` no vacía), pero contradice BR-U9-01 y BR-U7-04/05, y ya hay una candidata de U5 que advierte justo esto. Se corrige en el mismo Paso 13 |
| F-02 · `cutoff`, `n_min`, umbral y `auc_target` como literales | **Entra solo lo que necesita F-01** | El lanzador pasa al Job los parámetros normativos de la política activa (los que pide BR-U7-04/05). `n_min`, umbral y `auc_target` quedan en candidatas |
| AMARILLO (tres) y candidatas del informe | `CANDIDATAS.md` | RL-2 |

## Qué entra en la ronda 2 (la última por RL-2)

1. **F-03.** La plantilla de `job_manifest()` monta la CA interna (`vectra-internal-ca`, como la monten los demás clientes con `private_key_jwt`; mira cómo lo hace U3 o el `ServiceTokenProvider` de `vectra_common`) y fija `VECTRA_CA_BUNDLE`. Una prueba sin `poster` inyectado comprueba que, con el manifiesto generado, el proveedor real de tokens construye su contexto TLS sin `ContractViolation` (puede usar una CA de prueba).
2. **F-01 y lo necesario de F-02.** `initial_disparity` cuenta como favorable el `outcome` `favorable` de BR-U7-04/05, con `revision_requerida` como no favorable (BR-U9-01): normativo nulo, tasa sobre la usura y baja confianza según el `domain_envelope.json` del paquete. El lanzador pasa al Job los parámetros normativos de la política activa (`cutoff_efectivo` y los que use BR-U7-04). El oráculo de la prueba **no** repite la fórmula del código: usa casos construidos a mano con su `outcome` esperado, incluido al menos uno de cada causa de `revision_requerida`. Si BR-U7-04/05 necesita algo que el Job no puede obtener, **detente y repórtalo**.
3. **F-04.** `libgomp1` con versión fijada, y `hadolint` en 0.
4. **F-05.** NFR-U4-23 trazado en la prueba que lo cubre.

Nada más. El revisor de la ronda 2 comprueba esos cuatro puntos, CA-2 a CA-6 y `--all`.
