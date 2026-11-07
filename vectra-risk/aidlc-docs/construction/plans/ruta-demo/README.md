# Ruta demo de Vectra Risk

Objetivo: una demo completa con todas las unidades corriendo en el clúster kind local `kind-vectra`, sobre una máquina de 14,8 GiB de RAM y 8 CPU. Lo decidió el usuario el 2026-11-07; está registrado en `aidlc-docs/audit.md`.

## Decisiones del usuario

| Id | Decisión |
|---|---|
| RD0 | **Ruta demo por unidad.** De cada plan entran los pasos DEMO y DEMO-RECORTADO de las tablas `U3-U6.md`, `U7-U9.md` y `U10-U12.md`. Los DIFERIDO y las partes diferidas se marcan en el plan de la unidad cuando se prepara su primera tarea; no se borra nada. **Perfil kind-demo**: 1 réplica, sin HPA, requests mínimas y Postgres de 1 instancia, solo en kind; staging y prod no cambian. **Loop**: 2 rondas como máximo, después se para y se lleva al usuario, sin `/code-review` extra tras el VERDE |
| RD1 | **Excepción de Kyverno solo en kind.** U1 agrega un `PolicyException` para las reglas de réplicas, HPA y PDB (`require-spread-and-pdb`, `require-hpa-bounds`, `exempt-needs-two-replicas`, `require-min-replicas`, `active-inference-service-needs-two-replicas`), limitado a los namespaces de las unidades y a los recursos con `vectra.io/profile: kind-demo`. Staging y prod siguen en `Enforce`. Afecta a RESILIENCY-08/09 (extensión activa), y el cumplimiento de extensiones de U1 lo registra |
| RD2 | **`registry-db` con 2 instancias en kind** (≈ +0,27 GiB), para que el standby síncrono de U3 (AUTONOMIA-06) y `registry-db-ro` existan. Es la única base con 2 instancias en la demo |
| RD3 | **Los diferidos EXT se aprueban en bloque**: PBT stateful e inyección de fallos, perfil `nightly`, `mutmut` y Stryker, umbrales de cobertura, alertas y runbooks (menos los que la demo usa, como `CoreWriteAttempt`), carga (U12 Paso 11), sección `resilience` (U12 8b), staging y prod. Las PBT puras con perfil `ci` se mantienen. En el cumplimiento de extensiones de cada unidad quedan como «diferido (ruta demo)». Cada unidad tiene un target `make check-demo` con lo que entra |
| RD4 | **Seed de demo y RT-2 con 1 versión.** Una tarea nueva de U12, solo para kind, genera decisiones sintéticas por la API de ingesta, con volumen y sesgo conocidos, para que U9, U10 y U11 muestren datos. RT-2 se corre con una sola versión del proxy (AUTONOMIA-04, extensión activa) |
| RD5 | **Recortar U1 en kind-demo.** Solo en kind: Tempo apagado (la demo no muestra trazas), Loki y Prometheus con 1 réplica y retención corta, Argo CD sin dex ni ApplicationSet, un overlay de kserve con `kube-rbac-proxy` liviano y metrics-server para medir el uso real. El tope se mide con el uso real, sin swap, después de cada unidad. Staging y prod no cambian. La tarea de U1 para kind-demo también rehace el presupuesto de `test_kind_profile.py` (F-01 de la ronda 5 de U02-T18 y sus candidatas) |
| RD6 | **`--import-realm` solo en kind.** Keycloak importa el realm al arrancar (JSON con `${VAR}`, variables por `ExternalSecret`). Para reimportar hay un Job puntual con `kc.sh import --override true`. `keycloak.rego` lo admite solo en kind. Enmienda BR-U2-12 y FD Q10 en kind y afecta a SECURITY-12, porque los secretos sintéticos quedan en el entorno del pod. Staging y prod siguen con `keycloak-config-cli`, que sigue bloqueado y en `CANDIDATAS.md` |
| RD7 | **Seed de kind en U1.** Un script de U1, solo para kind e idempotente, genera valores válidos según el tipo: CA, pares ES256 con su JWKS, semillas TOTP en Base32 y contraseñas. Cada unidad declara sus paths en un manifiesto. Después de reiniciar el host, el operador corre un solo comando que hace el seed y la reimportación del realm. Vault sigue en modo dev |

AUTONOMIA-01 no se difiere: el usuario, como operador, aprueba cada instalación y cada escenario en kind, después de un PR aprobado.

## Orden

1. **U2**: se cierran U02-T15, T17 y T18, y luego U02-T19 (Pasos 15, 17 y 18).
2. **U1 para la demo**: RD1, RD2 y el overlay kind-demo de U1.
3. **U3 → U5 → U4 (con dobles) → U6 → U4 (validación real) → U7 → U8 → U9 → U10 → U11 → U12**, por `unit-of-work-dependency.md`.
4. **Instalación en kind por unidad**, con la aprobación del usuario.
5. **Ensayo general**: Pasos 12, 13 y 18 de U12, con el guion de `U10-U12.md`.

## Comprobaciones pendientes, antes de la unidad que las necesita

- **U3**: confirmar en el clúster que `registry-db-ro` tiene endpoints después de RD2 (B3).
- **U4, validación real**: el explicador de staging no tiene el flujo F46, que queda «Abierto» en el Infrastructure Design de U6 (B5).
- **U5, Paso 9**: no existe un usuario de MinIO que escriba en `validation-datasets` (B6).
- **U3**: Vault Transit no está configurado en kind. Solo importa si se muestran los checkpoints firmados (B4).
- **U6**: la política que rechaza imágenes sin firma no se instala en kind (B8).
- **U4 y U6**: confirmar que el Argo CD de kind vigila el remoto de GitHub para las promociones (B9).
- **U10**: el Paso 10 (prueba de concepto del step-up) es la puerta de los Pasos 11 a 15.
- **U12**: el sandbox de Chromium, porque el host restringe los user namespaces y el Paso 15 prohíbe `--no-sandbox`.
- **U11**: confirmar si el ciclo de 5 min publica el periodo `day` el mismo día. Si no, el dashboard queda vacío en la demo.
- **U8**: diferir la retención (Paso 16) rompe el `restore-drill` de U1, y eso solo importa si la demo muestra el simulacro.
- **Memoria**: se mide con `docker stats` después de cada unidad, contra 14,8 GiB, con la estimación de las tablas al lado.
