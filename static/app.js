/* Cyberpunk Mod Manager - Reactive Frontend Controller */

let activeModData = null;

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initEventListeners();
  loadConfigAndStatus();
  loadInstalledMods();
  loadEnvironment();
  startHeartbeat();
});

// Log helper
function appendLog(message, type = "info") {
  const consoleBox = document.getElementById("console-log");
  if (!consoleBox) return;

  const entry = document.createElement("div");
  entry.className = `log-entry log-${type}`;
  const timestamp = new Date().toLocaleTimeString();
  entry.textContent = `[${timestamp}] ${message}`;
  consoleBox.appendChild(entry);
  consoleBox.scrollTop = consoleBox.scrollHeight;
}

// Tab navigation
function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");

      if (targetId === "tab-installed") {
        loadInstalledMods();
      }
    });
  });
}

// Event Listeners
function initEventListeners() {
  // Inspect URL Button
  const btnInspect = document.getElementById("btn-inspect-url");
  if (btnInspect) {
    btnInspect.addEventListener("click", () => inspectUrl());
  }

  // Input Enter Key
  const inputUrl = document.getElementById("input-mod-url");
  if (inputUrl) {
    inputUrl.addEventListener("keypress", (e) => {
      if (e.key === "Enter") inspectUrl();
    });
  }

  // Paste Button
  const btnPaste = document.getElementById("btn-paste-url");
  if (btnPaste) {
    btnPaste.addEventListener("click", async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text && text.trim()) {
          inputUrl.value = text.trim();
          inspectUrl();
        }
      } catch (err) {
        appendLog("Clipboard read failed. Please paste manually into the input box.", "warning");
      }
    });
  }

  // Download & Install Button
  const btnInstall = document.getElementById("btn-download-install");
  if (btnInstall) {
    btnInstall.addEventListener("click", () => downloadAndInstall());
  }

  // Clear Log
  const btnClearLog = document.getElementById("btn-clear-log");
  if (btnClearLog) {
    btnClearLog.addEventListener("click", () => {
      const consoleBox = document.getElementById("console-log");
      consoleBox.innerHTML = '<div class="log-entry log-info">[Console] Log cleared.</div>';
    });
  }

  // Save Config
  const btnSaveConfig = document.getElementById("btn-save-config");
  if (btnSaveConfig) {
    btnSaveConfig.addEventListener("click", () => saveConfiguration());
  }

  // Validate Key
  const btnValidateKey = document.getElementById("btn-validate-key");
  if (btnValidateKey) {
    btnValidateKey.addEventListener("click", () => validateApiKey());
  }

  // Toggle Key Visibility
  const btnToggleKey = document.getElementById("btn-toggle-key");
  const cfgKey = document.getElementById("cfg-api-key");
  if (btnToggleKey && cfgKey) {
    btnToggleKey.addEventListener("click", () => {
      cfgKey.type = cfgKey.type === "password" ? "text" : "password";
    });
  }

  // Check Updates Button
  const btnCheckUpdates = document.getElementById("btn-check-updates");
  if (btnCheckUpdates) {
    btnCheckUpdates.addEventListener("click", () => checkUpdatesBatch());
  }

  // Refresh Installed
  const btnRefresh = document.getElementById("btn-refresh-installed");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => loadInstalledMods());
  }
}

// Load Configuration and Pre-fills
async function loadConfigAndStatus() {
  try {
    const res = await fetch("/api/config");
    const data = await res.json();
    if (data.success && data.config) {
      const c = data.config;
      document.getElementById("cfg-api-key").value = c.nexus_api_key || "";
      document.getElementById("cfg-cookie-session").value = c.nexusmods_session || "";
      document.getElementById("cfg-cookie-refresh").value = c.nexusmods_session_refresh || "";
      document.getElementById("cfg-game-path").value = c.game_path || "";
      document.getElementById("cfg-watch-dir").value = c.watch_dir || "";
      document.getElementById("cfg-keep-archives").checked = !!c.keep_archives;

      // Status Pill: Cookie
      const badgeCookie = document.getElementById("badge-cookie");
      const textCookie = document.getElementById("text-cookie-status");
      if (c.nexusmods_session) {
        badgeCookie.className = "status-pill status-pill-success";
        textCookie.textContent = "Cookie: Active ✓";
      } else {
        badgeCookie.className = "status-pill status-pill-warning";
        textCookie.textContent = "Cookie: Missing";
      }

      // Check API Key
      if (c.nexus_api_key) {
        validateApiKey(false);
      }
    }
  } catch (e) {
    appendLog(`Error loading configuration: ${e.message}`, "error");
  }
}

// Validate API Key
async function validateApiKey(verbose = true) {
  const key = document.getElementById("cfg-api-key").value.trim();
  const badgeApi = document.getElementById("badge-api");
  const textApi = document.getElementById("text-api-status");

  if (!key) {
    badgeApi.className = "status-pill status-pill-warning";
    textApi.textContent = "API: Missing";
    if (verbose) appendLog("Please provide an API Key first.", "warning");
    return;
  }

  try {
    const res = await fetch("/api/validate-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key })
    });
    const data = await res.json();
    if (data.success && data.user) {
      badgeApi.className = "status-pill status-pill-success";
      textApi.textContent = `API: ${data.user.name} (${data.user.is_premium ? "Premium" : "Free"}) ✓`;
      if (verbose) appendLog(`Nexus API Key Valid! User: ${data.user.name} (Free Tier - Session bypass active).`, "success");
    } else {
      badgeApi.className = "status-pill status-pill-warning";
      textApi.textContent = "API: Invalid";
      if (verbose) appendLog(`API Key validation error: ${data.error}`, "error");
    }
  } catch (e) {
    badgeApi.className = "status-pill status-pill-warning";
    textApi.textContent = "API: Error";
  }
}

// Save Configuration
async function saveConfiguration() {
  const payload = {
    nexus_api_key: document.getElementById("cfg-api-key").value.trim(),
    nexusmods_session: document.getElementById("cfg-cookie-session").value.trim(),
    nexusmods_session_refresh: document.getElementById("cfg-cookie-refresh").value.trim(),
    game_path: document.getElementById("cfg-game-path").value.trim(),
    watch_dir: document.getElementById("cfg-watch-dir").value.trim(),
    keep_archives: document.getElementById("cfg-keep-archives").checked
  };

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      appendLog("Configuration successfully saved to local config.json!", "success");
      loadConfigAndStatus();
    } else {
      appendLog(`Failed to save config: ${data.error}`, "error");
    }
  } catch (e) {
    appendLog(`Config save network error: ${e.message}`, "error");
  }
}

// Load Environment & Frameworks
async function loadEnvironment() {
  try {
    const res = await fetch("/api/inspect-game");
    const data = await res.json();
    const container = document.getElementById("frameworks-container");
    const badgeGame = document.getElementById("badge-game");
    const textGame = document.getElementById("text-game-status");

    if (data.success && data.environment) {
      const env = data.environment;
      if (env.valid) {
        badgeGame.className = "status-pill status-pill-success";
        textGame.textContent = "Game: CP2077 Detected ✓";
      } else {
        badgeGame.className = "status-pill status-pill-warning";
        textGame.textContent = "Game: Path Invalid";
      }

      container.innerHTML = "";
      if (env.frameworks && env.frameworks.length > 0) {
        env.frameworks.forEach(fw => {
          const item = document.createElement("div");
          item.className = "fw-item";
          item.innerHTML = `<span class="fw-check">✓</span> <span><strong>${fw}</strong> active</span>`;
          container.appendChild(item);
        });
      } else {
        container.innerHTML = '<p class="text-zinc-500 text-xs">No frameworks detected yet.</p>';
      }
    }
  } catch (e) {
    console.error("Game inspection error:", e);
  }
}

// Inspect URL
async function inspectUrl() {
  const url = document.getElementById("input-mod-url").value.trim();
  if (!url) {
    appendLog("Please paste a Nexus Mods URL first.", "warning");
    return;
  }

  appendLog(`Inspecting mod URL: ${url}...`, "info");
  const previewCard = document.getElementById("mod-preview-card");
  const btnInspect = document.getElementById("btn-inspect-url");

  btnInspect.disabled = true;
  btnInspect.textContent = "Inspecting...";

  try {
    const res = await fetch("/api/inspect-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    const data = await res.json();

    if (data.success && data.mod) {
      activeModData = data;
      const m = data.mod;

      document.getElementById("mod-name").textContent = m.name || "Unknown Mod";
      document.getElementById("mod-version-badge").textContent = `v${m.version || "1.0.0"}`;
      document.getElementById("mod-author").textContent = `By ${m.author || "Unknown"} • ${Number(m.downloads || 0).toLocaleString()} Downloads`;
      document.getElementById("mod-summary").textContent = m.summary || "";
      
      const thumb = document.getElementById("mod-thumb");
      thumb.src = m.picture_url || "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='120' fill='%23222'></svg>";

      // Populate file picker
      const selectFile = document.getElementById("select-mod-file");
      selectFile.innerHTML = "";

      let selectedMain = false;
      if (data.files && data.files.length > 0) {
        // Reverse so newest is first
        const sortedFiles = [...data.files].reverse();
        sortedFiles.forEach(f => {
          const opt = document.createElement("option");
          opt.value = f.file_id;
          const isMain = f.category_name === "MAIN";
          opt.textContent = `[${f.category_name}] ${f.name} (v${f.version || "?"}) - ${(f.size_kb || 0)} KB`;
          if (isMain && !selectedMain) {
            opt.selected = true;
            selectedMain = true;
          }
          selectFile.appendChild(opt);
        });
      }

      previewCard.classList.remove("hidden");
      appendLog(`Mod metadata loaded: "${m.name}" (v${m.version}) with ${data.files.length} downloadable files.`, "success");
    } else {
      appendLog(`Failed to inspect URL: ${data.error}`, "error");
    }
  } catch (e) {
    appendLog(`Network error inspecting URL: ${e.message}`, "error");
  } finally {
    btnInspect.disabled = false;
    btnInspect.textContent = "🔍 Inspect Mod";
  }
}

// Download & Install
async function downloadAndInstall(targetFileId = null) {
  const url = document.getElementById("input-mod-url").value.trim();
  const selectFile = document.getElementById("select-mod-file");
  const fileId = targetFileId || (selectFile ? parseInt(selectFile.value) : null);
  const btnInstall = document.getElementById("btn-download-install");

  if (!url) {
    appendLog("No URL specified.", "warning");
    return;
  }

  btnInstall.disabled = true;
  btnInstall.textContent = "⏳ Downloading & Installing...";

  appendLog("[1/4] Connecting to Nexus Mods internal endpoint to resolve direct CDN URL...", "info");

  try {
    const res = await fetch("/api/download-install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, file_id: fileId })
    });
    const data = await res.json();

    if (data.success && data.installed) {
      const inst = data.installed;
      appendLog("[2/4] File downloaded from CDN directly into watch folder.", "info");
      appendLog(`[3/4] Isolated staging verified. 0 core binaries overwritten. Deployed ${inst.files_deployed} files transactionally.`, "info");
      appendLog(`[4/4] Invariant 6: Raw archive automatically deleted. Manifest registered at: ${inst.manifest}`, "success");
      appendLog(`SUCCESS: "${inst.mod_name}" v${data.mod_version} is now installed and active in Cyberpunk 2077!`, "success");

      loadInstalledMods();
    } else {
      appendLog(`Installation failed: ${data.error}`, "error");
    }
  } catch (e) {
    appendLog(`Download/Install network failure: ${e.message}`, "error");
  } finally {
    btnInstall.disabled = false;
    btnInstall.textContent = "⬇️ Download & Install Mod Directly";
  }
}

// Load Installed Mods
async function loadInstalledMods() {
  const tbody = document.getElementById("installed-mods-tbody");
  const badgeCount = document.getElementById("installed-count");

  try {
    const res = await fetch("/api/installed-mods");
    const data = await res.json();

    if (data.success && data.mods) {
      badgeCount.textContent = data.mods.length;
      tbody.innerHTML = "";

      if (data.mods.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-zinc-500">No mods installed via Gemi yet.</td></tr>';
        return;
      }

      data.mods.forEach(m => {
        const tr = document.createElement("tr");
        tr.id = `mod-row-${m.name}`;
        tr.innerHTML = `
          <td><strong>${m.name}</strong></td>
          <td><span class="badge-pill">${m.mod_id || "Manual"}</span></td>
          <td><span class="badge-pill">${m.version || "Unknown"}</span></td>
          <td id="latest-ver-${m.name}"><span class="text-zinc-500">-</span></td>
          <td id="status-${m.name}"><span class="badge-pill badge-success">Active</span></td>
          <td class="text-right">
            <button class="btn btn-danger btn-sm" onclick="undeployMod('${m.name}')">Uninstall</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-rose-500">Error loading mods: ${e.message}</td></tr>`;
  }
}

// Batch Check Updates
async function checkUpdatesBatch() {
  const btnCheck = document.getElementById("btn-check-updates");
  btnCheck.disabled = true;
  btnCheck.textContent = "Checking...";
  appendLog("Checking Nexus Mods updates for all installed mods (single batch request)...", "info");

  try {
    const res = await fetch("/api/check-updates", { method: "POST" });
    const data = await res.json();

    if (data.success && data.mods) {
      appendLog(`Update check complete! Inspected ${data.total_checked} mods. Updates found: ${data.updates_found}.`, "success");

      data.mods.forEach(m => {
        const latestCell = document.getElementById(`latest-ver-${m.name}`);
        const statusCell = document.getElementById(`status-${m.name}`);

        if (latestCell && m.latest_version) {
          latestCell.innerHTML = `<span class="badge-pill">${m.latest_version}</span>`;
        }

        if (statusCell) {
          if (m.update_available) {
            statusCell.innerHTML = `<span class="badge-pill badge-warning">Update Available!</span>`;
            // Add update button
            const row = document.getElementById(`mod-row-${m.name}`);
            if (row && m.mod_id) {
              const actionCell = row.querySelector(".text-right");
              if (actionCell && !actionCell.querySelector(".btn-update-now")) {
                const btnUpdate = document.createElement("button");
                btnUpdate.className = "btn btn-primary btn-sm btn-update-now mr-2";
                btnUpdate.style.marginRight = "6px";
                btnUpdate.textContent = "⚡ Update";
                btnUpdate.onclick = () => {
                  document.getElementById("input-mod-url").value = `https://www.nexusmods.com/cyberpunk2077/mods/${m.mod_id}`;
                  document.querySelector('.nav-tab[data-tab="tab-install"]').click();
                  inspectUrl();
                };
                actionCell.prepend(btnUpdate);
              }
            }
          } else {
            statusCell.innerHTML = `<span class="badge-pill badge-success">${m.status || "Up-to-date"}</span>`;
          }
        }
      });
    } else {
      appendLog(`Update check error: ${data.error}`, "error");
    }
  } catch (e) {
    appendLog(`Update check network failure: ${e.message}`, "error");
  } finally {
    btnCheck.disabled = false;
    btnCheck.textContent = "🔄 Check All Updates";
  }
}

// Undeploy Mod
async function undeployMod(modName) {
  if (!confirm(`Are you sure you want to uninstall and remove "${modName}"?`)) return;

  appendLog(`Uninstalling mod "${modName}" safely (verifying SHA-256 manifest)...`, "info");
  try {
    const res = await fetch("/api/undeploy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mod_name: modName })
    });
    const data = await res.json();
    if (data.success && data.result) {
      appendLog(`Mod "${modName}" successfully uninstalled! Removed ${data.result.removed_count} files.`, "success");
      loadInstalledMods();
    } else {
      appendLog(`Failed to uninstall: ${data.error}`, "error");
    }
  } catch (e) {
    appendLog(`Uninstall error: ${e.message}`, "error");
  }
}

// Expose undeploy to window
window.undeployMod = undeployMod;

// Automated Heartbeat & Window-Close Lifecycle Sync
function startHeartbeat() {
  // Immediate initial heartbeat
  fetch("/api/heartbeat").catch(() => {});
  
  // Heartbeat every 2.5 seconds
  setInterval(() => {
    fetch("/api/heartbeat").catch(() => {});
  }, 2500);

  // Send beacon on window close to terminate server immediately
  window.addEventListener("beforeunload", () => {
    try {
      navigator.sendBeacon("/api/shutdown");
    } catch (_) {
      fetch("/api/shutdown", { method: "POST", keepalive: true }).catch(() => {});
    }
  });

  window.addEventListener("pagehide", () => {
    try {
      navigator.sendBeacon("/api/shutdown");
    } catch (_) {
      fetch("/api/shutdown", { method: "POST", keepalive: true }).catch(() => {});
    }
  });
}
