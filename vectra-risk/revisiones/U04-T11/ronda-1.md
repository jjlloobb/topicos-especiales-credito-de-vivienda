VEREDICTO: NO-VERDE

# Ronda 1 — U04-T11 (punta f5e1042)

**Nota del orquestador (2026-11-16):** resumen fiel del informe del revisor. Sin ROJO: por RL-3 no bloquea. El PR #191 se fusionó en `main` (97579d7) antes de que la revisión terminara; F-01 va a `CANDIDATAS.md`.

El arreglo es correcto: con la biblioteca real de Pod Security Admission, evaluada sin clúster (Kyverno 1.19.2 con una regla `validate.podSecurity: restricted`), el Job pasa y `main` falla por `seccompProfile`, igual que el clúster. E = ejecutado; L = leído.

## Criterios

| # | Comando | Resultado |
|---|---|---|
| 1 | `pytest governance/tests/unit -k "validation_job_template or pod_security"` y `--collect-only` | pasa (E): 18 passed; rojo contra `main` por `seccompProfile` |
| 2 | `make -C governance policy-job` | pasa (E): Kyverno `pass: 16, fail: 0`, conftest 14/14; `check` lo incluye |
| 3 | sin `.tools`: pytest de `governance` y de `platform` | governance: 132 failed por `falta platform/.tools/bin/helm` (preexistente, archivos fuera del diff; la CI no corre `governance`); platform: pasa (el único fallo es de la copia sin git) |
| 4 | grep de la guía y enlaces | pasa (E) |
| 5 | `make -C governance check` | rc 2 por el fallo conocido `XMinioServerNotInitialized`; lo que no corrió, corrido aparte en verde. La cobertura no se remidió en limpio |

## Hallazgos
### F-01 · NARANJA · `governance/tests/unit/test_validation_job_template.py:96-147` · La réplica de PodSecurity `restricted` no está completa
Contra el PSA real (E): `appArmorProfile: Unconfined` por campo, `seLinuxOptions` de contenedor y `seLinuxOptions.role` de pod pasan la réplica (falsos negativos); `seLinuxOptions.type: container_t` de pod, permitido, falla (falso positivo); `runAsUser: 0` de pod solo se detecta si ningún contenedor lo sobrescribe (L). El manifiesto de hoy no usa esos campos: el Job cumple; el hueco es de la guarda. Arreglo sugerido: añadir a `policy-job` una regla `podSecurity: restricted` de Kyverno (la biblioteca real, ya en `.tools`).
### F-02 · AMARILLO · `governance/docs/paso-20-kind.md` §5.2 · Faltan matices: el paso a `validacion_fallida` depende del ack del registro de decisiones; el primer barrido llega hasta 60 s después de cada arranque del pod; el Job se llama `validation-<run_id[:13]>`
### F-03 · AMARILLO · `governance/tests/render_validation_job.py:20` · La imagen es un literal copiado, no leído de los values

Dientes de `policy-job` (E): sin `priorityClassName`, con `docker.io/`, sin `resources` y con `readOnlyRootFilesystem: false`, rc ≠ 0.

## El procedimiento «Si el Job no arranca», afirmación por afirmación (L)
- (a) Cierta: `POST /validations` en `en_validacion` da 409.
- (b) Cierta: borrar el Job no libera el modelo.
- (c) Cierta, con matices: el barrido corre cada 60 s en cada réplica, sin estado en memoria; un reinicio de `governance` no pierde nada y basta con que el servicio esté arriba después de `deadline_at`. El modelo pasa a `validacion_fallida` tras el ack del registro de decisiones.
- (d) Cierta: el reintento crea otro `run_id` y otro Job. `create` trata un 409 como éxito (colisión improbable).
- (e) Con el registro caído, la transición queda pendiente y el modelo sigue en `en_validacion`; se reintenta cada 10 s.
- No hay camino legítimo más corto que las 2 h.

## Barrido y alcance (E)
El único que escribe en la API de Kubernetes es `k8s_jobs.py` (`POST jobs`). Ningún código crea `InferenceService`. El diff no toca `platform/policies`, `platform/namespaces` ni `validation_job/`.

## Tareas candidatas
- Correr `policy-job` y el `check` de `governance` en la CI.
- Que `KubernetesJobs.create` no trate un 409 como éxito cuando el Job existente es de otra corrida.

```
VEREDICTO: NO-VERDE
NARANJA|governance/tests/unit/test_validation_job_template.py:96-147|La réplica de PodSecurity restricted no es completa (AppArmor por campo, SELinux de contenedor y role del pod pasan; type container_t falla), comparado con el PSA real
INFORME: revisiones/U04-T11/ronda-1.md
```
