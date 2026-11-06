import os
import sys
import time
import json
import socket
import threading
import subprocess
import webbrowser
import urllib.parse
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

# Mandatory stream protection in windowed mode (prevents crashes when sys.stdout is None)
if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w")
    except Exception:
        pass

# Add current directory and bundles to sys.path for PyInstaller --onedir mode
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # PyInstaller bundle directory
    CURRENT_DIR = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.dirname(sys.executable)

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from engine.config_manager import ConfigManager
from engine.nexus_client import NexusClient
from engine.mod_installer import ModInstaller

PORT = 5560
last_heartbeat = time.time()
has_received_heartbeat = False

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class ModManagerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.base_dir = CURRENT_DIR
        self.static_dir = os.path.join(self.base_dir, "static")
        super().__init__(*args, directory=self.static_dir, **kwargs)

    def log_message(self, format, *args):
        # Silent logger to prevent I/O blocking in windowed mode
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        global last_heartbeat, has_received_heartbeat
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/heartbeat":
            last_heartbeat = time.time()
            has_received_heartbeat = True
            return self._send_json({"status": "alive", "timestamp": last_heartbeat})

        elif path == "/api/shutdown":
            self._send_json({"status": "shutting_down"})
            threading.Timer(0.15, lambda: os._exit(0)).start()
            return

        elif path == "/api/config":
            cfg = ConfigManager(self.base_dir)
            return self._send_json({"success": True, "config": cfg.get_all()})

        elif path == "/api/installed-mods":
            cfg = ConfigManager(self.base_dir)
            installer = ModInstaller(cfg.get("game_path"))
            mods = installer.list_installed_mods()
            return self._send_json({"success": True, "mods": mods})

        elif path == "/api/inspect-game":
            cfg = ConfigManager(self.base_dir)
            installer = ModInstaller(cfg.get("game_path"))
            info = installer.inspect_environment()
            return self._send_json({"success": True, "environment": info})

        return super().do_GET()

    def do_POST(self):
        global last_heartbeat, has_received_heartbeat
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("content-length", 0))
        post_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        
        try:
            body = json.loads(post_body)
        except Exception:
            body = {}

        if path == "/api/heartbeat":
            last_heartbeat = time.time()
            has_received_heartbeat = True
            return self._send_json({"status": "alive", "timestamp": last_heartbeat})

        elif path == "/api/shutdown":
            self._send_json({"status": "shutting_down"})
            threading.Timer(0.15, lambda: os._exit(0)).start()
            return

        cfg = ConfigManager(self.base_dir)

        if path == "/api/config":
            updated = cfg.update(body)
            return self._send_json({"success": True, "config": updated})

        elif path == "/api/validate-key":
            api_key = body.get("api_key") or cfg.get("nexus_api_key")
            client = NexusClient(api_key=api_key)
            try:
                user_data = client.validate_key(api_key)
                return self._send_json({"success": True, "user": user_data})
            except Exception as e:
                return self._send_json({"success": False, "error": str(e)}, status=400)

        elif path == "/api/inspect-url":
            url = body.get("url", "")
            try:
                parsed_mod = NexusClient.parse_mod_url(url, default_domain="cyberpunk2077")
                domain = parsed_mod["domain"]
                mod_id = parsed_mod["mod_id"]

                client = NexusClient(api_key=cfg.get("nexus_api_key"))
                mod_info = client.get_mod_info(domain, mod_id)
                files_info = client.get_mod_files(domain, mod_id)

                files_list = []
                for f in files_info.get("files", []):
                    files_list.append({
                        "file_id": f.get("file_id"),
                        "name": f.get("name"),
                        "file_name": f.get("file_name"),
                        "version": f.get("version"),
                        "category_name": f.get("category_name", "OPTIONAL"),
                        "is_primary": f.get("is_primary", False),
                        "size_kb": f.get("size_kb"),
                        "uploaded_time": f.get("uploaded_time"),
                        "description": f.get("description", "")
                    })

                return self._send_json({
                    "success": True,
                    "parsed": parsed_mod,
                    "mod": {
                        "mod_id": mod_id,
                        "domain": domain,
                        "name": mod_info.get("name"),
                        "summary": mod_info.get("summary"),
                        "description": mod_info.get("description"),
                        "version": mod_info.get("version"),
                        "author": mod_info.get("author"),
                        "picture_url": mod_info.get("picture_url"),
                        "downloads": mod_info.get("mod_downloads"),
                        "endorsements": mod_info.get("endorsement_count")
                    },
                    "files": files_list
                })
            except Exception as e:
                return self._send_json({"success": False, "error": str(e)}, status=400)

        elif path == "/api/download-install":
            url = body.get("url", "")
            custom_file_id = body.get("file_id")
            
            try:
                parsed_mod = NexusClient.parse_mod_url(url, default_domain="cyberpunk2077")
                domain = parsed_mod["domain"]
                mod_id = parsed_mod["mod_id"]
                file_id = custom_file_id or parsed_mod.get("file_id")
                nxm_key = parsed_mod.get("nxm_key")
                nxm_expires = parsed_mod.get("nxm_expires")

                client = NexusClient(
                    api_key=cfg.get("nexus_api_key"),
                    cookie_header=cfg.get_cookie_header()
                )

                if not file_id:
                    files_info = client.get_mod_files(domain, mod_id)
                    main_files = [f for f in files_info.get("files", []) if f.get("category_name") == "MAIN"]
                    if not main_files:
                        main_files = files_info.get("files", [])
                    if not main_files:
                        raise ValueError("No files found for this mod")
                    target_file = main_files[-1]
                    file_id = target_file["file_id"]
                    mod_version = target_file.get("version", "1.0.0")
                    file_name = target_file.get("file_name", f"mod_{mod_id}.zip")
                else:
                    files_info = client.get_mod_files(domain, mod_id)
                    target_file = next((f for f in files_info.get("files", []) if f.get("file_id") == file_id), None)
                    mod_version = target_file.get("version", "1.0.0") if target_file else "1.0.0"
                    file_name = target_file.get("file_name", f"mod_{mod_id}_file_{file_id}.zip") if target_file else f"mod_{mod_id}_file_{file_id}.zip"

                download_url = client.resolve_download_url(
                    domain, mod_id, file_id, nxm_key=nxm_key, nxm_expires=nxm_expires
                )

                watch_dir = cfg.get("watch_dir", r"D:\Game Mentah")
                archive_path = os.path.join(watch_dir, file_name)
                client.download_file(download_url, archive_path)

                installer = ModInstaller(cfg.get("game_path"))
                install_res = installer.install_from_archive(
                    archive_path=archive_path,
                    mod_name=target_file.get("name") if target_file else f"Mod_{mod_id}",
                    mod_id=mod_id,
                    version=mod_version,
                    domain=domain,
                    purge_archive=not cfg.get("keep_archives", False)
                )

                return self._send_json({
                    "success": True,
                    "installed": install_res,
                    "mod_version": mod_version,
                    "file_name": file_name
                })

            except Exception as e:
                return self._send_json({"success": False, "error": str(e)}, status=500)

        elif path == "/api/check-updates":
            try:
                game_path = cfg.get("game_path")
                installer = ModInstaller(game_path)
                installed_mods = installer.list_installed_mods()

                client = NexusClient(api_key=cfg.get("nexus_api_key"))
                updated_batch = client.check_updates_batch("cyberpunk2077", period="1w")
                updated_map = {item["mod_id"]: item for item in updated_batch if isinstance(item, dict) and "mod_id" in item}

                results = []
                for m in installed_mods:
                    mid = m.get("mod_id")
                    if not mid:
                        results.append({
                            "name": m["name"],
                            "mod_id": None,
                            "installed_version": m.get("version"),
                            "update_available": False,
                            "status": "Untracked"
                        })
                        continue

                    if mid in updated_map:
                        files_data = client.get_mod_files("cyberpunk2077", mid)
                        main_files = [f for f in files_data.get("files", []) if f.get("category_name") == "MAIN"] if isinstance(files_data, dict) else []
                        latest_file = main_files[-1] if main_files else None
                        latest_ver = latest_file.get("version") if latest_file else "Newer"
                        installed_ver = m.get("version")

                        has_new = True
                        if installed_ver and installed_ver != "Unknown" and latest_ver != "Newer":
                            if str(installed_ver).strip() == str(latest_ver).strip():
                                has_new = False

                        results.append({
                            "name": m["name"],
                            "mod_id": mid,
                            "installed_version": installed_ver,
                            "latest_version": latest_ver,
                            "latest_file_id": latest_file.get("file_id") if latest_file else None,
                            "update_available": has_new,
                            "status": "Update Available" if has_new else f"Up-to-date (v{installed_ver})"
                        })
                    else:
                        results.append({
                            "name": m["name"],
                            "mod_id": mid,
                            "installed_version": m.get("version"),
                            "latest_version": m.get("version"),
                            "update_available": False,
                            "status": "Up-to-date"
                        })

                return self._send_json({
                    "success": True,
                    "total_checked": len(installed_mods),
                    "updates_found": sum(1 for r in results if r.get("update_available")),
                    "mods": results
                })

            except Exception as e:
                return self._send_json({"success": False, "error": str(e)}, status=500)

        elif path == "/api/undeploy":
            mod_name = body.get("mod_name", "")
            try:
                installer = ModInstaller(cfg.get("game_path"))
                res = installer.undeploy_mod(mod_name)
                return self._send_json({"success": True, "result": res})
            except Exception as e:
                return self._send_json({"success": False, "error": str(e)}, status=400)

        self.send_error(404, "Endpoint Not Found")

def launch_app_window(url):
    """Launch standalone Edge/Chrome App window with custom profile."""
    user_data_dir = os.path.join(os.environ.get("LOCALAPPDATA", "."), "CyberpunkModManager_Profile")
    os.makedirs(user_data_dir, exist_ok=True)

    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]

    for exe in candidates:
        if os.path.exists(exe):
            cmd = [
                exe,
                f"--app={url}",
                f"--user-data-dir={user_data_dir}",
                "--window-size=1260,880",
                "--disable-extensions",
                "--disable-plugins"
            ]
            try:
                subprocess.Popen(cmd)
                return
            except Exception:
                pass

    webbrowser.open(url)

def is_server_already_running(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False

def watchdog_loop():
    """Watchdog thread: automatically terminates server process when window is closed."""
    global last_heartbeat, has_received_heartbeat
    time.sleep(12)  # 12 seconds grace period during initial app startup
    while True:
        time.sleep(2)
        if has_received_heartbeat:
            if time.time() - last_heartbeat > 7:
                # Heartbeat stopped for > 7 seconds -> User closed window
                os._exit(0)

def main():
    url = f"http://127.0.0.1:{PORT}/index.html"

    # If instance already running, just focus/open window and exit secondary process
    if is_server_already_running(PORT):
        launch_app_window(url)
        return

    # Start background watchdog for automated shutdown
    threading.Thread(target=watchdog_loop, daemon=True).start()

    server_address = ("127.0.0.1", PORT)
    httpd = ThreadedHTTPServer(server_address, ModManagerHandler)

    # Launch desktop app window
    threading.Timer(0.3, launch_app_window, args=[url]).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        os._exit(0)

if __name__ == "__main__":
    main()
