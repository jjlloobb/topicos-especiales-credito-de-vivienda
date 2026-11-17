# U01-T17 — Arbitraje de la ronda 1 (orquestador, 2026-11-17)

Informe: `ronda-1.md`. NO-VERDE con **un ROJO** (F-01, de evidencia, no de código), un NARANJA y cuatro AMARILLO. El revisor corrió los seis criterios y pasan; no encontró ningún camino para leer un `Secret` ni para escribir con la identidad nueva.

**Decisión: ronda 2, la última (RL-2), con todos los hallazgos.** Es una tarea de seguridad y los seis son pequeños; dejar el NARANJA en `CANDIDATAS.md` dejaría sin prueba justo lo que la tarea existe para impedir.

| Hallazgo | Decisión | Qué se pide |
|---|---|---|
| F-01 ROJO: la bitácora cita `17 passed` para CA-1 y el diff final da 36 | Ronda 2 | Corre de nuevo CA-1 a CA-6 sobre el commit final de la ronda 2 y pega las salidas reales, con el sha sobre el que corrieron. Ninguna cifra copiada de un bloque anterior |
| F-02 NARANJA: el validador es una lista de prohibidos (`nodes/proxy`, `services/proxy`, `nodes/log` y un nombre mal escrito pasan) y `check` no pregunta por ellos | Ronda 2 | (a) La prueba prohíbe **cualquier** subrecurso salvo `pods/log`. (b) Cada par `(apiGroup, resource)` del `ClusterRole` existe: se comprueba contra los CRD de `platform/.charts` y una lista del núcleo; un nombre que no exista falla. (c) La tabla de `check` añade, como «no», `get nodes/proxy`, `get pods/proxy`, `get services/proxy`, `get nodes/log`, `create serviceaccounts/token`, `escalate clusterroles` y `bind clusterroles`, y la prueba de la tabla mínima los fija. Las mutaciones del revisor deben fallar |
| F-03 AMARILLO: «Kyverno y sus políticas ya activas» en la wave 1 | Ronda 2 | Corrige la frase en `components.yaml`, el documento y la bitácora: es la misma wave; di por qué no importa |
| F-04 AMARILLO: `no - <motivo>` cuenta como «sin respuesta» | Ronda 2 | `check` compara la primera palabra. Con su prueba |
| F-05 AMARILLO: sin `trap`, el temporal con el token puede quedar; `write ~/.kube/config` sobrescribe el de administrador | Ronda 2 | `trap` que borra el temporal; `write` se niega si la ruta es el kubeconfig de administrador (`~/.kube/config` o lo que diga `KUBECONFIG` al invocarlo) o si el archivo existe y no es uno que el guion escribió (di cómo lo reconoces). Con sus pruebas |
| F-06 AMARILLO: documentación | Ronda 2 | Revocar exige una sincronización manual; «Qué NO resuelve» dice que la identidad lee la spec de los pods y `pods/log` (incluido que el token de desarrollo de Vault de kind es visible en la spec de su pod, y ya está en Git) |

**Sobre el commit `wip` (`ee78a05`):** no se reescribe el historial de la rama. El orquestador lo dirá en el PR para que el humano fusione con squash si lo prefiere.

Fuera de la ronda 2: la regla de permisos sobre `KUBECONFIG=` y `--kubeconfig`, y revisar qué imprimen los logs de los pods. Siguen como candidatas.
