/* Talk to NIRVAAN.
 *
 * Voice in:  browser SpeechRecognition (where available) or the text box.
 * Answer:    POST /api/talk  ->  { reply, panel, intent, offline, session_id, ... }
 * Voice out: browser speechSynthesis, one utterance queue at a time.
 *
 * The page language (data-lang on #talk-root, set by the top-bar selector) is
 * the only language state. Interface strings come from #talk-strings, which the
 * server renders in that language.
 */
(function () {
  "use strict";

  const root = document.getElementById("talk-root");
  if (!root) return;

  const $ = (id) => document.getElementById(id);
  const LANG = root.dataset.lang || "en";
  const BCP47 = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" }[LANG] || "en-IN";
  const CSRF = (window.NIRVAAN && window.NIRVAAN.csrf) || "";
  const STORE_KEY = "nirvaan_talk";
  const PREF_KEY = "nirvaan_talk_prefs";

  const S = {};
  document.querySelectorAll("#talk-strings [data-k]").forEach((el) => {
    S[el.dataset.k] = el.textContent.trim();
  });

  // ---------------------------------------------------------------- storage
  const load = (key, fallback) => {
    try { return JSON.parse(sessionStorage.getItem(key)) || fallback; } catch (e) { return fallback; }
  };
  const save = (key, value) => {
    try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
  };
  const loadPref = () => {
    try { return JSON.parse(localStorage.getItem(PREF_KEY)) || {}; } catch (e) { return {}; }
  };
  const savePref = (p) => { try { localStorage.setItem(PREF_KEY, JSON.stringify(p)); } catch (e) { /* ignore */ } };

  const convo = load(STORE_KEY, { session_id: null, turns: [], last: null });
  const prefs = Object.assign(
    {
      rate: Math.min(1.4, Math.max(0.6, (parseInt(root.dataset.speechRate, 10) || 100) / 100)),
      autospeak: root.dataset.voiceEnabled !== "false",
      captions: true,
    },
    loadPref()
  );

  // ------------------------------------------------------------------ state
  const state = { mode: "idle", muted: false, slower: false };
  const ui = {
    chip: $("talk-state-chip"), chipIcon: $("talk-state-icon"), status: $("talk-status"),
    error: $("talk-error"), wave: $("talk-wave"), halo: $("talk-halo"),
    mic: $("talk-mic"), micIcon: $("talk-mic-icon"), micLabel: $("talk-mic-label"),
    mute: $("talk-mute"), caption: $("talk-caption"), captionHint: $("talk-caption-hint"),
    log: $("talk-log"), logEmpty: $("talk-log-empty"), count: $("talk-turn-count"),
  };

  const MODE_ICON = { idle: "mic", listening: "graphic_eq", processing: "hourglass_top", speaking: "volume_up", muted: "mic_off", error: "error" };

  function setMode(mode, message) {
    state.mode = mode;
    const shown = state.muted && (mode === "idle") ? "muted" : mode;
    ui.chip.textContent = S[shown] || shown;
    ui.chipIcon.textContent = MODE_ICON[shown] || "mic";
    ui.status.textContent = S["status_" + shown] || "";
    const animate = mode === "listening" || mode === "speaking";
    ui.wave.querySelectorAll("span").forEach((b) => { b.style.animationPlayState = animate ? "running" : "paused"; });
    ui.wave.style.opacity = animate ? "1" : "0.45";
    ui.halo.classList.toggle("animate-pulse", animate);

    const listening = mode === "listening";
    ui.micIcon.textContent = listening ? "stop_circle" : "mic";
    ui.micLabel.textContent = listening ? S.stop : S.start;
    ui.mic.classList.toggle("bg-error", listening);
    ui.mic.classList.toggle("bg-primary-container", !listening);
    ui.mic.disabled = mode === "processing";
    ui.mic.classList.toggle("opacity-60", mode === "processing");

    if (mode === "error" && message) {
      ui.error.textContent = message;
      ui.error.classList.remove("hidden");
    } else if (mode !== "error") {
      ui.error.classList.add("hidden");
    }
  }

  function showError(message) {
    setMode("error", message);
  }

  // ------------------------------------------------------------- transcript
  function renderLog() {
    ui.log.innerHTML = "";
    convo.turns.forEach((t) => {
      const wrap = document.createElement("div");
      const mine = t.role === "user";
      wrap.className = "flex " + (mine ? "justify-end" : "justify-start");
      const bubble = document.createElement("div");
      bubble.className = "max-w-[90%] rounded-2xl px-4 py-3 break-words " +
        (mine ? "bg-primary text-on-primary rounded-br-md" : "bg-surface-container-low text-on-surface rounded-bl-md");
      const who = document.createElement("p");
      who.className = "font-label-sm text-label-sm font-bold mb-1 " + (mine ? "text-on-primary/80" : "text-primary");
      who.textContent = mine ? S.you : S.nirvaan;
      const body = document.createElement("p");
      body.className = "font-body-md text-body-md whitespace-pre-line";
      body.textContent = t.text;
      bubble.append(who, body);
      wrap.appendChild(bubble);
      ui.log.appendChild(wrap);
    });
    const users = convo.turns.filter((t) => t.role === "user").length;
    ui.count.textContent = String(users);
    ui.logEmpty.classList.toggle("hidden", convo.turns.length > 0);
    ui.log.scrollTop = ui.log.scrollHeight;
  }

  function setCaption(text, interim) {
    if (!text) {
      ui.caption.textContent = S.no_conversation;
      ui.caption.classList.add("text-on-surface-variant");
      ui.caption.classList.remove("text-on-surface");
      ui.captionHint.classList.remove("hidden");
      return;
    }
    ui.caption.textContent = "“" + text + "”";
    ui.caption.classList.toggle("text-on-surface-variant", !!interim);
    ui.caption.classList.toggle("text-on-surface", !interim);
    ui.captionHint.classList.add("hidden");
  }

  // ------------------------------------------------------------------ panel
  const panelEls = {
    title: $("talk-panel-title"), summary: $("talk-panel-summary"), points: $("talk-panel-points"),
    full: $("talk-panel-full"), info: $("talk-infographic"), offline: $("talk-panel-offline"),
    simple: $("talk-panel-simple"), detailed: $("talk-panel-detailed"),
  };

  function renderPanel(last) {
    if (!last) return;
    const p = last.panel || {};
    panelEls.title.textContent = p.title || S.default_title;
    panelEls.summary.textContent = p.summary || last.reply || S.default_summary;
    panelEls.points.innerHTML = "";
    (p.points || []).forEach((point) => {
      const row = document.createElement("div");
      row.className = "flex items-start gap-2.5 p-space-sm bg-surface-container-low rounded-xl";
      const icon = document.createElement("span");
      icon.className = "material-symbols-outlined text-[20px] text-tertiary mt-0.5";
      icon.textContent = "check_circle";
      const txt = document.createElement("span");
      txt.className = "font-body-md text-body-md text-on-surface break-words";
      txt.textContent = point;
      row.append(icon, txt);
      panelEls.points.appendChild(row);
    });
    panelEls.full.textContent = last.reply || "";
    const fund = last.intent === "mutual_fund" || last.intent === "sip";
    panelEls.info.classList.toggle("hidden", !fund);
    panelEls.info.classList.toggle("flex", fund);
    panelEls.offline.classList.toggle("hidden", !last.offline);
  }

  function setPanelMode(mode) {
    const detailed = mode === "detailed";
    panelEls.detailed.classList.toggle("hidden", !detailed);
    panelEls.detailed.classList.toggle("flex", detailed);
    panelEls.simple.classList.toggle("hidden", detailed);
    panelEls.points.classList.toggle("hidden", detailed);
    document.querySelectorAll('[role="tab"][data-panel-mode]').forEach((tab) => {
      const on = tab.dataset.panelMode === mode;
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.className = "px-3 py-1 rounded-full font-label-sm text-label-sm " +
        (on ? "bg-primary-container text-on-primary-container font-bold shadow-sm" : "text-on-surface-variant hover:text-on-surface");
    });
  }
  document.querySelectorAll("[data-panel-mode]").forEach((b) =>
    b.addEventListener("click", () => setPanelMode(b.dataset.panelMode)));

  // -------------------------------------------------------- speech synthesis
  const synth = "speechSynthesis" in window ? window.speechSynthesis : null;
  const tts = { chunks: [], index: 0, total: 0, done: 0, playing: false, paused: false, startedAt: 0, pausedFor: 0, pausedAt: 0, timer: null };
  const playBtn = $("talk-play"), playIcon = $("talk-play-icon"), replayBtn = $("talk-replay"),
    speakLatest = $("talk-speak-latest"), progress = $("talk-progress"), progressBar = $("talk-progress-bar"),
    elapsed = $("talk-elapsed"), ttsNote = $("talk-tts-note");

  function note(msg) {
    ttsNote.textContent = msg || "";
    ttsNote.classList.toggle("hidden", !msg);
  }

  function pickVoice() {
    if (!synth) return null;
    const voices = synth.getVoices();
    return voices.find((v) => v.lang === BCP47) ||
      voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(LANG)) || null;
  }

  function splitForSpeech(text) {
    // Short chunks avoid browsers cutting off long utterances.
    const parts = text.replace(/\n+/g, ". ").split(/(?<=[.!?।])\s+/);
    const chunks = [];
    let buf = "";
    parts.forEach((p) => {
      if ((buf + " " + p).length > 220 && buf) { chunks.push(buf.trim()); buf = p; } else { buf += " " + p; }
    });
    if (buf.trim()) chunks.push(buf.trim());
    return chunks.filter((c) => c.replace(/[.\s-]/g, ""));
  }

  function fmt(sec) {
    const s = Math.max(0, Math.floor(sec));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  }

  function tick() {
    if (!tts.playing) return;
    const now = tts.paused ? tts.pausedAt : Date.now();
    elapsed.textContent = fmt((now - tts.startedAt - tts.pausedFor) / 1000);
  }

  function setProgress(pct) {
    const v = Math.max(0, Math.min(100, pct));
    progress.style.width = v + "%";
    progressBar.setAttribute("aria-valuenow", String(Math.round(v)));
  }

  function updatePlayUi() {
    const showPause = tts.playing && !tts.paused;
    playIcon.textContent = showPause ? "pause" : "play_arrow";
    playBtn.setAttribute("aria-label", showPause ? S.pause : S.play);
    const has = !!(convo.last && convo.last.reply);
    playBtn.disabled = !has || !synth;
    replayBtn.disabled = !has || !synth;
    speakLatest.disabled = !has || !synth;
  }

  function stopSpeech() {
    if (synth) synth.cancel();
    tts.playing = false; tts.paused = false;
    clearInterval(tts.timer);
    updatePlayUi();
    if (state.mode === "speaking") setMode("idle");
  }

  function speakChunk() {
    if (!tts.playing) return;
    if (tts.index >= tts.chunks.length) {
      tts.playing = false;
      clearInterval(tts.timer);
      setProgress(100);
      updatePlayUi();
      if (state.mode === "speaking") setMode("idle");
      return;
    }
    const text = tts.chunks[tts.index];
    const u = new SpeechSynthesisUtterance(text);
    u.lang = BCP47;
    const voice = pickVoice();
    if (voice) u.voice = voice;
    u.rate = prefs.rate * (state.slower ? 0.8 : 1);
    u.onboundary = (e) => {
      if (typeof e.charIndex === "number") setProgress(((tts.done + e.charIndex) / tts.total) * 100);
    };
    u.onend = () => {
      tts.done += text.length + 1;
      setProgress((tts.done / tts.total) * 100);
      tts.index += 1;
      speakChunk();
    };
    u.onerror = (e) => {
      if (e.error === "interrupted" || e.error === "canceled") return;
      tts.playing = false;
      clearInterval(tts.timer);
      updatePlayUi();
      note(S.tts_unsupported);
      if (state.mode === "speaking") setMode("idle");
    };
    synth.speak(u);
    // Some devices accept speak() but never produce audio (no voices installed).
    // Detect that instead of leaving the UI saying "Speaking".
    const myIndex = tts.index;
    setTimeout(() => {
      if (tts.playing && !tts.paused && tts.index === myIndex && !synth.speaking && !synth.pending) {
        tts.playing = false;
        clearInterval(tts.timer);
        updatePlayUi();
        note(S.tts_failed);
        if (state.mode === "speaking") setMode("idle");
      }
    }, 2500);
  }

  function speak(text) {
    if (!text) return;
    if (!synth) { note(S.tts_unsupported); return; }
    synth.cancel(); // never overlap
    note(pickVoice() || !synth.getVoices().length ? "" : S.tts_novoice);
    tts.chunks = splitForSpeech(text);
    tts.total = tts.chunks.reduce((n, c) => n + c.length + 1, 0) || 1;
    tts.index = 0; tts.done = 0;
    tts.playing = true; tts.paused = false;
    tts.startedAt = Date.now(); tts.pausedFor = 0;
    setProgress(0);
    clearInterval(tts.timer);
    tts.timer = setInterval(tick, 250);
    if (state.mode !== "listening") setMode("speaking");
    updatePlayUi();
    // Chrome sometimes needs a beat after cancel() before speak().
    setTimeout(speakChunk, 60);
  }

  playBtn.addEventListener("click", () => {
    if (!synth || !convo.last) return;
    if (tts.playing && !tts.paused && !synth.speaking && !synth.pending) tts.playing = false; // stopped elsewhere
    if (tts.playing && !tts.paused) {
      synth.pause(); tts.paused = true; tts.pausedAt = Date.now();
      if (state.mode === "speaking") setMode("idle");
    } else if (tts.playing && tts.paused) {
      synth.resume(); tts.paused = false; tts.pausedFor += Date.now() - tts.pausedAt;
      setMode("speaking");
    } else {
      speak(convo.last.reply);
    }
    updatePlayUi();
  });
  replayBtn.addEventListener("click", () => convo.last && speak(convo.last.reply));
  speakLatest.addEventListener("click", () => convo.last && speak(convo.last.reply));

  const slowerBtn = $("talk-slower");
  slowerBtn.addEventListener("click", () => {
    state.slower = !state.slower;
    slowerBtn.setAttribute("aria-pressed", state.slower ? "true" : "false");
    slowerBtn.classList.toggle("ring-2", state.slower);
    slowerBtn.classList.toggle("ring-secondary", state.slower);
    if (tts.playing && convo.last) speak(convo.last.reply); // restart at the new speed
  });

  if (synth && "onvoiceschanged" in synth) synth.onvoiceschanged = () => {};
  if (!synth) note(S.tts_unsupported);

  // ------------------------------------------------------------- ask NIRVAAN
  let inFlight = null;

  async function ask(text, opts) {
    const options = opts || {};
    const question = (text || "").trim();
    if (!question) { showError(S.err_empty); return; }
    if (inFlight) inFlight.abort();
    stopSpeech();

    if (!options.silent) {
      convo.turns.push({ role: "user", text: question, lang: LANG });
      renderLog();
      setCaption(question, false);
    }
    save(STORE_KEY, convo);
    setMode("processing");

    const controller = new AbortController();
    inFlight = controller;
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const res = await fetch("/api/talk", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF },
        body: JSON.stringify({ text: question, language: LANG, session_id: convo.session_id }),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error("status " + res.status);
      const data = await res.json();
      convo.session_id = data.session_id || convo.session_id;
      convo.last = { question, reply: data.reply, panel: data.panel, intent: data.intent, offline: data.offline, lang: LANG };
      if (!options.silent) convo.turns.push({ role: "assistant", text: data.reply, lang: LANG });
      save(STORE_KEY, convo);
      renderLog();
      renderPanel(convo.last);
      setPanelMode("simple");
      setMode("idle");
      updatePlayUi();
      if (prefs.autospeak && !options.silent) speak(data.reply);
    } catch (err) {
      if (controller.signal.aborted && inFlight !== controller) return; // superseded
      showError(navigator.onLine === false ? S.err_offline : S.err_server);
    } finally {
      clearTimeout(timeout);
      if (inFlight === controller) inFlight = null;
    }
  }

  document.querySelectorAll("[data-talk-prompt]").forEach((b) =>
    b.addEventListener("click", () => {
      const label = b.querySelector("[data-prompt-text]");
      ask(label ? label.textContent : b.textContent);
    }));

  const textInput = $("talk-text");
  $("talk-text-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = textInput.value;
    textInput.value = "";
    ask(q);
  });
  $("talk-followup").addEventListener("click", () => {
    textInput.focus();
    textInput.scrollIntoView({ block: "center", behavior: "smooth" });
  });

  $("talk-new").addEventListener("click", () => {
    stopSpeech();
    if (convo.session_id) {
      fetch("/api/talk/end", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF },
        body: JSON.stringify({ session_id: convo.session_id }),
      }).catch(() => {});
    }
    convo.session_id = null; convo.turns = []; convo.last = null;
    save(STORE_KEY, convo);
    renderLog();
    setCaption("");
    panelEls.title.textContent = S.default_title;
    panelEls.summary.textContent = S.default_summary;
    panelEls.points.innerHTML = "";
    panelEls.full.textContent = "";
    panelEls.info.classList.add("hidden");
    panelEls.offline.classList.add("hidden");
    setProgress(0);
    elapsed.textContent = "0:00";
    updatePlayUi();
    setMode("idle");
  });

  // ------------------------------------------------------- speech recognition
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  let heard = "";

  function stopListening(abort) {
    if (recognizer) {
      try { abort ? recognizer.abort() : recognizer.stop(); } catch (e) { /* already stopped */ }
    }
  }

  function startListening() {
    if (state.muted) { showError(S.err_muted); return; }
    if (!Recognition) { showError(S.err_unsupported); return; }
    stopSpeech();
    heard = "";
    recognizer = new Recognition();
    recognizer.lang = BCP47;
    recognizer.interimResults = true;
    recognizer.continuous = false;
    recognizer.maxAlternatives = 1;

    recognizer.onstart = () => setMode("listening");
    recognizer.onresult = (event) => {
      let interim = "", final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) final += r[0].transcript; else interim += r[0].transcript;
      }
      if (final) heard += final;
      setCaption((heard + " " + interim).trim(), !final);
    };
    recognizer.onerror = (event) => {
      const map = {
        "not-allowed": S.err_denied, "service-not-allowed": S.err_denied,
        "audio-capture": S.err_nomic, "no-speech": S.err_nospeech, network: S.err_network,
        "language-not-supported": S.err_unsupported,
      };
      if (event.error === "aborted") return;
      recognizer = null;
      showError(map[event.error] || S.err_server);
      refreshPermission();
    };
    recognizer.onend = () => {
      const said = heard.trim();
      const wasListening = state.mode === "listening";
      recognizer = null;
      if (said && !state.muted) ask(said);
      else if (wasListening) setMode("idle");
    };
    try {
      recognizer.start();
    } catch (e) {
      recognizer = null;
      showError(S.err_server);
    }
  }

  ui.mic.addEventListener("click", () => {
    if (state.mode === "listening") stopListening(false);
    else startListening();
  });

  ui.mute.addEventListener("click", () => {
    state.muted = !state.muted;
    if (state.muted) {
      heard = ""; // nothing captured while muted is ever sent
      stopListening(true);
    }
    ui.mute.setAttribute("aria-pressed", state.muted ? "true" : "false");
    const label = state.muted ? S.unmute : S.mute;
    ui.mute.setAttribute("aria-label", label);
    ui.mute.title = label;
    ui.mute.querySelector(".material-symbols-outlined").textContent = state.muted ? "mic_off" : "mic";
    ui.mute.classList.toggle("bg-error", state.muted);
    ui.mute.classList.toggle("bg-white/10", !state.muted);
    if (state.mode !== "processing") setMode("idle");
  });

  // --------------------------------------------------------------- settings
  const settingsBtn = $("talk-settings-btn"), settings = $("talk-settings");
  const rate = $("talk-rate"), rateValue = $("talk-rate-value"),
    autospeak = $("talk-autospeak"), captions = $("talk-captions"), perm = $("talk-mic-permission");

  function toggleSettings(open) {
    const show = open === undefined ? settings.classList.contains("hidden") : open;
    settings.classList.toggle("hidden", !show);
    settingsBtn.setAttribute("aria-expanded", show ? "true" : "false");
    if (show) refreshPermission();
  }
  settingsBtn.addEventListener("click", (e) => { e.stopPropagation(); toggleSettings(); });
  document.addEventListener("click", (e) => {
    if (!settings.classList.contains("hidden") && !settings.contains(e.target)) toggleSettings(false);
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") toggleSettings(false); });

  rate.value = String(prefs.rate);
  rateValue.textContent = Number(prefs.rate).toFixed(1) + "x";
  rate.addEventListener("input", () => {
    prefs.rate = parseFloat(rate.value);
    rateValue.textContent = prefs.rate.toFixed(1) + "x";
    savePref(prefs);
  });
  autospeak.checked = !!prefs.autospeak;
  autospeak.addEventListener("change", () => { prefs.autospeak = autospeak.checked; savePref(prefs); if (!prefs.autospeak) stopSpeech(); });

  function applyCaptions() {
    document.querySelectorAll("[data-captions]").forEach((el) => el.classList.toggle("hidden", !prefs.captions));
    const toggle = $("sessionToggleBtn");
    toggle.setAttribute("aria-expanded", prefs.captions ? "true" : "false");
    toggle.classList.toggle("bg-primary-container", prefs.captions);
    toggle.classList.toggle("text-on-primary-container", prefs.captions);
    toggle.classList.toggle("bg-surface-container-high", !prefs.captions);
    captions.checked = !!prefs.captions;
  }
  captions.addEventListener("change", () => { prefs.captions = captions.checked; savePref(prefs); applyCaptions(); });
  $("sessionToggleBtn").addEventListener("click", () => {
    prefs.captions = !prefs.captions; savePref(prefs); applyCaptions();
    if (prefs.captions) $("talk-transcript").scrollIntoView({ block: "nearest", behavior: "smooth" });
  });

  async function refreshPermission() {
    if (!Recognition) { perm.textContent = S.perm_unsupported; return; }
    if (!navigator.permissions || !navigator.permissions.query) { perm.textContent = S.perm_unknown; return; }
    try {
      const status = await navigator.permissions.query({ name: "microphone" });
      perm.textContent = S["perm_" + status.state] || S.perm_unknown;
      status.onchange = () => { perm.textContent = S["perm_" + status.state] || S.perm_unknown; };
    } catch (e) {
      perm.textContent = S.perm_unknown;
    }
  }

  // ------------------------------------------------------------------- boot
  window.addEventListener("pagehide", () => { stopListening(true); if (synth) synth.cancel(); });

  applyCaptions();
  renderLog();
  const lastUser = [...convo.turns].reverse().find((t) => t.role === "user");
  setCaption(lastUser ? lastUser.text : "");
  setMode("idle");
  updatePlayUi();
  if (convo.last) {
    if (convo.last.lang !== LANG && convo.last.question) {
      // Language changed: refresh the explanation in the newly selected language.
      ask(convo.last.question, { silent: true });
    } else {
      renderPanel(convo.last);
    }
  }
  if (!Recognition) {
    ui.mic.title = S.err_unsupported;
  }
})();
