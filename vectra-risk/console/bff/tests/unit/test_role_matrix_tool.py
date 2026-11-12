"""`tools/role_matrix.py` (Paso 7; CA-5): tres fuentes que coinciden y el rojo sobre copias (`--c03`, `--matrix`)."""

from pathlib import Path

import pytest
import role_matrix

C03_TEXT = role_matrix.C03.read_text(encoding="utf-8")
MATRIX_TEXT = role_matrix.MATRIX.read_text(encoding="utf-8")


def test_the_three_sources_have_the_same_30_rows() -> None:
    sources = {
        "REGISTRY": role_matrix.from_registry(),
        "C03": role_matrix.from_c03(),
        "versionada": role_matrix.from_versioned(),
    }
    assert {len(m) for m in sources.values()} == {30}
    assert role_matrix.differences(sources) == []
    assert sum(1 for _, mfa in sources["C03"].values() if mfa) == 11


def test_check_passes_on_the_real_files(capsys: pytest.CaptureFixture[str]) -> None:
    assert role_matrix.main(["--check"]) == 0
    assert "30 endpoints comparados" in capsys.readouterr().out


def test_c03_where_retry_case_loses_cro_fails_and_names_the_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    altered = tmp_path / "component-methods.md"
    altered.write_text(
        C03_TEXT.replace(
            "`POST /api/console/cases/{id}/retry` | cro |", "`POST /api/console/cases/{id}/retry` | — |"
        ),
        encoding="utf-8",
    )
    assert altered.read_text() != C03_TEXT
    assert role_matrix.main(["--check", "--c03", str(altered)]) == 1
    err = capsys.readouterr().err
    assert (
        "POST /api/console/cases/{id}/retry" in err
        and "C03: roles=[]" in err
        and "REGISTRY: roles=['cro']" in err
    )


def test_c03_with_a_role_added_or_the_mfa_dropped_fails(tmp_path: Path) -> None:
    more = tmp_path / "more.md"
    more.write_text(
        C03_TEXT.replace(
            "`GET /api/console/policies` | analista, cro, cumplimiento |",
            "`GET /api/console/policies` | analista, cro, cumplimiento, ingeniero_riesgo |",
        ),
        encoding="utf-8",
    )
    assert role_matrix.check(more)[0] == 1
    nomfa = tmp_path / "nomfa.md"
    nomfa.write_text(
        C03_TEXT.replace(
            "`POST /api/console/models/{id}/approval` | cro | sí |",
            "`POST /api/console/models/{id}/approval` | cro | — |",
        ),
        encoding="utf-8",
    )
    code, message = role_matrix.check(nomfa)
    assert code == 1 and "models/{id}/approval" in message


def test_a_versioned_matrix_that_drifts_fails(tmp_path: Path) -> None:
    drifted = tmp_path / "role-endpoint-matrix.md"
    drifted.write_text(
        MATRIX_TEXT.replace(
            "| console-bff | GET | `/api/console/freezes/{id}` |  |  |  | x |",
            "| console-bff | GET | `/api/console/freezes/{id}` |  |  | x | x |",
        ),
        encoding="utf-8",
    )
    assert drifted.read_text() != MATRIX_TEXT
    code, message = role_matrix.check(matrix=drifted)
    assert code == 1 and "freezes/{id}" in message and "versionada" in message


def test_a_row_missing_from_one_source_is_reported_as_absent(tmp_path: Path) -> None:
    short = tmp_path / "short.md"
    short.write_text(
        "\n".join(line for line in C03_TEXT.splitlines() if "`GET /api/console/me`" not in line),
        encoding="utf-8",
    )
    code, message = role_matrix.check(short)
    assert code == 1 and "C03: ausente" in message


def test_cell_parsers() -> None:
    assert role_matrix._roles("todos") == frozenset(role_matrix.ROLE_COLUMNS)  # noqa: SLF001
    assert role_matrix._roles("**cumplimiento**") == {"cumplimiento"}  # noqa: SLF001
    assert role_matrix._roles("—") == frozenset() == role_matrix._roles("")  # noqa: SLF001
    assert (
        role_matrix._mfa("sí")
        and role_matrix._mfa("si")
        and not role_matrix._mfa("no (acción técnica)")
        and not role_matrix._mfa("—")
    )  # noqa: SLF001
