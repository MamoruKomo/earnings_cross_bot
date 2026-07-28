import unittest
from unittest.mock import patch
import requests
from datetime import date

from src.public_data_client import CalendarTableParser, PublicDataError, fetch_earnings_calendar, metric


class PublicDataClientTest(unittest.TestCase):
    def test_network_error_is_normalized(self):
        with patch("src.public_data_client.requests.get", side_effect=requests.ConnectionError("offline")):
            with self.assertRaises(PublicDataError):
                fetch_earnings_calendar(date(2026, 7, 28))
    def test_calendar_table_parser(self):
        parser = CalendarTableParser()
        parser.feed("""
        <table><tr><td>07/13</td><td>-</td><td><a>カネコ種</a><div>(1376/東S)</div></td>
        <td>連本決算</td><td>水産・農林業</td><td>176</td></tr></table>
        """)
        self.assertEqual(parser.rows[0][:4], ["07/13", "-", "カネコ種 (1376/東S)", "連本決算"])

    def test_financial_metric(self):
        source = '<tr><th>営業利益<br>(百万円)</th><td>1,900<br><span>+25.7%</span></td></tr>'
        value, yoy = metric(source, "営業利益")
        self.assertEqual(value, 1_900_000_000)
        self.assertAlmostEqual(yoy, 0.257)


if __name__ == "__main__": unittest.main()
