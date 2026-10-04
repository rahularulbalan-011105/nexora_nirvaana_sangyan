/* Learn & Explore behaviour.
 *
 * /learn         : category filter chips filter the lesson and path cards;
 *                  the spotlight "Listen" reads its text aloud.
 * /learn/{slug}  : mode tabs, Listen (browser speech synthesis in the page
 *                  language), and progress saved to the server.
 *
 * Interface strings come from #learn-strings so the page translator renders
 * them in the page language.
 */
(function () {
  "use strict";

  const S = {};
  document.querySelectorAll("#learn-strings [data-k]").forEach((el) => {
    S[el.dataset.k] = el.textContent.trim();
  });
  const LANG = (window.NIRVAAN && window.NIRVAAN.lang) || document.documentElement.lang || "en";
  const SPEECH_LANG = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" };

  // ---------------------------------------------------------------------------
  // Speech
  // ---------------------------------------------------------------------------
  const synth = "speechSynthesis" in window ? window.speechSynthesis : null;

  function loadVoices(timeoutMs) {
    return new Promise((resolve) => {
      if (!synth) return resolve([]);
      const now = synth.getVoices();
      if (now.length) return resolve(now);
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        resolve(synth.getVoices());
      };
      synth.addEventListener("voiceschanged", finish, { once: true });
      setTimeout(finish, timeoutMs);
    });
  }

  function pickVoice(voices, tag) {
    const want = tag.toLowerCase();
    const base = want.split("-")[0];
    const norm = (v) => (v.lang || "").toLowerCase().replace("_", "-");
    return (
      voices.find((v) => norm(v) === want) ||
      voices.find((v) => norm(v).split("-")[0] === base) ||
      null
    );
  }

  /** Speak ``text``. Calls ``onState(state, message)`` with
   *  "speaking" | "idle" | "unavailable" | "error". */
  async function speak(text, tag, onState) {
    if (!synth || typeof window.SpeechSynthesisUtterance === "undefined") {
      onState("unavailable", S.unsupported);
      return;
    }
    synth.cancel();
    const voices = await loadVoices(1500);
    const voice = pickVoice(voices, tag);
    const base = tag.split("-")[0];
    // English can fall back to the default voice; Hindi and Tamil read by an
    // English voice would be unintelligible, so say so instead.
    if (!voice && base !== "en") {
      onState("unavailable", S.no_voice);
      return;
    }
    const u = new SpeechSynthesisUtterance(text);
    u.lang = voice ? voice.lang : tag;
    if (voice) u.voice = voice;
    u.rate = 0.95;
    u.onend = () => onState("idle");
    u.onerror = (e) => {
      if (e && (e.error === "canceled" || e.error === "interrupted")) onState("idle");
      else onState("error", S.speech_error);
    };
    onState("speaking", S.speaking);
    synth.speak(u);
  }

  function stopSpeaking() {
    if (synth) synth.cancel();
  }

  window.addEventListener("pagehide", stopSpeaking);

  function wireListen(btn, labelEl, iconEl, statusEl, getText, tag) {
    if (!btn) return;
    let active = false;
    const setUi = (state, message) => {
      active = state === "speaking";
      btn.setAttribute("aria-pressed", active ? "true" : "false");
      if (labelEl) labelEl.textContent = active ? S.stop : S.listen;
      if (iconEl) iconEl.textContent = active ? "stop_circle" : "volume_up";
      if (statusEl) {
        statusEl.textContent = message || "";
        statusEl.hidden = !message || state === "idle";
      }
    };
    btn.addEventListener("click", () => {
      if (active) {
        stopSpeaking();
        setUi("idle");
        return;
      }
      speak(getText(), tag, setUi);
    });
    return { reset: () => { if (active) { stopSpeaking(); setUi("idle"); } } };
  }

  // ---------------------------------------------------------------------------
  // POST helper
  // ---------------------------------------------------------------------------
  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": (window.NIRVAAN && window.NIRVAAN.csrf) || "",
      },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  // ---------------------------------------------------------------------------
  // /learn : filters + spotlight
  // ---------------------------------------------------------------------------
  const chips = document.querySelectorAll("#category-filter-chips .filter-chip");
  if (chips.length) {
    const ACTIVE = ["active", "bg-primary-container", "text-on-primary-container", "font-semibold"];
    const IDLE = ["bg-surface-container-lowest", "text-on-surface"];
    const cards = document.querySelectorAll("[data-learn-card]");
    const paths = document.querySelectorAll("[data-learn-path]");
    const spotlight = document.getElementById("learn-spotlight");
    const empty = document.getElementById("learn-empty");
    const countEl = document.getElementById("learn-visible-count");

    // Cards carry Tailwind display classes (flex), which beat the [hidden]
    // attribute, so visibility is set through inline style as well.
    const show = (el, on) => { el.hidden = !on; el.style.display = on ? "" : "none"; };
    const apply = (cat) => {
      chips.forEach((c) => {
        const on = c.dataset.category === cat;
        ACTIVE.forEach((k) => c.classList.toggle(k, on));
        IDLE.forEach((k) => c.classList.toggle(k, !on));
        c.setAttribute("aria-pressed", on ? "true" : "false");
      });
      let shown = 0;
      cards.forEach((card) => {
        const on = cat === "all" || card.dataset.group === cat;
        show(card, on);
        if (on) shown += 1;
      });
      paths.forEach((p) => {
        const groups = (p.dataset.groups || "").split(" ");
        show(p, cat === "all" || groups.includes(cat));
      });
      if (spotlight) show(spotlight, cat === "all" || cat === "mutual-funds");
      if (empty) empty.hidden = shown !== 0;
      if (countEl) countEl.textContent = String(shown);
    };

    chips.forEach((chip) => chip.addEventListener("click", () => apply(chip.dataset.category)));
    apply("all");

    const spotText = document.getElementById("spotlight-text");
    wireListen(
      document.getElementById("spotlight-listen"),
      document.getElementById("spotlight-listen-label"),
      document.getElementById("spotlight-listen-icon"),
      document.getElementById("spotlight-status"),
      () => (spotText ? spotText.innerText : ""),
      SPEECH_LANG[LANG] || "en-IN"
    );
  }

  // ---------------------------------------------------------------------------
  // /learn/{slug} : lesson page
  // ---------------------------------------------------------------------------
  const root = document.getElementById("learn-module");
  if (!root) return;

  const slug = root.dataset.slug;
  const api = "/api/learn/" + encodeURIComponent(slug);
  const tag = root.dataset.speechLang || SPEECH_LANG[LANG] || "en-IN";
  const tabs = root.querySelectorAll(".mode-tab");
  const panels = root.querySelectorAll(".mode-panel");
  const percentEl = document.getElementById("progress-percent");
  const barEl = document.getElementById("progress-bar");
  const errEl = document.getElementById("progress-error");
  let complete = root.dataset.complete === "1";

  const showError = (on) => { if (errEl) { errEl.textContent = on ? S.save_error : ""; errEl.hidden = !on; } };
  const showPercent = (data) => {
    if (!data || typeof data.percent !== "number") return;
    if (percentEl) percentEl.textContent = String(data.percent);
    if (barEl) barEl.style.width = data.percent + "%";
  };

  const activePanel = () => [...panels].find((p) => !p.hidden) || panels[0];
  const listen = wireListen(
    document.getElementById("listen-btn"),
    document.getElementById("listen-label"),
    document.getElementById("listen-icon"),
    document.getElementById("listen-status"),
    () => {
      const p = activePanel();
      return p ? p.innerText : "";
    },
    tag
  );

  const seen = new Set();
  const ON = ["bg-primary", "text-on-primary", "shadow-sm"];
  const OFF = ["bg-surface-container", "hover:bg-surface-container-high", "text-on-surface-variant", "hover:text-on-surface"];

  function selectMode(mode, record) {
    tabs.forEach((t) => {
      const on = t.dataset.mode === mode;
      ON.forEach((k) => t.classList.toggle(k, on));
      OFF.forEach((k) => t.classList.toggle(k, !on));
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    panels.forEach((p) => { p.hidden = p.dataset.modePanel !== mode; });
    if (listen) listen.reset();
    const before = seen.size;
    seen.add(mode);
    if (record && seen.size > before && !complete && seen.size > 1) {
      post(api + "/progress", { modes_seen: seen.size })
        .then((d) => { showError(false); showPercent(d); })
        .catch(() => showError(true));
    }
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("mode", mode);
      window.history.replaceState(null, "", url.toString());
    } catch (e) { /* ignore */ }
  }

  tabs.forEach((t) => t.addEventListener("click", () => selectMode(t.dataset.mode, true)));
  // Arrow-key navigation between tabs.
  root.querySelector("#mode-tabs")?.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const list = [...tabs];
    const i = list.findIndex((t) => t.getAttribute("aria-selected") === "true");
    const next = list[(i + (e.key === "ArrowRight" ? 1 : list.length - 1)) % list.length];
    next.focus();
    selectMode(next.dataset.mode, true);
  });

  const initialTab = [...tabs].find((t) => t.getAttribute("aria-selected") === "true");
  if (initialTab) seen.add(initialTab.dataset.mode);

  // Opening the lesson counts as a view.
  post(api + "/view")
    .then((d) => { showError(false); showPercent(d); })
    .catch(() => showError(true));

  const completeBtn = document.getElementById("complete-btn");
  if (completeBtn) {
    completeBtn.addEventListener("click", () => {
      if (complete) return;
      completeBtn.disabled = true;
      post(api + "/complete")
        .then((d) => {
          complete = true;
          showError(false);
          showPercent(d);
          document.getElementById("complete-label").textContent = S.completed;
          document.getElementById("complete-icon").textContent = "task_alt";
          completeBtn.className = completeBtn.className
            .replace("bg-gradient-to-r from-primary to-primary-container hover:opacity-95 text-on-primary", "bg-tertiary-container/20 text-tertiary cursor-default");
        })
        .catch(() => { completeBtn.disabled = false; showError(true); });
    });
  }

  const bookmarkBtn = document.getElementById("bookmark-btn");
  if (bookmarkBtn) {
    bookmarkBtn.addEventListener("click", () => {
      const want = bookmarkBtn.getAttribute("aria-pressed") !== "true";
      bookmarkBtn.disabled = true;
      post(api + "/bookmark", { bookmarked: want })
        .then((d) => {
          showError(false);
          bookmarkBtn.setAttribute("aria-pressed", d.bookmarked ? "true" : "false");
          document.getElementById("bookmark-label").textContent = d.bookmarked ? S.bookmarked : S.bookmark;
          document.getElementById("bookmark-icon").textContent = d.bookmarked ? "bookmark_added" : "bookmark_add";
        })
        .catch(() => showError(true))
        .finally(() => { bookmarkBtn.disabled = false; });
    });
  }
})();
