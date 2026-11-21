"""`--as`: solo con una cuenta que ya tiene sesion en `gh`, cambiando solo durante la publicacion y restaurando siempre la cuenta anterior."""

from __future__ import annotations

from voz_doubles import FakeConsole


def switches(runner) -> list[str]:
    return [c[c.index("--user") + 1] for c in runner.calls if c[:3] == ("gh", "auth", "switch")]


def test_as_switches_only_to_publish_and_restores_the_previous_account(launch, runner) -> None:
    console = FakeConsole("s")
    assert launch(console, "12", "--as", "joseluisjedi") == 0
    assert switches(runner) == ["joseluisjedi", "jjlloobb"]
    assert runner.reviews[0]["as"] == "joseluisjedi" and runner.active() == "jjlloobb"
    kinds = [c[:3] for c in runner.calls if c[0] == "gh"]
    first_switch = kinds.index(("gh", "auth", "switch"))
    assert ("gh", "pr", "review") not in kinds[:first_switch]
    assert kinds[first_switch:] == [
        ("gh", "auth", "switch"),
        ("gh", "auth", "status"),
        ("gh", "pr", "review"),
        ("gh", "auth", "switch"),
        ("gh", "auth", "status"),
    ]
    assert "Se publicaria como: joseluisjedi (la cuenta activa de `gh` es jjlloobb" in console.output
    assert "Cuenta activa de `gh` restaurada: jjlloobb." in console.output
    assert console.prompts == [
        "¿Publicar esta nota en el PR #12 como joseluisjedi? (como comentario, sin aprobar) [s/N] "
    ]


def test_the_account_is_not_switched_before_the_confirmation(launch, runner) -> None:
    assert launch(FakeConsole("n"), "12", "--as", "joseluisjedi") == 1
    assert switches(runner) == [] and runner.active() == "jjlloobb"


def test_as_the_active_account_does_not_switch(launch, runner) -> None:
    assert launch(FakeConsole("s"), "12", "--as", "JJLLOOBB") == 0
    assert switches(runner) == [] and runner.reviews[0]["as"] == "jjlloobb"


def test_a_failed_switch_publishes_nothing_and_leaves_the_account_as_it_was(
    launch, runner, leftovers
) -> None:
    runner.switch_works = False
    console = FakeConsole("s")
    assert launch(console, "12", "--as", "joseluisjedi") == 2
    assert runner.reviews == [] and runner.active() == "jjlloobb"
    assert "no se pudo cambiar `gh` a la cuenta joseluisjedi: no se publico nada" in console.output
    assert leftovers() == []


def test_the_account_is_restored_when_the_review_fails_or_is_interrupted(launch, runner) -> None:
    runner.review_returncode = 1
    assert launch(FakeConsole("s"), "12", "--as", "joseluisjedi") == 2
    assert switches(runner) == ["joseluisjedi", "jjlloobb"] and runner.active() == "jjlloobb"
    runner.calls.clear()
    runner.switches = 0
    runner.review_raises = KeyboardInterrupt()
    assert launch(FakeConsole("s"), "12", "--as", "joseluisjedi") == 130
    assert switches(runner) == ["joseluisjedi", "jjlloobb"] and runner.active() == "jjlloobb"


def test_a_failed_restore_is_shouted_with_the_order_to_fix_it(launch, runner) -> None:
    runner.restore_works = False
    console = FakeConsole("s")
    assert launch(console, "12", "--as", "joseluisjedi") == 0
    assert "ATENCION: no se pudo restaurar" in console.output
    assert "gh auth switch --hostname github.com --user jjlloobb" in console.output
    assert "restaurada" not in console.output
