# Glosario de tecnología — Vectra Risk

Tecnologías que el proyecto usa de verdad: qué es cada una, para qué la usa Vectra, dónde está en el repositorio, qué versión fija y qué te pueden preguntar.
Cómo leerlo: busca por tema en el índice de arriba o por nombre en el índice alfabético del final; las rutas son relativas a la raíz del repositorio y la versión solo aparece si un archivo la fija.
Fecha: 2026-11-21. Complemento: [glosario de negocio](glosario-negocio.md).

Convenciones: «Qué es» es una definición general y breve; lo demás sale del repositorio. «P:» es una pregunta probable del evaluador y «R:» su respuesta en una frase. Tres límites valen para todo el documento: **solo kind está desplegado** (staging y producción tienen manifiestos generados, sin desplegar), **los datos son sintéticos** y **las imágenes no llevan firma ni SBOM propio**.

<!-- INDICE-TEMAS -->
## Índice por temas

- [1. Método y organización](#1-método-y-organización) (6 entradas)
- [2. Kubernetes y sus objetos](#2-kubernetes-y-sus-objetos) (22 entradas)
- [3. GitOps, Argo CD y Helm](#3-gitops-argo-cd-y-helm) (13 entradas)
- [4. Políticas de admisión](#4-políticas-de-admisión) (3 entradas)
- [5. Malla de servicios y borde](#5-malla-de-servicios-y-borde) (15 entradas)
- [6. Identidad](#6-identidad) (11 entradas)
- [7. Certificados y secretos](#7-certificados-y-secretos) (5 entradas)
- [8. Datos y almacenamiento](#8-datos-y-almacenamiento) (7 entradas)
- [9. Servir modelos](#9-servir-modelos) (6 entradas)
- [10. Observabilidad](#10-observabilidad) (12 entradas)
- [11. Aplicación: servicios en Python](#11-aplicación-servicios-en-python) (16 entradas)
- [12. Aplicación: la consola](#12-aplicación-la-consola) (11 entradas)
- [13. Cadena de suministro e integración continua](#13-cadena-de-suministro-e-integración-continua) (11 entradas)
- [14. Loop de agentes](#14-loop-de-agentes) (29 entradas)
- [Índice alfabético](#índice-alfabético)

Total: 167 entradas.
<!-- /INDICE-TEMAS -->

---

## 1. Método y organización

### AI-DLC
- **Qué es:** *AI-Driven Development Life Cycle*, un flujo de desarrollo con agentes en tres fases: *inception* (qué y por qué), *construction* (cómo, construir y probar) y *operations*.
- **En Vectra:** todo el diseño y el plan salen de este flujo; cada etapa deja documentos y una aprobación humana.
- **Dónde:** `vectra-risk/AGENTS.md` (despachador), `vectra-risk/aidlc-docs/aidlc-state.md` (estado), `vectra-risk/aidlc-docs/audit.md` (bitácora de aprobaciones).
- **P:** ¿En qué fase quedó? **R:** En *construction*, con todas las unidades cerradas en el plan de tareas; *operations* no se ejecutó.
- **Ojo:** el loop de agentes es una táctica dentro de la generación de código, no una fase de AI-DLC (`vectra-risk/loop/orquestador.md`).

### Inception
- **Qué es:** fase de AI-DLC que fija requisitos, historias de usuario y diseño de aplicación.
- **En Vectra:** produjo los requisitos, las personas e historias y la división en unidades.
- **Dónde:** `vectra-risk/aidlc-docs/inception/`.
- **P:** ¿De dónde salen los requisitos? **R:** Del PRD en `vectra-risk/entradas/prd.md`, precisados en `vectra-risk/aidlc-docs/inception/requirements/requirements.md`.

### Construction
- **Qué es:** fase de AI-DLC que, por cada unidad, hace diseño funcional, requisitos no funcionales, diseño no funcional, diseño de infraestructura y generación de código.
- **En Vectra:** una carpeta por unidad con esas etapas, y los planes de código que se parten en tareas del loop.
- **Dónde:** `vectra-risk/aidlc-docs/construction/`.
- **P:** ¿Dónde está la decisión de usar tal tecnología? **R:** En el `tech-stack-decisions.md` de la unidad, por ejemplo `vectra-risk/aidlc-docs/construction/console/nfr-requirements/tech-stack-decisions.md`.

### Unidades U0 a U12
- **Qué es:** las 13 unidades de trabajo en que se dividió el sistema.
- **En Vectra:** U0 `contracts`, U1 `platform-foundation`, U2 `identity-edge`, U3 `decision-registry`, U4 `governance`, U5 `reference-model`, U6 `model-serving`, U7 `scoring-explainability`, U8 `case-management`, U9 `bias-monitoring`, U10 `console`, U11 `product-metrics`, U12 `system-verification`.
- **Dónde:** `vectra-risk/aidlc-docs/inception/application-design/unit-of-work.md`; el código de cada una está en la carpeta de su nombre bajo `vectra-risk/` (U1 en `vectra-risk/platform/` y `vectra-risk/vectra-risk-gitops/`).
- **P:** ¿Qué unidad es la más crítica? **R:** U3, el registro de decisiones: es el único componente clasificado *Critical*.
- **Ojo:** las trece tienen código en `main`, pero no todo lo diseñado se construyó: lo diferido está en `vectra-risk/aidlc-docs/construction/plans/demo-recorte-funcional.md`.

### Monorepo
- **Qué es:** un solo repositorio para todo el código y la configuración.
- **En Vectra:** aplicación, plataforma y GitOps viven juntos; la carpeta de GitOps está dentro del mismo repositorio.
- **Dónde:** `vectra-risk/pyproject.toml` (espacio de trabajo), `vectra-risk/vectra-risk-gitops/`.
- **P:** ¿El repositorio de GitOps es aparte? **R:** No: es la carpeta `vectra-risk/vectra-risk-gitops/` del monorepo, y Argo CD lee de `main`.

### AUTONOMIA-01
- **Qué es:** regla del proyecto: los cambios a infraestructura solo entran por *pull request* aprobado.
- **En Vectra:** el agente propone, una persona aprueba y fusiona, y otra acción humana sincroniza. Nadie aplica cambios por fuera de Git.
- **Dónde:** `vectra-risk/aidlc-docs/inception/requirements/requirements.md` (§3); se hace cumplir en `.claude/settings.json`, en `vectra-risk/platform/policies/kyverno/disallow-argocd-auto-sync.yaml` y en `vectra-risk/platform/tests/forbidden_steps.py`.
- **P:** ¿Tu agente hace `kubectl apply`? **R:** No: está denegado por configuración, el servidor MCP solo lee y la cuenta del clúster no tiene verbos de escritura.
- **Ojo:** hay una excepción registrada: desde el 2026-11-14 la sesión del orquestador opera el clúster de kind con aprobación del usuario orden por orden (`vectra-risk/DECISIONES-LOOP.md`, §11).

---

## 2. Kubernetes y sus objetos

### Kubernetes
- **Qué es:** orquestador de contenedores: mantiene el estado declarado de las cargas de trabajo.
- **En Vectra:** es donde corre todo el producto, dentro del clúster del banco.
- **Dónde:** `vectra-risk/platform/`.
- **Versión:** 1.37.0, por la imagen de nodo `kindest/node:v1.37.0` fijada por digest en `vectra-risk/platform/kind/cluster.yaml`.
- **P:** ¿Por qué Kubernetes? **R:** Porque el cliente ideal ya lo opera y el producto se vende *self-hosted* en su clúster.

### kind
- **Qué es:** *Kubernetes in Docker*: un clúster cuyos nodos son contenedores.
- **En Vectra:** es el único entorno desplegado. Clúster `vectra` (contexto `kind-vectra`), con 1 plano de control y 2 nodos de trabajo en dos zonas simuladas.
- **Dónde:** `vectra-risk/platform/kind/cluster.yaml`; variante de 4 nodos de trabajo en `vectra-risk/platform/kind/cluster-ha.yaml`; instalación en `vectra-risk/platform/runbooks/install.md`.
- **P:** ¿Cuánta memoria pide? **R:** El perfil suma 13,73 GiB de *requests* en el pico, comprobado por `vectra-risk/platform/tests/test_kind_profile.py`.
- **Ojo:** staging y producción no se despliegan. Hay excepciones anotadas a «kind igual a staging» (réplicas y memoria reducidas) en `vectra-risk/DECISIONES-LOOP.md`. El failover de zona quedó inconcluso: pide una máquina de 32 GiB.

### Namespace
- **Qué es:** división lógica de un clúster.
- **En Vectra:** nueve propios: `vectra-edge` (borde y consola), `vectra-app` (servicios), `vectra-serving` (modelos), `vectra-staging` (validación de modelos), `vectra-data`, `vectra-identity`, `vectra-mock`, `vectra-observability` y `vectra-restore-drill`.
- **Dónde:** `vectra-risk/platform/namespaces/`.
- **P:** ¿Qué trae cada namespace? **R:** Etiquetas de Pod Security `restricted`, inyección de Linkerd con política de entrada `deny`, y red denegada por defecto.
- **Ojo:** `vectra-staging` es un namespace del mismo clúster para validar modelos; no es el entorno staging.

### Pod
- **Qué es:** unidad mínima de ejecución: uno o más contenedores que comparten red.
- **En Vectra:** cada pod de un namespace propio lleva además el proxy de Linkerd como *sidecar* nativo.
- **Dónde:** plantillas en `vectra-risk/case-management/chart/` y los demás charts de unidad.
- **P:** ¿Qué restricciones tienen los pods? **R:** No root, sistema de archivos de solo lectura, sin escalada de privilegios, sin capacidades y perfil seccomp por defecto.

### Deployment
- **Qué es:** objeto que mantiene N réplicas de un pod sin estado y hace actualizaciones graduales.
- **En Vectra:** los servicios de U3 a U11 y los operadores.
- **Dónde:** carpeta `chart/` de cada unidad, por ejemplo `vectra-risk/decision-registry/chart/`.
- **P:** ¿Cuántas réplicas? **R:** Mínimo 2 con reparto entre zonas; lo exige `vectra-risk/platform/policies/kyverno/require-spread-and-pdb.yaml`.

### StatefulSet
- **Qué es:** como un Deployment, pero con identidad y disco estables por réplica.
- **En Vectra:** Valkey y sus centinelas, Keycloak, Prometheus, Alertmanager y Vault.
- **Dónde:** `vectra-risk/identity-edge/charts/valkey/`.
- **P:** ¿PostgreSQL es un StatefulSet? **R:** No: lo gestiona el operador CloudNativePG con su propio recurso `Cluster`.

### Job
- **Qué es:** tarea que corre hasta terminar.
- **En Vectra:** migraciones de base de datos como ganchos de sincronización, la validación de un modelo (`model-validation-job`), la carga del realm de Keycloak y el intento de escritura al core de la demo D3 (`rt5-demo-<runId>`).
- **Dónde:** `vectra-risk/governance/validation_job/`, `vectra-risk/case-management/chart/`.
- **P:** ¿Quién lanza el Job de validación? **R:** `governance-service`, por la API de Kubernetes, cuando el ingeniero de riesgo pide validar.

### CronJob
- **Qué es:** Job que se repite con un horario.
- **En Vectra:** monitoreo de sesgo (cada 15 minutos), agregador del registro (cada 5 minutos), simulacro de restauración (semanal) y comprobaciones de identidad y de Grafana.
- **Dónde:** `vectra-risk/bias-monitoring/chart/values-monitoring-policy.yaml`, `vectra-risk/decision-registry/chart/values.yaml`, `vectra-risk/platform/restore-drill/cronjob.yaml`.
- **P:** ¿Quién congela un modelo? **R:** El CronJob de sesgo, con la identidad `bias-monitoring-job`; es la única que tiene ese permiso.
- **Ojo:** los CronJobs de retención de casos, archivo y puntos de control del registro están diferidos en la demo.

### HPA (Horizontal Pod Autoscaler)
- **Qué es:** objeto que ajusta el número de réplicas según una métrica.
- **En Vectra:** de 2 a 6 réplicas al 70 % de CPU en los servicios de staging y producción; en kind queda fijo en 2 a 2.
- **Dónde:** archivos `values-kind.yaml` de cada chart, por ejemplo `vectra-risk/case-management/chart/values-kind.yaml`; regla en `vectra-risk/platform/policies/rego/hpa.rego`.
- **P:** ¿Probaste el escalado? **R:** No: en kind el mínimo y el máximo son iguales y las pruebas de carga están diferidas.

### PDB (PodDisruptionBudget)
- **Qué es:** límite a cuántas réplicas pueden caer a la vez en un mantenimiento.
- **En Vectra:** uno por servicio; `hpa.rego` falla el render si un Deployment no tiene el suyo.
- **Dónde:** `vectra-risk/platform/policies/rego/hpa.rego`.
- **P:** ¿Para qué sirve aquí? **R:** Para que vaciar un nodo no deje un servicio sin réplicas.

### metrics-server
- **Qué es:** componente que publica el uso de CPU y memoria de los pods.
- **En Vectra:** alimenta los HPA; solo se instala en kind, porque un clúster del banco ya lo trae.
- **Dónde:** `vectra-risk/platform/operators/metrics-server-kind.yaml`.
- **Versión:** chart 3.13.0 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿De dónde saca el HPA la métrica? **R:** De metrics-server.

### ServiceAccount
- **Qué es:** identidad de una carga de trabajo dentro del clúster.
- **En Vectra:** es la identidad con la que Linkerd autoriza cada llamada entre servicios, y la que usan los agentes del loop para leer (`vectra-readonly-agent`).
- **Dónde:** `vectra-risk/platform/rbac/readonly-agent/readonly-agent-kind.yaml`.
- **P:** ¿Cuál es la ServiceAccount del agente? **R:** `vectra-readonly-agent`, en el namespace `argocd`: solo `get`, `list` y `watch`, y nada sobre `secrets`.
- **Ojo:** existe solo en kind. No hay un agente desplegado dentro del clúster: los agentes corren en la máquina de desarrollo con un kubeconfig de esa cuenta.

### RBAC
- **Qué es:** *Role-Based Access Control*: permisos por rol sobre la API de Kubernetes.
- **En Vectra:** mínimo privilegio y sin comodines. Dos roles propios para personas y agentes: el del operador de verificación (K16, lectura y `port-forward`) y el del agente de solo lectura.
- **Dónde:** `vectra-risk/platform/rbac/verification-operator/k16.yaml`, `vectra-risk/platform/rbac/readonly-agent/readonly-agent-kind.yaml`; comodines prohibidos en `vectra-risk/platform/policies/kyverno/disallow-rbac-wildcards.yaml`.
- **P:** ¿Cómo demuestras el mínimo privilegio? **R:** Con la herramienta `permissions` del servidor MCP, que devuelve `kubectl auth can-i --list` de la cuenta del agente.
- **Ojo:** en kind, External Secrets Operator puede leer todos los `Secret` (excepción K11); la instancia por namespace está decidida y sin implementar.

### vectra-readonly-agent
- **Qué es:** la ServiceAccount de solo lectura con la que corren los agentes del loop.
- **En Vectra:** vive en el namespace `argocd` con un `ClusterRole` del mismo nombre, sin comodines: cada regla lista solo `get`, `list` y `watch`. Faltan a propósito `secrets`, `pods/exec`, `pods/portforward`, `pods/attach`, todo verbo de escritura, `impersonate`, `escalate` y `bind`.
- **Dónde:** `vectra-risk/platform/rbac/readonly-agent/readonly-agent-kind.yaml`; prueba en `vectra-risk/platform/tests/test_readonly_agent.py`.
- **P:** ¿Por qué no usar el rol integrado `view`? **R:** Porque es un rol agregado: lo que trae lo decide cualquier chart que lo etiquete, y no cubre los recursos propios (Argo CD, KServe, Linkerd).
- **Ojo:** solo existe en kind. Staging y producción no la tienen.

### kubectl auth can-i
- **Qué es:** orden que pregunta a la API de Kubernetes si una identidad puede hacer algo; con `--list` enumera todo lo que puede.
- **En Vectra:** es la evidencia de mínimo privilegio que pide la guía de sustentación: `kubectl auth can-i --list --as=system:serviceaccount:argocd:vectra-readonly-agent`. El servidor MCP la usa al arrancar y la ofrece en su herramienta `permissions`.
- **Dónde:** `vectra-risk/loop/mcp-solo-lectura/src/vectra_mcp_readonly/kubectl.py`; salidas guardadas en `vectra-risk/aidlc-docs/construction/system-verification/evidence/sustentacion/mcp/`.
- **P:** ¿Qué responde para la cuenta del agente? **R:** «Sí» a `get`, `list` y `watch` de pods, eventos, cargas de trabajo, Applications e InferenceServices; «no» a crear o borrar pods, parchear Deployments, leer o listar `secrets`, `pods/exec` e `impersonate`.
- **Ojo:** `--as` necesita una identidad con permiso de suplantar: la ejecuta el operador con el kubeconfig de administrador. El agente pregunta por sí mismo, sin `--as`.

### Pod Security
- **Qué es:** control de admisión integrado de Kubernetes con tres niveles: `privileged`, `baseline` y `restricted`.
- **En Vectra:** todos los namespaces propios llevan `pod-security.kubernetes.io/enforce: restricted`; Kyverno añade sus reglas encima.
- **Dónde:** `vectra-risk/platform/namespaces/`.
- **P:** ¿Qué pasa si un pod pide ser root? **R:** La admisión lo rechaza dos veces: por Pod Security y por la política `require-run-as-non-root`.

### ResourceQuota y LimitRange
- **Qué es:** topes de recursos por namespace y valores por defecto por contenedor.
- **En Vectra:** nueve de cada uno, generados; el tope es el máximo del HPA más un 30 %.
- **Dónde:** `vectra-risk/platform/policies/quotas/`.
- **P:** ¿Qué pasa con un contenedor sin *requests*? **R:** Kyverno lo rechaza (`require-resources`); el LimitRange solo pone valores por defecto.

### PriorityClass
- **Qué es:** prioridad de un pod para el planificador cuando falta capacidad.
- **En Vectra:** cuatro clases: `vectra-critical`, `vectra-high`, `vectra-normal` y `vectra-low`.
- **Dónde:** `vectra-risk/platform/policies/priority-classes.yaml`.
- **P:** ¿Qué clase usa un servicio? **R:** La declara su chart; por ejemplo, el registro de decisiones usa `vectra-high` (`vectra-risk/decision-registry/chart/values.yaml`). Kyverno rechaza un pod sin clase (`require-priority-class`).

### NetworkPolicy
- **Qué es:** cortafuegos de capa 3 y 4 entre pods.
- **En Vectra:** todo denegado por defecto en entrada y salida, más una política por cada flujo permitido. En kind hay 372, generadas.
- **Dónde:** `vectra-risk/platform/network/generated/`.
- **P:** ¿Las escribiste a mano? **R:** No: se generan desde la lista de flujos y la integración continua falla si lo generado no coincide.

### Lista de flujos
- **Qué es:** archivo propio del proyecto que enumera cada conexión permitida, con identificador (F01, F22, etc.).
- **En Vectra:** fuente única de la red: de ella salen las NetworkPolicy y los recursos de autorización de Linkerd. Los casos que deben fallar (X01 a X10) están aparte.
- **Dónde:** `vectra-risk/platform/network/flows.yaml`, `vectra-risk/platform/network/forbidden.yaml`, `vectra-risk/platform/network/generate.py`.
- **P:** ¿Cómo abres un flujo nuevo? **R:** Añadiendo un renglón a `flows.yaml`, regenerando y abriendo un PR.
- **Ojo:** la demo D1 apaga el flujo F22 (scoring hacia el explicador) con un PR para provocar el fail-closed.

### Calico
- **Qué es:** complemento de red (CNI) que hace cumplir las NetworkPolicy.
- **En Vectra:** reemplaza la red por defecto de kind, que no las aplica.
- **Dónde:** se instala desde el manifiesto del proyecto Calico, según `vectra-risk/platform/runbooks/install.md`; no hay copia en el repositorio.
- **Versión:** v3.33.0 (la URL citada en ese runbook).
- **P:** ¿Cómo sabes que las políticas se aplican? **R:** Con la prueba de conformidad de NetworkPolicy: 51 pruebas, 0 fallos, en la evidencia de U1.

### cloud-provider-kind
- **Qué es:** herramienta que da direcciones a los servicios de tipo LoadBalancer en kind.
- **En Vectra:** expone el gateway; solo `api-gateway` puede ser LoadBalancer.
- **Dónde:** `vectra-risk/platform/runbooks/install.md`, `vectra-risk/platform/kind/gateway-address.sh`, `vectra-risk/platform/policies/kyverno/restrict-loadbalancer.yaml`.
- **P:** ¿Usas MetalLB? **R:** No.
- **Ojo:** la dirección del gateway cambia al reiniciar la máquina; hay que volver a ajustar `/etc/hosts`.

---

## 3. GitOps, Argo CD y Helm

### GitOps
- **Qué es:** operar el clúster desde Git: el estado deseado está en el repositorio y un controlador lo reconcilia.
- **En Vectra:** cada cambio es un PR; al fusionarlo, una persona sincroniza la aplicación en Argo CD.
- **Dónde:** `vectra-risk/vectra-risk-gitops/`.
- **P:** Muéstrame el bucle GitOps. **R:** En la demo D3: un PR cambia un valor, se fusiona, se sincroniza `case-management` y nace el Job.

### Argo CD
- **Qué es:** controlador de GitOps para Kubernetes.
- **En Vectra:** compara el clúster con `main` y aplica solo cuando una persona pulsa sincronizar.
- **Dónde:** `vectra-risk/platform/operators/argo-cd.yaml` y `vectra-risk/platform/operators/argo-cd-kind.yaml`.
- **Versión:** chart `argo-cd` 10.11.6 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Quién instala Argo CD? **R:** El operador, una vez, con Helm; después lo adopta su propia Application.

### Application
- **Qué es:** recurso de Argo CD que une una ruta de Git con un destino en el clúster.
- **En Vectra:** una por componente; en kind son 55 más la raíz.
- **Dónde:** `vectra-risk/vectra-risk-gitops/apps/kind/`.
- **P:** ¿Cómo sabes que todo está sano? **R:** La herramienta `argo_applications` del servidor MCP lista sincronización y salud de cada una.
- **Ojo:** el cierre de U1 midió 41 aplicaciones sanas, cuando aún no había servicios; hoy el catálogo genera 55. `linkerd-control-plane` y `kserve-crd` quedan `OutOfSync` aceptados.

### AppProject
- **Qué es:** recurso de Argo CD que limita qué repositorios, destinos y tipos de recurso puede usar un grupo de Applications.
- **En Vectra:** `vectra-kind`, `vectra-staging` y `vectra-prod`, con lista explícita de recursos de clúster; una regla Rego prohíbe el proyecto `default` y los comodines.
- **Dónde:** `vectra-risk/vectra-risk-gitops/apps/kind/`, `vectra-risk/platform/policies/rego/platform.rego`.
- **P:** ¿Para qué sirve? **R:** Para que una Application no pueda desplegar fuera de sus namespaces ni desde otro repositorio.

### Aplicación raíz
- **Qué es:** patrón *app of apps*: una Application que apunta a la carpeta de las demás.
- **En Vectra:** `root`, que lee `vectra-risk/vectra-risk-gitops/apps/kind` en `main`.
- **Dónde:** `vectra-risk/vectra-risk-gitops/apps/kind/root.yaml`.
- **P:** ¿Cómo añades un componente? **R:** Un renglón en `components.yaml`, regenerar, PR, y sincronizar `root` y luego la nueva.

### components.yaml y generate.py
- **Qué es:** catálogo propio de componentes y su generador.
- **En Vectra:** `components.yaml` lista 59 componentes con *wave*, namespace, chart, versión y entornos; `generate.py` escribe las Applications y los valores por entorno, y con `--check` falla si hay diferencia.
- **Dónde:** `vectra-risk/vectra-risk-gitops/components.yaml`, `vectra-risk/vectra-risk-gitops/generate.py`.
- **P:** ¿Dónde se fijan las versiones de los charts? **R:** En `components.yaml`.

### Sync
- **Qué es:** acción de Argo CD que aplica al clúster lo que hay en Git.
- **En Vectra:** siempre manual y hecha por una persona.
- **Dónde:** procedimiento en `vectra-risk/platform/runbooks/install.md`.
- **P:** ¿Qué pasa entre fusionar y sincronizar? **R:** Nada: la Application queda `OutOfSync` hasta que alguien la sincroniza.

### Wave
- **Qué es:** *sync wave* (ola de sincronización): número que ordena qué se aplica antes.
- **En Vectra:** siete, de la 0 a la 6: operadores y definiciones; malla, políticas, namespaces y red; datos; identidad y borde; observabilidad; servicios; y modelos servidos.
- **Dónde:** campo `wave` de `vectra-risk/vectra-risk-gitops/components.yaml`; prueba en `vectra-risk/platform/tests/test_waves.py`.
- **P:** ¿Argo CD respeta las waves solo? **R:** No aquí: sin auto-sync, el operador sigue el orden del runbook.
- **Ojo:** son siete, no seis: la 6 se añadió para `model-serving`, que necesita a los servicios de la 5.

### Prune
- **Qué es:** opción de sincronización que borra del clúster lo que ya no está en Git.
- **En Vectra:** no está en la política de ninguna Application; el operador la marca a mano cuando el guion lo pide, por ejemplo al apagar F22 en D1.
- **Dónde:** `vectra-risk/system-verification/demos/journey-7-3.md`.
- **P:** ¿Hay *self-heal*? **R:** No: ni `prune` ni `selfHeal` automáticos.

### Auto-sync desactivado
- **Qué es:** decisión de no usar `syncPolicy.automated` en Argo CD.
- **En Vectra:** ninguna Application la tiene y una política de Kyverno rechaza crear una que la tenga. Motivo: AUTONOMIA-01, un cambio solo llega al clúster con una aprobación humana explícita.
- **Dónde:** `vectra-risk/platform/policies/kyverno/disallow-argocd-auto-sync.yaml`, `vectra-risk/vectra-risk-gitops/README.md`.
- **P:** ¿Eso no rompe GitOps? **R:** No: Git sigue siendo la única fuente; lo que se quita es la aplicación sin persona.
- **Ojo:** gracias a esto, cuando un agente encendió los nodos en la prueba de cambio de modelo, nada se aplicó solo.

### Helm
- **Qué es:** gestor de paquetes de Kubernetes: plantillas más valores.
- **En Vectra:** forma de entrega del producto (requisito FR-PLT-01) y de casi todos los componentes de terceros.
- **Dónde:** `vectra-risk/platform/charts.sh` (descarga), `vectra-risk/platform/render.sh` (render).
- **Versión:** v4.3.0 (`vectra-risk/platform/tools.env`).
- **P:** ¿Los agentes pueden hacer `helm install`? **R:** No: está en `deny` de `.claude/settings.json`.

### Chart
- **Qué es:** paquete de Helm.
- **En Vectra:** de terceros (19 en kind) y propios: uno por unidad de servicio, más namespaces, datos, Valkey y modelos.
- **Dónde:** `vectra-risk/platform/data/chart/`, `vectra-risk/model-serving/chart/`, `vectra-risk/identity-edge/charts/valkey/`.
- **P:** ¿Cómo revisas un cambio de chart antes de aplicarlo? **R:** Con los renders guardados en `vectra-risk/platform/rendered/`: el PR muestra la diferencia en el manifiesto final.

### Kustomize
- **Qué es:** herramienta para componer manifiestos sin plantillas.
- **En Vectra:** uso mínimo: genera los ConfigMap de cuatro tableros.
- **Dónde:** `vectra-risk/platform/observability/dashboards/kustomization.yaml`.
- **P:** ¿Helm o Kustomize? **R:** Helm; Kustomize solo para esos tableros.

---

## 4. Políticas de admisión

### Kyverno
- **Qué es:** motor de políticas de admisión para Kubernetes, escritas en YAML.
- **En Vectra:** rechaza en la puerta lo que incumple las reglas de seguridad y de operación.
- **Dónde:** `vectra-risk/platform/policies/kyverno/`, valores en `vectra-risk/platform/operators/kyverno.yaml`.
- **Versión:** chart 3.9.2 (`vectra-risk/vectra-risk-gitops/components.yaml`); CLI v1.19.2 (`vectra-risk/platform/tools.env`).
- **P:** Dame un ejemplo de rechazo. **R:** Un pod con una imagen `latest`: la política `disallow-latest` exige digest.

### ClusterPolicy
- **Qué es:** política de Kyverno con alcance de clúster.
- **En Vectra:** 19 archivos: sin `latest`, no root, sin privilegiados, sin `hostPath`, raíz de solo lectura, recursos declarados, clase de prioridad, etiqueta de criticidad, sin `Secret` planos, sin comodines en RBAC, LoadBalancer restringido, registros permitidos, límites de HPA, reparto y PDB, sin auto-sync, verificación de firmas y tres que mutan.
- **Dónde:** `vectra-risk/platform/policies/kyverno/`; pruebas en `vectra-risk/platform/policies/kyverno/kyverno-test.yaml`.
- **P:** ¿Las 19 están activas en kind? **R:** 18: `verify-images` solo se instala en staging y producción.

### Conftest y Rego
- **Qué es:** Conftest evalúa archivos contra reglas escritas en Rego, el lenguaje de Open Policy Agent.
- **En Vectra:** revisa los manifiestos renderizados en el PR, antes de que lleguen al clúster: reparto por zonas, *sidecar* nativo, comodines, verbos del rol K16, proyecto de cada Application y que todo Deployment tenga HPA y PDB.
- **Dónde:** `vectra-risk/platform/policies/rego/platform.rego`, `vectra-risk/platform/policies/rego/hpa.rego`.
- **Versión:** conftest v0.71.1 (`vectra-risk/platform/tools.env`).
- **P:** ¿Por qué Kyverno y Conftest? **R:** Conftest frena en el PR; Kyverno frena en el clúster. Son dos momentos distintos.

---

## 5. Malla de servicios y borde

### Malla de servicios
- **Qué es:** capa de red que pone un proxy junto a cada pod para cifrar, autenticar y observar el tráfico.
- **En Vectra:** Linkerd, en los nueve namespaces propios.
- **Dónde:** `vectra-risk/platform/mesh/`.
- **P:** ¿Qué te da que no dé NetworkPolicy? **R:** Identidad criptográfica del llamador y autorización por ruta y método HTTP.

### Linkerd
- **Qué es:** malla de servicios ligera, proyecto graduado de la CNCF.
- **En Vectra:** mTLS automático entre servicios y autorización por identidad; instalado con su complemento CNI para no dar capacidades de red a los pods.
- **Dónde:** `vectra-risk/platform/mesh/linkerd-values.yaml`, `vectra-risk/platform/mesh/linkerd-kind.yaml`.
- **Versión:** charts 2026.10.2 del canal *edge* (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Por qué el canal *edge*? **R:** Es el que fija `components.yaml`; el repositorio no nombra una versión estable.
- **Ojo:** tras suspender o reiniciar la máquina hay que reiniciar Linkerd y recrear los pods con malla (`vectra-risk/platform/runbooks/install.md`).

### mTLS
- **Qué es:** TLS mutuo: cliente y servidor se autentican con certificado.
- **En Vectra:** lo ponen los proxies de Linkerd; la identidad es la ServiceAccount.
- **Dónde:** certificados en `vectra-risk/platform/mesh/certificates.yaml`.
- **P:** ¿Quién emite los certificados? **R:** cert-manager: ancla de confianza de 1 año y emisor de identidad de 48 horas.

### Proxy
- **Qué es:** proceso que intercepta el tráfico de un pod.
- **En Vectra:** el de Linkerd, como *sidecar* nativo; una política de Kyverno lo añade también a los Jobs.
- **Dónde:** `vectra-risk/platform/policies/kyverno/add-native-sidecar-to-jobs.yaml`.
- **P:** ¿Quién respondió el 403 de la demo D3? **R:** El proxy, no la aplicación: la respuesta lleva la cabecera `l5d-proxy-error`.

### Server
- **Qué es:** recurso de Linkerd que nombra un puerto de unos pods para poder ponerle política.
- **En Vectra:** 52 en kind, generados desde la lista de flujos.
- **Dónde:** `vectra-risk/platform/network/generated/`.
- **P:** ¿Qué pasa con un puerto sin `Server`? **R:** Aplica la política por defecto del namespace, que es denegar.

### AuthorizationPolicy
- **Qué es:** recurso de Linkerd que dice qué identidades pueden llamar a un `Server` o a una ruta.
- **En Vectra:** 124 en kind, generadas; junto con `MeshTLSAuthentication` y `HTTPRoute` limitan identidad, ruta y método.
- **Dónde:** `vectra-risk/platform/network/generated/`.
- **P:** ¿Por qué la malla deniega con 403? **R:** Porque la política por defecto es `deny` y solo pasan las llamadas con una `AuthorizationPolicy` que nombre esa identidad y esa ruta; hacia el core solo está permitido el `GET` de `case-service`.

### Gateway API
- **Qué es:** API estándar de Kubernetes para la entrada de tráfico, sucesora de Ingress.
- **En Vectra:** la usan Envoy Gateway en el borde y Linkerd para sus rutas internas.
- **Dónde:** `vectra-risk/identity-edge/gateway/generated/`.
- **P:** ¿Usas Ingress? **R:** No: Gateway API.

### Envoy Gateway
- **Qué es:** implementación de Gateway API sobre el proxy Envoy.
- **En Vectra:** única puerta de entrada: TLS, validación del token, autorización por rol, límite de tasa, límite de tamaño y cabeceras de seguridad.
- **Dónde:** `vectra-risk/platform/operators/envoy-gateway.yaml`, `vectra-risk/identity-edge/gateway/routes.yaml`, decisión en `vectra-risk/identity-edge/docs/adr-envoy-gateway.md`.
- **Versión:** chart `gateway-helm` v1.9.3 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Dónde se valida el JWT? **R:** En el gateway primero y otra vez en cada servicio.

### HTTPRoute
- **Qué es:** recurso de Gateway API que enruta peticiones por nombre de host y ruta.
- **En Vectra:** generadas desde `routes.yaml` por `route_gen.py`, igual que el resto del borde.
- **Dónde:** `vectra-risk/identity-edge/gateway/routes.yaml`, `vectra-risk/identity-edge/tools/route_gen.py`.
- **P:** ¿Por dónde entra una solicitud de un canal? **R:** Por la ruta de ingesta del gateway, hacia `case-service`.

### SecurityPolicy
- **Qué es:** recurso de Envoy Gateway para autenticación y autorización en una ruta.
- **En Vectra:** valida el JWT contra las llaves públicas de Keycloak y autoriza por cliente, rol y permiso, con acción por defecto `Deny`.
- **Dónde:** `vectra-risk/identity-edge/gateway/generated/`.
- **P:** ¿El gateway hace el inicio de sesión? **R:** No: solo valida el token; el inicio de sesión lo hace la SPA contra Keycloak.

### Límite de tasa
- **Qué es:** tope de peticiones por unidad de tiempo.
- **En Vectra:** global, por usuario o por origen: consola 20 por segundo por usuario, canal 10 por segundo, simulador 30 por segundo, inicio de sesión 600 por minuto por dirección.
- **Dónde:** bloque `rate_limits` de `vectra-risk/identity-edge/gateway/routes.yaml`.
- **P:** ¿Qué pasa si se cae el contador? **R:** Las rutas de autenticación fallan cerrado.

### Valkey
- **Qué es:** almacén clave-valor en memoria, bifurcación libre de Redis.
- **En Vectra:** guarda los contadores del límite de tasa, con centinelas para la alta disponibilidad. No guarda datos de negocio.
- **Dónde:** `vectra-risk/identity-edge/charts/valkey/`.
- **Versión:** 8.1.11 (`appVersion` de `vectra-risk/identity-edge/charts/valkey/Chart.yaml`).
- **P:** ¿Valkey guarda sesiones? **R:** No: solo contadores.

### CSP (Content Security Policy)
- **Qué es:** cabecera HTTP que limita de dónde puede cargar recursos una página.
- **En Vectra:** restrictiva y sin `unsafe-inline`: todo desde el mismo origen, sin marcos ajenos y con *Trusted Types*. La pone el gateway, no nginx ni el BFF.
- **Dónde:** perfil `spa` de `vectra-risk/identity-edge/gateway/routes.yaml`; prueba en `vectra-risk/console/spa/tests/csp/csp.spec.ts`.
- **P:** ¿Cómo sabes que la consola la cumple? **R:** Una prueba de Playwright exige cero violaciones y que la cabecera sea igual, carácter a carácter, a la del perfil.

### Trusted Types
- **Qué es:** mecanismo del navegador que impide pasar texto sin revisar a las funciones que inyectan HTML o código en la página.
- **En Vectra:** la CSP del perfil `spa` lleva `require-trusted-types-for 'script'` y `trusted-types 'none'`: la consola no puede crear ninguna política, así que no puede inyectar HTML desde texto.
- **Dónde:** `vectra-risk/identity-edge/gateway/routes.yaml`.
- **P:** ¿Qué pasa si el texto libre de una solicitud trae código? **R:** Se muestra como texto; hay una prueba de extremo a extremo que lo comprueba.
- **Ojo:** lo aplican los navegadores que lo implementan; en los demás protege el resto de la CSP.

### COOP (Cross-Origin-Opener-Policy)
- **Qué es:** cabecera que aísla una página de las ventanas de otros orígenes que la abren o que ella abre.
- **En Vectra:** `Cross-Origin-Opener-Policy: same-origin`, en el perfil común de cabeceras junto a HSTS, `nosniff` y `Referrer-Policy`.
- **Dónde:** `vectra-risk/identity-edge/gateway/routes.yaml`.
- **P:** ¿Forma parte de la CSP? **R:** No: es una cabecera aparte, del perfil común; junto con la CSP compone el endurecimiento del navegador que pone el gateway.

---

## 6. Identidad

### Keycloak
- **Qué es:** proveedor de identidad de código abierto.
- **En Vectra:** hace de proveedor de identidad del banco: usuarios, roles, segundo factor y clientes de servicio.
- **Dónde:** `vectra-risk/identity-edge/keycloak/`.
- **Versión:** imagen `keycloak:26.8.1` por digest (`vectra-risk/identity-edge/keycloak/Dockerfile`); chart `keycloakx` 7.4.0 (`vectra-risk/identity-edge/keycloak/values/common.yaml`).
- **P:** ¿En producción sería Keycloak? **R:** Sería el proveedor del banco; Keycloak lo simula.
- **Ojo:** los usuarios son sintéticos (`analista-1`, `cro-1`, `cumplimiento-1`).

### Realm
- **Qué es:** espacio aislado de usuarios, roles y clientes en Keycloak.
- **En Vectra:** `vectra`, definido como código, con un archivo por entorno.
- **Dónde:** `vectra-risk/identity-edge/keycloak/realm/realm.kind.yaml`.
- **P:** ¿Cómo cambias un rol? **R:** Editando el archivo del realm en un PR; un verificador (`realm_lint`) lo revisa.

### Cliente
- **Qué es:** aplicación registrada en Keycloak que puede pedir tokens.
- **En Vectra:** 17: la consola (`vectra-console`, pública), `promotion-tool`, Grafana y un cliente por cada identidad de servicio.
- **Dónde:** `vectra-risk/identity-edge/keycloak/realm/realm.kind.yaml`.
- **P:** ¿Cómo se autentican los servicios? **R:** Con `private_key_jwt`: firman una aserción con su llave privada; no hay secreto compartido.

### OIDC (OpenID Connect)
- **Qué es:** capa de identidad sobre OAuth 2.0 que entrega tokens firmados (JWT) con datos del usuario.
- **En Vectra:** la consola usa el flujo de código de autorización; los servicios validan el JWT en cada petición y solo aceptan RS256 y ES256.
- **Dónde:** `vectra-risk/console/spa/src/auth/`, `vectra-risk/contracts/python/vectra_common/src/vectra_common/authn.py`.
- **P:** ¿Dónde guarda los tokens la consola? **R:** En memoria; en `sessionStorage` solo queda el estado transitorio del flujo.

### PKCE
- **Qué es:** *Proof Key for Code Exchange*: protege el flujo de código de autorización en clientes sin secreto.
- **En Vectra:** obligatorio en la consola, con método S256.
- **Dónde:** cliente `vectra-console` en `vectra-risk/identity-edge/keycloak/realm/realm.kind.yaml`.
- **P:** ¿Por qué PKCE? **R:** Porque una SPA no puede guardar un secreto.

### acr
- **Qué es:** *Authentication Context Class Reference*: dato del token que dice con qué nivel se autenticó el usuario.
- **En Vectra:** dos valores: `pwd` (solo contraseña, nivel 1) y `mfa` (con segundo factor, nivel 2).
- **Dónde:** `vectra-risk/identity-edge/keycloak/realm/realm.kind.yaml`; lo exige `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`.
- **P:** ¿Cómo sabe el servidor que hubo segundo factor? **R:** Lee `acr = mfa` y la hora de autenticación del token.

### amr
- **Qué es:** *Authentication Methods References*: lista de métodos usados al autenticarse.
- **En Vectra:** `pwd`, `otp` (código temporal) y `hwk` (llave física); queda como evidencia.
- **Dónde:** `vectra-risk/identity-edge/keycloak/realm/realm.kind.yaml`.
- **P:** ¿Diferencia con `acr`? **R:** `acr` es el nivel alcanzado; `amr`, los métodos concretos.

### TOTP
- **Qué es:** *Time-based One-Time Password*: código de 6 dígitos que cambia cada 30 segundos.
- **En Vectra:** segundo factor por omisión; obligatorio para ingeniero de riesgo, CRO y cumplimiento.
- **Dónde:** `vectra-risk/identity-edge/keycloak/realm/realm.kind.yaml`.
- **P:** ¿Hay alternativa? **R:** WebAuthn, opcional.

### Step-up (técnico)
- **Qué es:** reautenticación con un nivel mayor justo antes de una acción sensible.
- **En Vectra:** la consola abre una ventana emergente contra Keycloak que fuerza el segundo factor; el servidor exige `acr = mfa` con no más de 900 segundos de antigüedad y, si no, responde 403 `mfa_required`.
- **Dónde:** `vectra-risk/console/spa/src/stepup/`, `MFA_MAX_AGE` en `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`.
- **P:** ¿Quién impone el step-up? **R:** El servidor (BFF y servicios); la consola solo lo facilita.

### keycloak-config-cli
- **Qué es:** herramienta que carga en Keycloak un realm descrito en archivos.
- **En Vectra:** corre como gancho después de sincronizar Keycloak.
- **Dónde:** `vectra-risk/identity-edge/keycloak/values/kind.yaml`, `vectra-risk/identity-edge/docs/realm-importacion.md`.
- **Versión:** 6.5.1 (etiqueta de imagen en esos valores).
- **P:** ¿Cómo llega el realm al clúster? **R:** Por ese gancho, desde el archivo en Git.
- **Ojo:** activado solo en kind.

### Tema de Keycloak
- **Qué es:** plantillas y estilos de las pantallas de inicio de sesión.
- **En Vectra:** tema propio `vectra`, dentro de la imagen construida; recibe el idioma de la consola por `ui_locales`.
- **Dónde:** `vectra-risk/identity-edge/keycloak/themes/`.
- **P:** ¿Por qué construyes tu propia imagen de Keycloak? **R:** Para incluir el tema y la ruta `/auth`.

---

## 7. Certificados y secretos

### cert-manager
- **Qué es:** operador que emite y renueva certificados dentro del clúster.
- **En Vectra:** certificados de la malla, del gateway, de PostgreSQL y de Keycloak.
- **Dónde:** `vectra-risk/platform/operators/cert-manager.yaml`, `vectra-risk/platform/mesh/certificates.yaml`.
- **Versión:** chart v1.21.3 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Qué pasa si un certificado va a vencer? **R:** Hay una alerta con su runbook: `vectra-risk/platform/runbooks/certificate-expiring-soon.md`.

### CA interna
- **Qué es:** autoridad de certificación propia del clúster.
- **En Vectra:** emisor `vectra-internal-ca`, creado desde uno autofirmado; trust-manager reparte su certificado a los namespaces.
- **Dónde:** `vectra-risk/platform/mesh/certificates.yaml`, `vectra-risk/platform/mesh/trust-manager-values.yaml`.
- **P:** ¿El navegador confía en ella? **R:** No sin instalarla: es una CA de demostración.

### Vault
- **Qué es:** almacén de secretos de HashiCorp.
- **En Vectra:** hace de bóveda del banco en kind; de ella salen todas las credenciales.
- **Dónde:** `vectra-risk/platform/operators/vault-kind.yaml`, siembra en `vectra-risk/platform/kind/seed-vault.sh`.
- **Versión:** chart 0.34.1 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Vault está en modo producción? **R:** No: modo de desarrollo, en memoria y con token raíz fijo.
- **Ojo:** si el pod se reinicia pierde todo y hay que volver a sembrar. En producción el almacén sería la bóveda del banco.

### External Secrets Operator
- **Qué es:** operador que copia secretos de un almacén externo a `Secret` de Kubernetes.
- **En Vectra:** único camino para crear un `Secret`; una política de Kyverno rechaza los `Secret` escritos a mano.
- **Dónde:** `vectra-risk/platform/operators/external-secrets.yaml`, `vectra-risk/platform/secrets/`.
- **Versión:** chart 2.14.0 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Hay secretos en Git? **R:** No: en Git están los `ExternalSecret`, que solo dicen qué ruta leer.
- **Ojo:** K11: en kind el operador tiene lectura de todos los `Secret` del clúster (`vectra-risk/platform/secrets/eso-rbac-secrets-read-kind.yaml`).

### ExternalSecret y ClusterSecretStore
- **Qué es:** recursos de External Secrets: el primero pide un secreto; el segundo dice de qué almacén sale.
- **En Vectra:** un almacén `vectra-store` por entorno y un `ExternalSecret` por credencial.
- **Dónde:** `vectra-risk/platform/secrets/cluster-secret-store-kind.yaml`.
- **P:** ¿Qué pasa si se borra un `ExternalSecret`? **R:** El `Secret` se conserva: la política de borrado es `Retain`.

---

## 8. Datos y almacenamiento

### PostgreSQL
- **Qué es:** base de datos relacional.
- **En Vectra:** cuatro bases: `registry-db` (registro), `case-db` (casos), `governance-db` (modelos y políticas) y `keycloak-db`.
- **Dónde:** `vectra-risk/platform/data/chart/`.
- **Versión:** imagen `postgresql:17.9` por digest (`vectra-risk/platform/data/chart/values.yaml`).
- **P:** ¿Cómo impides que alguien edite el registro? **R:** El rol de la aplicación solo tiene `INSERT` y `SELECT`, un disparador rechaza `UPDATE` y `DELETE`, y la cadena de hashes delata lo demás.

### CloudNativePG
- **Qué es:** operador de PostgreSQL para Kubernetes.
- **En Vectra:** crea los clústeres, gestiona réplicas y conmutación, y hace los respaldos.
- **Dónde:** `vectra-risk/platform/operators/cloudnative-pg.yaml`, `vectra-risk/platform/data/chart/`.
- **Versión:** chart `cloudnative-pg` 0.29.1 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Cuántas instancias hay? **R:** El diseño pide 3 con una réplica síncrona; en kind hay 1 por base, salvo `registry-db` con 2.
- **Ojo:** CloudNativePG 1.31 elimina el soporte nativo de Barman que se usa aquí: hay que migrar antes de actualizar.

### Respaldo y archivado WAL
- **Qué es:** copia completa periódica más archivado continuo del registro de escritura (WAL) para restaurar a un punto en el tiempo.
- **En Vectra:** respaldo diario y mensual hacia almacenamiento de objetos, con retención de 30 días.
- **Dónde:** `vectra-risk/platform/data/chart/`; runbooks `vectra-risk/platform/runbooks/backup-failed.md` y `vectra-risk/platform/runbooks/wal-archive-stale.md`.
- **P:** ¿A dónde van los respaldos? **R:** En kind, a MinIO dentro del clúster; en un banco irían a su almacenamiento fuera del sitio.

### Simulacro de restauración
- **Qué es:** prueba periódica de que un respaldo se puede restaurar.
- **En Vectra:** CronJob semanal que restaura `registry-db` y `case-db` en clústeres efímeros, los verifica y publica el resultado.
- **Dónde:** `vectra-risk/platform/restore-drill/`.
- **P:** ¿Cuánto tarda restaurar? **R:** 144 s `registry-db` y 110 s `case-db`, medidos en kind (`vectra-risk/aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md`).

### MinIO
- **Qué es:** almacenamiento de objetos compatible con S3.
- **En Vectra:** guarda paquetes de modelo, conjuntos de validación y respaldos.
- **Dónde:** `vectra-risk/platform/data/minio/`.
- **Versión:** chart `minio` 5.4.0 (`vectra-risk/vectra-risk-gitops/components.yaml`); binario `RELEASE.2025-10-15T17-29-55Z`, construido desde el código (`vectra-risk/platform/data/minio/Dockerfile`).
- **P:** ¿Por qué construyes MinIO? **R:** Porque ya no se publican imágenes oficiales sin autenticación.
- **Ojo:** el proyecto MinIO está archivado y sin mantenimiento. La decisión es dejarlo solo en kind y usar el S3 del banco en staging y producción; no está implementada.

### Model-store
- **Qué es:** depósito de MinIO donde vive cada paquete de modelo.
- **En Vectra:** KServe lee `s3://model-store/<model_version_id>/` con un usuario de solo lectura; el ingeniero de riesgo sube con otro.
- **Dónde:** `vectra-risk/platform/data/minio/values.yaml`, `vectra-risk/model-serving/chart/templates/inferenceservice.yaml`.
- **P:** ¿Puede KServe modificar un modelo? **R:** No: su usuario solo lee.

### Bloqueo de objetos (WORM)
- **Qué es:** *Write Once, Read Many*: un objeto no se puede borrar ni reescribir durante un plazo.
- **En Vectra:** en los depósitos de puntos de control y archivo del registro y de archivo de modelos.
- **Dónde:** `vectra-risk/platform/data/minio/`.
- **P:** ¿Lo probaste? **R:** Sí: la evidencia de U1 registra que MinIO rechaza borrar un objeto bloqueado.

---

## 9. Servir modelos

### KServe
- **Qué es:** plataforma para servir modelos en Kubernetes, proyecto en incubación de la CNCF.
- **En Vectra:** sirve cada versión de modelo con su predictor y su explicador.
- **Dónde:** `vectra-risk/platform/operators/kserve.yaml`, `vectra-risk/model-serving/`.
- **Versión:** charts `kserve-crd` y `kserve-resources` v0.21.0 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Usas Knative o Istio? **R:** No: modo `RawDeployment`, con Deployments y HPA normales.

### InferenceService
- **Qué es:** recurso de KServe que describe un modelo servido.
- **En Vectra:** uno por versión de modelo, llamado `isvc-<8 hexadecimales>`, con tres perfiles: `prod`, `inactive` y `staging`.
- **Dónde:** `vectra-risk/model-serving/chart/templates/inferenceservice.yaml`, `vectra-risk/vectra-risk-gitops/values/kind/model-serving.yaml`.
- **P:** ¿Quién edita ese archivo de valores? **R:** Solo `promotion-tool`, por PR.

### promotion-tool
- **Qué es:** herramienta de línea de órdenes propia que lleva una versión de modelo aprobada a servir, siempre por *pull request*.
- **En Vectra:** inicia sesión contra Keycloak como un ingeniero de riesgo, con segundo factor (OIDC con PKCE; el token vive solo en memoria). Órdenes: `list-promotable`, `create-promotion-pr` (PR que añade el InferenceService de la versión), `mark-active` (pide a gobierno el cambio de estado, después de fusionar y sincronizar), `post-activation-pr` (baja la versión anterior) y `rollback-pr`.
- **Dónde:** `vectra-risk/governance/promotion_tool/vectra_promotion/cli.py`, `vectra-risk/governance/promotion_tool/vectra_promotion/login.py`.
- **P:** ¿Por qué importa en la sustentación? **R:** Es la pieza de negocio que muestra «propone por PR, una persona aprueba»: la herramienta abre el PR y nunca aplica ni sincroniza (BR-U4-08).
- **Ojo:** es un programa determinista, no un agente. El orden es fijo: `post-activation-pr` solo vale después del `mark-active` de la versión nueva.

### Predictor
- **Qué es:** componente de un InferenceService que calcula la predicción.
- **En Vectra:** imagen propia en Python con XGBoost; devuelve puntaje y confianza.
- **Dónde:** `vectra-risk/model-serving/predictor/`.
- **P:** ¿Cargas modelos con pickle? **R:** No: formato JSON de XGBoost.

### Explainer
- **Qué es:** componente de un InferenceService que explica una predicción.
- **En Vectra:** imagen propia que calcula las contribuciones con el TreeSHAP nativo de XGBoost; vive en el mismo InferenceService que el predictor.
- **Dónde:** `vectra-risk/model-serving/explainer/`.
- **P:** ¿Cómo garantizas que explican el mismo modelo? **R:** Se despliegan juntos por versión, y el scoring compara el `model_version_id` de ambas respuestas.

### XGBoost
- **Qué es:** librería de árboles de decisión potenciados por gradiente.
- **En Vectra:** algoritmo del modelo de referencia y motor del predictor y del explicador.
- **Dónde:** `vectra-risk/reference-model/`.
- **Versión:** 3.4.1 (`vectra-risk/uv.lock`).
- **P:** ¿Vectra solo sirve XGBoost? **R:** El contrato acepta cualquier modelo tabular; el de referencia es XGBoost.

---

## 10. Observabilidad

### Prometheus
- **Qué es:** base de datos de series de tiempo que recoge métricas por *scrape* (raspado periódico).
- **En Vectra:** métricas de servicios, plataforma y malla; evalúa las reglas de alerta.
- **Dónde:** `vectra-risk/platform/observability/values/kube-prometheus-stack.yaml` y `vectra-risk/platform/observability/values/kube-prometheus-stack-kind.yaml`.
- **Versión:** chart `kube-prometheus-stack` 92.17.0 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Cuánto retiene? **R:** 3 días en kind; 30 en el diseño.

### ServiceMonitor y PodMonitor
- **Qué es:** recursos del operador de Prometheus que dicen qué raspar.
- **En Vectra:** cada chart de unidad trae su ServiceMonitor; la plataforma define cinco PodMonitor.
- **Dónde:** `vectra-risk/platform/observability/monitors/`.
- **P:** ¿Cómo empieza Prometheus a raspar un servicio nuevo? **R:** El chart del servicio incluye su monitor y el flujo de red correspondiente.

### Regla de alerta
- **Qué es:** expresión que, si se cumple durante un tiempo, produce una alerta. Recurso `PrometheusRule`.
- **En Vectra:** 28 reglas de plataforma, más las de cada unidad; cada alerta enlaza su runbook. Se prueban con `promtool`.
- **Dónde:** `vectra-risk/platform/observability/rules/platform-rules.yaml`.
- **P:** ¿Qué alertas se ven en la demo? **R:** `FailClosedPersistente` en D1 y `CoreWriteAttempt` en D3.

### Firing
- **Qué es:** estado de una alerta cuya condición se cumple (*firing*, disparada); antes pasa por `pending` si la regla tiene `for:`.
- **En Vectra:** `FailClosedPersistente` tiene `for: 1m`; `CoreWriteAttempt` no tiene `for:` y mira 5 minutos, así que se dispara al instante y se apaga sola.
- **Dónde:** `vectra-risk/system-verification/demos/rt-5.md`.
- **P:** ¿Por qué `Watchdog` siempre está disparada? **R:** Es un latido: si deja de llegar, la cadena de alertas está rota (`vectra-risk/platform/runbooks/watchdog.md`).

### Alertmanager
- **Qué es:** componente que agrupa, silencia y enruta alertas.
- **En Vectra:** recibe las alertas de Prometheus; su configuración llega como secreto.
- **Dónde:** `vectra-risk/platform/observability/values/kube-prometheus-stack.yaml`.
- **P:** ¿Dónde se ven las alertas en la demo? **R:** En la página de alertas de Prometheus; así lo dicen los guiones de D1 y D3.

### Grafana
- **Qué es:** herramienta de tableros.
- **En Vectra:** carpetas `Vectra / Sesgo`, `Vectra / Producto` y `Vectra / Operación`; tableros como código.
- **Dónde:** `vectra-risk/platform/observability/dashboards/`, `vectra-risk/platform/observability/grafana/`.
- **P:** ¿Cómo entras a Grafana en la demo? **R:** Por `port-forward`, con la cuenta de administrador.
- **Ojo:** Grafana no tiene OIDC ni está publicado por el gateway; los permisos por carpeta y rol no se enseñan (`vectra-risk/system-verification/demos/dashboard.md`).

### Pushgateway
- **Qué es:** intermediario que recibe métricas de procesos que terminan y las deja disponibles para Prometheus.
- **En Vectra:** lo usan los trabajos por lotes: monitoreo de sesgo y simulacro de restauración.
- **Dónde:** `vectra-risk/platform/observability/values/pushgateway.yaml`.
- **Versión:** chart 3.10.1 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Por qué no raspar el CronJob? **R:** Porque termina antes del siguiente raspado.

### OpenTelemetry
- **Qué es:** estándar abierto para trazas, métricas y logs.
- **En Vectra:** los servicios exportan trazas al Collector del clúster; el identificador de correlación de los logs es el de la traza.
- **Dónde:** `vectra-risk/contracts/python/vectra_common/src/vectra_common/telemetry.py`, `vectra-risk/platform/observability/values/otel-collector.yaml`.
- **Versión:** SDK 1.45.2 (`vectra-risk/uv.lock`); chart del Collector 0.178.1 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Dónde ves las trazas en kind? **R:** En ningún visor: en kind el Collector termina en un exportador de depuración.

### Loki, Tempo y Alloy
- **Qué es:** almacén de logs, almacén de trazas y agente recolector, de Grafana Labs.
- **En Vectra:** definidos para staging y producción.
- **Dónde:** `vectra-risk/platform/observability/values/loki.yaml`, `vectra-risk/platform/observability/values/tempo.yaml`, `vectra-risk/platform/observability/values/alloy.yaml`.
- **Versión:** charts 7.5.0, 1.61.3 y 1.15.0 (`vectra-risk/vectra-risk-gitops/components.yaml`).
- **P:** ¿Dónde ves los logs en la demo? **R:** Con `kubectl logs`.
- **Ojo:** no están instalados en kind: se retiraron para que el perfil quepa en memoria (`vectra-risk/DECISIONES-LOOP.md`, §11).

### Logs estructurados
- **Qué es:** logs en JSON con campos fijos.
- **En Vectra:** lista cerrada de campos; cualquier otro se descarta y se cuenta. Sin datos personales, tokens ni texto de terceros.
- **Dónde:** `LOG_RECORD_FIELDS` en `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/catalog.py`; `vectra-risk/contracts/python/vectra_common/src/vectra_common/logging.py`.
- **Versión:** structlog 26.1.0 (`vectra-risk/uv.lock`).
- **P:** ¿Cómo evitas datos personales en los logs? **R:** Solo salen los campos de la lista, y ninguno es de identificación.

### Runbook
- **Qué es:** procedimiento escrito para atender una alerta.
- **En Vectra:** uno por alerta de plataforma, más la instalación, la restauración del sitio y la plantilla de análisis posterior al incidente.
- **Dónde:** `vectra-risk/platform/runbooks/`.
- **P:** ¿Cómo se reproduce todo desde cero? **R:** Siguiendo `vectra-risk/platform/runbooks/install.md`.

### SLO y tasa de consumo
- **Qué es:** objetivo de nivel de servicio; la tasa de consumo mide qué tan rápido se gasta el margen de error.
- **En Vectra:** 99,5 % para la ruta de recomendación [INTERNO], con dos alertas: consumo rápido y consumo lento.
- **Dónde:** `vectra-risk/platform/observability/rules/platform-rules.yaml`; runbooks `vectra-risk/platform/runbooks/recommendation-slo-burn-fast.md` y `vectra-risk/platform/runbooks/recommendation-slo-burn-slow.md`.
- **P:** ¿Mediste la latencia? **R:** No con carga: las pruebas de carga están diferidas.

---

## 11. Aplicación: servicios en Python

### Python
- **Qué es:** lenguaje de programación.
- **En Vectra:** todos los servicios, las herramientas y el servidor MCP.
- **Dónde:** `vectra-risk/pyproject.toml`.
- **Versión:** 3.12 (`requires-python` en `vectra-risk/pyproject.toml`).
- **P:** ¿Dónde está decidido el lenguaje? **R:** En el `tech-stack-decisions.md` de cada unidad, por ejemplo `vectra-risk/aidlc-docs/construction/contracts/nfr-requirements/tech-stack-decisions.md`.

### uv
- **Qué es:** gestor de paquetes y entornos de Python.
- **En Vectra:** un solo espacio de trabajo con 17 paquetes y un único archivo de bloqueo.
- **Dónde:** `vectra-risk/pyproject.toml`, `vectra-risk/uv.lock`.
- **P:** ¿Cómo garantizas dependencias reproducibles? **R:** Versiones exactas en cada `pyproject.toml` y `uv.lock` en Git; el servidor MCP arranca con `uv run --frozen`.
- **Ojo:** la versión de uv en sí no está fijada.

### FastAPI
- **Qué es:** *framework* web asíncrono de Python.
- **En Vectra:** todos los servicios HTTP, creados siempre con la fábrica común `create_app`, que pone autenticación, errores, logs y métricas.
- **Dónde:** `vectra-risk/contracts/python/vectra_common/src/vectra_common/app_factory.py`.
- **Versión:** 0.162.0 (`vectra-risk/uv.lock`).
- **P:** ¿Todos los servicios son FastAPI? **R:** Todos menos `product-metrics`, que es un proceso `asyncio` sin API.

### Uvicorn
- **Qué es:** servidor ASGI para aplicaciones asíncronas de Python.
- **En Vectra:** sirve la API en el puerto 8080 y la operación (`/metrics`, `/healthz`, `/readyz`) en el 8081.
- **Dónde:** `vectra-risk/contracts/python/vectra_common/src/vectra_common/ops_server.py`.
- **Versión:** 0.37.0 (`vectra-risk/uv.lock`).
- **P:** ¿Por qué dos puertos? **R:** Separa la API de la operación: Prometheus raspa el 8081 y el gateway solo publica el 8080.

### Pydantic
- **Qué es:** librería de validación de datos con tipos.
- **En Vectra:** fuente de verdad del contrato: modelos estrictos que rechazan campos de más; de ellos se genera el OpenAPI.
- **Dónde:** `vectra-risk/contracts/python/vectra_contracts/`.
- **Versión:** 2.14.2 (`vectra-risk/uv.lock`).
- **P:** ¿Dónde vive la regla «sin explicación no hay recomendación»? **R:** En el constructor de `Recommendation` del contrato, que no deja crear una con versiones distintas.

### OpenAPI
- **Qué es:** formato estándar para describir una API HTTP.
- **En Vectra:** ocho especificaciones, generadas desde Pydantic; de ellas salen los tipos de TypeScript de la consola.
- **Dónde:** `vectra-risk/contracts/openapi/`, generador en `vectra-risk/contracts/tools/codegen.py`.
- **Versión:** OpenAPI 3.1.0.
- **P:** ¿Cómo evitas romper a un consumidor? **R:** La integración continua compara contra la última etiqueta del contrato y exige subir la versión mayor si el cambio rompe.

### Catálogo de enumerados
- **Qué es:** archivo único con las listas cerradas del dominio.
- **En Vectra:** causas de fail-closed, estados de caso, roles, permisos, tipos de entrada y campos de log; se exporta a TypeScript.
- **Dónde:** `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/catalog.py`.
- **P:** ¿Cómo añades una causa de fail-closed? **R:** En el catálogo; el módulo no carga si le falta la categoría.

### Problem Details
- **Qué es:** formato estándar de errores HTTP en JSON (RFC 9457).
- **En Vectra:** todos los errores usan el modelo `Problem`, con código cerrado e identificador de correlación, sin trazas de pila.
- **Dónde:** `ProblemCode` en `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/catalog.py`.
- **P:** ¿Un fail-closed es un error HTTP? **R:** No: viaja como respuesta 200 de tipo `FailClosed`; los errores son otra cosa.

### psycopg y Alembic
- **Qué es:** controlador de PostgreSQL para Python y herramienta de migraciones de esquema.
- **En Vectra:** SQL explícito, sin ORM; las migraciones corren en un Job antes del servicio.
- **Dónde:** `vectra-risk/decision-registry/migrations/`, `vectra-risk/case-management/migrations/`, `vectra-risk/governance/migrations/`.
- **Versión:** psycopg 3.3.8 y Alembic 1.20.1 (`vectra-risk/uv.lock`).
- **P:** ¿Por qué sin ORM? **R:** Para controlar cada consulta y los permisos por rol de base de datos.

### httpx y cortacircuitos
- **Qué es:** cliente HTTP asíncrono; un cortacircuitos deja de llamar a una dependencia que falla.
- **En Vectra:** las llamadas entre servicios pasan por un único módulo que obliga a poner tiempo de espera, propaga el plazo restante y tiene cortacircuitos por dependencia.
- **Dónde:** `vectra-risk/contracts/python/vectra_common/src/vectra_common/deps.py`; tiempos en `vectra-risk/scoring-explainability/scoring/src/scoring/config.py`.
- **Versión:** httpx 0.28.1 (`vectra-risk/uv.lock`).
- **P:** ¿Qué pasa si la explicación tarda? **R:** A los 800 ms el scoring corta y devuelve el fail-closed `timeout`; nunca un puntaje sin explicación.

### pytest
- **Qué es:** *framework* de pruebas de Python.
- **En Vectra:** pruebas unitarias, de integración y de propiedades de todas las unidades; cada unidad tiene `make check`.
- **Dónde:** carpetas `tests/` de cada unidad, por ejemplo `vectra-risk/contracts/tests/`.
- **Versión:** 9.0.3 (`vectra-risk/uv.lock`).
- **P:** ¿Qué cobertura exiges? **R:** De ramas: 95 % en contratos, registro, gobierno, sesgo y scoring; 100 % en los módulos críticos del contrato.

### Hypothesis y pruebas basadas en propiedades
- **Qué es:** en vez de ejemplos fijos, se enuncia una propiedad que debe cumplirse siempre y la librería genera cientos de casos y reduce el que falla al mínimo.
- **En Vectra:** propiedades del dominio: nunca hay recomendación sin explicación sincronizada ni sin entrada en el registro; la cadena del registro siempre verifica; la disparidad coincide con Fairlearn; cambiar solo el texto libre no cambia la recomendación.
- **Dónde:** carpetas `tests/property/`, por ejemplo `vectra-risk/scoring-explainability/tests/property/` y `vectra-risk/bias-monitoring/tests/property/test_disparity.py`.
- **Versión:** Hypothesis 6.170.14 (`vectra-risk/uv.lock`); en TypeScript, fast-check 4.10.2 (`vectra-risk/console/spa/package.json`).
- **P:** ¿Cómo reproduces un fallo? **R:** La integración continua registra la semilla de cada corrida.

### Pruebas de mutación
- **Qué es:** se introducen errores pequeños en el código y se comprueba que alguna prueba falle.
- **En Vectra:** automáticas con mutmut solo en U0; en las demás unidades están diferidas. Aparte, el revisor del loop aplica mutaciones a mano para demostrar que una prueba no detecta un error.
- **Dónde:** `vectra-risk/contracts/tools/mutation.py`; un ejemplo manual en `vectra-risk/revisiones/U01-T03/`.
- **Versión:** mutmut 3.8.1 (`vectra-risk/uv.lock`).
- **P:** ¿Usan pruebas de mutación? **R:** Automáticas, solo en contratos; manuales, en las revisiones.

### Testcontainers
- **Qué es:** librería que levanta contenedores reales durante una prueba.
- **En Vectra:** PostgreSQL real para probar migraciones, permisos y disparadores sin clúster.
- **Dónde:** `vectra-risk/decision-registry/tests/integration/`.
- **Versión:** 4.14.2 (`vectra-risk/uv.lock`).
- **P:** ¿Las pruebas del registro usan una base simulada? **R:** No: un PostgreSQL real en contenedor.

### Ruff, mypy e import-linter
- **Qué es:** analizador de estilo, verificador de tipos y verificador de dependencias entre módulos.
- **En Vectra:** mypy en modo estricto; import-linter obliga, por ejemplo, a que httpx solo se use en el módulo de dependencias.
- **Dónde:** `vectra-risk/pyproject.toml`, `vectra-risk/contracts/.importlinter`.
- **Versión:** ruff 0.17.3, mypy 2.4.1, import-linter 2.15 (`vectra-risk/uv.lock`).
- **P:** ¿Cómo evitas que el validador de factualidad copie al generador? **R:** Una regla de importación le prohíbe importarlo.

### Frases prohibidas
- **Qué es:** verificador propio que busca frases que el producto no puede decir.
- **En Vectra:** 17 frases que prometerían ausencia de sesgo o de discriminación; se aplica a textos, plantillas, tableros y documentos.
- **Dónde:** `vectra-risk/contracts/forbidden-phrases.yaml`, `vectra-risk/contracts/tools/forbidden_phrases.py`.
- **P:** ¿Quién puede cambiar la lista? **R:** Exige revisión de propietarios de código; el archivo está en `.github/CODEOWNERS`.

---

## 12. Aplicación: la consola

### SPA y BFF
- **Qué es:** *Single Page Application* (aplicación de una sola página) y *Backend for Frontend* (servidor a la medida de esa interfaz).
- **En Vectra:** la consola es una SPA con vistas por rol; habla solo con `console-bff`, que compone las llamadas a los servicios y aplica rol, segundo factor y regla de objeto.
- **Dónde:** `vectra-risk/console/spa/`, `vectra-risk/console/bff/`.
- **P:** ¿El BFF guarda sesión? **R:** No: no tiene estado ni cookies; la SPA envía el token en cada petición.

### React
- **Qué es:** librería para construir interfaces.
- **En Vectra:** la consola.
- **Dónde:** `vectra-risk/console/spa/src/`.
- **Versión:** 19.3.1 (`vectra-risk/console/spa/package.json`).
- **Ojo:** el `tech-stack-decisions.md` de la consola dice React 18; el paquete fija 19.3.1.
- **P:** ¿Qué versión de React? **R:** 19.3.1, según `package.json`.

### Vite
- **Qué es:** herramienta de construcción y servidor de desarrollo para web.
- **En Vectra:** compila la SPA a archivos estáticos.
- **Dónde:** `vectra-risk/console/spa/vite.config.ts`.
- **Versión:** 8.3.8 (`vectra-risk/console/spa/package.json`).
- **P:** ¿Quién sirve los archivos en el clúster? **R:** nginx sin privilegios, con sistema de archivos de solo lectura (`vectra-risk/console/spa/nginx.conf`).

### TypeScript
- **Qué es:** JavaScript con tipos.
- **En Vectra:** todo el código de la consola; los tipos de la API se generan del OpenAPI.
- **Dónde:** `vectra-risk/console/spa/tsconfig.json`, `vectra-risk/contracts/ts/`.
- **Versión:** 5.9.3 (`vectra-risk/console/spa/package.json`).
- **P:** ¿Cómo sabe la consola la forma de una respuesta? **R:** Por tipos generados del mismo contrato que usan los servicios.

### React Aria
- **Qué es:** componentes de interfaz accesibles y sin estilos, de Adobe.
- **En Vectra:** base de los controles de la consola, por accesibilidad.
- **Dónde:** `vectra-risk/console/spa/package.json`.
- **Versión:** `react-aria-components` 1.22.1.
- **P:** ¿Qué nivel de accesibilidad buscas? **R:** WCAG 2.1 AA.

### Catálogos de textos (i18n)
- **Qué es:** internacionalización: los textos viven fuera del código.
- **En Vectra:** catálogos en español e inglés, sin librería externa; el idioma elegido viaja a Keycloak.
- **Dónde:** `vectra-risk/console/spa/src/i18n/labels.es.json`, `vectra-risk/console/spa/src/i18n/messages.es.json` y sus pares `labels.en.json` y `messages.en.json`.
- **P:** ¿Cómo se llama en inglés «Se aparta de la recomendación»? **R:** *Overrides the recommendation*, en `labels.en.json`.

### Selector de idioma
- **Qué es:** control de la consola para elegir español o inglés.
- **En Vectra:** orden inicial: preferencia guardada, idioma del perfil, idioma del navegador y, por último, español. La elección se guarda en el almacenamiento local del navegador, en una clave con un valor de una lista cerrada.
- **Dónde:** `vectra-risk/console/spa/src/i18n/language.ts`, `vectra-risk/console/spa/src/preferences/storage.ts`.
- **P:** ¿No estaba prohibido el almacenamiento local? **R:** Para tokens y datos de sesión, sí: siguen en memoria. Idioma y tema son la única excepción, acotada a un módulo y a dos claves que no son datos personales.

### ui_locales
- **Qué es:** parámetro estándar de OIDC con el que el cliente dice en qué idioma quiere las pantallas del proveedor de identidad.
- **En Vectra:** la consola envía el idioma elegido (`es` o `en`, nunca texto libre) en cada redirección a Keycloak, y el inicio de sesión sale en ese idioma.
- **Dónde:** `vectra-risk/console/spa/src/auth/AuthProvider.tsx`.
- **P:** ¿Cómo sabe Keycloak el idioma de la consola? **R:** Por `ui_locales` en la petición de autorización.

### Selector de tema
- **Qué es:** control de la consola para elegir tema del sistema, claro u oscuro.
- **En Vectra:** una sola paleta: cada color lleva su valor claro y su valor oscuro con la función `light-dark()` de CSS, y el atributo `data-theme` de la página decide. Un guion del mismo origen aplica el tema antes de la primera pintura.
- **Dónde:** `vectra-risk/console/spa/src/styles.css`, `vectra-risk/console/spa/public/theme-boot.js`, `vectra-risk/console/spa/src/theme/`.
- **P:** ¿Por qué un archivo aparte y no un guion en línea? **R:** Porque la CSP solo admite guiones del mismo origen (`script-src 'self'`); uno en línea quedaría bloqueado.

### Playwright
- **Qué es:** herramienta que maneja navegadores reales para pruebas de extremo a extremo.
- **En Vectra:** prueba inicio de sesión, vistas por rol, decisión, step-up, cierre por inactividad y que el texto libre con código se muestre como texto; en Chromium y Firefox.
- **Dónde:** `vectra-risk/console/spa/tests/e2e/`, `vectra-risk/console/spa/playwright.config.ts`.
- **Versión:** `@playwright/test` 1.64.0 (`vectra-risk/console/spa/package.json`).
- **P:** ¿Corren contra el clúster? **R:** No: contra un emisor OIDC de prueba y el BFF con dobles.

### axe
- **Qué es:** motor de comprobación automática de accesibilidad.
- **En Vectra:** cero hallazgos graves o críticos en cada parada, con los cuatro roles, los dos navegadores y los dos temas.
- **Dónde:** `vectra-risk/console/spa/tests/a11y/`.
- **Versión:** `@axe-core/playwright` 4.14.0 (`vectra-risk/console/spa/package.json`).
- **P:** ¿axe garantiza accesibilidad? **R:** No: detecta una parte; la revisión manual con lector de pantalla está diferida.

---

## 13. Cadena de suministro e integración continua

### Digest de imagen
- **Qué es:** hash del contenido de una imagen (`@sha256:…`); a diferencia de una etiqueta, no puede apuntar a otra cosa mañana.
- **En Vectra:** todas las imágenes se referencian por digest, en los Dockerfile y en los manifiestos; el digest desplegado cambia por PR.
- **Dónde:** `vectra-risk/platform/policies/kyverno/disallow-latest.yaml`, `vectra-risk/platform/resolve_digest.py`, `vectra-risk/vectra-risk-gitops/values/kind/`.
- **P:** ¿Qué impide usar `latest`? **R:** Kyverno en el clúster y `forbidden_steps.py` en la integración continua.

### Registro local
- **Qué es:** registro de imágenes que corre en un contenedor junto a kind.
- **En Vectra:** `kind-registry`, publicado en `127.0.0.1:5001`; dentro del clúster hace de espejo del registro del banco.
- **Dónde:** `vectra-risk/platform/kind/registry.md`, `vectra-risk/platform/kind/certs.d/`.
- **Versión:** imagen `registry:3.0.0` por digest (`vectra-risk/platform/runbooks/install.md`).
- **P:** ¿De qué registros acepta imágenes el clúster? **R:** Solo de los de `restrict-registries`: el interno, el del banco y el local de kind.

### Trivy
- **Qué es:** escáner de vulnerabilidades, malas configuraciones y secretos.
- **En Vectra:** escanea el árbol del repositorio en cada PR y bloquea con hallazgos críticos o altos.
- **Dónde:** `.github/workflows/supply-chain.yml`.
- **Versión:** v0.76.1 (ese flujo de trabajo).
- **P:** ¿Escaneas las imágenes? **R:** No: se escanea el repositorio; el escaneo por imagen está diferido.

### SBOM
- **Qué es:** *Software Bill of Materials*: inventario de componentes de un software.
- **En Vectra:** la integración continua genera uno del repositorio en formato SPDX.
- **Dónde:** `.github/workflows/supply-chain.yml`, `.github/workflows/evidence.yml`.
- **P:** ¿Cada imagen tiene su SBOM? **R:** No: está diferido para la demo.
- **Ojo:** es el punto T1 de `vectra-risk/aidlc-docs/construction/plans/demo-kind-alcance.md`.

### Firma de imágenes (Cosign)
- **Qué es:** firma criptográfica de una imagen para comprobar quién la construyó.
- **En Vectra:** existe el flujo de trabajo para firmar por digest con llave propia y la política que verificaría la firma.
- **Dónde:** `.github/workflows/sign-image.yml`, `vectra-risk/platform/policies/kyverno/verify-images.yaml`.
- **P:** ¿Las imágenes están firmadas? **R:** No: ningún flujo llama al de firma, y `verify-images` no se instala en kind y tiene una llave de relleno.

### GitHub Actions
- **Qué es:** integración continua de GitHub.
- **En Vectra:** ocho flujos de trabajo; dos orquestan (`contracts.yml` y `platform.yml`) y seis son reutilizables.
- **Dónde:** `.github/workflows/`.
- **P:** ¿La integración continua despliega? **R:** No: solo comprueba; un flujo falla si otro intenta aplicar algo a un clúster.
- **Ojo:** las pruebas de los servicios no corren en ningún flujo: solo las de contratos, plataforma y servidor MCP. Las demás corren con `make check` en cada tarea.

### Pasos prohibidos
- **Qué es:** comprobación propia de que ningún flujo de trabajo cambia un clúster.
- **En Vectra:** rechaza `kubectl apply`, `helm install`, `argocd app sync`, acciones de despliegue y secretos con forma de kubeconfig; también Dockerfiles con `latest`.
- **Dónde:** `.github/workflows/forbidden-steps.yml`, `vectra-risk/platform/tests/forbidden_steps.py`.
- **P:** ¿Qué sí se permite? **R:** `kubectl diff` y `helm template`: ver sin cambiar.

### Evidencia del PR
- **Qué es:** flujo que adjunta a cada PR de infraestructura lo que va a cambiar.
- **En Vectra:** render de Helm, `kubectl diff` contra un kind efímero de solo lectura, pruebas con su semilla, informe de Trivy y SBOM.
- **Dónde:** `.github/workflows/evidence.yml`.
- **P:** ¿Dónde termina el trabajo del agente? **R:** En un PR con esa evidencia, la bitácora y las rondas de revisión.

### Protección de rama
- **Qué es:** reglas de GitHub que impiden fusionar sin cumplir condiciones.
- **En Vectra:** `main` exige las comprobaciones de la integración continua y la revisión de un propietario de código.
- **Dónde:** documentada en `vectra-risk/aidlc-docs/construction/plans/platform-foundation-code-generation-plan.md`.
- **P:** ¿Puede el agente fusionar? **R:** No lo hace: fusiona una persona.
- **Ojo:** la regla no aplica a administradores, porque un único dueño no puede aprobar su propio PR. Algunos PR se fusionaron antes de que su revisor terminara (`vectra-risk/DECISIONES-LOOP.md`, §11).

### CODEOWNERS
- **Qué es:** archivo de GitHub que asigna revisores obligatorios por ruta.
- **En Vectra:** protege la lista de frases prohibidas, la carpeta de GitOps, las políticas, la evidencia y los archivos con el umbral de sesgo y el piso de la métrica de ruido.
- **Dónde:** `.github/CODEOWNERS`.
- **P:** ¿Quién puede cambiar el umbral de 5 puntos? **R:** Nadie sin la revisión de un propietario de código.
- **Ojo:** los propietarios son dos personas que hacen de los equipos del banco, que no existen.

### rollback-note
- **Qué es:** comprobación propia que exige una sección «Rollback» con texto en el PR.
- **En Vectra:** trabajo del flujo `platform.yml`; falla si la sección está vacía.
- **Dónde:** `vectra-risk/platform/tests/rollback_note.py`, `.github/pull_request_template.md`.
- **P:** ¿Cómo se revierte un cambio? **R:** Revirtiendo el commit en Git y sincronizando a mano; el PR debe decirlo.

---

## 14. Loop de agentes

### Agente
- **Qué es:** modelo de lenguaje que trabaja en bucle: recibe un objetivo, usa herramientas, observa el resultado y decide el siguiente paso.
- **En Vectra:** los agentes construyen el proyecto; no forman parte del producto. El producto no llama a ningún LLM.
- **Dónde:** `vectra-risk/loop/README.md`, `.claude/agents/`.
- **P:** ¿Vectra usa un LLM para explicar? **R:** No: la narrativa es una plantilla determinista. Los agentes están en el proceso de desarrollo.
- **Ojo:** no hay ningún agente desplegado dentro del clúster.

### Claude Code
- **Qué es:** herramienta de línea de órdenes de Anthropic para trabajar con agentes sobre un repositorio.
- **En Vectra:** entorno donde corren el orquestador y sus subagentes.
- **Dónde:** `.claude/`, `.mcp.json`.
- **P:** ¿Qué es tuyo y qué es de Claude Code? **R:** De Claude Code, el motor; del proyecto, los contratos de cada papel, los permisos, el servidor MCP, las tareas y la evidencia.

### Loop de agentes
- **Qué es:** el ciclo despachar, implementar, revisar y arbitrar que se repite hasta un veredicto VERDE.
- **En Vectra:** cuatro papeles sellados: el orquestador despacha y arbitra, el codificador implementa, el revisor juzga y una persona fusiona.
- **Dónde:** `vectra-risk/loop/orquestador.md`, `.claude/agents/codificador.md`, `.claude/agents/revisor.md`.
- **P:** ¿Cuándo se detiene? **R:** Con un VERDE abre el PR; si una tarea llega a 4 rondas se detiene y la lleva a la persona; no despacha con más de 5 PR en espera.

### Orquestador
- **Qué es:** la sesión principal del loop.
- **En Vectra:** resuelve qué tareas se pueden despachar, despacha hasta 3 codificadores en paralelo, guarda cada informe del revisor tal cual, arbitra y abre el PR. No escribe código ni juzga.
- **Dónde:** `vectra-risk/loop/orquestador.md`.
- **P:** ¿Por qué no programa él mismo? **R:** Porque quien escribe y además aprueba es un modelo aprobándose a sí mismo.

### Codificador
- **Qué es:** subagente que implementa una tarea.
- **En Vectra:** trabaja en su propio worktree, desde el archivo de la tarea; reproduce el fallo antes de arreglarlo y deja la evidencia en su bitácora. Herramientas: `Bash, Read, Edit, Write, Grep, Glob`. Modelo: `sonnet`.
- **Dónde:** `.claude/agents/codificador.md`.
- **P:** ¿Tiene acceso al clúster? **R:** No tiene las herramientas MCP, y las órdenes de escritura están denegadas.

### Revisor
- **Qué es:** subagente que juzga el trabajo del codificador, sin poder editarlo.
- **En Vectra:** corre él mismo cada criterio de aceptación, exige evidencia fresca y emite hallazgos con severidad y un veredicto. Herramientas: `Bash, Read, Grep, Glob` y las seis lecturas MCP. Modelo: `opus`.
- **Dónde:** `.claude/agents/revisor.md`.
- **P:** ¿Cómo verifica? **R:** Corriendo, no leyendo; para cambios de estado exige leer el estado de vuelta, no un código de salida.

### Subagente
- **Qué es:** agente lanzado por otro, con contexto propio y una lista de herramientas propia.
- **En Vectra:** codificador y revisor son subagentes del orquestador; reciben rutas, nunca contenido pegado.
- **Dónde:** campo `tools:` de `.claude/agents/codificador.md` y `.claude/agents/revisor.md`.
- **P:** ¿Corren en máquinas separadas? **R:** No: en una sola sesión, con contexto separado.

### Tarea
- **Qué es:** archivo que describe un trabajo para un codificador.
- **En Vectra:** alcance dentro y fuera, archivos de contexto por ruta y criterios de aceptación, cada uno con su comando.
- **Dónde:** `vectra-risk/tareas/`, plantilla en `vectra-risk/loop/plantilla-tarea.md`.
- **P:** ¿Qué recibe el agente en cada vuelta? **R:** La ruta de la tarea con su hash de Git, su worktree y, en retrabajo, el informe anterior y su bitácora.

### Criterio de aceptación
- **Qué es:** condición que la tarea debe cumplir, escrita como un comando con su salida esperada.
- **En Vectra:** regla AUTONOMIA-02: un criterio sin comando deja la tarea sin despachar.
- **Dónde:** `vectra-risk/loop/plantilla-tarea.md`.
- **P:** ¿Quién decide que la tarea está bien? **R:** Los comandos, corridos por el revisor; no una opinión.

### Ronda
- **Qué es:** una vuelta completa: el codificador implementa y el revisor emite veredicto.
- **En Vectra:** cada ronda queda guardada sin resumir.
- **Dónde:** `vectra-risk/revisiones/`.
- **P:** ¿Cuántas rondas por tarea? **R:** El contrato para en 4; para la demo se acordaron 2 como máximo, con solo ROJO bloqueante (reglas RL-1 a RL-5).

### Veredicto
- **Qué es:** la última línea del informe del revisor: `VERDE` o `NO-VERDE`.
- **En Vectra:** VERDE significa que el revisor corrió todos los criterios, todos pasan y no queda ningún ROJO ni NARANJA. Cualquier otra cosa es NO-VERDE.
- **Dónde:** `.claude/agents/revisor.md`.
- **P:** ¿Puede el orquestador cambiar un veredicto? **R:** No: puede arbitrar un hallazgo con argumentos, pero no suavizar el veredicto.

### Severidades ROJO, NARANJA y AMARILLO
- **Qué es:** escala de los hallazgos del revisor.
- **En Vectra:** ROJO: un criterio no se cumple, la evidencia es falsa o hay trabajo fuera de alcance. NARANJA: defecto real que no rompe un criterio. AMARILLO: mejora que no bloquea.
- **Dónde:** `.claude/agents/revisor.md`.
- **P:** ¿Qué bloquea? **R:** En el contrato, ROJO y NARANJA; con las reglas de ritmo de la demo, solo ROJO.

### Bitácora
- **Qué es:** registro del codificador: acuse de lectura, comandos, salidas y respuesta a cada hallazgo.
- **En Vectra:** una por tarea; va adjunta al PR.
- **Dónde:** `vectra-risk/bitacoras/`.
- **P:** ¿Para qué el acuse de lectura? **R:** Para comprobar el hash de la tarea y reescribir el alcance antes de programar; si el hash no coincide, el codificador se detiene.

### Candidata
- **Qué es:** trabajo real que aparece y queda fuera del alcance de la tarea en curso.
- **En Vectra:** se anota y no se hace; así el alcance no crece solo.
- **Dónde:** `vectra-risk/CANDIDATAS.md`.
- **P:** ¿Qué hace el agente si ve algo roto fuera de su tarea? **R:** No lo toca: lo propone como candidata.

### Empuje de vuelta y arbitraje
- **Qué es:** el codificador rechaza un hallazgo con una prueba o por estar fuera de alcance, y el orquestador decide.
- **En Vectra:** las decisiones quedan escritas.
- **Dónde:** `vectra-risk/DECISIONES-LOOP.md`.
- **P:** Dame un caso en que el agente fue frenado. **R:** En `U01-T04` la prueba destapó un defecto en un archivo fuera de alcance; el codificador no lo tocó, dejó la prueba en rojo y pidió decisión.

### Worktree
- **Qué es:** copia de trabajo adicional de Git, en otra carpeta y otra rama, sobre el mismo repositorio.
- **En Vectra:** uno por codificador; nunca dos en el mismo.
- **Dónde:** `.claude/agents/codificador.md` (regla 1).
- **P:** ¿Cómo trabajan tres agentes a la vez sin pisarse? **R:** Cada uno en su worktree y en tareas que no comparten archivos.

### settings.json
- **Qué es:** archivo de configuración de Claude Code del proyecto; su bloque `permissions` gobierna qué herramientas y órdenes puede usar una sesión.
- **En Vectra:** versionado en Git, así que cambiarlo exige un PR; vale para el orquestador y para cada worktree de codificador o revisor.
- **Dónde:** `.claude/settings.json`.
- **P:** ¿Dónde están los límites del agente? **R:** En cuatro sitios: este archivo, el `tools:` de cada agente, lo que el servidor MCP registra y el RBAC del clúster.

### Reglas allow, deny y ask
- **Qué es:** las tres listas de `permissions`: `allow` (usar sin preguntar), `deny` (prohibir siempre) y `ask` (preguntar a la persona cada vez).
- **En Vectra:** `allow` nombra las seis herramientas MCP, una por una y sin comodines. `deny` tiene 32 patrones: las escrituras de `kubectl` (`apply`, `create`, `delete`, `patch`, `edit`, `replace`, `scale`, `rollout`, `annotate`, `label`, en dos formas cada una), `helm install`, `upgrade` y `uninstall`, `argocd app sync` y `delete`, `docker start`, `stop`, `restart`, `rm` y `kill`, y `kind create` y `delete`.
- **Dónde:** `.claude/settings.json`; decisión en `vectra-risk/DECISIONES-LOOP.md` (§11).
- **P:** ¿Por qué `deny` y no una instrucción? **R:** Porque en la prueba de cambio de modelo los dos modelos ignoraron la instrucción; una regla de configuración no depende del modelo.
- **Ojo:** tres límites honestos. Uno: `allow` no restringe, solo evita la pregunta para esas seis; lo que restringe es el `tools:` de cada agente y lo que el servidor registra. Dos: no hay ninguna regla sobre `gh`; que el agente no fusione descansa en su contrato y en la protección de rama. Tres: el archivo confirmado no usa `ask`; el dueño del proyecto, para operar el clúster de kind, pasó en su copia local los 32 patrones de `deny` a `ask` y aprobó orden por orden. Los worktrees de codificadores y revisores conservan `deny`.

### MCP (Model Context Protocol)
- **Qué es:** protocolo abierto para que un agente use herramientas externas a través de un servidor.
- **En Vectra:** da al loop lecturas acotadas del clúster.
- **Dónde:** `.mcp.json`, `vectra-risk/loop/mcp-solo-lectura/`.
- **Versión:** SDK `mcp` 2.3.0 (`vectra-risk/loop/mcp-solo-lectura/README.md`).
- **P:** ¿Qué puede hacer tu agente por MCP? **R:** Seis lecturas y ninguna escritura.
- **Ojo:** el servidor se añadió después de las primeras olas del loop: las tareas `U01-T01` a `U01-T06` se hicieron solo con las herramientas nativas de Claude Code.

### Servidor MCP
- **Qué es:** proceso que ofrece herramientas a un agente por MCP.
- **En Vectra:** `vectra-lectura`, que Claude Code arranca con `uv run --frozen --project vectra-risk vectra-mcp-lectura`.
- **Dónde:** `.mcp.json`, `vectra-risk/loop/mcp-solo-lectura/src/vectra_mcp_readonly/server.py`.
- **P:** ¿Qué pasa si el clúster está apagado? **R:** El servidor no arranca: no puede confirmar su identidad.

### Herramienta MCP
- **Qué es:** función con nombre y argumentos tipados que el servidor ofrece al agente.
- **En Vectra:** cada una es una lectura fija de un recurso fijo; no hay ninguna que reciba una orden libre.
- **Dónde:** `vectra-risk/loop/mcp-solo-lectura/src/vectra_mcp_readonly/tools.py`.
- **P:** ¿Por qué no una herramienta genérica de `kubectl get`? **R:** Porque una orden libre no se puede poner en una lista de permitidos.

### Allowlist
- **Qué es:** lista de lo permitido; lo que no está, no se puede.
- **En Vectra:** las seis herramientas, declaradas en cuatro sitios que una prueba obliga a coincidir: el servidor, `permissions.allow`, el `tools:` del revisor y la tabla del README.
- **Dónde:** `vectra-risk/loop/mcp-solo-lectura/tests/test_allowlist.py`.
- **P:** ¿Cómo añades una herramienta? **R:** Cambiando los cuatro sitios en un PR; la prueba falla si no coinciden.

### stdio
- **Qué es:** transporte de MCP por entrada y salida estándar: el servidor es un proceso hijo del cliente.
- **En Vectra:** único transporte; el servidor no escucha en ningún puerto.
- **Dónde:** `"type": "stdio"` en `.mcp.json`.
- **P:** ¿Alguien más puede conectarse a ese servidor? **R:** No: no hay puerto.

### Servidor vectra-lectura
- **Qué es:** el servidor MCP de solo lectura del proyecto.
- **En Vectra:** corre con la identidad `vectra-readonly-agent` y tiene seis capas de freno: el servidor, la validación de argumentos, un único punto que llama a `kubectl` con verbos literales, la comprobación de identidad al arrancar, el RBAC del clúster y los permisos de Claude Code.
- **Dónde:** `vectra-risk/loop/mcp-solo-lectura/README.md`; evidencia en `vectra-risk/aidlc-docs/construction/system-verification/evidence/sustentacion/mcp/`.
- **P:** ¿Qué no puede hacer? **R:** Escribir, entrar a un pod, leer un `Secret` ni leer logs de pods.
- **Ojo:** los logs quedan fuera a propósito: pueden traer datos de solicitantes.

### Las seis herramientas de vectra-lectura
- **Qué es:** la lista completa de lo que el agente puede leer del clúster.
- **En Vectra:** `argo_applications` (sincronización y salud de cada Application), `pods` (fase, reinicios y motivo de espera), `events` (eventos de un namespace), `inference_services` (si cada modelo servido está listo), `workloads` (réplicas deseadas y listas) y `permissions` (lo que la propia cuenta puede hacer).
- **Dónde:** `vectra-risk/loop/mcp-solo-lectura/README.md`; demostración en `vectra-risk/loop/mcp-solo-lectura/demo_cliente.py`.
- **P:** ¿Cuál enseñarías primero? **R:** `permissions`: muestra que la cuenta responde «no» a crear, borrar, parchear, leer secretos y entrar a pods.

### Kubeconfig de solo lectura
- **Qué es:** archivo de credenciales con un único contexto y el token de la cuenta de solo lectura.
- **En Vectra:** los agentes corren con él; el de administrador lo usa solo el operador.
- **Dónde:** `vectra-risk/platform/kind/readonly-kubeconfig.sh`, `vectra-risk/platform/kind/readonly-kubeconfig.md`.
- **P:** ¿Y si el agente usa otro kubeconfig? **R:** El servidor MCP no lee la variable `KUBECONFIG` y se niega a arrancar con otra identidad; para la línea de órdenes están las reglas `deny`.
- **Ojo:** el documento declara lo que no cubre: `argocd`, `docker` y quien fije `KUBECONFIG` por su cuenta.

### Prueba de cambio de modelo
- **Qué es:** cambiar el modelo de cada papel tocando solo configuración y repetir los mismos casos.
- **En Vectra:** 10 casos con dos configuraciones: A (codificador `sonnet`, revisor `opus`) y B (`haiku`, `sonnet`). Solo cambia el campo `model:` de cada agente. Resultado: A cumple 8 de 10 y B 7 de 10.
- **Dónde:** `vectra-risk/loop/cambio-de-modelo/README.md`.
- **P:** ¿Qué aprendiste? **R:** Que el sistema funciona con otro modelo y detecta la caída de calidad, y que los límites dados por instrucción fallaron con los dos.
- **Ojo:** en el caso 9 un codificador ejecutó `kubectl apply` y el otro encendió los nodos. De ahí salieron las reglas `deny` y la cuenta de solo lectura.

### Arnés y oráculo
- **Qué es:** guion que mide un resultado sin que lo juzgue un modelo; el oráculo es la respuesta contra la que se compara.
- **En Vectra:** `arnes.sh` mide dos niveles: que pasen los criterios de la tarea y que la implementación pase además las pruebas finales de su PR.
- **Dónde:** `vectra-risk/loop/cambio-de-modelo/arnes.sh`.
- **P:** ¿Quién califica la prueba de cambio de modelo? **R:** Un guion, no un LLM.

### Herramienta de verificación (U12)
- **Qué es:** programa `vectra-verification`, que comprueba el sistema de punta a punta y escribe un informe con evidencia.
- **En Vectra:** corre como contenedor en la máquina del operador, fuera del clúster y solo con lecturas; los cambios que piden las demos los hace una persona por PR.
- **Dónde:** `vectra-risk/system-verification/`, guía en `vectra-risk/system-verification/docs/paso-18-kind.md`.
- **P:** ¿Qué significa «no ejecutado»? **R:** Que no hay evidencia: nunca se cuenta como «pasa».
- **Ojo:** la guía declara que solo se ha ejecutado en parte en kind y que los tiempos de las demos son cifras de los guiones.

---

<!-- INDICE-ALFABETICO -->
## Índice alfabético

- [acr](#acr)
- [Agente](#agente)
- [AI-DLC](#ai-dlc)
- [Alertmanager](#alertmanager)
- [Allowlist](#allowlist)
- [amr](#amr)
- [Aplicación raíz](#aplicación-raíz)
- [Application](#application)
- [AppProject](#appproject)
- [Argo CD](#argo-cd)
- [Arnés y oráculo](#arnés-y-oráculo)
- [AuthorizationPolicy](#authorizationpolicy)
- [Auto-sync desactivado](#auto-sync-desactivado)
- [AUTONOMIA-01](#autonomia-01)
- [axe](#axe)
- [Bitácora](#bitácora)
- [Bloqueo de objetos (WORM)](#bloqueo-de-objetos-worm)
- [CA interna](#ca-interna)
- [Calico](#calico)
- [Candidata](#candidata)
- [Catálogo de enumerados](#catálogo-de-enumerados)
- [Catálogos de textos (i18n)](#catálogos-de-textos-i18n)
- [cert-manager](#cert-manager)
- [Chart](#chart)
- [Claude Code](#claude-code)
- [Cliente](#cliente)
- [cloud-provider-kind](#cloud-provider-kind)
- [CloudNativePG](#cloudnativepg)
- [ClusterPolicy](#clusterpolicy)
- [CODEOWNERS](#codeowners)
- [Codificador](#codificador)
- [components.yaml y generate.py](#componentsyaml-y-generatepy)
- [Conftest y Rego](#conftest-y-rego)
- [Construction](#construction)
- [COOP (Cross-Origin-Opener-Policy)](#coop-cross-origin-opener-policy)
- [Criterio de aceptación](#criterio-de-aceptación)
- [CronJob](#cronjob)
- [CSP (Content Security Policy)](#csp-content-security-policy)
- [Deployment](#deployment)
- [Digest de imagen](#digest-de-imagen)
- [Empuje de vuelta y arbitraje](#empuje-de-vuelta-y-arbitraje)
- [Envoy Gateway](#envoy-gateway)
- [Evidencia del PR](#evidencia-del-pr)
- [Explainer](#explainer)
- [External Secrets Operator](#external-secrets-operator)
- [ExternalSecret y ClusterSecretStore](#externalsecret-y-clustersecretstore)
- [FastAPI](#fastapi)
- [Firing](#firing)
- [Firma de imágenes (Cosign)](#firma-de-imágenes-cosign)
- [Frases prohibidas](#frases-prohibidas)
- [Gateway API](#gateway-api)
- [GitHub Actions](#github-actions)
- [GitOps](#gitops)
- [Grafana](#grafana)
- [Helm](#helm)
- [Herramienta de verificación (U12)](#herramienta-de-verificación-u12)
- [Herramienta MCP](#herramienta-mcp)
- [HPA (Horizontal Pod Autoscaler)](#hpa-horizontal-pod-autoscaler)
- [HTTPRoute](#httproute)
- [httpx y cortacircuitos](#httpx-y-cortacircuitos)
- [Hypothesis y pruebas basadas en propiedades](#hypothesis-y-pruebas-basadas-en-propiedades)
- [Inception](#inception)
- [InferenceService](#inferenceservice)
- [Job](#job)
- [Keycloak](#keycloak)
- [keycloak-config-cli](#keycloak-config-cli)
- [kind](#kind)
- [KServe](#kserve)
- [Kubeconfig de solo lectura](#kubeconfig-de-solo-lectura)
- [kubectl auth can-i](#kubectl-auth-can-i)
- [Kubernetes](#kubernetes)
- [Kustomize](#kustomize)
- [Kyverno](#kyverno)
- [Las seis herramientas de vectra-lectura](#las-seis-herramientas-de-vectra-lectura)
- [Límite de tasa](#límite-de-tasa)
- [Linkerd](#linkerd)
- [Lista de flujos](#lista-de-flujos)
- [Logs estructurados](#logs-estructurados)
- [Loki, Tempo y Alloy](#loki-tempo-y-alloy)
- [Loop de agentes](#loop-de-agentes)
- [Malla de servicios](#malla-de-servicios)
- [MCP (Model Context Protocol)](#mcp-model-context-protocol)
- [metrics-server](#metrics-server)
- [MinIO](#minio)
- [Model-store](#model-store)
- [Monorepo](#monorepo)
- [mTLS](#mtls)
- [Namespace](#namespace)
- [NetworkPolicy](#networkpolicy)
- [OIDC (OpenID Connect)](#oidc-openid-connect)
- [OpenAPI](#openapi)
- [OpenTelemetry](#opentelemetry)
- [Orquestador](#orquestador)
- [Pasos prohibidos](#pasos-prohibidos)
- [PDB (PodDisruptionBudget)](#pdb-poddisruptionbudget)
- [PKCE](#pkce)
- [Playwright](#playwright)
- [Pod](#pod)
- [Pod Security](#pod-security)
- [PostgreSQL](#postgresql)
- [Predictor](#predictor)
- [PriorityClass](#priorityclass)
- [Problem Details](#problem-details)
- [Prometheus](#prometheus)
- [promotion-tool](#promotion-tool)
- [Protección de rama](#protección-de-rama)
- [Proxy](#proxy)
- [Prueba de cambio de modelo](#prueba-de-cambio-de-modelo)
- [Pruebas de mutación](#pruebas-de-mutación)
- [Prune](#prune)
- [psycopg y Alembic](#psycopg-y-alembic)
- [Pushgateway](#pushgateway)
- [Pydantic](#pydantic)
- [pytest](#pytest)
- [Python](#python)
- [RBAC](#rbac)
- [React](#react)
- [React Aria](#react-aria)
- [Realm](#realm)
- [Registro local](#registro-local)
- [Regla de alerta](#regla-de-alerta)
- [Reglas allow, deny y ask](#reglas-allow-deny-y-ask)
- [ResourceQuota y LimitRange](#resourcequota-y-limitrange)
- [Respaldo y archivado WAL](#respaldo-y-archivado-wal)
- [Revisor](#revisor)
- [rollback-note](#rollback-note)
- [Ronda](#ronda)
- [Ruff, mypy e import-linter](#ruff-mypy-e-import-linter)
- [Runbook](#runbook)
- [SBOM](#sbom)
- [SecurityPolicy](#securitypolicy)
- [Selector de idioma](#selector-de-idioma)
- [Selector de tema](#selector-de-tema)
- [Server](#server)
- [ServiceAccount](#serviceaccount)
- [ServiceMonitor y PodMonitor](#servicemonitor-y-podmonitor)
- [Servidor MCP](#servidor-mcp)
- [Servidor vectra-lectura](#servidor-vectra-lectura)
- [settings.json](#settingsjson)
- [Severidades ROJO, NARANJA y AMARILLO](#severidades-rojo-naranja-y-amarillo)
- [Simulacro de restauración](#simulacro-de-restauración)
- [SLO y tasa de consumo](#slo-y-tasa-de-consumo)
- [SPA y BFF](#spa-y-bff)
- [StatefulSet](#statefulset)
- [stdio](#stdio)
- [Step-up (técnico)](#step-up-técnico)
- [Subagente](#subagente)
- [Sync](#sync)
- [Tarea](#tarea)
- [Tema de Keycloak](#tema-de-keycloak)
- [Testcontainers](#testcontainers)
- [TOTP](#totp)
- [Trivy](#trivy)
- [Trusted Types](#trusted-types)
- [TypeScript](#typescript)
- [ui_locales](#ui_locales)
- [Unidades U0 a U12](#unidades-u0-a-u12)
- [uv](#uv)
- [Uvicorn](#uvicorn)
- [Valkey](#valkey)
- [Vault](#vault)
- [vectra-readonly-agent](#vectra-readonly-agent)
- [Veredicto](#veredicto)
- [Vite](#vite)
- [Wave](#wave)
- [Worktree](#worktree)
- [XGBoost](#xgboost)
<!-- /INDICE-ALFABETICO -->
