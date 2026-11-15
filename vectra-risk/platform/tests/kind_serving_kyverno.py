#!/usr/bin/env python3
"""`require-hpa-bounds` (Kyverno) sobre los `InferenceService` que el chart de U6 rinde en kind con los InferenceService del pico de D2 (U01-T12 CA-2).

Necesita el binario `kyverno` de `platform/.tools/bin`, que el job `tests` de la CI no instala: por eso no es una prueba de pytest sino un paso de `make check-tools`
(como `rego_fixtures.py`), que la CI corre con las herramientas. Falla (rc 1) si Kyverno falla, no existe o no evalua nada: no se salta en silencio.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_kind_profile as kind  # noqa: E402

KYVERNO = kind.PLATFORM / ".tools/bin/kyverno"
POLICY = kind.PLATFORM / "policies/kyverno/require-hpa-bounds.yaml"


def main() -> int:
    if not KYVERNO.is_file():
        print(f"falta {KYVERNO}: corre platform/install-tools.sh", file=sys.stderr)
        return 1
    documents = kind.inference_services(kind.PEAK_INFERENCE_SERVICES)
    if not documents:
        print("el chart de U6 no rindio ningun InferenceService en kind", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as folder:
        resource = Path(folder) / "inference-services.yaml"
        resource.write_text(yaml.safe_dump_all(documents), encoding="utf-8")
        result = subprocess.run([str(KYVERNO), "apply", str(POLICY), "--resource", str(resource)], capture_output=True, text=True, check=False)  # noqa: S603
    output = result.stdout + result.stderr
    print(output)
    return 0 if result.returncode == 0 and "fail: 0, warn: 0, error: 0" in output and "pass: 0," not in output else 1


if __name__ == "__main__":
    sys.exit(main())
