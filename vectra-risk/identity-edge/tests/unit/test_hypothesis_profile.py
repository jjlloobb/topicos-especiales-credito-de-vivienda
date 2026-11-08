"""El perfil activo de Hypothesis es el que fija HYPOTHESIS_PROFILE (CA-3).

NFR-U2-40: `make test` fija `HYPOTHESIS_PROFILE=ci`; esta prueba comprueba que el perfil pedido es el activo.
"""

import os

from hypothesis import settings


def test_hypothesis_profile_is_the_one_set_by_env(u0_default_profile: str) -> None:
    expected = os.environ.get("HYPOTHESIS_PROFILE", u0_default_profile)
    assert settings.get_current_profile_name() == expected
