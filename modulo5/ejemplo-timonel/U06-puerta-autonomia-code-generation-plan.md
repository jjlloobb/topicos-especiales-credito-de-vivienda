# Plan de generación de código — U6 Puerta de autonomía y RBAC

> **Artefacto de ejemplo.** Esto es lo que produce la **Parte 1** de la etapa Code Generation
> de AI-DLC, y es **el punto exacto donde este trabajo se detiene**. La Parte 2 ejecuta este
> plan y escribe el código; solo corre si un humano aprueba el plan.
>
> Se eligió U6 para el ejemplo a propósito: es la unidad que convierte el límite de autonomía
> del PRD en código con pruebas, y es la que vas a enseñar en la sustentación.

Raíz del proyecto (greenfield). Añade `internal/gate/` y `config/rbac/`; **modifica** en su
sitio `internal/diagnose/loop.go` para que toda lectura del clúster pase por la puerta en vez
de por el cliente directo. Código de aplicación en la raíz; el resumen va en
`aidlc-docs/construction/U6-gate/code/`.

---

## Contexto de la unidad

- **Historias**: US-6.1 (ServiceAccount de solo lectura), US-6.2 (rechazo de verbos de
  escritura), US-6.3 (nunca leer secretos), US-6.4 (no ampliar sus propios permisos).
  Relacionada: US-6.5 vive en U9, porque el permiso de merge es del repositorio, no del clúster.
- **Depende de**: U1 (`internal/catalog` para los tipos), U2 (`internal/safety` para el
  registro de cada decisión). **Expone**: `gate.Allow(tool, verb, resource)`,
  `gate.Client()`, `gate.AuditLog()`.
- **Principios que materializa**: el agente observa, correlaciona, diagnostica y redacta; el
  agente nunca aplica, nunca aprueba, nunca toca secretos, nunca amplía permisos.

---

## Pasos

- [ ] **Paso 1 — `internal/gate/allowlist.go` (lista blanca de herramientas)**
  Tabla explícita de las herramientas permitidas y, para cada una, los verbos y recursos que
  puede tocar. Lo que no está en la tabla se rechaza. Sin comodines.
  **Criterio de aceptación:** `go test ./internal/gate -run TestAllowlistRechazaLoNoListado`
  pasa, y la tabla no contiene la cadena `*` en la columna de verbos.

- [ ] **Paso 2 — `internal/gate/rbac.go` (comprobación de permisos)**
  `CanI(verb, resource, namespace)` implementado con `SelfSubjectAccessReview` de la API de
  autorización. Se consulta **antes** de cada llamada, no se asume.
  **Criterio de aceptación:** `go test ./internal/gate -run TestCanI` pasa contra el clúster
  de pruebas, y `kubectl auth can-i get pods --as=system:serviceaccount:timonel:agente`
  responde `yes`.

- [ ] **Paso 3 — `internal/gate/refuse.go` (rechazo duro de escritura)**
  Lista negra de verbos: `create`, `update`, `patch`, `delete`, `deletecollection`. Cualquiera
  devuelve `ErrEscrituraProhibida` antes de tocar la red. No es una comprobación de permisos:
  es una negativa del código, para que siga valiendo aunque alguien amplíe el RBAC por error.
  **Criterio de aceptación:** `go test ./internal/gate -run TestRechazaEscritura` pasa para
  los cinco verbos, y ninguna prueba requiere clúster (el rechazo es previo a la red).

- [ ] **Paso 4 — `internal/gate/audit.go` (registro de cada decisión)**
  Toda decisión de la puerta, permitida o rechazada, se añade al registro con marca de tiempo
  ISO 8601, herramienta, verbo, recurso e identificador de incidente. **Solo se añade, nunca
  se reescribe.**
  **Criterio de aceptación:** `go test ./internal/gate -run TestAuditSoloAnade` pasa: tras
  dos escrituras, la primera entrada sigue presente byte a byte.

- [ ] **Paso 5 — `config/rbac/` (el ServiceAccount y su ClusterRole)**
  `ServiceAccount` `timonel:agente`, `ClusterRole` con verbos `get`, `list` y `watch`
  únicamente, sobre los recursos que el catálogo declara. **Sin** `secrets`. **Sin**
  `rolebindings` ni `clusterrolebindings`.
  **Criterio de aceptación:** los cuatro comandos de US-6.1, 6.3 y 6.4 responden lo esperado:
  ```bash
  kubectl auth can-i get pods        --as=system:serviceaccount:timonel:agente  # yes
  kubectl auth can-i create deployments --as=system:serviceaccount:timonel:agente  # no
  kubectl auth can-i get secrets     --as=system:serviceaccount:timonel:agente  # no
  kubectl auth can-i create clusterrolebindings --as=system:serviceaccount:timonel:agente  # no
  ```

- [ ] **Paso 6 — Cablear la puerta en `internal/diagnose/loop.go` (MODIFICAR en su sitio)**
  Reemplazar el cliente directo de Kubernetes por `gate.Client()`. No crear
  `loop_nuevo.go` ni `loop_v2.go`: se modifica el archivo existente.
  **Criterio de aceptación:** `grep -rn "kubernetes.NewForConfig" internal/diagnose/` no
  devuelve nada, y `go test ./internal/diagnose` sigue pasando.

- [ ] **Paso 7 — Pruebas negativas de escalada de privilegios (`test/gate/`)**
  Las que importan. Cada una intenta salirse del límite y **debe** fallar:
  - intentar `create` sobre un `Deployment` por la vía normal;
  - intentar leer un `Secret` con una herramienta que sí está en la lista blanca;
  - intentar registrar una herramienta nueva en tiempo de ejecución;
  - intentar crear un `ClusterRoleBinding` que amplíe el propio `ServiceAccount`;
  - intentar reescribir el registro de auditoría en vez de añadir.
  **Criterio de aceptación:** `go test ./test/gate -run TestEscalada` pasa con los cinco
  casos, y cada uno afirma **el error concreto**, no solo que hubo error.

- [ ] **Paso 8 — Resumen de la unidad**
  `aidlc-docs/construction/U6-gate/code/summary.md`: qué quedó construido, qué expone y qué
  comando demuestra el límite.
  **Criterio de aceptación:** el resumen contiene los cuatro comandos de `auth can-i` con su
  salida real pegada.

---

## Trazabilidad a historias

| Historia | Pasos que la implementan |
|---|---|
| US-6.1 ServiceAccount de solo lectura | Pasos 2, 5 |
| US-6.2 Rechazo de verbos de escritura | Pasos 1, 3, 6, 7 |
| US-6.3 Nunca leer secretos | Pasos 1, 5, 7 |
| US-6.4 No ampliar sus propios permisos | Pasos 5, 7 |
| Registro de la decisión (soporta US-8.3) | Pasos 4, 7 |

Ningún paso queda sin historia y ninguna historia de la unidad queda sin paso.

---

## Notas

- `internal/diagnose/loop.go` se **modifica en su sitio**. Nada de archivos duplicados con
  sufijo.
- Las pruebas se escriben **en esta etapa**, no se aplazan a Build and Test. Esa etapa
  verifica y amplía; no crea las pruebas desde cero.
- **Dos capas independientes, a propósito.** El Paso 3 rechaza la escritura en el código y el
  Paso 5 la niega en el RBAC. Es deliberado: si alguien amplía el `ClusterRole` por error, el
  código sigue negándose; si alguien toca el código, el RBAC sigue negándose. Una sola capa es
  una promesa; dos capas independientes es un límite.
- **Ningún paso de este plan aplica cambios a un clúster.** Los comandos de verificación son
  todos de lectura (`auth can-i` pregunta, no modifica). Esa es la regla `AUTONOMIA-01` del
  proyecto cumpliéndose dentro del propio plan de tareas.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
