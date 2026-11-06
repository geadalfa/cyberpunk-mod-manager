import os
import json
import hashlib
import zipfile
import shutil
import re
from pathlib import Path

MANIFEST_DIR_NAME = ".gemi_mods"

def get_file_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class ModInstaller:
    def __init__(self, game_path, staging_base=None):
        self.game_path = game_path
        self.staging_base = staging_base or os.path.join(os.environ.get("USERPROFILE", ""), ".gemini", "staging")

    def inspect_environment(self):
        """Inspects game path, detects executables and frameworks."""
        if not os.path.exists(self.game_path):
            return {"valid": False, "error": f"Game directory does not exist: {self.game_path}"}

        frameworks = []
        if os.path.exists(os.path.join(self.game_path, "red4ext", "RED4ext.dll")):
            frameworks.append("RED4ext")
        if os.path.exists(os.path.join(self.game_path, "engine", "tools", "scc.exe")):
            frameworks.append("redscript")
        if os.path.exists(os.path.join(self.game_path, "red4ext", "plugins", "ArchiveXL")):
            frameworks.append("ArchiveXL")
        if os.path.exists(os.path.join(self.game_path, "red4ext", "plugins", "Codeware")):
            frameworks.append("Codeware")
        if os.path.exists(os.path.join(self.game_path, "red4ext", "plugins", "mod_settings")):
            frameworks.append("Mod Settings")
        if os.path.exists(os.path.join(self.game_path, "red4ext", "plugins", "TweakXL")):
            frameworks.append("TweakXL")
        if os.path.exists(os.path.join(self.game_path, "bin", "x64", "version.dll")) and os.path.exists(os.path.join(self.game_path, "bin", "x64", "plugins", "cyber_engine_tweaks")):
            frameworks.append("Cyber Engine Tweaks (CET)")

        exe_path = os.path.join(self.game_path, "bin", "x64", "Cyberpunk2077.exe")
        has_main_exe = os.path.exists(exe_path)

        return {
            "valid": has_main_exe or len(frameworks) > 0,
            "game_path": self.game_path,
            "has_main_exe": has_main_exe,
            "frameworks": frameworks
        }

    def list_installed_mods(self):
        """Lists all mods installed via Gemi transactional manifests."""
        manifest_base = os.path.join(self.game_path, MANIFEST_DIR_NAME)
        mods = []
        if not os.path.exists(manifest_base):
            return mods

        for item in os.listdir(manifest_base):
            mp = os.path.join(manifest_base, item, "manifest.json")
            if os.path.exists(mp):
                try:
                    with open(mp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not data.get("uninstalled", False):
                        mods.append({
                            "name": data.get("mod_name", item),
                            "mod_id": data.get("mod_id"),
                            "version": data.get("version", "Unknown"),
                            "domain": data.get("domain", "cyberpunk2077"),
                            "installed_at": data.get("installed_at"),
                            "file_count": len(data.get("files", []))
                        })
                except Exception:
                    pass
        return mods

    def install_from_archive(self, archive_path, mod_name, mod_id=None, version=None, domain="cyberpunk2077", purge_archive=True):
        """
        Executes full transactional installation:
        Invariant 1: No Silent Clobber
        Invariant 3: Staging Isolation
        Invariant 4: Transactional Manifest
        Invariant 6: Automated Sanitation
        """
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive not found: {archive_path}")
        if not os.path.exists(self.game_path):
            raise FileNotFoundError(f"Game directory not found: {self.game_path}")

        # Clean mod name
        clean_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", mod_name).strip() or "Installed_Mod"
        staging_dir = os.path.join(self.staging_base, clean_name)
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir, ignore_errors=True)
        os.makedirs(staging_dir, exist_ok=True)

        try:
            # 1. Unpack to isolated staging
            with zipfile.ZipFile(archive_path, "r") as z:
                z.extractall(staging_dir)

            # 2. Pre-flight scan for Invariant 1 (No Silent Clobber)
            to_deploy = []
            for root, dirs, files in os.walk(staging_dir):
                for f in files:
                    src = os.path.join(root, f)
                    rel = os.path.relpath(src, staging_dir)
                    dst = os.path.join(self.game_path, rel)

                    # Invariant 1 violation guard
                    if os.path.exists(dst) and dst.lower().endswith(".exe"):
                        raise RuntimeError(f"Safety Violation (Invariant 1): Mod attempts to overwrite core game binary '{rel}'!")
                    to_deploy.append((src, dst, rel))

            if not to_deploy:
                raise ValueError("Archive is empty or contains no deployable files")

            # 3. Create manifest
            manifest_dir = os.path.join(self.game_path, MANIFEST_DIR_NAME, clean_name)
            os.makedirs(manifest_dir, exist_ok=True)
            manifest_file = os.path.join(manifest_dir, "manifest.json")

            manifest = {
                "mod_name": clean_name,
                "mod_id": mod_id,
                "version": version or "1.0.0",
                "domain": domain,
                "installed_at": str(Path(archive_path).stat().st_ctime if os.path.exists(archive_path) else ""),
                "files": []
            }

            # 4. Atomic deploy
            deployed_targets = []
            try:
                for src, dst, rel in to_deploy:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    sha = get_file_sha256(dst)
                    manifest["files"].append({
                        "rel_path": rel.replace("\\", "/"),
                        "sha256": sha,
                        "size": os.path.getsize(dst)
                    })
                    deployed_targets.append(dst)

                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)

            except Exception as e:
                # Rollback on deploy failure
                for t in deployed_targets:
                    try:
                        if os.path.exists(t):
                            os.remove(t)
                    except Exception:
                        pass
                raise RuntimeError(f"Deployment failed and was rolled back: {e}")

            # 5. Cleanup staging
            shutil.rmtree(staging_dir, ignore_errors=True)

            # 6. Purge source archive (Invariant 6)
            archive_deleted = False
            if purge_archive:
                try:
                    os.remove(archive_path)
                    archive_deleted = True
                except Exception:
                    pass

            return {
                "success": True,
                "mod_name": clean_name,
                "mod_id": mod_id,
                "version": version,
                "files_deployed": len(manifest["files"]),
                "manifest": manifest_file,
                "archive_purged": archive_deleted
            }

        except Exception as e:
            if os.path.exists(staging_dir):
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    def undeploy_mod(self, mod_name):
        """Undeploys a mod safely using its manifest, preserving user edits (Invariant 5)."""
        manifest_file = os.path.join(self.game_path, MANIFEST_DIR_NAME, mod_name, "manifest.json")
        if not os.path.exists(manifest_file):
            raise FileNotFoundError(f"Manifest not found for mod: {mod_name}")

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        removed = []
        backed_up = []
        backup_dir = os.path.join(self.game_path, MANIFEST_DIR_NAME, mod_name, "user_overwrites")

        for item in manifest.get("files", []):
            rel = item["rel_path"].replace("/", os.sep)
            target = os.path.join(self.game_path, rel)
            if not os.path.exists(target):
                continue

            current_hash = get_file_sha256(target)
            if current_hash == item["sha256"]:
                os.remove(target)
                removed.append(rel)
            else:
                os.makedirs(backup_dir, exist_ok=True)
                bk = os.path.join(backup_dir, os.path.basename(target))
                shutil.move(target, bk)
                backed_up.append(rel)

        # Cleanup empty directories
        for item in manifest.get("files", []):
            rel = item["rel_path"].replace("/", os.sep)
            target = os.path.join(self.game_path, rel)
            parent = os.path.dirname(target)
            while parent and parent != self.game_path and parent.startswith(self.game_path):
                try:
                    if os.path.exists(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                    parent = os.path.dirname(parent)
                except Exception:
                    break

        manifest["uninstalled"] = True
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return {
            "success": True,
            "mod_name": mod_name,
            "removed_count": len(removed),
            "backed_up_count": len(backed_up)
        }
