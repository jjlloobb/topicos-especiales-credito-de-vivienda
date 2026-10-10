# Decisiones de stack — U12 `system-verification`

Decisiones del plan (`system-verification-nfr-requirements-plan.md`, Q1–Q9 = A). Versiones
fijadas en `uv.lock`.

---

| Área | Decisión | Origen |
|---|---|---|
| Lenguaje | Python 3.12 | Q7 |
| Cliente HTTP | `httpx` propio (U12 es un cliente externo: no usa `vectra_common.deps`) | Q7 |
| Escenarios y oráculos | `pytest`, con un módulo por RT y por X de comportamiento | Q7 |
| Tipos | `vectra_contracts` para construir solicitudes y validar respuestas | Q7, U0 |
| TOTP | `pyotp`, en memoria | Q3 |
| Login OIDC sin navegador visible | Playwright con Chromium sin interfaz para el formulario de Keycloak; la herramienta intercepta el `redirect_uri` y canjea el `code` con PKCE (revisión del plan de tareas de U12, 2026-10-10) | Plan de tareas, Paso 5 |
| Carga | k6, con los scripts de U7, U8 y U10 | Q7 |
| Clúster | `kubectl` solo con `get`, `auth can-i`, `logs` y `port-forward` (NFR-U12-43; los dos últimos desde el Infrastructure Design de U12) | Q7; INF-U12-02, 03 |
| Observabilidad | APIs de lectura de Prometheus y Loki | Q7, Q9 |
| PBT | Hypothesis (PBT-U12-01..04) | Q8 |
| Cobertura y mutación | `pytest-cov`, `mutmut` | Q8 |
| Empaquetado | Imagen `system-verification` por digest, ejecutada por el operador fuera del clúster | Q1 |

## Descartado

| Opción | Motivo |
|---|---|
| Jobs de U12 dentro del clúster | Agregan identidades y recursos en el clúster para una herramienta de verificación; desde fuera, U12 entra como un canal y unos usuarios reales (Q1) |
| Todo en k6 | Los oráculos y el informe son más claros y probables en Python (Q7) |
| `.env` con credenciales | Las credenciales quedan en disco (Q3) |
