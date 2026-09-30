import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="Simulation RPG")
    parser.add_argument("--class", dest="class_name", default="Knight")
    parser.add_argument("--floors", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.floors < 1:
        parser.error("--floors doit être positif")
    from jeuxRPG._balance.simulator import simulate_tower

    print(json.dumps(simulate_tower(
        class_name=args.class_name, difficulty="easy", floors=args.floors,
        start_floor=1, enemies_per_floor=1, seed=args.seed,
        resolution="reward_curve",
    ), ensure_ascii=False, indent=2))
