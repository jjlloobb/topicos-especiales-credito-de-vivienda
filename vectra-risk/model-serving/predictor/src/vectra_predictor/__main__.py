"""Punto de entrada de la imagen del predictor: `python -m vectra_predictor` (8080 `:predict`, 8081 sondas y metricas)."""

from vectra_serving_common.metrics import PREDICTOR
from vectra_serving_common.package_loader import PREDICTOR_FILES
from vectra_serving_common.service import serve_forever, try_load

from vectra_predictor.app import create_app
from vectra_predictor.core import Predictor


def main() -> None:
    package = try_load(PREDICTOR_FILES, PREDICTOR)
    predictor = Predictor(package) if package is not None else None
    serve_forever(create_app(predictor), lambda: predictor is not None)


if __name__ == "__main__":
    main()
