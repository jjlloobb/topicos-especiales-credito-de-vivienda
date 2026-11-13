# U12-T01 — Arbitraje de la ronda 1 (orquestador, 2026-11-12)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con dos ROJO, los dos en barreras de seguridad de U12. Es la última ronda (RL-2): si alguno sigue en ROJO, la tarea se para y va al usuario.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: el detector de verbos de `kubectl` no ve una orden encadenada ni otras formas indirectas | **Entra en la ronda 2** | Es la barrera estática de BR-U12-09 y NFR-U12-43, y el Paso 12 la reutiliza sobre `demos/` |
| F-02 ROJO: el filtro de evidencias deja valores entre comillas y otras formas de secreto | **Entra en la ronda 2** | CA-6: un secreto escrito en una evidencia versionada |
| F-03 NARANJA: PBT-U12-01 casi no ejerce la propiedad (0 de 4 mutaciones muertas) | **Entra en la ronda 2** | Las PBT no se recortan, y el `sampler` es el que arma el lote de D2. El arreglo es solo de pruebas |
| F-05 AMARILLO: lotes de 25 entradas en PBT-U12-04 frente a 1 a 2 000 | **Entra en la ronda 2** | Es un cambio de una línea en el generador, y CA-10 dice el rango |
| F-04 AMARILLO: la barrera compara por `environment.name` | **Va a `CANDIDATAS.md`, destino U12-T02** | Hoy ninguna entrada externa lo produce; U12-T02 es la que construye el entorno desde la configuración |

## Lo que se espera de la ronda 2

El principio para las dos barreras es **fallar cerrado**: lo que el detector o el filtro no entiende es un hallazgo o un error, no un pase. No se pide un analizador completo de shell ni de Python.

- **F-01, detector de verbos.**
  - Cada aparición de `kubectl` en una línea se juzga por separado: `&&`, `||`, `;`, `|` y la continuación de línea con `\`.
  - Una bandera global que no esté en la lista conocida es un hallazgo (no se adivina si lleva valor).
  - Toda aparición de `kubectl` o `argocd` que no sea una invocación directa y legible es un hallazgo: el nombre en una variable (`K=kubectl`), `xargs kubectl`, `eval`, y en Python la concatenación, el f-string, el nombre en una variable y la lista que no sea un literal cuyos elementos siguientes son literales.
  - `kubectl auth` solo admite `can-i` como palabra siguiente; cualquier bandera entre las dos es un hallazgo.
  - `scan_tree` recorre todo archivo de texto del árbol que se le da, no una lista de extensiones.
  - Casos de prueba: como mínimo, cada una de las entradas que el revisor lista en F-01 (las tres encadenadas, las cinco de shell, las cuatro de Python, el `.bash` y `argocd` en variable), cada una con su rojo antes del arreglo. Las formas legítimas que ya pasaban siguen pasando.
- **F-02, filtro de evidencias.**
  - El valor de una cabecera sensible se redacta hasta el fin de la línea, con comillas o sin ellas. Entran `Cookie`, `Set-Cookie`, `Authorization` y `X-Vault-Token`, también en la forma `nombre=valor`.
  - Los campos sensibles en JSON y en formularios se redactan con las comillas escapadas bien leídas; entra `client_secret`.
  - `ensure_clean` busca cada secreto cargado en sus formas: literal, escapado en JSON, sin espacios ni saltos de línea, y sin distinguir mayúsculas donde el secreto no las distingue (la semilla Base32). Si tras redactar queda un trozo reconocible de un secreto cargado, es error, no evidencia.
  - Casos de prueba: como mínimo, cada entrada que el revisor lista en F-02 (las tres principales y las seis del barrido), cada una con su rojo antes del arreglo.
- **F-03, PBT-U12-01.** Un generador con poblaciones grandes y concentradas, de modo que haya celdas con 30 filas o más y `min_per_cell` ≥ 10, y celdas llenas y cortas a la vez. Una propiedad o prueba que exija que la semilla influye (semillas distintas, muestras distintas) y que `normal` no devuelve el orden de entrada. Las cuatro mutaciones del revisor (SM1 a SM4) deben morir por la PBT; la bitácora lo registra con la semilla.
- **F-05, PBT-U12-04.** Lotes de hasta 2 000 entradas, sin perder los empates ni la frontera de 1 800 s.
- **Sin cambios fuera de eso.** `guard`, `credentials`, `report`, `rt2_latency` y `story_map` no cambian, salvo lo que un caso nuevo destape.
- **Se vuelven a correr:** CA-1, CA-3, CA-6, CA-7, CA-8, CA-10, CA-12 (cobertura al 100 % de ramas en `report` y `sampler`), CA-14 y CA-18. Las semillas de las corridas rojas se guardan esta vez.
