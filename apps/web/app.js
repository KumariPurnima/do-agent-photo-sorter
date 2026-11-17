const fileInput = document.getElementById("fileInput");
const startSort = document.getElementById("startSort");
const selectionHint = document.getElementById("selectionHint");
const statusPanel = document.getElementById("statusPanel");
const foldersPanel = document.getElementById("foldersPanel");
const jobStatus = document.getElementById("jobStatus");
const jobMeta = document.getElementById("jobMeta");
const jobLog = document.getElementById("jobLog");
const folderGrid = document.getElementById("folderGrid");
const folderCount = document.getElementById("folderCount");

let selectedFiles = [];
let albumId = null;

fileInput.addEventListener("change", () => {
  selectedFiles = [...fileInput.files];
  startSort.disabled = selectedFiles.length === 0;
  selectionHint.textContent =
    selectedFiles.length === 0
      ? "No files selected yet."
      : `${selectedFiles.length} file${selectedFiles.length === 1 ? "" : "s"} ready.`;
});

startSort.addEventListener("click", async () => {
  startSort.disabled = true;
  statusPanel.hidden = false;
  setStatus("uploading", "Preparing album…");

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

async function pollJob(jobId) {
  let last = null;
  for (let i = 0; i < 40; i += 1) {
    last = await api(`/api/jobs/${jobId}/refresh`, { method: "POST", body: "{}" });
    setStatus(last.status, last.message);
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
    folderGrid.innerHTML = `<div class="folder-card"><h3>Waiting for sync</h3><p>When the agent finishes and syncs to Spaces, folders appear here. Locally, run <code>scripts/run_pipeline.py</code> against an inbox.</p></div>`;
    return;
  }
  folderGrid.innerHTML = entries
    .map(
      ([name, items]) =>
        `<article class="folder-card"><h3>${escapeHtml(name)}</h3><p>${items.length} file${items.length === 1 ? "" : "s"}</p></article>`
    )
    .join("");
}

function setStatus(status, message) {
  jobStatus.textContent = status;
  jobStatus.classList.toggle("warn", status === "error" || status === "queued");
  if (message) appendLog(message);
}

function appendLog(text) {
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

// Boot health
api("/api/health")
  .then((h) => {
    appendLog(
      h.demo_mode
        ? "API online · demo mode (set DIGITALOCEAN_TOKEN + DEMO_MODE=false for live Harness)."
        : "API online · live Harness mode."
    );
  })
  .catch(() => appendLog("API health check failed"));
