# Recursos del clúster: qué hace cada uno y qué parte del negocio sostiene

Catálogo de lo que corre en `kind-vectra`: servicios, pods, tareas programadas y tareas de una vez. Para cada recurso dice **qué hace en el clúster** y **qué parte del caso de negocio sostiene**. El inventario se leyó del clúster el 27 de noviembre de 2026 (`kubectl get`); lo que hace cada tarea se tomó de su código.

Documentos relacionados: [diagrama del clúster](diagrama-cluster.md), [caso completo de crédito de vivienda](diagrama-caso-credito-vivienda.md) y [órdenes `kubectl`](comandos-kubectl.md).

## El caso de negocio, en ocho capacidades

Vectra Risk existe para que un banco decida un crédito de vivienda con una recomendación explicada y auditable. Eso se descompone en ocho capacidades; el resto del documento las cita por su letra.

| | Capacidad | En una frase |
|---|---|---|
| **A** | Recibir la solicitud | El canal del banco entrega la solicitud y obtiene un identificador de caso |
| **B** | Recomendar | El modelo puntúa el caso y da un resultado: favorable, desfavorable o revisión requerida |
| **C** | Explicar | Cada recomendación sale con los factores que la movieron; sin explicación no hay recomendación |
| **D** | Decidir y dejar rastro | Una persona decide, y la recomendación y la decisión quedan en un registro al que solo se le añade |
| **E** | Gobernar el modelo | Qué versión está activa, cómo se promueve una nueva y cómo se congela una |
| **F** | Vigilar el sesgo | Medir la disparidad entre grupos y congelar el modelo si supera el límite |
| **G** | Medir el producto | Saber si la explicación cambia decisiones y si el comité sostiene lo que recomienda el modelo |
| **H** | Proteger y operar | Identidad, cifrado, secretos, respaldos, alertas y despliegue controlado |

## Los tipos de recurso

| Tipo | Qué es |
|---|---|
| `Pod` | Uno o más contenedores que corren juntos. En la aplicación cada pod lleva el servicio y el proxy de la malla |
| `Deployment` | Mantiene un número de réplicas de un pod sin estado y las actualiza de forma gradual |
| `StatefulSet` | Lo mismo para pods con identidad y disco propios, como una base de datos |
| `Service` | Un nombre y una dirección estables delante de un grupo de pods |
| `Job` | Una tarea que corre una vez hasta terminar |
| `CronJob` | Una tarea que se repite según un horario; cada corrida es un `Job` |

## 1. Borde: `vectra-edge`

| Recurso | Tipo y réplicas | Qué hace en el clúster | Qué sostiene |
|---|---|---|---|
| `api-gateway` | `Deployment` ×1 y `Service` de tipo `LoadBalancer` (puerto 443) | Única entrada desde fuera. Termina TLS, valida el token, aplica el límite de peticiones y reparte por siete rutas | **A**, **D** y **H**: por aquí entran las solicitudes y los usuarios; lo que no está declarado no pasa |
| `console-spa` | `Deployment` ×2 y `Service` | Sirve la aplicación web de la consola | **D**: la pantalla donde el analista revisa y decide |
| `valkey-a`, `valkey-b` | `StatefulSet` ×1 cada uno, con `Service` | Almacén en memoria con los contadores del límite de peticiones | **H**: evita que un cliente sature la entrada |
| `sentinel-a`, `sentinel-b` | `StatefulSet` (×1 y ×2), con `Service` | Vigilan a Valkey y eligen cuál responde | **H**: continuidad del límite de peticiones |

## 2. Identidad: `vectra-identity`

| Recurso | Tipo y réplicas | Qué hace en el clúster | Qué sostiene |
|---|---|---|---|
| `keycloak` | `StatefulSet` ×1, con cuatro `Service` | Inicia sesión a las personas (contraseña y segundo factor) y a los servicios (llave propia), y emite los tokens con el rol | **D** y **H**: cada decisión queda a nombre de quien la tomó, y cada servicio prueba quién es |
| `realm-drift` | `CronJob`, diario a las 03:00 UTC | Compara el realm de Keycloak con el declarado en Git y publica cuántas diferencias hay | **H**: detecta cambios de identidad hechos a mano, fuera de Git |
| `signing-key-age` | `CronJob`, cada hora | Publica la fecha de la llave con que Keycloak firma los tokens; una alerta salta si pasa de 80 días | **H**: recuerda rotar la llave de firma |
| `keycloak-config-cli` | `Job`, tras cada sincronización | Importa el realm (usuarios, roles, clientes, tema) desde Git | **H**: la identidad se despliega igual que el código |

## 3. Aplicación: `vectra-app`

Cada servicio tiene un `Deployment` con dos réplicas y un `Service`. El puerto 8080 es su API y el 8081 sirve las sondas de salud y las métricas; `case-worker` y `product-metrics` solo tienen el 8081 porque no reciben peticiones.

| Recurso | Qué hace en el clúster | Qué sostiene |
|---|---|---|
| `case-service` | Recibe las solicitudes, guarda los casos y su estado, y sirve la bandeja y el detalle a la consola | **A** y **D**: es la puerta de entrada de un caso y donde se registra la decisión del analista |
| `case-worker` | Proceso en bucle: toma cada caso pendiente, pide el puntaje y lo deja «Listo»; reintenta con esperas si algo falla | **B**: lleva el caso de «En evaluación» a «Listo» sin que nadie lo empuje |
| `scoring-service` | Llama al modelo, arma la recomendación y la anota en el registro antes de devolverla | **B** y **D**: produce la recomendación y garantiza que quede registrada |
| `explainability-service` | Obtiene del explicador el aporte de cada factor y arma la narrativa | **C**: lo que el analista lee al pulsar «Ver explicación» |
| `decision-registry-service` | Registro al que solo se le añade: guarda cada recomendación y cada decisión humana, y verifica su integridad | **D**: la trazabilidad, que es la razón de ser del producto |
| `governance-service` | Lleva las versiones del modelo y sus estados: activar, congelar, reactivar | **E**: decide con qué modelo se puede recomendar |
| `bias-monitoring-service` | Sirve a la consola los congelamientos y su paquete de evidencia | **F**: lo que ve el oficial de cumplimiento |
| `console-bff` | Servidor intermedio de la consola: mantiene la sesión, comprueba el rol y llama a los demás servicios | **D** y **H**: el control de quién puede hacer qué está aquí, no en la pantalla |
| `product-metrics` | Lee el registro y publica las métricas de producto en Prometheus | **G**: la North Star y las decisiones sostenidas |

### Tareas de `vectra-app`

| Recurso | Tipo y horario | Qué hace en el clúster | Qué sostiene |
|---|---|---|---|
| `bias-monitoring-job` | `CronJob`, minutos 2, 17, 32 y 47 de cada hora | Mide la disparidad de aprobación entre grupos; si supera el límite, ordena congelar el modelo | **F**: un modelo sesgado deja de recomendar sin esperar a una persona. Es la demo D2 |
| `registry-aggregator` | `CronJob`, cada 5 minutos | Cuenta las recomendaciones y decisiones del registro en tablas de totales, por lotes y sin contar dos veces | **F** y **G**: da los conteos sobre los que se calculan el sesgo y las métricas |
| `case-migration`, `governance-migration`, `registry-migration` | `Job`, una vez por despliegue | Crean o actualizan el esquema de cada base antes de que arranque el servicio | **H**: los cambios de esquema se despliegan de forma ordenada |
| `rt5-demo-20261121-0104` | `Job` terminado | Resto de una prueba de la verificación del 21 de noviembre | Ninguna capacidad: es un residuo |

## 4. Modelo: `vectra-serving`

| Recurso | Tipo y réplicas | Qué hace en el clúster | Qué sostiene |
|---|---|---|---|
| `isvc-8a98ab02` | `InferenceService` de KServe: predictor ×2 y explicador ×2, cada uno con su `Service` | La versión **activa** del modelo. El predictor da el puntaje; el explicador, el aporte de cada factor | **B** y **C**: de aquí salen el puntaje y la explicación |
| `isvc-f12bfeaf` | `InferenceService`: predictor ×1 y explicador ×1 | La versión **inactiva**, cargada y lista | **E**: permite un rollback o una promoción sin esperar a desplegar |

## 5. Datos: `vectra-data`

Cada base PostgreSQL es un `Cluster` de CloudNativePG con tres `Service`: `-rw` (escritura), `-ro` (solo lectura) y `-r` (cualquier instancia).

| Recurso | Instancias | Qué guarda | Qué sostiene |
|---|---|---|---|
| `case-db` | 1 | Los casos, sus estados y los trabajos de evaluación | **A** y **B** |
| `registry-db` | 2, con una réplica síncrona | El registro de recomendaciones y decisiones | **D**: es el dato que no se puede perder, y por eso es la única base con réplica |
| `governance-db` | 1 | Las versiones del modelo y sus transiciones | **E** |
| `keycloak-db` | 1 | Usuarios, roles y sesiones | **H** |
| `minio` | `StatefulSet` ×1, con tres `Service` | Almacén de objetos: los artefactos del modelo y los archivos del registro y de gobierno | **E** y **D** |

## 6. Simulador: `vectra-mock`

| Recurso | Tipo y réplicas | Qué hace en el clúster | Qué sostiene |
|---|---|---|---|
| `core-banking-mock` | `Deployment` ×2 y `Service` | Hace de core bancario: responde consultas de crédito y cuenta cualquier intento de escritura | **H**: permite demostrar que el sistema solo lee del core. Es la demo D3. Solo existe en kind y staging |

## 7. Observabilidad: `vectra-observability`

| Recurso | Tipo y réplicas | Qué hace en el clúster | Qué sostiene |
|---|---|---|---|
| `prometheus` | `StatefulSet` ×1 | Recoge las métricas de todos los servicios y evalúa las reglas de alerta | **G** y **H**: la fuente de los tableros y las alertas |
| `alertmanager` | `StatefulSet` ×1 | Agrupa y encamina las alertas | **H** |
| `grafana` | `Deployment` ×1 | Siete tableros, entre ellos «Producto» | **G**: donde el CRO ve si el producto cumple. Es la demo D4 |
| `otel-collector` | `Deployment` ×1 | Recibe la telemetría de los servicios | **H** |
| `pushgateway` | `Deployment` ×1 | Recibe las métricas de las tareas cortas, que terminan antes de que Prometheus las lea | **F** y **H**: por aquí publican el sesgo y los simulacros |
| `kube-state-metrics`, `operator` | `Deployment` ×1 cada uno | Métricas del estado de los objetos del clúster y gestión de Prometheus | **H** |
| `grafana-folder-check` | `CronJob`, cada 30 minutos | Comprueba que las carpetas de Grafana sean las declaradas | **H**: nació de un fallo real (miles de carpetas duplicadas) |
| `grafana-folder-permissions` | `Job`, tras la sincronización | Fija qué rol ve cada carpeta | **H**: el CRO ve Producto; operación, Operación |

## 8. Respaldo: `vectra-restore-drill`

| Recurso | Tipo y horario | Qué hace en el clúster | Qué sostiene |
|---|---|---|---|
| `restore-drill` | `CronJob`, domingos a las 02:00 UTC | Simulacro de restauración: recupera un respaldo y verifica la cadena del registro | **D** y **H**: comprueba que el registro se puede recuperar. En kind falla, y la alerta `RestoreDrillFailed` es esperada |

## 9. Plataforma

Estos namespaces no atienden casos; hacen posible que todo lo anterior corra con control.

| Namespace | Qué hace en el clúster | Qué sostiene |
|---|---|---|
| `argocd` | Lleva `main` al clúster: 56 aplicaciones, sin sincronización automática | **H**: ningún cambio llega sin un pull request aprobado y una orden de sincronización |
| `kyverno` | Rechaza en la admisión lo que no cumple las políticas | **H**: sin imágenes `latest`, sin privilegios, sin atajos |
| `linkerd`, `linkerd-cni` | Malla: cifra el tráfico entre servicios y autoriza cada flujo | **H**: es lo que niega la escritura al core en la demo D3 |
| `cert-manager` | Autoridad interna y certificados | **H** |
| `vault`, `external-secrets` | Guarda los secretos y los entrega a cada servicio | **H** |
| `cnpg-system` | Operador de las bases PostgreSQL | **D** y **H** |
| `kserve` | Controlador que convierte cada `InferenceService` en pods | **B** y **E** |
| `envoy-gateway-system` | Controlador del gateway y `envoy-ratelimit` ×2 | **A** y **H** |
| `kube-system` | Red de pods (Calico), nombres (CoreDNS) y métricas de uso | Base de todo lo demás |

## Lectura inversa: qué recursos sostienen cada capacidad

| Capacidad | Recursos que la sostienen |
|---|---|
| **A** Recibir la solicitud | `api-gateway`, `case-service`, `case-db` |
| **B** Recomendar | `case-worker`, `scoring-service`, predictor de `isvc-8a98ab02`, `governance-service` |
| **C** Explicar | `explainability-service`, explicador de `isvc-8a98ab02` |
| **D** Decidir y dejar rastro | `console-spa`, `console-bff`, `case-service`, `decision-registry-service`, `registry-db`, `keycloak` |
| **E** Gobernar el modelo | `governance-service`, `governance-db`, `minio`, `isvc-f12bfeaf`, Argo CD |
| **F** Vigilar el sesgo | `bias-monitoring-job`, `registry-aggregator`, `bias-monitoring-service`, `pushgateway`, `governance-service` |
| **G** Medir el producto | `product-metrics`, `prometheus`, `grafana` |
| **H** Proteger y operar | Borde, identidad, malla, políticas, secretos, alertas, respaldo y Argo CD |

## Qué recursos pone a prueba cada demo

| Demo | Qué demuestra | Recursos en juego |
|---|---|---|
| D1 | Sin explicación no hay recomendación | `case-worker`, `scoring-service`, `explainability-service` y la malla |
| D2 | Un modelo con sesgo se congela solo | `bias-monitoring-job`, `governance-service`, `bias-monitoring-service` |
| D3 | El sistema no escribe en el core del banco | `case-service`, `core-banking-mock`, Linkerd y las alertas |
| D4 | El tablero de producto | `decision-registry-service`, `product-metrics`, `prometheus`, `grafana` |

## Qué pasa si falta uno

| Si cae… | El efecto en el negocio |
|---|---|
| `api-gateway` | No entra nadie ni nada: ni solicitudes ni usuarios |
| `keycloak` | Nadie puede iniciar sesión; los servicios dejan de poder autenticarse cuando vencen sus tokens |
| `scoring-service`, el modelo o `explainability-service` | Los casos no llegan a «Listo»: se reintentan y, si no hay forma, quedan «No disponible». El banco sigue con su proceso manual |
| `decision-registry-service` o `registry-db` | Se detienen todas las recomendaciones y no se pierde evidencia; las decisiones quedan pendientes y se reintentan cuando vuelve. Sin rastro no hay recomendación |
| `governance-service` | No se sabe qué modelo está activo, así que no se recomienda |
| `product-metrics` o `grafana` | El negocio sigue; solo se dejan de ver las métricas |
| `bias-monitoring-job` | El negocio sigue, pero nadie vigila el sesgo; una alerta avisa si deja de correr |

## Límites de este documento

- Es el inventario de kind el 27 de noviembre de 2026; las réplicas las fija la memoria del portátil, no la carga.
- La columna «Qué sostiene» es mi lectura a partir del diseño y de las demos; el repositorio no declara esta correspondencia en un único sitio.
- La tabla «Qué pasa si falta uno» describe el comportamiento diseñado. Solo se midieron los casos de las demos D1 y D3; no se tumbó cada servicio para comprobar el resto.
- No lista cada `Service` interno de Keycloak, de las bases ni de Prometheus, ni los pods uno por uno; para verlos, las órdenes están en [`comandos-kubectl.md`](comandos-kubectl.md).
