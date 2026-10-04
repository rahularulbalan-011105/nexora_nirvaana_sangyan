/* ---------------------------------------------------------------------------
   NIRVAAN shell behaviour.

   Progressive enhancement only: every page works server-rendered without this
   file. It adds the online/offline indicator, toasts, accessibility
   preference application, the password meter and CSRF-aware fetch.

   Feature-specific interaction (voice recorder, pause timer, reflection
   stepper, batch uploader) lives in its own module and is loaded per page.
   ------------------------------------------------------------------------- */
(function () {
  "use strict";

  const CONFIG = window.NIRVAAN || {};

  /* --- small helpers ----------------------------------------------------- */

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  /** CSRF-aware JSON fetch. Never sends the token cross-origin. */
  async function api(path, options) {
    const opts = Object.assign({ method: "GET", headers: {} }, options || {});
    opts.headers = Object.assign(
      { Accept: "application/json" },
      opts.headers || {}
    );
    if (opts.method !== "GET" && opts.method !== "HEAD") {
      opts.headers["X-CSRF-Token"] = CONFIG.csrf || "";
    }
    if (opts.json !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
      delete opts.json;
    }
    opts.credentials = "same-origin";

    const response = await fetch(path, opts);
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (err) {
      data = { detail: text };
    }
    if (!response.ok) {
      const error = new Error((data && data.detail) || "Request failed");
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  /* --- toasts ------------------------------------------------------------ */

  const ICONS = {
    info: "info",
    success: "check_circle",
    warning: "warning",
    error: "error",
  };

  function toast(message, kind) {
    const host = $("[data-toast-host]");
    const template = $("[data-toast-template]");
    if (!host || !template) {
      return;
    }

    const node = template.content.firstElementChild.cloneNode(true);
    $("[data-toast-message]", node).textContent = message;

    const icon = $("[data-toast-icon]", node);
    icon.textContent = ICONS[kind] || ICONS.info;
    if (kind === "error") {
      icon.classList.replace("text-primary", "text-error");
    } else if (kind === "success") {
      icon.classList.replace("text-primary", "text-tertiary");
    }

    const dismiss = () => {
      node.style.opacity = "0";
      setTimeout(() => node.remove(), 200);
    };
    $("[data-toast-close]", node).addEventListener("click", dismiss);

    node.style.transition = "opacity .2s ease";
    host.appendChild(node);
    // Errors stay longer: they usually require the user to do something.
    setTimeout(dismiss, kind === "error" ? 8000 : 4500);
  }

  /* --- online / offline -------------------------------------------------- */

  function applyConnectivity() {
    const online = navigator.onLine;
    const banner = $("[data-offline-banner]");

    document.body.classList.toggle("is-offline", !online);
    if (banner) {
      banner.classList.toggle("hidden", online);
    }

    // Keep any status pill in the shell honest about the real state.
    $$("[data-connectivity-label]").forEach((el) => {
      el.textContent = online ? el.dataset.onlineText || "Online"
                              : el.dataset.offlineText || "Offline";
    });
  }

  window.addEventListener("online", () => {
    applyConnectivity();
    toast("Back online. Full assistant available again.", "success");
  });
  window.addEventListener("offline", () => {
    applyConnectivity();
    toast(
      "You are offline. Saved lessons, your journal and the pause timer still work.",
      "warning"
    );
  });

  /* --- accessibility preferences ---------------------------------------- */

  function applyPreferences() {
    // Server-rendered attributes are authoritative; this only mirrors the
    // contrast flag, which has no Tailwind utility equivalent.
    try {
      const stored = localStorage.getItem("nirvaan.contrast");
      if (stored === "high") {
        document.documentElement.setAttribute("data-contrast", "high");
      }
    } catch (err) {
      /* private mode: preference simply is not remembered */
    }
  }

  /* --- password visibility + strength meter ----------------------------- */

  function initPasswordControls() {
    $$("[data-password-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const input = document.getElementById(button.dataset.passwordToggle);
        if (!input) return;
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      });
    });

    const input = $("[data-password-meter-input]");
    const meter = $("[data-password-meter]");
    if (!input || !meter) return;

    const bars = $$("[data-meter-bar]", meter);
    const label = $("[data-meter-label]", meter);

    // Mirrors app/security/passwords.py: length first, then variety. The
    // server remains the authority - this is only guidance while typing.
    function score(value) {
      if (!value) return { level: 0, text: "Enter a password", colour: "" };
      if (value.length < 10) {
        return { level: 1, text: "Too short", colour: "bg-rose-500" };
      }
      const variety =
        (/[a-z]/.test(value) ? 1 : 0) +
        (/[A-Z]/.test(value) ? 1 : 0) +
        (/\d/.test(value) ? 1 : 0) +
        (/[^\w\s]/.test(value) ? 1 : 0);
      if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
        return { level: 1, text: "Add a letter and a number", colour: "bg-rose-500" };
      }
      if (value.length >= 16 || variety >= 3) {
        return { level: 3, text: "Strong", colour: "bg-emerald-500" };
      }
      return { level: 2, text: "Reasonable", colour: "bg-amber-500" };
    }

    input.addEventListener("input", () => {
      const result = score(input.value);
      bars.forEach((bar, index) => {
        bar.className = "h-1 flex-1 rounded-full " +
          (index < result.level ? result.colour : "bg-slate-200");
      });
      label.textContent = result.text;
      label.className = "font-medium " +
        (result.level === 3 ? "text-emerald-600"
          : result.level === 2 ? "text-amber-600"
          : result.level === 1 ? "text-rose-600" : "text-slate-500");
    });
  }

  /* --- language selector ------------------------------------------------- */

  function initLanguageSelector() {
    $$('[data-action="open-language"]').forEach((trigger) => {
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        const existing = $("[data-language-menu]");
        if (existing) {
          existing.remove();
          return;
        }

        const menu = document.createElement("div");
        menu.setAttribute("data-language-menu", "");
        menu.className =
          "absolute right-0 top-full mt-2 w-44 py-1.5 rounded-2xl " +
          "bg-surface-container-lowest shadow-[0_20px_40px_-8px_rgba(15,23,42,0.16)] " +
          "border border-outline-variant/40 z-50";

        (CONFIG.languages || [
          { code: "en", native: "English" },
          { code: "hi", native: "हिन्दी" },
          { code: "ta", native: "தமிழ்" },
        ]).forEach((lang) => {
          const form = document.createElement("form");
          form.method = "POST";
          form.action = "/api/language";
          form.innerHTML =
            '<input type="hidden" name="_csrf" value="' + (CONFIG.csrf || "") + '">' +
            '<input type="hidden" name="language" value="' + lang.code + '">' +
            '<input type="hidden" name="next" value="' +
              window.location.pathname + '">' +
            '<button type="submit" class="w-full text-left px-space-md py-2 ' +
              'font-label-md text-label-md hover:bg-surface-container ' +
              (lang.code === CONFIG.lang
                ? 'text-primary font-semibold'
                : 'text-on-surface') +
              '">' + lang.native + "</button>";
          menu.appendChild(form);
        });

        const anchor = trigger.parentElement;
        if (anchor) {
          anchor.style.position = "relative";
          anchor.appendChild(menu);
        }
      });
    });

    document.addEventListener("click", (event) => {
      const menu = $("[data-language-menu]");
      if (menu && !menu.contains(event.target) &&
          !event.target.closest('[data-action="open-language"]')) {
        menu.remove();
      }
    });
  }

  /* --- service worker ---------------------------------------------------- */

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    // Only over HTTPS or localhost; the browser rejects it otherwise anyway.
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/static/js/sw.js", { scope: "/" })
        .catch((err) => console.warn("NIRVAAN: service worker not registered", err));
    });
  }

  /* --- boot -------------------------------------------------------------- */

  function init() {
    applyConnectivity();
    applyPreferences();
    initPasswordControls();
    initLanguageSelector();
    registerServiceWorker();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Exposed for the per-feature modules.
  window.NIRVAAN = Object.assign(CONFIG, { api, toast, $, $$ });
})();
