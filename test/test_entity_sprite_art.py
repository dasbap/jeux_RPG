from copy import deepcopy

import pytest
from test_living_world import no_network  # noqa: F401

from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.entity_sprite_art import populate
from jeuxRPG.multiplayer.sprite_catalog import targets, validate


@pytest.fixture
def pack(tmp_path):
    project = Project(tmp_path / "project")
    return project, populate(project)


def test_every_existing_entity_has_an_animated_body_and_references_are_valid(pack):
    project, data = pack
    assert set(targets(project.content, project.mobs, project.maps)) <= set(
        data["bindings"]
    )
    assert len(data["assets"]) <= 64
    for sprite in data["assets"].values():
        assert len(sprite["frames"]) == 4
        assert len({tuple(frame) for frame in sprite["frames"]}) >= 2
    project.save()
    assert Project(project.directory).content["sprites"] == data


def test_goblins_share_their_body_while_weapons_and_tints_remain_independent(pack):
    _, data = pack
    variants = [
        "goblin",
        "gobelin_archer",
        "gobelin_apprenti",
        "gobelin_chamane",
        "garde_gobelin",
        "seigneur_gobelin",
        "gobelin_berserker",
    ]
    assert {data["bindings"][f"mob:{key}"] for key in variants} == {"gobelin_original"}
    assert data["equipment"]["mob:gobelin_archer"] == "arme_bow"
    assert data["equipment"]["mob:gobelin_chamane"] == "arme_staff"
    assert data["equipment"]["mob:gobelin_berserker"] == "arme_axe"
    assert data["equipment"]["mob:garde_gobelin"] == "arme_sword_shield"
    assert data["bindings"]["mob:slime_vert"] == data["bindings"]["mob:slime_bleu"]
    assert data["colors"]["mob:slime_vert"] != data["colors"]["mob:slime_bleu"]
    original = deepcopy(data["assets"]["gobelin_original"])
    data["equipment"]["mob:gobelin_archer"] = "arme_dagger"
    validate(data)
    assert data["assets"]["gobelin_original"] == original


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["equipment"].update({"mob:goblin": "missing"}),
        lambda d: d["equipment"].update({"unknown:entity": "arme_sword"}),
        lambda d: d["equipment"].update({"mob:goblin": "gobelin_original"}),
        lambda d: d["assets"]["arme_sword"].update(width=23),
        lambda d: d["colors"].update({"mob:goblin": "url(https://invalid)"}),
    ],
)
def test_invalid_equipment_dimensions_or_tints_are_rejected(pack, change):
    _, data = pack
    change(data)
    with pytest.raises(ValueError):
        validate(data)


def test_pack_generation_is_repeatable_and_keeps_custom_assets(pack):
    project, data = pack
    expected = deepcopy(data["assets"])
    project.content["sprites"]["assets"]["custom_original"] = deepcopy(
        data["assets"]["gobelin_original"]
    )
    result = populate(project)
    assert "custom_original" in result["assets"]
    assert {
        key: value
        for key, value in result["assets"].items()
        if key != "custom_original"
    } == expected


def test_builder_changes_and_renames_only_the_equipment_layer(pack):
    project, data = pack
    tk = pytest.importorskip("tkinter")
    from jeuxRPG.multiplayer.sprite_maker import SpriteMaker

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk nécessite un affichage local")
    root.withdraw()
    maker = None
    before = deepcopy(data["assets"]["gobelin_original"])
    try:
        maker = SpriteMaker(
            root, project, lambda previous: project.validate(), visible=False
        )
        target = next(
            label
            for label, key in maker.target_labels.items()
            if key == "mob:gobelin_archer"
        )
        maker.target.set(target)
        maker.selected_binding()
        assert maker.asset.get() == "gobelin_original"
        maker.weapon.set("arme_axe")
        maker.tint.set("#668844")
        maker.bind_sprite()
        assert (
            project.content["sprites"]["equipment"]["mob:gobelin_archer"] == "arme_axe"
        )
        assert project.content["sprites"]["assets"]["gobelin_original"] == before
        maker.load("arme_axe")
        maker.identifier.set("arme_axe_test")
        assert maker.apply()
        assert (
            project.content["sprites"]["equipment"]["mob:gobelin_archer"]
            == "arme_axe_test"
        )
        assert "arme_axe" not in project.content["sprites"]["assets"]
        maker.window.after_cancel(maker.timer)
        maker.animate()
        assert maker.preview_image.width() == 96
        project.save()
        assert (
            Project(project.directory).content["sprites"] == project.content["sprites"]
        )
    finally:
        if maker is not None:
            maker.window.after_cancel(maker.timer)
            maker.window.destroy()
        root.destroy()


def test_reptiles_have_their_own_body_instead_of_wolf_geometry(pack):
    _, data = pack
    lizard = data["assets"]["corps_lizard"]
    assert lizard["frames"] != data["assets"]["corps_wolf"]["frames"]
    for mob in ("salamandre_de_braise", "basilic_juvenile"):
        assert data["bindings"][f"mob:{mob}"] == "corps_lizard"


def test_art_refresh_preserves_personalized_bindings_equipment_and_tints(pack):
    project, data = pack
    data["bindings"]["mob:goblin"] = "corps_orc"
    data["equipment"]["mob:goblin"] = "arme_bow"
    data["colors"]["mob:goblin"] = "#123456"
    expected = {key: deepcopy(data[key]) for key in ("bindings", "equipment", "colors")}
    refreshed = populate(project, preserve_bindings=True)
    assert all(refreshed[key] == value for key, value in expected.items())
