from copy import deepcopy

import pytest
from test_living_world import no_network  # noqa: F401
from test_tactics import act, near, party

from jeuxRPG.multiplayer import combat_visuals, tactics
from jeuxRPG.multiplayer.service import GameError


def test_only_validated_attack_produces_an_animation_cue():
    data = party()
    before = deepcopy(data)
    with pytest.raises(GameError):
        act(data, "strike", target="mob")
    assert data == before
    near(data)
    act(data, "strike", target="mob")
    cue = data["battle"]["visual_events"][-1]
    assert cue["kind"] == "strike" and cue["actor"] == "p0" and cue["target"] == "mob"
    assert cue["source"] == [9, 5] and cue["destination"] == [9, 4]
    assert cue["amount"] >= 0


def test_casting_and_resolution_have_separate_cues_and_cancel_has_no_impact():
    for cancelled in (False, True):
        data = party()
        near(data)
        act(data, "skill", skill_name="Sword Slash", target="mob")
        unit = data["battle"]["players"]["p0"]
        assert data["battle"]["visual_events"][-1]["kind"] == "cast"
        ends_at = unit["casting"]["ends_at"]
        if cancelled:
            unit.pop("casting")
        tactics.complete_casts(data, ends_at + 0.01, lambda: 0.5)
        kinds = [cue["kind"] for cue in data["battle"]["visual_events"]]
        assert ("skill" in kinds) is (not cancelled)


def test_visual_queue_is_bounded_and_public_data_is_not_a_mutable_world_reference():
    data = party()
    near(data)
    for i in range(100):
        combat_visuals.emit(data, "p0", "mob", i * 0.01)
    assert len(data["battle"]["visual_events"]) == 32
    public = combat_visuals.public(data, "p0", 1)
    public[0]["source"][0] = 10000
    assert data["battle"]["visual_events"][0]["source"] == [9, 5]
    assert combat_visuals.public(data, "p0", 100) == []


def test_effects_outside_the_observers_vision_do_not_reveal_positions():
    data=party(count=2)
    far=[tactics.PLAYER_VISION*3+1,1]
    data["battle"]["players"]["p1"]["position"]=far
    data["mobs"][0]["position"]=far[:]
    combat_visuals.emit(data,"p1","mob",0)
    assert data["battle"]["visual_events"]
    assert combat_visuals.public(data,"p0",0)==[]
