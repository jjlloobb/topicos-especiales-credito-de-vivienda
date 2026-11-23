"""Carpetas de Grafana: una sola fuente (`folder-permissions.yaml`) para permisos, proveedores y anotaciones.

El defecto que esto impide (kind, 2026-11-22: 43 819 carpetas): con `foldersFromFilesStructure`, la anotacion
`grafana_folder: "Vectra / Operación"` se volvia los directorios `Vectra ` y ` Operación`. Grafana 13.3.0 guarda el
titulo recortado y busca la carpeta por el nombre sin recortar: no la encuentra y crea otra cada vez que el sidecar
reescribe un tablero. Un proveedor por carpeta, con UID fijo, no crea carpetas a partir de directorios.
"""

import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
VALUES = ROOT / "platform/observability/values/kube-prometheus-stack.yaml"
PERMISSIONS = ROOT / "platform/observability/grafana/folder-permissions.yaml"
KUSTOMIZATION = ROOT / "platform/observability/dashboards/kustomization.yaml"
CHART = ROOT / "platform/.charts/kube-prometheus-stack/kube-prometheus-stack"


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def grafana_values():
    return load(VALUES)["grafana"]


def sidecar():
    return grafana_values()["sidecar"]["dashboards"]


def providers():
    files = grafana_values().get("dashboardProviders", {})
    return [provider for file in files.values() for provider in file["providers"]]


def permission_folders():
    return {folder["uid"]: folder["title"] for folder in load(PERMISSIONS)["folders"]}


def annotated_folders():
    """Cada valor de la anotacion de carpeta que el repositorio despliega, con el archivo que lo declara."""
    annotation = sidecar()["folderAnnotation"]
    found = []
    for generator in load(KUSTOMIZATION)["configMapGenerator"]:
        value = generator.get("options", {}).get("annotations", {}).get(annotation)
        found.append((f"{KUSTOMIZATION.relative_to(ROOT)}:{generator['name']}", value))
    for values in sorted([*ROOT.glob("*/chart/values.yaml"), *ROOT.glob("*/chart/*/values.yaml")]):
        dashboard = (load(values) or {}).get("dashboard")
        if isinstance(dashboard, dict) and "folder" in dashboard:
            found.append((str(values.relative_to(ROOT)), dashboard["folder"]))
    return found


def padded_segments(folder):
    """Los tramos de la ruta que Grafana recortaria al titular la carpeta: asi nace la carpeta duplicada."""
    return [segment for segment in folder.split("/") if segment != segment.strip() or not segment]


def test_padded_segments_names_the_defect():
    assert padded_segments("Vectra / Operación") == ["Vectra ", " Operación"]
    assert padded_segments("Vectra/Operación") == []
    assert padded_segments("Vectra Operación") == []
    assert padded_segments("Operación ") == ["Operación "]
    assert padded_segments("Vectra//Operación") == [""]


def test_no_provider_builds_folders_from_the_directory_tree():
    dashboards = sidecar()
    assert dashboards.get("SCProvider") is False, "el proveedor unico del chart barre todo /tmp/dashboards"
    assert not dashboards.get("provider", {}).get("foldersFromFilesStructure")
    for provider in providers():
        assert provider["options"].get("foldersFromFilesStructure") is False, provider["name"]


def test_folder_annotations_have_no_padded_segments_if_folders_ever_come_from_directories():
    """Si alguien vuelve a `foldersFromFilesStructure`, ninguna anotacion puede tener espacios junto a la barra."""
    from_tree = sidecar().get("provider", {}).get("foldersFromFilesStructure") or any(
        provider["options"].get("foldersFromFilesStructure") for provider in providers()
    )
    if from_tree:
        bad = {source: value for source, value in annotated_folders() if padded_segments(value or "")}
        assert not bad, bad


def test_the_repository_declares_dashboards_in_folders():
    found = annotated_folders()
    assert len(found) >= 5, found  # cuatro tableros de U1 y el de U11
    assert all(value for _, value in found), found


def test_every_provider_is_a_folder_of_the_permissions_job():
    """Mismo `uid` y `title` que `folder-permissions.yaml`: el tablero queda en la carpeta con permisos (F110)."""
    folders = permission_folders()
    declared = providers()
    assert declared
    for provider in declared:
        uid = provider["folderUid"]
        assert folders.get(uid) == provider["folder"], f"{provider['name']}: {uid} no es {provider['folder']!r}"
        assert provider["type"] == "file" and provider["orgId"] == 1
        assert provider["disableDeletion"] is False and provider["allowUiUpdates"] is False
    for key in ("name", "folderUid", "folder"):
        values = [provider[key] for provider in declared]
        assert len(values) == len(set(values)), f"{key} repetido: {values}"
    paths = [provider["options"]["path"] for provider in declared]
    assert not [(a, b) for a in paths for b in paths if a != b and b.startswith(a.rstrip("/") + "/")], paths


def test_every_annotated_folder_has_exactly_one_provider_on_the_sidecar_directory():
    """El sidecar escribe en `<folder>/<anotacion>`; sin un proveedor en esa ruta, Grafana no carga el tablero."""
    base = sidecar().get("folder", "/tmp/dashboards")  # noqa: S108 - el valor por omision del chart
    by_title = {provider["folder"]: provider for provider in providers()}
    for source, value in annotated_folders():
        assert value in by_title, f"{source}: falta un proveedor en `dashboardProviders` para {value!r}"
        assert by_title[value]["options"]["path"] == f"{base}/{value}", source
        assert value in permission_folders().values(), f"{source}: {value!r} no esta en folder-permissions.yaml"


def test_folder_uids_and_titles_are_unique_and_trimmed():
    folders = load(PERMISSIONS)["folders"]
    assert len({f["uid"] for f in folders}) == len(folders) == len({f["title"] for f in folders})
    assert all(f["title"] == f["title"].strip() and f["uid"] == f["uid"].strip() for f in folders)


@pytest.fixture(scope="module")
def rendered():
    assert CHART.is_dir(), f"Falta {CHART}: corre `make -C platform charts`"
    command = ["helm", "template", "kube-prometheus-stack", str(CHART), "--namespace", "vectra-observability"]
    result = subprocess.run([*command, "--skip-tests", "-f", str(VALUES)], check=True, capture_output=True, text=True)
    return [d for d in yaml.safe_load_all(result.stdout) if d]


def test_rendered_grafana_mounts_only_our_providers(rendered):
    """Una clave mal escrita en los values se ignora en silencio: se comprueba lo que el chart renderiza."""
    config = next(
        d for d in rendered if d["kind"] == "ConfigMap" and d["metadata"]["name"] == "kube-prometheus-stack-grafana"
    )
    files = {key: yaml.safe_load(text) for key, text in config["data"].items() if key.endswith("providers.yaml")}
    assert [p for file in files.values() for p in file["providers"]] == providers()
    assert not [d for d in rendered if d["metadata"]["name"].endswith("-config-dashboards")]

    deployment = next(d for d in rendered if d["kind"] == "Deployment" and d["metadata"]["name"].endswith("grafana"))
    containers = {c["name"]: c for c in deployment["spec"]["template"]["spec"]["containers"]}
    mounts = {m["mountPath"]: m for m in containers["grafana"]["volumeMounts"]}
    provisioned = [path for path in mounts if path.startswith("/etc/grafana/provisioning/dashboards")]
    assert provisioned == [f"/etc/grafana/provisioning/dashboards/{key}" for key in files]
    base = sidecar().get("folder", "/tmp/dashboards")  # noqa: S108
    assert mounts[base]["name"] == "sc-dashboard-volume"

    env = {e["name"]: e.get("value") for e in containers["grafana-sc-dashboard"]["env"]}
    assert env["FOLDER"] == base and env["FOLDER_ANNOTATION"] == sidecar()["folderAnnotation"]
    assert env["LABEL"] == sidecar()["label"] and env["NAMESPACE"] == "ALL"
