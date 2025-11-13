"""Date and time utilities for Trakaido stats management."""

from datetime import datetime, timezone, timedelta

# Daily stats constants
DAILY_CUTOFF_HOUR = 7  # 0700 GMT
DAILY_CUTOFF_TIMEZONE = timezone.utc


def get_current_day_key() -> str:
    """Get the current day key based on 0700 GMT cutoff."""
    now = datetime.now(DAILY_CUTOFF_TIMEZONE)
    if now.hour < DAILY_CUTOFF_HOUR:
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")


def get_yesterday_day_key() -> str:
    """Get yesterday's day key based on 0700 GMT cutoff."""
    now = datetime.now(DAILY_CUTOFF_TIMEZONE)
    if now.hour < DAILY_CUTOFF_HOUR:
        now = now - timedelta(days=2)  # Two days back if before cutoff
    else:
        now = now - timedelta(days=1)  # One day back if after cutoff
    return now.strftime("%Y-%m-%d")


def get_week_ago_day_key() -> str:
    """Get the day key for 7 days ago based on 0700 GMT cutoff."""
    now = datetime.now(DAILY_CUTOFF_TIMEZONE)
    if now.hour < DAILY_CUTOFF_HOUR:
        now = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    return week_ago.strftime("%Y-%m-%d")


def get_30_days_ago_day_key() -> str:
    """Get the day key for exactly 30 days ago based on 0700 GMT cutoff."""
    now = datetime.now(DAILY_CUTOFF_TIMEZONE)
    if now.hour < DAILY_CUTOFF_HOUR:
        now = now - timedelta(days=1)
    thirty_days_ago = now - timedelta(days=30)
    return thirty_days_ago.strftime("%Y-%m-%d")


def get_30_day_date_range() -> tuple[str, str]:
    """Get the date range for the past 30 days (30 days ago to today)."""
    now = datetime.now(DAILY_CUTOFF_TIMEZONE)
    if now.hour < DAILY_CUTOFF_HOUR:
        now = now - timedelta(days=1)

    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=29)).strftime("%Y-%m-%d")  # 29 days back + today = 30 days total

    return start_date, end_date
