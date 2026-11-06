import os
import sys
import time
import socket
import threading
import subprocess
import webbrowser

# Protected streams
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

from server import run_server

PORT = 5560

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

def launch_app_window(url):
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
                "--window-size=1140,840",
                "--disable-extensions"
            ]
            try:
                subprocess.Popen(cmd)
                return
            except Exception:
                pass

    # Fallback to standard default browser
    webbrowser.open(url)

def main():
    app_url = f"http://127.0.0.1:{PORT}/index.html"

    # Start server if not already running
    if not is_port_in_use(PORT):
        t = threading.Thread(target=run_server, args=(PORT,), daemon=True)
        t.start()
        time.sleep(0.6)

    # Launch UI window
    launch_app_window(app_url)

    # Keep alive while server runs
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
