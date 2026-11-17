const fileInput = document.getElementById("fileInput");
const startSort = document.getElementById("startSort");
const replayDemo = document.getElementById("replayDemo");
const selectionHint = document.getElementById("selectionHint");
const statusPanel = document.getElementById("statusPanel");
const foldersPanel = document.getElementById("foldersPanel");
const jobStatus = document.getElementById("jobStatus");
const jobMeta = document.getElementById("jobMeta");
const jobLog = document.getElementById("jobLog");
const folderGrid = document.getElementById("folderGrid");
const folderCount = document.getElementById("folderCount");
const categoryChips = document.getElementById("categoryChips");
const thumbStrip = document.getElementById("thumbStrip");
const heroGif = document.getElementById("heroGif");
const sortGif = document.getElementById("sortGif");
const themeToggle = document.getElementById("themeToggle");

const PREVIEW_SRC = "/static/assets/preview.gif";

let selectedFiles = [];
let albumId = null;
let objectUrls = [];

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  if (next === "dark") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", "light");
  themeToggle.textContent = next === "light" ? "☀" : "☾";
});

replayDemo.addEventListener("click", () => {
  restartGif(heroGif);
  statusPanel.hidden = false;
  restartGif(sortGif);
  statusPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  appendLog("Replaying sort animation (placeholder demo images).");
});

fileInput.addEventListener("change", () => {
  clearObjectUrls();
  selectedFiles = [...fileInput.files];
  startSort.disabled = selectedFiles.length === 0;
  selectionHint.textContent =
    selectedFiles.length === 0
      ? "No files selected yet."
      : `${selectedFiles.length} file${selectedFiles.length === 1 ? "" : "s"} ready.`;
  renderThumbs(selectedFiles.slice(0, 24));
});

startSort.addEventListener("click", async () => {
  startSort.disabled = true;
  statusPanel.hidden = false;
  foldersPanel.hidden = true;
  restartGif(sortGif);
  setStatus("uploading", "Preparing album…");
  statusPanel.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const albumRes = await api("/api/albums", {
      method: "POST",
      body: JSON.stringify({ name: `Album ${new Date().toLocaleString()}` }),
    });
    albumId = albumRes.album_id;
    appendLog(`Album ${albumId} created`);

    let uploaded = 0;
    let demoUploads = false;
    for (const file of selectedFiles) {
      const presign = await api("/api/uploads/presign", {
        method: "POST",
        body: JSON.stringify({
          album_id: albumId,
          filename: file.name,
          content_type: file.type || undefined,
        }),
      });
      if (presign.demo || !presign.upload_url) {
        demoUploads = true;
      } else {
        const put = await fetch(presign.upload_url, {
          method: "PUT",
          headers: { "Content-Type": presign.content_type },
          body: file,
        });
        if (!put.ok) throw new Error(`Upload failed for ${file.name}`);
      }
      uploaded += 1;
      setStatus("uploading", `Uploaded ${uploaded}/${selectedFiles.length}`);
    }

    appendLog(
      demoUploads
        ? "Demo mode: files stayed in the browser; launching simulated Harness session."
        : "Uploads complete. Launching Harness Runtime session…"
    );

    const job = await api("/api/sort", {
      method: "POST",
      body: JSON.stringify({ album_id: albumId }),
    });
    setStatus(job.status, job.message);
    jobMeta.textContent = `job=${job.id} session=${job.session_name}`;
    appendLog(job.message);

    await pollJob(job.id);
    await loadFolders(albumId);
  } catch (err) {
    console.error(err);
    setStatus("error", err.message || String(err));
    appendLog(String(err));
  } finally {
    startSort.disabled = selectedFiles.length === 0;
  }
});

function renderThumbs(files) {
  if (!files.length) {
    thumbStrip.hidden = true;
    thumbStrip.innerHTML = "";
    return;
  }
  thumbStrip.hidden = false;
  thumbStrip.innerHTML = "";
  files.forEach((file, i) => {
    if (!file.type.startsWith("image/")) return;
    const url = URL.createObjectURL(file);
    objectUrls.push(url);
    const img = document.createElement("img");
    img.src = url;
    img.alt = file.name;
    img.style.animationDelay = `${i * 40}ms`;
    thumbStrip.appendChild(img);
  });
}

function clearObjectUrls() {
  objectUrls.forEach((u) => URL.revokeObjectURL(u));
  objectUrls = [];
}

function restartGif(img) {
  if (!img) return;
  img.src = `${PREVIEW_SRC}?t=${Date.now()}`;
}

async function pollJob(jobId) {
  let last = null;
  for (let i = 0; i < 40; i += 1) {
    last = await api(`/api/jobs/${jobId}/refresh`, { method: "POST", body: "{}" });
    setStatus(last.status, last.message || "");
    if (last.session_id) {
      jobMeta.textContent = `job=${last.id} session=${last.session_name} id=${last.session_id}`;
    }
    const done = ["complete", "completed", "succeeded", "success", "failed", "error", "stopped"].includes(
      String(last.status).toLowerCase()
    );
    if (done) break;
    if (last.status === "running" || last.status === "queued" || last.status === "pending") {
      await sleep(1500);
      continue;
    }
    await sleep(1200);
  }
  if (last && ["failed", "error"].includes(String(last.status).toLowerCase())) {
    appendLog("Harness session reported an error — check doctl harness-runtime show <session>.");
    return;
  }
  setStatus(last?.status || "complete", "Browse folders below when Spaces sync finishes.");
  appendLog("Attach interactively with: doctl harness-runtime launch <session-name>");
}

async function loadFolders(id) {
  foldersPanel.hidden = false;
  const data = await api(`/api/albums/${id}/sorted`);
  const entries = Object.entries(data.folders || {});
  folderCount.textContent = `${data.count} objects`;
  if (entries.length === 0) {
    // In demo mode, synthesize folders from selected file names for a richer UI.
    if (selectedFiles.length) {
      const demo = demoFoldersFromFiles(selectedFiles);
      folderCount.textContent = `${selectedFiles.length} demo placements`;
      folderGrid.innerHTML = Object.entries(demo)
        .map(([name, items]) => folderCard(name, items))
        .join("");
      appendLog("Demo folders rendered from selected filenames (no Spaces sync).");
      return;
    }
    folderGrid.innerHTML = `<div class="folder-card"><h3>Waiting for sync</h3><p>When the agent finishes and syncs to Spaces, folders appear here.</p></div>`;
    return;
  }
  folderGrid.innerHTML = entries
    .map(([name, items]) => {
      const thumbs = items
        .filter((i) => i.url)
        .slice(0, 4)
        .map((i) => `<img src="${escapeHtml(i.url)}" alt="" />`)
        .join("");
      return `<article class="folder-card"><h3>${escapeHtml(name)}</h3><p>${items.length} file${items.length === 1 ? "" : "s"}</p>${thumbs ? `<div class="folder-thumbs">${thumbs}</div>` : ""}</article>`;
    })
    .join("");
}

function folderCard(name, items) {
  const thumbs = items
    .slice(0, 4)
    .map((src) => `<img src="${src}" alt="" />`)
    .join("");
  return `<article class="folder-card"><h3>${escapeHtml(name)}</h3><p>${items.length} file${items.length === 1 ? "" : "s"}</p><div class="folder-thumbs">${thumbs}</div></article>`;
}

function demoFoldersFromFiles(files) {
  const buckets = {
    Selfies: [],
    "Food & drinks": [],
    "Travel & nature": [],
    Screenshots: [],
    "People & family": [],
    Other: [],
  };
  for (const file of files) {
    const n = file.name.toLowerCase();
    let folder = "Other";
    if (n.includes("selfie")) folder = "Selfies";
    else if (n.includes("food") || n.includes("dinner") || n.includes("coffee")) folder = "Food & drinks";
    else if (n.includes("screen")) folder = "Screenshots";
    else if (n.includes("beach") || n.includes("travel") || n.includes("sunset") || n.includes("mountain"))
      folder = "Travel & nature";
    else if (n.includes("family") || n.includes("people") || n.includes("group")) folder = "People & family";
    const url = file.type.startsWith("image/") ? URL.createObjectURL(file) : "";
    if (url) objectUrls.push(url);
    if (url) buckets[folder].push(url);
    else buckets[folder].push("");
  }
  return Object.fromEntries(Object.entries(buckets).filter(([, v]) => v.length));
}

function setStatus(status, message) {
  jobStatus.textContent = status;
  jobStatus.classList.toggle("warn", status === "error" || status === "queued" || status === "uploading");
  if (message) appendLog(message);
}

function appendLog(text) {
  if (!text) return;
  const stamp = new Date().toLocaleTimeString();
  jobLog.textContent += `[${stamp}] ${text}\n`;
  jobLog.scrollTop = jobLog.scrollHeight;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function loadCategories() {
  try {
    const data = await api("/api/categories");
    const folders = data.folders || [];
    categoryChips.innerHTML = folders
      .map((f) => `<span class="chip" title="${escapeHtml(f.description || "")}">${escapeHtml(f.name)}</span>`)
      .join("");
  } catch {
    categoryChips.innerHTML = `<span class="chip">Selfies</span><span class="chip">Food & drinks</span><span class="chip">Travel & nature</span>`;
  }
}

api("/api/health")
  .then((h) => {
    appendLog(
      h.demo_mode
        ? "API online · demo mode (set DIGITALOCEAN_TOKEN + DEMO_MODE=false for live Harness)."
        : "API online · live Harness mode."
    );
  })
  .catch(() => appendLog("API health check failed"));

loadCategories();
