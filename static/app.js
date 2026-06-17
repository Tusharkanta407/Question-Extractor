const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const resultTitle = document.getElementById("resultTitle");
const resultMeta = document.getElementById("resultMeta");
const outputEl = document.getElementById("output");
const copyBtn = document.getElementById("copyBtn");
const downloadTxtBtn = document.getElementById("downloadTxtBtn");
const downloadDocxBtn = document.getElementById("downloadDocxBtn");
const downloadJsonBtn = document.getElementById("downloadJsonBtn");

let lastResult = null;
let lastFile = null;

function setStatus(message, type) {
  statusEl.hidden = !message;
  statusEl.textContent = message;
  statusEl.className = `status ${type || ""}`.trim();
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function showResult(data) {
  lastResult = data;
  resultEl.hidden = false;
  resultTitle.textContent = data.filename_json || data.filename_txt || "Output";
  resultMeta.textContent = [
    data.title ? `Title: ${data.title}` : null,
    data.format ? `Format: ${data.format}` : null,
    data.question_count != null ? `${data.question_count} questions` : null,
    `${data.stats.input_lines} lines in -> ${data.stats.output_lines} lines out`,
  ]
    .filter(Boolean)
    .join(" | ");
  outputEl.textContent = data.content;
}

async function processFile(file) {
  if (!file) return;

  if (!file.name.toLowerCase().endsWith(".mmd")) {
    setStatus("Please upload a .mmd file.", "error");
    return;
  }

  lastFile = file;
  setStatus("Extracting questions and answers...", "loading");
  resultEl.hidden = true;

  const form = new FormData();
  form.append("file", file);

  try {
    const res = await fetch("/api/extract", { method: "POST", body: form });
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      throw new Error(data.detail || "Extraction failed.");
    }

    showResult(data);
    setStatus("Done. Preview below or download as .txt / .docx / .json.", "success");
  } catch (err) {
    setStatus(err.message || "Something went wrong.", "error");
  }
}

function downloadJsonLocal() {
  if (!lastResult?.json) {
    setStatus("Upload a file first.", "error");
    return;
  }
  const blob = new Blob([lastResult.json], { type: "application/json;charset=utf-8" });
  triggerDownload(blob, lastResult.filename_json || "output_qa.json");
  setStatus(`Downloaded ${lastResult.filename_json || "output_qa.json"}`, "success");
}

function downloadTxtLocal() {
  if (!lastResult?.content) {
    setStatus("Upload a file first.", "error");
    return;
  }
  const blob = new Blob([lastResult.content], { type: "text/plain;charset=utf-8" });
  triggerDownload(blob, lastResult.filename_txt || "output_qa.txt");
  setStatus(`Downloaded ${lastResult.filename_txt || "output_qa.txt"}`, "success");
}

async function downloadFromServer(format) {
  if (!lastFile) {
    setStatus("Upload a file first.", "error");
    return;
  }

  const form = new FormData();
  form.append("file", lastFile);
  form.append("output_format", format);

  setStatus(`Preparing ${format.toUpperCase()} file...`, "loading");

  try {
    const res = await fetch("/api/extract/download", { method: "POST", body: form });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Download failed.");
    }

    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : `output_qa.${format}`;

    triggerDownload(blob, filename);
    setStatus(`Downloaded ${filename}`, "success");
  } catch (err) {
    setStatus(err.message || "Download failed.", "error");
  }
}

browseBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  processFile(file);
  fileInput.value = "";
});

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("dragover");
});

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  processFile(file);
});

copyBtn.addEventListener("click", async () => {
  if (!lastResult) return;
  await navigator.clipboard.writeText(lastResult.content);
  setStatus("Copied to clipboard.", "success");
});

downloadTxtBtn.addEventListener("click", downloadTxtLocal);
downloadDocxBtn.addEventListener("click", () => downloadFromServer("docx"));
if (downloadJsonBtn) {
  downloadJsonBtn.addEventListener("click", downloadJsonLocal);
}
