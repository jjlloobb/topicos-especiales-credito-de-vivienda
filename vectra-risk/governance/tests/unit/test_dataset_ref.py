"""El `datasetRef` de kind es un objeto que el Job lee y la misma ruta a la que U5 sube el dataset (U04-T10; CA-1 a CA-3).

Toma el valor **renderizado** del chart con los `valueFiles` de la Application de kind y lo pasa por el analizador de URI real del lector
del Job. El diseño fija un solo dataset de validacion (U5 `domain-entities` §2; U4 `dataset_ref` del servicio, el mismo para `validacion`
y `source_comparison`, BR-U4-05): la ruta es un value fijo, no una por version.
"""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from vectra_validation.errors import ValidationJobError
from vectra_validation.s3 import S3Reader

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / "governance" / "chart"
APP = ROOT / "vectra-risk-gitops" / "apps" / "kind" / "governance.yaml"
RELEASE = ROOT / "reference-model" / "docs" / "release.md"
TOOLS_HELM = ROOT / "platform" / ".tools" / "bin" / "helm"
ENV = "GOVERNANCE_VALIDATION_DATASET"


def helm_bin() -> str:
    found = str(TOOLS_HELM) if TOOLS_HELM.is_file() else shutil.which("helm")
    assert found, "falta helm: corre platform/install-tools.sh"
    return found


def kind_value_files() -> list[str]:
    app = yaml.safe_load(APP.read_text(encoding="utf-8"))
    files = app["spec"]["source"]["helm"]["valueFiles"]
    return [str(ROOT / f.removeprefix("/vectra-risk/")) for f in files]


def helm(*sets: str) -> subprocess.CompletedProcess[str]:
    args = [helm_bin(), "template", "governance", str(CHART)]
    for f in kind_value_files():
        args += ["-f", f]
    for s in sets:
        args += ["--set", s]
    return subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603


def rendered_dataset_ref(*sets: str) -> str:
    result = helm(*sets)
    assert result.returncode == 0, result.stderr
    for doc in yaml.safe_load_all(result.stdout):
        if not doc or doc.get("kind") != "Deployment":
            continue
        for container in doc["spec"]["template"]["spec"]["containers"]:
            for env in container.get("env", []):
                if env["name"] == ENV:
                    value: str = env["value"]
                    return value
    raise AssertionError(f"el render no trae {ENV}")


def job_reader_accepts(uri: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"data")

    reader = S3Reader("http://minio:9000", "validation-readonly", "s3cret", transport=httpx.MockTransport(handler))
    assert reader.read(uri) == b"data"


def test_the_dataset_ref_rendered_for_kind_is_an_object_the_job_reader_accepts() -> None:
    job_reader_accepts(rendered_dataset_ref())


def test_the_job_reader_rejects_a_bare_bucket() -> None:
    with pytest.raises(ValidationJobError, match="object_uri_invalid"):
        job_reader_accepts("s3://validation-datasets")


def release_doc_upload_target() -> str:
    """El destino de la orden `mc cp` del dataset en `release.md`, como `s3://bucket/clave`."""
    text = RELEASE.read_text(encoding="utf-8")
    found = re.findall(r"^mc cp\s+\S*validation\.parquet\s+\"?kind/([^\"\s]+)\"?\s*$", text, re.M)
    assert len(found) == 1, f"release.md debe tener una sola orden `mc cp` del dataset de validacion: {found}"
    return f"s3://{found[0]}"


def test_release_doc_uploads_the_dataset_to_the_path_the_chart_renders() -> None:
    assert release_doc_upload_target() == rendered_dataset_ref()


def test_release_doc_check_step_reads_the_same_object() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    target = release_doc_upload_target().removeprefix("s3://")
    assert f'mc cat "kind/{target}"' in text


@pytest.mark.parametrize("bad", ["s3://validation-datasets", "s3://validation-datasets/", "https://minio/validation-datasets/v.parquet", "validation.parquet"])
def test_a_dataset_ref_without_an_object_is_not_deployed(bad: str) -> None:
    result = helm(f"validation.datasetRef={bad}")
    assert result.returncode != 0
    assert "validation.datasetRef" in result.stderr


def test_a_dataset_ref_with_an_object_is_deployed() -> None:
    assert rendered_dataset_ref() == "s3://validation-datasets/validation.parquet"
    assert rendered_dataset_ref("validation.datasetRef=s3://validation-datasets/otro/validation.parquet").endswith("otro/validation.parquet")


def test_no_other_chart_value_overrides_the_dataset_ref_for_kind() -> None:
    values: dict[str, Any] = {}
    for f in kind_value_files():
        values.update(yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {})
    assert "datasetRef" not in (values.get("validation") or {}), "kind debe usar el valor del chart: una sola ruta"
