"""Dockerfile de Keycloak (U02-T06, Paso 4): INF-U2-08. Imagen y opciones leidas del diseno."""

import pytest
import theme_checks as tc

IMAGE, DIGEST = tc.design_image()
OPTIONS = tc.design_build_options()
START = tc.design_start_args()
TEXT = tc.DOCKERFILE.read_text(encoding="utf-8")


def problems(text: str) -> list[str]:
    return tc.dockerfile_problems(text, IMAGE, DIGEST, OPTIONS, START)


def test_design_values_are_read_from_infrastructure_design():
    assert IMAGE.startswith("quay.io/keycloak/keycloak:26.")
    assert DIGEST.startswith("sha256:") and len(DIGEST) == 71
    assert sorted(OPTIONS) == ["--cache=ispn", "--db=postgres", "--health-enabled=true", "--metrics-enabled=true"]
    assert START == ["start", "--optimized"]


def test_dockerfile_meets_inf_u2_08():
    assert problems(TEXT) == []


def test_dockerfile_copies_the_theme_that_exists():
    assert (tc.DOCKERFILE.parent / "themes" / "vectra" / "login" / "theme.properties").is_file()


def test_dockerfile_has_no_other_digest():
    assert TEXT.count("@sha256:") == 1


def test_other_digest_is_detected():
    assert problems(TEXT.replace(DIGEST, "sha256:" + "0" * 64))


def test_missing_digest_is_detected():
    assert problems(TEXT.replace(f"@{DIGEST}", ""))


def test_other_tag_is_detected():
    assert problems(TEXT.replace(":26.8.1@", ":26.8.0@"))


@pytest.mark.parametrize("option", OPTIONS)
def test_missing_build_option_is_detected(option):
    assert f"falta {option} en kc.sh build" in problems(TEXT.replace(f"    {option}", "    --log-level=info"))


def test_missing_optimized_is_detected():
    assert problems(TEXT.replace('"--optimized"', '"--verbose"'))


def test_missing_theme_copy_is_detected():
    assert problems(TEXT.replace("COPY --chown=keycloak:keycloak themes/vectra", "COPY --chown=keycloak:keycloak other"))
