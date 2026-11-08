"""NFR-U5-32: `envelope.confidence` se importa y funciona en un entorno con solo numpy (como en la imagen de U6)."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import vectra_reference.envelope.confidence as confidence_module

ENVELOPE = {
    "numeric": [{"name": "a", "p1": 0.0, "p99": 10.0}, {"name": "b", "p1": 0.0, "p99": 10.0}],
    "categories": {"c": ["x", "y"]},
    "mean": [5.0, 5.0],
    "covariance": [[4.0, 0.0], [0.0, 4.0]],
    "distance_quantiles": [0.0, 1.0, 2.0, 3.0, 4.0],
}
SCRIPT = """
import json, sys
import confidence
env = json.loads(sys.argv[1])
print(json.dumps({
    "inside": confidence.confidence(env, {"a": 5.0, "b": 5.0, "c": "x"}),
    "unseen": confidence.confidence(env, {"a": 5.0, "b": 5.0, "c": "z"}),
    "modules": sorted(m.split(".")[0] for m in sys.modules),
}))
"""


def test_numpy_only_confidence_imports_and_runs_in_an_isolated_interpreter(tmp_path: Path) -> None:
    """Subproceso con `-S -E -s` (sin site-packages ni variables de entorno): el unico paquete visible es numpy, enlazado en un directorio nuevo."""
    numpy_dir = Path(np.__file__).parent
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "numpy").symlink_to(numpy_dir)
    for libs in numpy_dir.parent.glob("numpy.libs"):
        (sandbox / libs.name).symlink_to(libs)
    (sandbox / "confidence.py").write_bytes(Path(confidence_module.__file__).read_bytes())
    script = sandbox / "run.py"  # el directorio del script es sys.path[0]: el unico visible
    script.write_text(SCRIPT)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-S", "-E", "-s", str(script), json.dumps(ENVELOPE)],
        capture_output=True,
        text=True,
        check=False,
        env={},
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["inside"] == "1.0000"
    assert out["unseen"] == "0.0000"
    forbidden = {"sklearn", "scipy", "shap", "xgboost", "pandas", "pyarrow", "yaml", "vectra_contracts"}
    assert not forbidden & set(out["modules"]), out["modules"]


def test_numpy_only_the_module_source_imports_only_numpy_and_stdlib() -> None:
    import ast

    tree = ast.parse(Path(confidence_module.__file__).read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots <= {"__future__", "math", "collections", "decimal", "typing", "numpy"}, roots
