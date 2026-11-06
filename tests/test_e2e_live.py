import os
import unittest
import tempfile
import shutil
from engine.config_manager import ConfigManager
from engine.nexus_client import NexusClient
from engine.mod_installer import ModInstaller

class TestLiveEndToEnd(unittest.TestCase):
    def setUp(self):
        self.cfg = ConfigManager()
        self.client = NexusClient(
            api_key=self.cfg.get("nexus_api_key"),
            cookie_header=self.cfg.get_cookie_header()
        )
        self.test_root = tempfile.mkdtemp()
        self.mock_game = os.path.join(self.test_root, "Cyberpunk")
        os.makedirs(self.mock_game, exist_ok=True)
        self.installer = ModInstaller(self.mock_game, staging_base=os.path.join(self.test_root, "staging"))

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    def test_live_account_and_url_inspection(self):
        # 1. Validate real API key
        user = self.client.validate_key(self.cfg.get("nexus_api_key"))
        self.assertEqual(user["name"], "geadalfa")
        self.assertEqual(user["user_id"], 86073658)

        # 2. Inspect Mod 16565
        mod_info = self.client.get_mod_info("cyberpunk2077", 16565)
        self.assertEqual(mod_info["name"], "More Weapon Filters")

        # 3. Resolve direct CDN URL via session cookie
        download_url = self.client.resolve_download_url("cyberpunk2077", 16565, 168622)
        self.assertIn("nexus-cdn.com", download_url)
        self.assertIn("user_id=86073658", download_url)

        # 4. Stream download to temp archive
        target_zip = os.path.join(self.test_root, "test_download.zip")
        self.client.download_file(download_url, target_zip)
        self.assertTrue(os.path.exists(target_zip))
        self.assertGreater(os.path.getsize(target_zip), 1000)

        # 5. Deploy transactionally to mock game
        install_res = self.installer.install_from_archive(
            archive_path=target_zip,
            mod_name="More_Weapon_Filters",
            mod_id=16565,
            version="4.1",
            purge_archive=True
        )
        self.assertTrue(install_res["success"])
        self.assertEqual(install_res["files_deployed"], 4)
        # Verify archive auto-purged
        self.assertFalse(os.path.exists(target_zip))

        # Verify deployed files in mock game
        reds_file = os.path.join(self.mock_game, "r6", "scripts", "MoreWeaponFilters", "MoreWeaponFilters.reds")
        self.assertTrue(os.path.exists(reds_file))

        # 6. Verify undeploy
        undep_res = self.installer.undeploy_mod("More_Weapon_Filters")
        self.assertTrue(undep_res["success"])
        self.assertEqual(undep_res["removed_count"], 4)
        self.assertFalse(os.path.exists(reds_file))

if __name__ == "__main__":
    unittest.main()
