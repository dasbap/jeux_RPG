import statistics
import time
import tracemalloc

import pytest

from jeuxRPG._balance.simulator import simulate_duel
from jeuxRPG._class.character import Character


@pytest.mark.performance
def test_character_creation_and_duel_budget(record_property):
    samples = []
    tracemalloc.start()
    try:
        for batch in range(5):
            start = time.perf_counter()
            for index in range(100):
                character = Character.create("Knight", f"perf-{batch}-{index}", "Benchmark")
                assert character.is_alive()
            samples.append(time.perf_counter() - start)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    start = time.perf_counter()
    result = simulate_duel("Knight", "Goblin", matches=100, seed=42, max_rounds=100)
    duration = time.perf_counter() - start
    record_property("creation_100_median_seconds", statistics.median(samples))
    record_property("creation_peak_bytes", peak)
    record_property("duel_100_seconds", duration)
    assert result.fights == 100
    assert result.side_a.wins + result.side_b.wins + result.draws == 100
    assert statistics.median(samples) < 5
    assert peak < 64 * 1024 * 1024
    assert duration < 10
