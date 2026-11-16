# U12-T09 — Arbitraje de la ronda 1 (orquestador, 2026-11-16)

Informe: `ronda-1.md`. El revisor escribió NO-VERDE **sin ningún ROJO**: dos NARANJA y cinco AMARILLO. El veredicto se conserva tal cual. El revisor corrió `make -C system-verification check-fast` entero, con Docker, y pasa: eso cierra la salvedad de CA-6 del codificador.

**Decisión: hay ronda 2, acotada.** RL-2 permite dos rondas. La abro sin ROJO porque F-01 está en la guía que el operador va a seguir en los próximos días: tal como quedó, el procedimiento nuevo (clon limpio para `promotion-tool`, evidencia fuera del árbol) no dice dónde se llenan las plantillas ni cómo llegan al PR de verificación, y cualquiera de los dos caminos posibles rompe otro paso. Y porque `main` cambió desde que se redactó la tarea: U01-T16 se fusionó (#195), así que la guía ya puede decir lo que existe.

| Hallazgo | Decisión | Qué se pide en la ronda 2 |
|---|---|---|
| F-01 NARANJA | Ronda 2 | Un solo camino escrito, de punta a punta: en qué árbol se llenan las plantillas `00` a `12`, `cierre-demo.md` y el plan; cómo llegan al PR de verificación junto con `$EVID`; y que eso no ensucie el clon de `promotion-tool` ni bloquee el `git pull --ff-only`. Corrige la ruta de la línea 751. Con su prueba de la guía |
| F-02 NARANJA | Ronda 2 | Las tres pruebas que faltan: un 4xx distinto de 429 no se reintenta en las lecturas; el manifiesto conserva `sent` y `accepted` si la espera se interrumpe; `idempotency_key_invalid` no se reenvía. Cada una debe matar la mutación del revisor |
| F-03 AMARILLO | Ronda 2 | La forma escrita de empezar otra verificación con `EVID` fijo, y qué commit nombra el directorio |
| F-04 AMARILLO | Ronda 2 | Corrige la candidata contra `gateway-address.sh` (el Service se llama `api-gateway` por `GatewayNamespace`; lo midió además el orquestador en el clúster) y lo que la guía y el README digan al respecto. `CANDIDATAS.md` solo se añade: escribe una entrada de corrección, no edites la anterior |
| F-05 AMARILLO | Ronda 2 | Borrar la rama remota es una escritura en GitHub: o va como orden del operador con su nombre, o la guía ofrece el camino que no la necesita |
| F-06 AMARILLO | Ronda 2 | Añadir `sim_normal_lectura_agotada` a `scenarios.md` |
| F-07 AMARILLO | `CANDIDATAS.md` | Ya anotada por el codificador; el revisor comprobó que no puede hacer fallar D1 |

**Añadido por el orquestador, por el cambio de `main` (U01-T16 fusionada en #195):**

- Quita la excepción `PENDING` de `test_kind_guide.py`: `platform/kind/gateway-address.sh` ya existe.
- «Después de reiniciar la máquina» y R-7 siguen diciendo que `cloud-provider-kind` se lanza con `--rm` y que resembrar da «claves nuevas» (candidata del codificador de U01-T16). Ponlo al día con lo que hoy dicen `platform/kind/seed-vault.sh` y `platform/runbooks/install.md` («Vault reiniciado», pasos 3, 8 y 9; «Tras reiniciar la máquina»): la siembra recupera de los `Secret`, informa qué generó, y lo generado (seis rutas hoy) pide reimportar el realm y reiniciar Valkey, los Sentinel y `envoy-ratelimit`. No copies el runbook: remite a él por sección.

Fuera de la ronda 2: todo lo demás. No se toca `platform/`.
