import os
import unittest
import tempfile
import shutil
import zipfile
import json
from engine.mod_installer import ModInstaller

class TestModInstaller(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp()
        self.game_path = os.path.join(self.test_root, "Cyberpunk 2077")
        self.staging_base = os.path.join(self.test_root, "staging")
        os.makedirs(self.game_path, exist_ok=True)
        os.makedirs(self.staging_base, exist_ok=True)

        # Mock vanilla exe
        self.vanilla_exe_dir = os.path.join(self.game_path, "bin", "x64")
        os.makedirs(self.vanilla_exe_dir, exist_ok=True)
        self.vanilla_exe = os.path.join(self.vanilla_exe_dir, "Cyberpunk2077.exe")
        with open(self.vanilla_exe, "wb") as f:
            f.write(b"ORIGINAL_GAME_BINARY_DATA")

        self.installer = ModInstaller(self.game_path, staging_base=self.staging_base)

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    def _create_mock_zip(self, files_dict, zip_name="test_mod.zip"):
        zip_path = os.path.join(self.test_root, zip_name)
        with zipfile.ZipFile(zip_path, "w") as z:
            for rel_path, content in files_dict.items():
                z.writestr(rel_path, content)
        return zip_path

    def test_invariant_1_no_silent_clobber(self):
        """Invariant 1: Attempts to overwrite core game executable must raise RuntimeError."""
        malicious_files = {
            "bin/x64/Cyberpunk2077.exe": b"MALICIOUS_OVERWRITE_PAYLOAD"
        }
        zip_path = self._create_mock_zip(malicious_files, "malicious.zip")

        with self.assertRaises(RuntimeError) as ctx:
            self.installer.install_from_archive(zip_path, "Malicious_Mod")
        self.assertIn("Safety Violation (Invariant 1)", str(ctx.exception))

        # Assert vanilla exe was NOT modified
        with open(self.vanilla_exe, "rb") as f:
            self.assertEqual(f.read(), b"ORIGINAL_GAME_BINARY_DATA")

    def test_successful_deploy_and_manifest(self):
        """Invariant 4 & 6: Clean install, manifest creation, and source archive auto-purge."""
        valid_files = {
            "r6/scripts/MyMod/script.reds": b"print('Hello Mod')",
            "r6/tweaks/mymod.yaml": b"tweak: value"
        }
        zip_path = self._create_mock_zip(valid_files, "valid_mod.zip")

        res = self.installer.install_from_archive(
            zip_path, "MyMod", mod_id=99999, version="1.0.0", purge_archive=True
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["files_deployed"], 2)
        self.assertTrue(res["archive_purged"])
        # Invariant 6: Archive file must be deleted
        self.assertFalse(os.path.exists(zip_path))

        # Check deployed files exist in game
        deployed_script = os.path.join(self.game_path, "r6", "scripts", "MyMod", "script.reds")
        self.assertTrue(os.path.exists(deployed_script))

        # Check manifest
        manifest_file = os.path.join(self.game_path, ".gemi_mods", "MyMod", "manifest.json")
        self.assertTrue(os.path.exists(manifest_file))
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["mod_name"], "MyMod")
        self.assertEqual(manifest["mod_id"], 99999)
        self.assertEqual(len(manifest["files"]), 2)

    def test_invariant_5_reversible_undeploy(self):
        """Invariant 5: Undeploy removes files, but user modifications are backed up."""
        files = {
            "r6/scripts/TestMod/config.reds": b"original_config"
        }
        zip_path = self._create_mock_zip(files, "test_undeploy.zip")
        self.installer.install_from_archive(zip_path, "TestMod", purge_archive=False)

        deployed_file = os.path.join(self.game_path, "r6", "scripts", "TestMod", "config.reds")
        self.assertTrue(os.path.exists(deployed_file))

        # User customizes the file in-place
        with open(deployed_file, "wb") as f:
            f.write(b"USER_CUSTOM_TUNED_SETTINGS")

        # Undeploy
        undep_res = self.installer.undeploy_mod("TestMod")
        self.assertTrue(undep_res["success"])
        self.assertEqual(undep_res["backed_up_count"], 1)

        # File should be removed from game root, but saved in user_overwrites
        self.assertFalse(os.path.exists(deployed_file))
        backup_file = os.path.join(self.game_path, ".gemi_mods", "TestMod", "user_overwrites", "config.reds")
        self.assertTrue(os.path.exists(backup_file))
        with open(backup_file, "rb") as f:
            self.assertEqual(f.read(), b"USER_CUSTOM_TUNED_SETTINGS")

if __name__ == "__main__":
    unittest.main()
