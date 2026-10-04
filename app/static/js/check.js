/* Check a Message.
 *
 * One form, four modes (text / link / image / pdf), one endpoint:
 *   POST /api/check (multipart)  ->  { id, stored, html, row_html, text, kind_label, scan_count }
 *   GET  /api/check/<id>         ->  { html, text, kind_label }   (reopen a past check)
 *   POST /api/check/<id>/journal ->  { saved }
 * The result card HTML is rendered (and translated) by the server.
 * Interface strings come from #check-strings.
 */
(function () {
  "use strict";

  const root = document.getElementById("check-root");
  if (!root) return;

  const $ = (id) => document.getElementById(id);
  const CSRF = (window.NIRVAAN && window.NIRVAAN.csrf) || "";
  const OCR = root.dataset.ocr === "1";
  const MAX_BYTES = (parseInt(root.dataset.maxMb, 10) || 10) * 1024 * 1024;
  const S = {};
  document.querySelectorAll("#check-strings [data-k]").forEach((el) => {
    S[el.dataset.k] = el.textContent.trim();
  });

  const form = $("check-form");
  const slot = $("result-slot");
  const errorBox = $("check-error");
  const analyseBtn = $("btn-analyse");
  const listenBtn = $("btn-audio-guide");
  let mode = "text";
  const files = { image: null, pdf: null };
  let busy = false;

  // ------------------------------------------------------------------ modes
  const ACTIVE = "tab-btn flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-on-primary font-label-md text-label-md shadow-sm transition-all";
  const IDLE = "tab-btn flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl text-on-surface-variant hover:bg-surface-container font-label-md text-label-md transition-all";

  function setMode(next) {
    mode = next;
    document.querySelectorAll("#input-tabs .tab-btn").forEach((b) => {
      const on = b.dataset.type === next;
      b.className = on ? ACTIVE : IDLE;
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll("[data-mode-panel]").forEach((p) => {
      p.hidden = p.dataset.modePanel !== next;
    });
    hideError();
  }
  document.querySelectorAll("#input-tabs .tab-btn").forEach((b) => {
    b.addEventListener("click", () => setMode(b.dataset.type));
  });

  // ------------------------------------------------------------------ errors
  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove("hidden");
  }
  function hideError() {
    errorBox.textContent = "";
    errorBox.classList.add("hidden");
  }

  // ------------------------------------------------------------------ text counter
  const textArea = $("check-text");
  const counter = $("text-count");
  textArea.addEventListener("input", () => { counter.textContent = String(textArea.value.length); });

  // ------------------------------------------------------------------ files
  const fmtSize = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB");
  const IMAGE_OK = ["image/jpeg", "image/png", "image/webp"];

  function acceptFile(kind, file) {
    hideError();
    if (!file) return;
    if (kind === "image" && IMAGE_OK.indexOf(file.type) === -1) { showError(S.wrong_image); return; }
    if (kind === "pdf" && !(file.type === "application/pdf" || /\.pdf$/i.test(file.name))) { showError(S.wrong_pdf); return; }
    if (file.size > MAX_BYTES) { showError(S.too_big); return; }
    files[kind] = file;
    const drop = $(kind + "-drop");
    const preview = $(kind + "-preview");
    $(kind + "-name").textContent = file.name;
    $(kind + "-size").textContent = fmtSize(file.size);
    if (kind === "image") {
      // data: URL (the page CSP allows data: images, not blob:).
      const reader = new FileReader();
      reader.onload = () => { $("image-preview-img").src = reader.result; };
      reader.readAsDataURL(file);
    }
    drop.classList.add("hidden");
    preview.classList.remove("hidden");
    preview.classList.add("flex");
  }

  function removeFile(kind) {
    files[kind] = null;
    const input = $(kind + "-input");
    input.value = "";
    if (kind === "image") $("image-preview-img").removeAttribute("src");
    $(kind + "-preview").classList.add("hidden");
    $(kind + "-preview").classList.remove("flex");
    $(kind + "-drop").classList.remove("hidden");
  }

  ["image", "pdf"].forEach((kind) => {
    const input = $(kind + "-input");
    const drop = $(kind + "-drop");
    input.addEventListener("change", () => acceptFile(kind, input.files && input.files[0]));
    drop.addEventListener("click", () => input.click());
    drop.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
    });
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.add("bg-surface-container-high");
    }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.remove("bg-surface-container-high");
    }));
    drop.addEventListener("drop", (e) => {
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      acceptFile(kind, f);
    });
  });
  document.querySelectorAll("[data-replace]").forEach((b) => b.addEventListener("click", () => $(b.dataset.replace + "-input").click()));
  document.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", () => removeFile(b.dataset.remove)));

  // ------------------------------------------------------------------ link validation
  function linkProblem(raw) {
    const v = raw.trim();
    if (!v || /\s/.test(v)) return S.bad_url;
    const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(v) ? v : "https://" + v;
    try {
      const u = new URL(withScheme);
      if (u.protocol !== "http:" && u.protocol !== "https:") return S.bad_url;
      if (!u.hostname || u.hostname.indexOf(".") === -1) return S.bad_url;
    } catch (e) {
      return S.bad_url;
    }
    return null;
  }

  // ------------------------------------------------------------------ review bubble
  function showReview(kindLabel, text) {
    $("review-kind").textContent = kindLabel || "";
    $("review-text").textContent = text || "";
    $("review-filled").classList.remove("hidden");
    $("review-empty").classList.add("hidden");
  }
  function clearReview() {
    $("review-filled").classList.add("hidden");
    $("review-empty").classList.remove("hidden");
  }

  // ------------------------------------------------------------------ result card
  let emptyHtml = slot.innerHTML;

  function mountResult(html) {
    slot.innerHTML = html;
    if ("speechSynthesis" in window) listenBtn.disabled = false;
  }

  slot.addEventListener("click", async (e) => {
    const tab = e.target.closest(".analysis-tab-btn");
    if (tab) {
      const card = tab.closest("[data-result]");
      card.querySelectorAll(".analysis-tab-btn").forEach((b) => {
        const on = b === tab;
        b.setAttribute("aria-selected", on ? "true" : "false");
        b.classList.toggle("bg-surface-container-lowest", on);
        b.classList.toggle("text-primary", on);
        b.classList.toggle("shadow-xs", on);
        b.classList.toggle("text-on-surface-variant", !on);
      });
      card.querySelectorAll("[data-tab-panel]").forEach((p) => {
        const on = p.dataset.tabPanel === tab.dataset.tab;
        p.classList.toggle("hidden", !on);
        p.classList.toggle("flex", on);
      });
      return;
    }
    const action = e.target.closest("[data-action]");
    if (!action) return;
    const card = action.closest("[data-result]");
    if (action.dataset.action === "explain") {
      const panel = card.querySelector("[data-simple-panel]");
      const open = panel.classList.toggle("hidden") === false;
      action.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else if (action.dataset.action === "journal") {
      const id = card.dataset.analysisId;
      const msg = card.querySelector("[data-journal-msg]");
      if (!id) return;
      action.disabled = true;
      try {
        const res = await fetch("/api/check/" + encodeURIComponent(id) + "/journal", {
          method: "POST",
          headers: { "X-CSRF-Token": CSRF, Accept: "application/json" },
          credentials: "same-origin",
        });
        if (!res.ok) throw new Error(String(res.status));
        msg.textContent = S.journal_saved;
        action.querySelector("span:last-child").textContent = S.saved;
      } catch (err) {
        msg.textContent = S.journal_failed;
        action.disabled = false;
      }
      msg.classList.remove("hidden");
    }
  });

  // ------------------------------------------------------------------ submit
  function setBusy(on) {
    busy = on;
    analyseBtn.disabled = on;
    analyseBtn.setAttribute("aria-busy", on ? "true" : "false");
    $("btn-analyse-label").textContent = on ? S.analysing : S.analyse;
    $("btn-analyse-icon").textContent = on ? "progress_activity" : "bolt";
    $("btn-analyse-icon").classList.toggle("animate-spin", on);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (busy) return;
    hideError();
    const fd = new FormData();
    fd.append("mode", mode);
    if (mode === "text") {
      const v = textArea.value.trim();
      if (!v) { showError(S.empty_text); textArea.focus(); return; }
      fd.append("text", v);
    } else if (mode === "link") {
      const v = $("check-url").value.trim();
      const problem = linkProblem(v);
      if (problem) { showError(problem); $("check-url").focus(); return; }
      fd.append("url", v);
    } else if (mode === "image") {
      if (!files.image) { showError(S.no_file); return; }
      const typed = $("image-typed").value.trim();
      if (!OCR && !typed) { showError(S.need_typed); $("image-typed").focus(); return; }
      fd.append("file", files.image, files.image.name);
      fd.append("typed_text", typed);
    } else if (mode === "pdf") {
      if (!files.pdf) { showError(S.no_file); return; }
      fd.append("file", files.pdf, files.pdf.name);
    }

    setBusy(true);
    let res;
    let body = null;
    try {
      res = await fetch("/api/check", {
        method: "POST",
        headers: { "X-CSRF-Token": CSRF, Accept: "application/json" },
        credentials: "same-origin",
        body: fd,
      });
      body = await res.json().catch(() => null);
    } catch (err) {
      setBusy(false);
      showError(S.network);
      return;
    }
    setBusy(false);
    if (!res.ok || !body || !body.html) {
      const code = body && body.code;
      showError((code && S[code]) || (body && typeof body.detail === "string" && body.detail) || S.server);
      return;
    }
    mountResult(body.html);
    showReview(body.kind_label, body.text);
    if (body.row_html) {
      const list = $("past-list");
      list.insertAdjacentHTML("afterbegin", body.row_html);
      $("past-empty").classList.add("hidden");
      $("past-count").textContent = String(list.children.length);
    }
    if (typeof body.scan_count === "number") $("scan-count").textContent = String(body.scan_count);
    if (window.matchMedia("(max-width: 1023px)").matches) slot.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  // ------------------------------------------------------------------ clear
  $("btn-clear").addEventListener("click", () => {
    textArea.value = "";
    counter.textContent = "0";
    $("check-url").value = "";
    $("image-typed").value = "";
    removeFile("image");
    removeFile("pdf");
    hideError();
    clearReview();
    slot.innerHTML = emptyHtml;
    listenBtn.disabled = true;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  });

  // ------------------------------------------------------------------ past checks
  $("past-list").addEventListener("click", async (e) => {
    const row = e.target.closest("[data-open-check]");
    if (!row) return;
    hideError();
    row.setAttribute("aria-busy", "true");
    try {
      const res = await fetch("/api/check/" + encodeURIComponent(row.dataset.openCheck), {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const body = await res.json();
      if (!res.ok || !body.html) throw new Error("load");
      mountResult(body.html);
      showReview(body.kind_label, body.text);
      slot.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showError(S.load_failed);
    } finally {
      row.removeAttribute("aria-busy");
    }
  });

  // ------------------------------------------------------------------ listen
  const LANG = (document.documentElement.getAttribute("lang") || "en").slice(0, 2);
  const BCP47 = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" }[LANG] || "en-IN";
  if (!("speechSynthesis" in window)) {
    listenBtn.title = S.no_voice;
  }
  listenBtn.addEventListener("click", () => {
    if (!("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;
    if (synth.speaking) { synth.cancel(); return; }
    const card = slot.querySelector("[data-result]");
    if (!card) return;
    const parts = Array.from(card.querySelectorAll("[data-speak]")).map((el) => el.textContent.trim()).filter(Boolean);
    const u = new SpeechSynthesisUtterance(parts.join(". "));
    u.lang = BCP47;
    u.rate = 0.95;
    synth.speak(u);
  });
})();
