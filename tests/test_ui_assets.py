import unittest
import threading
import time
import urllib.request
from server import ThreadedHTTPServer, ModManagerHandler

UI_PORT = 5571

class TestUIAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadedHTTPServer(("127.0.0.1", UI_PORT), ModManagerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_index_html(self):
        url = f"http://127.0.0.1:{UI_PORT}/index.html"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode("utf-8")
            # Verify Form 1, Form 2, Form 3, Form 4 exist
            self.assertIn('id="cfg-api-key"', html)
            self.assertIn('id="input-mod-url"', html)
            self.assertIn('id="cfg-cookie-session"', html)
            self.assertIn('id="cfg-cookie-refresh"', html)
            self.assertIn('id="btn-download-install"', html)
            self.assertIn('id="btn-check-updates"', html)

    def test_style_css(self):
        url = f"http://127.0.0.1:{UI_PORT}/style.css"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            css = resp.read().decode("utf-8")
            self.assertIn("--bg-main: #09090b", css)

    def test_app_js(self):
        url = f"http://127.0.0.1:{UI_PORT}/app.js"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            js = resp.read().decode("utf-8")
            self.assertIn("function inspectUrl", js)
            self.assertIn("function downloadAndInstall", js)
            self.assertIn("function checkUpdatesBatch", js)

if __name__ == "__main__":
    unittest.main()
