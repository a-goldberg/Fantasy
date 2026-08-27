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
            self.assertEqual(rejected.status, 400)
            rejected.read()
        finally:
            conn.close()
            httpd.shutdown()
            thread.join()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
