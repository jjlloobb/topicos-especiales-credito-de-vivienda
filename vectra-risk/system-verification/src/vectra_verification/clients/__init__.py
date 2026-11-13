"""Clientes de lectura y del gateway (U12 Paso 5; INF-U12-03; NFR-U12-02, NFR-U12-50).

`oidc` (login, step-up, refresco y tokens de servicio), `gateway` y `bff` (solicitudes por el gateway, con la cabecera de escenario y el `traceparent` de la
corrida), `registry`, `prom` y `loki` (lectura por `port-forward` a un pod) y `k8s_read` (los cuatro verbos de solo lectura de `kubectl`). Playwright solo se importa
en `oidc` y `subprocess` solo en `k8s_read` (contratos de import-linter).
"""
