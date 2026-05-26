"""Emit deterministic AIGC filter quality metrics for Story M3.4."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import aigc_filter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.aigc.datasets import BENIGN_PROMPTS, RED_TEAM_PROMPTS  # noqa: E402


def build_report() -> dict[str, object]:
    red_team_results = [aigc_filter.filter(prompt, tier="strict") for prompt in RED_TEAM_PROMPTS]
    benign_results = [aigc_filter.filter(prompt, tier="strict") for prompt in BENIGN_PROMPTS]

    blocked_red_team = sum(result.blocked for result in red_team_results)
    blocked_benign = sum(result.blocked for result in benign_results)

    return {
        "module_version": aigc_filter.__version__,
        "red_team_count": len(RED_TEAM_PROMPTS),
        "benign_count": len(BENIGN_PROMPTS),
        "red_team_block_rate": blocked_red_team / len(RED_TEAM_PROMPTS),
        "benign_false_positive_rate": blocked_benign / len(BENIGN_PROMPTS),
        "red_team_gate": ">=0.98",
        "benign_gate": "<=0.02",
    }


def main() -> None:
    sys.stdout.write(json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
