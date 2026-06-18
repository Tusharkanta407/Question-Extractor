const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");
const toolbar = document.getElementById("toolbar");
const useLlm = document.getElementById("useLlm");
const extractBtn = document.getElementById("extractBtn");
const statusEl = document.getElementById("status");
const statsEl = document.getElementById("stats");
const resultEl = document.getElementById("result");
const resultTitle = document.getElementById("resultTitle");
const resultMeta = document.getElementById("resultMeta");
const outputEl = document.getElementById("output");
const copyBtn = document.getElementById("copyBtn");
const downloadDocxBtn = document.getElementById("downloadDocxBtn");
const downloadMmdBtn = document.getElementById("downloadMmdBtn");
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
  statsEl.hidden = false;
  resultEl.hidden = false;
  resultTitle.textContent = data.title || "Question Bank";
  resultMeta.textContent = [
    `Foundation ${data.subject}`,
    `Class ${data.class_level}`,
    `${data.question_count} questions`,
    `${data.paired_answers} book`,
    data.use_llm ? `${data.llm_filled} LLM` : "LLM off",
  ].join(" | ");
  document.getElementById("statQuestions").textContent = data.question_count;
  document.getElementById("statBook").textContent = data.paired_answers;
  document.getElementById("statLlm").textContent = data.llm_filled ?? 0;
  document.getElementById("statSkipped").textContent = data.llm_skipped_subjective ?? 0;
  document.getElementById("statMissing").textContent = data.objective_missing ?? 0;
  const lt = data.llm_tokens || {};
  document.getElementById("statLlmTokens").textContent = lt.total
    ? `${lt.input} / ${lt.output} (${lt.batch_calls} calls, ${lt.queued || "?"} queued)`
    : "—";
  outputEl.textContent = data.content;
}

async function downloadFromServer(format) {
  if (!lastFile) return;
  const form = new FormData();
  form.append("file", lastFile);
  form.append("output_format", format);
  form.append("use_llm", useLlm.checked ? "true" : "false");
  setStatus(`Preparing .${format}...`, "loading");
  try {
    const res = await fetch("/api/foundation/download", { method: "POST", body: form });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Download failed.");
    }
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : `question_bank.${format}`;
    triggerDownload(blob, filename);
    setStatus(`Downloaded ${filename}`, "success");
  } catch (err) {
    setStatus(err.message || "Download failed.", "error");
  }
}

async function processFile(file) {
  if (!file?.name.toLowerCase().endsWith(".mmd")) {
    setStatus("Please upload a .mmd file.", "error");
    return;
  }
  lastFile = file;
  const llmOn = useLlm.checked;
  setStatus(
    llmOn
      ? "Extracting… then LLM batch fill (objective only)…"
      : "Extracting book answers (no API)…",
    "loading"
  );
  resultEl.hidden = true;
  statsEl.hidden = true;

  const form = new FormData();
  form.append("file", file);
  form.append("use_llm", llmOn ? "true" : "false");

  try {
    const res = await fetch("/api/foundation/extract", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Extraction failed.");
    showResult(data);
    setStatus(
      llmOn
        ? `Done — ${data.paired_answers} book, ${data.llm_filled} LLM, ${data.llm_skipped_subjective} subjective skipped.`
        : `Done — ${data.paired_answers} book answers.`,
      "success"
    );
  } catch (err) {
    setStatus(err.message || "Something went wrong.", "error");
  }
}

function onFileSelected(file) {
  if (!file) return;
  lastFile = file;
  toolbar.hidden = false;
  resultEl.hidden = true;
  statsEl.hidden = true;
  setStatus(`Loaded ${file.name}. Click Extract.`, "success");
}

copyBtn.addEventListener("click", async () => {
  if (!lastResult) return;
  await navigator.clipboard.writeText(lastResult.content);
  setStatus("Copied.", "success");
});

downloadDocxBtn.addEventListener("click", () => downloadFromServer("docx"));
downloadMmdBtn.addEventListener("click", () => {
  if (!lastResult) return;
  triggerDownload(
    new Blob([lastResult.content], { type: "text/plain;charset=utf-8" }),
    lastResult.filename_mmd || "question_bank.mmd"
  );
});
downloadJsonBtn.addEventListener("click", () => {
  if (!lastResult?.json) return;
  triggerDownload(
    new Blob([lastResult.json], { type: "application/json;charset=utf-8" }),
    lastResult.filename_json || "question_bank.json"
  );
});

browseBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => { onFileSelected(fileInput.files[0]); fileInput.value = ""; });
extractBtn.addEventListener("click", () => processFile(lastFile));
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  onFileSelected(e.dataTransfer.files[0]);
});
