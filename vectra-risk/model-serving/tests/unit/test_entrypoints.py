"""Los `args` que KServe agrega al explicador (`--model_name`, `--predictor_host`, `--http_port`) no deben afectar al programa (U06-T02, F-01)."""

import importlib
import sys

import pytest

KSERVE_ARGS = [
    "vectra_explainer",
    "--model_name",
    "isvc-26300247",
    "--predictor_host",
    "isvc-26300247-predictor.vectra-serving",
    "--http_port",
    "8080",
]


@pytest.mark.parametrize("module", ["vectra_explainer.__main__", "vectra_predictor.__main__"])
def test_el_programa_ignora_los_argumentos_extra_de_sys_argv(
    module: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    served: list[object] = []
    main = importlib.import_module(module)
    monkeypatch.setattr(main, "try_load", lambda *_: None)
    monkeypatch.setattr(main, "serve_forever", lambda app, ready: served.append((app, ready())))
    monkeypatch.setattr(sys, "argv", KSERVE_ARGS)
    main.main()
    assert len(served) == 1
    assert served[0][1] is False  # type: ignore[index]
