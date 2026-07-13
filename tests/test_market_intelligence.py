from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from src.market_intelligence import load_market_intelligence


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class MarketIntelligenceTests(unittest.TestCase):
    def test_load_market_intelligence_compacts_and_sorts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "docs" / "data"
            write_json(data / "briefs.json", {"briefs": [{"date": "2026-07-12"}, {"date": "2026-07-13"}]})
            write_json(
                data / "tdnet.json",
                {"last_checked_jst": "2026-07-13T16:00:00+09:00", "items": [{"id": "old", "datetime_jst": "2026-07-13T15:00:00+09:00"}, {"id": "new", "datetime_jst": "2026-07-13T16:00:00+09:00"}]},
            )
            write_json(data / "watchlist_snapshots.json", {"snapshots": [{"datetime_jst": "2026-07-13T15:30:00+09:00", "items": []}]})
            write_json(data / "fundamentals_rankings.json", {"latest_month": "2026-07", "months": {"2026-07": {"metrics": {"roe": []}}}})

            result = load_market_intelligence(root, now=datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc))

            self.assertEqual(result["latest_brief"]["date"], "2026-07-13")
            self.assertEqual(result["disclosures"][0]["id"], "new")
            self.assertEqual(result["latest_watchlist"]["datetime_jst"], "2026-07-13T15:30:00+09:00")
            self.assertEqual(result["fundamentals"]["month"], "2026-07")
            self.assertEqual(result["health"]["overall"], "warning")

    def test_stale_watchlist_marks_market_data_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "docs" / "data"
            write_json(data / "briefs.json", {"briefs": [{"date": "2026-07-13"}]})
            write_json(data / "tdnet.json", {"last_checked_jst": "2026-07-13T16:00:00+09:00", "items": []})
            write_json(data / "watchlist_snapshots.json", {"snapshots": [{"datetime_jst": "2026-05-07T16:00:00+09:00", "items": []}]})
            write_json(data / "fundamentals_rankings.json", {"latest_month": "2026-07", "months": {"2026-07": {"generated_at": "2026-07-01T08:00:00+09:00"}}})

            result = load_market_intelligence(root, now=datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc))

            watchlist = next(item for item in result["health"]["sources"] if item["key"] == "watchlist")
            self.assertEqual(watchlist["status"], "stale")
            self.assertEqual(result["health"]["overall"], "stale")
            self.assertIn("判断に使用しない", watchlist["message"])
