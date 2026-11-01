"""Checks that the teaching UI preserves execution identity and source grounding."""
from datetime import date
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import tempfile

import demo
import workflow as w


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = demo.Demo(os.environ["CUSTOMERS_PATH"], os.environ["KB_PATH"], date(2026, 11, 1))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), demo.handler_for(cls.state))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def get(self, path):
        with urlopen(self.url + path) as r:
            return json.load(r)

    def test_counts_recomputed(self):
        d = self.get("/api/summary")
        self.assertEqual(d["long_tail"], 405)
        self.assertEqual(d["segments"]["基金风险解读"], 59)

    def test_profile_only_allowed_candidate(self):
        d = self.get("/api/profile?id=CUST_0005")
        self.assertEqual([s["id"] for s in d["candidates"]], ["fund_risk"])
        self.assertNotIn("customer_id", d["model_profile"])
        self.assertNotIn("total_assets", d["model_profile"])

    def test_current_mode_never_calls_model(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(demo, "ROOT", Path(tmp)), patch.object(w, "local_model") as model:
            d = self.state.run("CUST_0005", "current", "local")
            self.assertEqual(d["result"]["status"], "HOLD_NO_FRESH_SOURCE")
            self.assertFalse(d["live_model_response_received"])
            model.assert_not_called()

    def test_offline_identity_and_saved_envelope(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(demo, "ROOT", Path(tmp)):
            d = self.state.run("CUST_0005", "simulation", "offline")
            self.assertEqual(d["result"]["provider"], "offline")
            self.assertFalse(d["live_model_response_received"])
            self.assertFalse(d["result"]["actual_send"])
            saved = json.loads((Path(tmp)/d["saved_file"]).read_text())
            self.assertEqual(saved["view_kind"], "new_run")

    @unittest.skipUnless((demo.ROOT / "live_local_outputs/examples.json").is_file(),
                         "历史证据不在代码仓库；该项在本地演示包执行")
    def test_historical_record_not_new_run(self):
        d = self.get("/api/record?id=CUST_0005")
        self.assertEqual(d["view_kind"], "historical_record")
        self.assertFalse(d["live_model_response_received"])
        self.assertEqual(d["result"]["provider"], "local")

    def test_source_matches_actual_file(self):
        d = self.get("/api/source?fn=validate_decision")
        self.assertIn("unretrieved_sentence", d["code"])
        self.assertIn(f'{d["start_line"]:>3}  def validate_decision', d["code"])

    def test_post_requires_page_token(self):
        request = Request(self.url+"/api/run", data=b'{}', headers={"Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 403)

    def test_post_rejects_cross_origin(self):
        request = Request(self.url+"/api/run", data=b'{}', headers={"Content-Type":"application/json", "X-Demo-Token":self.state.token,"Origin":"https://example.com"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 403)

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError):
            self.state.run("arbitrary_customer", "simulation", "local")

    def test_host_rebinding_rejected(self):
        req = Request(self.url+"/api/summary", headers={"Host":"foreign.invalid"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(req)
        self.assertEqual(caught.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
