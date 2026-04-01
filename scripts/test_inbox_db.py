import json
import os
import tempfile
import unittest
import sys

sys.path.insert(0, os.path.dirname(__file__))
import _inbox_db as db


class TestInboxDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, ".relay"), exist_ok=True)
        self.conn = db.init_db(self.tmp)

    def tearDown(self):
        self.conn.close()

    def test_init_creates_table(self):
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='inbox_items'"
        )
        self.assertIsNotNone(cur.fetchone())

    def test_create_item(self):
        item = db.create_item(self.conn, "sentry", "crash", "TypeError", {"error": "null ref"})
        self.assertEqual(item["source"], "sentry")
        self.assertEqual(item["status"], "new")
        self.assertEqual(item["payload"], {"error": "null ref"})
        self.assertIsNotNone(item["id"])

    def test_list_items_all(self):
        db.create_item(self.conn, "sentry", "crash", "Err1", {})
        db.create_item(self.conn, "slack", "feature_request", "Dark mode", {})
        items = db.list_items(self.conn)
        self.assertEqual(len(items), 2)

    def test_list_items_filtered(self):
        item = db.create_item(self.conn, "sentry", "crash", "Err1", {})
        db.update_status(self.conn, item["id"], "triaging")
        self.assertEqual(len(db.list_items(self.conn, status="new")), 0)
        self.assertEqual(len(db.list_items(self.conn, status="triaging")), 1)

    def test_get_item(self):
        item = db.create_item(self.conn, "sentry", "crash", "Err1", {})
        fetched = db.get_item(self.conn, item["id"])
        self.assertEqual(fetched["title"], "Err1")

    def test_get_item_missing(self):
        self.assertIsNone(db.get_item(self.conn, 9999))

    def test_update_status_valid(self):
        item = db.create_item(self.conn, "sentry", "crash", "Err1", {})
        db.update_status(self.conn, item["id"], "triaging")
        self.assertEqual(db.get_item(self.conn, item["id"])["status"], "triaging")

    def test_update_status_with_triage_report(self):
        item = db.create_item(self.conn, "sentry", "crash", "Err1", {})
        db.update_status(self.conn, item["id"], "triaging")
        report = {"verdict": "Fix this", "severity": "high"}
        db.update_status(self.conn, item["id"], "actionable", triage_report=report)
        fetched = db.get_item(self.conn, item["id"])
        self.assertEqual(fetched["triage_report"]["verdict"], "Fix this")

    def test_dismiss_from_any_state(self):
        item = db.create_item(self.conn, "sentry", "crash", "Err1", {})
        db.update_status(self.conn, item["id"], "dismissed")
        self.assertEqual(db.get_item(self.conn, item["id"])["status"], "dismissed")

    def test_dismiss_from_triaging(self):
        item = db.create_item(self.conn, "sentry", "crash", "Err1", {})
        db.update_status(self.conn, item["id"], "triaging")
        db.update_status(self.conn, item["id"], "dismissed")
        self.assertEqual(db.get_item(self.conn, item["id"])["status"], "dismissed")

    def test_invalid_transition_raises(self):
        item = db.create_item(self.conn, "sentry", "crash", "Err1", {})
        with self.assertRaises(ValueError):
            db.update_status(self.conn, item["id"], "actionable")

    def test_update_promoted_to(self):
        item = db.create_item(self.conn, "sentry", "crash", "Err1", {})
        db.update_status(self.conn, item["id"], "triaging")
        db.update_status(self.conn, item["id"], "actionable", triage_report={"verdict": "fix"})
        db.update_status(self.conn, item["id"], "promoted", promoted_to="bugs/active/err1-bug.md")
        fetched = db.get_item(self.conn, item["id"])
        self.assertEqual(fetched["promoted_to"], "bugs/active/err1-bug.md")

    def test_list_order_newest_first(self):
        db.create_item(self.conn, "sentry", "crash", "First", {})
        db.create_item(self.conn, "slack", "feature_request", "Second", {})
        items = db.list_items(self.conn)
        self.assertEqual(items[0]["title"], "Second")
        self.assertEqual(items[1]["title"], "First")


if __name__ == "__main__":
    unittest.main()
