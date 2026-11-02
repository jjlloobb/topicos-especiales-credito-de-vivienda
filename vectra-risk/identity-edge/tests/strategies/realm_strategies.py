"""Generadores de Hypothesis para PBT-U2-01, 02 y 03 (PBT-07)."""

import string

from hypothesis import strategies as st
from vectra_contracts.catalog import Role, Scope

BUSINESS = [r.value for r in Role]
# Roles tecnicos que no interactuan con otras reglas (`operacion` y `realm-admin` se prueban aparte).
NEUTRAL_TECHNICAL = ["offline_access", "uma_authorization", "default-roles-vectra"]

CATALOG_SCOPES = [s.value for s in Scope]

business_role_subsets = st.lists(st.sampled_from(BUSINESS), unique=True, max_size=4)
neutral_technical_roles = st.lists(st.sampled_from(NEUTRAL_TECHNICAL), unique=True, max_size=3)
role_sets = st.tuples(business_role_subsets, neutral_technical_roles).map(
    lambda t: list(dict.fromkeys(t[0] + t[1]))
)
# Con `operacion` y `realm-admin` (ambos con TOTP en el usuario generado).
role_sets_with_special = st.tuples(
    business_role_subsets,
    st.lists(st.sampled_from(["operacion", "realm-admin", *NEUTRAL_TECHNICAL]), unique=True, max_size=4),
).map(lambda t: list(dict.fromkeys(t[0] + t[1])))

_name = st.text(alphabet=string.ascii_lowercase + "-", min_size=1, max_size=12).filter(
    lambda s: s[0] != "-" and s[-1] != "-"
)

# Grupos de LDAP: distinguidos por prefijo para separar mapeados y no mapeados.
mapped_group_maps = st.dictionaries(
    _name.map(lambda n: f"cn=vectra-{n},ou=groups"),
    st.sampled_from([*BUSINESS, "operacion"]),
    min_size=1,
    max_size=6,
)
unmapped_groups = st.lists(_name.map(lambda n: f"cn=otro-{n},ou=groups"), unique=True, max_size=4)


@st.composite
def ldap_assignments(draw: st.DrawFn) -> tuple[dict[str, str], list[str]]:
    """Una tabla `group-role-map` y los grupos de un usuario (mapeados y no mapeados)."""
    mapping = draw(mapped_group_maps)
    chosen = draw(st.lists(st.sampled_from(sorted(mapping)), unique=True, max_size=len(mapping)))
    others = draw(unmapped_groups)
    groups = draw(st.permutations(chosen + others))
    return mapping, list(groups)


# Client scopes propios de Keycloak: tampoco pasan (PBT-U2-03 enmendada, 2026-11-02). No se filtran.
KEYCLOAK_OWN_SCOPES = ["openid", "profile", "email", "roles", "web-origins", "acr", "offline_access", "microprofile-jwt"]
outside_catalog_scopes = st.one_of(
    st.sampled_from(KEYCLOAK_OWN_SCOPES),
    st.text(alphabet=string.ascii_lowercase + ":-", min_size=1, max_size=24).filter(lambda s: s not in CATALOG_SCOPES),
)
client_scope_lists = st.lists(
    st.one_of(st.sampled_from(CATALOG_SCOPES), outside_catalog_scopes), unique=True, max_size=8
)
# Clientes de ejemplo: el del job de sesgo, el servicio HTTP que no congela, y nombres arbitrarios.
client_ids = st.one_of(
    st.sampled_from(["bias-monitoring-job", "bias-monitoring-service", "case-service", "scoring-service"]),
    _name.map(lambda n: f"cliente-{n}"),
)
