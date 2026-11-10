"""El runbook de la politica de referencia se ejecuta tal cual (U04-T06 ronda 2, F-01 a F-05; U04-T07).

Todas las pruebas leen el archivo de `RUNBOOK` (por omision, `runbooks/kind-politica-de-referencia.md`), de modo que se pueden correr contra
una variante. La prueba distingue lo que corre en el pod (un bloque `python` que empieza con `# corre en el pod`) de lo que corre en la
maquina del operador (todo bloque `bash` y cualquier otro `python`).
"""

import ast
import os
import re
import subprocess
from pathlib import Path

import pytest

GOVERNANCE = Path(__file__).resolve().parents[2]
DEFAULT = GOVERNANCE / "runbooks" / "kind-politica-de-referencia.md"
FENCE = re.compile(r"^```(\S*)\n(.*?)^```", re.S | re.M)
SHELL_FENCES = {"sh", "shell", "zsh", "ksh", "fish", "console", "terminal"}
ALLOWED_FENCES = {"bash", "python", "text", "json"}
POD = "# corre en el pod"
# Un nombre que solo resuelve dentro del cluster: `*.svc`, `*.cluster.local` o un nombre corto `<servicio>.vectra-<ns>`.
INTERNAL = re.compile(r"\.svc\b|\.cluster\.local\b|\b[a-z][a-z0-9-]*\.vectra-[a-z-]+\b")
CREATE = re.compile(r"kubectl\b[^\n]*?\bcreate\s+(\w+)\s+([\w-]+)")
TMP_WRITE = re.compile(r"(?:>>?|-o|--output)\s*(/tmp/[\w./-]+)")


def fences(text: str) -> list[tuple[str, str]]:
    return FENCE.findall(text)


def blocks(text: str) -> list[str]:
    """Los bloques `bash`: lo que el operador pega en su maquina."""
    return [body for lang, body in fences(text) if lang == "bash"]


def problems(text: str) -> list[str]:
    found = []
    if "REEMPLAZA_POR" in text:
        found.append("lleva un marcador REEMPLAZA_POR_...: el comando debe obtener el valor (F-04)")
    shell = [body for lang, body in fences(text) if lang == "bash"]
    for lang, body in fences(text):
        if lang in SHELL_FENCES or lang not in ALLOWED_FENCES:
            found.append(f"cerco `{lang or '(sin lenguaje)'}`: solo `bash`, `python`, `text` y `json`; otro cerco esconde comandos a esta prueba")
        if lang in {"bash", "python"}:
            if "…" in body or "..." in body:
                found.append(f"bloque {lang}: lleva «…» o «...» (comando incompleto)")
            if lang == "python":
                try:
                    ast.parse(body)
                except SyntaxError as error:
                    found.append(f"bloque python: sintaxis invalida ({error.msg})")
        in_pod = lang == "python" and body.lstrip().startswith(POD)
        if lang in {"bash", "python"} and not in_pod and INTERNAL.search(body):
            found.append(f"bloque {lang}: usa un nombre interno del cluster fuera del pod (cliente en local, `bash <<EOF` o nombre corto)")
        if in_pod and "Bearer" in body and "sys.stdin" not in body:
            found.append("cliente del pod: el token no sale de stdin")
    for index, block in enumerate(shell, 1):
        if re.search(r"\bcurl\b", block):
            found.append(f"bloque bash {index}: usa curl (la imagen del pod no lo trae)")
        if re.search(r"create\s+secret|kind:\s*Secret|--from-literal", block):
            found.append(f"bloque bash {index}: crea un Secret a mano (`disallow-plain-secrets` lo rechaza; F-01): el token va por stdin")
        if re.search(r"\bexport\s+\w*TOKEN|\bTOKEN\w*=|\$\{?TOKEN|Bearer\s|--token", block):
            found.append(f"bloque bash {index}: el token pasa por una variable, un argumento o el historial (F-04)")
    found += order_problems(shell)
    return found


def order_problems(shell: list[str]) -> list[str]:
    """La verificacion (`GET /v1/policies`) va antes de la limpieza (la ultima orden `delete`), y la limpieza borra todo lo que se creo (F-02, F-05)."""
    found = []
    verify = next((i for i, b in enumerate(shell) if re.search(r"GET\s+/v1/policies", b)), None)
    cleanup = next((i for i in range(len(shell) - 1, -1, -1) if re.search(r"\bdelete\b", shell[i])), None)
    if verify is None or cleanup is None:
        return ["falta la verificacion `GET /v1/policies` o la limpieza (`delete`)"]
    if verify > cleanup:
        found.append("la verificacion va despues de la limpieza (F-02)")
    created = [(kind, name) for block in shell for kind, name in CREATE.findall(block) if "--rm" not in block]
    temporary = [path for block in shell for path in TMP_WRITE.findall(block)]
    for kind, name in created:
        if not re.search(rf"\bdelete\b[^\n]*\b{kind}\b[^\n]*\b{re.escape(name)}\b", shell[cleanup]):
            found.append(f"la limpieza no borra {kind} {name}")
    for path in temporary:
        if not re.search(rf"\brm\b[^\n]*{re.escape(path)}", shell[cleanup]):
            found.append(f"la limpieza no borra {path} (F-05)")
    return found


def runbook() -> str:
    return Path(os.environ.get("RUNBOOK", DEFAULT)).read_text(encoding="utf-8")


GOOD = """# R

```bash
kubectl --context kind-vectra -n vectra-app get serviceaccount console-bff
```

```bash
governance/docs/kind/token.sh cro-2 | governance/docs/kind/llamar.sh politica-lee GET /v1/policies
```

```bash
kubectl --context kind-vectra -n vectra-app delete serviceaccount console-bff
```
"""

LOCAL_CLIENT = "```python\nimport urllib.request\nurllib.request.urlopen('http://governance-service.vectra-app.svc.cluster.local:8080/v1/policies')\n```\n"
VARIANTS = {
    "cliente en local con hosts internos": GOOD + LOCAL_CLIENT + "```bash\npython3 cliente.py\n```\n",
    "bash heredoc con hosts internos": GOOD + "```bash\nbash <<EOF\ncurl_no http://governance-service.vectra-app.svc.cluster.local:8080/v1/policies\nEOF\n```\n",
    "nombre corto": GOOD + "```bash\nkubectl run x -- python -c 'print(1)' http://governance-service.vectra-app:8080/v1/policies\n```\n",
    "cerco sh": GOOD + "```sh\nkubectl --context kind-vectra -n vectra-app delete pod x\n```\n",
    "puntos suspensivos": GOOD + "```bash\nkubectl get pods …\n```\n",
    "marcador REEMPLAZA_POR": GOOD + "```bash\nexport DIGEST=sha256:REEMPLAZA_POR_EL_DIGEST\n```\n",
    "secret a mano": GOOD + "```bash\nkubectl -n vectra-app create secret generic t --from-literal=token=x\n```\n",
    "token exportado": GOOD + "```bash\nexport TOKEN_CRO2=abc\n```\n",
    "verificacion despues de la limpieza": GOOD.replace("GET /v1/policies", "GET /v1/models") + "```bash\nllamar.sh x GET /v1/policies\n```\n",
    "archivo temporal sin borrar": GOOD + "```bash\ncat > /tmp/llamar.py <<'EOF'\nprint(1)\nEOF\n```\n",
}


def test_el_buen_runbook_de_control_no_tiene_problemas() -> None:
    assert problems(GOOD) == []


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_la_prueba_detecta_cada_variante_mala(name: str) -> None:
    assert problems(VARIANTS[name]) != [], name


def test_el_runbook_no_tiene_problemas() -> None:
    assert blocks(runbook()), "el runbook no tiene bloques de comandos"
    assert problems(runbook()) == []


def test_cada_bloque_tiene_sintaxis_de_bash_valida() -> None:
    for index, block in enumerate(blocks(runbook()), 1):
        result = subprocess.run(["bash", "-n"], input=block, capture_output=True, text=True, check=False)  # noqa: S603, S607
        assert result.returncode == 0, f"bloque {index}: {result.stderr}"


def test_el_runbook_nombra_la_service_account_y_a_cro_2_y_cro_1() -> None:
    text = runbook()
    assert "create serviceaccount console-bff" in text and "no va en ningún chart" in text
    assert "cro-2" in text and "cro-1" in text and "ingeniero-1" not in text


def test_los_scripts_que_nombra_el_runbook_existen_y_son_ejecutables() -> None:
    named = set(re.findall(r"governance/docs/kind/[\w.-]+\.sh", runbook()))
    assert named, "el runbook usa los scripts de governance/docs/kind/ para el token y las llamadas"
    for script in named:
        path = GOVERNANCE.parent / script
        assert path.is_file() and os.access(path, os.X_OK), script
