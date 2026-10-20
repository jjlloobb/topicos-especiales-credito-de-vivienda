# Módulo 6: Certified Kubernetes Application Developer (CKAD)

**Sesiones 8 y 9 · sábados 26 de septiembre y 3 de octubre de 2026 · 9:00–12:00**

Cambio de silla. En el módulo 5 el clúster era tuyo; aquí el clúster es de otro y tú
tienes que desplegar una aplicación en él, sin permisos de administrador y sin romper
a los vecinos.

Certificación de referencia: **CKAD**.

---

## Objetivos de aprendizaje

- Implementar **sidecars nativos**: `initContainers` con `restartPolicy: Always` (K8s 1.29+).
- Desplegar charts de Helm desde registros OCI: `install`, `upgrade`, `rollback`.
- Dominar las tres sondas (`startupProbe`, `livenessProbe`, `readinessProbe`) y
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

## Laboratorios

Dos laboratorios, uno por sesión. Cada uno se verificó ejecutando **todos** sus comandos en un
clúster `kind` limpio (kind v0.33, Kubernetes v1.37); las salidas que muestran son reales.

**[Laboratorio 1: construir, arrancar, observar y depurar](./laboratorio-ckad-1.md)**
(sesión 8, 130–150 min):

1. Imagen **distroless** multi-stage de `pulso` (14,6 MB frente a 448 MB), sin shell
2. La trampa de `:latest` e `imagePullPolicy: Always` con la imagen ya en el nodo
3. `kubectl debug`: contenedor efímero con `--target`, copia con `--copy-to`, depuración de nodo
4. Las tres probes con una app que se deja romper: bucle de liveness, `startupProbe`,
   readiness (`ready=false` en el EndpointSlice) y un deadlock real con `logs --previous`
5. Init containers en secuencia y Downward API
6. Sidecars nativos: el Job que nunca termina, el `SIGTERM` que cuesta 30 s y el orden de arranque
7. QoS y `OOMKilled` (137)
8. Reto estilo examen con fallas ocultas y verificador que castiga los atajos

**[Laboratorio 2: extender, configurar, proteger, desplegar y exponer](./laboratorio-ckad-2.md)**
(sesión 9, 160–180 min):

1. Clúster `kind` con **Calico** y Whisker (y por qué `kindnet` ya aplica NetworkPolicy)
2. Un **CRD** propio con validación CEL y un controlador de juguete con RBAC mínimo
3. ConfigMaps (env, volumen, `subPath`) y Secrets
4. Pod Security `restricted`, `securityContext` y `kubectl debug --profile --custom`
5. LimitRange y ResourceQuota
6. Estrategias medidas con peticiones: RollingUpdate, Recreate, `preStop`, blue/green y canary
7. NetworkPolicies: denegar todo, el puerto correcto, Y frente a O, egress y DNS, Whisker y
   una cuarentena con `GlobalNetworkPolicy`
8. Migración de **Ingress a Gateway API** con `ingress2gateway`, pesos reales y
   `RateLimitPolicy` para lo que la traducción perdió
9. Reto estilo examen

**Herramientas:** Docker, `kind`, `kubectl`, Helm, `jq`, Calico, ingress-nginx (retirado,
como sistema a migrar), NGINX Gateway Fabric, `ingress2gateway`. `trivy` es opcional.

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

## Trabajo de proyecto final: el loop de agentes

Este módulo lleva el **cuarto paso del proyecto final**: la máquina que construye el código.
En el módulo 5 llegaste a las unidades con sus tareas y te detuviste antes de codificar. Aquí
montas un loop de tres agentes con **modelos escalonados** que despacha esas tareas, las revisa
con evidencia y las deja en un pull request.

**Guía paso a paso:** [`proyecto-final-loop-de-agentes.md`](./proyecto-final-loop-de-agentes.md)
**Los tres contratos listos para copiar:** [`agentes/`](./agentes/)

| Papel | Modelo | Qué hace | Qué **no** hace |
|---|---|---|---|
| Orquestador | el más capaz (`fable`) | Despacha, arbitra, entrega | No escribe código |
| Revisor | el siguiente (`opus`) | Corre los comandos él mismo y juzga | **No edita** |
| Codificador | el siguiente (`sonnet`) | Implementa una tarea en su worktree | No fusiona |
| Humano | (ninguno) | **Fusiona** | (nada) |

El escalonamiento va al revés de la intuición a propósito: un error del codificador lo atrapa el
revisor, pero **un error del revisor se va a producción**. La capacidad va donde equivocarse es
más caro.

Las tareas de unidades independientes se despachan **en paralelo**, cada codificador en su propio
worktree de git. Y el techo del loop es la **revisión humana**: nadie fusiona sin un humano. Es
la misma regla que en el módulo 8 impide que un agente toque producción.

> El loop **no es una fase de AI-DLC**. Es una técnica de ejecución dentro de la etapa de
> generación de código. El módulo 5 explica por qué confundirlas cuesta caro.

---

## Cómo conecta con el resto del curso

- **Módulo 3:** la imagen que despliegas aquí es la que construiste allá.
- **Módulo 5:** de ahí vienen las unidades y las tareas que el loop despacha, y de ahí sale la
  regla de que el criterio de aceptación se comprueba con un comando.
- **Módulo 8:** los charts de Helm y los overlays de Kustomize son lo que Argo CD o
  Flux van a reconciliar desde Git. Y el techo de revisión humana del loop es el mismo que
  gobierna al agente dentro del clúster.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
