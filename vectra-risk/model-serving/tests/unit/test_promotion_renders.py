"""Los cuatro PR de `promotion-tool` sobre el esquema de values (Paso 7; INF-U6-02; docs/values.md).

Cada cambio se aplica como lo describe `docs/values.md` (edicion de la lista `inferenceServices` del YAML), se renderiza el chart con
`helm` (que valida contra `values.schema.json`) y se comprueba el resultado: el cambio esperado, nada mas que cambie, y el activo nunca
con menos de 2 replicas. Los ejemplos del documento son lo que estas ediciones producen. Necesita `platform/install-tools.sh`."""

import copy
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from chart_helpers import ROOT, Doc, failures, helm, isvcs, of_kind, passes

DOCS = ROOT / "model-serving" / "docs" / "values.md"
M1 = "mv-2026-01-01-26300247"
M2 = "mv-2026-02-01-a1b2c3d4"
ISVC1, ISVC2 = "isvc-26300247", "isvc-a1b2c3d4"
Values = dict[str, Any]


def entry(version: str, profile: str) -> Values:
    return {"modelVersionId": version, "storageUri": f"s3://model-store/{version}/", "profile": profile}


def promote(values: Values, version: str) -> Values:
    """PR 1: agrega al final la version nueva con el perfil `prod`."""
    out = copy.deepcopy(values)
    out["inferenceServices"].append(entry(version, "prod"))
    return out


def demote(values: Values, version: str) -> Values:
    """PR 2: `prod` -> `inactive` en la entrada de la version anterior."""
    out = copy.deepcopy(values)
    (target,) = [
        e for e in out["inferenceServices"] if e["modelVersionId"] == version and e["profile"] == "prod"
    ]
    target["profile"] = "inactive"
    return out


def restore(values: Values, version: str) -> Values:
    """Rollback: `inactive` -> `prod` en la entrada de la version que se restaura."""
    out = copy.deepcopy(values)
    (target,) = [
        e for e in out["inferenceServices"] if e["modelVersionId"] == version and e["profile"] == "inactive"
    ]
    target["profile"] = "prod"
    return out


def retire(values: Values, version: str) -> Values:
    """PR 3: elimina la entrada de la version `inactive`."""
    out = copy.deepcopy(values)
    (target,) = [
        e for e in out["inferenceServices"] if e["modelVersionId"] == version and e["profile"] == "inactive"
    ]
    out["inferenceServices"].remove(target)
    return out


def render(values: Values, tmp_path: Path) -> list[Doc]:
    """El render que haria el PR: el archivo de values editado, a `helm template` (valida el esquema)."""
    path = tmp_path / "model-serving.yaml"
    path.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
    result = helm(path)
    assert result.returncode == 0, result.stderr
    docs = [d for d in yaml.safe_load_all(result.stdout) if d]
    assert passes(docs), failures(docs)
    return docs


def by_name(docs: list[Doc]) -> dict[str, list[Doc]]:
    """Los documentos de cada `InferenceService` (el suyo y los PDB `isvc-x-<componente>`)."""
    out: dict[str, list[Doc]] = {}
    for d in docs:
        if d["kind"] in {"InferenceService", "PodDisruptionBudget"}:
            key = re.match(r"isvc-[0-9a-f]{8}", d["metadata"]["name"])
            assert key
            out.setdefault(key.group(0), []).append(d)
    return out


def replicas(docs: list[Doc]) -> dict[str, tuple[int, int]]:
    return {
        c: (i["spec"][c]["minReplicas"], i["spec"][c]["maxReplicas"]) for i in isvcs(docs) for c in i["spec"]
    }


def assert_active_never_below_two(docs: list[Doc]) -> None:
    """Todo InferenceService de vectra-serving que no es `inactivo` tiene al menos 2 replicas por componente."""
    serving = [i for i in isvcs(docs) if i["metadata"]["namespace"] == "vectra-serving"]
    active = [i for i in serving if i["metadata"]["labels"].get("vectra.io/serving-state") != "inactivo"]
    assert active, "no hay ningun InferenceService activo"
    for isvc in active:
        assert all(isvc["spec"][c]["minReplicas"] >= 2 for c in ("predictor", "explainer")), isvc["metadata"][
            "name"
        ]


@pytest.fixture
def base() -> Values:
    return yaml.safe_load(
        (ROOT / "model-serving" / "tests" / "fixtures" / "values-base.yaml").read_text(encoding="utf-8")
    )  # type: ignore[no-any-return]


def example(name: str) -> Values:
    text = DOCS.read_text(encoding="utf-8")
    match = re.search(rf"<!-- ejemplo:{re.escape(name)} -->\n```yaml\n(.*?)```", text, re.DOTALL)
    assert match, f"falta el ejemplo {name} en docs/values.md"
    return yaml.safe_load(match.group(1))  # type: ignore[no-any-return]


def without_staging(values: Values) -> Values:
    return {"inferenceServices": [e for e in values["inferenceServices"] if e["profile"] != "staging"]}


def test_promocion_agrega_la_nueva_y_no_toca_el_activo(base: Values, tmp_path: Path) -> None:
    before = render(base, tmp_path)
    after_values = promote(base, M2)
    after = render(after_values, tmp_path)
    assert set(by_name(after)) == {ISVC1, ISVC2} and set(by_name(before)) == {ISVC1}
    assert by_name(after)[ISVC1] == by_name(before)[ISVC1]  # el activo, byte a byte igual
    assert replicas(after)["predictor"] == (2, 4) and replicas(after)["explainer"] == (2, 6)
    new = next(i for i in isvcs(after) if i["metadata"]["name"] == ISVC2)
    assert new["metadata"]["annotations"]["vectra.io/model-version-id"] == M2
    assert new["spec"]["predictor"]["priorityClassName"] == "vectra-high"
    assert_active_never_below_two(after)
    assert without_staging(after_values) == example("promocion:despues")


def test_post_activacion_baja_el_anterior_y_deja_el_nuevo_con_sus_minimos(
    base: Values, tmp_path: Path
) -> None:
    promoted = promote(base, M2)
    before = render(promoted, tmp_path)
    values = demote(promoted, M1)
    after = render(values, tmp_path)
    old = next(
        i
        for i in isvcs(after)
        if i["metadata"]["name"] == ISVC1 and i["metadata"]["namespace"] == "vectra-serving"
    )
    assert (
        old["metadata"]["labels"]["vectra.io/serving-state"] == "inactivo"
        and old["metadata"]["annotations"]["vectra.io/hpa-exempt"]
    )
    assert [
        old["spec"][c][k] for c in ("predictor", "explainer") for k in ("minReplicas", "maxReplicas")
    ] == [1, 1, 1, 1]
    assert not [d for d in of_kind(after, "PodDisruptionBudget") if d["metadata"]["name"].startswith(ISVC1)]
    assert by_name(after)[ISVC2] == by_name(before)[ISVC2]  # el nuevo no cambia
    assert_active_never_below_two(after)
    assert without_staging(values) == example("post-activacion:despues")


def test_rollback_restaura_los_minimos_antes_de_mark_active(base: Values, tmp_path: Path) -> None:
    inactive_m1 = demote(promote(base, M2), M1)
    before = render(inactive_m1, tmp_path)
    values = restore(inactive_m1, M1)
    after = render(values, tmp_path)
    restored = next(
        i
        for i in isvcs(after)
        if i["metadata"]["name"] == ISVC1 and i["metadata"]["namespace"] == "vectra-serving"
    )
    assert "vectra.io/serving-state" not in restored["metadata"]["labels"]
    assert "vectra.io/hpa-exempt" not in restored["metadata"]["annotations"]
    assert [
        restored["spec"][c][k] for c in ("predictor", "explainer") for k in ("minReplicas", "maxReplicas")
    ] == [2, 4, 2, 6]
    assert {
        d["metadata"]["name"]
        for d in of_kind(after, "PodDisruptionBudget")
        if d["metadata"]["name"].startswith(ISVC1)
    } == {
        f"{ISVC1}-predictor",
        f"{ISVC1}-explainer",
    }
    assert by_name(after)[ISVC2] == by_name(before)[ISVC2]  # M2 sigue como estaba hasta `mark_active`
    assert_active_never_below_two(after)
    assert without_staging(values) == example("rollback:despues")
    # el PR de post-activacion que sigue a `mark_active` de M1 baja a M2
    final = render(demote(values, M2), tmp_path)
    assert_active_never_below_two(final)
    assert replicas(
        [
            i
            for i in isvcs(final)
            if i["metadata"]["name"] == ISVC1 and i["metadata"]["namespace"] == "vectra-serving"
        ]
    )["predictor"] == (2, 4)


def test_retiro_quita_solo_el_inactivo(base: Values, tmp_path: Path) -> None:
    inactive_m1 = demote(promote(base, M2), M1)
    before = render(inactive_m1, tmp_path)
    values = retire(inactive_m1, M1)
    after = render(values, tmp_path)
    assert ISVC1 in by_name(before) and set(by_name(after)) == {ISVC2} | (
        {ISVC1} if any(i["metadata"]["namespace"] == "vectra-staging" for i in isvcs(after)) else set()
    )
    assert not [
        i
        for i in isvcs(after)
        if i["metadata"]["name"] == ISVC1 and i["metadata"]["namespace"] == "vectra-serving"
    ]
    assert [d for d in by_name(after)[ISVC2]] == by_name(before)[ISVC2]
    assert_active_never_below_two(after)
    assert without_staging(values) == example("retiro:despues")


def test_secuencia_completa_promocion_activacion_rollback_y_retiro(base: Values, tmp_path: Path) -> None:
    values = base
    for step in (
        lambda v: promote(v, M2),
        lambda v: demote(v, M1),
        lambda v: restore(v, M1),
        lambda v: demote(v, M2),
        lambda v: retire(v, M2),
    ):
        values = step(values)
        assert_active_never_below_two(render(values, tmp_path))
    assert without_staging(values) == {"inferenceServices": [entry(M1, "prod")]}


def test_los_ejemplos_del_documento_parten_del_mismo_estado_inicial(base: Values) -> None:
    assert without_staging(base) == example("promocion:antes")


def test_los_ejemplos_del_documento_renderizan(tmp_path: Path) -> None:
    for name in (
        "promocion:antes",
        "promocion:despues",
        "post-activacion:despues",
        "rollback:despues",
        "retiro:despues",
    ):
        render(example(name), tmp_path)


@pytest.mark.parametrize(
    "bad",
    [
        {"inferenceService": []},  # clave de mas por un error de tipeo
        {"inferenceServices": [{**entry(M2, "prod"), "replicas": 1}]},  # campo inventado
        {"inferenceServices": [entry(M2, "canary")]},  # perfil que no existe
        {"inferenceServices": [{**entry(M2, "prod"), "modelVersionId": "26300247"}]},
        {"inferenceServices": [{"modelVersionId": M2, "profile": "prod"}]},  # sin storageUri
        {"inferenceServices": [{**entry(M2, "prod"), "storageUri": "s3://otro-bucket/x/"}]},
        {
            "inferenceServices": [entry(M2, "prod"), entry(M2, "inactive")]
        },  # misma version dos veces en vectra-serving
    ],
)
def test_un_values_que_viola_el_esquema_no_se_renderiza(bad: Values, tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    assert helm(path).returncode != 0
