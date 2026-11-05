// Login gate. Loaded before app.js. Shows a login/setup overlay when the API answers 401.
(function () {
  const origFetch = window.fetch.bind(window);
  let overlay = null;

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

  async function showLogin() {
    if (overlay) return;
    const st = await j("GET", "/api/auth/status");
    if (!st.auth_enabled) return;
    const setup = st.needs_setup;
    overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;z-index:99999;background:#0f1115;display:flex;align-items:center;justify-content:center;font-family:system-ui,sans-serif";
    overlay.innerHTML = `
      <form id="auth-form" style="background:#1a1d24;padding:28px;border-radius:12px;width:320px;color:#e7e9ee;display:flex;flex-direction:column;gap:10px">
        <h2 style="margin:0 0 4px">${setup ? "Crear administrador" : "Iniciar sesión"}</h2>
        ${setup ? '<small style="opacity:.7">Primera vez: crea la cuenta de administrador.</small><input name="name" placeholder="Nombre" required>' : ""}
        <input name="email" type="email" placeholder="Email" required autocomplete="username">
        <input name="password" type="password" placeholder="Contraseña (mín. 8)" required minlength="8" autocomplete="${setup ? "new-password" : "current-password"}">
        <div id="auth-err" style="color:#ff6b6b;min-height:18px;font-size:13px"></div>
        <button style="padding:10px;border:0;border-radius:8px;background:#6c5ce7;color:#fff;cursor:pointer">${setup ? "Crear y entrar" : "Entrar"}</button>
      </form>`;
    overlay.querySelectorAll("input").forEach(i => i.style.cssText = "padding:10px;border-radius:8px;border:1px solid #333;background:#0f1115;color:#fff");
    document.body.appendChild(overlay);
    overlay.querySelector("#auth-form").onsubmit = async (e) => {
      e.preventDefault();
      const f = Object.fromEntries(new FormData(e.target));
      try {
        const user = await j("POST", setup ? "/api/auth/setup" : "/api/auth/login", f);
        localStorage.setItem("vpm_current_user_id", user.id);
        location.reload();
      } catch (err) { overlay.querySelector("#auth-err").textContent = err.message; }
    };
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
        row.innerHTML = `<span>👤 ${user.name}${user.role === "admin" ? " (admin)" : ""}</span> <a href="#" id="logout-link">Salir</a>`;
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
