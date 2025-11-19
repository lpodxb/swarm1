from __future__ import annotations
from typing import List

from lab.storage import get_strategies_summary


def get_approved_strategies_for_pair(pair: str, timeframe: str) -> List[str]:
    """
    Development version:
    - Allow strategies with status in {'approved', 'experimental', 'insufficient_data'}
      so that we can see the system trade even before full lab validation.
    Later, tighten this back to only 'approved'.
    """
    items = get_strategies_summary()
    allowed_status = {"approved", "experimental", "insufficient_data"}

    result: List[str] = []
    for s in items:
        if (
            s.get("pair") == pair
            and s.get("timeframe") == timeframe
            and s.get("status") in allowed_status
        ):
            result.append(s["id"])
    return result
