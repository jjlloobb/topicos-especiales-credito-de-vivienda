# U12-T06 — Verificación consolidada en kind y cierre de `system-verification`

**Unidad:** U12 `system-verification`
**Historias que verifica:** las del mapa de domain-entities §4.2 que quedan dentro del recorte (US-101, US-111, US-303 y las demos de US-304, 503, 504 y 505), en kind. Ninguna nueva. Es la última tarea de U12 y la última de la demo.
**Depende de:**
- **U12-T03 fusionada en `main`** (PR #___, commit de fusión `_______`: **por completar al fusionar**). En codificación al redactar. Da los oráculos de RT-2, RT-3, RT-5 y `SIM-NORMAL`, y `aidlc-docs/construction/system-verification/code/scenarios.md`.
- **U12-T04 fusionada en `main`** (PR #___, commit `_______`: **por completar**). Redactada, sin empezar. Da la CLI `vectra-verification` con sus 8 secciones, `store.py`, el manifiesto, los cuatro guiones con sus `verify/*.sh`, `demos/prs/`, `tests/unit/test_demos_closed_world.py` y `code/cli.md`.
- **U12-T05 fusionada en `main`** (PR #___, commit `_______`: **por completar**). Redactada, sin empezar. Da la imagen, `README.md`, `seccomp/chrome.json`, `tests/image/`, el `Makefile` con `check`, `check-fast`, `image`, `test-image` y `traceability`, y `evidence/cierre-demo.md` con solo «Diferido por la demo».
- **Ya en `main`** (comprobado en `7ec1478`): U12-T01 y U12-T02 (Pasos 1 a 6 en `[x]`), U02-T22 (PR #168, realm corregido) y U00-T04 (PR #167, `VECTRA_ASSERTION_AUDIENCE`).
- **Al empezar, lee `code/cli.md`, `code/scenarios.md`, `README.md` y los cuatro guiones de tu rama.** Lo que digan rige sobre lo que esta tarea supone de T03, T04 y T05. Cada diferencia va a la bitácora.

**Rama:** `tarea/U12-T06`, desde `origin/main` **después** de fusionar U12-T05.

Bloques G y H del plan de U12 (`aidlc-docs/construction/plans/system-verification-code-generation-plan.md`, Pasos 18 y 19). Partición de U12 (decisión del usuario, 2026-11-13; `DECISIONES-LOOP.md` §10; `demo-recorte-funcional.md` §8, fila U12): T01 A+B (1–4) · T02 C (5–6) · T03 D (8, 10) · T04 E (12, 13) · T05 F (15, 17) · **T06 G+H (18, 19)**.

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 18 Primera verificación completa en kind | **E\*** | Entra con las 8 secciones del Paso 13 (`prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11`, `report`). Es además la **verificación consolidada** de U3, U7, U8, U9, U10 y U11 | Enmienda §3 U12, fila «18 · 19: E\*, E\*, Con las secciones del Paso 13» (`demo-recorte-funcional.md`, línea 297); §8, «Regla» (líneas 424 a 427); alcance §3 U12: «18 Primera verificación completa en kind: E\*, Con las secciones del Paso 13» |
| 19 Cierre | **E\*** | Cierre acotado a la demo, con `evidence/cierre-demo.md` | Alcance §3 U12: «19 Cierre: E\*, Cierre acotado»; alcance §2, regla 4 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6. No hay PBT nuevas.

---

## Quién hace qué (léelo primero)

**AUTONOMIA-01.** Ningún agente aplica nada al clúster. Fuentes: plan de U12, líneas 28 a 31 («La verificación real la ejecuta **un operador en kind** después de un PR aprobado»); alcance §2, regla 5 («lo que toca el clúster lo ejecuta el operador tras un PR aprobado»); `.claude/agents/codificador.md`, regla 8 («Ningún comando toca infraestructura compartida»). Los PR los abre y fusiona una persona. Las sincronizaciones las hace el operador.

**El precedente.** Las tres guías de kind que existen se resolvieron igual: `identity-edge/docs/paso-16-kind.md` (U2), `tareas/U04-T07-kind-y-cierre.md` (U4) y `tareas/U06-T03-kind-y-cierre.md` (U6). El codificador escribió la guía, los guiones y las plantillas. El PR se fusionó con la evidencia «pendiente del operador» (U04-T07, CA-6: «el PR puede fusionarse con la guía y la evidencia pendiente, como hizo U2»). El paso de kind del plan quedó `[ ]` con la nota «guía lista, pendiente del operador» hasta que se adjunte la evidencia (plan de U4, línea 239; plan de U6, línea 124).

**Estado real de esas guías en `main` (`7ec1478`).** Ninguna tiene evidencia adjunta:
- U2: no existe `aidlc-docs/construction/identity-edge/evidence/`; el Paso 16 y el 18 de su plan están en `[ ]` (líneas 277 y 297).
- U4: las nueve plantillas de `aidlc-docs/construction/governance/evidence/kind/` dicen «Estado: pendiente del operador».
- U6: `aidlc-docs/construction/model-serving/evidence/kind/` solo trae `_plantilla.md`.

Por eso esta tarea no puede dar por instalados U2, U4 y U6. La guía los encadena (P-2).

| Quién | Qué hace | Con qué |
|---|---|---|
| **Codificador** (esta tarea, sin clúster) | La guía ordenada del operador; el inventario único de lo que solo se ve en kind; los guiones de lectura que faltan; el humo de login y de flujo base; las plantillas de evidencia; las pruebas sin clúster que atan todo eso al repositorio; el cierre (Paso 19) | Dobles, Testcontainers y Docker local. Ningún kubeconfig |
| **Operador** (el usuario, en kind) | Publica imágenes y fija digests por PR; sincroniza por waves; arranca política y modelo; corre el humo, las 8 secciones y las cuatro demos; devuelve el clúster a su estado; abre el **PR de verificación** | La guía, los guiones, la imagen de U12 y su kubeconfig de administrador de kind |
| **Revisor** (agente, sin clúster) | Ronda normal sobre el PR de esta tarea. Después, **lectura de evidencia** sobre el PR de verificación: no ejecuta nada contra kind, coteja esperado y obtenido, y asigna cada fallo a una unidad (P-1) | Solo lectura |
| **Personas de `CODEOWNERS`** | Aprueban y fusionan el PR de esta tarea y el PR de verificación (`.github/CODEOWNERS`, línea 9: `vectra-risk/system-verification/evidence/`) | GitHub |

**Cómo vuelve la evidencia al loop.** En un PR, el **PR de verificación**, que abre el operador desde una rama `verificacion/<fecha>-<commit>`:
1. `system-verification/evidence/<fecha>-<commit>/` con `manifest.json`, `verification-report.md` y lo que escribió cada sección. Lo escribe la herramienta (`store.py`, dependencia de U12-T04). Nadie lo edita a mano.
2. `aidlc-docs/construction/system-verification/evidence/kind/NN-*.md`: las plantillas de esta tarea, llenas (comando, salida, esperado frente a obtenido), con «Estado: completa» o «fallida».
3. `aidlc-docs/construction/system-verification/evidence/cierre-demo.md`: la tabla del inventario con el resultado de cada entrada.
4. El plan de U12: el Paso 18 pasa a `[x] (U12-T06, acotado a la demo)`.

**Qué es «cierre» (Paso 19) cuando parte depende de una persona.** Hay dos cierres y no se mezclan:
- **Cierre de la tarea** (PR de `tarea/U12-T06`): `make -C system-verification check` en 0, la guía y sus pruebas, `cierre-demo.md` completo con cada entrada en «pendiente del operador», Paso 19 en `[x]` y Paso 18 en `[ ]` con «guía lista, pendiente del operador». Es lo que dice el plan: «La verificación en kind (Paso 18) se revisa como el PR de verificación».
- **Cierre de la demo** (PR de verificación fusionado): el informe lista cada RT, demo e historia con su resultado y no marca `pasa` sin evidencia. Un `falla` no impide fusionar la evidencia: la evidencia dice la verdad. Cada `falla` abre una tarea en la unidad dueña; solo un fallo que rompe una de las cuatro demos obliga a repetir esa demo.

---

## Alcance

**Dentro:** los Pasos 18 y 19 del plan. Texto literal. Lo que el recorte difiere va ~~tachado~~ con su cita y se repite en «Fuera».

### Bloque G — Verificación en kind (con aprobación humana)

- [ ] **Paso 18 — Primera verificación completa en kind** (E\*; la guía y las herramientas son de esta tarea; la corrida es del operador)
  - **Requisito previo**: un PR con los Pasos 1–17 aprobado por un humano, con U1–U11 instalados en kind, el modelo de referencia activo y el binding K16 presente.
  - **Orden** (revisión del plan de tareas de U12, 2026-10-10):
    1. el operador ejecuta `prepare`, que fija el `runId` y el `started_at`;
    2. abre el PR de los Jobs de prueba con el parche que produjo `prepare` (`vectra-risk-gitops/values/kind/` de ~~`bias-monitoring`, `decision-registry-rebuild` y~~ `case-management`; revisión de consistencia entre unidades, 2026-11-01) y sincroniza ~~las **tres Applications**~~ con prune (pendientes consolidados, 2026-10-10); **(Solo `case-management`: enmienda §3 U12, fila «13»: «El parche de `prepare` solo toca `case-management` (sin `bias-monitoring` ni `decision-registry-rebuild`)». `decision-registry-rebuild` no existe en `vectra-risk-gitops/components.yaml`.)**
    3. ejecuta las demás secciones en orden, ~~empezando por `network`, que lee los Jobs ya terminados (con `completionTime` posterior a `started_at`)~~. **(`network` se difiere: enmienda §3 U12, fila «8b · 9 · 11: D», y §0, punto 2: «En U12: RT-1/RT-4 en el simulador, `LOGS-NO-PII` y `network`». La primera sección tras `prepare` es `decisions`; el Job que se lee es el de RT-5, en `rt5`, con la misma regla de frescura.)**
  - El operador ejecuta todas las secciones en orden, con los PRs preparados de RT-3 y RT-2 y sus reversiones, y el día siguiente la sección `u11`; genera el informe y abre el PR de verificación. **(«Todas» son las 8 del Paso 13 que entran: enmienda §3 U12, fila «18 · 19»: «Con las secciones del Paso 13».)**
  - Diseño: BR-U12-04..13; NFR-U12-30, 31; INF-U12-01..05. Historias: ~~US-609 y~~ las de domain-entities §4.2. **(US-609 es la carga, Paso 11: enmienda §3 U12, fila «8b · 9 · 11: D»; T3. Sale `no ejecutado`.)**
  - **Aceptación**: el PR de verificación con `evidence/<fecha>-<commit>/`, `manifest.json` y `verification-report.md`, revisado por `calidad` y `cumplimiento`; el informe lista cada RT, X, demo e historia con su resultado y no marca `pasa` sin evidencia.

### Bloque H — Cierre

- [ ] **Paso 19 — Cierre de la unidad** (E\*, cierre acotado)
  - **Aceptación**: `make -C system-verification check`, que corre en orden las verificaciones estáticas, las propiedades y las pruebas con dobles de los Pasos 1–17 y termina en 0. La verificación en kind (Paso 18) se revisa como el PR de verificación.

### Lo que el Paso 18 consolida (enmienda §8)

«Los bloques de "verificación en kind" por unidad se quitan para U3, U7, U8, U9, U10 y U11 […] Sus escenarios que sostienen una demo los cubren los ensayos de las cuatro demos y las secciones de `verify` de U12 (Paso 18)» (`demo-recorte-funcional.md`, líneas 424 y 425). «U4 y U6 conservan sus guías de kind […] y el operador las ejecuta antes de U12» (línea 427). «**Costo aceptado:** un fallo en kind aparece en U12 y cuesta más ubicar su unidad» (línea 429): por eso la guía trae una tabla de síntomas por unidad.

### Estructura de destino: lo que esta tarea crea o llena

```text
vectra-risk/system-verification/
|-- Makefile                                   # se modifica: `shellcheck` y `links` alcanzan `docs/`; nada mas
|-- docs/
|   |-- paso-18-kind.md                        # nuevo: la guia del operador, por fases
|   `-- kind/
|       |-- inventario.yaml                    # nuevo: la lista unica (K-01 a K-66), legible por las pruebas
|       |-- arranque.sh  observabilidad.sh  memoria.sh  identidad.sh  estado-final.sh   # nuevos: solo lectura
|       `-- humo.py                            # nuevo: login por rol y un caso de punta a punta, con los clientes de `src/`
`-- tests/
    |-- unit/         test_kind_guide.py  test_kind_inventory.py  test_kind_scripts.py   # nuevas
    |-- unit/         test_kubectl_verbs.py                                              # se amplia: recorre `docs/`
    `-- integration/  test_kind_smoke.py                                                 # nueva: `humo.py` contra dobles

vectra-risk/aidlc-docs/construction/system-verification/evidence/
|-- cierre-demo.md                             # se completa (U12-T05 dejo solo «Diferido por la demo»)
`-- kind/  00-prerrequisitos.md … 11-opcionales.md  12-duraciones-y-memoria.md   # nuevas: una plantilla por fase, «pendiente del operador»
```

Los nombres de los guiones y de las pruebas son una propuesta; lo que cambies va a la bitácora. Son fijos: `docs/paso-18-kind.md`, `docs/kind/inventario.yaml` y el directorio de plantillas.

**No** se crean: secciones nuevas de la CLI (las 8 son las del plan); `chart/`, `migrations/` ni el workflow de CI; nada dentro de `system-verification/evidence/` (sigue con `.gitkeep`: lo llena el operador).

### Cambios permitidos fuera de `system-verification/`

Uno por uno. Cualquier otro archivo fuera del directorio es un hallazgo.

1. `aidlc-docs/construction/plans/system-verification-code-generation-plan.md`: solo las casillas de los Pasos 18 y 19 (CA-11).
2. `aidlc-docs/construction/system-verification/evidence/cierre-demo.md` y `evidence/kind/*.md`.
3. `aidlc-docs/construction/system-verification/code/cli.md`: una sección corta que apunte a la guía. Nada más.
4. `CANDIDATAS.md` y `bitacoras/U12-T06.md` (nuevo).
5. `.github/CODEOWNERS`: **no cambia** (P-7).
6. `uv.lock` y `pyproject.toml` raíz: no cambian.

`platform/`, `vectra-risk-gitops/`, `identity-edge/`, `governance/`, `model-serving/`, `scoring-explainability/`, `case-management/`, `bias-monitoring/`, `console/`, `product-metrics/`, `decision-registry/`, `reference-model/` y `contracts/` **se leen, no se editan**. Tampoco los cierres de las otras unidades: sus filas «Pendiente en U12» se responden en el `cierre-demo.md` de U12, con la ruta y la línea de cada una. Si la guía revela un defecto de otra unidad, **detente y repórtalo**: es candidata o tarea de esa unidad.

---

## La guía del operador: `system-verification/docs/paso-18-kind.md`

Formato de `governance/docs/paso-20-kind.md`: por cada paso, el comando exacto, la salida esperada y la plantilla donde se guarda. La debe poder seguir una persona que no escribió el código.

**Reglas de la guía:**
- **No repite lo que ya está escrito.** Para publicar imágenes, sincronizar y arrancar política y modelo, remite por ruta y sección a los documentos dueños (tabla de abajo) y dice qué subconjunto hace falta. Si un documento dueño está mal, es un hallazgo de su unidad.
- **Todo comando propio de la guía es de solo lectura:** `kubectl get`, `logs`, `auth can-i` y `port-forward`; `curl` a un `port-forward`; `docker stats` y `free`; y la CLI de U12.
- **Las órdenes que escriben** van en bloques marcados «orden del operador» y solo pueden ser de la **lista cerrada** de P-4. La prueba de verbos lo comprueba (CA-3).
- **Cada espera dice cuánto dura y qué se mira mientras tanto.** Ninguna espera fija sin condición observable.
- **Cada fase termina con una puerta:** qué debe verse para seguir, y a qué unidad apunta cada síntoma si no se ve.
- Los nombres de recursos, namespaces, Applications, selectores, series, usuarios, secciones y opciones salen del repositorio. La prueba de mundo cerrado lo ata (CA-2).

**Documentos dueños a los que la guía remite** (existen en `7ec1478`):

| Para | Documento | Sección |
|---|---|---|
| Memoria, registro local, `sync`, bóveda, «Vault reiniciado» | `platform/runbooks/install.md` | «Antes de instalar» (línea 17), §5, §7 (línea 94; función `sync`, línea 98), §8, «Vault reiniciado» (línea 146) |
| U2: imágenes, secretos, sync y realm | `identity-edge/docs/paso-16-kind.md` | §3, §4 y §5 |
| Realm viejo y desbloqueo | `identity-edge/docs/realm-importacion.md` | «Qué hace el operador» (líneas 25 a 30), con la corrección de `revisiones/U02-T22/ronda-1.md`, F-01 |
| U3: imagen | `decision-registry/docs/imagen-kind.md` | «Publicar» (línea 22) |
| U4: imágenes, sync, política y modelo de referencia | `governance/docs/paso-20-kind.md` | §1 a §5; `governance/runbooks/kind-politica-de-referencia.md` |
| U6: imágenes, paquetes proxy y RT-3 en el model-store | `model-serving/docs/paso-11-kind.md` | §0 a §2 (paquetes: líneas 42 a 58) |
| U7, U8, U9, U11: imágenes y digests | `scoring-explainability/docs/imagenes.md`, `case-management/docs/imagenes.md`, `bias-monitoring/docs/imagenes.md`, `product-metrics/docs/imagenes.md` | Enteros |
| U10: imágenes | `console/README.md` | «Imágenes» |
| U12: imagen, orden `docker run`, prerrequisitos y lectura del informe | `system-verification/README.md` | **Dependencia de U12-T05** |
| Las cuatro demos y sus PR preparados | `system-verification/demos/*.md`, `demos/verify/*.sh`, `demos/prs/` | **Dependencia de U12-T04** |

### Fases, orden y tiempos

Las Applications de U3 a U11 están todas en la **wave 5** y `model-serving` en la 6 (`vectra-risk-gitops/components.yaml`, líneas 63 a 96). Sin auto-sync las waves no ordenan nada (`install.md`, línea 95): el orden dentro de la wave 5 lo fija esta guía.

| Fase | Qué | Orden y por qué | Tiempo estimado |
|---|---|---|---|
| **F0** Prerrequisitos | Memoria, kind arriba, bóveda sembrada, tareas en `main`, paquetes de U5, calendario | Antes de nada | 30 min |
| **F1** Imágenes y digests | Construir **del mismo commit** las imágenes de U3, U4, U6, U7, U8, U9, U10 y U11, publicarlas y fijar los digests en **un solo PR**; publicar la de U12 | Un solo PR: `ServingConfig` es estricto y un consumidor con el tipo viejo falla cerrado (cierre de U7, línea 42) | 60 a 90 min |
| **F2** Sync y arranque | U2 (si falta) → `decision-registry` → `governance` → **política** → `model-serving` → **modelo de referencia** → `scoring-explainability` → `case-management` → `bias-monitoring` → retirar el eco → `console-bff` y `console-spa` → `product-metrics` | La política va **antes** de `console-bff`: el runbook de U4 crea y borra una `ServiceAccount` `console-bff` temporal, y la del chart de U10 no debe existir aún (cierre de U10, línea 71). `product-metrics` va **el último**: si arranca antes que el registro, el dashboard queda vacío hasta 30 min (cierre de U11, línea 54) | 2 a 3 h (la validación del modelo tarda hasta 30 min) |
| **F3** Identidad y acceso | Realm, login por rol, tokens, bóveda, K16, Grafana, consola en el navegador | Tras F2: necesita el BFF y la SPA | 40 min |
| **F4** Flujo base | Una solicitud hasta `listo` y una decisión; puerta de las cuatro demos | Sin esto no se empieza ninguna demo | 15 min |
| **F5** `prepare` y D3 | `prepare` → PR de `runId` → sync de `case-management` → mirar la alerta en vivo | Orden del plan (Paso 18, puntos 1 y 2). El Job corre al sincronizar y la alerta dura ≈ 5 min: se mira **en ese momento** | 20 min |
| **F6** `decisions` (D4, día D) | 2 000 casos `normal` y el conductor; `rt5` al terminar | **BR-U12-06**: «Se corren **antes** de RT-2, con el modelo de referencia activo (sin congelar)». Tiene hora límite: lanzar antes de ≈ 22:18 UTC | ≈ 45 min |
| **F7** D1 (`rt3`) | RT3-a, c y d; PR de F22 apagado; esperar; PR de reversión; comprobar que vuelve a `listo` | Después de `decisions`: F22 apagado deja **todos** los casos en fail-closed. Antes de D2: debe estar revertido y comprobado antes del lote | ≈ 50 min (≥ 19,3 de espera, ≈ 21 hasta la alerta, 2 PR) |
| **F8** D2 (`rt2-setup`, `rt2`) | PR `proxy-staging`; `rt2-setup`; los PR de promoción; lote; `freeze`; 3 corridas de bias; reactivación; 1 corrida más; rollback; retirar staging | La más larga y la de más riesgo; termina con el rollback al modelo de referencia (BR-U12-10). Con la máquina sin otra carga (riesgo R-1) | ≈ 3 h (> 75 min de esperas, más 6 PR) |
| **F9** D4 (día D + 1 UTC) | `u11`; Grafana por `port-forward`; el dashboard «Producto» | No antes de ≈ 02:40 UTC (21:40 de Colombia del día D) | 15 min, tras la espera |
| **F10** Informe y estado final | `report`; `estado-final.sh`; PR de verificación | Al final | 30 min |
| **F11** Opcionales | Sondas que no sostienen ninguna demo | Solo después de F10: alguna reinicia pods | 30 min |

**Orden de las demos: D3 → D4 (día D) → D1 → D2 → D4 (día D + 1).** Razones:
1. Es el orden de las secciones de la CLI (`prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11`, `report`; plan, Paso 13) y el de business-logic-model §2.1. La guía no pide correr secciones fuera de orden.
2. **BR-U12-06** pone `decisions` antes de RT-2 y con el modelo sin congelar. Además `decisions` es la única con hora límite (no empieza si no termina antes de las 23:00 UTC).
3. D3 dura segundos, no toca el modelo y su estímulo ya ocurrió en F5. Va primero para no perder la ventana de 5 min de la alerta.
4. D1 apaga F22 para todas las versiones. Si se cruza con `decisions` o con el lote de D2, arruina las dos. Va entre ambas, con su reversión comprobada.
5. D2 va la última del día D: es la más larga (> 75 min), depende de dos crons (bias cada 15 min, `2,17,32,47`; agregador cada 5) y deja el modelo congelado mientras dura. Conviene terminarla **antes de las 00:00 UTC** (19:00 de Colombia): el oráculo «no se recongela el mismo día» no se ha probado cruzando la medianoche UTC. **Compruébalo en `bias-monitoring` (`window`, BR-U9-08) y dilo en la guía.**
6. D4 se cierra sola: el día D + 1 UTC empieza a las 19:00 de Colombia del día D, así que el dashboard se lee la misma noche.

**Duración total estimada: dos jornadas, ≈ 11 a 13 h de trabajo del operador.** Jornada 1 (F0 a F4): 5 a 7 h. Jornada 2 (F5 a F10): ≈ 5 h 30 min seguidos, empezando **antes de las 12:00 de Colombia (17:00 UTC)**, más la espera hasta las 21:40 para F9. Las esperas de aprobación de los ≈ 10 PR van aparte (NFR-U12-31). Son estimaciones sin medir: la guía pide anotar la duración real de cada fase.

Entre F5 y F10 no pueden pasar más de **3 días**: es la retención de Prometheus en kind (`platform/observability/values/kube-prometheus-stack-kind.yaml`, línea 5) y el oráculo de RT-5 da `no ejecutado` si la retención no cubre el Job.

### Si algo falla: a qué unidad apunta cada síntoma

La guía trae esta tabla, ampliada con lo que encuentres en las revisiones:

| Síntoma | Causa más probable | Unidad | Fuente |
|---|---|---|---|
| Pod en `ImagePullBackOff` | Digest de ejemplo: falta publicar la imagen o fusionar el PR de digests | La del pod | `CANDIDATAS.md`, línea 701; `paso-16-kind.md`, línea 15 |
| Contenedor que **sale con código 0 y sin mensaje**, `reason: Completed`, reinicios sin error | Falta una variable (por ejemplo `VECTRA_ASSERTION_AUDIENCE`) o la llave `private_key_jwt` no está montada | U0 `run_service`; mirar el `ExternalSecret` de esa unidad | `revisiones/U08-T05/ronda-1.md`, F-03 (línea 66); `CANDIDATAS.md`, líneas 616 y 624 |
| Pod en `CreateContainerConfigError` | El `ExternalSecret` no está `SecretSynced`: ruta sin sembrar en la bóveda | U1 o U2 (siembra) | `paso-16-kind.md`, línea 95 |
| Todos los `ExternalSecret` fallan de golpe, o los logins dejan de servir tras horas | El pod de la bóveda se reinició: en kind guarda todo en memoria | U1 | `install.md`, líneas 146 a 152 |
| Todo login da «Unexpected error when handling authentication request» | El kind tiene el realm viejo | U2: resincronizar | `realm-importacion.md`, líneas 10 y 28 |
| El login termina en una pantalla de perfil | `VERIFY_PROFILE` activa: realm viejo | U2 | `realm-importacion.md`, línea 11 |
| Toda la API da 401 con un token válido | El servicio valida otro emisor (`iss`) | El servicio que responde 401 | `CANDIDATAS.md`, líneas 692 y 702 |
| Ningún caso sale de `en_evaluacion`; logs con `invalid_client: Invalid token audience` | La `aud` de la aserción de servicio | U0 y el chart del servicio | `emisor-de-tokens.md`, línea 81 |
| Todos los casos salen `revision_requerida` | La vigencia de `reference-policy.json` no cubre la fecha | U5 y U4 | Enmienda §5.3 (línea 388) |
| Casos en fail-closed con `serving_config_unavailable` | No hay política activa o governance no responde | U4 | Enmienda §1.0 (líneas 43 a 47) |
| `case-service` no conecta con la base | `verify-full`: el certificado no cubre `case-db-rw.vectra-data.svc.cluster.local` | U8 y U1 | Cierre de U8, línea 74 |
| `product-metrics` con `/readyz` en 503 y dashboard vacío | Arrancó antes que el registro: reintenta a los 15 min | U11 (esperar hasta 30 min) | Cierre de U11, línea 54 |
| Los últimos casos de `decisions` quedan sin decidir | La bandeja se listó antes de que llegaran a `listo` | U12 (F-04 de U12-T02; U12-T03 debía corregirlo) | `CANDIDATAS.md`, línea 676 |
| 429 durante `decisions` | Límite del gateway: 30/s para el simulador, 20/s por usuario en `/api/console` | U2; bajar el ritmo | `identity-edge/gateway/routes.yaml`, líneas 87 a 97 |
| No hay `freeze` tras dos corridas de bias; el log del Job de bias trae 504 o `agregador_atrasado` | U3 tarda con la máquina cargada, o el agregador va atrasado | U3 (riesgo R-1) | `DECISIONES-LOOP.md` §9; `CANDIDATAS.md`, línea 254 |
| `CoreWriteAttempt` no dispara aunque el Job recibió 403 | La serie del proxy no existe: target `linkerd-proxy` caído o etiquetas distintas | U1 (riesgo R-6) | Cierre de U1, línea 28; `CANDIDATAS.md`, línea 719 |
| Los pods de `vectra-mock` no quedan `Ready` | El `Server` del 4191 bloquea las sondas `/live` y `/ready` | U1 (U01-T09) | Cierre de U8, línea 69 |
| Un pod `OOMKilled`, o el escritorio se congela | Memoria (riesgo R-4) | La del pod; parar y medir | `DECISIONES-LOOP.md` §7 |

### Cómo dejar el clúster como estaba

BR-U12-10: «RT-2 y RT-3 devuelven el entorno a su estado inicial al terminar: revierten por PR lo desplegado y vuelven al modelo de referencia con un rollback». La guía lo pide en F7 y F8 y lo comprueba en F10 con `estado-final.sh` (solo lectura):

1. **F22 encendido:** el PR de reversión fusionado y `network` sincronizada con prune; los cinco recursos de F22 otra vez presentes; un caso nuevo llega a `listo`.
2. **Modelo de referencia `activo`** y el proxy `inactivo` (`rollback_pr` y `mark_active`, del operador); ninguna versión `congelado`.
3. **`inferenceServices` de staging retirados** (PR inverso de `proxy-staging` y de `rt3-staging`).
4. Lo que **queda** y se anota: el `runId` en `values/kind/case-management.yaml`; los casos `no_disponible` de D1 y `FailClosedPersistente` (P-16 de la enmienda sigue pendiente: no hay `retry`); los 2 000 casos decididos; la segunda credencial OTP de cada usuario si se reimportó el realm.

---

## El inventario único: todo lo que solo se puede comprobar en kind

Es el corazón de la tarea. Reúne, sin duplicados y en el orden en que el operador lo comprueba: las secciones «Pendiente en U12» de los cierres, `CANDIDATAS.md`, `DECISIONES-LOOP.md`, «Lo que U12-T06 necesita» de U12-T05 y de U12-T04, la enmienda y el alcance. El codificador lo pasa a `docs/kind/inventario.yaml` (un registro por entrada: `id`, `fase`, `que`, `fuentes` con archivo y línea, `comprobacion`, `plantilla`, `demo`), y la guía, las plantillas y `cierre-demo.md` salen de ahí.

**Abreviaturas de las fuentes** (números de línea de `7ec1478`; **compruébalos en tu rama** y corrige los que hayan cambiado):
- `C-U1` = `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md`; `C-U3`, `C-U4`, `C-U6`, `C-U7`, `C-U8`, `C-U9`, `C-U10`, `C-U11` = `aidlc-docs/construction/<unidad>/evidence/cierre-demo.md` de `decision-registry`, `governance`, `model-serving`, `scoring-explainability`, `case-management`, `bias-monitoring`, `console` y `product-metrics`;
- `CAND` = `CANDIDATAS.md`; `DEC` = `DECISIONES-LOOP.md`; `ENM` = `demo-recorte-funcional.md`; `T05` = `tareas/U12-T05-imagen-y-documentacion.md`; `T04` = `tareas/U12-T04-demos-cli-y-manifiesto.md`;
- `REALM` = `identity-edge/docs/realm-importacion.md`; `EMISOR` = `identity-edge/docs/emisor-de-tokens.md`; `P16` = `identity-edge/docs/paso-16-kind.md`; `INST` = `platform/runbooks/install.md`.

**Columna «Cómo»:** `get`, `logs`, `can-i` y `pf` son `kubectl get`, `logs`, `auth can-i` y `port-forward`, siempre con `--context kind-vectra`. `PromQL:` es una consulta por `observabilidad.sh` (un `port-forward` al pod de Prometheus y `curl` a su API de lectura). Los guiones (`arranque.sh` y los demás) son los de esta tarea. Las secciones son las de la CLI.

**Columna «Demo»:** `Base` = el flujo base, que sostiene las cuatro; `D1` a `D4`; `—` = ninguna (se comprueba si hay tiempo, o queda `no ejecutado`).

### F0 — Prerrequisitos

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-01 | Memoria del host: al menos 8 GiB disponibles antes de instalar; el perfil pide 11,8 GiB de requests con todo menos U12, en una máquina de 14 GiB | `INST`:20; `platform/tests/test_kind_profile.py`:34; `DEC` §7 (líneas 78 a 86); `T05`:35 | `free -m`; `docker stats --no-stream`; `memoria.sh antes` | Base |
| K-02 | U12-T03, T04 y T05 en `main`; U02-T22 y U00-T04 en `main`; la reparación del realm retirada de `tests/doubles/keycloak_tc.py` | `T05`:358 y 359; `T04`:583; `REALM`:34; `CAND`:711 | `git log --oneline origin/main`; `grep -c repair_shared_authenticator_configs system-verification/tests/doubles/keycloak_tc.py` da 0 | Base |
| K-03 | Paquetes de U5 generados (`reference-model/.out/`: base, `proxy/run-1`, `adversarial/rt3`); la vigencia de `reference-policy.json` cubre los dos días de la corrida | `ENM`:388; `CAND`:401; `governance/docs/paso-20-kind.md`, §1 | Leer la vigencia del JSON; `ls reference-model/.out` | Base |
| K-04 | Calendario: `decisions` se lanza antes de ≈ 22:18 UTC; el día D + 1 no es día 1 del mes; F5 a F10 caben en 3 días | `ENM`:385; `T04`:170; `T05`:374; `kube-prometheus-stack-kind.yaml`:5 | `date -u`; `PromQL: prometheus_tsdb_lowest_timestamp_seconds` | D3, D4 |
| K-05 | La bóveda de kind está sembrada y no se ha reiniciado desde la siembra (guarda todo en memoria) | `INST`:146 a 152; `P16`:62 a 68 | `get pods -n vault` (edad y reinicios); `get externalsecret -A` | Base |

### F1 — Imágenes y digests

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-06 | Imágenes de U3 a U11 publicadas en `kind-registry` y digests reales en los values de kind, por PR; hoy son de ejemplo y los pods quedarían en `ImagePullBackOff` | `C-U7`:41; `C-U8`:72; `C-U9`:39; `C-U10`:70; `C-U11`:50; `CAND`:701 y 288; `T05`:360; `T04`:121 | `! grep -rn "sha256:0000" vectra-risk-gitops/values/kind`; `arranque.sh` (ningún `ImagePullBackOff`) | Base |
| K-07 | Governance, scoring, explainability y casos construidas **del mismo commit**, con sus digests en un solo PR | `C-U7`:42; `C-U8`:72; `CAND`:484 | El commit de cada imagen en la plantilla 01; un solo PR | Base |
| K-08 | Imágenes de U2 (Keycloak, `identity-jobs`, config-cli, Envoy, Valkey) publicadas, si U2 no está instalado | `P16`:15 y 33 a 57 | `arranque.sh vectra-identity vectra-edge` | Base |
| K-09 | Imagen de U12 publicada y corrida **por digest**; su memoria en el host frente a `--memory 1g` | `T05`:363 y 375; `T05`, P-9 | `docker stats --no-stream` del contenedor durante `decisions` | Base |

### F2 — Sync y arranque de cada unidad

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-10 | U2 arranca: Envoy con la raíz de solo lectura, las sondas de Valkey contestan, el Job `keycloak-config-cli` termina | `CAND`:95, 111 y 115; `P16`:87 a 100 | `arranque.sh vectra-edge vectra-identity`; `get job keycloak-config-cli -n vectra-identity` | Base |
| K-11 | `decision-registry`: Application `Synced` y `Healthy`; `/readyz` 200 | `C-U3`:71 y 72 | `get applications.argoproj.io decision-registry -n argocd`; `pf` al pod y `curl /readyz` | Base |
| K-12 | ESO materializa las llaves de cada unidad: `scoring-service-client`, `explainability-service-client`, `case-service-client`, `case-worker-client`, las dos de bias y `product-metrics-client`; existen los cuatro `pg-role-case-*` | `C-U7`:44; `C-U8`:73; `C-U9`:40; `C-U11`:51; `T05`:370 | `get externalsecret -n vectra-app` (todos `SecretSynced`) | Base |
| K-13 | Ningún contenedor sale con código 0 y sin mensaje (falta una variable o la llave) | `CAND`:616, 624 y 726; `revisiones/U08-T05/ronda-1.md`:66 | `arranque.sh vectra-app` (reinicios y `lastState.terminated.exitCode`); `logs --previous` | Base |
| K-14 | U8: el hook de migración corre antes de que los `Deployment` queden `Ready`; `sslmode=verify-full` conecta de verdad con `case-db` | `C-U8`:74; `CAND`:625 y 236 | `get jobs -n vectra-app`; `logs` de `case-service` sin errores de TLS | Base |
| K-15 | U7 arranca con la raíz de solo lectura y sin `emptyDir`; los hosts `<isvc>-predictor.vectra-serving` y `-explainer` resuelven desde `vectra-app` | `C-U7`:43 y 45; `CAND`:520 | `arranque.sh vectra-app`; el caso de K-36 en `listo` | Base |
| K-16 | `vectra-internal-ca` existe en `vectra-app` y el JWKS responde por `https` | `C-U10`:72 | `get configmap vectra-internal-ca -n vectra-app`; `logs` del BFF sin errores de JWKS | Base |
| K-17 | El eco de U2 y la `ServiceAccount` temporal `console-bff` de U4 no existen **antes** del sync de U10 | `C-U10`:71; `CAND`:402, 412 y 259; `T05`:361 | `get deploy,sa -n vectra-app` sin el eco; `get sa console-bff -n vectra-app` da `NotFound` antes del sync | Base |
| K-18 | `product-metrics` arranca **después** del registro; si no, 503 hasta 30 min y dashboard vacío | `C-U11`:54; `CAND`:598 | `get pods -l app.kubernetes.io/name=product-metrics -n vectra-app`; `logs` de la primera pasada | D4 |
| K-19 | Prometheus carga las `PrometheusRule` de U8 y U11 y raspa los `ServiceMonitor` de U8 (tres), del BFF y de U11; Grafana descubre el `ConfigMap` del dashboard en `Vectra / Producto` | `C-U8`:75; `C-U10`:73; `C-U11`:52; `T05`:372 | `observabilidad.sh reglas` y `observabilidad.sh targets` (API de lectura de Prometheus) | D1, D3, D4 |
| K-20 | Selectores y puertos de partida: Prometheus (`app.kubernetes.io/name=prometheus`, 9090), Loki (`loki`, 3100) y el registro (8080) | `CAND`:671; `T04`:141; `T05`:367 | `get pods -l app.kubernetes.io/name=prometheus -n vectra-observability`; lo mismo con `loki` y con `decision-registry-service` en `vectra-app` | Base |
| K-21 | Proxy de Linkerd en `vectra-mock`: el target `linkerd-proxy` en `up == 1` (no 403, raspado por mTLS) y los pods `Ready` con el `Server` del 4191 (las sondas `/live` y `/ready` pasan) | `C-U1`:28; `C-U8`:69; `DEC`:118; `T05`:369 | `PromQL: up{namespace="vectra-mock"}`; `get pods -n vectra-mock` | D3 |
| K-22 | Política activa y modelo de referencia `activo`: `serving-config` trae `policy_version_id` y la versión | `C-U4`:27 y 28; `ENM`:43 a 51 y 401 (P-7); `T05`:362 | Plantillas 03 y 04 de U4; `humo.py` lee `GET /api/console/models` | Base |
| K-23 | Con 256 MiB por pod bastan el predictor y el explicador del modelo de referencia | `DEC`:82 a 84; `C-U6`:34 | `get pods -n vectra-serving` (sin `OOMKilled`); `memoria.sh` | Base |
| K-24 | Paquetes proxy y RT-3 en el model-store, para D1 y D2 | `model-serving/docs/paso-11-kind.md`:42 a 58; `T05`:362 | La salida de `mc ls` de esa guía, en la plantilla 02 | D1, D2 |
| K-25 | `Watchdog` recibido, no solo disparado | `C-U1`:27; `T05`:369 | `PromQL: ALERTS{alertname="Watchdog"}`; el receptor, según `INST` | — |
| K-26 | Flujos **negados** (suite de conectividad, X01 a X10; casos bloqueados de INF-U10-04; X04) | `C-U1`:23 y 25; `C-U8`:70; `C-U9`:36; `C-U10`:68; `C-U11`:49 | **No se comprueba:** `network` y el Paso 9 están diferidos. Los flujos **permitidos** (F10, F11, F14, F15, F19 a F22, F28, F50, F60) se ven por el flujo base y por las demos. Queda `no ejecutado` | — |

### F3 — Identidad y acceso

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-27 | Si el kind tiene el realm viejo: tras resincronizar U2 quedan 26 de 26 ejecuciones enlazadas. config-cli avisa `Password policy violation … Password was NOT updated` (no reaplica contraseñas) y **añade una segunda credencial OTP** con la misma semilla | `REALM`:23 a 29; `CAND`:712 y 715; `revisiones/U02-T22/ronda-1.md`:50 y 68; `T05`:358 | `logs job/keycloak-config-cli -n vectra-identity`; el login de K-29 | Base |
| K-28 | Bloqueos por fuerza bruta: el login fallido por el error interno del realm viejo **no** cuenta (`numFailures: 0`); sí cuentan las contraseñas mal tecleadas (60 s al quinto fallo, permanente al 20) | `DEC`:122 y 128; `CAND`:715; `REALM`:29 | El login de K-29 no da «cuenta deshabilitada»; el desbloqueo es una precaución, no un paso obligado | Base |
| K-29 | Login **por rol** por el gateway real, con el emisor público y los `redirect_uri` reales: `analista-1`, `analista-2`, `ingeniero-1`, `cro-1` y `cumplimiento-1`; cada token con `acr = mfa`, `amr`, `aud` con `console-bff` y su rol | `C-U10`:65; `CAND`:42, 44 y 48; `DEC`:110; `T05`:367 y 373 | `humo.py login` (imprime los claims, nunca el token) | Base |
| K-30 | El `iss` de los tokens del navegador es el que valida el BFF **y cada destino** (F10 a F14) | `C-U10`:69; `CAND`:692 y 702; `EMISOR`:64 a 66 | `humo.py flujo`: 200 en bandeja, detalle, modelos y congelamientos; ningún 401 | Base |
| K-31 | La `aud` de la aserción de servicio la acepta el Keycloak del clúster (nunca medido en kind con el realm real) | `EMISOR`:81; `CAND`:65 y 703; `T05`:359 | `logs` de `case-worker` y `scoring-service` sin `invalid_client`; el caso de K-36 en `listo` | Base |
| K-32 | Camino a la bóveda desde la estación (no lo da K16): lectura de las 5 credenciales y las 2 llaves; el token `root` de kind no rompe el filtro de evidencias | `CAND`:640, 647, 673 y 678; `T05`:365 | `pf` al pod de la bóveda con el kubeconfig de administrador; `prepare` y `humo.py login` leen sin error | Base |
| K-33 | Credenciales de los usuarios «-2» (`analista-2` o `cro-2` en D1; `cumplimiento-2` en D2) en la bóveda, y sus semillas TOTP en el teléfono del presentador | `T05`:365 y 374; `T04`:585; `P16`:67 y 75 | Las claves `SYNTH_*` presentes en `identity/synthetic-users` (solo los nombres); login manual de `cumplimiento-2` en la consola | D1, D2 |
| K-34 | K16 de verdad: lo que cada `verify/*.sh` lee lo permite el grupo `vectra-verification-operators`; qué pasa en `vectra-staging` y `vectra-mock` (K16 no da nada) | `T05`:366; `T04`:127 a 135; `platform/rbac/verification-operator/k16.yaml` | `can-i get pods -n vectra-app --as=operador --as-group=vectra-verification-operators`, y lo mismo por cada recurso que usa un `verify` | D1, D2, D3 |
| K-35 | Consola en el navegador por el gateway real: redirección, `/callback`, recarga con `prompt=none`; **cero** `securitypolicyviolation` con la CSP real del perfil `spa` y la de `/auth/**`; la cookie `vectra-spa-route` llega a los pods | `C-U10`:65, 66 y 73; `CAND`:631 y 659; `T05`:371 | `humo.py consola` (Chromium sin interfaz, recoge los eventos de CSP); y a mano, la consola del navegador del presentador | Base |
| K-36 | `CASE_ALLOW_TEST_SCENARIOS` activo en kind (la cabecera de escenario de U12 se acepta) | `vectra-risk-gitops/values/kind/case-management.yaml`:3; `T05`:368 | La solicitud de `humo.py flujo` lleva la cabecera y se acepta | Base |
| K-37 | Límites del gateway con el volumen real: 30/s para el simulador, 20/s por usuario en `/api/console`, 600/min en `auth-login` y `auth-token` | `identity-edge/gateway/routes.yaml`:87 a 107; `T05`:368 | El `RunReport` de `decisions`: cero 429 | D4, D2 |

### F4 — Flujo base

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-38 | Humo de punta a punta: una solicitud por el gateway llega a `listo` con `registry_entry_id`; la explicación por el BFF; una decisión de `analista-1`; el append con ack | `C-U7`:40; `C-U3`:73; `ENM`:52 a 71 | `humo.py flujo` | Base |

### F5 — `prepare` y D3 (RT-5)

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-39 | `prepare` fija `runId` y `started_at`; con el PR de `runId` fusionado, `make -C case-management policy-chart` sigue en verde sobre `main` | `T04`:584; `ENM`:376 y 407 (P-13) | Sección `prepare`; `make -C case-management policy-chart` (sin clúster) | D3 |
| K-40 | El Job `rt5-demo-<runId>` termina después de `started_at`; su log trae el 403 del proxy y el valor real de `l5d-proxy-error` | `C-U8`:68; `T05`:370 | `get job rt5-demo-<runId> -n vectra-app`; `logs -l job-name=rt5-demo-<runId> -n vectra-app` | D3 |
| K-41 | La serie `inbound_http_authz_deny_total` existe con sus etiquetas **reales** (`namespace="vectra-mock"`, `route_name="core-mock-catch-all"`; la prueba de U1 declara otras) | `C-U1`:28; `C-U8`:69; `CAND`:719; `T05`:369 | `PromQL: inbound_http_authz_deny_total{namespace="vectra-mock"}` y copiar el conjunto de etiquetas | D3 |
| K-42 | `CoreWriteAttempt` llega a `firing` y cuánto dura (no tiene `for:`; la expresión mira 5 min) | `T04`:143 y 169; `T05`:370 y 374 | `PromQL: ALERTS{alertname="CoreWriteAttempt"}` cada 30 s durante 7 min | D3 |
| K-43 | `vectra_core_write_attempts_total` en 0 desde el arranque | `C-U8`:68; `DEC`:100 | `PromQL: sum(vectra_core_write_attempts_total)`; sección `rt5`; `demos/verify/rt-5.sh` | D3 |

### F6 — `decisions` (D4, día D)

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-44 | 2 000 casos: `accepted = sent`; cada uno en `listo` o en un fail-closed documentado; los últimos no quedan en `not_ready` sin decidir | `CAND`:676; plan, Pasos 6 y 10 | Sección `decisions`; el `RunReport` y `SIM-NORMAL` | D4 |
| K-45 | Las constantes de la estimación de `guard` (1 s por caso, 300 s) frente al tiempo real; el ritmo real frente a 10/s | `CAND`:634; `T05`:375 | La duración de la sección en el manifiesto | D4 |
| K-46 | `registry-aggregator` con atraso 0 y `POST /v1/monitoring/daily:query` con resultado mayor que 0 tras los 2 000 casos | `C-U3`:74 y 75 | `logs` del último Job del agregador; el log de la siguiente corrida de bias | D2 |
| K-47 | Memoria real con 2 000 decisiones frente a los 128 MiB de request de kind: `case-service`, `case-worker`, el BFF y `product-metrics` | `C-U8`:76; `C-U10`:74; `C-U11`:53; `CAND`:619 y 696; `DEC`:102, 104 y 108 | `memoria.sh despues` (`PromQL: container_memory_working_set_bytes` por pod) | D4 |

### F7 — D1 (RT-3, `journey-7-3`)

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-48 | RT3-a, c y d: 422 de U4 y `serving-config` sin cambio. RT3-b y «a y d desplegados» se informan y pueden quedar `no ejecutado` | `DEC`:124; `ENM`:79 a 81 | Sección `rt3` | D1 |
| K-49 | Con el PR de F22 fusionado y `network` sincronizada con prune, desaparecen los cinco recursos de F22; con la reversión, vuelven | `T04`:115 y 587; `ENM`:82 y 413 (P-19) | Lo dicen los casos (K16 no lee `NetworkPolicy`); con el kubeconfig de administrador, `get networkpolicy,server,authorizationpolicy -n vectra-serving` | D1 |
| K-50 | Qué `last_cause` da F22 apagado (`timeout` o `explainer_unavailable`); el caso pasa de `en_sincronizacion` a `no_disponible` en ≥ 19,3 min; cero `recommendation` | `T05`:374; `T04`:167; `ENM`:382 | Sección `rt3`; `demos/verify/journey-7-3.sh` | D1 |
| K-51 | `vectra_cases_failclosed_persistent` raspado y `FailClosedPersistente` en `firing` a los ≈ 21 min | `C-U8`:75; `T04`:143 y 167 | `PromQL: vectra_cases_failclosed_persistent` y `ALERTS{alertname="FailClosedPersistente"}` | D1 |
| K-52 | La reversión devuelve el flujo a `listo`; cuántos casos `no_disponible` quedan y si la alerta sigue activa durante D2 y D4 | `T05`:374; `ENM`:382 a 384 y 410 (P-16) | `humo.py flujo` otra vez; contar los `no_disponible` en la bandeja | D1, D2 |

### F8 — D2 (RT-2, `journey-7-4`)

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-53 | `rt2-setup`: el proxy queda `aprobado`, con `initial_disparity` no vacía, tras el PR `proxy-staging` | `ENM`:91; `T04`:118 y 119 | Sección `rt2-setup` | D2 |
| K-54 | Promoción con tráfico: 0 `version_mismatch`; el activo nunca baja de 2 réplicas; los requests de memoria durante la promoción caben | `C-U7`:38; `C-U6`:32; `DEC`:80 | `get inferenceservices,pods -n vectra-serving`; `memoria.sh durante` | D2 |
| K-55 | Las celdas de RT-2: `rt2` se niega solo por una celda **alcanzable** corta; las inalcanzables se informan | `DEC`:116; `CAND`:333 | La evidencia de `rt2` | D2 |
| K-56 | **U3 no responde 504 al cron de U9** con la máquina cargada; las métricas de bias llegan por el Pushgateway | `DEC`:94; `CAND`:254; `T05`:374 | `logs` del Job de bias de cada corrida; `PromQL: vectra_bias_last_run_ok` y `vectra_bias_last_run_timestamp` | D2 |
| K-57 | El proxy congela con una corrida real del CronJob; `rt2_latency` ≤ 1 800 s (una medición); el paquete completo (`FreezeContext`, `data_sources`, `initial_disparity`) | `C-U9`:37; `ENM`:99; `CAND`:641 | Sección `rt2` | D2 |
| K-58 | `FailClosed(model_frozen)` en ≤ 6 s tras el `freeze`; los casos nuevos quedan `modelo_congelado` | `C-U7`:39; `C-U4`:32 | Sección `rt2`; `demos/verify/journey-7-4.sh` | D2 |
| K-59 | Duración y pico de memoria de una corrida de bias, bajo los 256 MiB del límite | `C-U9`:38 | `get jobs -n vectra-app` (inicio y fin); `PromQL: max_over_time(container_memory_working_set_bytes…)` del pod del Job | D2 |
| K-60 | Los dos modos de reactivación: el de la herramienta con `cumplimiento-1`, y `--reactivation presenter` con `cumplimiento-2` en la consola: ventana emergente, `/stepup-callback`, `acr = mfa` y `ResolveFrozenDialog` | `C-U10`:67; `DEC`:132; `T04`:585; `T05`:374 | Sección `rt2` en cada modo; a mano, la consola | D2 |
| K-61 | Tras reactivar no se recongela; el barrido de U8 devuelve los `modelo_congelado`; el rollback deja el modelo de referencia `activo`; la duración real frente a «> 75 min» | `ENM`:98 y 100; `T04`:168; `T05`:374 | Sección `rt2` (campo de cierre); `estado-final.sh` | D2 |

### F9 — D4 (día D + 1 UTC)

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-62 | North Star, sostenida, tasa de consulta y `ProductMetricsStale` con datos reales, tras las 02:40 UTC | `C-U11`:47; `ENM`:117; `T05`:372 y 374 | Sección `u11`; `demos/verify/dashboard.sh` | D4 |
| K-63 | Grafana por `port-forward` con `grafana-admin` (la credencial sale del Secret `grafana-admin`, que ESO llena desde `grafana/admin`); el dashboard «Producto» carga con sus cuatro paneles. Los permisos por carpeta y rol **no** se enseñan | `DEC`:132; `C-U11`:48; `T04`:161 y 586; `T05`:373; `platform/observability/grafana/external-secrets.yaml`:31 a 36; `CAND`:82 | `pf` al pod de Grafana; a mano, el navegador | D4 |

### F10 — Informe y estado final

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-64 | El informe lista cada RT, demo e historia; salen `no ejecutado` US-106, 109, 603, 305, 604, 608, 609 y 610, RT3-b y «a y d desplegados»; ninguno sale `pasa` sin evidencia | `CAND`:641; `T05`:113; plan, Paso 18 | Sección `report`; leer `verification-report.md` | Base |
| K-65 | El clúster queda como estaba (lista de «Cómo dejar el clúster como estaba») | BR-U12-10 (`business-rules.md`, línea 130); `T04`:587 | `estado-final.sh` | D1, D2 |

### F11 — Opcionales (ninguna demo depende de ellas)

| Id | Qué se mira | Fuente | Cómo (solo lectura) | Demo |
|---|---|---|---|---|
| K-66 | (a) El login de la herramienta con Keycloak caído a mitad: ¿se cuelga o termina con error? (b) El apagado del worker con trabajo en vuelo (≈ 34 s frente a 40 s de gracia). (c) PBT-U8-07 abreviado contra el registro real | (a) `CAND`:684; (b) `C-U8`:77, `CAND`:625 y 613; (c) `C-U8`:71 | (a) y (b) necesitan una orden del operador de la lista cerrada (P-4 y P-8); la lectura es `logs` y `get pods` | — |

**Conteo (66 entradas; una entrada puede sostener varias demos):** flujo base 29 · D1 10 · D2 16 · D3 9 · D4 9 · ninguna 3. Si al pasar el inventario a `inventario.yaml` el conteo cambia, corrige esta línea y dilo en la bitácora.

**Lo que el inventario deja fuera a propósito** (está en «Pendiente» de algún cierre, pero el recorte lo difiere o es de otra guía): los ítems 3 a 8 del Paso 16 de U2 (`testssl.sh`, Valkey en 0, borrar el pod de Keycloak, el controlador en 0, la rotación de la llave, el 503 del eco) y los escenarios 4 y 7 de U4 y 1 a 3 de U6 que no sean el arranque (P-2); `LOGS-NO-PII`, `CASE-SIZE`, la carga y la resiliencia (diferidos); `break-glass`, `aud` por scope y el OIDC de Grafana (`CAND`:40, 47 y 48).

---

## Precisiones de lo que escribe el codificador

**Guiones de lectura** (`system-verification/docs/kind/*.sh`). Son del operador en la instalación y corren con su kubeconfig de administrador de kind: leen más de lo que K16 permite (`vectra-mock`, `vault`, el namespace de Argo CD, `externalsecret`, `configmap`). Los `verify/*.sh` de las demos siguen bajo K16 y no se tocan.

| Guion | Qué lee | Cubre |
|---|---|---|
| `arranque.sh <namespace>…` | Pods que no están `Running` o `Completed`; `ImagePullBackOff`; `CreateContainerConfigError`; reinicios con `lastState.terminated.exitCode == 0` (el patrón de K-13); Applications fuera de `Synced` y `Healthy`; `ExternalSecret` sin `SecretSynced` | K-06, K-08, K-10 a K-17 |
| `observabilidad.sh reglas\|targets\|consulta <expr>\|serie <nombre>` | La API de lectura de Prometheus por `port-forward` a **un pod** (nunca `svc/…`, INF-U12-03): grupos de reglas cargados, targets y su `health`, una consulta instantánea, y el conjunto de etiquetas de una serie | K-04, K-19 a K-21, K-25, K-41 a K-43, K-51, K-56 |
| `memoria.sh antes\|durante\|despues` | `free -m`, `docker stats --no-stream` de los nodos de kind y del contenedor de U12, y `container_memory_working_set_bytes` por pod desde Prometheus, frente al request de cada pod. **Sin `kubectl top`:** no es un verbo permitido | K-01, K-09, K-23, K-47, K-54, K-59 |
| `identidad.sh` | `kubectl auth can-i` con el grupo de K16 para cada recurso que usa un `verify`; el Job `keycloak-config-cli` y sus avisos; los nombres de las claves de `identity/synthetic-users` (**nunca los valores**) | K-27, K-33, K-34 |
| `estado-final.sh` | Modelo de referencia `activo`; ninguna versión `congelado`; `inferenceServices` de staging vacío; los recursos de F22 presentes; los casos `no_disponible` y las alertas que quedan | K-52, K-61, K-65 |

- Cada guion **falla con código distinto de 0** si una lectura falla. Nada de saltos en silencio con código 0 (F-02 de `revisiones/U04-T07/ronda-1.md`).
- Sin esperas fijas: sondeo con plazo (F-04 de la misma revisión).
- Sin fechas ni identificadores incrustados (F-05): todo sale de argumentos o del manifiesto.
- La salida pasa el filtro de evidencias de `src/` (ningún token, cookie ni semilla).
- Selectores, puertos y nombres de serie se toman de **un solo sitio**: los de `clients/` de U12-T02 o una tabla del propio guion, para que K-20 se corrija en un lugar.

**Humo de kind** (`docs/kind/humo.py`). Usa los clientes de `src/` (`clients/oidc.py`, `gateway.py`, `bff.py`, `credentials.py`, `guard.py`): no duplica el login. No es una sección de la CLI ni escribe en `evidence/` de la herramienta; imprime un resumen que el operador pega en la plantilla.
- `login`: los cinco usuarios de `credentials.USERS` (`credentials.py`, línea 26). Por cada uno imprime `iss`, `aud`, `acr`, `amr`, los roles y `auth_time`. Nunca el token. Respeta la espera de TOTP por usuario.
- `flujo`: una solicitud `normal` por el gateway con la cabecera de escenario; sondea hasta `listo` con plazo; lee el detalle y la explicación por el BFF con `analista-1`; registra una decisión; lee `/api/console/models` con `ingeniero-1` y `/api/console/freezes` con `cumplimiento-1`. Informa el estado HTTP de cada llamada.
- `consola`: abre la SPA real en Chromium sin interfaz, hace el login por redirección completa (sin interceptar el `redirect_uri`), recarga, y recoge los eventos `securitypolicyviolation` y la cookie de afinidad. Con el sandbox activo, como manda U12-T05.
- Pasa por `guard`: solo corre contra kind.

**Plantillas de evidencia** (`aidlc-docs/construction/system-verification/evidence/kind/`). Una por fase (`00-prerrequisitos.md` a `11-opcionales.md`, más `12-duraciones-y-memoria.md`), con el formato de `aidlc-docs/construction/governance/evidence/kind/03-arranque-politica.md`: «Estado: pendiente del operador»; guía y fase; fecha, operador y commit de `main` desplegado; y por cada entrada K de la fase: resultado esperado, comando, salida (sin secretos), y la tabla «Esperado · Obtenido · Cumple»; al final «Hallazgos», con la unidad a la que apunta cada uno.

**`cierre-demo.md`.** Formato del de U11. Secciones: «Comprobado» (lo de esta tarea, sin clúster, con su prueba); «Pendiente del operador» (la tabla del inventario: Id, qué, plantilla, estado «pendiente del operador», y la fila del cierre de origen que responde); «Diferido por la demo» (la de U12-T05, **sin tocarla**); «Quién ejecutó».

**Plan.** Paso 19: `[x] (U12-T06, acotado a la demo)`. Paso 18: sigue en `[ ]`, con «(U12-T06: guía lista, pendiente del operador; `system-verification/docs/paso-18-kind.md`)» tras el título, como hacen los planes de U4 (línea 239) y U6 (línea 124). Pasa a `[x]` en el PR de verificación.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Cualquier orden contra el clúster, y cualquier lectura de él.** Ni `kubectl`, ni el kubeconfig, ni `vectra.localtest.me`.
- **`network`** y los Jobs `x04-probe` y `x06-probe`; el parche de `prepare` en `bias-monitoring` y `decision-registry-rebuild`; **las tres Applications**. Enmienda §3 U12, filas «8b · 9 · 11: D» y «13».
- **US-609 (carga)**, `rt1`, `rt4`, `pii` (`LOGS-NO-PII`), `CASE-SIZE` y `resilience`. Enmienda §3 U12, filas «7: D», «8b · 9 · 11: D» y «10»; `mutmut` (T3) y el workflow de CI (T4).
- **Las cinco versiones del proxy:** RT-2 corre una (DD-1).
- **Secciones nuevas de la CLI**, cambios a los oráculos, a los guiones de demo o a la imagen. Son de U12-T03, T04 y T05. Un defecto suyo se corrige lo mínimo y se anota, o se reporta.
- **Corregir otras unidades:** el tope de `daily:query` de U3 (U03-T07, aparcada), ampliar K16 para la bóveda, el OIDC de Grafana, las etiquetas de `test_proxy_metrics.py`, el orden de arranque de U11.
- **Llenar la evidencia.** Las plantillas quedan en «pendiente del operador». Un codificador que escribe «obtenido» inventa.
- **Publicar la imagen** y **abrir el PR de verificación.** Son del operador.

---

## Riesgos conocidos que pueden impedir una demo

La guía los trae en su primera página, cada uno con su señal y su plan B.

| Id | Riesgo | Demo | Señal | Plan B |
|---|---|---|---|---|
| **R-1** | **U3 tarda o da 504 al cron de U9.** U03-T07 quedó aparcada y `main` no tiene tope por solicitud (`DEC` §9, línea 94). La forma que usa U9 medía 0,14 a 0,21 s; la consulta sin versión, hasta 9,6 s, y retiene la única conexión del pool `projections` (`CAND`:254). Sin respuesta no hay `freeze` (BR-U9-10) | **D2** | El log del Job de bias trae 504 o `agregador_atrasado`; `vectra_bias_last_run_ok` en 0; no hay `freeze` tras dos corridas (30 min) | (1) Correr D2 con la máquina sin otra carga: nada de `decisions`, de construir imágenes ni de navegadores de más. (2) Esperar la corrida siguiente (15 min): la sección `rt2` se retoma. (3) Tras tres corridas sin `freeze`: D2 queda `no ejecutado` con la causa, se hace el rollback y decide el usuario (P-3) |
| **R-2** | **`ImagePullBackOff`:** todos los charts llevan el digest de ejemplo | Todas | `arranque.sh` | F1 completa antes de sincronizar. Un solo PR de digests; `generate.py` regenerado. Si un pod sigue así, su digest no coincide con el publicado: compáralo con `docker inspect` |
| **R-3** | **El realm viejo** en el kind: ningún login funciona | Todas | «Unexpected error when handling authentication request»; el login termina en una pantalla de perfil | Resincronizar `keycloak` (`REALM`:28). No hace falta borrar el realm. Después, `humo.py login`. El aviso de la política de contraseñas y la segunda credencial OTP son esperados (K-27) |
| **R-4** | **Memoria:** 11,8 GiB de requests en una máquina de 14 GiB, más la estación (la imagen de U12 con Chromium, el navegador del presentador, Docker). En D2 conviven el modelo activo, el proxy y el de staging | Todas; sobre todo D2 | `free -m` con menos de ≈ 1,5 GiB disponibles; un pod `OOMKilled`; el escritorio lento | Cerrar todo lo demás (`INST`:20). No construir imágenes durante las demos. Retirar los `inferenceServices` de staging en cuanto `rt2-setup` y `rt3` terminen. Si no alcanza: parar, medir con `memoria.sh` y decidir (P-9); no se bajan requests sin un PR |
| **R-5** | **Los tres arreglos de autenticación solo se han probado contra un Keycloak local:** el emisor público que valida cada servicio (U02-T21), la `aud` de la aserción de servicio (U00-T04) y el realm (U02-T22). Nunca en kind con el realm real, PostgreSQL, Infinispan y el gateway (`REALM`:8; `EMISOR`:81) | Todas | 401 en toda la API (emisor); `invalid_client: Invalid token audience` en los logs y ningún caso sale de `en_evaluacion` (`aud`); login roto (realm) | No hay atajo: es un defecto de U0 o de U2 y va por tarea y PR. Por eso F3 y F4 se hacen en la **jornada 1**: queda un día para corregir antes de las demos |
| **R-6** | **La serie de Linkerd:** nadie ha visto en un clúster el target `linkerd-proxy` de `vectra-mock`, ni las etiquetas reales de `inbound_http_authz_deny_total`; la prueba de U1 declara etiquetas que el proxy no emite (`CAND`:719). El `Server` del 4191 puede bloquear el raspado o las sondas | **D3** | `up{namespace="vectra-mock"}` en 0 o ausente; los pods de `vectra-mock` no quedan `Ready`; `CoreWriteAttempt` no dispara aunque el Job recibió 403 | K-21 se comprueba en F2, un día antes. Si la serie existe con otras etiquetas, se anota el conjunto real y es una tarea corta de U1 o de U8. En la demo, el 403 con `l5d-proxy-error` del log del Job y el contador en 0 siguen siendo ciertos; el oráculo marcará `falla` y el informe lo dirá |
| **R-7** | **La bóveda de kind guarda todo en memoria.** Si su pod se reinicia en los dos días, lo sembrado se pierde y las claves nuevas no coinciden | Todas | Todos los `ExternalSecret` fallan a la vez; `prepare` o `humo.py` no leen credenciales | `INST`, «Vault reiniciado» (líneas 146 a 152). K-05 lo mira al empezar cada jornada |
| **R-8** | **Calendario de D4:** `decisions` lanzada tarde, `product-metrics` arrancado antes que el registro, o lectura antes de las 02:40 UTC | **D4** | `decisions` se niega (hora); dashboard vacío; `/readyz` de `product-metrics` en 503 | Empezar la jornada 2 antes de las 12:00 de Colombia. `product-metrics` se sincroniza el último (K-18). Si el dashboard está vacío, esperar la siguiente pasada (15 min) antes de darlo por fallo |

Más probables, por lo que dicen las fuentes: **R-5** (tres cambios sin probar juntos en un clúster), **R-2** y **R-4** (seguros si no se atienden), y **R-1** (medido bajo carga).

---

## Candidatas (`CANDIDATAS.md`)

Números de línea de `main` (`7ec1478`).

**Se atienden aquí** (se comprueban en kind por el inventario; la candidata se marca «comprobada en U12-T06, pendiente del operador» y se cierra en el PR de verificación):

| Línea | Candidata | Entrada |
|---|---|---|
| 701, 288 | Digests de ejemplo de U10 y de U3 (y los de U8 y U11 de sus cierres) | K-06 |
| 484 | Governance y sus consumidores, juntos | K-07 |
| 640, 673, 678, 647 | K16 y el camino a la bóveda; la lista de hosts; el token `root` y el filtro | K-32 |
| 671 | Selectores y puertos de Prometheus, Loki y el registro | K-20 |
| 402, 412, 259 | El eco de U2 y la `ServiceAccount` temporal `console-bff` | K-17 |
| 598 | `product-metrics` antes que el registro | K-18 |
| 619, 696 | Memoria real de U8 y del BFF | K-47 |
| 631, 659 | CSP del gateway real y `/callback` | K-35 |
| 692, 702; 65, 703 | El `iss` en cada destino; la `aud` de la aserción en el clúster | K-30, K-31 |
| 625, 236 | `verify-full` contra `case-db`; el apagado del worker | K-14, K-66 |
| 719 | Etiquetas reales de `inbound_http_authz_deny_total` | K-41 |
| 712, 715 | Migración del realm y fuerza bruta | K-27, K-28 |
| 42, 44, 48 | Tokens reales por rol | K-29 |
| 95, 111, 115 | Envoy con la raíz de solo lectura; sondas de Valkey | K-10 |
| 616, 624 | Salida con código 0 sin mensaje | K-13 (síntoma) |
| 684 | Login con Keycloak caído a mitad | K-66 |
| 634, 676 | Constantes de `guard`; casos sin decidir al final | K-44, K-45 |
| 254 | 504 de U3 al cron de U9 | K-56, R-1 |
| 641 | Lo que saldrá `no ejecutado` | K-64 |

**Se quedan** (no son de kind o están diferidas): 40, 47 y 82 (OIDC de Grafana); 96, 108 (U2 y U1, sin demo); 333 y 637 (resueltas por `DEC`:116); 520 y 525 (ya comprobado en la máquina); 579; 636, 638 y 642.

**Candidatas nuevas que esta tarea deja**, si no están ya: «Contradicciones» 1 a 6; que la bóveda de kind en memoria no aguanta una corrida de dos días; que D2 cruzando las 00:00 UTC no se ha probado; y lo que encuentres al comprobar los números de línea.

---

## Contradicciones entre plan, recorte, diseño y `main`

1. **El plan da por instalados U1 a U11** («con U1–U11 instalados en kind, el modelo de referencia activo»). En `main` las guías de U2, U4 y U6 no tienen evidencia y la enmienda §8 quitó el paso de kind de las otras seis. La instalación entera cae en esta corrida. La guía la encadena (P-2).
2. **«Revisado por `calidad` y `cumplimiento`».** Esos equipos no existen: `.github/CODEOWNERS`, línea 9, nombra a dos personas. Rige P-7 de U12-T04 y T05: no se toca. La guía dice quién revisa hoy.
3. **`CODEOWNERS` cubre `system-verification/evidence/`, no `aidlc-docs/…/evidence/kind/`,** donde van las plantillas (el sitio que usan U4 y U6). El PR de verificación siempre toca los dos directorios, así que la revisión de los dueños se pide igual (P-7).
4. **El plan (Paso 18, punto 3) empieza por `network`;** está diferida. Y dice que `network` «lee los Jobs ya terminados»: el único Job que queda es el de RT-5, que lee `rt5`.
5. **La ruta crítica es un orden (`demo-kind-alcance.md` §4: «U2 (cierre) → U3 → U4 → U6 → U7 → U8 → U9 → U10 → U11 → U12»), pero `components.yaml` pone U3 a U11 en la misma wave 5** y U6 en la 6, después de U7 y U8, que lo necesitan. El cierre de U11 ya lo sufre (línea 54). El orden real lo da la guía (F2).
6. **`values/kind/case-management.yaml`, línea 4, dice que `prepare` agrega el `runId` «en el PR de los digests».** El plan (Paso 18) y U12-T04 (`demos/prs/rt5-run-id`) lo ponen en un PR propio, después de `prepare`. Rige el plan: la instalación (F1) es anterior a `prepare` (F5), y así el Job corre cuando todo está sano. El comentario es de U8: candidata.
7. **NFR-U12-31 presupuesta «6 a 8 h»** con 5 corridas y carga. Con el recorte y con la instalación dentro: dos jornadas, ≈ 11 a 13 h.
8. **El plan (Paso 8) dice «sin `auth can-i` de otras identidades, que exigiría impersonación».** Vale para la herramienta bajo K16. `identidad.sh` sí usa `--as-group`, con el kubeconfig de administrador del operador, para comprobar K16 (K-34): es lectura. Si el revisor lo ve como contradicción, la alternativa es un kubeconfig de prueba del grupo, que hoy no existe.
9. **`realm-importacion.md` (líneas 12 y 29) dice que el login fallido por el error interno cuenta para la fuerza bruta.** Medido: no cuenta (`revisiones/U02-T22/ronda-1.md`, F-01; `DEC`:128). La guía sigue lo medido.
10. **El alcance §3 U12 (fila 13) todavía lista `pii`** entre las secciones; la enmienda la saca («sale `pii`»). Rige la enmienda: 8 secciones.

---

## Preguntas abiertas

**Necesitan al usuario antes de despachar: P-1 y P-2.** P-3 necesita al usuario antes de la corrida, no antes del despacho. En las demás rige la recomendación.

- **P-1 — Quién hace qué, y cómo vuelve la evidencia. (Usuario, antes de despachar.)** El plan lo deja a medias: la aceptación del Paso 18 es un PR que solo puede abrir quien corrió kind.
  - (a) U12-T06 entrega la guía y las herramientas y se fusiona con la evidencia «pendiente del operador» (como U2, U4 y U6). La corrida es del operador, fuera del loop; su evidencia entra en el PR de verificación, que revisan las personas de `CODEOWNERS`.
  - (b) Partir en U12-T06a (guía y herramientas, sin clúster) y U12-T06b (corrida asistida: el operador ejecuta y un agente, sin tocar el clúster, lee la evidencia y la juzga). Una tarea más, con archivo y rondas.
  - (c) Como (a), y además el orquestador despacha al **revisor** sobre el PR de verificación, en solo lectura: coteja esperado y obtenido, comprueba los hashes del manifiesto y asigna cada `falla` a una unidad. Sin tarea nueva ni codificador; si hay fallos, cada uno abre su tarea en la unidad dueña.
  - **Recomendación: (c).** Sigue el precedente, no añade una tarea al final de la demo y paga el «costo aceptado» de la enmienda §8 (ubicar la unidad de cada fallo) donde hace falta. Esta redacción supone (c); con (a) solo cambia la fila del revisor de «Quién hace qué».
- **P-2 — ¿La corrida incluye las guías de U2, U4 y U6, que siguen pendientes? (Usuario, antes de despachar: es su tiempo y solo él sabe cómo está su kind.)**
  - (a) Sí, **el subconjunto que sostiene las demos**: de U2, imágenes, secretos, sync y realm (`P16` §3 a §5); de U4, imágenes, sync, política y modelo de referencia (`paso-20-kind.md` §2 a §5); de U6, imágenes y paquetes (`paso-11-kind.md` §1 y §2). Sus demás escenarios (ítems 3 a 8 de U2; rollback y `freeze` de U4; los tres de U6) quedan pendientes en sus unidades. Dos jornadas.
  - (b) Antes de U12, el operador completa esas tres guías enteras, con su evidencia y sus PR. Tres corridas más; la de U12 baja a una jornada larga.
  - (c) El kind ya tiene parte instalada: la guía empieza por un diagnóstico (`arranque.sh`) y salta lo que esté sano.
  - **Recomendación: (a) con el diagnóstico de (c) al inicio.** D2 ya ejercita la promoción, el rollback y el `freeze` de punta a punta, que es lo que los escenarios de U4 y U6 medían por partes.
- **P-3 — Qué se hace si U3 da 504 al cron de U9 en D2 (R-1). (Usuario, antes de la corrida.)**
  - (a) Correr D2 como está, con la máquina sin carga, y reintentar hasta tres corridas de bias. Si no congela, D2 queda `no ejecutado` y se decide entonces.
  - (b) Reactivar U03-T07 antes de la corrida.
  - (c) Aceptar de antemano que D2 se enseñe con una grabación de un ensayo que sí pasó.
  - **Recomendación: (a).** La forma real de U9 medía 0,14 a 0,21 s; el 504 se midió con el tope que `main` no tiene. Si el primer ensayo falla, (b).
- **P-4 — Cómo escribe la guía las órdenes que cambian el clúster.** La prueba de verbos rechaza toda orden de escritura y la orden de sincronizar de Argo CD, incluso en un texto; pero una persona que no escribió el código necesita la orden exacta.
  - (a) La guía remite a los documentos dueños para todo lo que ya está escrito, y las órdenes propias van en bloques marcados «orden del operador», de una **lista cerrada** que la prueba comprueba: sincronizar una Application que exista en `vectra-risk-gitops/apps/kind/` (con la función `sync` de `INST`, línea 98, o con prune para `network`, `case-management` y `model-serving`); retirar el eco (`identity-edge/tests/e2e/echo/manifests.yaml`); publicar la imagen de U12; las órdenes de `promotion-tool` (por referencia a `paso-20-kind.md`); y, solo en F11, reiniciar `case-worker` y borrar un pod de Keycloak. Fuera de esos bloques, solo los cuatro verbos de lectura. Los guiones, nunca.
  - (b) La guía no escribe ninguna orden: solo prosa («sincroniza `case-management` con prune»). Pasa el detector sin excepción, pero no es ejecutable por un tercero.
  - **Recomendación: (a).** Si el detector de U12-T04 no admite la excepción por bloque, repórtalo antes de debilitarlo.
- **P-5 — Fechas.** La corrida pide dos días seguidos, el segundo empezando antes de las 12:00 de Colombia, sin que el día D + 1 sea día 1 de mes y con margen antes de la sustentación para corregir un fallo de R-5. Lo decide el usuario al planear; no bloquea el despacho.
- **P-6 — `make check` de todas las unidades (RL-4: «corre una vez, al cerrar la unidad»).** U12 es la última.
  - (a) El codificador corre solo `make -C system-verification check`; el `check` de las demás lo corre el revisor u orquestador una vez, en serie y con la máquina libre, y los fallos de otras unidades van a `CANDIDATAS.md`.
  - (b) Entra como criterio del codificador.
  - **Recomendación: (a).** En una máquina con carga de 12 a 15, once `check` en serie pasan de dos horas y dan falsos rojos por tiempo. CA-14 lo recoge.
- **P-7 — `CODEOWNERS` y dónde va la evidencia manual.** Rige: `CODEOWNERS` no cambia; las plantillas van en `aidlc-docs/…/evidence/kind/` y lo que escribe la herramienta en `system-verification/evidence/` («Contradicciones» 3).
- **P-8 — Las sondas opcionales (K-66).** Reiniciar `case-worker` y tumbar Keycloak a mitad de un login no sostienen ninguna demo y tocan el clúster. **Recomendación:** solo en F11, después del PR de verificación, y solo si hay tiempo; si no, quedan como candidatas.
- **P-9 — Umbral de memoria.** **Recomendación:** la guía fija como puerta «al menos 8 GiB disponibles antes de instalar» (`INST`:20) y «al menos 1,5 GiB disponibles antes de F8»; son valores de partida, a corregir con lo que mida `memoria.sh` en la jornada 1. Si no se cumple, se para: bajar requests es otra decisión del usuario, como las de `DEC` §9 y §10.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/system-verification-code-generation-plan.md` (§1, líneas 28 a 31; Pasos 18 y 19)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1, §3 U12, §5 y §8) y `demo-kind-alcance.md` (§1, §2 con la regla 4 y T1 a T6, §3 U12, §4 y §6)
- `DECISIONES-LOOP.md` (§6 a §10) y `CANDIDATAS.md` (las líneas de «Candidatas»)
- `tareas/U12-T05-imagen-y-documentacion.md` («Lo que U12-T06 necesita», líneas 353 a 376) y `tareas/U12-T04-demos-cli-y-manifiesto.md` («Lo que los guiones tocan de verdad», líneas 107 a 170, y líneas 582 a 587)
- Los precedentes: `tareas/U04-T07-kind-y-cierre.md`, `tareas/U06-T03-kind-y-cierre.md`, sus bitácoras y `revisiones/U04-T07/ronda-1.md` y `ronda-2.md`, `revisiones/U06-T03/ronda-1.md`; `governance/docs/paso-20-kind.md` y `governance/docs/kind/`; `model-serving/docs/paso-11-kind.md` y `model-serving/docs/kind/`; `identity-edge/docs/paso-16-kind.md`; `aidlc-docs/construction/governance/evidence/kind/`
- Los cierres con «Pendiente en U12»: `aidlc-docs/construction/{decision-registry,scoring-explainability,case-management,bias-monitoring,console,product-metrics}/evidence/cierre-demo.md`; y `platform-foundation/evidence/cierre-acotado.md` (líneas 18 a 33), `governance/evidence/cierre-demo.md` (líneas 19 a 37) y `model-serving/evidence/cierre-demo.md` (líneas 28 a 34)
- `identity-edge/docs/realm-importacion.md`, `identity-edge/docs/emisor-de-tokens.md` y `revisiones/U02-T22/ronda-1.md` (F-01)
- `platform/runbooks/install.md`, `vectra-risk-gitops/components.yaml`, `vectra-risk-gitops/apps/kind/` y `vectra-risk-gitops/values/kind/`
- Los `docs/imagenes.md` de `scoring-explainability`, `case-management`, `bias-monitoring` y `product-metrics`; `decision-registry/docs/imagen-kind.md`; `console/README.md`
- `platform/rbac/verification-operator/k16.yaml`, `identity-edge/gateway/routes.yaml` (líneas 85 a 107) y `platform/tests/test_kind_profile.py`
- De tu rama: `system-verification/README.md`, `demos/`, `src/vectra_verification/` y `aidlc-docs/construction/system-verification/code/`

---

## Criterios de aceptación

Hay dos grupos. Los **CA-1 a CA-14** los verifica el codificador y los repite el revisor, **sin clúster**, desde `vectra-risk/`. Los **CA-O1 a CA-O9** solo los puede marcar el **operador**, con la plantilla de evidencia; el codificador los deja escritos en la guía y sin marcar. Ninguno admite pruebas omitidas ni `xfail`.

### Sin clúster (codificador y revisor)

- [ ] **CA-1** — La guía existe y tiene las doce fases, en orden.
  ```bash
  test -s system-verification/docs/paso-18-kind.md && grep -nE "^## F(0|1|2|3|4|5|6|7|8|9|10|11) " system-verification/docs/paso-18-kind.md && uv run pytest system-verification/tests/unit/test_kind_guide.py -v -k structure
  ```
  Esperado: doce encabezados, de F0 a F11, en ese orden; la prueba pasa. Cada fase tiene prerrequisitos, pasos con comando y salida esperada, la plantilla donde se guarda, su duración estimada y su **puerta**. La primera página trae «Quién hace qué», la tabla de riesgos R-1 a R-8, la tabla de síntomas y «Cómo dejar el clúster como estaba».

- [ ] **CA-2** — Mundo cerrado sobre la guía (como `test_demos_closed_world.py` con los guiones).
  ```bash
  uv run pytest system-verification/tests/unit/test_kind_guide.py -v -k closed_world
  ```
  Esperado: pasan. La guía solo nombra cosas que existen en el repositorio:
  - cada Application, en `vectra-risk-gitops/apps/kind/`; cada namespace, en `platform/namespaces` o en `components.yaml`;
  - cada sección y opción de la CLI, en la CLI real; cada guion, en `docs/kind/` o `demos/verify/`; cada PR preparado, en `demos/prs/`;
  - cada ruta de archivo citada existe; cada «línea N» citada cae dentro del archivo;
  - cada selector `-l`, en un chart o en `clients/`; cada serie y cada alerta de una consulta, en una regla, un chart o el código que la emite;
  - cada usuario, en `identity-edge/keycloak/realm/realm.kind.yaml`; cada ruta de la consola, en `console/spa/src/views/shared/routes.ts`;
  - los tiempos de D1, D2, D3 y `decisions` son los de los guiones de U12-T04 (una sola fuente);
  - el orden de F2 respeta: política antes de `console-bff`; el eco retirado antes de `console-bff`; `product-metrics` el último; `decisions` antes de `rt2`.

  **Rojo primero:** una Application inventada, un selector que no existe, una «línea 9999» y `product-metrics` antes de `decision-registry` hacen fallar la prueba; regístralo.

- [ ] **CA-3** — Verbos de `kubectl`: la prueba recorre la guía y los guiones nuevos.
  ```bash
  uv run pytest system-verification/tests/unit/test_kubectl_verbs.py -v && ! grep -rnE "kubectl +(-[^ ]+ +)*(apply|create|delete|patch|scale|edit|exec|run|rollout|cp|top|replace|label|annotate|drain)|helm (install|upgrade)|argocd app sync|terraform apply" system-verification/docs/kind/; echo "rc=$?"
  ```
  Esperado: `rc=0`. `scan_tree` alcanza `docs/`. En `docs/kind/` no hay ninguna orden de escritura. En la guía, fuera de los bloques «orden del operador», solo `get`, `logs`, `auth can-i` y `port-forward`; dentro, solo órdenes de la lista cerrada de P-4, y cada Application que sincronizan existe. **Rojo primero:** una orden de borrar un pod fuera de un bloque marcado, y una orden que no es de la lista dentro de uno, fallan; regístralo. Las pruebas y los fixtures de U12-T01 no se debilitan.

- [ ] **CA-4** — El inventario: cada entrada tiene su comprobación, y nada de los cierres se pierde.
  ```bash
  uv run pytest system-verification/tests/unit/test_kind_inventory.py -v
  ```
  Esperado: pasan.
  - `docs/kind/inventario.yaml` trae K-01 a K-66 (o las que resulten), sin identificadores repetidos; cada una con fase, fuentes (archivo que existe y línea dentro del archivo), comprobación (un guion de `docs/kind/`, un `verify`, una sección de la CLI o un comando de lectura), plantilla y demo (`Base`, `D1` a `D4` o ninguna).
  - **Cada fila o viñeta de «Pendiente en U12»** de los seis cierres, cada fila con destino U12 de `cierre-acotado.md`, y cada línea de `CANDIDATAS.md` de la tabla «Se atienden aquí», aparece como fuente de al menos una entrada. La prueba lee esas secciones y compara por archivo y línea.
  - Cada entrada aparece en la guía, en **una** plantilla y en la tabla de `cierre-demo.md`.
  - Ninguna entrada usa como comprobación una sección diferida (`network`, `pii`, `load`, `resilience`, `rt1`, `rt4`).

  **Rojo primero:** quitar del inventario la fuente `C-U11`:54 hace fallar la prueba; una entrada sin comprobación, también.

- [ ] **CA-5** — Guiones de lectura.
  ```bash
  uvx --from shellcheck-py shellcheck system-verification/docs/kind/*.sh && uv run pytest system-verification/tests/unit/test_kind_scripts.py -v
  ```
  Esperado: los dos en 0. Contra `tests/doubles/kubectl_double.py` y `obs_double.py`: cada guion pide solo los cuatro verbos; `port-forward` va a `pod/<nombre>`; un pod en `ImagePullBackOff`, uno con salida 0 y reinicios, y un `ExternalSecret` sin sincronizar se informan y dan código distinto de 0; un `port-forward` caído da error claro y código distinto de 0, sin reintento silencioso; ninguna espera fija; la salida pasa el filtro de evidencias; `identidad.sh` nunca imprime un valor de la bóveda. **Rojo primero:** un guion que captura el error de `kubectl` y sale con 0 hace fallar la prueba.

- [ ] **CA-6** — Humo de kind, contra dobles.
  ```bash
  uv run pytest system-verification/tests/integration/test_kind_smoke.py -v
  ```
  Esperado: pasan, con el Keycloak de Testcontainers de U12-T02 y los dobles del gateway y del BFF: `login` imprime los claims de los cinco usuarios y ningún token; un `iss` distinto del público se informa como fallo; `flujo` informa el estado de cada llamada y falla si el caso no llega a `listo` en el plazo (reloj inyectado); un 401 en un destino nombra ese destino; `consola` cuenta un `securitypolicyviolation` provocado; `guard` niega un host que no es de kind, sin ninguna solicitud. Nada queda en disco.

- [ ] **CA-7** — Plantillas de evidencia.
  ```bash
  ls aidlc-docs/construction/system-verification/evidence/kind/ && grep -L "Estado: pendiente del operador" aidlc-docs/construction/system-verification/evidence/kind/*.md; uv run pytest system-verification/tests/unit/test_kind_inventory.py -v -k templates
  ```
  Esperado: trece archivos (`00` a `12`); el `grep -L` no lista ninguno; la prueba pasa: cada plantilla tiene guía y fase, fecha, operador y commit, y por cada entrada K: esperado, comando, salida y la tabla «Esperado · Obtenido · Cumple», con «Obtenido» en «_pendiente_». Ninguna trae una salida inventada.

- [ ] **CA-8** — La guía es coherente con el README y con los guiones (una sola verdad).
  ```bash
  uv run pytest system-verification/tests/unit/test_kind_guide.py -v -k coherence && uv run pytest system-verification/tests/unit/test_demos_closed_world.py -v
  ```
  Esperado: pasan. La orden `docker run` de la guía es la del README (no una copia editada); las 8 secciones aparecen en el orden de la CLI; la guía no nombra `k6`, `network`, `pii` ni las Applications diferidas como algo que el operador ejecute; los cuatro `verify` se invocan como los definió U12-T04.

- [ ] **CA-9** — Paso 19: `check` de la unidad, con su tiempo.
  ```bash
  uptime; time make -C system-verification check; echo "rc=$?"; uptime; docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' | grep -iE "u12t06|keycloak|prometheus|postgres"; echo "restantes=$?"
  ```
  Esperado: `rc=0` y `restantes=1` (o solo los que ya estaban: lístalos antes). Es la aceptación literal del Paso 19. `check` incluye lo que dejaron U12-T04 y T05 más las pruebas nuevas; `shellcheck` y `links` alcanzan `docs/`. Anota el tiempo real y los `uptime`.

- [ ] **CA-10** — Trazabilidad en 0, con la lista «Diferido por la demo».
  ```bash
  uv run python platform/tests/test_traceability.py --unit system-verification --all; echo "rc=$?"; git diff origin/main...HEAD -- aidlc-docs/construction/system-verification/evidence/cierre-demo.md | grep -E "^[-+]\| (BR|NFR|INF|PBT)-U12"; uv run python platform/tests/test_traceability.py --all
  ```
  Esperado: `rc=0`. El segundo comando no imprime nada: la lista «Diferido por la demo» de U12-T05 no cambia. El `--all` final da, para las demás unidades, el mismo conjunto que en la base (`DECISIONES-LOOP.md` §6); U2 no tiene `cierre-demo.md`.

- [ ] **CA-11** — Cierre y plan.
  ```bash
  grep -nE "^## " aidlc-docs/construction/system-verification/evidence/cierre-demo.md; grep -nE "^- \[x\] \*\*Paso 19 " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; grep -nE "^- \[ \] \*\*Paso 18 " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; git diff origin/main...HEAD -- aidlc-docs/construction/plans/system-verification-code-generation-plan.md | grep -cE "^[-+]- \["
  ```
  Esperado: `cierre-demo.md` con «Comprobado», «Pendiente del operador», «Diferido por la demo» y «Quién ejecutó»; el Paso 19 marcado con `(U12-T06, acotado a la demo)`; el Paso 18 sin marcar, con «guía lista, pendiente del operador»; el diff del plan toca solo esas dos casillas (el último comando da 4).

- [ ] **CA-12** — Enlaces y frases prohibidas.
  ```bash
  uv run python platform/tests/test_links.py && uv run python contracts/tools/forbidden_phrases.py system-verification/docs/paso-18-kind.md
  ```
  Esperado: los dos en 0.

- [ ] **CA-13** — Lock y alcance del diff.
  ```bash
  uv lock --check && git diff --name-only origin/main...HEAD | grep -vE "^vectra-risk/(system-verification/(docs/|tests/|Makefile$)|CANDIDATAS\.md$|bitacoras/U12-T06\.md$|aidlc-docs/construction/system-verification/(code/cli\.md$|evidence/)|aidlc-docs/construction/plans/system-verification-code-generation-plan\.md$)"; echo "fuera=$?"; git diff origin/main...HEAD --stat -- vectra-risk/system-verification/src vectra-risk/system-verification/demos vectra-risk/system-verification/README.md; ls system-verification/evidence
  ```
  Esperado: `uv lock --check` en 0; `fuera=1`; `src/`, `demos/` y `README.md` sin cambios, o los mínimos que la guía exigió, explicados en la bitácora; `system-verification/evidence/` solo con `.gitkeep`.

- [ ] **CA-14** — `make check` de las demás unidades, una vez (RL-4; P-6 (a): lo corre el revisor o el orquestador, no el codificador).
  ```bash
  for u in contracts platform identity-edge decision-registry governance reference-model model-serving scoring-explainability case-management bias-monitoring console product-metrics; do uptime; make -C "$u" check; echo "$u rc=$?"; done
  ```
  Esperado: cada uno en 0, en serie y con la máquina libre. Un rojo por tiempo se repite en frío. Un rojo real de otra unidad **no** bloquea esta tarea: va a `CANDIDATAS.md` con su salida, y decide el usuario.

### Solo el operador (en kind, con la plantilla de evidencia)

Cada uno se marca en el PR de verificación. La evidencia es la plantilla de la fase: comando, salida y esperado frente a obtenido. Los comandos son de solo lectura; las opciones exactas de la CLI son las de `code/cli.md` (dependencia de U12-T04) y la orden `docker run`, la del README (U12-T05).

- [ ] **CA-O1** — Instalación sana (F0 a F2; K-01 a K-26). Plantillas `00` a `02`.
  ```bash
  free -m
  kubectl --context kind-vectra get applications.argoproj.io -n argocd
  kubectl --context kind-vectra get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
  system-verification/docs/kind/arranque.sh vectra-identity vectra-edge vectra-app vectra-serving vectra-mock vectra-observability
  system-verification/docs/kind/observabilidad.sh targets
  ```
  Esperado: al menos 8 GiB disponibles antes de instalar; todas las Applications de U2 a U11 `Synced` y `Healthy` (las cinco `OutOfSync` conocidas de U1, `cierre-acotado.md`, línea 22, se anotan); ningún pod fuera de `Running` o `Completed`; `arranque.sh` en 0; el target `linkerd-proxy` de `vectra-mock` en `up`.

- [ ] **CA-O2** — Acceso y flujo base (F3 y F4; K-27 a K-38). Plantillas `03` y `04`. **Es la puerta de las cuatro demos.**
  ```bash
  system-verification/docs/kind/identidad.sh
  uv run python system-verification/docs/kind/humo.py login
  uv run python system-verification/docs/kind/humo.py flujo
  uv run python system-verification/docs/kind/humo.py consola
  ```
  Esperado: los cinco usuarios entran, con `iss = https://vectra.localtest.me/auth/realms/vectra`, `acr = mfa` y su rol; un caso llega a `listo` con `registry_entry_id` y se decide; ninguna llamada da 401 ni 429; cero `securitypolicyviolation`.

- [ ] **CA-O3** — D3 (F5 y `rt5`; K-39 a K-43). Plantilla `05`.
  ```bash
  vectra-verification prepare
  kubectl --context kind-vectra get jobs -n vectra-app
  system-verification/docs/kind/observabilidad.sh serie inbound_http_authz_deny_total
  system-verification/docs/kind/observabilidad.sh consulta 'ALERTS{alertname="CoreWriteAttempt"}'
  vectra-verification rt5 && system-verification/demos/verify/rt-5.sh
  ```
  Esperado: el Job `rt5-demo-<runId>` terminado después de `started_at`, con el 403 y `l5d-proxy-error` en su log; la serie con `namespace="vectra-mock"` y `route_name="core-mock-catch-all"` (se copia el conjunto real de etiquetas); la alerta en `firing`, con la hora en que aparece y en que se apaga; `vectra_core_write_attempts_total` en 0; `RT-5` y `rt-5` en `pasa`.

- [ ] **CA-O4** — D4 (F6 y F9; K-44 a K-47, K-62 y K-63). Plantillas `06` y `09`.
  ```bash
  date -u; vectra-verification decisions
  system-verification/docs/kind/memoria.sh despues
  date -u; vectra-verification u11 && system-verification/demos/verify/dashboard.sh
  ```
  Esperado: `decisions` lanzada antes de ≈ 22:18 UTC; 2 000 enviados, aceptados y decididos (o el número real, con su causa); cero 429; la memoria de `case-service`, `case-worker`, el BFF y `product-metrics` bajo su límite, con la cifra frente a los 128 MiB de request; `u11` después de las 02:40 UTC del día D + 1, con North Star, sostenida y tasa de consulta; el dashboard «Producto» abierto por `port-forward` con sus cuatro paneles con datos.

- [ ] **CA-O5** — D1 (F7; K-48 a K-52). Plantilla `07`.
  ```bash
  vectra-verification rt3 && system-verification/demos/verify/journey-7-3.sh
  system-verification/docs/kind/observabilidad.sh consulta 'ALERTS{alertname="FailClosedPersistente"}'
  uv run python system-verification/docs/kind/humo.py flujo
  ```
  Esperado: RT3-a, c y d con 422; con F22 apagado, cero `recommendation` y los casos de sonda en `no_disponible` con `last_cause` `timeout` o `explainer_unavailable`, con el tiempo medido (≥ 19,3 min esperados); la alerta en `firing`; **tras la reversión**, `humo.py flujo` vuelve a dar `listo`. Se anota cuántos `no_disponible` quedan.

- [ ] **CA-O6** — D2 (F8; K-53 a K-61). Plantilla `08`.
  ```bash
  vectra-verification rt2-setup
  vectra-verification rt2
  kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=bias-monitoring-job --tail=50   # etiqueta de `bias-monitoring/chart/templates/cronjob.yaml`, línea 35
  system-verification/docs/kind/observabilidad.sh consulta 'vectra_bias_last_run_ok'
  system-verification/demos/verify/journey-7-4.sh
  ```
  Esperado: el proxy `aprobado` y luego `activo`; el `freeze` con su paquete completo y `rt2_latency` ≤ 1 800 s; ningún 504 en el log del Job de bias (si lo hay: R-1, con la hora y la carga de la máquina); casos nuevos en `modelo_congelado`; la reactivación en el modo elegido, y el otro modo ensayado al menos una vez; no se recongela; el rollback hecho. Se anota la duración total frente a «> 75 min».

- [ ] **CA-O7** — El clúster queda como estaba (F10; K-65).
  ```bash
  system-verification/docs/kind/estado-final.sh
  ```
  Esperado: código 0: modelo de referencia `activo`, ninguna versión `congelado`, sin `InferenceService` de staging, F22 encendido y un caso nuevo en `listo`. Lo que queda (los `no_disponible`, el `runId`) va anotado.

- [ ] **CA-O8** — **El PR de verificación** (aceptación literal del Paso 18).
  ```bash
  vectra-verification report
  ls system-verification/evidence/*/manifest.json system-verification/evidence/*/verification-report.md
  grep -c "no ejecutado" system-verification/evidence/*/verification-report.md
  ```
  Esperado: el PR de verificación con `evidence/<fecha>-<commit>/`, `manifest.json` y `verification-report.md`, revisado por `calidad` y `cumplimiento` (hoy, las dos personas de `CODEOWNERS`); el informe lista cada RT, X, demo e historia con su resultado y no marca `pasa` sin evidencia. Lleva además las trece plantillas llenas, `cierre-demo.md` con el resultado de cada entrada K, y el Paso 18 en `[x]`.

- [ ] **CA-O9** — Duraciones y memoria (plantilla `12`): la duración real de cada fase frente a la estimada; `free -m` al empezar y al terminar cada jornada y en el pico de D2; la memoria del contenedor de U12 frente a `--memory 1g`; las constantes de `guard` frente a lo medido. Con eso se corrigen el README, la guía y, si hace falta, `BUDGET_GIB`.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/unit/test_kind_guide.py` (CA-1, CA-2 y CA-8), `test_kind_inventory.py` (CA-4 y CA-7), `test_kind_scripts.py` (CA-5) y `tests/integration/test_kind_smoke.py` (CA-6); y la ampliación de `test_kubectl_verbs.py` a `docs/` (CA-3).
- **Rojo primero:** antes de cada prueba nueva, reproduce el fallo que debe atrapar y regístralo en `bitacoras/U12-T06.md`; como mínimo los nombrados en CA-2 a CA-5.
- **Lo que el revisor encontró en las guías anteriores:**
  - un guion que nunca corrió contra nada real perdía la entrada (`revisiones/U04-T07/ronda-1.md`, F-01, ROJO): cada guion se ejercita de verdad contra los dobles, con su salida completa;
  - objetivos que se saltan en silencio con código 0 (F-02);
  - una espera fija con carrera (F-04) y fechas incrustadas (F-05);
  - un identificador «trazado por la guía» que la guía solo nombraba (F-06): una entrada del inventario sin comprobación real no cuenta;
  - un guion que entendía solo una unidad de memoria (`CANDIDATAS.md`, línea 388): `memoria.sh` normaliza `Ki`, `Mi` y `Gi`.
- La prueba de mundo cerrado **no** demuestra que la guía funcione en kind: demuestra que no nombra nada inventado. Dilo así en `cierre-demo.md`.

---

## Restricciones del entorno

Las de U12-T05, más:

- **No uses el clúster kind de la máquina ni te conectes a `vectra.localtest.me`, ni siquiera para leer.** Hay un kubeconfig que funciona: no lo uses. Ninguna prueba ejecuta el `kubectl` del host. Los guiones se prueban con `tests/doubles/kubectl_double.py` por delante en el `PATH`.
- **No copies el repositorio a `/tmp`.** Temporales dentro del worktree, en una carpeta sin versionar (`platform/.tools/tmp/u12t06/`).
- **Máquina compartida y muy cargada** (al redactar U12-T05: carga de 12 a 15 y ≈ 4 GiB disponibles de 14). Anota `uptime` con cada medida. Las esperas usan el reloj inyectado, nunca `sleep` real. Una prueba que falla por tiempo se repite en frío antes de darla por rota. No corras el `check` de otras unidades (CA-14 no es tuyo).
- **Docker es compartido** con kind (`vectra-control-plane`, `vectra-worker`, `vectra-worker2`, `kind-registry`) y con otros codificadores. Contenedores con el prefijo `u12t06-`, puertos al azar, `--memory` siempre; bórralos al terminar. Nada de `docker system prune`. **No publiques ninguna imagen.**
- **Descargas:** ninguna nueva. Las imágenes de Keycloak, config-cli, PostgreSQL y Prometheus ya están.
- **No toques el árbol principal ni otros worktrees.** No uses `git stash` sin etiqueta.
- **U12-T05 debe estar en `main`** antes de crear la rama. Si otra tarea toca `uv.lock`, el orquestador fusiona `origin/main`.

---

## Notas

- **Orden sugerido:** (1) leer `cli.md`, `scenarios.md`, el README y los guiones de tu rama, y anotar las diferencias con esta tarea; (2) comprobar los números de línea del inventario y escribir `inventario.yaml`; (3) `test_kind_inventory.py`; (4) los guiones de lectura y su prueba; (5) `humo.py` y su prueba; (6) la guía, fase por fase, con `test_kind_guide.py`; (7) las plantillas; (8) `cierre-demo.md`, el plan, `Makefile` y la bitácora.
- **Si T03, T04 o T05 cambiaron algo que esta tarea supone** (nombres de secciones, opciones, tiempos, la orden `docker run`, el nombre de un `verify`), rige lo que está en `main`. Si falta algo que la guía necesita (por ejemplo, que `rt2` no se pueda retomar), **detente y repórtalo**: no lo rodees en la guía.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` dentro de `system-verification/`.
- **Enlaces:** `test_links.py` lee como enlace un corchete cerrado seguido de un paréntesis. Cuidado con los patrones de `grep` en la guía, las plantillas y la bitácora.
- **El detector de verbos lee la prosa.** El nombre del binario de Argo CD seguido de una orden solo puede aparecer en un bloque «orden del operador». En el resto, escribe «Argo CD» y «sincroniza la Application».
- **Bitácora** `bitacoras/U12-T06.md`: la salida real de cada comando; las diferencias con T03, T04 y T05; los números de línea corregidos; los pares falla-pasa; el tiempo de `make check` con sus `uptime`; los contenedores antes y después. **Ningún secreto.**
- U12 no tiene datos propios ni recursos en el clúster: esta tarea no deja nada que limpiar en kind.

### Lo que queda después de esta tarea

1. El operador sigue `system-verification/docs/paso-18-kind.md` y abre el PR de verificación.
2. El revisor lee esa evidencia (P-1 (c)) y las personas de `CODEOWNERS` lo fusionan.
3. Cada `falla` abre una tarea en su unidad. Lo diferido sigue en la lista «Diferido por la demo» de cada `cierre-demo.md`, con su destino.
