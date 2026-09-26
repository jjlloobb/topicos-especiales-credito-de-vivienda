# Módulo 9 (opcional): Helm, el gestor de paquetes de Kubernetes

> **Este módulo es opcional y está fuera del cronograma de las 16 sesiones.** No tiene
> fecha asignada, no reemplaza ninguna sesión oficial y no forma parte del proyecto final
> evaluado. Existe para quien ya cursó el módulo 4 y quiere profundizar en una herramienta
> que el módulo 8 solo menciona de paso.

---

## Por qué existe este módulo

El módulo 8 nombra a Helm dentro del paisaje CNCF de producción (junto a Argo CD, Flux,
Trivy, Cosign, Cilium, Crossplane) y su laboratorio usa un `HelmRelease` de Flux, pero
ninguna sesión oficial del curso enseña Helm desde cero: qué es un chart, cómo se
construye uno propio, cómo se actualiza y revierte una release. Ese hueco es exactamente
lo que cubre este módulo.

Casi todo el software de terceros que vas a instalar en un clúster real (ingress
controllers, cert-manager, Prometheus, Grafana, el propio Argo CD) se distribuye como
chart de Helm. Saber leer y escribir uno no es opcional en el trabajo real, aunque sí lo
sea en este curso.

---

## Objetivos de aprendizaje

- Explicar la diferencia entre un **chart**, una **release** y un **repositorio** de
  Helm.
- Instalar un chart público de terceros y verificarlo con `kubectl`.
- Crear un chart propio con `helm create`, entender cada archivo que genera y
  configurarlo (editando `values.yaml` o con `--set`).
- Usar `helm lint` y `helm template` para detectar errores antes de tocar el clúster, y
  reconocer qué tipo de errores esas herramientas SÍ detectan y cuáles no.
- Ejecutar el ciclo completo de una release: `install` → `upgrade` → `history` →
  `rollback` → `uninstall`, explicando qué pasa en el clúster en cada paso.

---

## Agenda

| Tema | Contenido |
|---|---|
| Conceptos | Chart, release, repositorio, values: las cuatro piezas de Helm |
| Instalar de un repo público | `helm repo add/update/search`, `helm install`, verificación con `kubectl` |
| Crear un chart propio | `helm create`, estructura generada, `values.yaml` |
| Configurar y validar | Editar valores, `--set`, `helm template`, `helm lint` |
| El ciclo de vida de una release | `helm upgrade`, `helm history`, `helm rollback`, `helm uninstall` |

---

## Laboratorio

[**Helm: charts, releases y el ciclo instalar / actualizar / revertir**](./laboratorio-helm.md),
55-60 minutos, 10 pasos. Se hace sobre un clúster `kind` dedicado, `topicos-m9`, que tú
creas y borras en la misma sesión de estudio; no toca ningún otro clúster que ya tengas
(por ejemplo el `topicos-m4` del módulo 4).

Cada paso incluye la salida real de los comandos ejecutados contra Helm v4.2.3, kind
v0.32.0 y kubectl v1.36.1, incluyendo un error real de configuración (Paso 6) que se
diagnostica con evidencia de `kubectl describe`, no se maquilla.

**Requisito:** haber pasado por el módulo 4 (arquitectura de Kubernetes, Pods,
Deployments, Services, `kubectl`). Este módulo no repite esos fundamentos.

**Herramientas y conceptos:** `helm`, `kind`, `kubectl`, chart, release, repositorio,
`values.yaml`, `helm lint`, `helm template`, `helm upgrade`, `helm rollback`,
`helm history`.

---

## Cómo conecta con el resto del curso

- **Módulo 4:** este módulo asume que ya entiendes Deployments, Services y el loop de
  reconciliación; Helm no cambia esas piezas, solo empaqueta y versiona los manifiestos
  que las crean.
- **Módulo 8:** el `HelmRelease` de Flux del laboratorio de GitOps es, literalmente, un
  controlador que ejecuta `helm upgrade --install` por ti cada vez que cambia el chart en
  Git. Entender el ciclo `install`/`upgrade`/`rollback` de este módulo es lo que hace
  legible ese `HelmRelease`.

---

## Entregable

Este módulo no tiene entrega evaluada (es opcional y no aparece en el cronograma). El
laboratorio detalla, en su propia sección de entregable, qué evidencia produce quien lo
completa por su cuenta.
