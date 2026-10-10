# Pregunta de aclaración — U9 NFR Requirements (lanzamiento de la reconstrucción de U3)

Viene de los hallazgos del 2026-10-10, 05:49. Ya probé dos diseños para lanzar los Jobs
`registry-aggregator-reset` y `registry-aggregator-rebuild` de U3, y los dos tienen problemas.
Antes de editar otra vez, la decisión es tuya.

- **Hooks de sync de Argo CD** (descartado): se repiten en cada sync mientras el value siga fijado, bloquean la Application y no tienen TTL.
- **K15 y `kubectl create job --from`** (el actual): los hallazgos 1, 3, 4 y 5 aplican.
  - `restrict-manual-jobs` es eludible, porque el `ownerReference` lo escribe el cliente; el reset corre con `registry_migrator`.
  - Es una excepción a AUTONOMIA-01 que no está registrada.
  - K15 no tiene dueño en U1.

El hallazgo 2 (dos Jobs a la vez) aplica a cualquier opción y se resuelve igual en todas: los dos
comandos toman un *advisory lock* de PostgreSQL (`pg_try_advisory_lock` sobre una llave fija de
la reconstrucción) y terminan con error si ya está tomado. Así, un reset no puede correr durante
un rebuild ni otro reset, y `MonitoringAggregatorStale` delata el intento fallido.

### Clarification Question 1
¿Cómo se lanzan los Jobs de la reconstrucción?

A) **Jobs normales en Git, no hooks**:
   - el chart renderiza los dos Jobs como recursos normales (no hooks) **solo** cuando el value `monitoringRebuild.runId` está fijado, con nombres que llevan el `runId` y `sync-wave` sucesivas (reset antes que rebuild);
   - el runbook es un PR que fija un `runId` nuevo y un sync manual; los crea Argo CD (K04), con el pod spec revisado en el PR: nadie puede cambiar imagen, comando ni volúmenes, y no hay excepción a AUTONOMIA-01 ni binding nuevo (se quita K15);
   - un Job ya completado **no** se vuelve a ejecutar en un sync posterior, porque el recurso existe y no cambió (a diferencia de un hook). Si el PR que quita el `runId` se olvida, no pasa nada; el siguiente `runId` reemplaza al anterior y Argo CD poda el viejo en el sync (sin TTL, para que Argo CD no lo recree);
   - el *advisory lock* impide dos reconstrucciones a la vez;
   - **a verificar en kind**: si la versión de Argo CD que se fije espera la salud de la última `sync-wave`, el sync queda en curso hasta que termine el rebuild (≤ 90 min). Es aceptable, porque ese sync no lleva otros cambios de U3, pero se mide en el Paso 18.

   (Recomendado: elimina los hallazgos 1, 3, 4 y 5 en lugar de mitigarlos)

B) **Mantener K15 y endurecerlo**:
   - `restrict-manual-jobs` pasa a validar el pod template completo contra el del CronJob (ServiceAccount, imagen por digest, comando, volúmenes y `envFrom`), leído con un `apiCall` de Kyverno;
   - la excepción a AUTONOMIA-01 se registra en NFR-U1-43, P-U1-12, `component-dependency` §9 y `application-design` §7.1, con el audit log de Kubernetes como evidencia y un paso del runbook para guardarlo;
   - U1 es dueño de K15: Role, RoleBinding, grupo de operadores, su simulación en kind y `kubectl auth can-i`;
   - `restrict-manual-jobs` entra en NFR-U1-25, con un patrón P-U1-13 y casos de `kyverno test`.

X) Other (please describe after [Answer]: tag below)

[Answer]: A
