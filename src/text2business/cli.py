from __future__ import annotations

import argparse
import json

from text2business.evals import execute_eval_case
from text2business.scenarios import EVAL_CASES


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic Text2Business scenario")
    parser.add_argument("--scenario", choices=sorted(EVAL_CASES), default="full")
    parser.add_argument("--list-scenarios", action="store_true")
    args = parser.parse_args()
    if args.list_scenarios:
        print("\n".join(sorted(EVAL_CASES)))
        return
    result = execute_eval_case(EVAL_CASES[args.scenario]).result
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
