from __future__ import annotations

import argparse
import json

from text2business.scenarios import SCENARIOS
from text2business.workflow import run_case


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic Text2Business scenario")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="full")
    parser.add_argument("--list-scenarios", action="store_true")
    args = parser.parse_args()
    if args.list_scenarios:
        print("\n".join(sorted(SCENARIOS)))
        return
    result = run_case(SCENARIOS[args.scenario])
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
