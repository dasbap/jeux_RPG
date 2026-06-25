import math
import json
import os
import subprocess
import sys
from pathlib import Path


def _win_rate(side_dict: dict, fights: int) -> float:
    if fights <= 0:
        return 0.0
    return side_dict.get("wins", 0) / fights


def test_skill_duel_balancing_knight_vs_mage():
    """
    Balance criteria for Knight vs Mage using Sword Slash (forced on Knight):
    - With advantage (weak): win rate > 80%
    - Neutral: 40% <= win rate <= 60%

    Notes:
    - We run with a fixed seed and enough matches to reduce variance.
    - This test codifies the product balancing expectation; failing it indicates a tuning regression.
    """
    matches = 200
    # Run in a fresh Python process to avoid module/global state bleed
    out = Path(".data/balance/test_duel_knight_vs_mage.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "jeuxRPG._balance.run_simulation",
        "--mode","skill_duel",
        "--class-a","Knight",
        "--class-b","Mage",
        "--skill","Sword Slash",
        "--matches", str(matches),
        "--adv", "all",
        "--force","A",
        "--seed","42",
        "--out", str(out)
    ]
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
    with out.open("r", encoding="utf-8") as f:
        res = json.load(f)

    modes = res.get("modes", {})
    neutral = modes["neutral"]
    weak = modes["weak"]

    wr_neutral = _win_rate(neutral["side_a"], neutral["fights"])
    wr_weak = _win_rate(weak["side_a"], weak["fights"])

    # Assert expectations
    assert wr_weak >= 0.80, f"Weak advantage too low: {wr_weak:.2%} (expected >= 80%)"
    assert 0.40 <= wr_neutral <= 0.60, (
        f"Neutral winrate out of range: {wr_neutral:.2%} (expected 40%-60%)"
    )
