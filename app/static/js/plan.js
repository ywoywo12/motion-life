/* Plan editor: exercise library + device program pickers that append editable plan items. */
(function () {
  "use strict";
  const pk = document.getElementById("picker");
  if (!pk) return;
  let DATA = null;
  const $ = (sel, root) => (root || pk).querySelector(sel);
  const esc = s => ML.esc(s);

  function addItem(pre) {
    const tpl = document.getElementById("item-tpl");
    const list = document.getElementById("items");
    const idx = list.children.length;
    list.insertAdjacentHTML("beforeend", tpl.innerHTML.replace(/__i__/g, idx));
    const row = list.lastElementChild;
    const set = (f, v) => { const el = row.querySelector(`[name="items[${idx}].${f}"]`); if (el && v != null) el.value = v; };
    Object.entries(pre.fields).forEach(([k, v]) => set(k, v));
    if (pre.thumb) { const im = row.querySelector("[data-thumb]"); im.src = pre.thumb; im.hidden = false; }
    if (pre.progLabel) { const b = row.querySelector("[data-prog-label]"); b.textContent = "برنامج الجهاز: " + pre.progLabel; b.hidden = false; }
    row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    ML.toast("أُضيف: " + pre.fields.title + " — احفظ المسودة لتثبيت التغيير", "ok");
  }

  function renderEx() {
    const q = $('[data-f="q"]').value.trim().toLowerCase();
    const r = $('[data-f="region"]').value, t = $('[data-f="type"]').value;
    const rows = DATA.exercises.filter(e => (!r || e.region === r) && (!t || e.type === t) &&
      (!q || e.name_ar.includes(q) || e.name_en.toLowerCase().includes(q)));
    $('[data-list="ex"]').innerHTML = rows.length ? rows.map(e => `
      <div class="pick-row"><img src="/library/figure/${esc(e.code)}.svg" width="64" height="59" alt="" loading="lazy">
        <div class="meta"><b>${esc(e.name_ar)}</b><span class="small muted">${esc(e.region_ar)} · ${esc(e.type_ar)} · ${esc(e.dosage)}</span></div>
        <button type="button" data-add-ex="${esc(e.code)}">＋ إضافة</button></div>`).join("")
      : '<p class="empty">لا توجد تمارين مطابقة.</p>';
  }
  function renderDev() {
    const q = $('[data-f="dq"]').value.trim().toLowerCase();
    $('[data-list="dev"]').innerHTML = DATA.devices.map(d => {
      const progs = d.programs.filter(p => !q || p.ar.includes(q) || p.en.toLowerCase().includes(q));
      if (q && !progs.length) return "";
      const body = d.programs.length
        ? progs.map(p => `<div class="prog-row"><span>${esc(p.ar)}<br><span class="ltr small muted">${esc(p.en)}</span></span>
            <button type="button" data-add-prog="${esc(p.code)}" data-dev="${esc(d.code)}">＋ إضافة</button></div>`).join("")
        : `<div class="prog-row"><span class="small muted">${esc(d.status_note)}</span><button type="button" data-add-dev="${esc(d.code)}">＋ إضافة الجهاز (إعداد يدوي)</button></div>`;
      return `<details ${q ? "open" : ""}><summary class="dev-head"><span><b>${esc(d.name_ar)}</b><br><span class="ltr small muted">${esc(d.name)}</span></span>
              <span class="badge">${progs.length || d.programs.length}</span></summary>${body}</details>`;
    }).join("");
  }

  pk.addEventListener("click", ev => {
    const tab = ev.target.closest("[data-tab]");
    if (tab) {
      pk.querySelectorAll("[data-tab]").forEach(b => b.setAttribute("aria-selected", b === tab ? "true" : "false"));
      pk.querySelectorAll("[data-pane]").forEach(p => { p.hidden = p.dataset.pane !== tab.dataset.tab; });
      return;
    }
    const ex = ev.target.closest("[data-add-ex]");
    if (ex) {
      const e = DATA.exercises.find(x => x.code === ex.dataset.addEx);
      addItem({ thumb: `/library/figure/${e.code}.svg`, fields: { category: $('[data-f="as"]').value, title: e.name_ar,
        method: e.steps, dosage: e.dosage, precautions: e.caution, exercise_code: e.code, target: e.type_ar } });
      return;
    }
    const pr = ev.target.closest("[data-add-prog]");
    if (pr) {
      const d = DATA.devices.find(x => x.code === pr.dataset.dev);
      const p = d.programs.find(x => x.code === pr.dataset.addProg);
      addItem({ progLabel: `${p.ar} — ${p.en}`, fields: { category: "DEVICE", title: `${d.name_ar}: ${p.ar}`, equipment_code: d.code,
        program_code: p.code, dosage: "برنامج الجهاز المسبق (" + p.en + ") — يضبط المختص الشدة/الزمن حسب الحالة",
        method: d.name } });
      return;
    }
    const dv = ev.target.closest("[data-add-dev]");
    if (dv) {
      const d = DATA.devices.find(x => x.code === dv.dataset.addDev);
      addItem({ fields: { category: "DEVICE", title: d.name_ar, equipment_code: d.code, method: d.name } });
    }
  });
  pk.addEventListener("input", ev => { if (ev.target.dataset.f === "dq") renderDev(); else if (ev.target.dataset.f) renderEx(); });
  pk.addEventListener("change", ev => { if (["region", "type"].includes(ev.target.dataset.f)) renderEx(); });

  ML.api("GET", pk.dataset.src).then(d => {
    DATA = d;
    $('[data-f="region"]').insertAdjacentHTML("beforeend", d.regions.map(r => `<option value="${r.code}">${esc(r.ar)}</option>`).join(""));
    $('[data-f="type"]').insertAdjacentHTML("beforeend", d.types.map(t => `<option value="${t.code}">${esc(t.ar)}</option>`).join(""));
    if (pk.dataset.region) $('[data-f="region"]').value = pk.dataset.region;
    renderEx(); renderDev();
  }).catch(err => { $('[data-list="ex"]').innerHTML = ML.renderError(err); });
})();
