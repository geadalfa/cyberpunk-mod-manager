import unittest
import threading
import time
import urllib.request
import json
import socket
from server import ThreadedHTTPServer, ModManagerHandler

TEST_PORT = 5569

class TestServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadedHTTPServer(("127.0.0.1", TEST_PORT), ModManagerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _request(self, path, method="GET", body=None):
        url = f"http://127.0.0.1:{TEST_PORT}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())

    def test_get_config(self):
        res = self._request("/api/config")
        self.assertTrue(res.get("success"))
        self.assertIn("nexus_api_key", res.get("config", {}))

    def test_inspect_game(self):
        res = self._request("/api/inspect-game")
        self.assertTrue(res.get("success"))
        self.assertIn("environment", res)

    def test_installed_mods(self):
        res = self._request("/api/installed-mods")
        self.assertTrue(res.get("success"))
        self.assertIsInstance(res.get("mods"), list)

if __name__ == "__main__":
    unittest.main()
