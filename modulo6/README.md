# Módulo 6 — Certified Kubernetes Application Developer (CKAD)

**Sesiones 8 y 9 · sábados 19 y 26 de septiembre de 2026 · 9:00–12:00**

Cambio de silla. En el módulo 5 el clúster era tuyo; aquí el clúster es de otro y tú
tienes que desplegar una aplicación en él, sin permisos de administrador y sin romper
a los vecinos.

Certificación de referencia: **CKAD**.

---

## Objetivos de aprendizaje

- Implementar **sidecars nativos**: `initContainers` con `restartPolicy: Always` (K8s 1.29+).
- Desplegar charts de Helm desde registros OCI: `install`, `upgrade`, `rollback`.
- Dominar las tres sondas — `startupProbe`, `livenessProbe`, `readinessProbe` — y
  cuándo cada una.
- Aplicar overlays de Kustomize con el campo unificado `patches`.
- Diagnosticar pods en ejecución con contenedores efímeros y `kubectl debug`.

---

## Dominios del examen CKAD

| Dominio | Peso |
|---|---|
| Entorno, configuración y seguridad de la aplicación | 25% |
| Diseño y construcción de aplicaciones | 20% |
| Despliegue de aplicaciones | 20% |
| Servicios y redes | 20% |
| Observabilidad y mantenimiento | 15% |

> Verifica los pesos vigentes en la página oficial del examen CKAD de la CNCF antes
> de presentarlo.

---

## Laboratorio

**Sidecars nativos, Helm sobre OCI y startup probes** — 60 minutos, 5 pasos
(requiere Kubernetes 1.29+ y Helm 3.8+):

1. Pod con sidecar nativo (`initContainer` con `restartPolicy: Always`)
2. `startupProbe` con `failureThreshold` y `periodSeconds` para una app de arranque lento
3. Crear y publicar un chart de Helm en un registro OCI (`helm push` / `helm pull`)
4. Diagnosticar con `kubectl debug` y contenedores efímeros
5. Aplicar `ResourceQuota` y `LimitRange`

**Herramientas:** Helm con soporte OCI, Kustomize, Ingress NGINX, `kubectl debug`,
contenedores efímeros.

---

## Las tres sondas, en una tabla

| Sonda | Pregunta que responde | Qué pasa si falla |
|---|---|---|
| `startupProbe` | ¿Ya terminó de arrancar? | Se reinicia el contenedor; **suspende a las otras dos mientras corre** |
| `livenessProbe` | ¿Sigue vivo? | Se reinicia el contenedor |
| `readinessProbe` | ¿Puede recibir tráfico? | Se saca del Service; **no** se reinicia |

El error clásico es usar `livenessProbe` para una app de arranque lento: el contenedor
entra en bucle de reinicios y nunca llega a arrancar. Para eso existe `startupProbe`.

---

## Cómo conecta con el resto del curso

- **Módulo 3:** la imagen que despliegas aquí es la que construiste allá.
- **Módulo 8:** los charts de Helm y los overlays de Kustomize son lo que Argo CD o
  Flux van a reconciliar desde Git.
