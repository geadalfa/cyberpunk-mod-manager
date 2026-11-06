import os
import json
import re
import urllib.request
import urllib.parse
import shutil

class NexusClient:
    def __init__(self, api_key=None, cookie_header=None):
        self.api_key = api_key
        self.cookie_header = cookie_header
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    @staticmethod
    def parse_mod_url(url_or_id, default_domain="cyberpunk2077"):
        """
        Parse user input into domain, mod_id, and optional file_id.
        Handles:
        - https://www.nexusmods.com/cyberpunk2077/mods/16565
        - https://www.nexusmods.com/cyberpunk2077/mods/16565?tab=files&file_id=168622
        - nxm://cyberpunk2077/mods/16565/files/168622?key=...&expires=...
        - Raw integer "16565"
        """
        text = str(url_or_id).strip()
        
        # Check raw integer
        if text.isdigit():
            return {
                "domain": default_domain,
                "mod_id": int(text),
                "file_id": None,
                "nxm_key": None,
                "nxm_expires": None
            }

        # Check NXM format
        m_nxm = re.match(r"^nxm://([^/?#]+)/mods/(\d+)/files/(\d+)(?:\?(.+))?$", text, re.IGNORECASE)
        if m_nxm:
            domain = m_nxm.group(1)
            mod_id = int(m_nxm.group(2))
            file_id = int(m_nxm.group(3))
            query = m_nxm.group(4) or ""
            params = urllib.parse.parse_qs(query)
            return {
                "domain": domain,
                "mod_id": mod_id,
                "file_id": file_id,
                "nxm_key": params.get("key", [None])[0],
                "nxm_expires": params.get("expires", [None])[0]
            }

        # Check Web URL format
        m_web = re.search(r"nexusmods\.com/([a-zA-Z0-9_-]+)/mods/(\d+)", text, re.IGNORECASE)
        if m_web:
            domain = m_web.group(1)
            mod_id = int(m_web.group(2))
            
            # Check for file_id in query params
            file_id = None
            if "file_id=" in text:
                m_fid = re.search(r"[?&]file_id=(\d+)", text)
                if m_fid:
                    file_id = int(m_fid.group(1))

            return {
                "domain": domain,
                "mod_id": mod_id,
                "file_id": file_id,
                "nxm_key": None,
                "nxm_expires": None
            }

        raise ValueError(f"Could not parse valid Nexus Mods URL or ID from '{text}'")

    def query_api(self, endpoint, api_key=None):
        key = api_key or self.api_key
        if not key:
            raise ValueError("Nexus API Key is required")

        url = f"https://api.nexusmods.com{endpoint}" if endpoint.startswith("/") else f"https://api.nexusmods.com/{endpoint}"
        req = urllib.request.Request(url, headers={
            "apikey": key.strip(),
            "Application-Name": "CyberpunkModManager-Gemi",
            "Application-Version": "2.0.0",
            "User-Agent": self.user_agent
        })
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="ignore")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("message") or err_json.get("error") or err_body
            except Exception:
                msg = err_body
            raise RuntimeError(f"Nexus API HTTP {e.code}: {msg}")
        except Exception as e:
            raise RuntimeError(f"Network error querying Nexus API: {e}")

    def validate_key(self, api_key):
        return self.query_api("/v1/users/validate.json", api_key=api_key)

    def get_mod_info(self, domain, mod_id):
        return self.query_api(f"/v1/games/{domain}/mods/{mod_id}.json")

    def get_mod_files(self, domain, mod_id):
        return self.query_api(f"/v1/games/{domain}/mods/{mod_id}/files.json")

    def get_numeric_game_id(self, domain):
        if domain.lower() in ["cyberpunk2077", "cyberpunk 2077"]:
            return 3333
        if domain.lower() in ["mountandblade2bannerlord"]:
            return 3174
        if domain.lower() in ["skyrimspecialedition"]:
            return 1704
        try:
            data = self.query_api(f"/v1/games/{domain}.json")
            if isinstance(data, dict) and "id" in data:
                return data["id"]
        except Exception:
            pass
        return 3333

    def resolve_download_url(self, domain, mod_id, file_id, nxm_key=None, nxm_expires=None):
        """
        Determines direct CDN download URL.
        1. Uses signed NXM params if provided.
        2. Tries internal GenerateDownloadUrl with session cookie (Free account bypass).
        3. Falls back to official download_link.json (for Premium).
        """
        # 1. Signed NXM Link
        if nxm_key and nxm_expires:
            endpoint = f"/v1/games/{domain}/mods/{mod_id}/files/{file_id}/download_link.json?key={nxm_key}&expires={nxm_expires}"
            try:
                res = self.query_api(endpoint)
                if isinstance(res, list) and res and "URI" in res[0]:
                    return res[0]["URI"]
            except Exception:
                pass

        # 2. Free Account Bypass via GenerateDownloadUrl
        if self.cookie_header:
            numeric_id = self.get_numeric_game_id(domain)
            gen_url = "https://www.nexusmods.com/Core/Libs/Common/Managers/Downloads?GenerateDownloadUrl"
            post_data = urllib.parse.urlencode({
                "fid": file_id,
                "game_id": numeric_id
            }).encode("utf-8")
            
            req = urllib.request.Request(gen_url, data=post_data, headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": self.user_agent,
                "Cookie": self.cookie_header,
                "Referer": f"https://www.nexusmods.com/{domain}/mods/{mod_id}?tab=files"
            })
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode())
                    if isinstance(data, dict) and data.get("url"):
                        return data["url"]
                    elif isinstance(data, list) and data and "url" in data[0]:
                        return data[0]["url"]
            except Exception as e:
                pass

        # 3. Official API (Premium accounts)
        try:
            res = self.query_api(f"/v1/games/{domain}/mods/{mod_id}/files/{file_id}/download_link.json")
            if isinstance(res, list) and res and "URI" in res[0]:
                return res[0]["URI"]
        except Exception:
            pass

        raise RuntimeError(
            "Could not obtain download URL. Ensure your session cookie (nexusmods_session) is filled, "
            "or use a signed nxm:// link from the 'Mod Manager Download' button."
        )

    def download_file(self, download_url, target_path, progress_callback=None):
        """Streams file download to target_path with byte progress."""
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        req = urllib.request.Request(download_url, headers={"User-Agent": self.user_agent})
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 32768
            
            with open(target_path, "wb") as f_out:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

        return target_path

    def check_updates_batch(self, domain="cyberpunk2077", period="1w"):
        return self.query_api(f"/v1/games/{domain}/mods/updated.json?period={period}")
