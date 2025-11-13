"""Snapshot management and progress calculations for Trakaido user statistics."""

# Standard library imports
import os
from datetime import datetime, timedelta
from typing import Any, Dict

# Local application imports
from .shared import logger
from .stats_schema import JourneyStats, DailyStats, DIRECT_PRACTICE_TYPES, CONTEXTUAL_EXPOSURE_TYPES
from .date_utils import (
    get_current_day_key,
    get_week_ago_day_key,
    get_30_days_ago_day_key,
    get_30_day_date_range
)
from .nonce_utils import cleanup_old_nonce_files


##############################################################################
# Daily Snapshot Management Functions
##############################################################################

def compress_previous_day_files(user_id: str, language: str = "lithuanian") -> bool:
    """Compress previous day files to GZIP during daily rotation."""
    try:
        current_day = get_current_day_key()
        current_date = datetime.strptime(current_day, "%Y-%m-%d")

        # Get all available dates for this user and language
        available_dates = DailyStats.get_available_dates(user_id, "current", language)
        available_dates.extend(DailyStats.get_available_dates(user_id, "yesterday", language))
        available_dates = list(set(available_dates))  # Remove duplicates

        compressed_count = 0

        for date_str in available_dates:
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                # Only compress files from previous days (not current day)
                if file_date < current_date:
                    for stats_type in ["current", "yesterday"]:
                        daily_stats = DailyStats(user_id, date_str, stats_type, language)

                        # Only compress if regular file exists and GZIP doesn't
                        if (os.path.exists(daily_stats.file_path) and
                            not os.path.exists(daily_stats.gzip_file_path)):

                            if daily_stats.compress_to_gzip():
                                compressed_count += 1
                                logger.debug(f"Compressed {date_str}_{stats_type}.json for user {user_id} language {language}")

            except ValueError:
                # Skip invalid date formats
                continue

        if compressed_count > 0:
            logger.info(f"Compressed {compressed_count} previous day files for user {user_id} language {language}")

        return True
    except Exception as e:
        logger.error(f"Error compressing previous day files for user {user_id} language {language}: {str(e)}")
        return False


def ensure_daily_snapshots(user_id: str, language: str = "lithuanian") -> bool:
    """Ensure that daily snapshots are properly set up for the current day."""
    try:
        current_day = get_current_day_key()

        # Check if we need to create yesterday's snapshot
        yesterday_daily_stats = DailyStats(user_id, current_day, "yesterday", language)
        if not DailyStats.exists(user_id, current_day, "yesterday", language) or yesterday_daily_stats.is_empty():
            journey_stats = JourneyStats(user_id, language)
            yesterday_daily_stats.stats = journey_stats.stats
            yesterday_daily_stats.save()
            logger.debug(f"Created yesterday snapshot for user {user_id} day {current_day} language {language}")

        # Ensure current snapshot exists
        current_daily_stats = DailyStats(user_id, current_day, "current", language)
        if not DailyStats.exists(user_id, current_day, "current", language):
            journey_stats = JourneyStats(user_id, language)
            current_daily_stats.stats = journey_stats.stats
            current_daily_stats.save()
            logger.debug(f"Created current snapshot for user {user_id} day {current_day} language {language}")

        # Compress previous day files once current day is set up
        compress_previous_day_files(user_id, language)

        # Clean up old nonce files (keep only today and yesterday)
        cleanup_old_nonce_files(user_id, language)

        return True
    except Exception as e:
        logger.error(f"Error ensuring daily snapshots for user {user_id} language {language}: {str(e)}")
        return False


def find_best_baseline(user_id: str, target_day: str, max_days: int, language: str = "lithuanian") -> DailyStats:
    """Find the best available baseline stats for comparison over a given period.

    Args:
        user_id: The user ID to find baseline stats for
        target_day: The target day to find baseline stats for (YYYY-MM-DD format)
        max_days: Maximum number of days to look forward from target day

    Returns:
        DailyStats object with the best available baseline stats
    """
    try:
        # Try exact target day first
        target_daily_stats = DailyStats(user_id, target_day, "current", language)
        if DailyStats.exists(user_id, target_day, "current", language) and not target_daily_stats.is_empty():
            return target_daily_stats

        # If target date doesn't exist, walk forward and find the oldest "yesterday" snapshot
        # that is less than max_days old from the target date
        target_date = datetime.strptime(target_day, "%Y-%m-%d")
        yesterday_dates = DailyStats.get_available_dates(user_id, "yesterday", language)

        best_daily_stats = None
        best_date = None

        # Check up to max_days forward from target
        for days_forward in range(1, max_days + 1):
            check_date = target_date + timedelta(days=days_forward)
            check_day_key = check_date.strftime("%Y-%m-%d")

            if check_day_key in yesterday_dates:
                check_daily_stats = DailyStats(user_id, check_day_key, "yesterday", language)
                if not check_daily_stats.is_empty():
                    # We want the oldest (earliest) "yesterday" snapshot, so take the first one we find
                    if best_date is None or check_date < best_date:
                        best_daily_stats = check_daily_stats
                        best_date = check_date

        if best_daily_stats:
            return best_daily_stats
        else:
            period_name = "weekly" if max_days <= 7 else "monthly"
            logger.debug(f"No suitable {period_name} baseline found for user {user_id} language {language}, using empty baseline")
            empty_stats = DailyStats(user_id, target_day, "current", language)
            empty_stats.stats = {"stats": {}}
            return empty_stats

    except Exception as e:
        period_name = "weekly" if max_days <= 7 else "monthly"
        logger.error(f"Error finding {period_name} baseline for user {user_id} language {language}: {str(e)}")
        empty_stats = DailyStats(user_id, target_day, "current", language)
        empty_stats.stats = {"stats": {}}
        return empty_stats


##############################################################################
# Progress Calculation Functions
##############################################################################

def calculate_progress_delta(current_stats: DailyStats, baseline_stats: DailyStats) -> Dict[str, Any]:
    """Calculate the delta between current stats and baseline stats.

    Returns a progress structure with deltas for:
    - directPractice activities
    - contextualExposure (sentences)
    - exposed words (new and total)
    """
    progress = {
        "directPractice": {activity: {"correct": 0, "incorrect": 0} for activity in DIRECT_PRACTICE_TYPES},
        "contextualExposure": {activity: {"correct": 0, "incorrect": 0} for activity in CONTEXTUAL_EXPOSURE_TYPES},
        "exposed": {"new": 0, "total": 0}
    }

    # Calculate progress for each word
    for word_key, current_word_stats in current_stats.stats["stats"].items():
        baseline_word_stats = baseline_stats.get_word_stats(word_key)

        # Count exposed words
        if current_word_stats.get("exposed", False):
            progress["exposed"]["total"] += 1
            # Count new exposed words (words that exist in current but not in baseline)
            if not baseline_word_stats or not baseline_word_stats.get("exposed", False):
                progress["exposed"]["new"] += 1

        # Calculate directPractice deltas
        if "directPractice" in current_word_stats:
            for activity_type in DIRECT_PRACTICE_TYPES:
                if activity_type in current_word_stats["directPractice"]:
                    current_activity = current_word_stats["directPractice"][activity_type]
                    current_correct = current_activity.get("correct", 0)
                    current_incorrect = current_activity.get("incorrect", 0)

                    baseline_correct = 0
                    baseline_incorrect = 0
                    if (baseline_word_stats and "directPractice" in baseline_word_stats and
                        activity_type in baseline_word_stats["directPractice"]):
                        baseline_activity = baseline_word_stats["directPractice"][activity_type]
                        baseline_correct = baseline_activity.get("correct", 0)
                        baseline_incorrect = baseline_activity.get("incorrect", 0)

                    # Calculate delta
                    progress["directPractice"][activity_type]["correct"] += max(0, current_correct - baseline_correct)
                    progress["directPractice"][activity_type]["incorrect"] += max(0, current_incorrect - baseline_incorrect)

        # Calculate contextualExposure deltas
        if "contextualExposure" in current_word_stats:
            for activity_type in CONTEXTUAL_EXPOSURE_TYPES:
                if activity_type in current_word_stats["contextualExposure"]:
                    current_activity = current_word_stats["contextualExposure"][activity_type]
                    current_correct = current_activity.get("correct", 0)
                    current_incorrect = current_activity.get("incorrect", 0)

                    baseline_correct = 0
                    baseline_incorrect = 0
                    if (baseline_word_stats and "contextualExposure" in baseline_word_stats and
                        activity_type in baseline_word_stats["contextualExposure"]):
                        baseline_activity = baseline_word_stats["contextualExposure"][activity_type]
                        baseline_correct = baseline_activity.get("correct", 0)
                        baseline_incorrect = baseline_activity.get("incorrect", 0)

                    progress["contextualExposure"][activity_type]["correct"] += max(0, current_correct - baseline_correct)
                    progress["contextualExposure"][activity_type]["incorrect"] += max(0, current_incorrect - baseline_incorrect)

    return progress


def calculate_daily_progress(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """Calculate daily progress by comparing current and yesterday snapshots."""
    try:
        current_day = get_current_day_key()

        if not ensure_daily_snapshots(user_id, language):
            return {"error": "Failed to ensure daily snapshots"}

        yesterday_daily_stats = DailyStats(user_id, current_day, "yesterday", language)
        current_daily_stats = DailyStats(user_id, current_day, "current", language)

        # Calculate progress delta
        daily_progress = calculate_progress_delta(current_daily_stats, yesterday_daily_stats)

        return {"currentDay": current_day, "progress": daily_progress}
    except Exception as e:
        logger.error(f"Error calculating daily progress for user {user_id}: {str(e)}")
        return {"error": str(e)}


def calculate_weekly_progress(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """Calculate weekly progress by comparing current stats with stats from 7 days ago."""
    try:
        current_day = get_current_day_key()
        week_ago_day = get_week_ago_day_key()

        if not ensure_daily_snapshots(user_id, language):
            return {"error": "Failed to ensure daily snapshots"}

        current_daily_stats = DailyStats(user_id, current_day, "current", language)
        week_ago_daily_stats = find_best_baseline(user_id, week_ago_day, 7, language)

        # Calculate progress delta
        weekly_progress = calculate_progress_delta(current_daily_stats, week_ago_daily_stats)

        actual_baseline_day = week_ago_daily_stats.date if not week_ago_daily_stats.is_empty() else None

        return {
            "currentDay": current_day,
            "targetBaselineDay": week_ago_day,
            "actualBaselineDay": actual_baseline_day,
            "progress": weekly_progress
        }
    except Exception as e:
        logger.error(f"Error calculating weekly progress for user {user_id}: {str(e)}")
        return {"error": str(e)}


def calculate_monthly_progress(user_id: str, language: str = "lithuanian") -> Dict[str, Any]:
    """
    Calculate monthly stats with daily breakdown and monthly aggregate for the past 30 days.

    Returns two main components:
    1. monthlyAggregate - Aggregate stats for the entire 30-day period (similar to weekly stats)
    2. dailyData - Per-day stats showing:
       - questionsAnswered: Number of questions answered on each day
       - exposedWordsCount: Total number of exposed words on each day
       - newlyExposedWords: Number of words newly exposed on each day (compared to most recent previous day with data)
    """
    try:
        current_day = get_current_day_key()
        thirty_days_ago_day = get_30_days_ago_day_key()

        if not ensure_daily_snapshots(user_id, language):
            return {"error": "Failed to ensure daily snapshots"}

        # Get current stats and baseline for summary
        current_daily_stats = DailyStats(user_id, current_day, "current", language)
        thirty_days_ago_daily_stats = find_best_baseline(user_id, thirty_days_ago_day, 30, language)

        # Calculate monthly aggregate stats using delta helper
        monthly_aggregate = calculate_progress_delta(current_daily_stats, thirty_days_ago_daily_stats)

        # Get daily breakdown for the past 30 days
        start_date_str, end_date_str = get_30_day_date_range()
        available_dates = DailyStats.get_available_dates(user_id, "current", language)

        daily_data = []

        # Generate all dates in the past 30 days
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            questions_answered_on_day = 0
            exposed_words_count_on_day = 0
            newly_exposed_words_on_day = 0

            if date_str in available_dates:
                daily_stats = DailyStats(user_id, date_str, "current", language)
                if not daily_stats.is_empty():
                    # Calculate questions answered on this day (sum of all correct + incorrect for all stat types)
                    for word_key, word_stats in daily_stats.stats["stats"].items():
                        # Count directPractice activities
                        if "directPractice" in word_stats:
                            for activity_type in DIRECT_PRACTICE_TYPES:
                                if activity_type in word_stats["directPractice"]:
                                    activity_stats = word_stats["directPractice"][activity_type]
                                    if isinstance(activity_stats, dict):
                                        questions_answered_on_day += activity_stats.get("correct", 0)
                                        questions_answered_on_day += activity_stats.get("incorrect", 0)
                        # Count contextualExposure activities
                        if "contextualExposure" in word_stats:
                            for activity_type in CONTEXTUAL_EXPOSURE_TYPES:
                                if activity_type in word_stats["contextualExposure"]:
                                    activity_stats = word_stats["contextualExposure"][activity_type]
                                    if isinstance(activity_stats, dict):
                                        questions_answered_on_day += activity_stats.get("correct", 0)
                                        questions_answered_on_day += activity_stats.get("incorrect", 0)

                    # Count exposed words on this day
                    for word_key, word_stats in daily_stats.stats["stats"].items():
                        if word_stats.get("exposed", False):
                            exposed_words_count_on_day += 1

                    # Calculate new exposed words on this day by finding the most recent previous data
                    if current_date > start_date:
                        # Find the most recent previous day with data
                        most_recent_prev_date = None
                        most_recent_prev_stats = None

                        # Start from yesterday and go backwards until we find data
                        check_date = current_date - timedelta(days=1)
                        while check_date >= start_date:
                            check_date_str = check_date.strftime("%Y-%m-%d")
                            if check_date_str in available_dates:
                                prev_daily_stats = DailyStats(user_id, check_date_str, "current", language)
                                if not prev_daily_stats.is_empty():
                                    most_recent_prev_date = check_date_str
                                    most_recent_prev_stats = prev_daily_stats
                                    break
                            check_date -= timedelta(days=1)

                        if most_recent_prev_stats:
                            # Count words that are exposed today but weren't exposed in the most recent previous day with data
                            for word_key, word_stats in daily_stats.stats["stats"].items():
                                if word_stats.get("exposed", False):
                                    prev_word_stats = most_recent_prev_stats.get_word_stats(word_key)
                                    if not prev_word_stats or not prev_word_stats.get("exposed", False):
                                        newly_exposed_words_on_day += 1
                        else:
                            # If no previous data within the period, try to find data from before the period
                            baseline_found = False
                            all_available_dates = DailyStats.get_available_dates(user_id, "current", language)
                            earlier_dates = [d for d in all_available_dates if datetime.strptime(d, "%Y-%m-%d") < start_date]

                            if earlier_dates:
                                # Use the most recent date before our period as baseline
                                baseline_date = max(earlier_dates)
                                baseline_stats = DailyStats(user_id, baseline_date, "current", language)

                                if not baseline_stats.is_empty():
                                    baseline_found = True
                                    # Count words that are exposed on this day but weren't in baseline
                                    for word_key, word_stats in daily_stats.stats["stats"].items():
                                        if word_stats.get("exposed", False):
                                            baseline_word_stats = baseline_stats.get_word_stats(word_key)
                                            if not baseline_word_stats or not baseline_word_stats.get("exposed", False):
                                                newly_exposed_words_on_day += 1

                            # If no valid baseline found, set newly exposed to 0 since we can't determine what's new
                            if not baseline_found:
                                newly_exposed_words_on_day = 0
                    else:
                        # First day of the 30-day period with data
                        # Try to find a baseline from before the 30-day period to compare with
                        baseline_found = False

                        # Look for snapshots before the start date
                        all_available_dates = DailyStats.get_available_dates(user_id, "current", language)
                        earlier_dates = [d for d in all_available_dates if datetime.strptime(d, "%Y-%m-%d") < start_date]

                        if earlier_dates:
                            # Use the most recent date before our period as baseline
                            baseline_date = max(earlier_dates)
                            baseline_stats = DailyStats(user_id, baseline_date, "current", language)

                            if not baseline_stats.is_empty():
                                baseline_found = True
                                # Count words that are exposed on first day but weren't in baseline
                                for word_key, word_stats in daily_stats.stats["stats"].items():
                                    if word_stats.get("exposed", False):
                                        baseline_word_stats = baseline_stats.get_word_stats(word_key)
                                        if not baseline_word_stats or not baseline_word_stats.get("exposed", False):
                                            newly_exposed_words_on_day += 1

                        # If no valid baseline found, set newly exposed to 0 since we can't determine what's new
                        if not baseline_found:
                            newly_exposed_words_on_day = 0

            daily_data.append({
                "date": date_str,
                "questionsAnswered": questions_answered_on_day,
                "exposedWordsCount": exposed_words_count_on_day,
                "newlyExposedWords": newly_exposed_words_on_day
            })

            current_date += timedelta(days=1)

        actual_baseline_day = thirty_days_ago_daily_stats.date if not thirty_days_ago_daily_stats.is_empty() else None

        # Format the period description
        period_description = f"Past 30 Days ({start_date_str} to {end_date_str})"

        return {
            "currentMonth": period_description,
            "currentDay": current_day,
            "targetBaselineDay": thirty_days_ago_day,
            "actualBaselineDay": actual_baseline_day,
            "monthlyAggregate": monthly_aggregate,
            "dailyData": daily_data
        }
    except Exception as e:
        logger.error(f"Error calculating monthly progress for user {user_id}: {str(e)}")
        return {"error": str(e)}
