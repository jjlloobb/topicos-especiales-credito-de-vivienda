"""El runbook de la politica de referencia se ejecuta tal cual (U04-T06, ronda 2, F-02): sus bloques de comandos no llevan «…» ni «...»,
no usan `curl` (la imagen del pod trae Python), tienen sintaxis valida de `bash` y los nombres internos del cluster (`*.svc.cluster.local`) solo
aparecen dentro del cliente que corre en el pod (el cuerpo de un heredoc), nunca en un comando del operador en su maquina.
"""

import os
import re
import subprocess
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[2] / "runbooks" / "kind-politica-de-referencia.md"
BLOCK = re.compile(r"```bash\n(.*?)```", re.S)
HEREDOC = re.compile(r"<<'?(\w+)'?\n.*?\n\1\n", re.S)
INTERNAL = re.compile(r"\.svc(\.cluster\.local)?\b|\.svc\.")


def blocks(text: str) -> list[str]:
    return BLOCK.findall(text)


def problems(text: str) -> list[str]:
    found = []
    for index, block in enumerate(blocks(text), 1):
        if "…" in block or "..." in block:
            found.append(f"bloque {index}: lleva «…» o «...» (comando incompleto)")
        if re.search(r"\bcurl\b", block):
            found.append(f"bloque {index}: usa curl (la imagen del pod no lo trae)")
        outside = HEREDOC.sub("", block)
        if INTERNAL.search(outside):
            found.append(f"bloque {index}: usa un nombre interno del cluster fuera del pod")
    return found


def test_el_runbook_no_tiene_comandos_elididos_ni_hosts_internos_en_la_maquina_del_operador() -> None:
    path = Path(os.environ.get("RUNBOOK", DEFAULT))
    assert blocks(path.read_text(encoding="utf-8")), "el runbook no tiene bloques de comandos"
    assert problems(path.read_text(encoding="utf-8")) == []


def test_la_prueba_detecta_el_runbook_anterior() -> None:
    old = "```bash\ncurl -s http://governance-service.vectra-app.svc.cluster.local:8080/v1/policies\n… curl -s -X POST x\n```"
    assert len(problems(old)) >= 3


def test_cada_bloque_tiene_sintaxis_de_bash_valida() -> None:
    for index, block in enumerate(blocks(DEFAULT.read_text(encoding="utf-8")), 1):
        result = subprocess.run(["bash", "-n"], input=block, capture_output=True, text=True, check=False)  # noqa: S603, S607
        assert result.returncode == 0, f"bloque {index}: {result.stderr}"


def test_el_runbook_nombra_la_service_account_y_a_cro_2_y_cro_1() -> None:
    text = DEFAULT.read_text(encoding="utf-8")
    assert "create serviceaccount console-bff" in text and "no va en ningún chart" in text
    assert "cro-2" in text and "cro-1" in text and "ingeniero-1" not in text
