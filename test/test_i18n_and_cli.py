import json

import pytest

from jeuxRPG import cli, i18n
from jeuxRPG._balance import loader, simulator


@pytest.mark.parametrize("lang", ["en", "fr", "ja"])
def test_language_roundtrip(lang):
    i18n.clear_cache()
    assert i18n.is_supported_language(lang)
    translated = i18n.translate_class_name("Knight", lang)
    assert i18n.get_internal_class_name(translated, ["Knight", "Mage"]) == "Knight"
    assert i18n.get_translator(lang)("class.Knight") == translated
    assert i18n.translate_class_list(["Knight"], lang) == [translated]
    assert i18n.t("missing.key", lang) == "missing.key"
    assert i18n.translate_class_name("Unknown", lang) == "Unknown"


def test_player_translation_without_bot():
    assert i18n.get_player_language("unknown") == "en"
    assert i18n.t_player("class.Knight", "unknown") == i18n.t("class.Knight")
    assert i18n.translate_class_name_player("Knight", "unknown") == i18n.translate_class_name("Knight")
    assert i18n.translate_class_list_player(["Knight"], "unknown") == i18n.translate_class_list(["Knight"])
    assert i18n.get_internal_class_name("KNIGHT", ["Knight"]) == "Knight"
    assert i18n.get_internal_class_name("missing", ["Knight"]) is None
    assert not i18n.is_supported_language("missing")
    assert i18n.t("class.Knight", "missing") == i18n.t("class.Knight")


def test_cli_report(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["jeux-rpg", "--floors", "2"])
    cli.main()
    assert json.loads(capsys.readouterr().out)["completed"] is True
    monkeypatch.setattr("sys.argv", ["jeux-rpg", "--floors", "0"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_overrides_and_report(tmp_path, monkeypatch):
    table = {"base_stats": {"hp": 10, "force": 5}}
    monkeypatch.setattr(loader, "CLASS_TABLES", {"Example": table})
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"Example": {"base_stats": {"hp": 20}}, "Unknown": {}}))
    assert loader.apply_class_overrides(patch)
    assert table == {"base_stats": {"hp": 20, "force": 5}}
    with pytest.raises(TypeError):
        loader._read_json(12)
    report = simulator.simulate_matrix(["Knight", "Goblin"], matches_per_pair=2, seed=42)
    assert report["summary"]["Knight"]["total_matches"] == 4
    report["analysis"] = simulator.analyze_summary(report["summary"])
    output = tmp_path / "nested" / "report.json"
    simulator.write_report(report, output)
    assert json.loads(output.read_text()) == report
