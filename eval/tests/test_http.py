# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""The Jev-shaped HTTP client against a local stub server (no network)."""

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from eval import backends as be
from eval.questions import BANK, TASK


class Stub(BaseHTTPRequestHandler):
    # Set per test: (status, body bytes, delay in seconds).
    reply = (200, b"{}", 0.0)
    seen = []

    def do_POST(self):  # noqa: N802 (http.server's naming)
        n = int(self.headers["Content-Length"])
        Stub.seen.append((self.path, dict(self.headers), json.loads(self.rfile.read(n))))
        status, body, delay = Stub.reply
        time.sleep(delay)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def log_message(self, *args):
        pass


def good_answers():
    """A full answer set in the shapes OpenJev and s1 return."""
    out = {}
    for q in BANK:
        if q.type == "noul":
            out[q.key] = {"noul": 0.9}
        elif q.type == "choice":
            opts = q.options()
            out[q.key] = {
                "choice": opts[0],
                "probabilities": {
                    o: (0.7 if i == 0 else 0.3 / (len(opts) - 1)) for i, o in enumerate(opts)
                },
                "confidence": 0.5,
            }
        else:
            n = len(q.criteria)
            out[q.key] = {
                "score": 1.0,
                "probabilities": {str(i): (0.6 if i == 1 else 0.1) for i in range(n)},
            }
    return {"model": "stub", "answers": out, "usage": {"input_tokens": 1, "output_tokens": 0}}


class TestHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Stub.seen = []
        Stub.reply = (200, json.dumps(good_answers()).encode(), 0.0)

    def backend(self, **kw):
        env = {"PF_TEST_URL": self.url + "/", "PF_TEST_KEY": "secret-from-env"}
        args = {"api_key_env": "PF_TEST_KEY", "model": "m1"} | kw
        return be.JevHTTPBackend("test", "PF_TEST_URL", env=env, **args)

    def test_request_shape_and_auth(self):
        r = self.backend().ask("Warm bass drive", BANK)
        self.assertEqual(r.status, be.OK)
        path, headers, body = Stub.seen[0]
        self.assertEqual(path, "/v1/systemone")
        self.assertEqual(headers["Authorization"], "Bearer secret-from-env")
        self.assertEqual(body["model"], "m1")
        self.assertEqual(
            json.loads(body["state"]), {"task": TASK, "description": "Warm bass drive"}
        )
        self.assertEqual(set(body["questions"]), set(BANK.keys()))
        self.assertEqual(
            body["questions"]["needs_drive"],
            {"type": "noul", "instructions": BANK["needs_drive"].instructions},
        )
        self.assertEqual(r.answers["drive_amount"].value, 1)
        self.assertAlmostEqual(r.answers["instrument"].confidence, 0.7)
        self.assertGreater(r.latency_ms, 0)

    def test_object_state_and_custom_path(self):
        self.backend(path="/v1/decisions", state_format="object", model=None).ask("x", BANK)
        path, _, body = Stub.seen[0]
        self.assertEqual(path, "/v1/decisions")
        self.assertEqual(body["state"], {"task": TASK, "description": "x"})
        self.assertNotIn("model", body)

    def test_no_key_no_header(self):
        b = be.JevHTTPBackend("t", "U", env={"U": self.url})
        b.ask("x", BANK)
        self.assertNotIn("Authorization", Stub.seen[0][1])

    def test_http_error(self):
        Stub.reply = (500, b"oops", 0.0)
        r = self.backend().ask("x", BANK)
        self.assertEqual(r.status, be.ERROR)
        self.assertTrue(all(a.status == be.ERROR for a in r.answers.values()))
        self.assertIn("500", r.error)

    def test_timeout(self):
        Stub.reply = (200, b"{}", 0.5)
        r = self.backend(timeout_s=0.1).ask("x", BANK)
        self.assertEqual(r.status, be.TIMEOUT)

    def test_malformed_response(self):
        Stub.reply = (200, b"not json", 0.0)
        self.assertEqual(self.backend().ask("x", BANK).status, be.INVALID)

    def test_missing_question_is_invalid_only_for_it(self):
        body = good_answers()
        del body["answers"]["shaper"]
        Stub.reply = (200, json.dumps(body).encode(), 0.0)
        r = self.backend().ask("x", BANK)
        self.assertEqual(r.answers["shaper"].status, be.INVALID)
        self.assertEqual(r.answers["instrument"].status, be.OK)

    def test_connection_refused(self):
        b = be.JevHTTPBackend("t", "U", env={"U": "http://127.0.0.1:9"}, timeout_s=1)
        self.assertIn(b.ask("x", BANK).status, (be.ERROR, be.TIMEOUT))


if __name__ == "__main__":
    unittest.main()
