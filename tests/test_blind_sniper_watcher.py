import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import blind_sniper_watcher as w


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cursor = Path(self.tmp.name) / "cursor.json"
        self.sent = []

    def run_pass(self, items, deliver=None):
        return w.run_once(target="r:w", correlation_id="c1", fetch=lambda: items,
                          deliver=deliver or self.sent.append, cursor_path=self.cursor)

    def test_new_change_then_dedup(self):
        runs = [{"id": 1, "status": "completed", "conclusion": "failure", "url": "u1"}]
        d1 = self.run_pass(runs)
        self.assertEqual([e["class"] for e in d1["events"]], ["new"])
        d2 = self.run_pass(runs)  # same state: no report
        self.assertEqual(d2["events"], [])
        self.assertEqual(len(self.sent), 1)
        runs[0] = {"id": 1, "status": "completed", "conclusion": "success", "url": "u1"}
        d3 = self.run_pass(runs)
        self.assertEqual([e["class"] for e in d3["events"]], ["recovered"])
        self.assertEqual(d3["correlation_id"], "c1")
        self.assertIn("not continuous monitoring", d3["scope"])

    def test_cursor_not_advanced_when_delivery_fails(self):
        runs = [{"id": 7, "status": "completed", "conclusion": "failure", "url": "u"}]

        def boom(_digest):
            raise OSError("route down")

        with self.assertRaises(OSError):
            self.run_pass(runs, deliver=boom)
        self.assertFalse(self.cursor.exists())
        d = self.run_pass(runs)  # retried, reported exactly once
        self.assertEqual(len(d["events"]), 1)
        self.assertEqual(len(self.run_pass(runs)["events"]), 0)

    def test_corrupt_cursor_and_stop_condition_fail_closed(self):
        self.cursor.write_text("{not json")
        with self.assertRaises(w.WatcherError):
            self.run_pass([])
        self.cursor.unlink()
        many = [{"id": i, "status": "queued", "conclusion": None, "url": "u"} for i in range(201)]
        with self.assertRaises(w.WatcherError):
            self.run_pass(many)

    def test_module_has_no_scheduler_or_background_loop(self):
        text = Path(w.__file__).read_text()
        for forbidden in ("sleep(", "while True", "threading", "cron", "schedule."):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
