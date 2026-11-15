# U12-T06 — Arbitraje de la ronda 1 (orquestador, 2026-11-14)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con un ROJO (F-01). Los criterios sin clúster pasan; los hallazgos son cosas que las pruebas no ven. La ronda 2 es la última (RL-2).

El 2026-11-14 el usuario decidió preparar la demo **en esta máquina** y autorizó al orquestador un diagnóstico de lectura y la recuperación de la plataforma de kind. Lo medido ese día es la mejor prueba de la guía que hay hasta ahora, y por eso F-04 entra en la ronda 2 con esos datos.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: `identidad.sh` espera el `port-forward` de la bóveda sin plazo y sale 2 | **Entra** | La puerta de F3 no se puede pasar en un clúster real |
| F-02 NARANJA: selector `keycloakx` inexistente; el mundo cerrado compara por subcadena; seis mentiras sin detectar | **Entra** | Un operador sigue la guía al pie de la letra; la prueba es lo único que la ata al repositorio |
| F-03 NARANJA: «la evidencia trae dos lotes» es falso | **Entra** (solo la guía) | El defecto de `src/` y del README es de U12-T05: candidata |
| F-04 NARANJA: los tres casos de reinicio no están cubiertos | **Entra**, con lo medido (abajo) | Es lo que pasó de verdad al preparar la demo |
| F-05 NARANJA: `estado-final.sh` informa una lectura fallida como «falta» | **Entra** | Contradice el contrato del guion; arreglo corto |
| F-06 AMARILLO: `humo modelos` tras `humo flujo` sin esperar; `humo flujo` sin `--delivery` | **Entra** | Un rechazo cuenta para el bloqueo por fuerza bruta |
| F-07 AMARILLO | No requiere cambio | — |
| Candidatas del informe (U12 `src/` y README; U1 runbook; U1 inotify) | A `CANDIDATAS.md` | Fuera del alcance de la tarea |

## Lo medido el 2026-11-14 en `kind-vectra` (para F-04)

Tras un reinicio de la máquina:

1. **inotify.** `fs.inotify.max_user_instances` era 128. `linkerd-cni` fallaba en los dos workers con `couldn't initialize inotify: too many open files` (más de 840 reinicios). Con 1024 (y `max_user_watches` en 1048576, persistente en `/etc/sysctl.d/`) arrancó.
2. **Los pods con malla no se recuperan solos.** Sus sandbox se crearon antes de que el plugin de Linkerd estuviera en la configuración de CNI; `linkerd-network-validator` sigue fallando («Failed to validate networking configuration») aunque `linkerd-cni` ya corra. Hubo que **borrar los pods** para que se recrearan: primero los del namespace `linkerd`, luego `vectra-data`, luego `vectra-observability`. Estaban en `Unknown`.
3. **Bóveda vacía.** Los `ExternalSecret` en `False` («could not get secret data from provider»). `seed-vault.sh` y `seed-vault.sh identity` los devolvieron a sincronizados, con claves nuevas.
4. **MinIO conserva las claves viejas de sus usuarios.** El Job `minio-post-job` del chart solo crea un usuario si no existe («User already exists») y no cambia su clave; los usuarios viven en el volumen. `argocd app sync minio` terminó bien y Tempo siguió en `CrashLoopBackOff` («The request signature we calculated does not match») y Loki con 403. Se arregló con un Job de una sola vez que corre el script `add-user` del chart forzando `mc admin user add` para cada usuario (12), con `priorityClassName: vectra-normal` (Kyverno lo exige); después, reiniciar los pods de Tempo.
5. **Grafana.** El contenedor `grafana` usa 250 MiB en reposo con un límite de 256: `OOMKilled` al arrancar con la máquina cargada, y otra vez al ejecutar `grafana cli admin reset-admin-password` dentro del contenedor. La clave de `admin` del Secret daba 401 (la base conserva la vieja). Se subió el límite a 512 MiB a mano (deriva respecto a Git; candidata de U1), se restableció la clave, se corrió `seed-vault.sh grafana-token` y se sincronizó `grafana-config`.
6. **Keycloak no estaba instalado**, así que lo que el revisor dedujo sobre resincronizar `keycloak` tras `seed-vault.sh identity` sigue **sin medir**.

## Lo que se espera de la ronda 2

- **F-01.** `identidad.sh` espera el `port-forward` con sondeo y plazo (el de `demos/verify/lib.sh`, o esa misma función). Prueba con el doble y un retardo de 0,5 s: sale 0; y con un `port-forward` que nunca abre: sale 2 al vencer el plazo, sin colgarse.
- **F-02.** El selector de F11 (a) es el real. El mundo cerrado comprueba cada selector `-l` como `clave: valor` de una etiqueta, no como subcadena. Mueren las seis mutaciones que el revisor dejó vivas (códigos de salida, `prepare` repetido, `pod/vault-0`, el valor de `--reactivation`, la hora límite, «≈ 42 min»): los valores de las opciones se comprueban contra la CLI y cada cifra en el sitio donde se usa.
- **F-03.** La advertencia 1 de F8 dice lo que pasa de verdad: el lote se reenvía entero y el envío parcial **no** queda en la evidencia; el operador anota la hora del corte. No se toca `src/` ni el README.
- **F-04.** La guía cubre el reinicio de la máquina con lo medido arriba, en un solo sitio al que remitan F0, el inicio de la jornada 2 (requisitos de F5) y la tabla de síntomas: comprobar inotify; `arranque.sh` lee también `linkerd-cni`; pods con malla en `Unknown` se recrean en el orden medido; bóveda vacía y resiembra; claves de MinIO (el Job del chart no las cambia) y reinicio de Tempo; Grafana (clave de `admin`, token, `grafana-config`, y el límite de memoria). Cada orden de escritura va marcada como del operador. Lo que no está medido (Keycloak tras `seed-vault.sh identity`) se dice como no medido. `arranque.sh` marca un pod de la bóveda que se reinició después de la siembra, con cualquier código de salida, o la guía da otra lectura que lo detecte.
- **F-05.** `estado-final.sh` distingue `NotFound` (1) de una lectura fallida (2) en las cinco lecturas de F22; prueba con el doble.
- **F-06.** F4 repite la espera de 30 s entre dos `humo` del mismo usuario, y `humo flujo` lleva `--delivery` en todas sus apariciones (guía, inventario y sus copias).
- `CANDIDATAS.md`: las tres candidatas del informe, más dos de U1 medidas hoy (el Job de MinIO no cambia la clave de un usuario existente; el límite de 256 MiB de Grafana), sin mover las líneas anteriores.
- **Se vuelven a correr:** CA-1 a CA-13 (`make -C system-verification check`) y los comprobadores de fuera de `make check`.
