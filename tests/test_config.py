import os
import unittest
import tempfile
import shutil
import json
from engine.config_manager import ConfigManager

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_prefills(self):
        cfg = ConfigManager(base_dir=self.test_dir)
        all_cfg = cfg.get_all()
        self.assertIn("nexus_api_key", all_cfg)
        self.assertIn("nexusmods_session", all_cfg)
        self.assertIn("nexusmods_session_refresh", all_cfg)
        self.assertIn("game_path", all_cfg)
        self.assertIn("watch_dir", all_cfg)
        self.assertTrue(len(all_cfg["nexus_api_key"]) > 10)

    def test_cookie_header_generation(self):
        cfg = ConfigManager(base_dir=self.test_dir)
        cfg.update({
            "nexusmods_session": "test_sess_123",
            "nexusmods_session_refresh": "test_ref_456"
        })
        cookie_header = cfg.get_cookie_header()
        self.assertIn("nexusmods_session=test_sess_123", cookie_header)
        self.assertIn("nexusmods_session_refresh=test_ref_456", cookie_header)

    def test_update_and_persistence(self):
        cfg = ConfigManager(base_dir=self.test_dir)
        cfg.update({"custom_setting": "val_99"})
        
        # Re-open config from disk
        cfg2 = ConfigManager(base_dir=self.test_dir)
        self.assertEqual(cfg2.get("custom_setting"), "val_99")

if __name__ == "__main__":
    unittest.main()
