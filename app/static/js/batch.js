/* Batch Analysis.
 *
 * Create:   POST /api/batch (multipart: label, messages, links, files[], file_texts[])
 * Progress: GET  /api/batch/{id} every ~1.5 s while the job is queued/processing;
 *           the response carries the re-rendered results region (`html`).
 * Switch:   the "Your Batches" list loads another job through the same endpoint.
 * Journal:  POST /api/batch/{id}/journal once a job has finished.
 *
 * Interface strings come from #batch-strings, rendered in the page language.
 */
(function () {
  "use strict";

  const results = document.getElementById("batch-results");
  const form = document.getElementById("new-batch");
  if (!results || !form) return;

  const $ = (id) => document.getElementById(id);
  const CSRF = (window.NIRVAAN && window.NIRVAAN.csrf) || "";
  const MAX_ITEMS = parseInt(form.dataset.maxItems, 10) || 20;
  const MAX_BYTES = parseInt(form.dataset.maxBytes, 10) || 10 * 1024 * 1024;
  const POLL_MS = 1500;
  const SEPARATOR = /^[ \t]*-{3,}[ \t]*$/m;
  const FILE_OK = /^(image\/(jpeg|png|webp)|application\/pdf)$/;

  const S = {};
  document.querySelectorAll("#batch-strings [data-k]").forEach((el) => {
    S[el.dataset.k] = el.textContent.trim();
  });

  // ------------------------------------------------------------ results region
  let filter = "all";
  let pollTimer = null;
  let currentJob = results.dataset.jobId || "";

  function applyFilter() {
    const tabs = { all: $("filter-all"), flagged: $("filter-flagged"), clean: $("filter-clean") };
    Object.keys(tabs).forEach((key) => {
      const btn = tabs[key];
      if (!btn) return;
      const on = key === filter;
      btn.classList.toggle("bg-surface-container-lowest", on);
      btn.classList.toggle("text-primary", on);
      btn.classList.toggle("font-bold", on);
      btn.classList.toggle("shadow-sm", on);
      btn.classList.toggle("text-on-surface-variant", !on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
    results.querySelectorAll(".batch-card").forEach((card) => {
      card.classList.toggle("hidden", filter !== "all" && card.dataset.category !== filter);
    });
  }

  results.addEventListener("click", (event) => {
    const tab = event.target.closest(".filter-tab");
    if (tab) {
      filter = { "filter-flagged": "flagged", "filter-clean": "clean" }[tab.id] || "all";
      applyFilter();
      return;
    }
    const journal = event.target.closest("#btn-save-journal");
    if (journal && !journal.disabled && journal.dataset.jobId) saveJournal(journal);
  });

  function markSelected(jobId) {
    document.querySelectorAll(".batch-job").forEach((btn) => {
      const on = btn.dataset.jobId === jobId;
      btn.classList.toggle("bg-surface-container-low", on);
      btn.classList.toggle("ring-1", on);
      btn.classList.toggle("ring-primary/30", on);
      if (on) btn.setAttribute("aria-current", "true");
      else btn.removeAttribute("aria-current");
    });
  }

  function stopPolling() {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null;
  }

  async function loadJob(jobId, { poll = true } = {}) {
    stopPolling();
    currentJob = jobId;
    let data;
    try {
      const res = await fetch("/api/batch/" + encodeURIComponent(jobId), {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (res.status === 404) {
        showError(S.not_found);
        return;
      }
      if (!res.ok) throw new Error(String(res.status));
      data = await res.json();
    } catch (e) {
      // Keep trying quietly while a job is running; a blip should not end the progress view.
      if (poll && jobId === currentJob) pollTimer = setTimeout(() => loadJob(jobId), POLL_MS * 2);
      return;
    }
    if (jobId !== currentJob) return; // the user switched to another batch meanwhile
    results.innerHTML = data.html;
    results.dataset.jobId = data.id;
    results.dataset.running = data.running ? "1" : "0";
    applyFilter();
    markSelected(data.id);
    updateListStatus(data.id, data.status);
    if (data.running && poll) pollTimer = setTimeout(() => loadJob(jobId), POLL_MS);
  }

  function updateListStatus(jobId, status) {
    const btn = document.querySelector('.batch-job[data-job-id="' + jobId + '"]');
    if (!btn) return;
    const pill = btn.querySelector("span.flex-shrink-0");
    if (pill && status) pill.textContent = status.charAt(0) + status.slice(1).toLowerCase();
  }

  document.querySelectorAll(".batch-job").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.jobId;
      try {
        const url = new URL(window.location.href);
        url.searchParams.set("job", id);
        window.history.replaceState(null, "", url);
      } catch (e) { /* ignore */ }
      loadJob(id);
      results.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  async function saveJournal(btn) {
    const label = btn.querySelector("span:last-child");
    const original = label ? label.textContent : "";
    btn.disabled = true;
    if (label) label.textContent = S.saving;
    try {
      const res = await fetch("/api/batch/" + encodeURIComponent(btn.dataset.jobId) + "/journal", {
        method: "POST",
        headers: { "X-CSRF-Token": CSRF, Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error(String(res.status));
      if (label) label.textContent = S.saved;
      btn.classList.add("opacity-80");
      // Stays disabled: the summary is saved; a second click would only duplicate it.
    } catch (e) {
      if (label) label.textContent = S.save_failed;
      setTimeout(() => {
        if (label) label.textContent = original;
        btn.disabled = false;
      }, 2500);
    }
  }

  // ------------------------------------------------------------ the form
  const messagesEl = $("batch-messages");
  const linksEl = $("batch-links");
  const fileInput = $("batch-files");
  const fileList = $("batch-file-list");
  const countEl = $("batch-count");
  const errorEl = $("batch-error");
  const submitBtn = $("batch-submit");
  const OCR = fileList.dataset.ocr === "1";
  let picked = []; // [{file, text}]

  function splitMessages() {
    return messagesEl.value.split(SEPARATOR).map((s) => s.trim()).filter(Boolean);
  }
  function splitLinks() {
    return linksEl.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  }
  function itemCount() {
    return splitMessages().length + splitLinks().length + picked.length;
  }
  function updateCount() {
    const n = itemCount();
    countEl.textContent = String(n);
    countEl.classList.toggle("text-error", n > MAX_ITEMS);
  }
  function showError(message) {
    errorEl.textContent = message || "";
    errorEl.classList.toggle("hidden", !message);
  }

  const isPdf = (f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name);

  function renderFiles() {
    fileList.textContent = "";
    picked.forEach((entry, index) => {
      const li = document.createElement("li");
      li.className = "rounded-xl bg-surface-container-low p-3 space-y-2 min-w-0";
      const row = document.createElement("div");
      row.className = "flex items-center justify-between gap-2 min-w-0";
      const name = document.createElement("span");
      name.className = "flex items-center gap-2 min-w-0 font-label-md text-label-md text-on-surface";
      const icon = document.createElement("span");
      icon.className = "material-symbols-outlined text-[18px] text-primary flex-shrink-0";
      icon.textContent = isPdf(entry.file) ? "picture_as_pdf" : "image";
      const text = document.createElement("span");
      text.className = "truncate";
      text.textContent = entry.file.name;
      name.append(icon, text);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "flex-shrink-0 px-3 py-1 rounded-full text-on-surface-variant hover:bg-surface-container font-label-sm text-label-sm";
      remove.textContent = S.remove;
      remove.addEventListener("click", () => {
        picked.splice(index, 1);
        renderFiles();
        updateCount();
      });
      row.append(name, remove);
      li.append(row);
      if (!isPdf(entry.file)) {
        const id = "batch-typed-" + index;
        const label = document.createElement("label");
        label.className = "block font-body-sm text-body-sm text-on-surface-variant";
        label.htmlFor = id;
        label.textContent = OCR ? S.typed_optional : S.typed_label;
        const area = document.createElement("textarea");
        area.id = id;
        area.rows = 2;
        area.className = "w-full rounded-xl bg-surface-container-lowest border-0 focus:ring-2 focus:ring-primary px-3 py-2 font-body-sm text-body-sm text-on-surface";
        area.value = entry.text;
        area.addEventListener("input", () => { entry.text = area.value; });
        li.append(label, area);
      }
      fileList.append(li);
    });
  }

  fileInput.addEventListener("change", () => {
    showError("");
    const problems = [];
    Array.from(fileInput.files || []).forEach((file) => {
      if (!FILE_OK.test(file.type) && !/\.(pdf|jpe?g|png|webp)$/i.test(file.name)) {
        problems.push(file.name + ": " + S.bad_type);
      } else if (file.size > MAX_BYTES) {
        problems.push(file.name + ": " + S.too_big);
      } else {
        picked.push({ file, text: "" });
      }
    });
    fileInput.value = "";
    renderFiles();
    updateCount();
    if (problems.length) showError(problems.join(" "));
  });

  messagesEl.addEventListener("input", updateCount);
  linksEl.addEventListener("input", updateCount);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError("");
    const n = itemCount();
    if (n === 0) return showError(S.empty);
    if (n > MAX_ITEMS) return showError(S.too_many);
    if (!OCR && picked.some((p) => !isPdf(p.file) && !p.text.trim())) return showError(S.need_typed);

    const body = new FormData();
    body.append("label", $("batch-label").value);
    body.append("messages", messagesEl.value);
    body.append("links", linksEl.value);
    picked.forEach((p) => {
      body.append("files", p.file, p.file.name);
      body.append("file_texts", p.text);
    });

    const label = submitBtn.querySelector("span:last-child");
    const original = label.textContent;
    submitBtn.disabled = true;
    label.textContent = S.submitting;
    try {
      const res = await fetch("/api/batch", {
        method: "POST",
        headers: { "X-CSRF-Token": CSRF, Accept: "application/json" },
        credentials: "same-origin",
        body,
      });
      let data = {};
      try { data = await res.json(); } catch (e) { /* non-JSON error page */ }
      if (!res.ok) {
        showError(data.detail || S.failed);
        return;
      }
      // Full load so "Your Batches" includes the new job; the page then polls it.
      window.location.assign("/batch?job=" + encodeURIComponent(data.id));
      return;
    } catch (e) {
      showError(S.network);
    } finally {
      submitBtn.disabled = false;
      label.textContent = original;
    }
  });

  // ------------------------------------------------------------ start up
  applyFilter();
  updateCount();
  let wanted = "";
  try { wanted = new URL(window.location.href).searchParams.get("job") || ""; } catch (e) { /* ignore */ }
  if (wanted && wanted !== results.dataset.jobId) {
    loadJob(wanted);
  } else if (results.dataset.running === "1" && currentJob) {
    pollTimer = setTimeout(() => loadJob(currentJob), POLL_MS);
  }
})();
