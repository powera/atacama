"""Tests for date_utils module."""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, Mock

from web.blueprints.trakaido.date_utils import (
    get_current_day_key,
    get_yesterday_day_key,
    get_week_ago_day_key,
    get_30_days_ago_day_key,
    get_30_day_date_range,
    DAILY_CUTOFF_HOUR,
    DAILY_CUTOFF_TIMEZONE
)


class DateUtilsTests(unittest.TestCase):
    """Test cases for date utility functions."""

    def test_get_current_day_key_after_cutoff(self):
        """Test get_current_day_key when current time is after 7am GMT."""
        # Create a fixed time after 7am GMT
        test_datetime = datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            # Configure the mock to return our test datetime
            mock_datetime_class.now.return_value = test_datetime
            # Import timedelta from the real datetime module
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_current_day_key()

            # Should return current date since we're after 7am
            self.assertEqual(result, "2025-10-28")

    def test_get_current_day_key_before_cutoff(self):
        """Test get_current_day_key when current time is before 7am GMT."""
        # Create a fixed time before 7am GMT (5am)
        test_datetime = datetime(2025, 10, 28, 5, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_current_day_key()

            # Should return previous date since we're before 7am
            self.assertEqual(result, "2025-10-27")

    def test_get_current_day_key_exactly_at_cutoff(self):
        """Test get_current_day_key when current time is exactly 7am GMT."""
        # Create a fixed time exactly at 7am GMT
        test_datetime = datetime(2025, 10, 28, 7, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_current_day_key()

            # Should return current date (7am is the cutoff, so >= 7am returns current)
            self.assertEqual(result, "2025-10-28")

    def test_get_yesterday_day_key_after_cutoff(self):
        """Test get_yesterday_day_key when current time is after 7am GMT."""
        test_datetime = datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_yesterday_day_key()

            # Should return one day back
            self.assertEqual(result, "2025-10-27")

    def test_get_yesterday_day_key_before_cutoff(self):
        """Test get_yesterday_day_key when current time is before 7am GMT."""
        test_datetime = datetime(2025, 10, 28, 5, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_yesterday_day_key()

            # Should return two days back
            self.assertEqual(result, "2025-10-26")

    def test_get_week_ago_day_key_after_cutoff(self):
        """Test get_week_ago_day_key when current time is after 7am GMT."""
        test_datetime = datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_week_ago_day_key()

            # Should return 7 days back from current date
            self.assertEqual(result, "2025-10-21")

    def test_get_week_ago_day_key_before_cutoff(self):
        """Test get_week_ago_day_key when current time is before 7am GMT."""
        test_datetime = datetime(2025, 10, 28, 5, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_week_ago_day_key()

            # Should return 7 days back from yesterday (8 days back from test_datetime)
            self.assertEqual(result, "2025-10-20")

    def test_get_30_days_ago_day_key_after_cutoff(self):
        """Test get_30_days_ago_day_key when current time is after 7am GMT."""
        test_datetime = datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_30_days_ago_day_key()

            # Should return 30 days back from current date
            self.assertEqual(result, "2025-09-28")

    def test_get_30_days_ago_day_key_before_cutoff(self):
        """Test get_30_days_ago_day_key when current time is before 7am GMT."""
        test_datetime = datetime(2025, 10, 28, 5, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = get_30_days_ago_day_key()

            # Should return 30 days back from yesterday (31 days back from test_datetime)
            self.assertEqual(result, "2025-09-27")

    def test_get_30_day_date_range_after_cutoff(self):
        """Test get_30_day_date_range when current time is after 7am GMT."""
        test_datetime = datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            start_date, end_date = get_30_day_date_range()

            # Should return 30-day range ending today
            self.assertEqual(end_date, "2025-10-28")
            # 29 days back + today = 30 days total
            self.assertEqual(start_date, "2025-09-29")

    def test_get_30_day_date_range_before_cutoff(self):
        """Test get_30_day_date_range when current time is before 7am GMT."""
        test_datetime = datetime(2025, 10, 28, 5, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)

            start_date, end_date = get_30_day_date_range()

            # Should return 30-day range ending yesterday
            self.assertEqual(end_date, "2025-10-27")
            # 29 days back from yesterday + yesterday = 30 days total
            self.assertEqual(start_date, "2025-09-28")

    def test_date_range_spans_30_days(self):
        """Test that get_30_day_date_range returns exactly 30 days."""
        test_datetime = datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc)

        with patch('web.blueprints.trakaido.date_utils.datetime') as mock_datetime_class:
            mock_datetime_class.now.return_value = test_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime_class.strptime = datetime.strptime

            start_date, end_date = get_30_day_date_range()

            # Calculate the number of days between start and end
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            days_diff = (end_dt - start_dt).days

            # Should be exactly 29 days difference (30 days inclusive)
            self.assertEqual(days_diff, 29)

    def test_constants(self):
        """Test that constants are set correctly."""
        self.assertEqual(DAILY_CUTOFF_HOUR, 7)
        self.assertEqual(DAILY_CUTOFF_TIMEZONE, timezone.utc)

    def test_get_current_day_key_returns_string(self):
        """Test get_current_day_key returns a string in YYYY-MM-DD format."""
        result = get_current_day_key()
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 10)
        self.assertEqual(result.count('-'), 2)
        # Verify it's a valid date
        datetime.strptime(result, "%Y-%m-%d")

    def test_get_yesterday_day_key_returns_string(self):
        """Test get_yesterday_day_key returns a string in YYYY-MM-DD format."""
        result = get_yesterday_day_key()
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 10)
        # Verify it's a valid date
        datetime.strptime(result, "%Y-%m-%d")

    def test_date_keys_are_ordered_correctly(self):
        """Test that date keys are in correct order (yesterday < current)."""
        # Use actual functions to ensure consistency
        yesterday = get_yesterday_day_key()
        current = get_current_day_key()
        week_ago = get_week_ago_day_key()
        thirty_days_ago = get_30_days_ago_day_key()

        # Convert to datetime for comparison
        yesterday_dt = datetime.strptime(yesterday, "%Y-%m-%d")
        current_dt = datetime.strptime(current, "%Y-%m-%d")
        week_ago_dt = datetime.strptime(week_ago, "%Y-%m-%d")
        thirty_days_ago_dt = datetime.strptime(thirty_days_ago, "%Y-%m-%d")

        # Verify ordering
        self.assertLess(yesterday_dt, current_dt)
        self.assertLess(week_ago_dt, current_dt)
        self.assertLess(thirty_days_ago_dt, current_dt)
        self.assertLess(thirty_days_ago_dt, week_ago_dt)


if __name__ == '__main__':
    unittest.main()
