const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");
const estimateBtn = document.getElementById("estimateBtn");
const convertBtn = document.getElementById("convertBtn");
const toolbar = document.getElementById("toolbar");
const statusEl = document.getElementById("status");
const previewEl = document.getElementById("preview");
const previewMeta = document.getElementById("previewMeta");
const previewTable = document.getElementById("previewTable");
const statsEl = document.getElementById("stats");
const eliminatedPanel = document.getElementById("eliminatedPanel");
const eliminatedList = document.getElementById("eliminatedList");
const resultsEl = document.getElementById("results");
const questionList = document.getElementById("questionList");
const downloadTxtBtn = document.getElementById("downloadTxtBtn");
const downloadJsonBtn = document.getElementById("downloadJsonBtn");

let lastFile = null;
let lastResult = null;
let questions = [];

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

function renderPreview(data) {
  previewEl.hidden = false;
  previewMeta.textContent = [
    `Source: ${data.source}`,
    `Subject: ${data.subject}`,
    `Class: ${data.class_level}`,
    `${data.batch_calls} batch calls (size ${data.batch_size})`,
    `~${data.estimated_input_tokens} tokens (save ~${data.token_saving_pct}%)`,
  ].join(" | ");

  const rows = (data.preview_scores || [])
    .map(
      (q) => `<tr>
        <td>${q.question_id}</td>
        <td>${escapeHtml(q.stem.slice(0, 80))}${q.stem.length > 80 ? "…" : ""}</td>
        <td>${q.scores.scq}</td>
        <td>${q.scores.mcq}</td>
        <td>${q.scores.integer}</td>
        <td><strong>${q.recommended_type.toUpperCase()}</strong></td>
        <td>${q.confidence}</td>
      </tr>`
    )
    .join("");

  previewTable.innerHTML = `<table>
    <thead><tr>
      <th>ID</th><th>Stem</th><th>SCQ</th><th>MCQ</th><th>INT</th><th>Pick</th><th>Conf</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderEliminated(items) {
  if (!items || !items.length) {
    eliminatedPanel.hidden = true;
    return;
  }
  eliminatedPanel.hidden = false;
  eliminatedList.innerHTML = items
    .map(
      (e) => `<div class="eliminated-item">
        <strong>${escapeHtml(e.question_id)}</strong>
        <span> — ${escapeHtml((e.stem || "").slice(0, 120))}${(e.stem || "").length > 120 ? "…" : ""}</span>
      </div>`
    )
    .join("");
}

function updateStats(data) {
  statsEl.hidden = false;
  const tokens = data.tokens || {};
  const inTok = (tokens.analysis_input || 0) + (tokens.conversion_input || 0);
  const outTok = (tokens.analysis_output || 0) + (tokens.conversion_output || 0);

  document.getElementById("statCount").textContent =
    `${data.converted_count ?? questions.length} / ${data.input_question_count ?? "?"}`;
  document.getElementById("statEliminated").textContent = data.eliminated_count ?? 0;
  document.getElementById("statBatches").textContent = data.batch_calls ?? "—";
  document.getElementById("statReview").textContent =
    data.needs_review_count ?? questions.filter((q) => q.needs_review).length;
  document.getElementById("statTokens").textContent = [inTok, outTok, tokens.total ?? inTok + outTok].join(" / ");
  document.getElementById("statModel").textContent = data.model || "—";
}

function renderQuestions() {
  questionList.innerHTML = "";
  questions.forEach((q, idx) => {
    const card = document.createElement("div");
    card.className = `q-card${q.needs_review ? " review" : ""}`;
    card.innerHTML = `
      <div class="q-card-head">
        <h3>${escapeHtml(q.question_id)} — ${escapeHtml(q.qid)}</h3>
        <div class="q-badges">
          <span class="badge">${escapeHtml(q.questionType.toUpperCase())}</span>
          <span class="badge">conf ${q.confidence}</span>
          ${q.needs_review ? '<span class="badge review">needs review</span>' : ""}
        </div>
      </div>
      <div class="inline-fields">
        <div class="field">
          <label>Type</label>
          <select data-field="questionType" data-idx="${idx}">
            <option value="scq">SCQ</option>
            <option value="mcq">MCQ</option>
            <option value="integer">INTEGER</option>
          </select>
        </div>
        <div class="field">
          <label>Answer key</label>
          <input data-field="answer_key" data-idx="${idx}" />
        </div>
        <div class="field">
          <label>Level</label>
          <select data-field="level" data-idx="${idx}">
            <option>EASY</option>
            <option>MEDIUM</option>
            <option>HARD</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label>Question content</label>
        <textarea data-field="question_content" data-idx="${idx}"></textarea>
      </div>
      <div class="field">
        <label>Solution</label>
        <textarea data-field="solution_content" data-idx="${idx}"></textarea>
      </div>
      <div class="q-actions">
        <button type="button" class="btn secondary regenerate-btn" data-idx="${idx}">Regenerate</button>
      </div>
    `;

    questionList.appendChild(card);

    card.querySelector('[data-field="questionType"]').value = q.questionType;
    card.querySelector('[data-field="answer_key"]').value = q.answer_key;
    card.querySelector('[data-field="level"]').value = q.level;
    card.querySelector('[data-field="question_content"]').value = q.question_content;
    card.querySelector('[data-field="solution_content"]').value = q.solution_content;
  });

  questionList.querySelectorAll("[data-field]").forEach((el) => {
    el.addEventListener("input", () => {
      const idx = Number(el.dataset.idx);
      questions[idx][el.dataset.field] = el.value;
    });
    el.addEventListener("change", () => {
      const idx = Number(el.dataset.idx);
      questions[idx][el.dataset.field] = el.value;
    });
  });

  questionList.querySelectorAll(".regenerate-btn").forEach((btn) => {
    btn.addEventListener("click", () => regenerateOne(Number(btn.dataset.idx)));
  });
}

async function regenerateOne(idx) {
  const q = questions[idx];
  const originalStem = lastResult?.preview_stem?.[q.question_id] || q.question_content.split("\n")[0];

  const form = new FormData();
  form.append("stem", originalStem);
  form.append("question_id", q.question_id);
  form.append("subject", q.subject);
  form.append("class_level", String(q.class_level));
  form.append("source", q.source);
  form.append("question_type", q.questionType);
  form.append("line_start", String(q.line_start));
  form.append("line_end", String(q.line_end));

  setStatus(`Regenerating ${q.question_id}...`, "loading");

  try {
    const res = await fetch("/api/bypass/regenerate", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Regenerate failed.");
    questions[idx] = data.question;
    renderQuestions();
    setStatus(`Regenerated ${q.question_id}. Tokens: ${data.tokens.input} in / ${data.tokens.output} out`, "success");
  } catch (err) {
    setStatus(err.message || "Regenerate failed.", "error");
  }
}

function showResults(data) {
  lastResult = data;
  questions = data.questions || [];
  resultsEl.hidden = false;
  updateStats(data);
  renderEliminated(data.eliminated || data.skipped || []);
  renderQuestions();
}

async function runEstimate() {
  if (!lastFile) return;
  setStatus("Estimating batch tokens (no API)...", "loading");
  const form = new FormData();
  form.append("file", lastFile);
  try {
    const res = await fetch("/api/bypass/estimate", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Estimate failed.");
    renderPreview(data);
    setStatus(`Preview ready — ${data.batch_calls} batch call(s). Click Convert all.`, "success");
  } catch (err) {
    setStatus(err.message || "Estimate failed.", "error");
  }
}

async function runConvert() {
  if (!lastFile) return;
  setStatus("Converting in batches via OpenAI...", "loading");
  previewEl.hidden = true;
  resultsEl.hidden = true;
  eliminatedPanel.hidden = true;
  const form = new FormData();
  form.append("file", lastFile);
  try {
    const res = await fetch("/api/bypass/convert", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Conversion failed.");
    showResults(data);
    setStatus(
      `Done — ${data.converted_count} converted, ${data.eliminated_count} eliminated, ` +
        `${data.batch_calls} batch call(s), ${data.tokens.total} tokens.`,
      "success"
    );
  } catch (err) {
    setStatus(err.message || "Conversion failed.", "error");
  }
}

async function downloadEdited(format) {
  if (!questions.length) {
    setStatus("Convert questions first.", "error");
    return;
  }
  const form = new FormData();
  form.append("payload", JSON.stringify(questions));
  form.append("output_format", format);
  form.append("filename_stem", lastResult?.source || "bypass_converted");

  setStatus(`Preparing .${format}...`, "loading");
  try {
    const res = await fetch("/api/bypass/export", { method: "POST", body: form });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Export failed.");
    }
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : `bypass_converted.${format}`;
    triggerDownload(blob, filename);
    setStatus(`Downloaded ${filename}`, "success");
  } catch (err) {
    setStatus(err.message || "Export failed.", "error");
  }
}

function onFileSelected(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".mmd")) {
    setStatus("Please upload a .mmd file.", "error");
    return;
  }
  lastFile = file;
  lastResult = null;
  questions = [];
  toolbar.hidden = false;
  previewEl.hidden = true;
  resultsEl.hidden = true;
  eliminatedPanel.hidden = true;
  statsEl.hidden = true;
  setStatus(`Loaded ${file.name}. Preview scores or Convert all.`, "success");
}

browseBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  onFileSelected(fileInput.files[0]);
  fileInput.value = "";
});
estimateBtn.addEventListener("click", runEstimate);
convertBtn.addEventListener("click", runConvert);
downloadTxtBtn.addEventListener("click", () => downloadEdited("txt"));
downloadJsonBtn.addEventListener("click", () => downloadEdited("json"));

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  onFileSelected(e.dataTransfer.files[0]);
});
