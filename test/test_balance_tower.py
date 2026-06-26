from jeuxRPG._balance.simulator import simulate_tower


def test_balance_tower_mode_is_reproducible():
    first = simulate_tower(
        class_name="Knight",
        difficulty="easy",
        floors=20,
        seed=123,
        resolution="reward_curve",
    )
    second = simulate_tower(
        class_name="Knight",
        difficulty="easy",
        floors=20,
        seed=123,
        resolution="reward_curve",
    )

    assert first == second
    assert first["target_floor"] == 20
    assert 10 <= first["final_level"] <= 15


def test_balance_tower_xp_curve_does_not_match_floor_number():
    report = simulate_tower(
        class_name="Knight",
        difficulty="easy",
        floors=50,
        seed=123,
        resolution="reward_curve",
    )

    assert report["completed"] is True
    assert report["final_level"] < report["target_floor"]


def test_balance_easy_combat_reaches_floor_10_but_not_50():
    floor_10 = simulate_tower(
        class_name="Knight",
        difficulty="easy",
        floors=10,
        seed=0,
        resolution="combat",
    )
    floor_50 = simulate_tower(
        class_name="Knight",
        difficulty="easy",
        floors=50,
        seed=0,
        resolution="combat",
    )

    assert floor_10["completed"] is True
    assert floor_10["reached_floor"] == 10
    assert floor_50["completed"] is False
    assert floor_50["reached_floor"] < floor_50["target_floor"]
