"""Shared metrics calculators for stats dashboard payloads.

These helpers define canonical metric semantics that are used by both:
1) self-service journey stats endpoints, and
2) classroom manager endpoints.

Keeping definitions here prevents frontend/backend drift.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from trakaido.blueprints.stats_backend import get_journey_stats
from trakaido.blueprints.stats_schema import (
    CONTEXTUAL_EXPOSURE_TYPES,
    DIRECT_PRACTICE_TYPES,
)


def _get_stats_map(journey_stats: Any) -> Dict[str, Dict[str, Any]]:
    """Extract the per-word stats map from a JourneyStats object or raw dict."""
    if hasattr(journey_stats, "stats") and isinstance(journey_stats.stats, dict):
        return journey_stats.stats.get("stats", {})

    if isinstance(journey_stats, dict):
        return journey_stats.get("stats", {})

    return {}


def compute_words_known(journey_stats: Any, fallback_min_direct_correct: int = 3) -> int:
    """Compute `wordsKnown` from per-word stats.

    Metric definition:
    - Primary source of truth: `markedAsKnown == True`.
    - Optional fallback heuristic (for legacy records that never wrote
      `markedAsKnown`): if `markedAsKnown` is missing, count a word as known when
      total direct-practice correct answers >= `fallback_min_direct_correct`.

    This fallback intentionally does *not* override explicit
    `markedAsKnown == False`.
    """
    known_count = 0
    stats_map = _get_stats_map(journey_stats)

    for word_stats in stats_map.values():
        marked = word_stats.get("markedAsKnown")
        if marked is True:
            known_count += 1
            continue

        if marked is False:
            continue

        # Legacy fallback: only when key is absent or non-boolean.
        direct_correct_total = 0
        direct_practice = word_stats.get("directPractice", {})
        if isinstance(direct_practice, dict):
            for activity in DIRECT_PRACTICE_TYPES:
                activity_stats = direct_practice.get(activity, {})
                if isinstance(activity_stats, dict):
                    direct_correct_total += activity_stats.get("correct", 0)

        if direct_correct_total >= fallback_min_direct_correct:
            known_count += 1

    return known_count


def compute_daily_activity_summary(journey_stats: Any) -> Dict[str, Any]:
    """Aggregate direct/contextual counters into a normalized activity summary.

    Metric definition:
    - `directPractice.total*` values are sums across all direct-practice activity
      counters (`correct`, `incorrect`).
    - `contextualExposure.total*` values are sums across all contextual-exposure
      counters.
    - `combined.totalAnswered` is total correct + incorrect from both categories.
    """
    stats_map = _get_stats_map(journey_stats)

    by_activity = {
        "directPractice": {
            activity: {"correct": 0, "incorrect": 0} for activity in DIRECT_PRACTICE_TYPES
        },
        "contextualExposure": {
            activity: {"correct": 0, "incorrect": 0} for activity in CONTEXTUAL_EXPOSURE_TYPES
        },
    }

    for word_stats in stats_map.values():
        direct_practice = word_stats.get("directPractice", {})
        if isinstance(direct_practice, dict):
            for activity in DIRECT_PRACTICE_TYPES:
                activity_stats = direct_practice.get(activity, {})
                if isinstance(activity_stats, dict):
                    by_activity["directPractice"][activity]["correct"] += activity_stats.get(
                        "correct", 0
                    )
                    by_activity["directPractice"][activity]["incorrect"] += activity_stats.get(
                        "incorrect", 0
                    )

        contextual_exposure = word_stats.get("contextualExposure", {})
        if isinstance(contextual_exposure, dict):
            for activity in CONTEXTUAL_EXPOSURE_TYPES:
                activity_stats = contextual_exposure.get(activity, {})
                if isinstance(activity_stats, dict):
                    by_activity["contextualExposure"][activity]["correct"] += activity_stats.get(
                        "correct", 0
                    )
                    by_activity["contextualExposure"][activity]["incorrect"] += activity_stats.get(
                        "incorrect", 0
                    )

    return build_activity_summary_from_totals(by_activity)


def empty_activity_summary() -> Dict[str, Any]:
    """Return a zeroed activity summary with canonical shape."""
    return build_activity_summary_from_totals(
        {
            "directPractice": {
                activity: {"correct": 0, "incorrect": 0} for activity in DIRECT_PRACTICE_TYPES
            },
            "contextualExposure": {
                activity: {"correct": 0, "incorrect": 0} for activity in CONTEXTUAL_EXPOSURE_TYPES
            },
        }
    )


def build_activity_summary_from_totals(
    by_activity: Dict[str, Dict[str, Dict[str, int]]]
) -> Dict[str, Any]:
    """Build canonical activity summary from per-activity totals.

    Accepts an object shaped like:
    {
      "directPractice": {activity: {"correct": n, "incorrect": n}, ...},
      "contextualExposure": {activity: {"correct": n, "incorrect": n}, ...}
    }

    This is used by snapshot readers (e.g. SQLite daily snapshots) that already
    persist per-activity totals and need to expose the same summary contract
    without reconstructing per-word stats.
    """
    direct = by_activity.get("directPractice", {})
    contextual = by_activity.get("contextualExposure", {})

    direct_correct = sum(v.get("correct", 0) for v in direct.values())
    direct_incorrect = sum(v.get("incorrect", 0) for v in direct.values())
    contextual_correct = sum(v.get("correct", 0) for v in contextual.values())
    contextual_incorrect = sum(v.get("incorrect", 0) for v in contextual.values())

    return {
        "byActivity": by_activity,
        "directPractice": {
            "totalCorrect": direct_correct,
            "totalIncorrect": direct_incorrect,
            "totalAnswered": direct_correct + direct_incorrect,
        },
        "contextualExposure": {
            "totalCorrect": contextual_correct,
            "totalIncorrect": contextual_incorrect,
            "totalAnswered": contextual_correct + contextual_incorrect,
        },
        "combined": {
            "totalCorrect": direct_correct + contextual_correct,
            "totalIncorrect": direct_incorrect + contextual_incorrect,
            "totalAnswered": direct_correct
            + direct_incorrect
            + contextual_correct
            + contextual_incorrect,
        },
    }


def compute_member_summary(
    user_id: str,
    language: str = "lithuanian",
    journey_stats: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build normalized dashboard summary payload for one member.

    Metric definition:
    - `wordsTracked`: number of entries in stats map.
    - `wordsExposed`: number of entries with `exposed == True`.
    - `wordsKnown`: value from `compute_words_known`.
    - `activitySummary`: value from `compute_daily_activity_summary`.

    Args:
        user_id: User identifier, preserved in the response payload.
        language: Language namespace for stats storage.
        journey_stats: Optional preloaded stats object/dict. When omitted, this
            function reads from storage via `get_journey_stats`.
    """
    source_stats = (
        journey_stats if journey_stats is not None else get_journey_stats(str(user_id), language)
    )
    stats_map = _get_stats_map(source_stats)

    words_tracked = len(stats_map)
    words_exposed = sum(1 for word_stats in stats_map.values() if word_stats.get("exposed", False))

    activity_summary = compute_daily_activity_summary(source_stats)

    return {
        "userId": str(user_id),
        "language": language,
        "wordsTracked": words_tracked,
        "wordsExposed": words_exposed,
        "wordsKnown": compute_words_known(source_stats),
        "activitySummary": activity_summary,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
