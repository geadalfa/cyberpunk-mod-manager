import unittest
from engine.nexus_client import NexusClient

class TestNexusClient(unittest.TestCase):
    def test_parse_mod_url_standard(self):
        url = "https://www.nexusmods.com/cyberpunk2077/mods/16565"
        res = NexusClient.parse_mod_url(url)
        self.assertEqual(res["domain"], "cyberpunk2077")
        self.assertEqual(res["mod_id"], 16565)
        self.assertIsNone(res["file_id"])

    def test_parse_mod_url_with_tabs(self):
        url = "https://www.nexusmods.com/cyberpunk2077/mods/16565?tab=files&file_id=168622"
        res = NexusClient.parse_mod_url(url)
        self.assertEqual(res["domain"], "cyberpunk2077")
        self.assertEqual(res["mod_id"], 16565)
        self.assertEqual(res["file_id"], 168622)

    def test_parse_nxm_url(self):
        url = "nxm://cyberpunk2077/mods/16565/files/168622?key=xyz123&expires=1793959026&user_id=86073658"
        res = NexusClient.parse_mod_url(url)
        self.assertEqual(res["domain"], "cyberpunk2077")
        self.assertEqual(res["mod_id"], 16565)
        self.assertEqual(res["file_id"], 168622)
        self.assertEqual(res["nxm_key"], "xyz123")
        self.assertEqual(res["nxm_expires"], "1793959026")

    def test_parse_raw_id(self):
        res = NexusClient.parse_mod_url("16565")
        self.assertEqual(res["domain"], "cyberpunk2077")
        self.assertEqual(res["mod_id"], 16565)

    def test_invalid_url(self):
        with self.assertRaises(ValueError):
            NexusClient.parse_mod_url("https://google.com/search")

if __name__ == "__main__":
    unittest.main()
