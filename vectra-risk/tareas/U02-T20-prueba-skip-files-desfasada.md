# U02-T20 — La prueba de `skip-files` de Trivy en `identity-edge` quedó desfasada

**Unidad:** U2 `identity-edge`
**Historias:** ninguna nueva. Restituye la guarda de la decisión T1 (KSV-0109, U02-T08) que `make -C identity-edge check` ya no puede pasar.
**Depende de:** nada. Todo lo que toca ya está en `main`.
**Se despacha** cuando haya un hueco (RL-5).
**Rama:** `tarea/U02-T20`, desde `origin/main`.

**Por qué.** El revisor de U03-T06 (`revisiones/U03-T06/ronda-1.md`, F-01) encontró que `identity-edge/tests/unit/test_identity_jobs.py::test_t1_supply_chain_skips_exactly_the_three_realm_configmaps` falla en `main`. Lo bisecó así:
- en `8d2cabd^` (`4e711e6`) pasa;
- desde `8d2cabd` hasta `origin/main` falla con `Left contains one more item: '…/keycloak/rendered/kind/config-cli-realm.yaml'`.

`8d2cabd` (U02-T19, PR #85, «skip it in Trivy (KSV-0109)») añadió a `skip-files` de `.github/workflows/supply-chain.yml` una quinta entrada, `vectra-risk/identity-edge/keycloak/rendered/kind/config-cli-realm.yaml`, con su comentario en el workflow y en `.trivyignore`, bajo la misma decisión T1. Actualizó `platform/tests/test_platform.py::test_trivy_skips_only_the_kind_secret_read_and_the_realm_configmaps` y añadió `identity-edge/tests/unit/test_config_cli.py::test_trivy_skips_only_the_new_file_and_the_decision_is_recorded`, pero no tocó la prueba de U02-T08 (`3845024`), que sigue esperando cuatro entradas.

Nadie lo vio porque ningún workflow corre `make -C <unidad> check` (`CANDIDATAS.md`, candidata de U1 del revisor de U04-T07, ronda 1). Esa candidata **no entra** en esta tarea.

Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea.

---

## Alcance

**Dentro:**

1. **Actualizar la prueba de U02-T08** en `identity-edge/tests/unit/test_identity_jobs.py`, para que vuelva a afirmar **exactamente** el conjunto vigente de `skip-files`, en orden:
   - `vectra-risk/platform/secrets/eso-rbac-secrets-read-kind.yaml` (KSV-0041, solo kind);
   - los tres `vectra-risk/identity-edge/jobs/rendered/<entorno>/realm-configmap.yaml` (KSV-0109, decisión T1, U02-T08);
   - `vectra-risk/identity-edge/keycloak/rendered/kind/config-cli-realm.yaml` (KSV-0109, decisión T1, U02-T19, PR 85).

   Conserva lo que ya afirma:
   - que no hay comodines;
   - que cada archivo omitido existe;
   - que el workflow cita `KSV-0109` y `realm-lint`;
   - que siguen `trivyignores: vectra-risk/.trivyignore` y `scanners: vuln,misconfig,secret`.

   Afirma además que la exención sigue siendo la mínima (lo que fijó `8d2cabd`):
   - `identity-edge/keycloak/rendered/kind/keycloak.yaml` **no** se omite;
   - ningún archivo de `keycloak/rendered/staging` ni de `keycloak/rendered/prod` se omite.
2. **Nombre de la prueba** según P-1.
3. **`CANDIDATAS.md`:** una entrada de este hallazgo, marcada «Resuelta (U02-T20)», que cite `revisiones/U03-T06/ronda-1.md` F-01 y `8d2cabd`.

**Fuera:**

- `.github/workflows/supply-chain.yml` y `.trivyignore`. Si crees que la lista vigente no es la mínima, **detente y repórtalo**; no la cambies (P-2).
- Las otras dos pruebas de `skip-files` (`platform/tests/test_platform.py` y `test_config_cli.py`), salvo lo que decida P-3.
- La candidata de U1 sobre los workflows que no corren `make check`, y la de `skip-dirs` (`CANDIDATAS.md`, revisor de U02-T08, ronda 5).
- Cualquier cambio al render de Keycloak o de los Jobs.

---

## Archivos de contexto

- `revisiones/U03-T06/ronda-1.md` (F-01, con la bisección) en la rama `tarea/U03-T06`, o en `main` si ya está fusionada.
- `git show 8d2cabd` (sobre todo `supply-chain.yml`, `.trivyignore`, `platform/tests/test_platform.py` y `identity-edge/tests/unit/test_config_cli.py`).
- `tareas/U02-T08-realm-drift-y-signing-key-age.md` (decisión T1) y `tareas/U02-T19-prerrequisitos-paso-16.md` (B-1, el Job de `keycloak-config-cli`).
- `identity-edge/tests/unit/test_identity_jobs.py` (`_workflow`, `test_t1_…`, `test_t1_trivyignore_mentions_the_new_skip`).

---

## Criterios de aceptación

Desde `vectra-risk/`.

- [ ] **CA-1 — La prueba pasa.**
  ```
  uv run pytest identity-edge/tests/unit/test_identity_jobs.py -k "t1_supply_chain" -v
  ```
  Termina en 0. **Rojo previo:** el mismo comando sobre `origin/main` termina en 1 con `Left contains one more item: '…/config-cli-realm.yaml'`. La salida va en la bitácora.
- [ ] **CA-2 — Rojo en los dos sentidos.** Sobre una **copia** del workflow (no el archivo real; por ejemplo, haciendo que `_workflow()` lea una ruta de una variable de entorno solo en la prueba de mutación, o con `monkeypatch` en una prueba aparte), la prueba falla:
  - **(a)** si se quita cualquier entrada de `skip-files`;
  - **(b)** si se añade una entrada, por ejemplo `vectra-risk/identity-edge/keycloak/rendered/kind/keycloak.yaml`;
  - **(c)** si se añade un comodín.

  Cada caso queda como prueba con `pytest.raises(AssertionError)` o como par falla-pasa en la bitácora, con su comando y su salida.
- [ ] **CA-3 — Sin cambios en el workflow ni en `.trivyignore`.**
  ```
  git diff --exit-code origin/main -- ../.github/workflows/supply-chain.yml .trivyignore
  ```
  Termina en 0.
- [ ] **CA-4 — El `check` de la unidad.** `make -C identity-edge check` termina en 0. Si falta el chart `keycloakx` 7.4.0 en `platform/.charts`, cópialo del árbol principal (está ignorado por git) o bájalo con `helm pull`, y anótalo. Si faltan herramientas, `platform/install-tools.sh`.
- [ ] **CA-5 — Las otras guardas siguen en verde.**
  ```
  uv run pytest platform/tests/test_platform.py identity-edge/tests/unit/test_config_cli.py -k trivy_skips -v
  ```
  Termina en 0, con exactamente 2 pruebas seleccionadas.
- [ ] **CA-6 — `CANDIDATAS.md`.** `grep -n "U02-T20" CANDIDATAS.md` devuelve la entrada del punto 3 del alcance.

Corre los `make check` **en serie** y anota la carga (`cut -d' ' -f1-3 /proc/loadavg`). Guarda los logs con el prefijo `u02t20-`: el scratchpad lo comparten varios agentes.

---

## Preguntas abiertas

**P-1 — El nombre de la prueba.** `…_skips_exactly_the_three_realm_configmaps` ya no dice la verdad: son cinco entradas y cuatro ConfigMaps del realm.
- (a) Renombrarla, por ejemplo a `test_t1_supply_chain_skips_exactly_the_realm_configmaps_and_the_kind_secret_read`, y citar en su docstring U02-T08 y U02-T19.
- (b) Conservar el nombre y corregir solo el cuerpo.

**Recomendación del orquestador: (a).** Un nombre que miente es justo lo que ocultó este defecto. Si no hay respuesta, rige (a).

**P-2 — ¿La lista vigente es la mínima?** `8d2cabd` separó el ConfigMap del Job en `config-cli-realm.yaml` justamente para que `keycloak.yaml` se siga escaneando entero. La lista vigente parece la mínima.
- (a) No tocar el workflow; la prueba fija la lista vigente.
- (b) Si al leer `8d2cabd` encuentras una forma más estrecha, detente y repórtalo.

**Recomendación: (a).** Si no hay respuesta, rige (a).

**P-3 — Tres pruebas guardan la misma lista.** `platform/tests/test_platform.py` (U1) y `test_config_cli.py` (U2) ya la fijan, la primera también en orden exacto.
- (a) Mantener las tres y que esta tarea solo alinee la de U02-T08.
- (b) Retirar la de U02-T08 y dejar que la guarde la de U1.

**Recomendación: (a).** Cambiar pruebas de otra unidad sale del alcance, y la de U2 es la que lee la unidad al correr su propio `check`. Registra la duplicación como candidata. Si no hay respuesta, rige (a).

---

## Notas

- **Bitácora:** `bitacoras/U02-T20.md`, con el acuse de lectura (hash de este archivo), el rojo de CA-1 sobre `origin/main`, los pares de CA-2 y la carga de cada `check`.
- **Lección para el loop.** Este defecto llegó a `main` porque el CI no corre los `make check` de las unidades. La candidata de U1 que lo arreglaría ya está registrada (revisor de U04-T07, ronda 1). No la anticipes aquí.
