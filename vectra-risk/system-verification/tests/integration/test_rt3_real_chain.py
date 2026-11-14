"""CA-16 (U12-T03, P-6 (a)): RT-3 y `rt2-setup` contra **governance real**: el BFF real en proceso encadenado a la app real de governance sobre PostgreSQL de Testcontainers, y los paquetes de
`vectra_reference.adversarial.rt3_package` sobre un paquete real chico (`run_release` con 6 000 filas, como `governance/tests/integration/conftest.py`).

Es la prueba de la leccion de la enmienda §8 para D1: lo que el oraculo espera (422 con `invalid_params`, 409 de RT3-b) es lo que governance produce, no lo que un doble supone.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from external_paths import use_governance_doubles
from fake_clock import FakeClock
from rt2_world import TAG, WorldOidc, make_package  # noqa: F401
from u5_delivery import SCRATCH

use_governance_doubles()
import governance_pg  # noqa: E402
from real_chain import RealChain  # noqa: E402
from vectra_reference.adversarial import REJECTED_BY_U4, rt3_package  # noqa: E402
from vectra_reference.generate import load_config, with_overrides  # noqa: E402
from vectra_reference.release import run_release  # noqa: E402

from vectra_verification import guard  # noqa: E402
from vectra_verification.scenarios import rt2, rt3  # noqa: E402
from vectra_verification.scenarios.common import Sessions, list_all_models, package_version, snapshot  # noqa: E402

pytestmark = pytest.mark.integration

PREFIX = {"RT3-a": "rt3-a", "RT3-c": "rt3-c", "RT3-d": "rt3-d", "RT3-b": "rt3-b"}


@pytest.fixture(scope="module")
def package_dir() -> Iterator[Path]:
    """El paquete real de U5 (una entrega chica, 6 000 filas) dentro del worktree, no en `/tmp`."""
    directory = SCRATCH.parent / "u12t03" / f"u5-pkg-{os.getpid()}"
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    try:
        yield run_release(
            directory, with_overrides(load_config(), n_rows=6000), enforce_min_auc=False
        ).package_dir
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture(scope="module")
def gov_template(pg: Any) -> str:
    governance_pg.create_roles(pg)
    name = "governance_template_u12t03"
    governance_pg.create_database(pg, name)
    governance_pg.migrate(pg, name)
    return name


@pytest.fixture
def chain(pg: Any, gov_template: str) -> Iterator[RealChain]:
    import uuid

    name = "t_" + uuid.uuid4().hex[:12]
    governance_pg.create_database(pg, name, gov_template)
    built = RealChain(governance_pg.Db(pg, name))
    yield built
    built.close()
    governance_pg.drop_database(pg, name)


class Holder:
    """Lo que `WorldOidc` necesita de un mundo: un reloj."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock


@pytest.fixture
def sessions(chain: RealChain, dynamic_environment: guard.Environment) -> Sessions:
    clock = FakeClock()
    return Sessions(
        dynamic_environment, WorldOidc(Holder(clock)), clock, TAG, transport=chain.transport, verify=False
    )  # type: ignore[arg-type]


def rt3_packages(chain: RealChain, package_dir: Path, tmp_path: Path) -> dict[str, rt3.Rt3Package]:
    out: dict[str, rt3.Rt3Package] = {}
    for case_id in (*REJECTED_BY_U4, "RT3-b"):
        target = tmp_path / case_id
        rt3_package(case_id, package_dir, target)
        chain.add_package(PREFIX[case_id], target)
        out[case_id] = rt3.Rt3Package(case_id, target, PREFIX[case_id])
    return out


def run_for(sessions: Sessions, environment: guard.Environment) -> rt3.Rt3Run:
    deps = rt3.Rt3Deps(environment, sessions._clock, sessions, None, None)  # type: ignore[arg-type]
    return rt3.Rt3Run(deps, rt3.Rt3Params({}, 1))


def test_rt3_real_chain_a_c_and_d_are_422_with_the_reason_of_the_table_and_the_models_do_not_change(
    chain: RealChain,
    sessions: Sessions,
    dynamic_environment: guard.Environment,
    package_dir: Path,
    tmp_path: Path,
) -> None:
    packages = rt3_packages(chain, package_dir, tmp_path)
    chain.add_package(package_version(package_dir), package_dir)
    sessions.write(
        "ingeniero-1", lambda c: c.register_model(rt2.registration_body(package_dir))
    )  # el modelo base, registrado como en kind
    reader = sessions.reader("ingeniero-1")
    before = snapshot(list_all_models(reader))
    assert before == {package_version(package_dir): "registrado"}
    run = run_for(sessions, dynamic_environment)
    results = {case_id: run.register(packages[case_id]) for case_id in REJECTED_BY_U4}
    after = snapshot(list_all_models(reader))
    for case_id, reading in results.items():
        assert (reading.status, reading.code) == (422, "validation_error"), (case_id, reading)
        assert reading.invalid_params == (("package", rt3.EXPECTED_REASON[case_id]),), (case_id, reading)
        assert rt3.judge_registration(case_id, reading).result == "pasa"
    assert (
        rt3.judge_unchanged(before, after, rt3.active_model(before), rt3.active_model(after)).result == "pasa"
    )
    assert (
        chain.state(package_version(package_dir)) == "registrado"
        and len(chain.api.sql("SELECT 1 FROM model_versions")) == 1
    )


def test_rt3_real_chain_rt3b_with_the_base_model_unregistered_is_200_and_registrado(
    chain: RealChain,
    sessions: Sessions,
    dynamic_environment: guard.Environment,
    package_dir: Path,
    tmp_path: Path,
) -> None:
    packages = rt3_packages(chain, package_dir, tmp_path)
    reading = run_for(sessions, dynamic_environment).register(packages["RT3-b"])
    assert reading.status == 200
    assert chain.state(package_version(packages["RT3-b"].package_dir)) == "registrado"


def test_rt3_real_chain_rt3b_with_the_base_model_already_registered_is_409_and_the_oracle_says_no_ejecutado(
    chain: RealChain,
    sessions: Sessions,
    dynamic_environment: guard.Environment,
    package_dir: Path,
    tmp_path: Path,
) -> None:
    """«Contradicciones» 3, reproducida: en kind el modelo de referencia ya esta registrado y RT3-b comparte su `model_version_id`."""
    packages = rt3_packages(chain, package_dir, tmp_path)
    chain.add_package(package_version(package_dir), package_dir)
    sessions.write("ingeniero-1", lambda c: c.register_model(rt2.registration_body(package_dir)))
    reading = run_for(sessions, dynamic_environment).register(packages["RT3-b"])
    assert (reading.status, reading.code) == (409, "conflict_state")
    result = rt3.judge_rt3b(reading, None, [], [], package_version(package_dir))
    assert result.result == "no ejecutado" and result.missing == ("rt3b_version_ya_registrada",)


def test_rt3_real_chain_red_the_convention_uris_make_governance_read_the_base_package_and_the_oracle_fails(
    chain: RealChain,
    sessions: Sessions,
    dynamic_environment: guard.Environment,
    package_dir: Path,
    tmp_path: Path,
) -> None:
    """Rojo primero: el cuerpo con las URIs de la convencion `<model_version_id>/` (en vez del prefijo por parametro) hace que governance lea el paquete base y llegue `manifest_sha256_mismatch`, no el motivo de la tabla."""
    packages = rt3_packages(chain, package_dir, tmp_path)
    chain.add_package(
        package_version(package_dir), package_dir
    )  # el model-store tiene el base bajo `<model_version_id>/`
    wrong = rt3.Rt3Package("RT3-a", packages["RT3-a"].package_dir, package_version(package_dir))
    reading = run_for(sessions, dynamic_environment).register(wrong)
    assert reading.status == 422 and ("package", "manifest_sha256_mismatch") in (reading.invalid_params or ())
    result = rt3.judge_registration("RT3-a", reading)
    assert result.result == "falla" and result.missing == ("rt3_RT3-a_reason_code_distinto",)


def test_rt2_setup_real_chain_the_engineer_registers_the_cro_approves_and_approved_by_differs_from_registered_by(
    chain: RealChain, sessions: Sessions, dynamic_environment: guard.Environment, package_dir: Path
) -> None:
    clock = sessions._clock
    assert isinstance(clock, FakeClock)
    from rt2_world import WorldClock

    world_clock = WorldClock()
    sessions = Sessions(
        dynamic_environment,
        WorldOidc(Holder(world_clock)),
        world_clock,
        TAG,
        transport=chain.transport,
        verify=False,
    )  # type: ignore[arg-type]
    model_id = package_version(package_dir)
    chain.add_package(model_id, package_dir)
    world_clock.at(40.0, lambda: chain.deliver_validation_report(model_id))  # el Job de validacion termina
    outcome = rt2.rt2_setup(
        dynamic_environment, sessions, world_clock, [rt2.ProxyVersion(1, model_id, package_dir)]
    )
    assert outcome.result == "pasa", outcome
    row = chain.api.sql(
        "SELECT state, registered_by, approved_by FROM model_versions WHERE model_version_id = %s", model_id
    )[0]
    assert (row["state"], row["registered_by"], row["approved_by"]) == ("aprobado", "ingeniero-1", "cro-1")
    assert outcome.subresults[0].readings["approved_by_differs"] is True
    detail = sessions.reader("ingeniero-1").get_model(model_id)
    assert (
        detail.registered_by == "ingeniero-1" and detail.approved_by == "cro-1" and detail.state == "aprobado"
    )


def test_rt2_setup_real_chain_approving_with_the_sub_that_registered_is_409_and_the_oracle_fails(
    chain: RealChain, sessions: Sessions, dynamic_environment: guard.Environment, package_dir: Path
) -> None:
    from evidence_support import VALIDATION_JOB, new_model, report
    from vectra_contracts.catalog import Role
    from vectra_governance.model_fsm import Actor

    model_id = package_version(package_dir)
    same = Actor(
        "user", "cro-1", Role.INGENIERO_RIESGO, "mfa"
    )  # quien registro es el mismo `sub` que va a aprobar
    chain.api.svc.register(same, new_model(model_id))
    chain.api.svc.start_validation(same, model_id, job_name=f"job-{model_id}")
    run_id = str(
        chain.api.sql("SELECT run_id FROM validation_runs WHERE model_version_id = %s", model_id)[0]["run_id"]
    )
    chain.api.svc.receive_report(VALIDATION_JOB, model_id, run_id, report(True))
    assert chain.state(model_id) == "lista_para_aprobacion"
    outcome = rt2.rt2_setup(
        dynamic_environment, sessions, sessions._clock, [rt2.ProxyVersion(1, model_id, package_dir)]
    )
    assert outcome.result == "falla" and outcome.missing == ("rt2_setup_aprobacion_http_409_conflict_state",)
    assert chain.state(model_id) == "lista_para_aprobacion"


def test_the_rt3_package_manifests_carry_the_model_version_id_of_the_base_package(
    package_dir: Path, tmp_path: Path
) -> None:
    """«Contradicciones» 3 en los bytes: los cuatro paquetes RT-3 llevan el `model_version_id` del modelo de referencia."""
    base = package_version(package_dir)
    for case_id in (*REJECTED_BY_U4, "RT3-b"):
        target = tmp_path / case_id
        rt3_package(case_id, package_dir, target)
        assert json.loads((target / "manifest.json").read_text(encoding="utf-8"))["model_version_id"] == base
