# U12-T02 — Arbitraje de la ronda 1 (orquestador, 2026-11-13)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con un solo ROJO (F-01), que es de una línea. Es la última ronda (RL-2).

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: un comentario de `pyproject.toml` con el nombre `vectra_common` impide que CA-1 imprima `OK` | **Entra en la ronda 2** | Rompe el criterio tal como está escrito |
| F-03 NARANJA: un fallo de TLS escapa como `playwright.Error` y su traza trae `state`, `nonce` y `code_challenge` | **Entra en la ronda 2** | El módulo trata el `nonce` como secreto, y esa excepción puede acabar en una evidencia o en la terminal del presentador. El arreglo es acotado |
| F-05 AMARILLO: el filtro de evidencias no limpia un HAR con el orden `value`, `name`, ni un formulario que empieza por `code=` | **Entra en la ronda 2** | Es la barrera que la enmienda del despacho pidió cerrar (F-08 de U12-T01), y son dos patrones |
| F-07 AMARILLO: una aserción con `or` siempre verdadera, y el CA-2 viejo en la bitácora | **Entra en la ronda 2** (solo esas dos) | Una prueba que no puede fallar no prueba nada; la bitácora debe decir lo que hay |
| F-02 NARANJA: la confianza TLS del formulario es la de Node (`NODE_EXTRA_CA_CERTS`), no la huella SPKI de P-2 | **Entra en la ronda 2 solo el docstring**; el resto, `CANDIDATAS.md`, destino U12-T04 | El revisor comprobó que no se acepta cualquier certificado. Cerrar la confianza de los dos caminos es de la imagen (Paso 15) |
| F-04 NARANJA: el conductor lista la bandeja una sola vez y no espera a `listo` | **`CANDIDATAS.md`, destino U12-T03** | El diseño no pide esperar, y la sección `decisions` que lo orquesta se cierra en T03 y T04. Afecta a D4: se le pasa a U12-T03 como encargo |
| F-06 AMARILLO: la lista de hosts de la bóveda es global, no por entorno | **`CANDIDATAS.md`** | Depende de cómo se resuelva el camino a la bóveda (U12-T05) |
| F-07, lo demás (`max_examples=20`, la ventana recortada en `1e-6`, 11 min de `make check`) | **`CANDIDATAS.md`** | Mejoras |
| Realm de kind: los dos defectos, reproducidos con una configuración fiel a kind | **Tarea de U2 aparte** (U02-T22) | Fuera del alcance de U12-T02. Sin ella nadie inicia sesión en kind |

## Lo que se espera de la ronda 2

- **F-01:** el comentario de `pyproject.toml` se reescribe sin ese nombre. El comando literal de CA-1 imprime `OK` y la bitácora pega la salida completa, con la línea del bucle.
- **F-03:** un fallo de TLS o de red durante el login termina en un `OidcError` con código estable, también cuando el fallo ocurre al cerrar el contexto. El mensaje y la traza que salen del módulo no contienen `state`, `nonce`, `code_challenge`, `code_verifier` ni la URL de autorización. Prueba con su rojo (la «prueba D» del revisor: Node sin la CA).
- **F-05:** el filtro limpia el objeto HAR con cualquier orden de claves, y `code=` al principio de un cuerpo de formulario. `{"code": "conflict_state"}` sigue intacto. Casos de prueba con su rojo.
- **F-07:** la aserción de `test_oidc_headless.py:280` deja de ser siempre verdadera; se comprueba con una mutación que la hace fallar. La bitácora corrige el CA-2 pegado.
- **F-02:** el docstring de `clients/oidc.py` dice lo que de verdad protege cada camino.
- **Se vuelven a correr:** CA-1, CA-3, CA-4, CA-5, CA-6, CA-20 (`make -C system-verification check`, con la semilla) y CA-24.
- Nada más cambia.
