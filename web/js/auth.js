// Login gate. Loaded before app.js. Shows a login/setup overlay when the API answers 401.
(function () {
  const origFetch = window.fetch.bind(window);
  let overlay = null;
  let showing = false;

  window.fetch = async (...args) => {
    const res = await origFetch(...args);
    const url = String(args[0] && args[0].url || args[0]);
    if (res.status === 401 && !url.includes("/api/auth/")) showLogin();
    return res;
  };

  async function j(method, url, body) {
    const res = await origFetch(url, {
      method, headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || res.statusText);
    return data;
  }

  const INPUT_CSS = "padding:10px;border-radius:8px;border:1px solid #333;background:#0f1115;color:#fff";
  const BTN_CSS = "padding:10px;border:0;border-radius:8px;background:#6c5ce7;color:#fff;cursor:pointer";
  const CARD_CSS = "text-align:left;padding:14px;border-radius:10px;border:1px solid #333;background:#0f1115;color:#e7e9ee;cursor:pointer";

  function mount(html) {
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.style.cssText = "position:fixed;inset:0;z-index:99999;background:#0f1115;display:flex;align-items:center;justify-content:center;font-family:system-ui,sans-serif";
      document.body.appendChild(overlay);
    }
    overlay.innerHTML = `<div style="background:#1a1d24;padding:28px;border-radius:12px;width:340px;max-width:92vw;color:#e7e9ee;display:flex;flex-direction:column;gap:10px">${html}</div>`;
    overlay.querySelectorAll("input").forEach(i => i.style.cssText = INPUT_CSS);
    return overlay;
  }

  const MODE_TEXT = {
    local: ["Local", "Solo yo, sin cuentas ni contraseña."],
    team: ["Equipo", "Pocas personas con cuenta. Todos con los mismos permisos, sin administrador."],
    studio: ["Estudio", "Con administrador y permisos por proyecto (lector, editor, propietario)."],
  };

  function showModeChooser() {
    mount(`<h2 style="margin:0">¿Cómo vas a usar Studio Manager?</h2>
      ${Object.entries(MODE_TEXT).map(([k, [t, d]]) => `<button data-mode="${k}" style="${CARD_CSS}"><b>${t}</b><br><small style="opacity:.7">${d}</small></button>`).join("")}`);
    overlay.querySelectorAll("[data-mode]").forEach(btn => btn.onclick = async () => {
      const mode = btn.dataset.mode;
      if (mode === "local") {
        try { await j("POST", "/api/auth/mode", { mode }); location.reload(); }
        catch (err) { alert(err.message); }
      } else showForm(mode, true);
    });
  }

  function showForm(mode, setup) {
    const title = setup ? (mode === "studio" ? "Crear administrador" : "Crear la primera cuenta") : "Iniciar sesión";
    mount(`<form id="auth-form" style="display:flex;flex-direction:column;gap:10px">
        <h2 style="margin:0 0 4px">${title}</h2>
        ${setup ? `<small style="opacity:.7">Modo ${MODE_TEXT[mode][0]}. ${mode === "studio" ? "Esta cuenta será la del administrador." : "Después podrás añadir al resto del equipo en 👥 Equipo."}</small><input name="name" placeholder="Nombre" required>` : ""}
        <input name="email" type="email" placeholder="Email" required autocomplete="username">
        <input name="password" type="password" placeholder="Contraseña (mín. 8)" required minlength="8" autocomplete="${setup ? "new-password" : "current-password"}">
        <div id="auth-err" style="color:#ff6b6b;min-height:18px;font-size:13px"></div>
        <button style="${BTN_CSS}">${setup ? "Crear y entrar" : "Entrar"}</button>
        ${setup ? '<a href="#" id="auth-back" style="color:#a29bfe;font-size:13px">← Cambiar de modo</a>' : ""}
      </form>`);
    const back = overlay.querySelector("#auth-back");
    if (back) back.onclick = (e) => { e.preventDefault(); showModeChooser(); };
    overlay.querySelector("#auth-form").onsubmit = async (e) => {
      e.preventDefault();
      const f = Object.fromEntries(new FormData(e.target));
      if (setup) f.mode = mode;
      try {
        const user = await j("POST", setup ? "/api/auth/setup" : "/api/auth/login", f);
        localStorage.setItem("vpm_current_user_id", user.id);
        location.reload();
      } catch (err) { overlay.querySelector("#auth-err").textContent = err.message; }
    };
  }

  async function showLogin() {
    if (showing) return;  // set synchronously: several parallel 401s must open only one overlay
    showing = true;
    const st = await j("GET", "/api/auth/status");
    if (!st.auth_enabled) { showing = false; return; }
    if (st.needs_setup) {
      if (st.mode) showForm(st.mode, true);   // mode fixed by the server (VPM_MODE)
      else showModeChooser();
    } else showForm(st.mode, false);
  }

  async function init() {
    try {
      const st = await j("GET", "/api/auth/status");
      if (!st.auth_enabled) return;
      const me = await origFetch("/api/auth/me");
      if (!me.ok) return showLogin();
      const user = await me.json();
      localStorage.setItem("vpm_current_user_id", user.id);
      // Real identity replaces the trust-based "Soy:" selector.
      const row = document.querySelector(".whoami-row");
      if (row) {
        row.innerHTML = `<span>👤 ${user.name}${st.mode === "studio" && user.role === "admin" ? " (admin)" : ""}</span> <a href="#" id="logout-link" style="color:#a29bfe">Salir</a>`;
        row.querySelector("#logout-link").onclick = async (e) => {
          e.preventDefault();
          await j("POST", "/api/auth/logout");
          location.reload();
        };
      }
    } catch (e) { /* offline or auth disabled */ }
  }
  document.addEventListener("DOMContentLoaded", init);
})();
