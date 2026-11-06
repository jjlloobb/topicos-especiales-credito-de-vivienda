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


def test_it_creates_the_users_with_the_role_without_mfa_and_without_otp(admin):
    seeder(admin).create(LAST - FIRST + 1)
    assert sorted(u["username"] for u in admin.users.values()) == NAMES
    assert len(admin.users) == ld.concurrent_users()
    role = ld.load_role()
    assert role not in mfa_required_roles()
    for user in admin.users.values():
        assert user["otp"] is False and user["requiredActions"] == [] and user["enabled"] is True
        assert admin.mapped[user["id"]] == [role]
        assert admin.passwords[user["id"]] == PASSWORD


def test_it_is_idempotent(admin):
    s = seeder(admin)
    s.create(LAST - FIRST + 1)
    posts = admin.count("POST", "/users")
    s.create(LAST - FIRST + 1)
    assert admin.count("POST", "/users") == posts, "la segunda corrida creo usuarios"
    assert len(admin.users) == ld.concurrent_users()
    assert all(admin.mapped[u] == [ld.load_role()] for u in admin.users)


def test_it_repairs_a_user_that_lost_its_role(admin):
    s = seeder(admin)
    s.create(3)
    victim = admin.by_name(NAMES[1])["id"]
    admin.mapped[victim] = []
    s.create(3)
    assert admin.mapped[victim] == [ld.load_role()]


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


@pytest.mark.parametrize("bad_role", sorted(mfa_required_roles()))
def test_a_copy_with_a_role_that_requires_mfa_fails(tmp_path, admin, bad_role):
    role = ld.load_role()
    assert f'LOAD_ROLE = "{role}"' in SEED_TEXT
    copy = tmp_path / "seed_users.py"
    copy.write_text(SEED_TEXT.replace(f'LOAD_ROLE = "{role}"', f'LOAD_ROLE = "{bad_role}"'), encoding="utf-8")
    module = load_module(copy)
    seeder(admin, module).create(2)
    created = {r for u in admin.users for r in admin.mapped[u]}
    assert created == {bad_role}
    assert not created <= {ld.load_role()}, "la copia mutada deberia crear un rol distinto del esperado"
    assert created & mfa_required_roles(), "el rol mutado exige MFA (BR-U2-03): el control de la prueba lo detecta"


def test_a_copy_that_enrols_otp_is_detected(tmp_path, admin):
    assert '"requiredActions": []' in SEED_TEXT
    copy = tmp_path / "seed_users.py"
    copy.write_text(SEED_TEXT.replace('"requiredActions": []', '"requiredActions": ["CONFIGURE_TOTP"]'), encoding="utf-8")
    seeder(admin, load_module(copy)).create(1)
    assert any(u["requiredActions"] for u in admin.users.values())


def test_the_constants_follow_j1():
    module = load_module()
    assert module.PREFIX == PREFIX and module.DEFAULT_COUNT == ld.concurrent_users()
    assert module.LOAD_ROLE == ld.load_role()
