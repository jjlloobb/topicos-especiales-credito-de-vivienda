# Respuesta a la ronda 3 — U02-T08

Código en 3845024. Evidencia en `bitacoras/U02-T08.md` (sección «Ronda 4»).

- T1: Corregido en 3845024: el ConfigMap del realm se renderiza en `identity-edge/jobs/rendered/<env>/realm-configmap.yaml` (plantilla propia `realm-configmap.yaml` del chart y `render-jobs` con `--show-only`); los CronJobs y las ServiceAccount quedan en `identity-jobs.yaml`. `skip-files` de `.github/workflows/supply-chain.yml` agrega solo esos tres archivos, sin comodines y con su comentario; el comentario de `.trivyignore` también los menciona. El comando de CA-8 falla antes con KSV-0109 (3 archivos, uno por entorno) y termina en 0 después. Render, políticas y pruebas siguen con el conjunto exacto de documentos, ahora en dos archivos (`test_t1_*`).
- F-12/F-13: candidatas: ya están en `CANDIDATAS.md`; no se tocaron en esta ronda.
