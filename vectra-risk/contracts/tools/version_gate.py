"""BR-U0-91, 92: un cambio incompatible exige subir la version mayor."""

import argparse
import shutil
import subprocess
import sys


def major(version: str) -> int:
    return int(version.split(".")[0])


def breaking(base: str, head: str, oasdiff: str = "oasdiff") -> int:
    """Invoca `oasdiff breaking` y propaga su codigo de salida."""
    return subprocess.run([oasdiff, "breaking", "--fail-on", "ERR", base, head], check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base-version", required=True)
    parser.add_argument("--head-version", required=True)
    parser.add_argument("--oasdiff", default="oasdiff")
    args = parser.parse_args(argv)
    if shutil.which(args.oasdiff) is None:
        print(f"no se encontro {args.oasdiff}")
        return 2
    code = breaking(args.base, args.head, args.oasdiff)
    if code != 0 and major(args.head_version) <= major(args.base_version):
        print("cambio incompatible sin subir la version mayor (BR-U0-91)")
        return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
