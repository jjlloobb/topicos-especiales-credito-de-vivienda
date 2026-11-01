"""NFR-U0-20, BR-U0-25."""

import shutil
import subprocess
import sys
from pathlib import Path

import vectra_contracts

from vectra_contracts.dane import DEPARTMENTS, MUNICIPALITY_DEPARTMENT


def test_tables_loaded():
    assert len(DEPARTMENTS) == 33
    assert MUNICIPALITY_DEPARTMENT["11001"] == "11" and MUNICIPALITY_DEPARTMENT["05001"] == "05"
    assert all(code[:2] == department for code, department in MUNICIPALITY_DEPARTMENT.items())


def test_one_altered_byte_fails_on_import(tmp_path: Path):
    source = Path(vectra_contracts.__file__).parent
    target = tmp_path / "vectra_contracts"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    data = target / "data" / "divipola.csv"
    raw = bytearray(data.read_bytes())
    raw[-2] ^= 1
    data.write_bytes(bytes(raw))
    result = subprocess.run(
        [sys.executable, "-c", "import vectra_contracts.dane"],
        cwd=tmp_path, capture_output=True, text=True, check=False, env={"PYTHONPATH": str(tmp_path)},
    )
    assert result.returncode != 0 and "DataIntegrityError" in result.stderr
