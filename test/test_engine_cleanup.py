from types import SimpleNamespace

import pytest

from jeuxRPG import cli
from jeuxRPG._class.character import Character
from jeuxRPG.multiplayer.controller import parse_field


def test_character_does_not_hide_navigation_initialization_errors(monkeypatch):
    def fail(self):
        raise RuntimeError("navigation unavailable")

    monkeypatch.setattr(Character, "_init_navigation", fail)
    with pytest.raises(RuntimeError, match="navigation unavailable"):
        Character.create("Knight", "navigation-check", "Navigation")


def test_interactive_routes_commands_and_rejects_invalid_arity(monkeypatch, capsys):
    calls = []
    output = []
    session = SimpleNamespace(
        observe=lambda: calls.append(("observe",)),
        save=lambda: calls.append(("save",)),
        travel=lambda route: calls.append(("travel", route)),
        rest_at_camp=lambda when: calls.append(("rest", when)),
        establish_camp=lambda name: calls.append(("camp", name)),
    )
    commands = iter(
        [
            "",
            '"unfinished',
            "combat extra",
            "observer",
            "voyager road",
            "dormir nuit",
            "camp Camp de test",
            "quitter",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))
    monkeypatch.setattr(cli, "show", output.append)
    cli.interactive(session)
    assert calls == [
        ("observe",),
        ("save",),
        ("travel", "road"),
        ("rest", "night"),
        ("camp", "Camp de test"),
    ]
    assert len(output) == 4
    assert "Commande mal formée." in capsys.readouterr().out


@pytest.mark.parametrize("key", ["chance", "hp_multiplier", "damage_multiplier"])
@pytest.mark.parametrize("initial", [0, 1])
def test_decimal_fields_keep_fractional_values_from_integer_defaults(key, initial):
    assert parse_field(key, "0,75", initial) == 0.75
