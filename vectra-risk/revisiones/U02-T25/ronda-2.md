VEREDICTO: VERDE

# Ronda 2 — U02-T25 (punta 5b53435, diff `b67cddd..5b53435`)

**Nota del orquestador (2026-11-16):** resumen fiel del informe del revisor. El PR #188 se fusionó en `main` (cce33c0) antes de que la revisión terminara. **Medido en `kind-vectra` tras sincronizar `gateway`:** el pod nuevo lleva `LINKERD2_PROXY_INBOUND_PORTS=10443,19001,19002,19003`; tras 100 s y 130 s sin tráfico la primera petición responde 200 (antes fallaba a los 90 s) y el proxy no registra ninguna denegación.

## Hallazgos de la ronda 1

| # | Qué | Resultado (ejecutado por el revisor salvo que diga «leído») |
|---|---|---|
| F-01 | CI de `platform` | **cerrado**: `pytest platform` sin `.tools`, 971 passed (1 fallo de la copia, que no es un repositorio git; en el worktree pasa) |
| F-01 | Cifras del presupuesto | **idénticas** en `origin/main` y en la rama: pico 13,7344 GiB (13,8), 10,665 CPU (10,7), data plane 1 réplica `[250m/256Mi, 10m/32Mi]` |
| F-01 | Mutaciones de `patch_resources()` | `envoy` con `resources` o `image`: ValueError; contenedor nuevo o `shutdown-manager` sin `resources`: ValueError; contenedor nuevo con recursos: se cuenta |
| F-02 | Barrido y `CANDIDATAS.md` | **cerrado** (leído): coincide con la tabla de la ronda 1; la corrección solo añade al final |
| F-03 | Prueba de mezcla sobre el Deployment | **cerrado, con reserva (F-N1)**: el contenido coincide con `kubectl patch --local --type strategic` en 4 casos; el orden, no |
| F-03 | Orden `envoy` antes de `shutdown-manager` | la regla rego lo detecta (3 FAIL); la prueba de mezcla, no |
| F-04 | Literales 10443, 10000, 1024 | queda (AMARILLO) |
| F-05 | Prueba tautológica | **cerrado**: eliminada |
| F-06 | `envoy` duplicado y UDP | **cerrado en parte**: un puerto TCP extra sigue pasando |

Regresión: `make -C identity-edge route-gen check-route-gen kubeconform-gateway policy-gateway xds-gateway` rc 0; `pytest identity-edge/tests/unit -k "route_gen or data_plane"` 490 passed; los módulos que leen `edge.rego` y el ADR fuera del filtro, 151 passed. En `platform/` el diff solo toca `tests/test_kind_profile.py`.

## Hallazgos nuevos
### F-N1 · AMARILLO · `identity-edge/tests/unit/test_data_plane_policies.py:301-303,342` · `strategic_merge()` no reproduce el orden de la mezcla real y la aserción de orden no comprueba nada
Con el parche invertido, `kubectl` reordena los contenedores y el helper no: la mutación no tumba la prueba. El orden lo fija la regla rego (verificada). El fixture de EG v1.9.3 está simplificado.
### F-N2 · AMARILLO · `CANDIDATAS.md:836` · La corrección dice que `valkey-26379` y `sentinel-6379` «no seleccionan ningún pod»; son puertos cruzados (seleccionan pods que no sirven ese puerto)
### F-06 (resto) · AMARILLO · `edge.rego:292-345` · `envoy-container-port` acepta un puerto TCP extra

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tests/unit/test_data_plane_policies.py:301-303,342|strategic_merge() no reproduce el orden real; la aserción de orden no detecta la inversión (la regla rego sí)
AMARILLO|CANDIDATAS.md:836|redacción inexacta: son puertos cruzados
AMARILLO|identity-edge/gateway/policy/edge.rego:292-345|acepta un puerto TCP extra
AMARILLO|identity-edge/tools/route_gen.py:591-593|literales sin cruce con egctl
INFORME: revisiones/U02-T25/ronda-2.md
```
