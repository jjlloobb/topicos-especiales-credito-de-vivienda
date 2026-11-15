# Ronda 1 — U12-T06

VEREDICTO: NO-VERDE

Base: `origin/main...tarea/U12-T06`, punta da28d3d. No se ejecutó nada contra `kind-vectra`. Las mutaciones y los experimentos se hicieron en una copia (`git archive HEAD`) fuera del worktree; al terminar, `git status --short` del worktree sale vacío.

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | 12 fases en orden | `grep -nE "^## F(0..11) "` y `pytest test_kind_guide.py -v -k structure` | pasa: 12 encabezados, 4 passed |
| 2 | Mundo cerrado | `pytest test_kind_guide.py -v -k closed_world` | pasa: 12 passed. Es débil: ver F-02 |
| 3 | Verbos | `pytest test_kubectl_verbs.py` y el `grep` de `docs/kind/` | pasa: 134 passed, rc=0 |
| 4 | Inventario | `pytest test_kind_inventory.py` | pasa: 10 passed |
| 5 | Guiones | `shellcheck docs/kind/*.sh` y `pytest test_kind_scripts.py` | pasa: sc=0, 39 passed. Pero el guion falla en kind: ver F-01 |
| 6 | Humo contra dobles | dentro de `make check` | pasa: `test_kind_smoke.py` 20 passed, 0 skipped |
| 7 | Plantillas | `ls`, `grep -L`, `-k templates` | pasa: 13 archivos, `grep -L` vacío, 2 passed |
| 8 | Coherencia | `-k coherence` y `test_demos_closed_world.py` | pasa: 7 passed y 69 passed |
| 9 | `make -C system-verification check` | `/usr/bin/time -v make ... check` (una vez; imagen desde la caché) | pasa: rc=0, 28:04 de reloj; 1164 + 895 + 32 passed, 0 skipped; carga 3,82 al empezar y 2,25 al terminar; ningún contenedor `u12t06-` sobrante |
| 10 | Trazabilidad | los tres comandos de CA-10 | pasa: rc=0, el diff de «Diferido» no imprime nada, `--all` correcto |
| 11 | Cierre y plan | los grep de CA-11 | pasa: 4 secciones, Paso 19 `[x]`, Paso 18 `[ ]` con «guía lista», conteo 4 |
| 12 | Enlaces y frases | `test_links.py` y `forbidden_phrases.py` | pasa: 0 y 0 |
| 13 | Lock y alcance | `uv lock --check` y el grep de fuera | pasa: lock=0, `fuera=1`, sin cambios en `src/`, `demos/` ni README; `evidence/` solo con `.gitkeep` |
| 14 | `check` de las otras unidades | — | no se corrió (P-6 (a), y la máquina estaba cargada) |

Los criterios sin clúster pasan. Los hallazgos son cosas que las pruebas no ven.

## Hallazgos

### F-01 · ROJO · `system-verification/docs/kind/identidad.sh:53-59` · Espera sin plazo al `port-forward` de la bóveda; la puerta de F3 queda inalcanzable
El bucle que espera la línea `Forwarding from` da 50 vueltas **sin pausa**: no tiene `sleep` ni plazo de tiempo. En `open_prom` de `demos/verify/lib.sh` el mismo patrón espera 0,2 s por vuelta (10 s en total). Aquí las 50 vueltas duran unos 100 ms. Un `kubectl port-forward` real tarda más que eso en imprimir, así que el guion sale con 2 antes de leer la bóveda.

Comprobado ejecutando, con el doble de `tests/doubles/kind_kubectl_bin.py` y un retardo antes del `Forwarding`:
```
delay=0.0 rc=0   identidad: sin hallazgos
delay=0.1 rc=0
delay=0.2 rc=2   NO SE PUDO LEER: el port-forward a la boveda no abrio
delay=0.5 rc=2
(observabilidad.sh consulta up con delay=0.5: rc=0; su espera es la de lib.sh)
```
La guía (F3, «Puerta»: «`identidad.sh` sale 0») y CA-O2 dependen de este guion. Además incumple «Sin esperas fijas: sondeo con plazo» de las Precisiones. La prueba de CA-5 no lo ve porque el doble imprime enseguida.

### F-02 · NARANJA · `paso-18-kind.md:695` y `tests/unit/test_kind_guide.py:213-215` · Selector que no existe (`keycloakx`), y un mundo cerrado que lo deja pasar
La orden de F11 (a) es `delete pod -n vectra-identity -l app.kubernetes.io/name=keycloakx`. En `identity-edge/keycloak/rendered/kind/keycloak.yaml` la etiqueta es `app.kubernetes.io/name: keycloak`. Con grep sobre los manifiestos: `keycloakx` tiene 0 archivos con esa etiqueta, y el resto de selectores de la guía y de los guiones aparece al menos una vez. La sonda K-66 (a) no borraría nada.

La prueba no lo detecta porque comprueba `value in corpus` como subcadena, y `keycloakx` aparece en `helm.sh/chart: keycloakx-7.4.0`. Eso incumple la viñeta de CA-2 «cada selector `-l`, en un chart».

**Barrido de mutaciones** (en la copia; `test_kind_guide.py` y `test_kind_inventory.py` después de cada una).
- **Las detecta:** `rt-5.sh 7`, `--commmit`, `product-metrics` antes del BFF, los tiempos de D1, D2 75 → 20 min, `humo --deliverx`, `-n cert-managerx`, la advertencia 1 invertida, el `--entrypoint` de `humo`, `--memory 2g` en `vv`, quitar `KUBECONFIG`.
- **No las detecta (38 passed):**
  - el código 3 cambiado a 4 en «Cómo leer el código de salida»;
  - «`prepare` repetido da 3» cambiado a «da 1»;
  - `pod/vault-0` cambiado a `pod/vault-1`;
  - `--reactivation presentador`, un valor inválido;
  - «antes de ≈ 22:18 UTC» cambiado a «23:58», en todas sus apariciones;
  - «≈ 42 min» cambiado a «≈ 10 min».

  La comprobación de tiempos (`TIMES`, línea 47) solo exige que la frase aparezca una vez en algún sitio, y la de opciones no mira los valores.

### F-03 · NARANJA · `paso-18-kind.md:560` (advertencia 1 de F8) · «La evidencia queda con dos lotes» es falso
Comprobado con un Ctrl-C **durante** `_lote`: una prueba añadida a una copia de `tests/integration/test_cli.py` lanza `KeyboardInterrupt` a mitad de `simulator.run` (`stratified`) y después retoma. Resultado:
- `state-rt2.json` queda con `batch: null` y la sección `interrumpida`.
- Al retomar, el lote se envía **otra vez**: hay 2 corridas `stratified` y el sistema recibe 150 casos `lot` (la mitad de la primera más la segunda).
- El manifiesto solo trae **un** lote: `rows_sent.rt2` tiene las filas 0 a 99.

`RecordingSimulator.run` (`cli.py:279-283`) solo anota cuando `run` vuelve, y en `src/` no hay ningún manejo de `KeyboardInterrupt`. Entonces:
- **Lo que la guía afirma bien:** se reenvía entero, también con Ctrl-C.
- **Lo que afirma mal:** que «la evidencia trae dos lotes» y que el operador lo verá allí. Hay casos duplicados en el sistema que ninguna evidencia muestra.

La guía debe decir que el envío parcial **no** queda en la evidencia y pedir al operador que anote la hora del corte. En el experimento el `rt2` retomado dio `falla` (`rt2_resolucion_antes_de_las_corridas`), pero puede ser un artefacto del doble: no se afirma.

### F-04 · NARANJA · `paso-18-kind.md:42` (R-7), `:51-71` (tabla de síntomas), `:136`, `:165` y `:219` (K-05) · La guía no cubre los tres casos de reinicio medidos el 2026-11-14
1. **inotify y `linkerd-cni`.** F0 (línea 136) menciona el límite como requisito de la instalación y remite a `install.md`. Pero:
   - no pide volver a aplicarlo tras un reinicio al empezar la jornada 2 (ni en la puerta de F0 ni en los requisitos de F5);
   - la tabla de síntomas no tiene la fila «pods con malla en `Unknown` o `ContainerCreating`; `linkerd-cni` con `too many open files`»;
   - ningún `arranque.sh` de la guía lee el namespace `linkerd-cni`, que está en `apps/kind/linkerd-cni.yaml:19`. Su Application puede verse `Healthy` mientras los pods fallan (`install.md:96`).

   **No cubierto.**
2. **Bóveda que perdió la siembra.** La fila de síntomas y R-7 existen. Pero:
   - el diagnóstico de K-05 (`arranque.sh vault`) **no** marca un pod de la bóveda reiniciado: solo marca reinicios con `exitCode 0` o `OOMKilled`, y un reinicio de la máquina deja otro código;
   - el plan B de R-7 («`seed-vault.sh identity` y reinicia lo que lee esas claves») no basta. `vault_paths.py:259-270` genera contraseñas, semillas TOTP y pares de llaves **nuevos al azar**, y Keycloak conserva los viejos en PostgreSQL. Hace falta resincronizar `keycloak` (el hook `keycloak-config-cli`), y la guía no lo dice.

   Deducido leyendo, no medido. **Cubierto a medias.**
3. **Tempo y Loki con 403 contra MinIO tras resembrar.** No aparece en la guía ni en «Vault reiniciado» de `install.md:146-152`, que solo reinicia MinIO y resincroniza `minio`. **No cubierto.** La parte que falta en el runbook es de U1: va como candidata.

### F-05 · NARANJA · `docs/kind/estado-final.sh:47-51` · Una lectura fallida sale como «falta» (1), no como «no se pudo leer» (2)
Las cinco lecturas de F22 descartan el error con `2>/dev/null`. Comprobado ejecutando el guion con el doble: `connection refused` en las cinco. Salida:
```
FALLA F22: falta NetworkPolicy allow-f22-... (K-49)   x5
estado final: NO ES COMO ESTABA   rc 1
```
Una API caída se informa como «la reversión de F7 no se sincronizó (U1)». Eso contradice el contrato del propio guion (2 = no se pudo leer) y la regla de la guía «solo un `NotFound` es "no existe"». En los demás guiones las lecturas fallidas sí salen con 2.

### F-06 · AMARILLO · `paso-18-kind.md:413-417` · `humo modelos` justo después de `humo flujo`, sin esperar 30 s
Las dos órdenes usan `ingeniero-1`. Si se lanzan seguidas, la segunda reusa el código TOTP, Keycloak la rechaza (`login_rejected`) y ese rechazo cuenta para el bloqueo por fuerza bruta. La regla general de esperar 30 s está en F0 y en F3, pero el paso 3 de F4 no la repite. De la misma familia: `humo flujo` sin `--delivery` usa la ruta relativa `reference-model/.out` (`humo.py:398`), que no existe dentro de la imagen y da código 2. El inventario, F2 (K-15, K-22) y CA-O2 escriben `humo flujo` sin la opción; F4 y F7 sí la llevan.

### F-07 · AMARILLO · `paso-18-kind.md:9` y `:315` · Nota menor
La lista cerrada y la orden de `delete -f` del eco son correctas. Del resto de la guía se comprobó contra el código, solo leyendo: las opciones de la CLI; los pasos de cada `verify`; `rt3 --closing`, que no reinicia `rt3`; los códigos 0/1/2/3, que coinciden con el README y con `cli.py:41-44`; `vv` frente al README (mismos montajes, salvo las rutas y `--name`, lo que la guía declara); el Job `keycloak-config-cli`, que se conserva (`BeforeHookCreation`); `vectra-internal-ca` en `cert-manager`; la función `sync` de varios argumentos. No se halló otro paso imposible.

## Tareas candidatas (defectos reales fuera de alcance)
- U12 (`src/`): un lote de `rt2` cortado a mitad no queda en `rows_sent` ni en ninguna evidencia, así que NFR-U12-11 (detectar solicitudes repetidas) no ve el reenvío. `README.md:22` dice que con Ctrl-C se retoma «sin reenviar el lote», y es falso: contradice la guía y a `_lote`.
- U1 (`platform/runbooks/install.md`, «Vault reiniciado»): faltan reiniciar Tempo y Loki tras rotar las claves de MinIO, y resincronizar `keycloak` tras `seed-vault.sh identity`.
- U1: tras un reinicio de la máquina hay que volver a aplicar `fs.inotify.max_user_instances`; podría hacerlo un paso del runbook o una comprobación previa.

**Qué se ejecutó y qué solo se leyó.** Ejecutado: todos los criterios menos CA-14, F-01, F-03, F-05 y las mutaciones de F-02. Solo leído: F-04 (los tres casos de reinicio, contra `install.md`, `vault_paths.py` y `arranque.sh`), el selector `keycloakx` (por grep sobre los manifiestos), la entrega de Ctrl-C a Python como PID 1 sin `-it`, y F-07.

```
VEREDICTO: NO-VERDE
ROJO|system-verification/docs/kind/identidad.sh:53-59|espera sin plazo al port-forward de la bóveda; sale 2 si tarda 0,2 s o más y la puerta de F3 queda inalcanzable
NARANJA|paso-18-kind.md:695; tests/unit/test_kind_guide.py:213-215|selector keycloakx inexistente que el mundo cerrado deja pasar por subcadena; 6 mentiras de la guía sin detectar
NARANJA|paso-18-kind.md:560|«la evidencia trae dos lotes» es falso: el lote parcial no queda en la evidencia
NARANJA|paso-18-kind.md:42,51-71,136,219|reinicio de la máquina: inotify y linkerd-cni, bóveda resembrada con identidad nueva, Tempo y Loki con 403; sin cubrir o a medias
NARANJA|system-verification/docs/kind/estado-final.sh:47-51|una lectura fallida de F22 sale como «falta» (1) en vez de 2
INFORME: revisiones/U12-T06/ronda-1.md
```
