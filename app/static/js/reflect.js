/* Pause & Reflect: five-step flow, entirely client-side until "Complete".
 *
 * Answers live in memory and in sessionStorage (per user) so a refresh keeps
 * them. Completing POSTs them to /api/reflect/complete, which stores a real
 * ReflectionSession + ReflectionAnswer rows and returns the descriptive labels.
 * Visible strings come from #reflect-strings (translated server-side) or from
 * the option/question elements already on the page.
 */
(function () {
  "use strict";

  const root = document.getElementById("reflect-root");
  const form = document.getElementById("reflect-form");
  if (!root || !form) return;

  const STEPS = 5;
  const KEY = "nirvaan.reflect.v1." + (root.dataset.user || "anon");
  const S = {};
  document.querySelectorAll("#reflect-strings [data-k]").forEach((el) => {
    S[el.dataset.k] = el.textContent.trim();
  });

  // Required answers per step, in the order they are checked.
  const REQUIRED = {
    1: ["reason"],
    2: ["evidence", "understanding"],
    3: ["deadline", "commitment", "essentials"],
    4: ["emotions", "counterfactual"],
    5: [],
  };
  const MULTI = { evidence: true, emotions: true };
  const TEXT_FIELDS = ["reason_text", "analysis_id", "change_mind", "note", "save_journal"];

  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));

  /* --- state ------------------------------------------------------------ */

  function fresh() {
    return { step: 1, maxStep: 1, startedAt: Date.now(), answers: {} };
  }

  function load() {
    try {
      const raw = sessionStorage.getItem(KEY);
      if (raw) {
        const s = JSON.parse(raw);
        if (s && typeof s === "object" && s.answers) return s;
      }
    } catch (err) {
      /* storage blocked: the flow still works in memory */
    }
    return fresh();
  }

  function persist() {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(state));
    } catch (err) {
      /* ignore */
    }
  }

  function clearStored() {
    try {
      sessionStorage.removeItem(KEY);
    } catch (err) {
      /* ignore */
    }
  }

  let state = load();
  const initialObs = {
    chip: (document.getElementById("observation-chip") || {}).textContent || "",
    text: (document.getElementById("observation-text") || {}).textContent || "",
  };

  /* --- option buttons --------------------------------------------------- */

  function paintOption(btn, on) {
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.classList.toggle("bg-surface", !on);
    btn.classList.toggle("bg-surface-container-high", on);
    btn.classList.toggle("ring-2", on);
    btn.classList.toggle("ring-primary", on);
    const circle = $(".check-circle", btn);
    const dot = $(".dot", btn);
    const title = $(".opt-title", btn);
    if (circle) {
      circle.classList.toggle("bg-primary", on);
      circle.classList.toggle("bg-surface-container-high", !on);
    }
    if (dot) {
      dot.classList.toggle("bg-on-primary", on);
      dot.classList.toggle("bg-transparent", !on);
    }
    if (title) {
      title.classList.toggle("text-primary", on);
      title.classList.toggle("font-bold", on);
      title.classList.toggle("text-on-surface", !on);
    }
  }

  function selected(name) {
    const v = state.answers[name];
    if (MULTI[name]) return Array.isArray(v) ? v : [];
    return v ? [v] : [];
  }

  function paintAll() {
    $$(".reflect-opt").forEach((btn) => {
      paintOption(btn, selected(btn.dataset.name).includes(btn.dataset.value));
    });
    TEXT_FIELDS.forEach((name) => {
      const el = form.elements[name];
      if (!el) return;
      if (el.type === "checkbox") el.checked = !!state.answers[name];
      else el.value = state.answers[name] || "";
    });
    // A linked check that is no longer listed (e.g. deleted) is dropped.
    const sel = form.elements.analysis_id;
    if (sel && sel.value !== (state.answers.analysis_id || "")) state.answers.analysis_id = "";
    updateObservation();
  }

  $$(".reflect-opt").forEach((btn) => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.name;
      const value = btn.dataset.value;
      if (MULTI[name]) {
        let list = selected(name).slice();
        if (list.includes(value)) {
          list = list.filter((v) => v !== value);
        } else if (btn.hasAttribute("data-exclusive")) {
          list = [value];
        } else {
          const exclusive = $$(`.reflect-opt[data-name="${name}"][data-exclusive]`).map((b) => b.dataset.value);
          list = list.filter((v) => !exclusive.includes(v)).concat(value);
        }
        state.answers[name] = list;
      } else {
        state.answers[name] = value;
      }
      paintAll();
      hideError();
      persist();
    });
  });

  TEXT_FIELDS.forEach((name) => {
    const el = form.elements[name];
    if (!el) return;
    const evt = el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input";
    el.addEventListener(evt, () => {
      state.answers[name] = el.type === "checkbox" ? el.checked : el.value;
      persist();
    });
  });

  $$(".reflect-suggest").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = form.elements.change_mind;
      const text = $("[data-suggest]", btn).textContent.trim();
      const current = input.value.trim();
      if (current.split(/;\s*/).includes(text)) return;
      input.value = current ? current + "; " + text : text;
      state.answers.change_mind = input.value.slice(0, 400);
      persist();
    });
  });

  function updateObservation() {
    const reason = state.answers.reason;
    const text = $("#observation-text");
    const chip = $("#observation-chip");
    if (!reason || !text || !S["obs_" + reason]) return;
    text.textContent = S["obs_" + reason];
    chip.textContent = reason === "researched" ? S.obs_chip_calm : S.obs_chip;
  }

  /* --- steps ------------------------------------------------------------ */

  const errorBox = $("#step-error");
  function showError(msg) {
    $("#step-error-text").textContent = msg;
    errorBox.hidden = false;
  }
  function hideError() {
    errorBox.hidden = true;
  }

  function missing(step) {
    return REQUIRED[step].find((name) => selected(name).length === 0) || null;
  }

  function render() {
    const step = state.step;
    $$("[data-panel]").forEach((p) => {
      p.hidden = Number(p.dataset.panel) !== step;
    });
    $("#step-num").textContent = String(step);
    $("#btn-back").disabled = step === 1;
    $("#btn-next").hidden = step === STEPS;
    $("#btn-complete").hidden = step !== STEPS;

    const progress = $("#reflect-progress");
    progress.style.width = `calc((100% - 3rem) * ${(step - 1) / (STEPS - 1)})`;

    $$("[data-step-dot]").forEach((btn) => {
      const n = Number(btn.dataset.stepDot);
      const dot = $("[data-dot]", btn);
      const name = $("[data-step-name]", btn);
      const current = n === step;
      const done = n < step || n <= state.maxStep;
      btn.disabled = n > state.maxStep || current;
      if (current) btn.setAttribute("aria-current", "step");
      else btn.removeAttribute("aria-current");
      dot.className =
        "w-10 h-10 rounded-full font-label-md text-label-md flex items-center justify-center transition-all " +
        (current
          ? "bg-primary text-on-primary shadow-md ring-4 ring-primary-fixed/50"
          : done
            ? "bg-primary-fixed text-on-primary-fixed"
            : "bg-surface-container text-on-surface-variant");
      name.classList.toggle("text-primary", current);
      name.classList.toggle("font-bold", current);
      name.classList.toggle("text-on-surface-variant", !current);
    });

    if (step === STEPS) buildReview();
  }

  function go(step, focus) {
    state.step = Math.max(1, Math.min(STEPS, step));
    state.maxStep = Math.max(state.maxStep, state.step);
    hideError();
    stopSpeaking();
    persist();
    render();
    if (focus !== false) {
      const heading = $(`[data-panel="${state.step}"] h2`);
      if (heading) {
        heading.setAttribute("tabindex", "-1");
        heading.focus({ preventScroll: true });
      }
      const top = form.getBoundingClientRect().top + window.scrollY - 96;
      if (window.scrollY > top) window.scrollTo({ top, behavior: "smooth" });
    }
  }

  function firstIncomplete(upTo) {
    for (let s = 1; s <= upTo; s++) if (missing(s)) return s;
    return null;
  }

  $("#btn-next").addEventListener("click", () => {
    const name = missing(state.step);
    if (name) {
      showError(S["need_" + name] || "");
      const first = $(`.reflect-opt[data-name="${name}"]`);
      if (first) first.focus();
      return;
    }
    go(state.step + 1);
  });

  $("#btn-back").addEventListener("click", () => go(state.step - 1));

  $$("[data-step-dot]").forEach((btn) => {
    btn.addEventListener("click", () => go(Number(btn.dataset.stepDot)));
  });

  form.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.tagName === "INPUT" && e.target.type === "text") e.preventDefault();
  });

  /* --- review ----------------------------------------------------------- */

  function questionText(name) {
    const el = $(`[data-q="${name}"]`);
    return el ? el.textContent.trim() : name;
  }

  function optionLabels(name) {
    return selected(name).map((v) => {
      const b = $(`.reflect-opt[data-name="${name}"][data-value="${v}"] [data-label]`);
      return b ? b.textContent.trim() : v;
    });
  }

  const REVIEW = {
    1: ["reason", "reason_text", "analysis_id"],
    2: ["evidence", "understanding", "change_mind"],
    3: ["deadline", "commitment", "essentials"],
    4: ["emotions", "counterfactual"],
  };

  function answerText(name) {
    if (name === "analysis_id") {
      const sel = form.elements.analysis_id;
      if (!sel || !sel.value) return null;
      return sel.options[sel.selectedIndex].textContent.trim();
    }
    if (TEXT_FIELDS.includes(name)) {
      const v = (state.answers[name] || "").trim();
      return v || null;
    }
    const labels = optionLabels(name);
    return labels.length ? labels.join(", ") : S.not_answered;
  }

  function buildReview() {
    const list = $("#review-list");
    list.textContent = "";
    const stepNames = $$("[data-step-name]").map((el) => el.textContent.trim());
    Object.keys(REVIEW).forEach((k) => {
      const step = Number(k);
      const card = document.createElement("div");
      card.className = "bg-surface rounded-2xl p-space-md min-w-0";
      const head = document.createElement("div");
      head.className = "flex items-center justify-between gap-2 mb-space-xs";
      const title = document.createElement("h3");
      title.className = "font-label-lg text-label-lg text-primary font-bold";
      title.textContent = `${step}. ${stepNames[step - 1] || ""}`;
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className =
        "px-3 py-1 rounded-full bg-surface-container-lowest hover:bg-surface-container text-primary font-label-md text-label-md flex items-center gap-1";
      edit.innerHTML = '<span class="material-symbols-outlined text-[16px]">edit</span>';
      const editText = document.createElement("span");
      editText.textContent = S.edit;
      edit.appendChild(editText);
      edit.setAttribute("aria-label", `${S.edit}: ${stepNames[step - 1] || step}`);
      edit.addEventListener("click", () => go(step));
      head.append(title, edit);
      card.appendChild(head);

      const dl = document.createElement("dl");
      dl.className = "flex flex-col gap-1.5";
      REVIEW[k].forEach((name) => {
        const value = answerText(name);
        if (value === null) return;
        const dt = document.createElement("dt");
        dt.className = "font-body-sm text-body-sm text-on-surface-variant";
        dt.textContent = questionText(name);
        const dd = document.createElement("dd");
        dd.className = "font-body-md text-body-md text-on-surface font-semibold break-words";
        dd.textContent = value;
        dl.append(dt, dd);
      });
      card.appendChild(dl);
      list.appendChild(card);
    });
  }

  /* --- complete --------------------------------------------------------- */

  let saving = false;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (saving) return;
    const gap = firstIncomplete(4);
    if (gap) {
      go(gap);
      showError(S["need_" + missing(gap)] || "");
      return;
    }
    if (!navigator.onLine) {
      showError(S.offline);
      return;
    }
    const a = state.answers;
    const payload = {
      reason: a.reason,
      reason_text: (a.reason_text || "").slice(0, 600),
      analysis_id: a.analysis_id || null,
      evidence: selected("evidence"),
      change_mind: (a.change_mind || "").slice(0, 400),
      understanding: a.understanding,
      deadline: a.deadline,
      commitment: a.commitment,
      essentials: a.essentials,
      emotions: selected("emotions"),
      counterfactual: a.counterfactual,
      note: (a.note || "").slice(0, 1500),
      save_journal: !!a.save_journal,
      elapsed_seconds: Math.max(0, Math.round((Date.now() - (state.startedAt || Date.now())) / 1000)),
    };
    saving = true;
    const btn = $("#btn-complete");
    btn.disabled = true;
    $("#btn-complete-text").textContent = S.saving;
    hideError();
    try {
      const res = await fetch("/api/reflect/complete", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRF-Token": (window.NIRVAAN && window.NIRVAAN.csrf) || "",
        },
        body: JSON.stringify(payload),
      });
      let data = null;
      try {
        data = await res.json();
      } catch (err) {
        data = null;
      }
      if (!res.ok || !data || !data.ok) {
        showError((data && (data.error || (typeof data.detail === "string" && data.detail))) || S.save_failed);
        return;
      }
      showDone(data);
    } catch (err) {
      showError(S.save_failed);
    } finally {
      saving = false;
      btn.disabled = false;
      $("#btn-complete-text").textContent = S.complete;
    }
  });

  function showDone(data) {
    clearStored();
    form.hidden = true;
    const done = $("#reflect-done");
    const list = $("#done-cards");
    list.textContent = "";
    (data.cards || []).forEach((c) => {
      const li = document.createElement("li");
      li.className = "p-space-sm bg-surface rounded-xl flex flex-col sm:flex-row sm:items-start gap-2 min-w-0";
      const head = document.createElement("div");
      head.className = "flex items-center justify-between sm:justify-start gap-2 sm:w-56 flex-shrink-0";
      const nameEl = document.createElement("span");
      nameEl.className = "font-label-md text-label-md text-on-surface";
      // Use the (translated) matrix card name for this dimension.
      const matrixName = $(`[data-card="${c.key}"] .font-label-sm`);
      nameEl.textContent = matrixName ? matrixName.textContent.trim() : c.name;
      const chip = document.createElement("span");
      chip.className = `inline-block px-2 py-0.5 rounded-full ${c.chip} font-label-sm text-label-sm font-bold`;
      chip.textContent = S["label_" + c.label] || c.label;
      head.append(nameEl, chip);
      const why = document.createElement("p");
      why.className = "font-body-sm text-body-sm text-on-surface-variant min-w-0";
      why.textContent = S["why_" + c.reason_key] || c.reason || "";
      li.append(head, why);
      list.appendChild(li);
      updateMatrix(c);
    });
    $("#done-journal").hidden = !data.journal_id;
    if (typeof data.completed === "number") $("#reflect-count").textContent = String(data.completed);
    const from = $("#matrix-from");
    if (from) {
      from.hidden = false;
      $("#matrix-date").textContent = S.today;
    }
    const empty = $("#matrix-empty");
    if (empty) empty.hidden = true;
    $("#matrix-chip").textContent = S.last_reflection;
    $$("[data-step-dot]").forEach((b) => (b.disabled = true));
    $("#reflect-progress").style.width = "calc(100% - 3rem)";
    $$("[data-dot]").forEach((d) => {
      d.className =
        "w-10 h-10 rounded-full font-label-md text-label-md flex items-center justify-center transition-all bg-primary-fixed text-on-primary-fixed";
    });
    done.hidden = false;
    done.focus();
  }

  function updateMatrix(c) {
    const card = $(`[data-card="${c.key}"]`);
    if (!card) return;
    const label = $("[data-card-label]", card);
    label.className = `inline-block px-2 py-0.5 rounded-full ${c.chip} font-label-sm text-label-sm font-bold`;
    label.textContent = S["label_" + c.label] || c.label;
    const icon = $("[data-card-icon]", card);
    if (icon && Array.isArray(c.icon)) {
      icon.className = `material-symbols-outlined text-[16px] ${c.icon[1]}`;
      icon.textContent = c.icon[0];
    }
  }

  $("#btn-restart").addEventListener("click", () => {
    state = fresh();
    persist();
    $("#reflect-done").hidden = true;
    form.hidden = false;
    paintAll();
    $("#observation-chip").textContent = initialObs.chip;
    $("#observation-text").textContent = initialObs.text;
    go(1);
  });

  /* --- read aloud ------------------------------------------------------- */

  const synth = "speechSynthesis" in window ? window.speechSynthesis : null;
  const audioBtn = $("#audio-toggle-btn");
  const audioIcon = $("#audio-icon");
  const audioStatus = $("#audio-status");
  const BCP47 = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" }[root.dataset.lang] || "en-IN";

  function setAudio(on) {
    audioBtn.setAttribute("aria-pressed", on ? "true" : "false");
    audioIcon.textContent = on ? "stop" : "volume_up";
    audioStatus.textContent = on ? S.audio_on : S.audio_idle;
  }

  function stopSpeaking() {
    if (synth && synth.speaking) synth.cancel();
    if (audioBtn && synth) setAudio(false);
  }

  if (!synth || typeof SpeechSynthesisUtterance === "undefined") {
    audioBtn.disabled = true;
    audioStatus.textContent = S.audio_none;
  } else {
    audioBtn.addEventListener("click", () => {
      if (synth.speaking) {
        stopSpeaking();
        return;
      }
      const panel = $(`[data-panel="${state.step}"]`);
      if (!panel || panel.hidden) return;
      const parts = [];
      const h = $("[data-speak]", panel);
      if (h) parts.push(h.textContent.trim());
      const p = $("h2 + p", panel);
      if (p) parts.push(p.textContent.trim());
      const u = new SpeechSynthesisUtterance(parts.join(". "));
      u.lang = BCP47;
      const voice = synth.getVoices().find((v) => v.lang === BCP47);
      if (voice) u.voice = voice;
      u.onend = u.onerror = () => setAudio(false);
      setAudio(true);
      synth.speak(u);
    });
  }

  /* --- init ------------------------------------------------------------- */

  // ?analysis=<id> pre-links a check, but only if it is one of the user's listed checks.
  const params = new URLSearchParams(location.search);
  const pre = params.get("analysis");
  const sel = form.elements.analysis_id;
  if (pre && sel && Array.from(sel.options).some((o) => o.value === pre) && !state.answers.analysis_id) {
    state.answers.analysis_id = pre;
  }
  if (!state.startedAt) state.startedAt = Date.now();
  paintAll();
  // A stored step whose earlier steps are incomplete falls back to the first gap.
  const gap = firstIncomplete(Math.min(state.step, STEPS) - 1);
  if (gap) state.step = gap;
  go(state.step, false);
})();
