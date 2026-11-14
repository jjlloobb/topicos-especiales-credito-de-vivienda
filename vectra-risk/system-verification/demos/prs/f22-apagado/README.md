# PR `f22-apagado`: F22 apagado en kind (D1, RT-3)

Lo abre el **operador**; esta tarea no lo aplica. `apagar.patch` cambia en `vectra-risk/platform/network/flows.yaml` la clave `env_disabled` de `kind: []` a `kind: [F22]` (nunca staging ni producción: P-19)
y trae lo regenerado por `generate.py`: `generated/kind/vectra-app.yaml`, `vectra-serving.yaml` y `connectivity-suite.yaml`. `revertir.patch` deshace todo.

Desaparecen **cinco** recursos en kind: `NetworkPolicy` `allow-f22-explainability-service-to-explainer-egress` (`vectra-app`), y en `vectra-serving` `NetworkPolicy` `allow-f22-to-explainer-ingress`,
`AuthorizationPolicy` `f22-explainer-8080`, `MeshTLSAuthentication` `f22-explainer-8080-mtls` y `Server` `explainer-8080`.

Después de fusionar, el operador sincroniza la Application `network` en Argo CD, con prune. Para revertir, abre el PR de `revertir.patch`, lo fusiona y sincroniza igual.
Comprobación local: `git apply --check apagar.patch` desde la raíz del repositorio, y `uv run python platform/network/generate.py --check` con el parche aplicado.
