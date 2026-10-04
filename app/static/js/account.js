/* Settings, Privacy Center and Offline Mode controls.
 *
 * Switches:   [data-pref="field"] / [data-privacy="field"] on a checkbox or a
 *             role="switch" button  ->  POST /api/account/{preferences|privacy}
 * Choices:    [data-pref-choice="field"][data-value="true|false"] buttons
 * Speech:     #voiceSpeedRange  -> speech_rate (percent)
 * Language:   form[data-autosubmit] submits on change (POST /api/language)
 * Destructive:[data-confirm="kind"][data-url]  -> confirm dialog, then POST
 *             {confirm: true} (or {confirm_text} when data-typed is present)
 *
 * Every state change waits for the server; on failure the control reverts.
 */
(function () {
  "use strict";

  const S = {};
  document.querySelectorAll("#account-strings [data-k]").forEach((el) => {
    S[el.dataset.k] = el.textContent.trim();
  });
  const t = (k, fallback) => S[k] || fallback || k;
  const toast = (msg, kind) => {
    if (window.NIRVAAN && typeof window.NIRVAAN.toast === "function") window.NIRVAAN.toast(msg, kind);
  };
  const CSRF = () => (window.NIRVAAN && window.NIRVAAN.csrf) || "";

  async function post(url, body) {
    let res;
    try {
      res = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF(), Accept: "application/json" },
        body: JSON.stringify(body || {}),
      });
    } catch (e) {
      return { ok: false, error: t("network") };
    }
    let data = {};
    try { data = await res.json(); } catch (e) { /* non-JSON */ }
    if (!res.ok || data.ok === false) {
      return { ok: false, error: data.error || data.detail || t("save_failed") };
    }
    return Object.assign({ ok: true }, data);
  }

  // Talk keeps per-browser overrides; a new account default should win.
  function clearTalkOverride(key) {
    try {
      const k = "nirvaan_talk_prefs";
      const p = JSON.parse(localStorage.getItem(k) || "{}");
      if (p && typeof p === "object" && key in p) { delete p[key]; localStorage.setItem(k, JSON.stringify(p)); }
    } catch (e) { /* storage unavailable */ }
  }

  // ------------------------------------------------------------ live effects
  const root = document.documentElement;
  const EFFECTS = {
    large_text: (on) => root.classList.toggle("text-[18px]", on),
    high_contrast: (on) => root.setAttribute("data-contrast", on ? "high" : "normal"),
    data_saver: (on) => {
      root.setAttribute("data-data-saver", on ? "1" : "0");
      if (window.NIRVAAN) window.NIRVAAN.dataSaver = on;
    },
    voice_enabled: () => clearTalkOverride("autospeak"),
  };

  // ------------------------------------------------------------ switches
  function readSwitch(el) {
    return el.matches("input[type=checkbox]") ? el.checked : el.getAttribute("aria-checked") === "true";
  }
  function paintSwitch(el, on) {
    if (el.matches("input[type=checkbox]")) { el.checked = on; return; }
    el.setAttribute("aria-checked", on ? "true" : "false");
    el.classList.toggle("bg-primary-container", on);
    el.classList.toggle("bg-surface-dim", !on);
    const thumb = el.querySelector("span");
    if (thumb) { thumb.classList.toggle("translate-x-6", on); thumb.classList.toggle("translate-x-0", !on); }
  }
  function paintStatus(field, on) {
    document.querySelectorAll(`[data-status-for="${field}"]`).forEach((badge) => {
      badge.textContent = on ? t("active") : t("off");
      badge.classList.toggle("bg-primary-fixed", on);
      badge.classList.toggle("text-on-primary-fixed-variant", on);
      badge.classList.toggle("bg-surface-container-highest", !on);
      badge.classList.toggle("text-on-surface-variant", !on);
    });
    document.querySelectorAll(`[data-show-when="${field}"]`).forEach((n) => { n.hidden = !on; });
    document.querySelectorAll(`[data-hide-when="${field}"]`).forEach((n) => { n.hidden = on; });
  }

  async function saveField(kind, field, value) {
    const url = kind === "privacy" ? "/api/account/privacy" : "/api/account/preferences";
    return post(url, { [field]: value });
  }

  document.querySelectorAll("[data-pref], [data-privacy]").forEach((el) => {
    const kind = el.hasAttribute("data-privacy") ? "privacy" : "pref";
    const field = el.getAttribute(kind === "privacy" ? "data-privacy" : "data-pref");
    const evt = el.matches("input") ? "change" : "click";
    el.addEventListener(evt, async () => {
      const before = el.matches("input") ? !el.checked : readSwitch(el);
      const next = !before;
      paintSwitch(el, next);
      el.setAttribute("aria-busy", "true");
      const res = await saveField(kind, field, next);
      el.removeAttribute("aria-busy");
      if (!res.ok) {
        paintSwitch(el, before);
        toast(res.error, "error");
        return;
      }
      if (EFFECTS[field]) EFFECTS[field](next);
      paintStatus(field, next);
      toast(t("saved"), "success");
    });
  });

  // Segmented choices (e.g. Normal / High Contrast, Standard / Large text).
  const ON_CLS = (el) => (el.dataset.onClass || "").split(" ").filter(Boolean);
  const OFF_CLS = (el) => (el.dataset.offClass || "").split(" ").filter(Boolean);
  function paintChoice(field, value) {
    document.querySelectorAll(`[data-pref-choice="${field}"]`).forEach((b) => {
      const on = (b.dataset.value === "true") === value;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      ON_CLS(b).forEach((c) => b.classList.toggle(c, on));
      OFF_CLS(b).forEach((c) => b.classList.toggle(c, !on));
    });
  }
  document.querySelectorAll("[data-pref-choice]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const field = btn.dataset.prefChoice;
      const value = btn.dataset.value === "true";
      if (btn.getAttribute("aria-pressed") === "true") return;
      const res = await saveField("pref", field, value);
      if (!res.ok) { toast(res.error, "error"); return; }
      paintChoice(field, value);
      if (EFFECTS[field]) EFFECTS[field](value);
      toast(t("saved"), "success");
    });
  });

  // ------------------------------------------------------------ speech rate
  const speed = document.getElementById("voiceSpeedRange");
  const speedLabel = document.getElementById("speedValueLabel");
  if (speed) {
    const nuance = (v) => (v < 0.85 ? "slow" : v <= 0.95 ? "calm" : v <= 1.1 ? "neutral" : "brisk");
    const paint = () => {
      const v = parseFloat(speed.value);
      if (speedLabel) speedLabel.textContent = `${v.toFixed(2)}x • ${t("speed." + nuance(v))}`;
    };
    speed.addEventListener("input", paint);
    speed.addEventListener("change", async () => {
      const res = await saveField("pref", "speech_rate", Math.round(parseFloat(speed.value) * 100));
      if (!res.ok) { toast(res.error, "error"); return; }
      clearTalkOverride("rate");
      toast(t("saved"), "success");
    });
  }

  // ------------------------------------------------------------ auto-submit forms
  document.querySelectorAll("form[data-autosubmit] select").forEach((sel) => {
    sel.addEventListener("change", () => sel.form.requestSubmit ? sel.form.requestSubmit() : sel.form.submit());
  });

  // ------------------------------------------------------------ confirm dialog
  const dlg = document.getElementById("account-confirm");
  const ui = dlg && {
    title: document.getElementById("account-confirm-title"),
    body: document.getElementById("account-confirm-body"),
    typedWrap: document.getElementById("account-confirm-typed"),
    input: document.getElementById("account-confirm-input"),
    error: document.getElementById("account-confirm-error"),
    ok: document.getElementById("account-confirm-ok"),
    cancel: document.getElementById("account-confirm-cancel"),
    form: document.getElementById("account-confirm-form"),
  };
  let pending = null;

  function openConfirm(btn) {
    if (!dlg) return;
    const kind = btn.dataset.confirm;
    const typed = btn.hasAttribute("data-typed");
    pending = { btn, kind, typed, url: btn.dataset.url };
    ui.title.textContent = t(kind + ".title");
    ui.body.textContent = t(kind + ".body");
    ui.ok.textContent = t(kind + ".ok", t("delete.ok"));
    ui.error.hidden = true;
    ui.error.classList.add("hidden");
    ui.typedWrap.classList.toggle("hidden", !typed);
    ui.input.value = "";
    ui.ok.disabled = typed;
    if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
    (typed ? ui.input : ui.cancel).focus();
  }
  function closeConfirm() {
    pending = null;
    if (dlg.open) dlg.close();
  }
  if (dlg) {
    ui.input.addEventListener("input", () => { ui.ok.disabled = ui.input.value.trim() !== "DELETE"; });
    ui.cancel.addEventListener("click", closeConfirm);
    ui.form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!pending) return;
      const job = pending;
      const body = job.typed ? { confirm_text: ui.input.value.trim() } : { confirm: true };
      ui.ok.disabled = true;
      const res = await post(job.url, body);
      if (!res.ok) {
        ui.error.textContent = res.error;
        ui.error.hidden = false;
        ui.error.classList.remove("hidden");
        ui.ok.disabled = job.typed && ui.input.value.trim() !== "DELETE";
        return;
      }
      closeConfirm();
      if (res.redirect) { window.location.assign(res.redirect); return; }
      if (job.btn.dataset.removeRow) {
        const row = job.btn.closest(job.btn.dataset.removeRow);
        if (row) row.remove();
      }
      if (job.kind === "session") {
        toast(t("session_ended"), "success");
        return;
      }
      toast(res.deleted ? t("deleted") : t("nothing"), "success");
      // Counts on the page come from the server; reload so they stay true.
      if (!job.btn.dataset.removeRow) setTimeout(() => window.location.reload(), 600);
      else document.querySelectorAll("[data-memory-count]").forEach((n) => {
        n.textContent = String(Math.max(0, (parseInt(n.textContent, 10) || 0) - 1));
      });
    });
  }
  document.querySelectorAll("[data-confirm][data-url]").forEach((btn) => {
    btn.addEventListener("click", (e) => { e.preventDefault(); openConfirm(btn); });
  });
})();
