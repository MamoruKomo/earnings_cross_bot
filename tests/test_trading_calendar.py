from datetime import date
import unittest

from src.trading_calendar import is_trading_day, next_trading_day, previous_trading_day


class TradingCalendarTest(unittest.TestCase):
    def test_weekend_is_not_trading_day(self):
        self.assertFalse(is_trading_day("2026-07-11"))

    def test_static_japanese_holiday_is_not_trading_day(self):
        self.assertFalse(is_trading_day("2026-07-20"))

    def test_next_and_previous_trading_day_skip_weekends_and_holidays(self):
        self.assertEqual(next_trading_day(date(2026, 7, 17)).isoformat(), "2026-07-21")
        self.assertEqual(previous_trading_day(date(2026, 7, 21)).isoformat(), "2026-07-17")


if __name__ == "__main__":
    unittest.main()
