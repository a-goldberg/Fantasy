"""Focused safety checks for the loopback draft-state API."""
import importlib.util
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("draft_server", ROOT / "2026" / "App" / "serve.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class DraftStateApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = server.LIVE_STATE
        server.LIVE_STATE = Path(self.tmp.name) / "live.json"
        self.handler = object.__new__(server.Handler)

    def tearDown(self):
        server.LIVE_STATE = self.original
        self.tmp.cleanup()

    def test_empty_state_contains_configured_keepers(self):
        state = self.handler.live_state()
        self.assertEqual(state["version"], 0)
        self.assertTrue(any(pick["player"] == "Matthew Stafford" for pick in state["picks"]))

    def test_accepts_valid_live_pick(self):
        picks = self.handler.live_state()["picks"] + [{"overall": 1, "player": "Bijan Robinson", "type": "live"}]
        self.handler.validate_picks(picks)

    def test_rejects_duplicate_overall_and_unknown_player(self):
        with self.assertRaisesRegex(ValueError, "only once"):
            self.handler.validate_picks([{"overall": 1, "player": "Bijan Robinson"}, {"overall": 1, "player": "Jahmyr Gibbs"}])
        with self.assertRaisesRegex(ValueError, "Unknown player"):
            self.handler.validate_picks([{"overall": 1, "player": "Not A Real Player"}])

    def test_saved_state_is_atomic_and_reapplies_keepers(self):
        self.handler.save_live_state({"version": 3, "picks": [{"overall": 1, "player": "Bijan Robinson", "type": "live"}], "history": []})
        state = self.handler.live_state()
        self.assertEqual(state["version"], 3)
        self.assertTrue(any(pick["player"] == "Bijan Robinson" for pick in state["picks"]))
        self.assertTrue(any(pick["type"] == "keeper" for pick in state["picks"]))

    def test_http_sync_requires_version_and_validates_payload(self):
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]
            conn = http.client.HTTPConnection("127.0.0.1", port)
            body = json.dumps({"expected_version": 0, "picks": [{"overall": 1, "player": "Bijan Robinson", "type": "live"}]})
            conn.request("POST", "/api/draft-state/sync", body, {"Content-Type": "application/json"})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["version"], 1)
            conn.request("POST", "/api/draft-state/sync", body, {"Content-Type": "application/json"})
            rejected = conn.getresponse()
            self.assertEqual(rejected.status, 409)
            rejected.read()
        finally:
            conn.close()
            httpd.shutdown()
            thread.join()
            httpd.server_close()

    def request(self, path, payload, origin=None):
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1])
            headers = {"Content-Type": "application/json"}
            if origin:
                headers["Origin"] = origin
            conn.request("POST", path, json.dumps(payload), headers)
            response = conn.getresponse()
            body = json.loads(response.read())
            status = response.status
            conn.close()
            return status, body
        finally:
            httpd.shutdown()
            thread.join()
            httpd.server_close()

    def test_http_pick_is_atomic_canonical_and_in_sequence(self):
        status, picked = self.request("/api/draft-state/picks", {
            "expected_version": 0,
            "overall": 1,
            "player": "James Cook",
            "source": "draftkick",
        })
        self.assertEqual(status, 200)
        pick = next(item for item in picked["picks"] if item["overall"] == 1)
        self.assertEqual(pick["player"], "James Cook III")
        self.assertEqual(pick["manager"], "Ori")
        self.assertEqual(picked["current_overall"], 2)

        status, conflict = self.request("/api/draft-state/picks", {
            "expected_version": 1,
            "overall": 3,
            "player": "Josh Allen",
        })
        self.assertEqual(status, 409)
        self.assertIn("Expected overall pick 2", conflict["error"])

    def test_http_reconcile_merges_and_rejects_conflicts(self):
        status, reconciled = self.request("/api/draft-state/reconcile", {
            "expected_version": 0,
            "picks": [
                {"overall": 1, "player": "Bijan Robinson", "source": "draftkick"},
                {"overall": 2, "player": "Jahmyr Gibbs", "source": "draftkick"},
                {"overall": 3, "player": "Josh Allen", "source": "draftkick"},
            ],
        })
        self.assertEqual(status, 200)
        self.assertEqual(reconciled["current_overall"], 4)

        status, conflict = self.request("/api/draft-state/reconcile", {
            "expected_version": 1,
            "picks": [{"overall": 2, "player": "Lamar Jackson"}],
        })
        self.assertEqual(status, 409)
        self.assertIn("conflicts", conflict["error"])

    def test_http_undo_reset_and_origin_protection(self):
        self.request("/api/draft-state/picks", {"expected_version": 0, "overall": 1, "player": "Bijan Robinson"})
        status, undone = self.request("/api/draft-state/undo", {"expected_version": 1})
        self.assertEqual(status, 200)
        self.assertEqual(undone["current_overall"], 1)
        status, rejected = self.request("/api/draft-state/reset", {"expected_version": 2, "confirm": False})
        self.assertEqual(status, 400)
        self.assertIn("confirm", rejected["error"])
        status, reset = self.request("/api/draft-state/reset", {"expected_version": 2, "confirm": True})
        self.assertEqual(status, 200)
        self.assertEqual(reset["current_overall"], 1)
        status, _ = self.request("/api/draft-state/picks", {"expected_version": 3, "overall": 1, "player": "Bijan Robinson"}, "https://evil.example")
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
