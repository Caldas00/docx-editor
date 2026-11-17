"use strict";

const $ = (id) => document.getElementById(id);
const state = { session: null, view: "redline", viewing: null, samples: [], busy: false };

const OP_LABEL = {
  replace_text: "replace", delete_text: "delete", insert_text: "insert",
  insert_paragraph: "new paragraph", delete_paragraph: "remove paragraph", format_text: "format",
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(msg, ms = 4200) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), ms);
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  let body = null;
  try { body = await res.json(); } catch { /* not json */ }
  if (!res.ok) throw new Error((body && body.detail) || `Request failed (${res.status})`);
  return body;
}
const post = (path, data) => api(path, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data ?? {}),
});

/* ------------------------------------------------------------------ boot */
async function boot() {
  try {
    const cfg = await api("/api/config");
    $("model-pill").textContent = `model ${cfg.model}`;
    state.samples = cfg.samples;
    renderSamples();
    if (!cfg.has_api_key) toast("OPENAI_API_KEY is not set - edits will fail.", 8000);
  } catch (e) { toast(e.message); }
  const params = new URLSearchParams(location.search);
  if (params.get("session")) {
    const v = params.get("version");
    try {
      setSession(await api(`/api/sessions/${encodeURIComponent(params.get("session"))}` + (v ? `?version=${Number(v)}` : "")));
    } catch { history.replaceState(null, "", "/"); }
  }
}

function renderSamples() {
  $("samples").innerHTML = state.samples.map((s) => `
    <button class="sample" data-name="${esc(s.name)}">
      <div class="s-icon">DOCX</div>
      <div class="s-title">${esc(s.title)}</div>
      <div class="s-desc">${esc(s.description)}</div>
    </button>`).join("");
  $("samples").querySelectorAll(".sample").forEach((b) =>
    b.addEventListener("click", () => openSample(b.dataset.name)));
}

/* ------------------------------------------------------------- documents */
async function openSample(name) {
  try { setSession(await post("/api/sessions/sample", { name })); } catch (e) { toast(e.message); }
}

async function uploadFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".docx")) return toast("Please choose a .docx file.");
  const fd = new FormData();
  fd.append("file", file);
  try { setSession(await api("/api/sessions/upload", { method: "POST", body: fd })); }
  catch (e) { toast(e.message); }
}

function setSession(s, { keepResult = false } = {}) {
  state.session = s;
  state.viewing = s.version;
  $("empty").hidden = true;
  $("toolbar").hidden = false;
  $("paper-wrap").hidden = false;
  $("change-doc").hidden = false;
  $("doc-name").textContent = s.name;
  $("instruction").disabled = false;
  $("apply-btn").disabled = false;
  const sample = state.samples.find((x) => x.name === s.name);
  $("chips").innerHTML = (sample ? sample.suggestions : []).map((t) =>
    `<button class="chip" type="button">${esc(t)}</button>`).join("");
  $("chips").querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => {
    $("instruction").value = c.textContent;
    $("instruction").focus();
  }));
  if (!keepResult) {
    $("clarify").hidden = true;
    if (s.outcome) renderResult(s.outcome); else $("result").hidden = true;
  }
  history.replaceState(null, "", `?session=${s.id}${s.version !== s.latest ? `&version=${s.version}` : ""}`);
  if (s.pending) showClarification(s.pending);
  renderDocument(s);
  renderHistory();
}

function renderDocument(s) {
  const hasRedline = Boolean(s.redline_html);
  const view = hasRedline ? state.view : "clean";
  $("view-redline").disabled = !hasRedline;
  $("view-redline").setAttribute("aria-selected", String(view === "redline"));
  $("view-clean").setAttribute("aria-selected", String(view === "clean"));
  $("legend").hidden = view !== "redline";
  const paper = $("paper");
  paper.innerHTML = view === "redline" ? s.redline_html : s.preview_html;
  paper.classList.toggle("clean", view === "clean");
  $("version-pill").textContent = s.version === 0 ? "original" :
    `version ${s.version}${s.version === s.latest ? " · latest" : ""}`;
  const dl = $("download-btn");
  dl.href = `/api/sessions/${s.id}/download?version=${s.version}`;
  $("undo-btn").disabled = s.latest === 0 || state.busy;
}

function renderHistory() {
  const s = state.session;
  const items = [{ version: 0, instruction: "Original document", summary: "", seconds: null }, ...s.history];
  $("history-card").hidden = s.history.length === 0;
  $("history").innerHTML = items.slice().reverse().map((h) => `
    <li><button data-v="${h.version}" class="${h.version === state.viewing ? "active" : ""}"
         title="${esc(h.summary || h.instruction)}">
      <span class="v">v${h.version}</span>
      <span class="h-text">${esc(h.instruction)}</span>
      <span class="h-meta">${h.seconds != null ? h.seconds + "s" : ""}</span>
    </button></li>`).join("");
  $("history").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => viewVersion(Number(b.dataset.v))));
}

async function viewVersion(v) {
  try {
    const s = await api(`/api/sessions/${state.session.id}?version=${v}`);
    state.session = { ...s };
    state.viewing = v;
    renderDocument(s);
    renderHistory();
    if (s.outcome) renderResult(s.outcome); else $("result").hidden = true;
  } catch (e) { toast(e.message); }
}

/* ------------------------------------------------------------------ edit */
function setBusy(on) {
  state.busy = on;
  const btn = $("apply-btn");
  btn.classList.toggle("loading", on);
  btn.disabled = on;
  $("instruction").disabled = on;
  $("answer-btn").disabled = on;
  $("undo-btn").disabled = on || !state.session || state.session.latest === 0;
  $("working").hidden = !on;
  clearInterval(setBusy._t);
  if (on) {
    const t0 = performance.now();
    $("elapsed").textContent = "0.0s";
    setBusy._t = setInterval(() => {
      $("elapsed").textContent = ((performance.now() - t0) / 1000).toFixed(1) + "s";
    }, 100);
  }
}

async function applyEdit() {
  const instruction = $("instruction").value.trim();
  if (!instruction || state.busy || !state.session) return;
  $("result").hidden = true;
  $("clarify").hidden = true;
  setBusy(true);
  try {
    const res = await post(`/api/sessions/${state.session.id}/edit`, { instruction });
    handleResult(res);
  } catch (e) { toast(e.message); } finally { setBusy(false); }
}

async function sendAnswer(answer) {
  answer = (answer ?? $("answer-input").value).trim();
  if (!answer || state.busy) return;
  $("clarify").hidden = true;
  setBusy(true);
  try {
    const res = await post(`/api/sessions/${state.session.id}/answer`, { answer });
    handleResult(res);
  } catch (e) { toast(e.message); $("clarify").hidden = false; } finally { setBusy(false); }
}

function handleResult({ outcome, session }) {
  if (outcome.status === "done") state.view = "redline";
  setSession(session, { keepResult: true });
  if (outcome.status === "done") scrollToFirstChange();
  if (outcome.status === "needs_clarification") {
    $("result").hidden = true;
    showClarification(outcome);
    return;
  }
  $("clarify").hidden = true;
  if (outcome.status === "done") $("instruction").value = "";
  renderResult(outcome);
}

function scrollToFirstChange() {
  const first = $("paper").querySelector("ins, del, .fmt-changed, .block-ins, .block-del");
  if (first) first.scrollIntoView({ behavior: "smooth", block: "center" });
}

function showClarification(o) {
  $("question").textContent = o.question;
  $("options").innerHTML = (o.options || []).map((opt) =>
    `<button type="button">${esc(opt)}</button>`).join("");
  $("options").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => sendAnswer(b.textContent)));
  $("answer-input").value = "";
  $("clarify").hidden = false;
}

const ICON = {
  ok: '<svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.2 14.2-4-4 1.4-1.4 2.6 2.6 5.6-5.6 1.4 1.4-7 7z"/></svg>',
  warn: '<svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>',
  bad: '<svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm4.3 12.9-1.4 1.4L12 13.4l-2.9 2.9-1.4-1.4 2.9-2.9-2.9-2.9 1.4-1.4 2.9 2.9 2.9-2.9 1.4 1.4-2.9 2.9 2.9 2.9z"/></svg>',
  tick: '<svg viewBox="0 0 24 24" width="11" height="11"><path fill="currentColor" d="m9 16.2-4.2-4.2-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>',
  cross: '<svg viewBox="0 0 24 24" width="11" height="11"><path fill="currentColor" d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>',
};

function renderResult(o) {
  const kind = { done: "ok", declined: "warn" }[o.status] || "bad";
  const title = { done: "Edit applied", declined: "Not applied" }[o.status] || "Could not apply the edit";
  const meta = `${o.seconds}s · ${o.llm_calls} LLM call${o.llm_calls === 1 ? "" : "s"}`;
  let html = `<div class="status-head ${kind}">${ICON[kind]}<span>${title}</span><span class="meta">${meta}</span></div>
    <p class="summary">${esc(o.message)}</p>`;

  if (o.status === "done" && o.changes.length) {
    html += `<div class="section-label">Changes</div><ul class="changes">` + o.changes.map((c) => {
      let text = "";
      if (c.op === "delete_paragraph") text = `<del>${esc(c.before)}</del>`;
      else if (c.op === "insert_paragraph") text = `<ins>${esc(c.after)}</ins>`;
      else if (c.op === "format_text") text = esc(c.after);
      else text = inlineDiff(c.before || "", c.after || "");
      return `<li><span class="op ${c.op}">${OP_LABEL[c.op] || c.op}</span><span class="blk">${esc(c.block_id)}</span>
        <div class="change-text">${text}</div></li>`;
    }).join("") + `</ul>`;
  }

  if (o.verification) {
    const v = o.verification;
    const n = v.checks.filter((c) => c.passed).length;
    html += `<div class="section-label">Integrity verification</div>
      <div class="verdict ${v.passed ? "" : "bad"}">${v.passed ? ICON.ok : ICON.bad}
        ${v.passed ? `All ${n} checks passed` : `${v.checks.length - n} check(s) failed - nothing was saved`}</div>
      <ul class="checks">` + v.checks.map((c) => `
        <li><span class="ic ${c.passed ? "ok" : "bad"}">${c.passed ? ICON.tick : ICON.cross}</span>
          <span>${esc(c.name)}${c.detail ? `<span class="detail">${esc(c.detail)}</span>` : ""}</span></li>`).join("") + `</ul>`;
  }
  if (o.plan) {
    html += `<details class="plan"><summary>Edit plan (JSON)</summary><pre>${esc(JSON.stringify(o.plan, null, 2))}</pre></details>`;
  }
  $("result").innerHTML = html;
  $("result").hidden = false;
}

/** Word-level diff for the change list (common prefix/suffix trim, good enough for one edit). */
function inlineDiff(a, b) {
  const ta = a.split(/(\s+)/), tb = b.split(/(\s+)/);
  let i = 0;
  while (i < ta.length && i < tb.length && ta[i] === tb[i]) i++;
  let j = 0;
  while (j < ta.length - i && j < tb.length - i && ta[ta.length - 1 - j] === tb[tb.length - 1 - j]) j++;
  // keep ~60 chars of context on each side, cut at a word boundary
  const ctx = (arr) => {
    const s = arr.join("");
    return s.length > 60 ? "…" + s.slice(-60).replace(/^\S*\s/, " ") : s;
  };
  const ctxEnd = (arr) => {
    const s = arr.join("");
    return s.length > 60 ? s.slice(0, 60).replace(/\s\S*$/, " ") + "…" : s;
  };
  const pre = ctx(ta.slice(0, i));
  const delPart = ta.slice(i, ta.length - j).join("");
  const insPart = tb.slice(i, tb.length - j).join("");
  const post = ctxEnd(ta.slice(ta.length - j));
  return esc(pre) + (delPart ? `<del>${esc(delPart)}</del>` : "") +
    (insPart ? `<ins>${esc(insPart)}</ins>` : "") + esc(post);
}

/* ---------------------------------------------------------------- events */
$("apply-btn").addEventListener("click", applyEdit);
$("instruction").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); applyEdit(); }
});
$("answer-btn").addEventListener("click", () => sendAnswer());
$("answer-input").addEventListener("keydown", (e) => { if (e.key === "Enter") sendAnswer(); });
$("view-redline").addEventListener("click", () => { state.view = "redline"; renderDocument(state.session); });
$("view-clean").addEventListener("click", () => { state.view = "clean"; renderDocument(state.session); });
$("undo-btn").addEventListener("click", async () => {
  try {
    const s = await post(`/api/sessions/${state.session.id}/undo`);
    $("result").hidden = true;
    setSession(s);
    toast("Last edit reverted.");
  } catch (e) { toast(e.message); }
});
$("change-doc").addEventListener("click", () => {
  state.session = null;
  history.replaceState(null, "", "/");
  $("empty").hidden = false;
  $("toolbar").hidden = true;
  $("legend").hidden = true;
  $("paper-wrap").hidden = true;
  $("result").hidden = true;
  $("clarify").hidden = true;
  $("history-card").hidden = true;
  $("change-doc").hidden = true;
  $("instruction").disabled = true;
  $("apply-btn").disabled = true;
  $("chips").innerHTML = "";
});

const dz = $("dropzone");
$("file-input").addEventListener("change", (e) => uploadFile(e.target.files[0]));
["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", (e) => uploadFile(e.dataTransfer.files[0]));

if (/Mac|iPhone|iPad/.test(navigator.platform)) $("mod-key").textContent = "⌘";
boot();
