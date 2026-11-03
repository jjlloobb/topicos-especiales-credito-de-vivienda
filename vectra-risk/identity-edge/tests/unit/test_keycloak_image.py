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
    tag = tc.design_version()
    assert problems(TEXT.replace(f":{tag}@", ":26.0.0@"))


@pytest.mark.parametrize("option", OPTIONS)
def test_missing_build_option_is_detected(option):
    assert any(p.startswith(f"kc.sh build debe llevar {option}") for p in problems(TEXT.replace(f"    {option}", "    --log-level=info")))


def test_missing_optimized_is_detected():
    assert problems(TEXT.replace('"--optimized"', '"--verbose"'))


def test_missing_theme_copy_is_detected():
    assert problems(TEXT.replace("COPY --chown=keycloak:keycloak themes/vectra", "COPY --chown=keycloak:keycloak other"))


def test_copy_to_another_path_is_detected():
    """D01."""
    assert problems(TEXT.replace("/opt/keycloak/themes/vectra", "/srv/themes/vectra"))


@pytest.mark.parametrize("option", OPTIONS)
def test_contradictory_duplicate_option_is_detected(option):
    """D02 y D04."""
    name = option.split("=", 1)[0]
    assert problems(TEXT.replace(f"    {option}", f"    {option} \\\n    {name}=dev-file"))


@pytest.mark.parametrize("option", OPTIONS)
def test_wrong_value_of_an_option_is_detected(option):
    name = option.split("=", 1)[0]
    assert problems(TEXT.replace(option, f"{name}=false"))


def test_second_kc_build_is_detected():
    """D03."""
    extra = "RUN /opt/keycloak/bin/kc.sh build --db=dev-file\n"
    assert problems(TEXT.replace("# Usuario", extra + "# Usuario"))


@pytest.mark.parametrize("env", ["KC_DB=dev-file", "KC_HEALTH_ENABLED=false", "KC_METRICS_ENABLED=false", "KC_CACHE=local"])
def test_env_contradicting_an_option_is_detected(env):
    """D07."""
    assert problems(TEXT.replace("USER 1000", f"ENV {env}\nUSER 1000"))


def test_env_equal_to_the_option_is_accepted():
    assert problems(TEXT.replace("USER 1000", "ENV KC_DB=postgres\nUSER 1000")) == []


def test_missing_user_is_detected():
    """F-06: el escaneo de supply-chain.yml exige USER."""
    assert problems(TEXT.replace("USER 1000\n", ""))


@pytest.mark.parametrize("user", ["root", "0", "keycloak"])
def test_other_user_is_detected(user):
    assert problems(TEXT.replace("USER 1000", f"USER {user}"))


def test_user_after_the_entrypoint_is_detected():
    assert problems(TEXT.replace("USER 1000\n\n", "") + "USER 1000\n")


SECOND_BUILD = {
    "D03 shell": "RUN /opt/keycloak/bin/kc.sh build --db=dev-file",
    "N37 exec": 'RUN ["/opt/keycloak/bin/kc.sh", "build", "--db=dev-file"]',
    "N38 opcion antes de build": "RUN /opt/keycloak/bin/kc.sh --verbose build --db=dev-file",
    "minusculas": "run /opt/keycloak/bin/kc.sh build --db=dev-file",
    "encadenado con &&": "RUN echo hi && /opt/keycloak/bin/kc.sh build --db=dev-file",
    "encadenado con ;": "RUN echo hi; kc.sh build --db=dev-file",
    "continuacion de linea": "RUN /opt/keycloak/bin/kc.sh \\\n    build --db=dev-file",
    "ruta relativa": "RUN bin/kc.sh build",
}


@pytest.mark.parametrize("name", SECOND_BUILD)
def test_second_kc_build_in_any_form_is_detected(name):
    assert problems(TEXT.replace("USER 1000", SECOND_BUILD[name] + "\nUSER 1000")), name


def test_kc_build_in_exec_form_with_the_design_options_is_accepted():
    exec_form = TEXT.replace(
        TEXT[TEXT.index("RUN "):TEXT.index("# Usuario")],
        'RUN ["/opt/keycloak/bin/kc.sh", "build", ' + ", ".join(f'"{o}"' for o in OPTIONS) + "]\n\n",
    )
    assert problems(exec_form) == []


def test_lowercase_instructions_are_equivalent():
    assert problems(TEXT.replace("COPY", "copy").replace("USER", "user").replace("ENTRYPOINT", "entrypoint").replace("CMD", "cmd")) == []


FINAL_STAGE = {
    "N50 from en minusculas": "from busybox:1.36",
    "FROM en mayusculas": "FROM busybox:1.36",
    "FROM con alias": "FROM busybox:1.36 AS final",
    "FROM con plataforma": "FROM --platform=linux/amd64 busybox:1.36",
}


@pytest.mark.parametrize("name", FINAL_STAGE)
def test_another_final_stage_is_detected(name):
    assert problems(TEXT.replace("USER 1000", FINAL_STAGE[name] + "\nUSER 1000")), name


@pytest.mark.parametrize("extra", ["user 0", "USER root", "User keycloak", "USER 0:0", "USER 1001"])
def test_any_other_user_is_detected(extra):
    """N49."""
    assert problems(TEXT.replace("ENTRYPOINT", extra + "\nENTRYPOINT")), extra
    assert problems(TEXT.replace("USER 1000\n", "")  + extra + "\n"), extra


def test_user_1000_then_another_user_is_detected():
    assert problems(TEXT.replace("USER 1000", "USER 1000\nUSER 0"))


@pytest.mark.parametrize("env", ["ENV KC_DB dev-file", "env KC_DB=dev-file", "ARG KC_CACHE=local", "RUN KC_HEALTH_ENABLED=false true"])
def test_env_forms_contradicting_an_option_are_detected(env):
    assert problems(TEXT.replace("USER 1000", env + "\nUSER 1000")), env
