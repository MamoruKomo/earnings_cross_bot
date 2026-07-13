import sqlite3
import unittest

from src import db


class NotificationRunTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        db.init_db(self.conn)

    def test_sent_notification_is_deduplicated(self):
        self.assertFalse(db.notification_sent(self.conn, "2026-07-13", "morning"))
        db.record_notification(self.conn, "2026-07-13", "morning", "sent", {"candidate_count": 0})
        self.assertTrue(db.notification_sent(self.conn, "2026-07-13", "morning"))

    def test_failed_notification_can_retry(self):
        db.record_notification(self.conn, "2026-07-13", "morning", "failed", {})
        self.assertFalse(db.notification_sent(self.conn, "2026-07-13", "morning"))


if __name__ == "__main__":
    unittest.main()
