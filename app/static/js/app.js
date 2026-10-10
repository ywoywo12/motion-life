/* Motion Life — shared client helpers. No external libraries. */
(function () {
  "use strict";
  const csrf = () => (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  async function api(method, url, body, isForm) {
    const opts = { method, headers: { "X-CSRF-Token": csrf(), Accept: "application/json" }, credentials: "same-origin" };
    if (body !== undefined) {
      if (isForm) opts.body = body;
      else { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    }
    let res;
    try { res = await fetch(url, opts); }
    catch (e) { throw { status: 0, error: { message: "تعذّر الاتصال بالخادم. تحقق من الشبكة — لم يتم حفظ العملية." } }; }
    let data = null;
    try { data = await res.json(); } catch (e) { /* non-json */ }
    if (!res.ok) {
      if (res.status === 401 && !url.endsWith("/auth/login")) { location.href = "/login?next=" + encodeURIComponent(location.pathname); }
      throw { status: res.status, error: (data && data.error) || { message: "خطأ غير متوقع (" + res.status + ")" } };
    }
    return data;
  }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  function renderError(err) {
    const e = (err && err.error) || { message: String(err) };
    let html = '<div class="notice danger" role="alert"><h3>⛔ ' + esc(e.message) + "</h3>";
    const d = e.details || {};
    if (d.blockers && d.blockers.length) html += "<ul>" + d.blockers.map(b => "<li>" + esc(b) + "</li>").join("") + "</ul>";
    if (d.candidates && d.candidates.length) {
      html += "<p>ملفات مشابهة:</p><ul>" + d.candidates.map(c => '<li><a href="/patients/' + esc(c.id) + '">' + esc(c.full_name) +
        " — " + esc(c.file_no) + (c.birth_date ? " — " + esc(c.birth_date) : "") + "</a></li>").join("") + "</ul>";
    }
    return html + "</div>";
  }

  function toast(msg, kind) {
    const t = document.createElement("div");
    t.className = "toast notice " + (kind || "ok");
    t.setAttribute("role", "status");
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  /* ---- serializer: supports names like a.b, items[0].title, multi checkboxes (data-multi) ---- */
  function setPath(obj, path, val) {
    const parts = path.replace(/\]/g, "").split(/\.|\[/);
    let o = obj;
    for (let i = 0; i < parts.length - 1; i++) {
      const k = parts[i], nextIsIdx = /^\d+$/.test(parts[i + 1]);
      if (o[k] === undefined) o[k] = nextIsIdx ? [] : {};
      o = o[k];
    }
    o[parts[parts.length - 1]] = val;
  }
  function serialize(form) {
    const out = {};
    const multis = {};
    form.querySelectorAll("input, select, textarea").forEach(el => {
      if (!el.name || el.disabled || el.closest("[hidden]")) return;
      if (el.type === "checkbox" && el.dataset.multi !== undefined) {
        multis[el.name] = multis[el.name] || [];
        if (el.checked) multis[el.name].push(el.value);
        return;
      }
      if (el.type === "radio") { if (el.checked) setPath(out, el.name, el.value); return; }
      if (el.type === "checkbox") { setPath(out, el.name, el.checked); return; }
      if (el.type === "file") return;
      let v = el.value;
      if (v === "") return;
      if (el.dataset.num !== undefined || el.type === "number") v = Number(v);
      setPath(out, el.name, v);
    });
    Object.keys(multis).forEach(k => setPath(out, k, multis[k]));
    const clean = o => Array.isArray(o) ? o.filter(x => x !== undefined).map(clean) :
      (o && typeof o === "object") ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, clean(v)])) : o;
    return clean(out);
  }

  function bindApiForms(root) {
    (root || document).querySelectorAll("form[data-api]").forEach(form => {
      if (form.dataset.bound) return;
      form.dataset.bound = "1";
      form.addEventListener("submit", async ev => {
        ev.preventDefault();
        const box = form.querySelector(".form-errors") || form.insertAdjacentElement("afterbegin", Object.assign(document.createElement("div"), { className: "form-errors" }));
        box.innerHTML = "";
        const btn = ev.submitter || form.querySelector("button[type=submit], button:not([type])");
        if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) return;
        let body = serialize(form);
        if (btn && btn.name) body[btn.name] = btn.value;
        if (form.dataset.extra) Object.assign(body, JSON.parse(form.dataset.extra));
        let isForm = false;
        if (form.enctype === "multipart/form-data") { body = new FormData(form); isForm = true; }
        if (btn) { btn.disabled = true; btn.dataset.label = btn.textContent; btn.textContent = "جارٍ الإرسال…"; }
        try {
          const res = await api(form.dataset.method || "POST", form.dataset.api, body, isForm);
          if (form.dataset.redirect) location.href = form.dataset.redirect.replace("{id}", (res && res.id) || "");
          else if (form.dataset.reload !== undefined) { sessionStorage.setItem("ml_toast", form.dataset.success || "تم الحفظ"); location.reload(); }
          else { toast(form.dataset.success || "تم الحفظ"); form.dispatchEvent(new CustomEvent("api:success", { detail: res })); }
        } catch (err) {
          box.innerHTML = renderError(err);
          if (err.error && err.error.code === "DUPLICATE_SUSPECTED") {
            const d = form.querySelector("[data-dup]"); if (d) d.hidden = false;
          }
          box.scrollIntoView({ block: "center", behavior: "smooth" });
        } finally {
          if (btn) { btn.disabled = false; btn.textContent = btn.dataset.label; }
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindApiForms(document);
    const t = sessionStorage.getItem("ml_toast");
    if (t) { sessionStorage.removeItem("ml_toast"); toast(t); }
    const lo = document.getElementById("logout");
    if (lo) lo.addEventListener("click", async () => { try { await api("POST", "/api/auth/logout", {}); } finally { location.href = "/login"; } });
    document.querySelectorAll("[data-copy-row]").forEach(b => b.addEventListener("click", () => {
      const tpl = document.getElementById(b.dataset.copyRow);
      const list = document.getElementById(b.dataset.target);
      const idx = list.children.length;
      const html = tpl.innerHTML.replace(/__i__/g, idx).replace(/__n__/g, idx + 1);
      list.insertAdjacentHTML("beforeend", html);
      list.lastElementChild.querySelector("input,select,textarea")?.focus();
    }));
    document.addEventListener("click", ev => {
      const rm = ev.target.closest("[data-remove-row]");
      if (!rm) return;
      const list = rm.closest("[data-rows]");
      rm.closest(".item-row").remove();
      [...list.children].forEach((row, i) => row.querySelectorAll("[name]").forEach(el => {
        el.name = el.name.replace(/\[\d+\]/, "[" + i + "]");
      }));
    });
    document.querySelectorAll("[data-toggle-target]").forEach(el => el.addEventListener("change", () => {
      const t = document.getElementById(el.dataset.toggleTarget);
      if (t) t.hidden = !el.checked;
    }));
  });

  window.ML = { api, esc, renderError, toast, serialize, bindApiForms };
})();
