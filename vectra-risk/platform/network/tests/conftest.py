import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Los modelos de los pods del borde (U2) y el lector del diseno viven en las pruebas de identity-edge (U02-T12, test_edge_*).
_EDGE_TESTS = Path(__file__).resolve().parents[3] / "identity-edge" / "tests"
for _dir in (_EDGE_TESTS / "strategies", _EDGE_TESTS / "unit"):
    if str(_dir) not in sys.path:
        sys.path.append(str(_dir))
