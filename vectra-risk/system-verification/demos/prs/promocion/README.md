# PRs `promocion`: los cuatro que crea `promotion-tool` (D2)

No son parches: los **crea** `promotion-tool` (`governance/promotion_tool/vectra_promotion/cli.py`). Las cuatro órdenes (las tres primeras abren un PR que el operador revisa, fusiona y sincroniza en la Application `model-serving`):

1. `create-promotion-pr <model_version_id>`: agrega la entrada `prod` de la versión promovida.
2. `post-activation-pr <previous_version_id>`: pasa a `inactive` la versión anterior, tras `mark-active`.
3. `rollback-pr <model_version_id>`: devuelve la versión a los mínimos de `prod` (cierre de D2).
4. `mark-active <model_version_id> --evidence "<texto>"`: marca la versión activa en governance (no abre PR).

Además, `list-promotable` lista lo promovible. La invocación completa (emisor, API, `--diff-command`) está en `governance/docs/paso-20-kind.md`, secciones 5 y 6: **no se copia aquí**.
