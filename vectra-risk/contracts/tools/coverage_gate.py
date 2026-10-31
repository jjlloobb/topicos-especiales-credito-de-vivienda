"""Cobertura del 100 % en los modulos criticos (NFR-U0-40). Lee `coverage json`."""

import json
import subprocess
import sys
from pathlib import Path

CRITICAL = (
    "vectra_contracts/outcome/",
    "vectra_common/authz.py",
    "vectra_common/logging.py",
    "vectra_common/deps.py",
    "vectra_common/deadline.py",
)


def main() -> int:
    report = Path("coverage.json")
    subprocess.run([sys.executable, "-m", "coverage", "json", "-o", str(report), "-q"], check=True)
    files = json.loads(report.read_text(encoding="utf-8"))["files"]
    failed = False
    for name, data in sorted(files.items()):
        if any(part in name for part in CRITICAL):
            percent = data["summary"]["percent_covered"]
            print(f"{percent:6.2f} % {name}")
            if percent < 100:
                print("  sin cubrir:", data["missing_lines"], data.get("missing_branches", []))
                failed = True
    report.unlink()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
