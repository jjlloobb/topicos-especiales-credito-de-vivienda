"""El perfil activo de Hypothesis es el que fija HYPOTHESIS_PROFILE (CA-3)."""

import os

from hypothesis import settings


def test_hypothesis_profile_is_the_one_set_by_env() -> None:
    expected = os.environ.get("HYPOTHESIS_PROFILE", "dev")
    assert settings.get_current_profile_name() == expected
