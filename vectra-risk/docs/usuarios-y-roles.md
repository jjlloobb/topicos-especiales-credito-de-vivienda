# Usuarios, roles y accesos de la consola

Quién puede entrar a la consola de Vectra Risk en `kind-vectra`, con qué rol, qué ve y qué puede hacer. Los usuarios y sus roles salen del realm de Keycloak (`identity-edge/keycloak/realm/realm.kind.yaml`); los accesos, de la tabla de rutas de la consola (`console/spa/src/views/shared/routes.ts`) y de las operaciones del BFF (`aidlc-docs/inception/application-design/component-methods.md`). Leído el 27 de noviembre de 2026.

Diagramas relacionados: [viaje de los usuarios](diagrama-viaje-usuarios.md) y [caso completo de crédito de vivienda](diagrama-caso-credito-vivienda.md).

> **Las contraseñas y las semillas del segundo factor no están en este repositorio.** Son usuarios sintéticos, pero sus credenciales viven en la bóveda del clúster. La sección «Cómo obtener las credenciales» dice dónde.

## Los diez usuarios

Hay cinco roles y dos usuarios por rol. Todos entran con contraseña y un segundo factor (código TOTP de seis dígitos).

| Usuario | Rol | Pantalla de inicio | Para qué sirve en una demostración |
|---|---|---|---|
| `analista-1`, `analista-2` | `analista` | Bandeja de casos | Revisar un caso y registrar la decisión |
| `cro-1`, `cro-2` | `cro` | Bandeja de casos | Ver los casos, los modelos y los congelamientos, sin decidir |
| `cumplimiento-1`, `cumplimiento-2` | `cumplimiento` | Congelamientos | Ver la evidencia de un congelamiento y resolverlo |
| `ingeniero-1`, `ingeniero-2` | `ingeniero_riesgo` | Modelos | Ver las versiones del modelo y su informe de validación |
| `operacion-1`, `operacion-2` | `operacion` | Ninguna | No tiene vistas en la consola; trabaja con Grafana, Argo CD y los runbooks |

**Cuál usar.** Los guiones de verificación y las pruebas de humo entran con los usuarios `-1` (y con `analista-2` para consultar casos). Para presentar a mano conviene usar los `-2`, salvo el analista: usa `analista-1` en el navegador, porque `analista-2` lo ocupa el guion que envía la solicitud del caso en vivo.

## Cómo entrar

1. Abre `https://vectra.localtest.me/`. La consola redirige al inicio de sesión de Vectra.
2. Escribe el usuario y la contraseña.
3. Escribe el código de seis dígitos de la aplicación de autenticación.
4. La consola abre la pantalla de inicio del rol.

Arriba a la derecha están el rol con que entraste, el estado de la verificación en dos pasos, el idioma (español, inglés o portugués de Brasil), el tema (claro, oscuro o el del sistema) y «Cerrar sesión».

### Reglas de la sesión

| Regla | Valor | Qué significa al presentar |
|---|---|---|
| Vida del token de acceso | 5 minutos | Se renueva sola mientras la sesión esté viva |
| Sesión inactiva | 30 minutos | Pasado ese tiempo sin usarla, pide entrar de nuevo |
| Duración máxima de la sesión | 10 horas | Entra el mismo día de la presentación |
| Intentos fallidos | 5 | Al quinto, la cuenta se bloquea un tiempo |
| Código TOTP | Un uso por ventana de 30 s | No entres dos veces seguidas con el mismo usuario: espera 30 segundos |
| Verificación reforzada | Tras 15 minutos de sesión | Resolver un congelamiento vuelve a pedir contraseña y código |

Un código rechazado cuenta como intento fallido. Si un guion y una persona usan el mismo usuario a la vez, uno de los dos gasta el código del otro.

## Qué puede hacer cada rol

### Analista (`analista-1`, `analista-2`)

Es el único rol que **decide** un caso.

| Dónde | Qué hace |
|---|---|
| **Bandeja de casos** | Ve las solicitudes con su estado, canal, fecha, recomendación y puntaje. Filtra por estado. Va a un caso pegando su identificador en «Ir al caso». La bandeja se actualiza cada 15 segundos |
| **Detalle del caso** | Ve la recomendación del modelo: resultado, puntaje, confianza y razones |
| «Ver explicación» | Ve la narrativa y el aporte de cada factor. Abrirla queda contado en las métricas de producto |
| «Ver los datos de la solicitud» | Ve los datos (sintéticos) con que se evaluó el caso |
| **Registrar decisión** | Elige si sigue la recomendación o se aparta, el resultado final y los factores que usó. Si se aparta o resuelve una revisión, debe escribir una justificación de al menos 20 caracteres. La consola pide confirmar antes de enviar |

No puede: ver modelos ni congelamientos. En su menú aparecen «Alta manual de solicitud» y «Políticas», que muestran «Esta pantalla no está disponible en esta versión».

### VP de Riesgo, CRO (`cro-1`, `cro-2`)

Ve casi todo, pero **no decide casos ni resuelve congelamientos**.

| Dónde | Qué hace |
|---|---|
| **Bandeja de casos** y **detalle del caso** | Ve los casos y su recomendación, igual que el analista, sin registrar decisión |
| **Modelos** y **detalle del modelo** | Ve las versiones, su estado (activo, inactivo, congelado) y el informe de validación |
| **Congelamientos** | Ve la lista de congelamientos; no abre el paquete de evidencia |

Diferidas en su menú: «Políticas», «Fuentes de datos», «Monitoreo de sesgo», «Expedientes», «Fallos persistentes» y «Verificación de integridad».

### Oficial de cumplimiento (`cumplimiento-1`, `cumplimiento-2`)

Es el único rol que **resuelve un congelamiento**.

| Dónde | Qué hace |
|---|---|
| **Congelamientos** | Ve la lista de modelos congelados y resueltos |
| **Contexto del congelamiento** | Abre el paquete de evidencia: por qué se congeló el modelo y con qué datos. Solo este rol lo ve |
| «Resolver este congelamiento» | Decide si el modelo se reactiva o no, con una justificación. Si la sesión tiene más de 15 minutos, el botón dice «Verificar y confirmar» y una ventana pide contraseña y código otra vez |
| **Modelos** y **detalle del modelo** | Ve las versiones y su informe de validación |

No puede: ver la bandeja ni el detalle de los casos. Diferidas en su menú: «Políticas», «Fuentes de datos», «Monitoreo de sesgo» y «Expedientes».

En `kind-vectra` hay un congelamiento real ya resuelto (el de la demo D2) que sirve para mostrar el paquete de evidencia sin congelar nada. Intentar resolverlo otra vez responde con un conflicto, que es lo esperado.

### Ingeniero de riesgo (`ingeniero-1`, `ingeniero-2`)

| Dónde | Qué hace |
|---|---|
| **Modelos** | Ve las versiones del modelo y cuál está activa |
| **Detalle del modelo** | Ve el informe de validación de una versión |

Promover un modelo **no se hace en la consola**: se propone con `promotion-tool`, que abre un pull request; una persona lo aprueba y Argo CD lo sincroniza. Diferida en su menú: «Fuentes de datos».

### Operación (`operacion-1`, `operacion-2`)

No tiene vistas en la consola. Su trabajo está fuera de ella: los tableros de Grafana, Argo CD y los runbooks de `platform/runbooks/`.

## Resumen de accesos

| Vista u operación | Analista | CRO | Cumplimiento | Ingeniero | Operación |
|---|---|---|---|---|---|
| Bandeja y detalle del caso | Sí | Sí | — | — | — |
| Registrar que se vio la explicación | Sí | — | — | — | — |
| Registrar la decisión de un caso | Sí | — | — | — | — |
| Modelos y detalle del modelo | — | Sí | Sí | Sí | — |
| Lista de congelamientos | — | Sí | Sí | — | — |
| Paquete de evidencia de un congelamiento | — | — | Sí | — | — |
| Resolver un congelamiento | — | — | Sí | — | — |

El rol viaja en el token que emite Keycloak; quien decide si una petición pasa es el BFF de la consola, no la interfaz. Ocultar un botón no es el control.

## Acceso a Grafana por rol

Las carpetas de Grafana tienen permisos por equipo (`platform/observability/grafana/folder-permissions.yaml`):

| Carpeta | Quién la ve |
|---|---|
| Vectra / Producto | CRO, cumplimiento e ingeniero de riesgo |
| Vectra / Sesgo | CRO y cumplimiento |
| Vectra / Operación | Operación, con permiso de edición |

En `kind-vectra` el inicio de sesión de Grafana con estos usuarios **no funciona por el gateway**: Grafana se abre por port-forward con su cuenta de administrador. Estos permisos están declarados, pero no se han probado entrando con cada rol.

## Cómo obtener las credenciales

- **Dónde viven.** En la bóveda del clúster, en la ruta `identity/synthetic-users`. Las siembra `platform/kind/seed-vault.sh identity`, que también las escribe para las pruebas en un archivo local (`${VECTRA_E2E_KEYS_DIR:-$XDG_RUNTIME_DIR/vectra-e2e-keys}/env`), con permisos solo para el usuario.
- **Qué hay ahí.** Por cada usuario, una contraseña y una semilla TOTP. La semilla se registra una vez en una aplicación de autenticación (por ejemplo, escaneando un QR) y a partir de ahí la aplicación da el código de seis dígitos.
- **Se conservan entre reinicios.** Al resembrar la bóveda tras reiniciar la máquina, las contraseñas y las semillas de los usuarios se recuperan, no se regeneran: lo registrado en el teléfono sigue sirviendo.
- **No las imprimas en una pantalla compartida** ni las pegues en un documento, un PR o una conversación.

## Recorridos sugeridos para una demostración

| Con quién | Recorrido | Tiempo |
|---|---|---|
| `analista-1` | Bandeja, abrir un caso «Listo», ver la explicación, registrar la decisión | 2 min |
| `cro-2` | Bandeja, un caso ya decidido, Modelos, Congelamientos | 1 min |
| `cumplimiento-2` | Congelamientos, abrir el congelamiento resuelto y su paquete de evidencia | 1 min |
| `ingeniero-2` | Modelos, detalle de la versión activa y su informe de validación | 1 min |

Deja pasar 30 segundos entre dos entradas con el mismo usuario, y usa perfiles de navegador distintos si vas a tener dos roles abiertos a la vez.

## Límites de este documento

- Los usuarios son sintéticos y solo existen en kind. Ninguna persona real de un banco ha usado la consola.
- Las siete vistas diferidas están en el menú, pero no hacen nada: no las abras en una demostración.
- Lo que hace cada rol se tomó de las tablas de rutas y de operaciones; el recorrido del analista se ejecutó de punta a punta el 27 de noviembre de 2026, y los de CRO, cumplimiento e ingeniero se probaron en las demos del 20 al 23 de noviembre. No comprobé qué ve exactamente `operacion-1` al entrar.
