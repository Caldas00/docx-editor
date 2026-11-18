"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  session: null,   // last session payload from the server
  view: "redline", // "redline" | "clean"
  selection: null, // {text, blocks} the user pointed at
  busy: false,
  expanded: new Set(), // turn indexes whose change list is expanded
  marks: [],       // the user's own markers: [{id, text, at}] (found again by their text)
  pending: null,   // {text, selection} of the message the agent is working on
  queue: [],       // messages typed while the agent was busy, sent one after another
};

const OPS = {
  replace_text: ["edit", "replace"], delete_text: ["remove", "delete"], insert_text: ["add", "insert"],
  insert_paragraph: ["add", "new paragraph"], delete_paragraph: ["remove", "paragraph removed"],
  format_text: ["style", "format"], restyle_text: ["style", "restyle"],
  delete_images: ["remove", "pictures removed"], delete_table_row: ["remove", "row removed"],
  insert_table_row: ["add", "new row"], delete_table: ["remove", "table removed"],
  reorder_table_rows: ["edit", "rows reordered"], set_shape_fill: ["style", "shape colour"],
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
    state.exact = Boolean(cfg.exact_pages) && Boolean(window.pdfjsLib);
    if (state.exact) {
      pdfjsLib.GlobalWorkerOptions.workerSrc =
        "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
      $("view-clean").title = "The document laid out page by page by LibreOffice";
    }
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
  state.marks = [];
  $("marks-pop").hidden = true;
  history.replaceState(null, "", "/");
  document.body.classList.add("no-doc");
  $("home").hidden = false;
  $("workspace").hidden = true;
}

function showSession(s) {
  const switched = !state.session || state.session.id !== s.id;
  state.session = s;
  if (switched) {
    state.expanded.clear();
    state.queue = [];
    state.marks = loadMarks(s.id);
  }
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
  $("shadow").innerHTML = s.preview_html; // maps selections on exact pages to block ids
  if (view === "clean" && state.exact) {
    paper.className = "paper clean";
    finishHeader(s);
    state.layout = renderExact().then(() => resolveMarks());
    return state.layout;
  }
  paper.innerHTML = view === "redline" ? s.redline_html : s.preview_html;
  paper.className = "paper";
  paper.classList.toggle("clean", view === "clean");
  finishHeader(s);
  if (state.selection) clearSelection(); // the highlighted range belonged to the old page
  // lay it out on pages, then find the marks again (moving nodes resets old ranges)
  state.layout = paginate().then(() => resolveMarks());
  return state.layout;
}
function finishHeader(s) {
  $("version-pill").textContent = s.version === 0 ? "original" : `version ${s.version}`;
  $("old-version").hidden = s.version === s.latest;
  $("old-version-text").textContent = `You are viewing version ${s.version} of ${s.latest}. New edits apply to the latest version.`;
  $("download-btn").href = `/api/sessions/${s.id}/download?version=${s.version}`;
  $("undo-btn").disabled = s.latest === 0 || state.busy;
}

/* ============================================================== exact pages */
// When LibreOffice is available (it ships in the Docker image), the "Document" view shows the
// pages as a real layout engine lays them out: the server converts the version to PDF and
// pdf.js draws each page with a text layer, so text can still be selected, marked and pointed
// at. Without it, the view uses the app's own HTML layout.
async function renderExact() {
  const token = (paginate.n = (paginate.n || 0) + 1);
  const s = state.session;
  const paper = $("paper");
  paper.style.zoom = "";
  paper.style.width = "";
  if (state.selection) clearSelection();
  paper.innerHTML = '<div class="exact-loading"><span class="typing"><i></i><i></i><i></i></span>Laying out the pages…</div>';
  let pdf;
  try {
    pdf = await pdfjsLib.getDocument({ url: `/api/sessions/${s.id}/pdf?version=${s.version}` }).promise;
  } catch {
    if (token !== paginate.n) return;
    toast("The pages could not be laid out; showing the approximate preview.");
    state.exact = false;
    $("view-clean").textContent = "Clean";
    return renderDocument();
  }
  if (token !== paginate.n) return;
  const scale = 96 / 72; // PDF points -> CSS pixels: 100 % like Word
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const sheets = [];
  for (let n = 1; n <= pdf.numPages; n++) {
    const page = await pdf.getPage(n);
    if (token !== paginate.n) return;
    const vp = page.getViewport({ scale });
    const sheet = document.createElement("section");
    sheet.className = "page exact-page";
    sheet.style.width = `${vp.width}px`;
    sheet.style.height = `${vp.height}px`;
    sheet.setAttribute("aria-label", `Page ${n}`);
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(vp.width * ratio);
    canvas.height = Math.floor(vp.height * ratio);
    const layer = document.createElement("div");
    layer.className = "textLayer";
    layer.style.setProperty("--scale-factor", String(scale));
    sheet.append(canvas, layer);
    sheets.push({ sheet, page, vp, canvas, layer });
  }
  paper.replaceChildren(...sheets.map((x) => x.sheet));
  paper.classList.add("paged", "exact");
  fitPages();
  // the picture and the selectable text layer are built side by side (a background tab may
  // hold back canvas drawing; selection should not wait for it)
  sheets.forEach(({ page, vp, canvas }) => {
    page.render({ canvasContext: canvas.getContext("2d"), viewport: vp,
      transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null }).promise.catch(() => {});
  });
  await Promise.all(sheets.map(({ page, vp, layer }) => page.getTextContent()
    .then((text) => pdfjsLib.renderTextLayer({
      textContentSource: text, container: layer, viewport: vp, textDivs: [] }).promise)
    .then(() => addEndOfContent(layer))
    .catch(() => {})));
  if (token === paginate.n) {
    paintExactChanges();
    renderRail();
  }
}
// Text on a PDF page is a scatter of absolutely placed words. When a drag passes over the gaps
// between them the browser has no text under the pointer and jumps the selection to wherever
// the page's text happens to start or end, often half the page away. pdf.js's own viewer
// avoids this with an "end of content" block: while selecting it covers the page *under* the
// words and sits right after the word being dragged to, so blank space extends the selection
// up to that word instead.
const textLayers = new Map(); // text layer -> its end-of-content block
let lastExactRange = null;
function addEndOfContent(layer) {
  const end = document.createElement("div");
  end.className = "endOfContent";
  layer.append(end);
  textLayers.set(layer, end);
  layer.addEventListener("mousedown", () => layer.classList.add("selecting"));
}
function resetEndOfContent(layer, end) {
  layer.append(end);
  end.style.width = end.style.height = "";
  layer.classList.remove("selecting");
}
function steadyExactSelection() {
  for (const layer of [...textLayers.keys()]) if (!layer.isConnected) textLayers.delete(layer);
  if (!textLayers.size) return;
  const sel = document.getSelection();
  if (!sel || sel.rangeCount === 0) {
    textLayers.forEach((end, layer) => resetEndOfContent(layer, end));
    lastExactRange = null;
    return;
  }
  const range = sel.getRangeAt(0);
  textLayers.forEach((end, layer) => {
    if (range.intersectsNode(layer)) layer.classList.add("selecting");
    else resetEndOfContent(layer, end);
  });
  // the end being dragged: the start when the drag goes backwards, else the end
  const backwards = lastExactRange && (range.compareBoundaryPoints(Range.END_TO_END, lastExactRange) === 0 ||
    range.compareBoundaryPoints(Range.START_TO_END, lastExactRange) === 0);
  let anchor = backwards ? range.startContainer : range.endContainer;
  if (anchor.nodeType === Node.TEXT_NODE) anchor = anchor.parentNode;
  const layer = anchor.closest && anchor.closest(".textLayer");
  const end = layer && textLayers.get(layer);
  if (end && anchor !== layer && anchor !== end && anchor.parentNode) {
    end.style.width = `${layer.offsetWidth}px`;
    end.style.height = `${layer.offsetHeight}px`;
    anchor.parentNode.insertBefore(end, backwards ? anchor : anchor.nextSibling);
  }
  lastExactRange = range.cloneRange();
}
document.addEventListener("pointerup", () => {
  textLayers.forEach((end, layer) => resetEndOfContent(layer, end));
  lastExactRange = null;
});

// The block ids of a selection made on exact pages: find each selected line in the HTML copy.
function blocksForText(text) {
  const norm = (t) => t.replace(/\s+/g, " ").trim();
  const paras = [...$("shadow").querySelectorAll(".para[data-bid]")]
    .map((el) => ({ bid: el.dataset.bid, text: norm(el.textContent) }));
  const out = [];
  for (const line of text.split(/\n+/).map(norm).filter((l) => l.length >= 3)) {
    // the most specific paragraph: a text box's own paragraph, not the one holding the shape
    const hit = paras.filter((p) => p.text.includes(line)).sort((a, b) => a.text.length - b.text.length)[0] ||
      paras.find((p) => p.text.length >= 3 && line.includes(p.text));
    if (hit && !out.includes(hit.bid)) out.push(hit.bid);
  }
  const order = new Map(paras.map((p, i) => [p.bid, i]));
  return out.sort((a, b) => order.get(a) - order.get(b));
}

/* ==================================================================== pages */
// The preview is laid out on real pages, like Word's print layout: the document's own page
// size and margins, its header and footer on every page with the page number filled in,
// page and section breaks starting a new page, and long tables continuing on the next page.
// Line breaking differs a little from Word's, so page ends are close to Word's, not exact.
const DEFAULT_PAGE = { width: 816, height: 1056, top: 96, bottom: 96, left: 96, right: 96, header: 48, footer: 48 };
function isPageBreakPara(el) {
  if (!el.matches(".para") || el.classList.contains("block-del")) return null;
  const breaks = [...el.querySelectorAll(".page-break")].filter((b) => !b.closest("del"));
  if (!breaks.length) return null;
  const before = document.createRange();
  before.setStart(el, 0);
  before.setEndBefore(breaks[0]);
  const after = document.createRange();
  after.setStartAfter(breaks[breaks.length - 1]);
  after.setEnd(el, el.childNodes.length);
  const textBefore = before.toString().replace(/\u00a0/g, " ").trim();
  const textAfter = after.toString().replace(/\u00a0/g, " ").trim();
  if (!textBefore && !textAfter) return "only";
  return textBefore ? "after" : "before";
}
async function paginate() {
  const token = (paginate.n = (paginate.n || 0) + 1);
  const paper = $("paper");
  const pg = { ...DEFAULT_PAGE, ...(state.session && state.session.page) };
  const textW = pg.width - pg.left - pg.right;
  const textH = pg.height - pg.top - pg.bottom;
  paper.style.zoom = "";
  paper.classList.remove("paged");
  paper.classList.add("measuring");
  paper.style.width = `${textW}px`;
  const hfs = [...paper.querySelectorAll(":scope > .hf")];
  hfs.forEach((h) => h.remove());
  // Picture sizes are needed to measure. decode() can wait forever in a background tab, so
  // wait at most 1.5 s; pictures that arrive later trigger one more layout.
  const imgs = [...paper.querySelectorAll("img")];
  const decoded = Promise.all(imgs.map((img) => (img.decode ? img.decode().catch(() => {}) : null)));
  await Promise.race([decoded, new Promise((r) => setTimeout(r, 1500))]);
  if (token !== paginate.n) return; // a newer render took over
  const late = imgs.filter((img) => !img.complete);
  if (late.length) {
    let pending = late.length;
    const again = () => { if (--pending === 0 && token === paginate.n) renderDocument(); };
    late.forEach((img) => { img.addEventListener("load", again, { once: true }); img.addEventListener("error", again, { once: true }); });
  }

  const origin = paper.getBoundingClientRect().top;
  const top = (el) => el.getBoundingClientRect().top - origin;
  const bottom = (el) => el.getBoundingClientRect().bottom - origin;
  const pages = [];
  let cur = null, start = 0;
  const newPage = (at, cls = "") => { cur = { items: [], cls }; pages.push(cur); start = at; };
  newPage(0);
  for (const el of [...paper.children]) {
    const kind = el.matches(".para") ? isPageBreakPara(el) : null;
    const t = top(el), b = bottom(el);
    if ((kind === "before" || el.classList.contains("break-before")) && cur.items.length) newPage(t);
    if (el.tagName === "TABLE" && b - start > textH) { // continue the table on the next pages
      let rows = [];
      for (const tr of el.rows) {
        if (bottom(tr) - start > textH && (rows.length || cur.items.length)) {
          if (rows.length) cur.items.push({ table: el, rows });
          newPage(top(tr));
          rows = [];
        }
        rows.push(tr);
      }
      if (rows.length) cur.items.push({ table: el, rows });
      continue;
    }
    if (b - start > textH && cur.items.length) newPage(t);
    if (kind === "only") el.classList.add("pb-only");
    cur.items.push(el);
    if (kind === "only" || kind === "after" || el.classList.contains("section-end")) {
      newPage(b, el.classList.contains("block-ins") || el.querySelector("ins .page-break") ? "page-new" : "");
    }
  }
  while (pages.length > 1 && !pages[pages.length - 1].items.length) pages.pop();

  const pick = (kind, n) => {
    const list = hfs.filter((h) => h.dataset.kind === kind);
    const by = (u) => list.find((h) => (h.dataset.uses || "default").split(",").includes(u));
    if (n === 1 && pg.title_page) return by("first");
    if (pg.even_and_odd && n % 2 === 0) return by("even");
    return by("default");
  };
  const fill = (root, n) => {
    root.querySelectorAll('[data-field="page"]').forEach((f) => { f.textContent = String(n); });
    root.querySelectorAll('[data-field="numpages"]').forEach((f) => { f.textContent = String(pages.length); });
  };
  const frag = document.createDocumentFragment();
  const tablesSeen = new Set();
  pages.forEach((p, i) => {
    const n = i + 1;
    const sheet = document.createElement("section");
    sheet.className = `page ${p.cls}`.trim();
    sheet.style.cssText = `width:${pg.width}px;min-height:${pg.height}px;padding:${pg.top}px ${pg.right}px ${pg.bottom}px ${pg.left}px`;
    sheet.setAttribute("aria-label", `Page ${n}`);
    const body = document.createElement("div");
    body.className = "page-body";
    body.style.minHeight = `${textH}px`;
    for (const item of p.items) {
      if (!item.table) { body.appendChild(item); continue; }
      let table = item.table;
      if (tablesSeen.has(table)) { // a later part of a split table: a fresh table shell
        table = item.table.cloneNode(false);
        table.removeAttribute("data-bid");
        table.classList.add("continued");
        table.appendChild(document.createElement("tbody"));
      }
      tablesSeen.add(item.table);
      if (table !== item.table) item.rows.forEach((tr) => table.tBodies[0].appendChild(tr));
      body.appendChild(table);
    }
    fill(body, n);
    sheet.appendChild(body);
    for (const kind of ["header", "footer"]) {
      const src = pick(kind, n);
      if (!src) continue;
      const box = document.createElement("div");
      box.className = `page-hf page-${kind}${n > 1 ? " page-hf-repeat" : ""}`;
      box.style.cssText = `left:${pg.left}px;right:${pg.right}px;` +
        (kind === "header" ? `top:${pg.header}px` : `bottom:${pg.footer}px`);
      box.appendChild(src.cloneNode(true));
      fill(box, n);
      sheet.appendChild(box);
    }
    const num = document.createElement("span");
    num.className = "page-num";
    num.textContent = `${n} / ${pages.length}`;
    sheet.appendChild(num);
    frag.appendChild(sheet);
  });
  // rows that went to continuation tables were moved; the original keeps only its first part
  paper.replaceChildren(frag);
  paper.style.width = "";
  paper.classList.remove("measuring");
  paper.classList.add("paged");
  paper.querySelectorAll(".page").forEach((sheet) => {
    sheet.querySelectorAll(".anchored").forEach((a) => placeAnchored(a, sheet, pg));
  });
  fitPages();
}
// Text boxes, lines and pictures anchored to the page (a cover page, the rule under a header)
// are placed where Word puts them: their offset from the page, the margins or the paragraph.
function placeAnchored(a, sheet, pg) {
  const d = a.dataset;
  const w = parseFloat(d.w) || a.offsetWidth;
  const h = parseFloat(d.h) || a.offsetHeight;
  const box = sheet.getBoundingClientRect();
  const para = a.closest(".para");
  const paraTop = para ? para.getBoundingClientRect().top - box.top : pg.top;
  const horiz = {
    page: [0, pg.width], margin: [pg.left, pg.width - pg.left - pg.right],
    leftMargin: [0, pg.left], rightMargin: [pg.width - pg.right, pg.right],
  }[d.rh] || [pg.left, pg.width - pg.left - pg.right];
  const vert = {
    page: [0, pg.height], margin: [pg.top, pg.height - pg.top - pg.bottom],
    topMargin: [0, pg.top], bottomMargin: [pg.height - pg.bottom, pg.bottom],
  }[d.rv] || [paraTop, pg.height - paraTop];
  const place = (offset, align, [base, size], len) => (offset !== "" && offset !== undefined
    ? base + parseFloat(offset)
    : base + (align === "center" ? (size - len) / 2 : (align === "right" || align === "bottom") ? size - len : 0));
  a.style.left = `${Math.round(place(d.x, d.ah, horiz, w))}px`;
  a.style.top = `${Math.round(place(d.y, d.av, vert, h))}px`;
  sheet.appendChild(a);
}
// Zoom the pages down when the viewer is narrower than a page (like Word's "fit width").
function fitPages() {
  const paper = $("paper");
  if (!paper.classList.contains("paged") || !state.session) return;
  const pg = { ...DEFAULT_PAGE, ...state.session.page };
  const first = paper.querySelector(".exact-page");
  const width = first ? parseFloat(first.style.width) : pg.width;
  const avail = $("paper-wrap").clientWidth - 8;
  const z = Math.min(1, avail / width);
  paper.style.zoom = z < 0.999 ? String(Math.max(0.3, z)) : "";
}

async function viewVersion(v) {
  try {
    showSession(await api(`/api/sessions/${state.session.id}?version=${v}`));
  } catch (e) { toast(e.message); }
}

/* ================================================================ selection */
// Works like selecting text to copy it: whatever you highlight in the preview is kept (painted
// green) after you click into the chat box, and is sent with your next message. Clicking
// anywhere outside the chat (or pressing Esc) drops it, like clicking away in an editor.
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
  const blocks = paper.classList.contains("exact") ? blocksForText(text) : paras.map((el) => el.dataset.bid);
  if (rows.length && paras.length > 1) blocks.push(...rows.map((el) => el.dataset.row));
  state.selection = { text: text.slice(0, 4000), blocks: [...new Set(blocks)].slice(0, 60), range: range.cloneRange() };
  paintSelection();
  updateComposer();
  placeMarkPill();
}
function clearSelection() {
  state.selection = null;
  const sel = window.getSelection();
  if (sel && sel.rangeCount && $("paper").contains(sel.anchorNode)) sel.removeAllRanges();
  paintSelection();
  updateComposer();
  $("mark-pill").hidden = true;
}
function paintSelection() {
  if (!(window.CSS && CSS.highlights && window.Highlight)) return;
  CSS.highlights.delete("docx-selection");
  if (state.selection && state.selection.range) {
    const h = new Highlight(state.selection.range);
    h.priority = 2; // the green selection shows over amber marks
    CSS.highlights.set("docx-selection", h);
  }
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
    </div>`);
  }
  s.turns.forEach((t) => parts.push(...turnHtml(t)));
  if (pendingInstruction) {
    parts.push(userBubble(pendingInstruction.text, pendingInstruction.selection));
    parts.push(`<div class="msg agent"><span class="typing"><i></i><i></i><i></i></span><span class="working-text" id="elapsed">0.0s</span></div>`);
  }
  state.queue.forEach((q, n) => parts.push(userBubble(q.text, q.selection, n)));
  box.innerHTML = parts.join("");
  box.querySelectorAll("[data-answer]").forEach((b) => b.addEventListener("click", () => send(b.dataset.answer)));
  box.querySelectorAll("[data-version]").forEach((b) => b.addEventListener("click", () => viewVersion(Number(b.dataset.version))));
  box.querySelectorAll("[data-undo]").forEach((b) => b.addEventListener("click", undo));
  box.querySelectorAll("[data-unqueue]").forEach((b) => b.addEventListener("click", () => {
    state.queue.splice(Number(b.dataset.unqueue), 1);
    renderChat(state.pending);
  }));
  box.querySelectorAll("[data-more]").forEach((b) => b.addEventListener("click", () => {
    state.expanded.add(Number(b.dataset.more));
    renderChat();
  }));
  box.scrollTop = box.scrollHeight;
}

function userBubble(text, selection, queuedAt) {
  const quote = selection ? `<span class="quote"><b>Selection</b> · ${esc(selection.text.length > 140 ? selection.text.slice(0, 140) + "…" : selection.text)}</span>` : "";
  if (queuedAt === undefined) return `<div class="msg user">${quote}${esc(text)}</div>`;
  return `<div class="msg user queued">${quote}${esc(text)}<span class="queued-tag">Queued - sent when the current edit finishes<button type="button" class="queued-x" data-unqueue="${queuedAt}" title="Remove from the queue" aria-label="Remove from the queue">×</button></span></div>`;
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

/* ================================================================== markers */
// Marks are the user's own bookmarks in the preview: amber highlights that survive edits,
// undo and switching views (each is found again by its text, nearest to where it was), listed
// under "Marks" and shown as ticks on the rail - the document's scrollbar - to jump back to.
// They live in this browser only (localStorage) and never reach the .docx or the assistant.
const marksKey = (sid) => `docx-marks:${sid}`;
function loadMarks(sid) {
  try {
    const raw = JSON.parse(localStorage.getItem(marksKey(sid)) || "[]");
    return Array.isArray(raw) ? raw.filter((m) => m && typeof m.text === "string" && m.text) : [];
  } catch { return []; }
}
function saveMarks() {
  if (!state.session) return;
  try {
    localStorage.setItem(marksKey(state.session.id),
      JSON.stringify(state.marks.map(({ id, text, at }) => ({ id, text, at }))));
  } catch { /* private mode or storage full: marks just won't survive a reload */ }
}

// The preview's visible text as one string, with a map back to its text nodes. Struck-through
// (deleted) text and header/footer labels are left out, so a mark reads the same in both views.
function textIndex() {
  const walker = document.createTreeWalker($("paper"), NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement.closest("del, .hf-label, .page-hf, .page-num")
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  const nodes = [];
  let text = "";
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    nodes.push({ node: n, start: text.length });
    text += n.data;
  }
  return { text, nodes };
}
function offsetIn(idx, node, offset) {
  const hit = node.nodeType === Node.TEXT_NODE && idx.nodes.find((x) => x.node === node);
  if (hit) return hit.start + offset;
  for (const x of idx.nodes) { // a boundary between elements: the next indexed text
    const r = document.createRange();
    r.selectNodeContents(x.node);
    if (r.comparePoint(node, offset) <= 0) return x.start;
  }
  return idx.text.length;
}
function rangeAt(idx, start, end) {
  const find = (off, isEnd) => {
    let lo = 0, hi = idx.nodes.length - 1, k = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (idx.nodes[mid].start <= off) { k = mid; lo = mid + 1; } else hi = mid - 1;
    }
    let x = idx.nodes[k];
    while (isEnd && k > 0 && off === x.start) x = idx.nodes[--k]; // end at the previous node
    return [x.node, Math.max(0, Math.min(off - x.start, x.node.data.length))];
  };
  const r = document.createRange();
  r.setStart(...find(start, false));
  r.setEnd(...find(end, true));
  return r;
}

function resolveMarks() {
  if (!state.session) return;
  const idx = textIndex();
  for (const m of state.marks) {
    let best = -1;
    for (let i = idx.text.indexOf(m.text); i >= 0; i = idx.text.indexOf(m.text, i + 1)) {
      if (best < 0 || Math.abs(i - m.at) < Math.abs(best - m.at)) best = i;
    }
    m.range = best >= 0 ? rangeAt(idx, best, best + m.text.length) : null;
    m.lost = best < 0;
    if (best >= 0) m.at = best;
  }
  paintMarks();
  saveMarks();
  renderMarksMenu();
  renderRail();
}
function paintMarks() {
  if (!(window.CSS && CSS.highlights && window.Highlight)) return;
  const ranges = state.marks.filter((m) => m.range).map((m) => m.range);
  if (ranges.length) CSS.highlights.set("docx-mark", new Highlight(...ranges));
  else CSS.highlights.delete("docx-mark");
}
function addMark() {
  const sel = state.selection;
  if (!sel || !sel.range) return;
  const idx = textIndex();
  const start = offsetIn(idx, sel.range.startContainer, sel.range.startOffset);
  const end = offsetIn(idx, sel.range.endContainer, sel.range.endOffset);
  const text = idx.text.slice(start, end);
  clearSelection();
  if (!text.trim()) return toast("Select some text to mark.");
  if (state.marks.some((m) => m.text === text && m.at === start)) return toast("That text is already marked.");
  state.marks.push({ id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), text, at: start });
  state.marks.sort((a, b) => a.at - b.at);
  resolveMarks();
}
function removeMark(id) {
  state.marks = state.marks.filter((m) => m.id !== id);
  resolveMarks();
}
function jumpToMark(id) {
  const m = state.marks.find((x) => x.id === id);
  if (!m || !m.range) return;
  scrollPaperTo(m.range.getBoundingClientRect().top, 3);
  if (window.CSS && CSS.highlights && window.Highlight) {
    const h = new Highlight(m.range);
    h.priority = 1;
    CSS.highlights.set("docx-mark-active", h);
    clearTimeout(jumpToMark._t);
    jumpToMark._t = setTimeout(() => CSS.highlights.delete("docx-mark-active"), 1600);
  }
}
// Scroll the preview so a point (client y) sits 1/at of the way down. scrollIntoView is not
// used: some browsers ignore a smooth scrollIntoView inside this scroll container.
function scrollPaperTo(clientTop, at) {
  const wrap = $("paper-wrap");
  const top = clientTop - wrap.getBoundingClientRect().top;
  wrap.scrollTo({ top: wrap.scrollTop + top - wrap.clientHeight / at, behavior: "smooth" });
}
const snippet = (t) => { t = t.replace(/\s+/g, " ").trim(); return t.length > 110 ? t.slice(0, 110) + "…" : t; };
function renderMarksMenu() {
  const n = state.marks.length;
  $("marks-count").textContent = String(n);
  $("marks-count").hidden = n === 0;
  $("marks-pop").innerHTML = n
    ? `<div class="marks-head"><span>Marks</span><button type="button" class="link-btn" data-clear>Clear all</button></div>`
      + state.marks.map((m) => `<div class="mark-item${m.lost ? " lost" : ""}">
          <button type="button" class="mark-go" data-go="${esc(m.id)}"${m.lost ? " disabled" : ""}>${esc(snippet(m.text))}${m.lost ? '<span class="lost-note">Not in this version</span>' : ""}</button>
          <button type="button" class="mark-del" data-del="${esc(m.id)}" title="Remove mark" aria-label="Remove mark">×</button>
        </div>`).join("")
    : `<p class="marks-empty">Select text in the document and click <b>Mark</b>. Marks show as amber ticks on the bar beside the document; click one to jump back.</p>`;
}
function placeMarkPill() {
  const pill = $("mark-pill");
  const sel = state.selection;
  if (!sel || !sel.range) { pill.hidden = true; return; }
  const rect = sel.range.getBoundingClientRect();
  const box = $("paper-wrap").getBoundingClientRect();
  if (rect.bottom < box.top || rect.top > box.bottom || !rect.width) { pill.hidden = true; return; }
  pill.hidden = false;
  const top = rect.top - 36 > box.top ? rect.top - 36 : Math.min(rect.bottom + 8, box.bottom - 36);
  const left = Math.max(box.left + 8, Math.min(rect.left, box.right - pill.offsetWidth - 8));
  pill.style.top = `${Math.round(top)}px`;
  pill.style.left = `${Math.round(left)}px`;
}

/* --------------------------------------------------------------------- rail */
const CHANGE_SEL = "ins, del, .fmt-changed, .block-ins, .block-del, .block-moved, .block-fmt, tr.row-ins, tr.row-del, tr.row-moved, .tbl-ins, .tbl-moved, .tbl-del";
function renderRail() {
  const wrap = $("paper-wrap"), rail = $("rail");
  const H = wrap.scrollHeight, h = rail.clientHeight;
  if (!state.session || !H || !h) return;
  const origin = wrap.getBoundingClientRect().top - wrap.scrollTop;
  const y = (top) => Math.round(Math.max(0, Math.min(h - 4, ((top - origin) / H) * h)));
  const out = [];
  if (!$("paper").classList.contains("clean")) {
    const seen = new Set();
    $("paper").querySelectorAll(CHANGE_SEL).forEach((el) => {
      if (el.closest(".page-hf-repeat")) return; // a header/footer change: tick its first page only
      const kind = el.matches("del, .block-del, .row-del, .tbl-del") ? "del"
        : el.matches(".fmt-changed, .block-fmt") ? "fmt"
        : el.matches(".block-moved, .row-moved, .tbl-moved") ? "moved" : "ins";
      const top = y(el.getBoundingClientRect().top);
      if (seen.has(kind + top)) return;
      seen.add(kind + top);
      out.push(`<i class="tick change ${kind}" style="top:${top}px"></i>`);
    });
  }
  for (const m of state.marks) {
    if (!m.range) continue;
    out.push(`<button type="button" class="tick mark" style="top:${y(m.range.getBoundingClientRect().top)}px" data-mark="${esc(m.id)}" title="${esc(snippet(m.text))}" aria-label="Jump to mark"></button>`);
  }
  $("rail-ticks").innerHTML = out.join("");
  updateThumb();
}
function updateThumb() {
  const wrap = $("paper-wrap"), thumb = $("rail-thumb");
  const H = wrap.scrollHeight, h = $("rail").clientHeight;
  thumb.hidden = !H || H <= wrap.clientHeight + 1;
  if (thumb.hidden) return;
  thumb.style.height = `${Math.max(28, (wrap.clientHeight / H) * h)}px`;
  thumb.style.transform = `translateY(${(wrap.scrollTop / H) * h}px)`;
}
let railDrag = null;
$("rail").addEventListener("pointerdown", (e) => {
  if (e.target.closest(".tick.mark") || e.button !== 0) return;
  const wrap = $("paper-wrap"), rail = $("rail");
  const H = wrap.scrollHeight, h = rail.clientHeight;
  if (e.target !== $("rail-thumb")) { // click on the track: centre the view there
    const y = e.clientY - rail.getBoundingClientRect().top;
    wrap.scrollTop = (y / h) * H - wrap.clientHeight / 2;
  }
  railDrag = { y: e.clientY, top: wrap.scrollTop, ratio: H / h };
  rail.setPointerCapture(e.pointerId);
  rail.classList.add("dragging");
  e.preventDefault();
});
$("rail").addEventListener("pointermove", (e) => {
  if (railDrag) $("paper-wrap").scrollTop = railDrag.top + (e.clientY - railDrag.y) * railDrag.ratio;
});
["pointerup", "pointercancel"].forEach((ev) => $("rail").addEventListener(ev, () => {
  railDrag = null;
  $("rail").classList.remove("dragging");
}));
$("rail").addEventListener("click", (e) => {
  const tick = e.target.closest(".tick.mark");
  if (tick) jumpToMark(tick.dataset.mark);
});
let railFrame = 0;
$("paper-wrap").addEventListener("scroll", () => {
  cancelAnimationFrame(railFrame);
  railFrame = requestAnimationFrame(() => { updateThumb(); placeMarkPill(); });
});
let railTimer = null;
const railSoon = () => { clearTimeout(railTimer); railTimer = setTimeout(renderRail, 120); };
window.addEventListener("resize", () => { fitPages(); railSoon(); placeMarkPill(); });
if (window.ResizeObserver) new ResizeObserver(railSoon).observe($("paper")); // images, fonts

/* -------------------------------------------------------------- mark events */
$("mark-pill").addEventListener("mousedown", (e) => e.preventDefault()); // keep the selection
$("mark-pill").addEventListener("click", addMark);
$("sel-mark").addEventListener("click", addMark);
$("marks-btn").addEventListener("click", () => {
  const pop = $("marks-pop");
  pop.hidden = !pop.hidden;
  $("marks-btn").setAttribute("aria-expanded", String(!pop.hidden));
});
$("marks-pop").addEventListener("click", (e) => {
  const go = e.target.closest("[data-go]"), del = e.target.closest("[data-del]");
  if (go) { jumpToMark(go.dataset.go); $("marks-pop").hidden = true; }
  else if (del) removeMark(del.dataset.del);
  else if (e.target.closest("[data-clear]")) { state.marks = []; resolveMarks(); }
});
document.addEventListener("click", (e) => {
  if (!$("marks-pop").hidden && !$("marks-menu").contains(e.target)) $("marks-pop").hidden = true;
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") $("marks-pop").hidden = true;
});

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
    : state.busy ? "Type your next message - it is sent when this edit finishes…"
    : asked ? "Reply to the assistant…" : "Describe the change…";
  // the box stays usable while the agent works: Enter queues the message
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
  if (!text || !state.session) return;
  const selection = selectionPayload();
  $("instruction").value = "";
  autoGrow();
  if (state.busy) { // queue it: it runs on the version the current edit produces
    state.queue.push({ text, selection });
    clearSelection();
    renderChat(state.pending);
    $("messages").scrollTop = $("messages").scrollHeight;
    return;
  }
  await run(text, selection);
}

async function run(text, selection) {
  state.pending = { text, selection };
  setBusy(true, state.pending);
  try {
    const res = await post(`/api/sessions/${state.session.id}/edit`, { instruction: text, selection });
    // after an edit, show the real pages (with the change highlighted) when we have them
    if (res.turn.status === "done") state.view = state.exact ? "clean" : "redline";
    state.busy = false;
    clearSelection();
    showSession(res.session);
    if (res.turn.status === "done") scrollToFirstChange();
  } catch (e) {
    toast(e.message);
    if (!$("instruction").value && !state.queue.length) $("instruction").value = text;
  } finally {
    state.pending = null;
    setBusy(false);
  }
  const next = state.queue.shift();
  if (next && state.session) await run(next.text, next.selection);
  else if (state.session) renderChat();
}

async function undo() {
  try {
    showSession(await post(`/api/sessions/${state.session.id}/undo`));
    toast("Last edit undone.");
  } catch (e) { toast(e.message); }
}

async function scrollToFirstChange() {
  await state.layout; // the pages must be laid out before we know where the change is
  if ($("paper").classList.contains("exact")) {
    const r = state.exactChanges && state.exactChanges[0];
    if (r) scrollPaperTo(r.getBoundingClientRect().top, 2);
    return;
  }
  const first = $("paper").querySelector(CHANGE_SEL);
  if (first) scrollPaperTo(first.getBoundingClientRect().top, 2);
}

// On the real pages, highlight the paragraphs the last edit changed. They are found by text:
// the redline knows which paragraphs changed; their new text is looked up on the pages
// (ignoring spaces, which the PDF text layer splits differently).
function paintExactChanges() {
  state.exactChanges = [];
  if (window.CSS && CSS.highlights) CSS.highlights.delete("docx-change");
  const s = state.session;
  if (!s.redline_html || !(window.CSS && CSS.highlights && window.Highlight)) return;
  const tmp = document.createElement("div");
  tmp.innerHTML = s.redline_html;
  const changed = [...tmp.querySelectorAll(".para")].filter((p) =>
    p.matches(".block-ins, .block-moved, .block-fmt") || p.querySelector(":scope > ins, :scope > .fmt-changed, ins, .fmt-changed"));
  const idx = textIndex();
  const map = [];
  let compact = "";
  for (let i = 0; i < idx.text.length; i++) {
    if (!/\s/.test(idx.text[i])) { map.push(i); compact += idx.text[i]; }
  }
  let from = 0;
  for (const p of changed) {
    p.querySelectorAll("del, .num-label").forEach((d) => d.remove());
    const needle = p.textContent.replace(/\s+/g, "");
    if (needle.length < 2) continue;
    let k = compact.indexOf(needle, from);
    if (k < 0) k = compact.indexOf(needle);
    if (k < 0) continue;
    from = k + needle.length;
    state.exactChanges.push(rangeAt(idx, map[k], map[k + needle.length - 1] + 1));
  }
  if (state.exactChanges.length) CSS.highlights.set("docx-change", new Highlight(...state.exactChanges));
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
  steadyExactSelection();
  clearTimeout(selTimer);
  selTimer = setTimeout(captureSelection, 120);
});
document.addEventListener("mouseup", () => setTimeout(captureSelection, 0));
document.addEventListener("click", (e) => {
  if (!state.selection || $("chat").contains(e.target)) return; // typing in the chat keeps it
  if ($("rail").contains(e.target) || $("marks-menu").contains(e.target)) return; // just scrolling
  const wrap = $("paper-wrap");
  if (e.target === wrap && e.offsetX >= wrap.clientWidth) return; // dragging the scrollbar
  const sel = window.getSelection();
  if (sel && !sel.isCollapsed && $("paper").contains(sel.anchorNode)) return; // a new selection
  clearSelection();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && state.selection) clearSelection();
});
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
