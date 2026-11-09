"""Punto de entrada de la imagen del explicador: `python -m vectra_explainer` (8080 `:explain`, 8081 sondas y metricas)."""

from vectra_serving_common.metrics import EXPLAINER
from vectra_serving_common.package_loader import EXPLAINER_FILES
from vectra_serving_common.service import serve_forever, try_load

from vectra_explainer.app import create_app
from vectra_explainer.core import Explainer


def main() -> None:
    package = try_load(EXPLAINER_FILES, EXPLAINER)
    explainer = Explainer(package) if package is not None else None
    serve_forever(create_app(explainer), lambda: explainer is not None)


if __name__ == "__main__":
    main()
