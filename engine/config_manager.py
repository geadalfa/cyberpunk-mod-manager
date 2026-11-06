import os
import sys
import json
import re

CONFIG_FILE_NAME = "config.json"

DEFAULT_PREFILLS = {
    "nexus_api_key": "lZ7cZkkWNEP1TFVU5062amGYlmF+rcCAS6UB3CMEb32V85AonA==--gUobvw8cOOyIcehE--VyJ+Dom6ep3KghUum7efNg==",
    "nexusmods_session": "a19e907855eb6dbce257e5beac0d7b8b",
    "nexusmods_session_refresh": "1793943186",
    "game_path": r"F:\SteamLibrary\steamapps\common\Cyberpunk 2077",
    "watch_dir": r"D:\Game Mentah",
    "keep_archives": False
}

class ConfigManager:
    def __init__(self, base_dir=None):
        if base_dir:
            self.base_dir = base_dir
        elif getattr(sys, "frozen", False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, CONFIG_FILE_NAME)
        self.config = self._load()

    def _load(self):
        cfg = dict(DEFAULT_PREFILLS)
        
        # Check system existing key file if present
        sys_key_file = os.path.expanduser(r"~\.gemini\config\nexus_api_key.txt")
        if os.path.exists(sys_key_file):
            try:
                with open(sys_key_file, "r", encoding="utf-8") as f:
                    k = f.read().strip()
                    if k:
                        cfg["nexus_api_key"] = k
            except Exception:
                pass

        # Check system existing cookie file if present
        sys_cookie_file = os.path.expanduser(r"~\.gemini\config\nexus_cookie.txt")
        if os.path.exists(sys_cookie_file):
            try:
                with open(sys_cookie_file, "r", encoding="utf-8") as f:
                    c = f.read().strip()
                    if "nexusmods_session=" in c:
                        m_sess = re.search(r"nexusmods_session=([a-zA-Z0-9]+)", c)
                        if m_sess:
                            cfg["nexusmods_session"] = m_sess.group(1)
                    if "nexusmods_session_refresh=" in c:
                        m_ref = re.search(r"nexusmods_session_refresh=([0-9]+)", c)
                        if m_ref:
                            cfg["nexusmods_session_refresh"] = m_ref.group(1)
            except Exception:
                pass

        # Override with local config.json if exists
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    cfg.update(saved)
            except Exception:
                pass
        else:
            # First run: save pre-fills
            self._save_to_disk(cfg)

        return cfg

    def _save_to_disk(self, data):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def get_all(self):
        return dict(self.config)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def update(self, new_data):
        self.config.update(new_data)
        self._save_to_disk(self.config)
        return dict(self.config)

    def get_cookie_header(self):
        sess = self.config.get("nexusmods_session", "").strip()
        ref = self.config.get("nexusmods_session_refresh", "").strip()
        parts = []
        if sess:
            parts.append(f"nexusmods_session={sess}")
        if ref:
            parts.append(f"nexusmods_session_refresh={ref}")
        return "; ".join(parts)
