# Ronda 1 — U02-T27

VEREDICTO: VERDE

Corrí yo los cuatro criterios y todos pasan. CA-4 tuvo un solo fallo: la prueba de latencia de k6, ajena al diff, que pasó al repetirla sola con la máquina en calma. No encontré ningún camino para entrar sin el MFA debido, y el comportamiento del flujo nuevo coincide con el del realm de `main` en todos los casos que medí. Quedan cinco hallazgos AMARILLO y ningún ROJO ni NARANJA.

Base de la revisión: HEAD `3ee6b79`, base `origin/main` `524273a`. El hash de la tarea coincide: `5017297b87e690e1013af3bba53020bd7e0c0030`. Todo corrió con `KUBECONFIG=/nonexistent` y sin `/snap/bin` en el `PATH`. Docker solo a través de Testcontainers, con un Keycloak a la vez.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Descubrimiento 200 y segundo login con sesión abierta | `uv run pytest identity-edge/tests/integration -q -p no:cacheprovider -k "discovery or sesion_abierta or loa"` (carga 5.55) | pasa: 17 passed, 12 deselected, 123 s |
| 1-rojo | Las pruebas nuevas fallan con el realm de `main` | `test_login_levels.py` sobre una copia en el scratchpad con el realm de `main` (el fixture es idéntico a `origin/main` según `cmp`) | 8 failed / 8 passed. Las 8 fallan con `Duplicate key 2`: descubrimiento 500, y 400 en el segundo login para los 5 roles, para `acr_values=mfa` y para el usuario sin rol |
| 2 | MFA por rol y TOTP repetido | integración completa con `-v -rs` (carga 4.7) | pasa: 29 passed y 0 skipped en 164 s, incluido `test_reused_totp_code_gives_no_authorization_code` |
| 2-mut | Quitar del flujo la exigencia de MFA de un rol | mutación C (borrar `cond-role-none-cro` y su configuración) en una copia | muere: 2 failed (`[cro]`, `'pwd' == 'mfa'` y «cro-1 obtuvo un codigo con solo la contrasena») |
| 3 | Realms y renders coherentes | `make -C identity-edge render-keycloak render-jobs`, luego `check-keycloak-rendered check-jobs-rendered` | rc 0 y `git status` vacío. Los flujos y las `authenticatorConfig` de los tres ConfigMap rendidos son iguales a los de su realm (comprobado con un parse). Los flujos de kind, staging y prod son idénticos |
| 4 | Unidad en verde | `make -C identity-edge check`, una sola vez (carga 5.03 al empezar, 2.62 al terminar) | rc 2: 1 failed y 2887 passed. La única que falla es `test_load_spec.py::test_the_script_runs_against_a_fake_gateway_scaled_down`, por el sobrecosto NFR-U2-11: 5.74 ms frente a un máximo de 5 ms. Repetida sola con carga 2.36: **1 passed** en 34 s |

El filtro `--collect-only` selecciona 17 de 29 pruebas. El término `sesion_abierta` no selecciona ninguna (ver F-03).

## Lo que pediste apretar
1. **Equivalencia.** La medí con pruebas mías contra el realm nuevo y contra el de `main`, en una copia del scratchpad. Con un caso por línea:
   - **Usuario con dos roles** (`cro-2` + `operacion`): un solo TOTP, `acr=mfa`, `amr=[pwd,otp]`. Igual en los dos realms. Con el viejo, el segundo login con sesión da 400; con el nuevo, 302.
   - **Rol heredado** (`cro` por grupo, `cumplimiento` por rol compuesto, `realm-admin` dentro de un rol compuesto de realm), sin factor: no hay código en ningún caso, igual en los dos realms.
   - **Usuario sin ninguno de los seis roles:**
     - con el realm viejo entraba de verdad con `acr=pwd`: la prueba del codificador falló ahí solo en el segundo login;
     - pidiendo step-up (`acr_values=mfa`, con o sin `prompt=login` y `max_age=0`) recibe un código con `acr=pwd`, igual que antes.
   - **Re-login de un usuario con MFA** (`prompt=login`, `max_age=0`): pide contraseña y luego TOTP, y queda en `acr=mfa`.
   - **Mutaciones mías, todas mueren:**
     - A, negar mal `cond-role-none-cro`: 3 failed en integración y 3 en las pruebas unitarias;
     - B, `check_result: executed`: 15 failed;
     - D, poner en `DISABLED` una condición de `vectra-mfa-exempt`: sin Docker solo la detecta la simetría entre realms (F-04).
2. **`analista` sin factor no entra con el realm de `main`.** Es cierto, medido: `test_loa_an_analyst_without_a_factor_does_not_enter_today` pasa contra el fixture viejo. No es un defecto de este diff; es una **decisión del usuario** (F-05).
3. **Rojo primero, mutaciones y filtro:** cubierto en la tabla de criterios.
4. **Pruebas existentes.** No se relajó nada sin sustituto, salvo dos cosas:
   - Desapareció la aserción de que `conditional-user-configured` existe para los roles opcionales. Esa estructura nunca filtró nada; ahora se exige la lista exacta de roles excluidos y que no haya `conditional-user-configured` en `vectra-mfa`.
   - `load_role` ya no «comprueba» contra el realm. Esa comprobación era falsa; ya está en candidatas.

   El orden de `vectra-browser forms` ahora se exige exacto, que es más estricto que antes.
5. **CA-3:** staging y prod tampoco tienen `config-cli-realm.yaml` en `main`, así que no falta nada. No queda ninguna referencia a los alias viejos fuera de los fixtures, la bitácora y la historia de la documentación.
6. **Migración y `realm_drift`.**
   - La prueba de migración existe y pasa: descubrimiento 500, luego 200, sin configuraciones viejas y con 6 flujos `vectra-*`.
   - La proyección sin Docker (`test_realm_diff`) está dentro de CA-4, que pasó.
   - El lector real marca 35 diferencias; ya marcaba 58 con el realm viejo contra su propio YAML. Es un defecto previo y ya está en candidatas.
7. **Órdenes y sesiones abiertas.**
   - Las órdenes son correctas: `keycloak` en wave 3 con el Job `PostSync` de config-cli, luego `identity-jobs` en wave 4, sincronización manual y `targetRevision: main`. Pero están en `docs/realm-importacion.md`, no en la bitácora (F-01).
   - **Lo medí yo:** abrí sesión con el realm viejo (`cro-2` y `operacion-2`), importé el nuevo encima y volví a entrar con la misma cookie. El resultado fue 302 con código y `acr=mfa`, **pero con `amr=[]`** (F-02).
8. **Higiene del diff.**
   - `CANDIDATAS.md` solo crece al final (+3 entradas).
   - No se tocó el gateway ni `routes.yaml`.
   - El fixture es una copia literal del realm de `main`: 37 referencias `$(env:…)` y ningún secreto literal.
   - `skip-files` sigue válido porque las rutas no cambian.
   - El fixture es YAML de realm, no un manifiesto, igual que `realm-pre-u02t22`, que ya está en `main`. No debería hacer saltar Trivy, pero no lo medí: no hay `trivy` en `.tools`.
9. **`test_prepared_prs.py::test_rt3_staging_with_rt3_a_and_rt3_d…`** falla igual en `origin/main`. Lo corrí en una copia sacada con `git archive`, con `git init` en el scratchpad y el mismo `.charts`. Por tanto no es ROJO de este diff: es candidata.

## Hallazgos
### F-01 · AMARILLO · `bitacoras/U02-T27.md` · Las órdenes para el orquestador no están en la bitácora
Las Notas de la tarea piden en la bitácora qué Applications sincronizar, el Job, el `curl`, el segundo login y qué hacer si el realm queda a medias. El contenido existe y es correcto, pero solo en `identity-edge/docs/realm-importacion.md` («Qué hace el operador»), y la bitácora no lo enlaza.

### F-02 · AMARILLO · `docs/realm-importacion.md` y docstring de `test_discovery_migration…` · «No se tocan sesiones» es inexacto
Lo medí con el Keycloak real: una sesión abierta con el realm viejo sobrevive a la migración y vuelve a entrar con `acr=mfa`, pero el token sale con `amr=[]` hasta que el usuario se autentica de nuevo. La bitácora lo marcaba como no medido y la documentación lo afirma como hecho. No abre un camino sin MFA.

### F-03 · AMARILLO · CA-1 · `sesion_abierta` no selecciona ninguna prueba
`-k sesion_abierta --collect-only` devuelve 0. Las pruebas de sesión abierta entran por el prefijo `test_loa_`. Funciona, pero el término del filtro es letra muerta.

### F-04 · AMARILLO · `tests/unit/test_realm_files.py` · No se comprueba el `requirement` de las condiciones de `vectra-mfa-exempt`
Si se pone `DISABLED` una condición en los tres realms a la vez, ninguna prueba sin Docker lo detecta (solo `test_flows_and_actions_are_equal_in_the_three_realms`, que compara los realms entre sí). La integración sí lo detectaría, por analogía con las mutaciones A y C.

### F-05 · AMARILLO · decisión del usuario · `analista`
Antes y ahora, un analista sin factor no entra, en contra de BR-U2-03 (que dice que su MFA es opcional). Con este diff, además, el realm deja de llevar la marca estructural de «opcional». El comportamiento no cambia y queda fijado en una prueba y en candidatas. Arreglarlo cambia el login: lo decide el usuario.

## Tareas candidatas (defectos reales fuera de alcance)
- `system-verification/tests/unit/test_prepared_prs.py::test_rt3_staging_with_rt3_a_and_rt3_d_at_the_same_time_helm_fails_with_repetido…` falla también en `origin/main` (con el `.charts` copiado de `u01-t13`).
- Un usuario con un rol de MFA obligatorio y sin factor recibe «Invalid username or password» en lugar de la acción requerida de configurar el TOTP. Pasa con el realm viejo y con el nuevo; ya figura en `CANDIDATAS.md`, U02-T22.
- La prueba de k6 `test_the_script_runs_against_a_fake_gateway_scaled_down` es sensible a la carga (5.74 ms frente a 5 ms).

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4ae739e1-8e17-45a7-86d4-a1f29d9f6082/scratchpad/`:
- `rev-u02t27-red.log`: las pruebas nuevas contra el realm de `main`
- `rev-u02t27-extra-new.log` y `rev-u02t27-extra-old.log`: mis pruebas de dos roles, grupo, compuesto y step-up
- `rev-u02t27-mutA.log`, `rev-u02t27-mutB.log` y `rev-u02t27-mutC.log`: las mutaciones
- `rev-u02t27-sess.log`: la sesión abierta a través de la migración
- `rev-u02t27-ca4.log` y `rev-u02t27-ca4.uptime`: CA-4

Ya borré las copias del árbol. Estos logs son lo único que dejé en el scratchpad: bórralos cuando los hayas guardado. El worktree queda limpio: `git status --short` vacío, sin `.tools` ni `.charts`, HEAD `3ee6b79`.

```
VEREDICTO: VERDE
AMARILLO|bitacoras/U02-T27.md|Las órdenes para el orquestador están en docs, no en la bitácora
AMARILLO|docs/realm-importacion.md|Las sesiones previas a la migración sobreviven con amr=[]: «no se tocan sesiones» es inexacto
AMARILLO|CA-1 -k|«sesion_abierta» no selecciona ninguna prueba
AMARILLO|tests/unit/test_realm_files.py|No se comprueba el requirement de las condiciones de vectra-mfa-exempt
AMARILLO|decisión del usuario|Un analista sin factor no entra (antes y ahora), contra BR-U2-03
INFORME: revisiones/U02-T27/ronda-1.md
```
