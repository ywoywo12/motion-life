/* Questionnaire cards: branching (show_if), per-answer autosave with honest save state,
   conflict detection (base_id) and local recovery of unsaved answers. */
(function () {
  "use strict";
  const root = document.querySelector("[data-qform]");
  if (!root) return;
  const saveUrl = root.dataset.saveUrl;
  const ctx = JSON.parse(root.dataset.ctx || "{}");
  const storeKey = "ml_pending:" + root.dataset.key;
  const bar = document.getElementById("savebar");
  const cards = {};
  root.querySelectorAll(".q[data-code]").forEach(c => { cards[c.dataset.code] = c; });
  let pending = {};
  let timer = null, inflight = false;

  function readAnswer(code) {
    const c = cards[code];
    const st = c.querySelector('input[name="s:' + code + '"]:checked');
    const note = (c.querySelector('[name="n:' + code + '"]') || {}).value || "";
    if (st) return { status: st.value, value: null, note };
    const type = c.dataset.type;
    let value = null;
    if (type === "tri" || type === "choice" || type === "scale010") {
      const r = c.querySelector('input[name="v:' + code + '"]:checked');
      value = r ? (type === "scale010" ? Number(r.value) : r.value) : null;
    } else if (type === "multi") {
      const vs = [...c.querySelectorAll('input[name="v:' + code + '"]:checked')].map(x => x.value);
      value = vs.length ? vs : null;
    } else {
      const el = c.querySelector('[name="v:' + code + '"]');
      value = el && el.value.trim() !== "" ? (type === "number" ? Number(el.value) : el.value) : null;
    }
    return value === null ? { status: "NOT_ASKED", value: null, note } : { status: "ANSWERED", value, note };
  }
  function answersMap() {
    const m = {};
    Object.keys(cards).forEach(k => { m[k] = readAnswer(k); });
    return m;
  }
  function val(m, code) { const a = m[code]; return a && a.status === "ANSWERED" ? a.value : null; }
  function evalCond(cond, m) {
    if (!cond) return true;
    if (cond.all) return cond.all.every(c => evalCond(c, m));
    if (cond.any) return cond.any.some(c => evalCond(c, m));
    if (cond.sex) return ctx.sex === cond.sex;
    const v = val(m, cond.q);
    if ("answered" in cond) return (v !== null && !(Array.isArray(v) && !v.length)) === !!cond.answered;
    if (v === null) return false;
    if ("eq" in cond) return v === cond.eq;
    if ("in" in cond) return cond.in.includes(v);
    if ("includes" in cond) return Array.isArray(v) && v.includes(cond.includes);
    if ("includes_any" in cond) return Array.isArray(v) && cond.includes_any.some(x => v.includes(x));
    if ("not_in" in cond) return Array.isArray(v) ? v.length > 0 && !v.every(x => cond.not_in.includes(x)) : !cond.not_in.includes(v);
    if ("gte" in cond) return typeof v === "number" && v >= cond.gte;
    return true;
  }
  function refresh() {
    let m = answersMap();
    for (let i = 0; i < 3; i++) {
      Object.values(cards).forEach(c => {
        const cond = c.dataset.showIf ? JSON.parse(c.dataset.showIf) : null;
        c.hidden = !evalCond(cond, m);
      });
      m = answersMap();
    }
    const counts = {};
    Object.values(cards).forEach(c => {
      const a = m[c.dataset.code];
      const miss = !c.hidden && c.dataset.required === "1" && !(a.status === "ANSWERED" || a.status === "NOT_APPLICABLE");
      c.classList.toggle("missing", miss);
      c.classList.toggle("yes", a.status === "ANSWERED" && a.value === "YES");
      const flag = c.querySelector(".miss-flag");
      if (flag) flag.hidden = !miss;
      const sec = c.dataset.section;
      counts[sec] = (counts[sec] || 0) + (miss ? 1 : 0);
    });
    document.querySelectorAll("[data-step-count]").forEach(el => {
      const secs = el.dataset.stepCount.split(",");
      const n = secs.reduce((s, k) => s + (counts[k] || 0), 0);
      el.textContent = n ? n + " ناقص" : "مكتمل";
      el.closest("a")?.classList.toggle("done", !n);
    });
    document.querySelectorAll("[data-section-wrap]").forEach(w => {
      const visible = [...w.querySelectorAll(".q[data-code]")].some(c => !c.hidden);
      w.hidden = !visible && w.dataset.hideEmpty !== undefined;
    });
  }

  function setBar(state, text, retry) {
    if (!bar) return;
    bar.dataset.state = state;
    bar.querySelector(".txt").textContent = text;
    bar.querySelector("button").hidden = !retry;
  }
  function backup() {
    try {
      if (Object.keys(pending).length) localStorage.setItem(storeKey, JSON.stringify({ at: Date.now(), items: pending }));
      else localStorage.removeItem(storeKey);
    } catch (e) { /* storage unavailable: in-memory queue still retried */ }
  }
  function queue(code) {
    const c = cards[code];
    const a = readAnswer(code);
    const source = (document.getElementById("q-source") || {}).value || "THERAPIST_ENTRY";
    pending[code] = { code, status: a.status, value: a.value, note: a.note || null, source, base_id: c.dataset.baseId || null };
    backup();
    setBar("dirty", "تعديلات غير محفوظة (" + Object.keys(pending).length + ")…", false);
    clearTimeout(timer);
    timer = setTimeout(save, 700);
  }

  async function save() {
    if (inflight) { clearTimeout(timer); timer = setTimeout(save, 400); return; }
    const items = Object.values(pending);
    if (!items.length) return;
    inflight = true;
    const sent = {};
    items.forEach(i => { sent[i.code] = i; });
    setBar("saving", "جارٍ الحفظ…", false);
    try {
      const res = await ML.api("POST", saveUrl, { items });
      Object.keys(sent).forEach(code => { if (pending[code] === sent[code]) delete pending[code]; });
      Object.entries(res.answers || {}).forEach(([code, a]) => { if (cards[code]) cards[code].dataset.baseId = a.id; });
      Object.keys(cards).forEach(code => { if (!(res.answers || {})[code]) cards[code].dataset.baseId = ""; });
      (res.conflicts || []).forEach(cf => showConflict(cf));
      backup();
      const time = new Date().toLocaleTimeString("ar-SY-u-nu-latn", { hour: "2-digit", minute: "2-digit" });
      if ((res.conflicts || []).length) setBar("failed", "بعض الإجابات عدّلها مستخدم آخر — راجع البطاقات المعلّمة", false);
      else setBar("saved", "حُفظ ✓ " + time, false);
      if (res.safety) renderSafety(res.safety);
    } catch (err) {
      const msg = (err.error && err.error.message) || "فشل الحفظ";
      setBar("failed", "فشل الحفظ — لم تُحفظ " + items.length + " إجابة: " + msg, true);
      if (err.status === 422) { // validation: show on the card, drop it from the queue to avoid an endless retry
        items.forEach(i => { if (pending[i.code] === sent[i.code]) delete pending[i.code]; });
        ML.toast(msg, "danger");
        backup();
      }
    } finally {
      inflight = false;
      if (Object.keys(pending).length && bar.dataset.state !== "failed") { clearTimeout(timer); timer = setTimeout(save, 500); }
    }
  }

  function showConflict(cf) {
    const c = cards[cf.code];
    if (!c) return;
    let box = c.querySelector(".conflict");
    if (!box) { box = document.createElement("div"); box.className = "conflict notice warn small"; c.querySelector(".q-body").appendChild(box); }
    const cur = cf.current;
    box.innerHTML = "⚠ عدّل " + ML.esc(cur ? cur.recorded_by : "مستخدم آخر") + " هذه الإجابة قبلك. القيمة المحفوظة الآن: <b>" +
      ML.esc(cur ? (cur.status === "ANSWERED" ? JSON.stringify(cur.value) : cur.status) : "—") +
      "</b>. أعد تحميل الصفحة لرؤية أحدث البيانات ثم عدّل إن لزم.";
    c.dataset.baseId = cur ? cur.id : "";
    delete pending[cf.code];
  }

  const SAFETY_TXT = { NOT_CONFIRMED: "◌ لم يتأكد بعد", INCOMPLETE: "◌ غير مكتمل", EMERGENCY: "⛔ مسار إسعافي — إحالة فورية",
    NEEDS_REVIEW: "⚠ يحتاج مراجعة/تقييم إضافي", NO_FLAGS_REPORTED: "✓ لا توجد مؤشرات مبلّغ عنها" };
  function renderSafety(s) {
    const box = document.getElementById("safety-live");
    if (!box) return;
    const cls = s.status === "EMERGENCY" ? "danger" : s.status === "NEEDS_REVIEW" ? "warn" : s.status === "NO_FLAGS_REPORTED" ? "ok" : "";
    let h = '<div class="notice ' + cls + '" role="status" aria-live="polite"><h3>فرز السلامة: ' + SAFETY_TXT[s.status] + "</h3>";
    if (s.triggered.length) h += "<ul>" + s.triggered.map(t => "<li><b>" + ML.esc(t.message) + "</b><br><span class='small'>الإجراء: " +
      ML.esc(t.action) + " — بسبب: " + t.because.map(b => ML.esc(b.text)).join("، ") + "</span></li>").join("") + "</ul>";
    if (s.missing.length) h += "<p class='small'>لم يُحسم بعد (" + s.missing.length + "): " + s.missing.slice(0, 6).map(m => ML.esc(m.text) + " (" + ML.esc(m.reason) + ")").join("؛ ") + (s.missing.length > 6 ? "…" : "") + "</p>";
    if (s.status === "NO_FLAGS_REPORTED") h += "<p class='small'>يسمح باستكمال التقييم، وليس تصريحاً آلياً بسلامة كل الإجراءات أو الأجهزة.</p>";
    if (s.status === "EMERGENCY") h += "<p><b>أوقف الفحص الاستفزازي والعلاج الروتيني. وثّق قرار الإحالة في خطوة «الملخص».</b></p>";
    box.innerHTML = h + "</div>";
  }

  root.addEventListener("change", ev => {
    const el = ev.target;
    const c = el.closest(".q[data-code]");
    if (!c) return;
    const code = c.dataset.code;
    if (el.name === "s:" + code && el.checked) {
      c.querySelectorAll('[name="v:' + code + '"]').forEach(x => { if (x.type === "radio" || x.type === "checkbox") x.checked = false; else x.value = ""; });
    } else if (el.name === "v:" + code) {
      c.querySelectorAll('input[name="s:' + code + '"]').forEach(x => { x.checked = false; });
      const ex = c.dataset.exclusive;
      if (ex && el.type === "checkbox" && el.checked) {
        c.querySelectorAll('input[name="v:' + code + '"]').forEach(x => {
          if (el.value === ex ? x.value !== ex : x.value === ex) x.checked = false;
        });
      }
    }
    refresh();
    queue(code);
  });
  root.addEventListener("click", ev => {
    // allow un-checking a status radio by clicking it again
    const el = ev.target;
    if (el.type === "radio" && el.name.startsWith("s:") && el.dataset.was === "1") {
      el.checked = false; el.dataset.was = "0"; refresh(); queue(el.name.slice(2));
    } else if (el.type === "radio" && el.name.startsWith("s:")) {
      root.querySelectorAll('input[name="' + el.name + '"]').forEach(x => { x.dataset.was = "0"; });
      el.dataset.was = "1";
    }
  });
  if (bar) bar.querySelector("button").addEventListener("click", () => { setBar("saving", "إعادة المحاولة…", false); save(); });
  window.addEventListener("beforeunload", ev => { if (Object.keys(pending).length || inflight) { ev.preventDefault(); ev.returnValue = ""; } });

  // recovery of unsaved answers from a previous crash / lost connection
  try {
    const raw = localStorage.getItem(storeKey);
    if (raw) {
      const saved = JSON.parse(raw);
      const n = Object.keys(saved.items || {}).length;
      const box = document.getElementById("recover");
      if (n && box) {
        box.hidden = false;
        box.querySelector(".n").textContent = n;
        box.querySelector("[data-restore]").addEventListener("click", () => {
          pending = saved.items;
          Object.values(pending).forEach(it => applyToInputs(it));
          refresh(); box.hidden = true; save();
        });
        box.querySelector("[data-discard]").addEventListener("click", () => { localStorage.removeItem(storeKey); box.hidden = true; });
      }
    }
  } catch (e) { /* ignore */ }

  function applyToInputs(it) {
    const c = cards[it.code];
    if (!c) return;
    c.querySelectorAll('[name="v:' + it.code + '"]').forEach(x => {
      if (x.type === "radio") x.checked = it.status === "ANSWERED" && String(x.value) === String(it.value);
      else if (x.type === "checkbox") x.checked = it.status === "ANSWERED" && Array.isArray(it.value) && it.value.includes(x.value);
      else x.value = it.status === "ANSWERED" ? it.value : "";
    });
    c.querySelectorAll('input[name="s:' + it.code + '"]').forEach(x => { x.checked = x.value === it.status; });
    const n = c.querySelector('[name="n:' + it.code + '"]');
    if (n) n.value = it.note || "";
  }

  refresh();
  if (root.dataset.safety) renderSafety(JSON.parse(root.dataset.safety));
})();
