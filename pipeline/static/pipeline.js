const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");

const bankDropzone = document.getElementById("bankDropzone");
const bankFileInput = document.getElementById("bankFileInput");
const bankBrowseBtn = document.getElementById("bankBrowseBtn");
const bankFileName = document.getElementById("bankFileName");
const bankClearBtn = document.getElementById("bankClearBtn");

const toolbar = document.getElementById("toolbar");
const thresholdInput = document.getElementById("threshold");
const skipEmbeddings = document.getElementById("skipEmbeddings");
const ruleBasedTagging = document.getElementById("ruleBasedTagging");
const runBtn = document.getElementById("runBtn");

const statusEl = document.getElementById("status");
const statsEl = document.getElementById("stats");
const resultEl = document.getElementById("result");
const resultMeta = document.getElementById("resultMeta");
const cardsView = document.getElementById("cardsView");
const outputEl = document.getElementById("output");
const viewToggleBtn = document.getElementById("viewToggleBtn");
const copyBtn = document.getElementById("copyBtn");
const downloadJsonBtn = document.getElementById("downloadJsonBtn");

const droppedSection = document.getElementById("droppedSection");
const droppedMeta = document.getElementById("droppedMeta");
const droppedList = document.getElementById("droppedList");

let lastFile = null;
let lastBankFile = null;
let lastResult = null;
let showingRaw = false;

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

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function difficultyClass(level) {
  const l = (level || "").toLowerCase();
  if (l === "easy") return "chip-difficulty-easy";
  if (l === "hard") return "chip-difficulty-hard";
  return "chip-difficulty-medium";
}

function renderQuestionCard(q) {
  const tags = q.tags || {};
  const content = q.question_content_mathml || q.question_content || "";

  const optionsHtml = (q.options || []).length
    ? `<ul class="options-list">${q.options
        .map((o) => {
          const correct = (q.answer_key || "").toUpperCase() === (o.label || "").toUpperCase();
          return `<li class="${correct ? "correct" : ""}"><strong>${escapeHtml(o.label)})</strong> ${o.text_mathml || escapeHtml(o.text)}</li>`;
        })
        .join("")}</ul>`
    : "";

  const examChips = (tags.exam_tags || [])
    .map((t) => `<span class="chip chip-exam">${escapeHtml(t)}</span>`)
    .join("");

  return `
    <div class="question-card">
      <div class="question-card-head">
        <span class="qid">${escapeHtml(q.qid)}</span>
        <span class="qtype-badge">${escapeHtml(q.question_type)}</span>
      </div>
      <p class="question-content">${content}</p>
      ${optionsHtml}
      <div class="tag-chips">
        ${tags.difficulty ? `<span class="chip ${difficultyClass(tags.difficulty)}">${escapeHtml(tags.difficulty)}</span>` : ""}
        ${tags.bloom_level ? `<span class="chip chip-bloom">${escapeHtml(tags.bloom_level)}</span>` : ""}
        ${tags.topic ? `<span class="chip chip-topic">${escapeHtml(tags.topic)}</span>` : ""}
        ${examChips}
      </div>
    </div>
  `;
}

function renderDropped(dropped) {
  if (!dropped || !dropped.length) {
    droppedSection.hidden = true;
    return;
  }
  droppedSection.hidden = false;
  droppedMeta.textContent = `${dropped.length} question(s) dropped`;
  droppedList.innerHTML = dropped
    .map((d) => {
      const match = d.similarity_match;
      const matchLine = match
        ? `<span class="dropped-match">Matched ${escapeHtml(match.matched_qid)} (score ${match.score}, vs ${match.against}): "${escapeHtml((match.matched_content || "").slice(0, 120))}${(match.matched_content || "").length > 120 ? "…" : ""}"</span>`
        : "";
      return `
        <div class="dropped-item">
          <span class="dropped-reason">${escapeHtml(d.dropped_reason)}</span>
          <span class="qid">${escapeHtml(d.qid)}</span>
          <div>${escapeHtml((d.question_content || "").slice(0, 160))}${(d.question_content || "").length > 160 ? "…" : ""}</div>
          ${matchLine}
        </div>
      `;
    })
    .join("");
}

function showResult(data) {
  lastResult = data;
  statsEl.hidden = false;
  resultEl.hidden = false;

  const stats = data.stats || {};
  document.getElementById("statInput").textContent = stats.input_count ?? 0;
  document.getElementById("statEmbedded").textContent = stats.embedded_count ?? 0;
  document.getElementById("statDupDropped").textContent = stats.dropped_duplicate_count ?? 0;
  document.getElementById("statEmptyDropped").textContent = stats.dropped_empty_count ?? 0;
  document.getElementById("statMathml").textContent = stats.mathml_conversions ?? 0;
  document.getElementById("statOutput").textContent = stats.output_count ?? 0;

  resultMeta.textContent = `${data.source_file || "uploaded JSON"} · ${data.question_count} kept · ${data.dropped_count} dropped`;

  cardsView.innerHTML = (data.questions || []).map(renderQuestionCard).join("") ||
    '<p class="meta">No questions survived the pipeline. Check the dropped list below.</p>';
  outputEl.textContent = JSON.stringify(data, null, 2);

  renderDropped(data.dropped);

  showingRaw = false;
  cardsView.hidden = false;
  outputEl.hidden = true;
  viewToggleBtn.textContent = "View raw JSON";
}

async function runPipeline() {
  if (!lastFile) return;

  setStatus("Running pipeline (extract → embeddings → dedup → clean → MathML → tag)…", "loading");
  resultEl.hidden = true;
  statsEl.hidden = true;
  droppedSection.hidden = true;

  const form = new FormData();
  form.append("file", lastFile);
  if (lastBankFile) form.append("uploaded_bank", lastBankFile);
  form.append("similarity_threshold", thresholdInput.value || "0.93");
  form.append("skip_embeddings", skipEmbeddings.checked ? "true" : "false");
  form.append("force_rule_based_tagging", ruleBasedTagging.checked ? "true" : "false");

  try {
    const res = await fetch("/api/pipeline/run", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Pipeline run failed.");
    showResult(data);
    setStatus(
      `Done — ${data.question_count} questions kept, ${data.dropped_count} dropped.`,
      "success"
    );
  } catch (err) {
    setStatus(err.message || "Something went wrong.", "error");
  }
}

function onFileSelected(file) {
  if (!file?.name.toLowerCase().endsWith(".mmd")) {
    setStatus("Please upload a .mmd file.", "error");
    return;
  }
  lastFile = file;
  toolbar.hidden = false;
  resultEl.hidden = true;
  statsEl.hidden = true;
  droppedSection.hidden = true;
  setStatus(`Loaded ${file.name}. Click "Run pipeline".`, "success");
}

function onBankFileSelected(file) {
  if (!file) return;
  const name = file.name.toLowerCase();
  if (!name.endsWith(".mmd") && !name.endsWith(".json")) {
    setStatus("Uploaded bank must be a .mmd or .json file.", "error");
    return;
  }
  lastBankFile = file;
  bankFileName.textContent = file.name;
  bankClearBtn.hidden = false;
}

viewToggleBtn.addEventListener("click", () => {
  showingRaw = !showingRaw;
  cardsView.hidden = showingRaw;
  outputEl.hidden = !showingRaw;
  viewToggleBtn.textContent = showingRaw ? "View as cards" : "View raw JSON";
});

copyBtn.addEventListener("click", async () => {
  if (!lastResult) return;
  await navigator.clipboard.writeText(JSON.stringify(lastResult, null, 2));
  setStatus("Copied JSON to clipboard.", "success");
});

downloadJsonBtn.addEventListener("click", () => {
  if (!lastResult) return;
  const stem = (lastResult.source_file || "pipeline_output").replace(/\.mmd$/i, "");
  triggerDownload(
    new Blob([JSON.stringify(lastResult, null, 2)], { type: "application/json;charset=utf-8" }),
    `${stem}_pipeline.json`
  );
});

browseBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => { onFileSelected(fileInput.files[0]); fileInput.value = ""; });
runBtn.addEventListener("click", runPipeline);

dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  onFileSelected(e.dataTransfer.files[0]);
});

bankBrowseBtn.addEventListener("click", () => bankFileInput.click());
bankFileInput.addEventListener("change", () => { onBankFileSelected(bankFileInput.files[0]); bankFileInput.value = ""; });
bankClearBtn.addEventListener("click", () => {
  lastBankFile = null;
  bankFileName.textContent = "No file selected";
  bankClearBtn.hidden = true;
});
bankDropzone.addEventListener("dragover", (e) => { e.preventDefault(); bankDropzone.classList.add("dragover"); });
bankDropzone.addEventListener("dragleave", () => bankDropzone.classList.remove("dragover"));
bankDropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  bankDropzone.classList.remove("dragover");
  onBankFileSelected(e.dataTransfer.files[0]);
});
