"""Usuarios de carga (U02-T15, CA-4): `seed_users.py` contra un doble de la Admin API, sin red.

El rol esperado sale del realm y de domain-entities (`load_design.load_role`); la cuenta y los nombres, de J1.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import fake_admin
import load_design as ld
import pytest
from design_values import mfa_required_roles

SEED_TEXT = ld.SEED.read_text(encoding="utf-8")
PASSWORD = "contrasena-de-carga-1234"  # noqa: S105
PREFIX, FIRST, LAST = ld.load_users()
NAMES = [f"{PREFIX}{i:03d}" for i in range(FIRST, LAST + 1)]


def load_module(path: Path = ld.SEED) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"seed_users_{abs(hash(path))}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seeder(admin: fake_admin.FakeAdmin, module: ModuleType | None = None):
    module = module or load_module()
    return module.Seeder(admin.client(), "http://keycloak.test/auth", "admin", fake_admin.ADMIN_PASSWORD, PASSWORD)


@pytest.fixture
def admin() -> fake_admin.FakeAdmin:
    return fake_admin.FakeAdmin(ld.realm())


def assert_users_follow_the_design(admin: fake_admin.FakeAdmin) -> None:
    """El oraculo de CA-4: los usuarios de J1, con un rol sin MFA obligatorio (BR-U2-03), sin OTP y sin acciones pendientes."""
    assert sorted(u["username"] for u in admin.users.values()) == NAMES
    assert len(admin.users) == ld.concurrent_users()
    role = ld.load_role()
    assert role not in mfa_required_roles()
    for user in admin.users.values():
        assert user["otp"] is False and user["requiredActions"] == [] and user["enabled"] is True
        assert admin.mapped[user["id"]] == [role]
        assert admin.passwords[user["id"]] == PASSWORD


def test_it_creates_the_users_with_the_role_without_mfa_and_without_otp(admin):
    seeder(admin).create(LAST - FIRST + 1)
    assert_users_follow_the_design(admin)


def test_it_is_idempotent(admin):
    s = seeder(admin)
    s.create(LAST - FIRST + 1)
    s.create(LAST - FIRST + 1)
    assert len(admin.users) == ld.concurrent_users()
    assert all(admin.mapped[u] == [ld.load_role()] for u in admin.users)


def pollute(admin: fake_admin.FakeAdmin, name: str) -> None:
    """Un usuario de una corrida anterior: bloqueado, con una accion pendiente y con OTP, y con la misma contrasena de carga."""
    user = admin.by_name(name)
    user.update(enabled=False, requiredActions=["CONFIGURE_TOTP"], otp=True)


def test_a_second_run_with_the_same_password_does_not_hit_the_password_history(admin):
    """C-01: Keycloak 26.8.1 rechaza reusar la contrasena vigente (passwordHistory); `create` no puede depender de ello."""
    s = seeder(admin)
    s.create(3)
    s.create(3)
    s.create(3)
    assert sorted(u["username"] for u in admin.users.values()) == NAMES[:3]


def test_it_re_enables_and_cleans_an_existing_user(admin):
    """C-03: un usuario bloqueado, con acciones pendientes u OTP de una corrida anterior queda como uno nuevo."""
    s = seeder(admin)
    s.create(3)
    for name in NAMES[:3]:
        pollute(admin, name)
    s.create(3)
    for user in admin.users.values():
        assert user["enabled"] is True and user["requiredActions"] == [] and user["otp"] is False
        assert admin.passwords[user["id"]] == PASSWORD
        assert admin.mapped[user["id"]] == [ld.load_role()]


def test_the_fake_admin_rejects_reusing_the_current_password(admin):
    seeder(admin).create(1)
    user_id = admin.by_name(NAMES[0])["id"]
    headers = {"Authorization": "Bearer admin-token"}
    body = {"type": "password", "value": PASSWORD, "temporary": False}
    same = admin.client().put(f"{admin.prefix}/users/{user_id}/reset-password", json=body, headers=headers)
    assert same.status_code == 400


def test_it_repairs_a_user_that_lost_its_role(admin):
    s = seeder(admin)
    s.create(3)
    victim = admin.by_name(NAMES[1])["id"]
    admin.mapped[victim] = []
    s.create(3)
    assert admin.mapped[admin.by_name(NAMES[1])["id"]] == [ld.load_role()]  # el usuario se vuelve a crear: otro id


def test_it_deletes_only_the_load_users(admin):
    other = admin.client().post(
        f"{admin.prefix}/users", json={"username": "analista-1"}, headers={"Authorization": "Bearer admin-token"}
    )
    assert other.status_code == 201
    s = seeder(admin)
    s.create(LAST - FIRST + 1)
    s.delete(LAST - FIRST + 1)
    assert [u["username"] for u in admin.users.values()] == ["analista-1"]
    s.delete(LAST - FIRST + 1)  # idempotente: ya no hay nada que borrar
    assert [u["username"] for u in admin.users.values()] == ["analista-1"]


def test_a_wrong_admin_password_fails_loudly(admin):
    module = load_module()
    bad = module.Seeder(admin.client(), "http://keycloak.test/auth", "admin", "otra", PASSWORD)
    with pytest.raises(Exception, match="401"):
        bad.create(1)


def test_the_script_does_not_run_anything_on_import(admin):
    load_module()
    assert admin.requests == []


def _create_with_copy(tmp_path, admin, old: str, new: str) -> None:
    """Crea los usuarios con una copia mutada de `seed_users.py` (la mutacion debe encontrarse en el texto)."""
    assert old in SEED_TEXT, f"la mutacion no encuentra {old!r}"
    copy = tmp_path / "seed_users.py"
    copy.write_text(SEED_TEXT.replace(old, new), encoding="utf-8")
    seeder(admin, load_module(copy)).create(LAST - FIRST + 1)


@pytest.mark.parametrize("bad_role", sorted(mfa_required_roles()))
def test_a_copy_with_a_role_that_requires_mfa_fails_the_oracle(tmp_path, admin, bad_role):
    role = ld.load_role()
    _create_with_copy(tmp_path, admin, f'LOAD_ROLE = "{role}"', f'LOAD_ROLE = "{bad_role}"')
    with pytest.raises(AssertionError):
        assert_users_follow_the_design(admin)


def test_a_copy_that_enrols_otp_fails_the_oracle(tmp_path, admin):
    _create_with_copy(tmp_path, admin, '"requiredActions": []', '"requiredActions": ["CONFIGURE_TOTP"]')
    with pytest.raises(AssertionError):
        assert_users_follow_the_design(admin)


def test_the_constants_follow_j1():
    module = load_module()
    assert module.PREFIX == PREFIX and module.DEFAULT_COUNT == ld.concurrent_users()
    assert module.LOAD_ROLE == ld.load_role()
