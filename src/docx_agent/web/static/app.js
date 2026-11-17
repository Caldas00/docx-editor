"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  session: null,   // last session payload from the server
  view: "redline", // "redline" | "clean"
  selection: null, // {text, blocks} the user pointed at
  busy: false,
  samples: [],
  expanded: new Set(), // turn indexes whose change list is expanded
};

const OPS = {
  replace_text: ["edit", "replace"], delete_text: ["remove", "delete"], insert_text: ["add", "insert"],
  insert_paragraph: ["add", "new paragraph"], delete_paragraph: ["remove", "paragraph removed"],
  format_text: ["style", "format"], restyle_text: ["style", "restyle"],
  delete_images: ["remove", "pictures removed"], delete_table_row: ["remove", "row removed"],
  insert_table_row: ["add", "new row"], delete_table: ["remove", "table removed"],
  insert_table: ["add", "new table"], move_blocks: ["edit", "moved"],
  duplicate_blocks: ["add", "duplicated"], set_paragraph_format: ["style", "paragraph style"],
  split_paragraph: ["edit", "split"], merge_paragraphs: ["edit", "merged"],
  insert_page_break: ["add", "page break"], insert_table_column: ["add", "new column"],
  delete_table_columns: ["remove", "columns removed"], blocks_to_table: ["add", "into a table"],
  insert_hyperlink: ["edit", "link added"], remove_hyperlink: ["edit", "link removed"],
  set_hyperlink_url: ["edit", "link changed"], create_header_footer: ["add", "header/footer"],
};

const ICON = {
  ok: '<svg viewBox="0 0 24 24" width="15" height="15"><path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.2 14.2-4-4 1.4-1.4 2.6 2.6 5.6-5.6 1.4 1.4-7 7z"/></svg>',
  warn: '<svg viewBox="0 0 24 24" width="15" height="15"><path fill="currentColor" d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>',
  bad: '<svg viewBox="0 0 24 24" width="15" height="15"><path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm4.3 12.9-1.4 1.4L12 13.4l-2.9 2.9-1.4-1.4 2.9-2.9-2.9-2.9 1.4-1.4 2.9 2.9 2.9-2.9 1.4 1.4-2.9 2.9 2.9 2.9z"/></svg>',
  ask: '<svg viewBox="0 0 24 24" width="15" height="15"><path fill="currentColor" d="M11 18h2v-2h-2v2zm1-16a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0-14a4 4 0 0 0-4 4h2a2 2 0 1 1 4 0c0 2-3 1.75-3 5h2c0-2.25 3-2.5 3-5a4 4 0 0 0-4-4z"/></svg>',
  undo: '<svg viewBox="0 0 24 24" width="15" height="15"><path fill="currentColor" d="M12.5 8c-2.65 0-5.05 1-6.9 2.6L2 7v9h9l-3.62-3.62A7.96 7.96 0 0 1 12.5 10.5c3.54 0 6.55 2.31 7.6 5.5l2.37-.78A10.5 10.5 0 0 0 12.5 8z"/></svg>',
  chev: '<svg class="chev" viewBox="0 0 24 24" width="12" height="12"><path fill="currentColor" d="m9 6 6 6-6 6-1.4-1.4 4.6-4.6-4.6-4.6z"/></svg>',
  tick: '<svg class="ic-ok" viewBox="0 0 24 24" width="13" height="13"><path fill="currentColor" d="m9 16.2-4.2-4.2-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>',
  cross: '<svg class="ic-bad" viewBox="0 0 24 24" width="13" height="13"><path fill="currentColor" d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>',
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
const post = (path, data) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data ?? {}) });

/* =================================================================== boot */
async function boot() {
  try {
    const cfg = await api("/api/config");
    $("model-pill").textContent = cfg.model;
    state.samples = cfg.samples;
    $("samples").innerHTML = '<span>or try a sample:</span>' + cfg.samples.map((s) =>
      `<button type="button" data-name="${esc(s.name)}">${esc(s.title)}</button>`).join("");
    $("samples").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => openSample(b.dataset.name)));
    if (!cfg.has_api_key) toast("OPENAI_API_KEY is not set - edits will fail.", 8000);
  } catch (e) { toast(e.message); }
  const params = new URLSearchParams(location.search);
  if (params.get("session")) {
    const v = params.get("version");
    try {
      showSession(await api(`/api/sessions/${encodeURIComponent(params.get("session"))}` + (v ? `?version=${Number(v)}` : "")));
    } catch { goHome(); }
  }
}

/* ============================================================== documents */
async function openSample(name) {
  try { state.view = "redline"; showSession(await post("/api/sessions/sample", { name })); } catch (e) { toast(e.message); }
}
async function uploadFile(file) {
  if (!file) return;
  if (!/\.docx$/i.test(file.name)) return toast("Please choose a .docx file.");
  const fd = new FormData();
  fd.append("file", file);
  try { state.view = "redline"; showSession(await api("/api/sessions/upload", { method: "POST", body: fd })); }
  catch (e) { toast(e.message); }
  $("file-input").value = "";
}
function goHome() {
  state.session = null;
  clearSelection();
  history.replaceState(null, "", "/");
  document.body.classList.add("no-doc");
  $("home").hidden = false;
  $("workspace").hidden = true;
}

function showSession(s) {
  const switched = !state.session || state.session.id !== s.id;
  state.session = s;
  if (switched) state.expanded.clear();
  document.body.classList.remove("no-doc");
  $("home").hidden = true;
  $("workspace").hidden = false;
  $("doc-name").textContent = s.name;
  history.replaceState(null, "", `?session=${s.id}${s.version !== s.latest ? `&version=${s.version}` : ""}`);
  renderDocument();
  renderChat();
  updateComposer();
}

function renderDocument() {
  const s = state.session;
  const hasRedline = Boolean(s.redline_html);
  const view = hasRedline ? state.view : "clean";
  $("view-redline").disabled = !hasRedline;
  $("view-redline").setAttribute("aria-selected", String(view === "redline"));
  $("view-clean").setAttribute("aria-selected", String(view === "clean"));
  $("legend").hidden = view !== "redline";
  const paper = $("paper");
  paper.innerHTML = view === "redline" ? s.redline_html : s.preview_html;
  paper.classList.toggle("clean", view === "clean");
  $("version-pill").textContent = s.version === 0 ? "original" : `version ${s.version}`;
  $("old-version").hidden = s.version === s.latest;
  $("old-version-text").textContent = `You are viewing version ${s.version} of ${s.latest}. New edits apply to the latest version.`;
  $("download-btn").href = `/api/sessions/${s.id}/download?version=${s.version}`;
  $("undo-btn").disabled = s.latest === 0 || state.busy;
  if (state.selection) clearSelection(); // the highlighted range belonged to the old page
}

async function viewVersion(v) {
  try {
    showSession(await api(`/api/sessions/${state.session.id}?version=${v}`));
  } catch (e) { toast(e.message); }
}

/* ================================================================ selection */
// Works like selecting text to copy it: whatever you highlight in the preview is kept (painted
// green) after you click into the chat box, and is sent with your next message.
function captureSelection() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !state.session) return;
  const range = sel.getRangeAt(0);
  const paper = $("paper");
  if (!paper.contains(range.commonAncestorContainer)) return;
  const text = sel.toString().replace(/[ \t]+\n/g, "\n").trim();
  if (!text) return;
  if (state.session.version !== state.session.latest) {
    toast("Select text on the latest version - click “Back to latest”.");
    return;
  }
  const paras = [...paper.querySelectorAll(".para[data-bid]")].filter((el) => range.intersectsNode(el));
  const rows = [...paper.querySelectorAll("tr[data-row]")].filter((el) => range.intersectsNode(el));
  const blocks = paras.map((el) => el.dataset.bid);
  if (rows.length && paras.length > 1) blocks.push(...rows.map((el) => el.dataset.row));
  state.selection = { text: text.slice(0, 4000), blocks: [...new Set(blocks)].slice(0, 60), range: range.cloneRange() };
  paintSelection();
  updateComposer();
}
function clearSelection() {
  state.selection = null;
  paintSelection();
  updateComposer();
}
function paintSelection() {
  if (!(window.CSS && CSS.highlights && window.Highlight)) return;
  CSS.highlights.delete("docx-selection");
  if (state.selection && state.selection.range) CSS.highlights.set("docx-selection", new Highlight(state.selection.range));
}
const selectionPayload = () => state.selection && { text: state.selection.text, blocks: state.selection.blocks };

/* ===================================================================== chat */
function renderChat(pendingInstruction) {
  const s = state.session;
  const box = $("messages");
  const parts = [];
  if (!s.turns.length && !pendingInstruction) {
    parts.push(`<div class="empty-chat">
      <h3>What should change?</h3>
      <p>Describe an edit in plain language, or select text in the document first and say what to do with it.</p>
      <div class="suggestions">${s.suggestions.map((t) => `<button type="button">${esc(t)}</button>`).join("")}</div>
    </div>`);
  }
  s.turns.forEach((t) => parts.push(...turnHtml(t)));
  if (pendingInstruction) {
    parts.push(userBubble(pendingInstruction.text, pendingInstruction.selection));
    parts.push(`<div class="msg agent"><span class="typing"><i></i><i></i><i></i></span><span class="working-text" id="elapsed">0.0s</span></div>`);
  }
  box.innerHTML = parts.join("");
  box.querySelectorAll(".suggestions button").forEach((b) => b.addEventListener("click", () => {
    $("instruction").value = b.textContent;
    autoGrow();
    $("instruction").focus();
  }));
  box.querySelectorAll("[data-answer]").forEach((b) => b.addEventListener("click", () => send(b.dataset.answer)));
  box.querySelectorAll("[data-version]").forEach((b) => b.addEventListener("click", () => viewVersion(Number(b.dataset.version))));
  box.querySelectorAll("[data-undo]").forEach((b) => b.addEventListener("click", undo));
  box.querySelectorAll("[data-more]").forEach((b) => b.addEventListener("click", () => {
    state.expanded.add(Number(b.dataset.more));
    renderChat();
  }));
  box.scrollTop = box.scrollHeight;
}

function userBubble(text, selection) {
  const quote = selection ? `<span class="quote"><b>Selection</b> · ${esc(selection.text.length > 140 ? selection.text.slice(0, 140) + "…" : selection.text)}</span>` : "";
  return `<div class="msg user">${quote}${esc(text)}</div>`;
}

function turnHtml(t) {
  const out = [userBubble(t.instruction, t.selection)];
  const s = state.session;
  const meta = [t.seconds != null ? `${t.seconds}s` : null, t.cost != null ? `$${t.cost < 0.001 ? t.cost.toFixed(5) : t.cost.toFixed(4)}` : null].filter(Boolean).join(" · ");
  const metaHtml = meta ? `<span class="meta" title="${esc(t.model || "")} · ${t.llm_calls || 0} LLM call(s) · ${(t.usage && t.usage.input) || 0} input tokens">${meta}</span>` : "";

  if (t.status === "needs_clarification") {
    const live = t.index === s.turns.length - 1 && !state.busy;
    out.push(`<div class="msg agent">
      <div class="agent-top"><span class="status warn">${ICON.ask} Which one did you mean?</span>${metaHtml}</div>
      <div class="question">${esc(t.question)}</div>
      <div class="options">${(t.options || []).map((o) => `<button type="button" data-answer="${esc(o)}" ${live ? "" : "disabled"}>${esc(o)}</button>`).join("")}</div>
      ${live ? '<div class="hint-line">Pick an option or just reply below.</div>' : ""}
    </div>`);
    return out;
  }
  if (t.status === "declined" || t.status === "failed") {
    const cls = t.status === "declined" ? "warn" : "bad";
    const title = t.status === "declined" ? "Not applied" : "Could not apply";
    out.push(`<div class="msg agent">
      <div class="agent-top"><span class="status ${cls}">${ICON[cls]} ${title}</span>${metaHtml}</div>
      <div class="agent-text">${esc(t.message)}</div>${checksHtml(t)}</div>`);
    return out;
  }
  if (t.status !== "done") return out;

  const isViewing = s.version === t.version;
  const canUndo = !t.undone && t.version === s.latest && !state.busy;
  const changes = t.changes || [];
  const limit = state.expanded.has(t.index) ? changes.length : 4;
  const list = changes.slice(0, limit).map(changeHtml).join("");
  const more = changes.length > limit ? `<button type="button" class="more-btn" data-more="${t.index}">Show ${changes.length - limit} more</button>` : "";
  out.push(`<div class="msg agent ${t.undone ? "muted" : ""}">
    <div class="agent-top">
      <span class="status ${t.undone ? "neutral" : "ok"}">${t.undone ? ICON.undo + " Undone" : ICON.ok + " Applied"}</span>
      ${t.version != null && !t.undone ? `<button type="button" class="vlink ${isViewing ? "active" : ""}" data-version="${t.version}" title="Show this version">v${t.version}</button>` : ""}
      ${metaHtml}
    </div>
    <div class="agent-text">${esc(t.message)}</div>
    <ul class="changes">${list}</ul>${more}
    ${checksHtml(t)}
    ${t.plan ? `<details class="plan"><summary>${ICON.chev} Edit plan</summary><pre>${esc(JSON.stringify(t.plan, null, 2))}</pre></details>` : ""}
    ${canUndo ? `<div class="card-actions"><button type="button" class="link-btn" data-undo>Undo this edit</button></div>` : ""}
  </div>`);
  return out;
}

function checksHtml(t) {
  const v = t.verification;
  if (!v) return "";
  const n = v.checks.filter((c) => c.passed).length;
  const label = v.passed ? `Verified · ${n} integrity checks passed` : `${v.checks.length - n} integrity check(s) failed - nothing saved`;
  return `<details class="checks"><summary class="${v.passed ? "ok" : "bad"}">${ICON.chev} ${label}</summary>
    <ul class="check-list">${v.checks.map((c) => `<li>${c.passed ? ICON.tick : ICON.cross}<span>${esc(c.name)}${c.detail ? `<span class="d">${esc(c.detail)}</span>` : ""}</span></li>`).join("")}</ul></details>`;
}

function changeHtml(c) {
  const [cls, label] = OPS[c.op] || ["edit", c.op];
  let text;
  if (c.before == null) text = `<ins>${esc(c.after)}</ins>`;
  else if (c.after == null) text = `<del>${esc(c.before)}</del>`;
  else if (["format_text", "restyle_text", "set_paragraph_format", "move_blocks", "split_paragraph", "merge_paragraphs", "insert_hyperlink", "remove_hyperlink", "set_hyperlink_url"].includes(c.op)) text = esc(c.after.length > 160 ? c.after.slice(0, 160) + "…" : c.after);
  else text = inlineDiff(c.before, c.after);
  return `<li><span class="op ${cls}">${esc(label)}</span>${text}</li>`;
}

/** Word-level diff for one change (common prefix/suffix trimmed, short context kept). */
function inlineDiff(a, b) {
  const ta = a.split(/(\s+)/), tb = b.split(/(\s+)/);
  let i = 0;
  while (i < ta.length && i < tb.length && ta[i] === tb[i]) i++;
  let j = 0;
  while (j < ta.length - i && j < tb.length - i && ta[ta.length - 1 - j] === tb[tb.length - 1 - j]) j++;
  const pre = ta.slice(0, i).join(""), post = ta.slice(ta.length - j).join("");
  const preT = pre.length > 50 ? "…" + pre.slice(-50).replace(/^\S*\s/, " ") : pre;
  const postT = post.length > 50 ? post.slice(0, 50).replace(/\s\S*$/, " ") + "…" : post;
  const d = ta.slice(i, ta.length - j).join(""), n = tb.slice(i, tb.length - j).join("");
  return esc(preT) + (d ? `<del>${esc(d)}</del>` : "") + (n ? `<ins>${esc(n)}</ins>` : "") + esc(postT);
}

/* ================================================================ composer */
function updateComposer() {
  const s = state.session;
  const chip = $("sel-chip");
  if (state.selection) {
    const t = state.selection.text;
    $("sel-text").textContent = `Selected: “${t.length > 90 ? t.slice(0, 90) + "…" : t}”`;
    $("sel-text").title = `${t}\n\nBlocks: ${state.selection.blocks.join(", ")}`;
    chip.hidden = false;
  } else chip.hidden = true;
  const last = s && s.turns.length ? s.turns[s.turns.length - 1] : null;
  const asked = last && last.status === "needs_clarification";
  $("instruction").placeholder = state.selection ? "What should happen to the selected text?"
    : asked ? "Reply to the assistant…" : "Describe the change…";
  $("send-btn").disabled = state.busy;
  $("instruction").disabled = state.busy;
}

function autoGrow() {
  const ta = $("instruction");
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
}

function setBusy(on, pending) {
  state.busy = on;
  clearInterval(setBusy._t);
  if (on) {
    renderChat(pending);
    const t0 = performance.now();
    setBusy._t = setInterval(() => {
      const el = $("elapsed");
      if (el) el.textContent = ((performance.now() - t0) / 1000).toFixed(1) + "s";
    }, 100);
  }
  updateComposer();
  $("undo-btn").disabled = on || !state.session || state.session.latest === 0;
}

function submit() {
  const text = $("instruction").value.trim();
  if (text) send(text);
}

async function send(text) {
  if (!text || state.busy || !state.session) return;
  const selection = selectionPayload();
  $("instruction").value = "";
  autoGrow();
  setBusy(true, { text, selection });
  try {
    const res = await post(`/api/sessions/${state.session.id}/edit`, { instruction: text, selection });
    if (res.turn.status === "done") state.view = "redline";
    state.busy = false;
    clearSelection();
    showSession(res.session);
    if (res.turn.status === "done") scrollToFirstChange();
  } catch (e) {
    toast(e.message);
    if (!$("instruction").value) $("instruction").value = text;
  } finally { setBusy(false); }
}

async function undo() {
  try {
    showSession(await post(`/api/sessions/${state.session.id}/undo`));
    toast("Last edit undone.");
  } catch (e) { toast(e.message); }
}

function scrollToFirstChange() {
  const first = $("paper").querySelector("ins, del, .fmt-changed, .block-ins, .block-del, .row-ins, .row-del, .tbl-del");
  if (first) first.scrollIntoView({ behavior: "smooth", block: "center" });
}

/* ================================================================== events */
$("composer").addEventListener("submit", (e) => { e.preventDefault(); submit(); });
$("instruction").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); }
});
$("instruction").addEventListener("input", autoGrow);
$("sel-clear").addEventListener("click", clearSelection);
// Any way of selecting text (drag, double/triple click, shift+arrows) ends up here.
let selTimer = null;
document.addEventListener("selectionchange", () => {
  clearTimeout(selTimer);
  selTimer = setTimeout(captureSelection, 120);
});
document.addEventListener("mouseup", () => setTimeout(captureSelection, 0));
$("view-redline").addEventListener("click", () => { state.view = "redline"; renderDocument(); });
$("view-clean").addEventListener("click", () => { state.view = "clean"; renderDocument(); });
$("undo-btn").addEventListener("click", undo);
$("back-latest").addEventListener("click", () => viewVersion(state.session.latest));
$("open-btn").addEventListener("click", () => $("file-input").click());
$("home-btn").addEventListener("click", goHome);
$("file-input").addEventListener("change", (e) => uploadFile(e.target.files[0]));

const dz = $("dropzone");
["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", (e) => uploadFile(e.dataTransfer.files[0]));
// dropping a file anywhere on the workspace opens it too
document.addEventListener("dragover", (e) => { if (state.session) e.preventDefault(); });
document.addEventListener("drop", (e) => {
  if (!state.session || !e.dataTransfer.files.length) return;
  e.preventDefault();
  uploadFile(e.dataTransfer.files[0]);
});

boot();
