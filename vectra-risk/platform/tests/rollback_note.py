#!/usr/bin/env python3
"""La nota de rollback del PR es obligatoria (NFR-U1-44). Lee el cuerpo de $BODY o de un archivo."""

import os
import re
import sys
from pathlib import Path

#: Un comentario sin cerrar tambien oculta el resto en GitHub.
COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
HEADING = re.compile(r"^#{1,2}\s+(.*?)\s*#*\s*$")


def has_rollback_note(body: str) -> bool:
    """True si la seccion `## Rollback` tiene texto visible."""
    inside = False
    for line in COMMENT.sub("", body).splitlines():
        heading = HEADING.match(line)
        if heading:
            inside = heading.group(1).strip().lower() == "rollback"
        elif inside and line.strip():
            return True
    return False


def main(argv: list[str]) -> int:
    body = Path(argv[0]).read_text(encoding="utf-8") if argv else os.environ.get("BODY", "")
    if has_rollback_note(body):
        return 0
    print("El PR no tiene nota de rollback: llena la seccion `## Rollback` (NFR-U1-44)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
