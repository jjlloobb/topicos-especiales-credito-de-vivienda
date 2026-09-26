# Límite de autonomía del agente

## Overview
Estas reglas son restricciones bloqueantes en todas las fases de AI-DLC para la
construcción de Vectra Risk. No son recomendaciones. Cada etapa DEBE verificarlas
antes de presentar su mensaje de finalización. Las reglas AUTONOMIA-03 a AUTONOMIA-06
operacionalizan los Principios 1 a 4 del PRD ("El modelo puntúa, el humano decide",
"Soberanía del dato", "Fail-closed", "El monitoreo mide, no certifica") — no son
añadidos del agente, son restricciones que ya existían en `entradas/prd.md`,
Segmento 6.

### Default Enforcement
Todas las reglas de este documento son **bloqueantes**. Si no se cumple un criterio de
verificación, es un hallazgo bloqueante: la etapa solo puede ofrecer «Request Changes».

---

## Rule AUTONOMIA-01: Ninguna tarea aplica cambios a infraestructura sin aprobación

**Rule**: Ninguna unidad de trabajo puede contener una tarea que aplique cambios al
clúster Kubernetes del banco, a su configuración de RBAC/NetworkPolicy, o a cualquier
entorno compartido sin una aprobación humana registrada. El destino de la cadena del
agente es un pull request con evidencia adjunta (manifiestos, resultado de
`kubectl diff`, salida de pruebas), nunca un `kubectl apply`, `helm install` o
`terraform apply` autónomo — incluido el clúster de desarrollo/staging usado durante
CONSTRUCTION.

**Verification**:
- Ningún plan de tareas contiene un paso que ejecute `kubectl apply`, `terraform apply`,
  `helm install`/`helm upgrade` o equivalente sin un paso previo de aprobación humana
- Toda tarea que toque `scoring-service`, `explainability-service`,
  `bias-monitoring-service`, el Decision Registry o cualquier `NetworkPolicy`/`RBAC`
  produce un artefacto revisable (PR), no un cambio directo al clúster

---

## Rule AUTONOMIA-02: Todo criterio de aceptación se verifica con un comando

**Rule**: Cada tarea de cada unidad DEBE tener un criterio de aceptación comprobable
ejecutando un comando. Las formulaciones de opinión no son criterios de aceptación.

**Verification**:
- Ningún criterio de aceptación usa formulaciones como «funciona correctamente»,
  «es usable» o «tiene buen rendimiento» sin un comando o umbral medible
- Cada tarea nombra el comando, la prueba o la comprobación que demuestra que terminó
  (ej. `kubectl get rolebinding -o yaml`, una prueba de integración específica, o el
  resultado de un escenario de red-teaming del Segmento 11 del PRD)

---

## Rule AUTONOMIA-03: Ningún servicio escribe estado de crédito

**Rule**: Ninguna tarea puede implementar, en `scoring-service`, `explainability-service`
o `bias-monitoring-service`, una ruta de código o un permiso de RBAC que escriba sobre
el estado de un crédito (aprobado, rechazado, desembolsado) en el core bancario. Estos
servicios exponen únicamente un objeto de recomendación; el cambio de estado del
crédito ocurre exclusivamente en el core bancario, mediante una acción humana explícita.
Esto no es una restricción de alcance del MVP: es una prohibición permanente (Principio
1 del PRD) que ninguna fase posterior puede levantar.

**Verification**:
- El `Role`/`ClusterRole` de `scoring-service` y `explainability-service` otorga
  **solo lectura** (`get`, `list`, `watch`) sobre cualquier recurso que represente
  estado de crédito del core bancario (mock/adapter incluido), y escritura únicamente
  sobre sus propias tablas (recomendaciones, explicaciones, Decision Registry)
- Ninguna tarea agrega un endpoint, mutación o cliente HTTP desde estos servicios
  hacia una ruta del core bancario que modifique estado (`POST`/`PUT`/`PATCH`/`DELETE`
  sobre crédito)
- El escenario de red-teaming #5 del Segmento 11 (intento de escritura hacia estado de
  crédito) se ejecuta y falla como se espera antes de cerrar cualquier unidad que toque
  estos tres servicios

---

## Rule AUTONOMIA-04: Ninguna reactivación automática de un modelo congelado

**Rule**: Cuando `bias-monitoring-service` congela un modelo por superar el umbral de
disparidad (Principio 4 del PRD), ninguna tarea puede implementar una ruta de código
que reactive ese modelo automáticamente. La reactivación es una decisión humana del
oficial de cumplimiento, registrada con su propio `user_id` y timestamp — el sistema
solo la ejecuta una vez tomada.

**Verification**:
- No existe en el código ningún job, cronjob, webhook o lógica de reintento que cambie
  el estado de un modelo de `congelado` a `activo` sin una llamada explícita autenticada
  como el rol de cumplimiento
- Toda prueba de este flujo verifica que un modelo congelado permanece congelado tras
  reintentos automáticos del sistema, y que solo un cambio de estado hecho por el rol
  de cumplimiento lo reactiva

---

## Rule AUTONOMIA-05: Ningún dato del solicitante sale del clúster del banco

**Rule**: Ninguna tarea puede implementar una llamada saliente desde `scoring-service`,
`explainability-service` o `bias-monitoring-service` que envíe PII o variables del
solicitante a un destino fuera del clúster del banco — incluida telemetría propia de
Vectra Risk, un SDK de observabilidad de terceros, logging centralizado gestionado por
el vendor, o una llamada a un modelo o API externa — sin pasar antes por una función de
anonimización auditada. Esto es el Principio 2 del PRD (soberanía del dato) y sostiene
el diferenciador central del producto; ninguna fase de CONSTRUCTION puede levantarlo
para "mejorar" observabilidad o depuración.

**Verification**:
- Ninguna tarea agrega una dependencia, SDK o llamada HTTP saliente hacia un dominio
  fuera del clúster desde estos tres servicios sin que el campo transmitido pase
  primero por una función de anonimización con su propia prueba
- Las `NetworkPolicies` del namespace no permiten tráfico de egress hacia destinos
  externos al clúster desde estos tres servicios, salvo los explícitamente aprobados
  (ej. el identity provider del banco)
- Ninguna tarea de logging o métricas incluye campos de PII (nombre, cédula, ingreso,
  dirección) en texto plano en destinos de log agregados fuera del clúster

---

## Rule AUTONOMIA-06: Ninguna tarea implementa un bypass del fail-closed

**Rule**: Ninguna tarea puede implementar una ruta de código que entregue un score como
decisión usable cuando `explainability-service` no responde, responde con error, o
responde con un `model_version_id` distinto al de `scoring-service`. Esto es el
Principio 3 del PRD (fail-closed): un score sin explicación sincronizada no es una
decisión degradada aceptable, es una no-decisión. Ninguna tarea puede agregar un valor
por defecto, una plantilla genérica u otra forma de "explicación de respaldo" para
evitar el estado "no disponible", aunque la intención declarada sea mejorar la
experiencia del analista.

**Verification**:
- Ninguna tarea agrega un valor por defecto, plantilla genérica o explicación de una
  versión anterior del modelo como sustituto cuando `explainability-service` no
  responde o responde con una versión distinta a la de `scoring-service`
- El escenario de red-teaming #3 del Segmento 11 (desincronía forzada de versión) se
  ejecuta antes de cerrar cualquier unidad que toque estos dos servicios, y el sistema
  responde "no disponible, reintentando" — nunca un score sin explicación sincronizada
