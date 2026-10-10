/* Motion Life — نظام مبسط لملف المريض والخطة العلاجية */
(function () {
'use strict';
const D = window.ML_DATA;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const REG = Object.fromEntries(D.regions.map(r => [r.code, r.ar]));
const TYP = Object.fromEntries(D.types.map(t => [t.code, t.ar]));
const EXM = Object.fromEntries(D.exercises.map(e => [e.code, e]));
const DEVM = Object.fromEntries(D.devices.map(d => [d.code, d]));
const today = () => new Date().toISOString().slice(0, 10);

/* ---------- storage (safe) ---------- */
const store = {
  get(k, def) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : def; } catch (e) { return def; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { toast('تعذّر الحفظ في المتصفح'); return false; } }
};
const sess = {
  get() { try { return sessionStorage.getItem('ml_in') === '1'; } catch (e) { return window.__in === true; } },
  set(v) { try { v ? sessionStorage.setItem('ml_in', '1') : sessionStorage.removeItem('ml_in'); } catch (e) {} window.__in = v; }
};
async function hash(s) {
  try {
    const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('motionlife|' + s));
    return Array.from(new Uint8Array(b)).map(x => x.toString(16).padStart(2, '0')).join('');
  } catch (e) { return 'p:' + s; }
}
const DEFAULT_USER = 'admin', DEFAULT_PASS = 'Motion2026';

let patients = store.get('ml_patients', []);
const savePatients = () => store.set('ml_patients', patients);
const getP = id => patients.find(p => p.id === id);

function newPatient() {
  const nums = patients.map(p => parseInt(p.fileNo, 10)).filter(n => !isNaN(n));
  return {
    id: 'p' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    created: new Date().toISOString(),
    serial: String(patients.length + 1), shelf: '', cabinet: '', fileNo: String((nums.length ? Math.max(...nums) : 0) + 1),
    name: '', age: '', gender: '', phone: '', job: '', evalDate: today(),
    complaint: '', chronic: '', history: '', clinical: '',
    symptoms: '', pain: null, painType: [], duration: '',
    strength: '', limits: '', notes: '', therapist: '',
    startDate: today(), plan: '', devices: [], exercises: [],
    sessions: Array.from({ length: 22 }, () => ({ date: '', note: '', by: '' })),
    eval6: '', eval12: '', agreedSessions: '', agreedTotal: '',
    payments: Array.from({ length: 4 }, () => ({ amount: '', date: '' }))
  };
}

/* ---------- ui helpers ---------- */
let toastT;
function toast(msg) { const t = $('#toast'); t.textContent = msg; t.classList.remove('hidden'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.add('hidden'), 2200); }
function openModal(html) { $('#modalBox').innerHTML = html; $('#modal').classList.remove('hidden'); document.body.style.overflow = 'hidden'; }
function closeModal() { $('#modal').classList.add('hidden'); document.body.style.overflow = ''; }
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
const fig = code => 'figures/' + (EXM[code] ? EXM[code].fig : code) + '.svg';
const num = v => { const n = parseFloat(String(v).replace(/[^\d.]/g, '')); return isNaN(n) ? 0 : n; };
const fmt = n => n.toLocaleString('en-US');

/* ---------- router ---------- */
const go = h => { location.hash = h; };
window.addEventListener('hashchange', render);

function shell(active, inner) {
  const nav = [['home', 'الرئيسية'], ['patients', 'المرضى'], ['library', 'مكتبة التمارين'], ['devices', 'الأجهزة والبروتوكولات'], ['settings', 'الإعدادات']];
  return `<header class="topbar"><div class="topbar-in">
    <div class="brand" data-go="home"><b>Motion Life</b><small>مركز العلاج الفيزيائي وإعادة التأهيل</small></div>
    <nav class="nav">${nav.map(([k, t]) => `<button data-go="${k}" class="${active === k ? 'on' : ''}">${t}</button>`).join('')}</nav>
  </div></header><main class="wrap">${inner}</main>`;
}

function render() {
  const app = $('#app');
  if (!sess.get()) { app.innerHTML = loginView(); bindLogin(); return; }
  const h = (location.hash || '#home').slice(1).split('/');
  closeModal();
  if (h[0] === 'p' && getP(h[1])) { app.innerHTML = shell('patients', patientView(getP(h[1]), h[2] || '1')); bindPatient(getP(h[1]), h[2] || '1'); }
  else if (h[0] === 'patients') { app.innerHTML = shell('patients', patientsView()); bindPatients(); }
  else if (h[0] === 'library') { app.innerHTML = shell('library', libraryView()); bindLibrary(); }
  else if (h[0] === 'devices') { app.innerHTML = shell('devices', devicesView()); bindDevices(); }
  else if (h[0] === 'settings') { app.innerHTML = shell('settings', settingsView()); bindSettings(); }
  else { app.innerHTML = shell('home', homeView()); }
  $$('[data-go]').forEach(b => b.addEventListener('click', () => go(b.dataset.go)));
  window.scrollTo(0, 0);
}

/* ---------- login ---------- */
function loginView() {
  return `<div class="login"><form class="login-box" id="lf">
    <h1>Motion Life</h1><p>نظام ملف المريض والخطة العلاجية</p>
    <label for="lu">اسم المستخدم</label><input id="lu" autocomplete="username" value="">
    <label for="lp">كلمة المرور</label><input id="lp" type="password" autocomplete="current-password">
    <button class="btn big" style="width:100%;margin-top:20px">دخول</button>
    <div class="err" id="lerr"></div></form></div>`;
}
function bindLogin() {
  $('#lu').focus();
  $('#lf').addEventListener('submit', async e => {
    e.preventDefault();
    const auth = store.get('ml_auth', null);
    const u = $('#lu').value.trim(), p = $('#lp').value;
    const ok = auth ? (u === auth.user && (await hash(p)) === auth.hash) : (u === DEFAULT_USER && p === DEFAULT_PASS);
    if (ok) { sess.set(true); if (!location.hash || location.hash === '#login') location.hash = '#home'; render(); }
    else $('#lerr').textContent = 'اسم المستخدم أو كلمة المرور غير صحيحة';
  });
}

/* ---------- home ---------- */
function homeView() {
  const recent = [...patients].sort((a, b) => (b.updated || b.created).localeCompare(a.updated || a.created)).slice(0, 5);
  return `<div class="hello">أهلاً بك 👋 ماذا تريد أن تفعل؟</div>
  <div class="tiles">
    <div class="tile main" id="newP"><div class="ic">➕</div><div><b>مريض جديد</b><span>افتح ملفاً وابدأ التقييم</span></div></div>
    <div class="tile" data-go="patients"><div class="ic">📁</div><div><b>ملفات المرضى</b><span>${patients.length} ملف محفوظ</span></div></div>
    <div class="tile" data-go="library"><div class="ic">🏃</div><div><b>مكتبة التمارين</b><span>${D.exercises.length} تمريناً مع رسوم توضيحية</span></div></div>
    <div class="tile" data-go="devices"><div class="ic">⚡</div><div><b>الأجهزة والبروتوكولات</b><span>${D.devices.length} جهازاً وبرامجها</span></div></div>
  </div>
  ${recent.length ? `<h3 style="color:var(--navy);margin:26px 0 6px">آخر الملفات</h3><div class="plist">${recent.map(pCard).join('')}</div>` : ''}`;
}
document.addEventListener('click', e => {
  if (e.target.closest('#newP')) { const p = newPatient(); patients.push(p); savePatients(); go('p/' + p.id + '/1'); }
  const pc = e.target.closest('.pcard'); if (pc) go('p/' + pc.dataset.id + '/1');
});
function pCard(p) {
  const ini = (p.name || '؟').trim().charAt(0);
  const done = p.sessions.filter(s => s.date).length;
  return `<div class="pcard" data-id="${p.id}"><div class="av">${esc(ini)}</div><div style="flex:1">
    <b>${esc(p.name || 'بدون اسم')}</b><div class="m">رقم الملف: ${esc(p.fileNo)} · ${esc(p.phone || '—')} · ${esc(p.complaint ? p.complaint.slice(0, 40) : '')}</div></div>
    <span class="badge">${done} / 22 جلسة</span></div>`;
}

/* ---------- patients list ---------- */
function patientsView() {
  return `<div class="row"><h2 style="margin:0;color:var(--navy)">ملفات المرضى</h2><span class="spacer"></span><button class="btn" id="newP">➕ مريض جديد</button></div>
  <input class="search" id="ps" placeholder="🔍 ابحث بالاسم أو رقم الملف أو الهاتف" style="margin-top:14px">
  <div class="plist" id="pl"></div>`;
}
function bindPatients() {
  const draw = () => {
    const q = $('#ps').value.trim();
    const list = patients.filter(p => !q || [p.name, p.fileNo, p.phone].join(' ').includes(q)).sort((a, b) => (b.updated || b.created).localeCompare(a.updated || a.created));
    $('#pl').innerHTML = list.length ? list.map(pCard).join('') : `<div class="empty">لا توجد ملفات بعد. اضغط «مريض جديد» للبدء.</div>`;
  };
  $('#ps').addEventListener('input', draw); draw();
}

/* ---------- patient file ---------- */
const head = (title, sub) => `<div class="sheet-head"><div class="logo"><b>Motion Life</b><small>مركز العلاج الفيزيائي وإعادة التأهيل</small></div>
  <div class="tag"><b>${title}</b>${sub}</div></div>`;
const inp = (k, label, type = 'text', v = '') => `<div class="f"><label>${label}:</label><input data-k="${k}" type="${type}" value="${esc(v)}"></div>`;
const ta = (k, rows, v) => `<textarea class="lined" data-k="${k}" rows="${rows}">${esc(v)}</textarea>`;
const PAIN_C = ['#2e9e5b','#4caf50','#7cb342','#c0ca33','#fdd835','#fbc02d','#ffa000','#f57c00','#ef6c00','#e64a19','#c62828'];

function patientView(p, tab) {
  const tabs = `<div class="ptabs">
    <button class="tab ${tab === '1' ? 'on' : ''}" data-go="p/${p.id}/1">١- ملف المريض والتقييم</button>
    <button class="tab ${tab === '2' ? 'on' : ''}" data-go="p/${p.id}/2">٢- الخطة العلاجية والجلسات</button>
    <span class="spacer"></span><span class="saved" id="sv"></span>
    <button class="btn ghost sm" id="prt">🖨️ طباعة الملف</button>
    <button class="btn ghost sm" id="prtEx">🖨️ ورقة تمارين للمريض</button>
    <button class="btn danger sm" id="delP">حذف</button></div>`;
  return tabs + (tab === '2' ? page2(p) : page1(p));
}

function page1(p) {
  const pt = ['راحة', 'حركة', 'ليل', 'متقطع', 'مستمر'];
  return `<div class="sheet">${head('الحركة تبدأ من هنا', 'ملف المريض والتقييم السريري')}
  <div class="box"><div class="box-b grid4">
    ${inp('fileNo', 'رقم الملف', 'text', p.fileNo)}${inp('cabinet', 'الخزانة / الدرج', 'text', p.cabinet)}${inp('shelf', 'الرف', 'text', p.shelf)}${inp('serial', 'رقم التسلسل', 'text', p.serial)}
  </div></div>
  <div class="grid3" style="margin-bottom:16px">
    ${inp('name', 'الاسم الكامل', 'text', p.name)}${inp('age', 'العمر', 'number', p.age)}
    <div class="f"><label>الجنس:</label><span><label class="chk"><input type="radio" name="g" data-k="gender" value="ذكر" ${p.gender === 'ذكر' ? 'checked' : ''}>ذكر</label><label class="chk"><input type="radio" name="g" data-k="gender" value="أنثى" ${p.gender === 'أنثى' ? 'checked' : ''}>أنثى</label></span></div>
    ${inp('phone', 'رقم الهاتف', 'tel', p.phone)}${inp('job', 'المهنة', 'text', p.job)}${inp('evalDate', 'تاريخ التقييم', 'date', p.evalDate)}
  </div>
  <div class="box"><div class="box-t">الشكوى الرئيسية والتاريخ الصحي</div><div class="box-b">
    <div class="grid2"><div class="fcol"><span class="lbl">الشكوى الرئيسية</span>${ta('complaint', 2, p.complaint)}</div>
    <div class="fcol"><span class="lbl">الأمراض المزمنة / الأدوية / العمليات السابقة</span>${ta('chronic', 2, p.chronic)}</div></div>
    <div class="fcol" style="margin-top:10px"><span class="lbl">القصة المرضية</span>${ta('history', 4, p.history)}</div>
  </div></div>
  <div class="box"><div class="box-t">التقييم السريري</div><div class="box-b">${ta('clinical', 6, p.clinical)}</div></div>
  <div class="box"><div class="box-t">الأعراض الحالية ومقياس الألم</div><div class="box-b grid2">
    <div class="fcol"><span class="lbl">الأعراض الحالية</span>${ta('symptoms', 3, p.symptoms)}</div>
    <div class="fcol"><div class="f" style="align-items:center"><label>شدة الألم:</label>
      <div class="pain" id="pain">${Array.from({ length: 11 }, (_, i) => `<button type="button" data-v="${i}" class="${p.pain === i ? 'on' : ''}" style="${p.pain === i ? 'background:' + PAIN_C[i] : ''}">${i}</button>`).join('')}</div></div>
      <div style="margin-top:8px">${pt.map(t => `<label class="chk"><input type="checkbox" data-pt="${t}" ${p.painType.includes(t) ? 'checked' : ''}>${t}</label>`).join('')}</div>
      ${inp('duration', 'مدة الأعراض', 'text', p.duration)}</div>
  </div></div>
  <div class="box"><div class="box-t">القوة العضلية والقيود الحالية</div><div class="box-b grid2">
    <div class="fcol"><span class="lbl">القوة العضلية</span>${ta('strength', 3, p.strength)}</div>
    <div class="fcol"><span class="lbl">القيود / الصعوبات الحالية</span>${ta('limits', 3, p.limits)}</div>
  </div></div>
  <div class="sign">${inp('notes', 'ملاحظات عامة', 'text', p.notes)}${inp('therapist', 'اسم / توقيع المعالج', 'text', p.therapist)}</div>
  </div>
  <div class="row"><span class="spacer"></span><button class="btn big" data-go="p/${p.id}/2">التالي: الخطة العلاجية ←</button></div>`;
}

function page2(p) {
  const half = (from, to) => `<table class="sess"><thead><tr><th>الجلسة</th><th>التاريخ</th><th>الملاحظات / الاستجابة</th><th>المعالج</th></tr></thead><tbody>
    ${p.sessions.slice(from, to).map((s, j) => { const i = from + j; return `<tr><td class="n">${i + 1}</td>
      <td><input type="date" data-s="${i}" data-f="date" value="${esc(s.date)}"></td>
      <td><input data-s="${i}" data-f="note" value="${esc(s.note)}"></td>
      <td><input data-s="${i}" data-f="by" value="${esc(s.by)}" style="width:90px"></td></tr>`; }).join('')}</tbody></table>`;
  const paid = p.payments.reduce((a, x) => a + num(x.amount), 0);
  return `<div class="sheet">${head('الخطة العلاجية ومتابعة الجلسات', 'حتى 22 جلسة')}
  <div class="grid3" style="margin-bottom:16px">
    ${inp('startDate', 'تاريخ بدء العلاج', 'date', p.startDate)}
    <div class="f"><label>رقم الملف:</label><input value="${esc(p.fileNo)}" readonly tabindex="-1"></div>
    <div class="f"><label>اسم المريض:</label><input value="${esc(p.name)}" readonly tabindex="-1"></div>
  </div>
  <div class="box"><div class="box-t">الخطة العلاجية</div><div class="box-b">
    ${ta('plan', 4, p.plan)}
    <div class="plan-sub"><h4>⚡ الأجهزة العلاجية والبروتوكولات <span class="cnt">${p.devices.length}</span><span class="spacer"></span><button class="btn sm" id="addDev">➕ إضافة جهاز</button></h4>
      <div id="devList">${devListHTML(p)}</div></div>
    <div class="plan-sub"><h4>🏃 التمارين العلاجية <span class="cnt">${p.exercises.length}</span><span class="spacer"></span><button class="btn sm" id="addEx">➕ إضافة تمارين من المكتبة</button></h4>
      <div id="exList">${exListHTML(p)}</div></div>
  </div></div>
  <div class="sess-wrap">${half(0, 11)}${half(11, 22)}</div>
  <div class="grid2" style="margin-bottom:14px">
    <div class="fcol"><span class="lbl">التقييم بعد الجلسة السادسة:</span>${ta('eval6', 2, p.eval6)}</div>
    <div class="fcol"><span class="lbl">التقييم بعد الجلسة الثانية عشرة:</span>${ta('eval12', 2, p.eval12)}</div>
  </div>
  <div class="pay">
    <div class="paybox">${inp('agreedSessions', 'عدد الجلسات المتفق عليها', 'text', p.agreedSessions)}</div>
    <div class="paybox">${inp('agreedTotal', 'المبلغ الإجمالي المتفق عليه', 'text', p.agreedTotal)}</div>
    ${p.payments.map((x, i) => `<div class="paybox soft"><div class="row" style="flex-wrap:nowrap"><b style="white-space:nowrap">الدفعة ${i + 1}:</b>
      <div class="f" style="flex:1"><label>المبلغ</label><input data-pay="${i}" data-f="amount" value="${esc(x.amount)}" inputmode="numeric"></div>
      <div class="f" style="flex:1"><label>التاريخ</label><input type="date" data-pay="${i}" data-f="date" value="${esc(x.date)}"></div></div></div>`).join('')}
    <div class="paybox"><div class="f"><label>المبلغ المتبقي:</label><input id="remain" readonly value="${p.agreedTotal ? fmt(num(p.agreedTotal) - paid) : ''}"></div></div>
    <div class="paybox"><div class="f"><label>إجمالي المبلغ المدفوع:</label><input id="paid" readonly value="${paid ? fmt(paid) : ''}"></div></div>
  </div></div>`;
}

function devListHTML(p) {
  if (!p.devices.length) return `<div class="empty">لم تتم إضافة أجهزة بعد — اضغط «إضافة جهاز» واختر الجهاز ثم البروتوكول.</div>`;
  return p.devices.map((d, i) => { const dev = DEVM[d.dev] || { name: d.dev, params: [] };
    return `<div class="dev-item"><div style="flex:1"><div class="dn">${esc(dev.name)}</div><div class="dp">${esc(d.program)}</div>
      <div class="dv">${(dev.params || []).map((n, j) => d.values[j] ? `${esc(n)}: <b>${esc(d.values[j])}</b>` : '').filter(Boolean).join(' · ')}
      ${d.area ? ` · المنطقة: <b>${esc(d.area)}</b>` : ''}${d.note ? ` · ${esc(d.note)}` : ''}</div></div>
      <button class="btn light sm" data-edev="${i}">تعديل</button><button class="x" data-rdev="${i}" title="حذف">×</button></div>`; }).join('');
}
function exListHTML(p) {
  if (!p.exercises.length) return `<div class="empty">لم تتم إضافة تمارين بعد — اضغط «إضافة تمارين من المكتبة» واختر المنطقة ونوع التمرين.</div>`;
  return `<div class="ex-list">${p.exercises.map((x, i) => { const e = EXM[x.code]; if (!e) return '';
    return `<div class="ex-item"><img src="${fig(x.code)}" alt="" data-exinfo="${x.code}" style="cursor:pointer">
      <div style="flex:1;min-width:0"><div class="t">${esc(e.name_ar)}</div>
      <span class="badge">${esc(REG[e.region])}</span> <span class="badge o">${esc(TYP[e.type])}</span>
      <input data-exd="${i}" value="${esc(x.dosage)}" title="الجرعة" placeholder="الجرعة">
      <input data-exn="${i}" value="${esc(x.note || '')}" placeholder="ملاحظة (اختياري)"></div>
      <button class="x" data-rex="${i}" title="حذف">×</button></div>`; }).join('')}</div>`;
}

function bindPatient(p, tab) {
  let t;
  const touch = () => { p.updated = new Date().toISOString(); clearTimeout(t); $('#sv').textContent = '...'; t = setTimeout(() => { if (savePatients()) $('#sv').textContent = '✓ تم الحفظ تلقائياً'; }, 350); };
  $$('[data-k]').forEach(el => el.addEventListener(el.type === 'radio' ? 'change' : 'input', () => { p[el.dataset.k] = el.value; touch(); if (el.dataset.k === 'agreedTotal') calc(); }));
  $$('[data-pt]').forEach(el => el.addEventListener('change', () => { const v = el.dataset.pt; p.painType = p.painType.filter(x => x !== v); if (el.checked) p.painType.push(v); touch(); }));
  const pain = $('#pain');
  if (pain) pain.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; const v = +b.dataset.v; p.pain = p.pain === v ? null : v;
    $$('button', pain).forEach(x => { const on = +x.dataset.v === p.pain; x.classList.toggle('on', on); x.style.background = on ? PAIN_C[p.pain] : ''; }); touch(); });
  $$('[data-s]').forEach(el => el.addEventListener('input', () => { p.sessions[+el.dataset.s][el.dataset.f] = el.value; touch(); }));
  const calc = () => { const paid = p.payments.reduce((a, x) => a + num(x.amount), 0); if ($('#paid')) { $('#paid').value = paid ? fmt(paid) : ''; $('#remain').value = p.agreedTotal ? fmt(num(p.agreedTotal) - paid) : ''; } };
  $$('[data-pay]').forEach(el => el.addEventListener('input', () => { p.payments[+el.dataset.pay][el.dataset.f] = el.value; touch(); calc(); }));
  $('#prt').addEventListener('click', () => printPatient(p, false));
  $('#prtEx').addEventListener('click', () => p.exercises.length ? printPatient(p, true) : toast('أضف تمارين في الخطة العلاجية أولاً'));
  $('#delP').addEventListener('click', () => openModal(`<div class="modal-h"><h3>حذف ملف ${esc(p.name || 'المريض')}؟</h3></div><p>لا يمكن التراجع عن الحذف.</p>
    <div class="row"><button class="btn danger" id="yes">نعم، احذف</button><button class="btn ghost" id="no">إلغاء</button></div>`) ||
    ($('#yes').onclick = () => { patients = patients.filter(x => x.id !== p.id); savePatients(); closeModal(); go('patients'); }, $('#no').onclick = closeModal));
  if (tab !== '2') return;
  const redraw = () => { $('#devList').innerHTML = devListHTML(p); $('#exList').innerHTML = exListHTML(p); bindLists(); touch();
    $$('.plan-sub .cnt')[0].textContent = p.devices.length; $$('.plan-sub .cnt')[1].textContent = p.exercises.length; };
  function bindLists() {
    $$('[data-rdev]').forEach(b => b.onclick = () => { p.devices.splice(+b.dataset.rdev, 1); redraw(); });
    $$('[data-edev]').forEach(b => b.onclick = () => { const d = p.devices[+b.dataset.edev]; deviceParamsStep(DEVM[d.dev], d.program, d.values, d, v => { p.devices[+b.dataset.edev] = v; redraw(); }); });
    $$('[data-rex]').forEach(b => b.onclick = () => { p.exercises.splice(+b.dataset.rex, 1); redraw(); });
    $$('[data-exd]').forEach(el => el.oninput = () => { p.exercises[+el.dataset.exd].dosage = el.value; touch(); });
    $$('[data-exn]').forEach(el => el.oninput = () => { p.exercises[+el.dataset.exn].note = el.value; touch(); });
    $$('[data-exinfo]').forEach(el => el.onclick = () => exInfo(el.dataset.exinfo));
  }
  bindLists();
  $('#addDev').addEventListener('click', () => devicePicker(v => { p.devices.push(v); redraw(); toast('تمت إضافة الجهاز إلى الخطة'); }));
  $('#addEx').addEventListener('click', () => exercisePicker(p.exercises.map(x => x.code), codes => {
    codes.forEach(c => { if (!p.exercises.some(x => x.code === c)) p.exercises.push({ code: c, dosage: EXM[c].dosage, note: '' }); }); redraw(); toast('تمت إضافة ' + codes.length + ' تمرين'); }));
}

/* ---------- device picker (3 easy steps) ---------- */
const stepsBar = n => `<div class="steps-i">${['١ اختر الجهاز', '٢ اختر البروتوكول', '٣ اضبط الإعدادات'].map((t, i) => `<span class="${i + 1 === n ? 'on' : ''}">${t}</span>`).join('')}</div>`;
function devicePicker(done) {
  openModal(`<div class="modal-h"><h3>إضافة جهاز علاجي</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>${stepsBar(1)}
    <div class="devgrid">${D.devices.map(d => `<button class="devcard" data-dev="${d.code}"><b>${esc(d.name)}</b><span>${esc(d.name_ar)}</span><br>
      <span class="badge">${d.programs.length ? d.programs.length + ' برنامج' : d.presets.length + ' بروتوكول مقترح'}</span></button>`).join('')}</div>`);
  $('#mc').onclick = closeModal;
  $$('[data-dev]').forEach(b => b.onclick = () => programStep(DEVM[b.dataset.dev], done));
}
function programStep(dev, done) {
  const progs = dev.programs, pres = dev.presets;
  openModal(`<div class="modal-h"><button class="btn ghost sm" id="back">→ رجوع</button><h3 style="direction:ltr">${esc(dev.name)}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>${stepsBar(2)}
    <input class="search" id="qs" placeholder="🔍 ابحث عن الحالة (عربي أو إنجليزي)">
    <div class="proglist" id="pls"></div>
    <div class="modal-f"><button class="btn light" id="manual">✍️ إعداد يدوي (بدون برنامج محدد)</button><span class="spacer"></span><small style="color:var(--muted)">${esc(dev.source)}</small></div>`);
  const draw = () => {
    const q = $('#qs').value.trim().toLowerCase();
    const m = x => !q || (x.ar + ' ' + (x.en || '') + ' ' + (x.group || '')).toLowerCase().includes(q);
    const P = pres.filter(m), G = progs.filter(m);
    $('#pls').innerHTML = (P.length ? `<div class="section-t">بروتوكولات جاهزة بقيم مقترحة</div>` + P.map(x => `<button class="prog preset" data-pr="${pres.indexOf(x)}"><b>${esc(x.ar)}</b><small style="direction:rtl">${dev.params.map((n, j) => x.values[j] ? n + ': ' + x.values[j] : '').filter(Boolean).join(' · ')}</small></button>`).join('') : '') +
      (G.length ? `<div class="section-t">برامج الجهاز (من ملف البروتوكولات)</div>` + G.map(x => `<button class="prog" data-pg="${progs.indexOf(x)}"><b>${x.ar ? esc(x.ar) : esc(x.en)}</b><small>${esc(x.en)}</small></button>`).join('') : '') ||
      `<div class="empty">لا نتائج. جرّب كلمة أخرى أو استخدم الإعداد اليدوي.</div>`;
    $$('[data-pr]').forEach(b => b.onclick = () => { const x = pres[+b.dataset.pr]; deviceParamsStep(dev, x.ar, x.values.slice(), null, done); });
    $$('[data-pg]').forEach(b => b.onclick = () => { const x = progs[+b.dataset.pg]; deviceParamsStep(dev, x.ar ? x.ar + ' — ' + x.en : x.en, [], null, done); });
  };
  $('#qs').addEventListener('input', draw); draw(); $('#qs').focus();
  $('#back').onclick = () => devicePicker(done); $('#mc').onclick = closeModal;
  $('#manual').onclick = () => deviceParamsStep(dev, 'إعداد يدوي', [], null, done);
}
function deviceParamsStep(dev, program, values, existing, done) {
  openModal(`<div class="modal-h">${existing ? '' : '<button class="btn ghost sm" id="back">→ رجوع</button>'}<h3 style="direction:ltr">${esc(dev.name)}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>${stepsBar(3)}
    <div class="pform">
      <div class="fcol" style="grid-column:1/-1"><span class="lbl">البروتوكول / البرنامج</span><input id="pp" value="${esc(program)}"></div>
      ${dev.params.map((n, j) => `<div class="fcol"><span class="lbl">${esc(n)}</span><input data-pv="${j}" value="${esc(values[j] || '')}"></div>`).join('')}
      <div class="fcol"><span class="lbl">منطقة التطبيق</span><input id="parea" value="${esc(existing ? existing.area : '')}" placeholder="مثال: الركبة اليمنى"></div>
      <div class="fcol" style="grid-column:1/-1"><span class="lbl">ملاحظات</span><input id="pnote" value="${esc(existing ? existing.note : '')}"></div>
    </div>
    <div class="warn" style="margin-top:12px">القيم المقترحة نقطة بداية فقط — راجع موانع الاستعمال ودليل الشركة وعدّلها حسب حالة المريض.</div>
    <div class="modal-f"><button class="btn big" id="ok">${existing ? 'حفظ التعديل' : '✓ إضافة إلى الخطة'}</button><button class="btn ghost" id="cn">إلغاء</button></div>`);
  $('#mc').onclick = closeModal; $('#cn').onclick = closeModal;
  if ($('#back')) $('#back').onclick = () => programStep(dev, done);
  $('#ok').onclick = () => { done({ dev: dev.code, program: $('#pp').value.trim() || 'إعداد يدوي', values: $$('[data-pv]').map(i => i.value.trim()), area: $('#parea').value.trim(), note: $('#pnote').value.trim() }); closeModal(); };
}

/* ---------- exercise picker / library ---------- */
function libFilters(prefix) {
  return `<input class="search" id="${prefix}q" placeholder="🔍 ابحث عن تمرين">
  <div class="lbl-s">١- منطقة الجسم</div><div class="chips" id="${prefix}r"><button class="chip on" data-v="">الكل</button>${D.regions.map(r => `<button class="chip" data-v="${r.code}">${r.ar}</button>`).join('')}</div>
  <div class="lbl-s">٢- نوع التمرين (الهدف)</div><div class="chips" id="${prefix}t"><button class="chip on" data-v="">الكل</button>${D.types.map(t => `<button class="chip" data-v="${t.code}">${t.ar}</button>`).join('')}</div>`;
}
function useFilters(prefix, onChange) {
  const st = { r: '', t: '', q: '' };
  ['r', 't'].forEach(k => $('#' + prefix + k).addEventListener('click', e => { const b = e.target.closest('.chip'); if (!b) return; st[k] = b.dataset.v;
    $$('.chip', $('#' + prefix + k)).forEach(c => c.classList.toggle('on', c === b)); onChange(st); }));
  $('#' + prefix + 'q').addEventListener('input', e => { st.q = e.target.value.trim(); onChange(st); });
  return st;
}
const filterEx = st => D.exercises.filter(e => (!st.r || e.region === st.r) && (!st.t || e.type === st.t) && (!st.q || (e.name_ar + ' ' + e.name_en + ' ' + e.steps).toLowerCase().includes(st.q.toLowerCase())));
const exCard = (e, sel) => `<div class="card ${sel ? 'sel' : ''}" data-ex="${e.code}"><img src="${fig(e.code)}" alt="" loading="lazy">
  <div class="t">${esc(e.name_ar)}</div><div><span class="badge">${esc(REG[e.region])}</span> <span class="badge o">${esc(TYP[e.type])}</span></div><div class="d">${esc(e.dosage)}</div></div>`;

function exercisePicker(already, done) {
  const sel = new Set();
  openModal(`<div class="modal-h"><h3>اختيار التمارين</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
    ${libFilters('m')}<div class="lib" id="ml"></div>
    <div class="modal-f"><button class="btn big" id="ok" disabled>إضافة التمارين المختارة (0)</button><button class="btn ghost" id="cn">إلغاء</button>
    <span class="spacer"></span><small style="color:var(--muted)">اضغط على التمرين لاختياره، واضغط مرة ثانية لإلغائه</small></div>`);
  const draw = st => { const L = filterEx(st); $('#ml').innerHTML = L.length ? L.map(e => exCard(e, sel.has(e.code)).replace('</div></div>', (already.includes(e.code) ? '<span class="badge" style="background:#e7f6ee;color:var(--ok)">موجود في الخطة</span>' : '') + '</div></div>')).join('') : '<div class="empty">لا توجد تمارين بهذه المواصفات.</div>'; };
  const st = useFilters('m', draw); draw(st);
  $('#ml').addEventListener('click', e => { const c = e.target.closest('.card'); if (!c) return; const k = c.dataset.ex; sel.has(k) ? sel.delete(k) : sel.add(k); c.classList.toggle('sel');
    $('#ok').textContent = `إضافة التمارين المختارة (${sel.size})`; $('#ok').disabled = !sel.size; });
  $('#mc').onclick = closeModal; $('#cn').onclick = closeModal;
  $('#ok').onclick = () => { done([...sel]); closeModal(); };
}
function exInfo(code) {
  const e = EXM[code];
  openModal(`<div class="modal-h"><h3>${esc(e.name_ar)}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
    <div class="exd"><img src="${fig(code)}" alt=""><div>
      <div><span class="badge">${esc(REG[e.region])}</span> <span class="badge o">${esc(TYP[e.type])}</span> ${e.name_en ? `<small style="color:var(--muted)">${esc(e.name_en)}</small>` : ''}</div>
      <h4 style="margin:12px 0 4px;color:var(--teal-d)">طريقة الأداء</h4><p style="margin:0">${esc(e.steps)}</p>
      <h4 style="margin:12px 0 4px;color:var(--teal-d)">الجرعة المقترحة</h4><p style="margin:0">${esc(e.dosage)}</p>
      <div class="warn" style="margin-top:12px">⚠️ ${esc(e.caution)}</div></div></div>`);
  $('#mc').onclick = closeModal;
}
function libraryView() {
  return `<div class="row"><h2 style="margin:0;color:var(--navy)">مكتبة التمارين</h2><span class="badge" id="lc"></span></div>
  <div class="help" style="margin-top:10px">اختر منطقة الجسم ثم نوع التمرين (تقوية، إطالة، ثبات، توازن...). اضغط على أي تمرين لرؤية طريقة الأداء. لإضافة تمارين لمريض: افتح ملفه ← الخطة العلاجية ← «إضافة تمارين».</div>
  ${libFilters('l')}<div class="lib" id="ll"></div>`;
}
function bindLibrary() {
  const draw = st => { const L = filterEx(st); $('#lc').textContent = L.length + ' تمرين'; $('#ll').innerHTML = L.map(e => exCard(e, false)).join('') || '<div class="empty">لا توجد تمارين بهذه المواصفات.</div>'; };
  const st = useFilters('l', draw); draw(st);
  $('#ll').addEventListener('click', e => { const c = e.target.closest('.card'); if (c) exInfo(c.dataset.ex); });
}

/* ---------- devices page ---------- */
function devicesView() {
  return `<h2 style="margin:0 0 10px;color:var(--navy)">الأجهزة العلاجية والبروتوكولات</h2>
  <div class="help">اضغط على الجهاز لرؤية برامجه. لإضافة جهاز لخطة مريض: افتح ملفه ← الخطة العلاجية ← «إضافة جهاز».</div>
  <div class="devgrid">${D.devices.map(d => `<button class="devcard" data-dev="${d.code}"><b>${esc(d.name)}</b><span>${esc(d.name_ar)}</span><br>
    <span class="badge">${d.programs.length ? d.programs.length + ' برنامج من ملف الجهاز' : d.presets.length + ' بروتوكول مقترح'}</span></button>`).join('')}</div>`;
}
function bindDevices() {
  $$('[data-dev]').forEach(b => b.onclick = () => { const d = DEVM[b.dataset.dev];
    openModal(`<div class="modal-h"><h3 style="direction:ltr">${esc(d.name)}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
      <p style="margin:0 0 6px;color:var(--muted)">${esc(d.name_ar)} — إعدادات الضبط: ${d.params.map(esc).join('، ')}</p>
      <input class="search" id="qs" placeholder="🔍 ابحث عن حالة"><div class="proglist" id="pls"></div>`);
    const draw = () => { const q = $('#qs').value.trim().toLowerCase(); const m = x => !q || (x.ar + ' ' + (x.en || '')).toLowerCase().includes(q);
      $('#pls').innerHTML = d.presets.filter(m).map(x => `<div class="prog preset"><b>${esc(x.ar)}</b><small style="direction:rtl">${d.params.map((n, j) => x.values[j] ? n + ': ' + x.values[j] : '').filter(Boolean).join(' · ')}</small></div>`).join('') +
        d.programs.filter(m).map((x, i) => `<div class="prog"><b>${esc(x.ar || x.en)}</b><small>${esc(x.en)}</small></div>`).join(''); };
    $('#qs').oninput = draw; draw(); $('#mc').onclick = closeModal; });
}

/* ---------- settings ---------- */
function settingsView() {
  const auth = store.get('ml_auth', null);
  return `<h2 style="margin:0 0 14px;color:var(--navy)">الإعدادات</h2>
  <div class="sheet"><h3 style="margin-top:0">🔑 تغيير بيانات الدخول</h3>
    <div class="pform"><div class="fcol"><span class="lbl">اسم المستخدم الجديد</span><input id="nu" value="${esc(auth ? auth.user : DEFAULT_USER)}"></div>
    <div class="fcol"><span class="lbl">كلمة المرور الجديدة</span><input id="np" type="password"></div></div>
    <button class="btn" id="saveAuth" style="margin-top:12px">حفظ</button></div>
  <div class="sheet"><h3 style="margin-top:0">💾 النسخ الاحتياطي</h3>
    <p style="color:var(--muted);margin-top:0">الملفات محفوظة على هذا الجهاز وهذا المتصفح. خذ نسخة احتياطية أسبوعياً، واستخدمها لنقل الملفات إلى جهاز آخر.</p>
    <div class="row"><button class="btn" id="exp">⬇️ تنزيل نسخة احتياطية</button>
    <label class="btn light" style="cursor:pointer">⬆️ استرجاع نسخة<input type="file" id="imp" accept=".json,application/json" hidden></label></div></div>
  <div class="sheet"><button class="btn ghost" id="out">🚪 تسجيل الخروج</button></div>`;
}
function bindSettings() {
  $('#saveAuth').onclick = async () => { const u = $('#nu').value.trim(), pw = $('#np').value; if (!u || pw.length < 4) return toast('اكتب اسم مستخدم وكلمة مرور (4 أحرف على الأقل)');
    store.set('ml_auth', { user: u, hash: await hash(pw) }); $('#np').value = ''; toast('تم حفظ بيانات الدخول الجديدة'); };
  $('#exp').onclick = () => { const blob = new Blob([JSON.stringify({ app: 'motion-life', v: 1, at: new Date().toISOString(), patients }, null, 1)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'motion-life-backup-' + today() + '.json'; document.body.appendChild(a); a.click(); a.remove(); toast('تم تنزيل النسخة الاحتياطية'); };
  $('#imp').onchange = e => { const f = e.target.files[0]; if (!f) return; const r = new FileReader();
    r.onload = () => { try { const d = JSON.parse(r.result); if (!Array.isArray(d.patients)) throw 0; let n = 0;
      d.patients.forEach(x => { if (x && x.id) { const i = patients.findIndex(p => p.id === x.id); if (i >= 0) patients[i] = x; else patients.push(x); n++; } });
      savePatients(); toast('تم استرجاع ' + n + ' ملف'); } catch (err) { toast('الملف غير صالح'); } }; r.readAsText(f); };
  $('#out').onclick = () => { sess.set(false); location.hash = ''; render(); };
}

/* ---------- printing ---------- */
const pv = (label, v) => `<div class="f"><label>${label}:</label><div class="pv">${esc(v)}</div></div>`;
const pt = (v, min) => `<div class="pt" style="min-height:${Math.round(min*0.9)}px">${esc(v)}</div>`;
const pfoot = (r, l) => `<div class="pfoot"><span>${r}</span><span>${l}</span></div>`;
function printPatient(p, exOnly) {
  const phone = 'دمشق - الميدان | 011 8838215 - 0945823770';
  let h = '';
  if (!exOnly) {
    h += `<div class="pg sheet">${head('الحركة تبدأ من هنا', 'ملف المريض والتقييم السريري')}
      <div class="box"><div class="box-b grid4">${pv('رقم الملف', p.fileNo)}${pv('الخزانة / الدرج', p.cabinet)}${pv('الرف', p.shelf)}${pv('رقم التسلسل', p.serial)}</div></div>
      <div class="grid3" style="margin-bottom:10px">${pv('الاسم الكامل', p.name)}${pv('العمر', p.age)}<div class="f"><label>الجنس:</label><div class="pv">${p.gender === 'ذكر' ? '☑' : '☐'} ذكر &nbsp; ${p.gender === 'أنثى' ? '☑' : '☐'} أنثى</div></div>
        ${pv('رقم الهاتف', p.phone)}${pv('المهنة', p.job)}${pv('تاريخ التقييم', p.evalDate)}</div>
      <div class="box"><div class="box-t">الشكوى الرئيسية والتاريخ الصحي</div><div class="box-b"><div class="grid2"><div class="fcol"><span class="lbl">الشكوى الرئيسية</span>${pt(p.complaint, 44)}</div><div class="fcol"><span class="lbl">الأمراض المزمنة / الأدوية / العمليات السابقة</span>${pt(p.chronic, 44)}</div></div>
        <div class="fcol" style="margin-top:6px"><span class="lbl">القصة المرضية</span>${pt(p.history, 88)}</div></div></div>
      <div class="box"><div class="box-t">التقييم السريري</div><div class="box-b">${pt(p.clinical, 132)}</div></div>
      <div class="box"><div class="box-t">الأعراض الحالية ومقياس الألم</div><div class="box-b grid2"><div class="fcol"><span class="lbl">الأعراض الحالية</span>${pt(p.symptoms, 66)}</div>
        <div class="fcol"><div class="f"><label>شدة الألم:</label><span class="pain" style="direction:ltr">${Array.from({ length: 11 }, (_, i) => `<span class="${p.pain === i ? 'on' : ''}">${i}</span>`).join('')}</span></div>
        <div>${['راحة', 'حركة', 'ليل', 'متقطع', 'مستمر'].map(t => (p.painType.includes(t) ? '☑ ' : '☐ ') + t).join(' &nbsp; ')}</div>${pv('مدة الأعراض', p.duration)}</div></div></div>
      <div class="box"><div class="box-t">القوة العضلية والقيود الحالية</div><div class="box-b grid2"><div class="fcol"><span class="lbl">القوة العضلية</span>${pt(p.strength, 66)}</div><div class="fcol"><span class="lbl">القيود / الصعوبات الحالية</span>${pt(p.limits, 66)}</div></div></div>
      <div class="sign">${pv('ملاحظات عامة', p.notes)}${pv('اسم / توقيع المعالج', p.therapist)}</div>
      ${pfoot('Motion Life - ملف المريض', phone)}</div>`;
    const devs = p.devices.map(d => { const dev = DEVM[d.dev] || { name: d.dev, params: [] };
      return `<li><b style="direction:ltr;unicode-bidi:embed">${esc(dev.name)}</b> — ${esc(d.program)}${(dev.params || []).map((n, j) => d.values[j] ? ` · ${esc(n)}: ${esc(d.values[j])}` : '').join('')}${d.area ? ' · ' + esc(d.area) : ''}${d.note ? ' · ' + esc(d.note) : ''}</li>`; }).join('');
    const exs = p.exercises.map(x => EXM[x.code] ? `<li>${esc(EXM[x.code].name_ar)} (${esc(TYP[EXM[x.code].type])}) — ${esc(x.dosage)}${x.note ? ' · ' + esc(x.note) : ''}</li>` : '').join('');
    const row = i => { const s = p.sessions[i]; return `<tr><td class="n">${i + 1}</td><td>${esc(s.date)}</td><td>${esc(s.note)}</td><td>${esc(s.by)}</td></tr>`; };
    const tbl = (a, b) => `<table class="sess"><thead><tr><th>الجلسة</th><th>التاريخ</th><th>الملاحظات / الاستجابة</th><th>المعالج</th></tr></thead><tbody>${Array.from({ length: b - a }, (_, k) => row(a + k)).join('')}</tbody></table>`;
    const paid = p.payments.reduce((a, x) => a + num(x.amount), 0);
    h += `<div class="pg sheet">${head('الخطة العلاجية ومتابعة الجلسات', 'حتى 22 جلسة')}
      <div class="grid3" style="margin-bottom:8px">${pv('تاريخ بدء العلاج', p.startDate)}${pv('رقم الملف', p.fileNo)}${pv('اسم المريض', p.name)}</div>
      <div class="box"><div class="box-t">الخطة العلاجية</div><div class="box-b">${pt(p.plan, devs || exs ? 22 : 176)}
        ${devs ? `<div class="lbl" style="margin-top:6px">الأجهزة العلاجية والبروتوكولات:</div><ul class="pr-list">${devs}</ul>` : ''}
        ${exs ? `<div class="lbl" style="margin-top:6px">التمارين العلاجية:</div><ul class="pr-list">${exs}</ul>` : ''}</div></div>
      <div class="sess-wrap">${tbl(0, 11)}${tbl(11, 22)}</div>
      <div class="grid2" style="margin-bottom:8px">${pv('التقييم بعد الجلسة السادسة', p.eval6)}${pv('التقييم بعد الجلسة الثانية عشرة', p.eval12)}</div>
      <div class="pay"><div class="paybox">${pv('عدد الجلسات المتفق عليها', p.agreedSessions)}</div><div class="paybox">${pv('المبلغ الإجمالي المتفق عليه', p.agreedTotal)}</div>
        ${p.payments.map((x, i) => `<div class="paybox soft"><div class="row" style="flex-wrap:nowrap"><b>الدفعة ${i + 1}:</b>${pv('المبلغ', x.amount)}${pv('التاريخ', x.date)}</div></div>`).join('')}
        <div class="paybox">${pv('المبلغ المتبقي', p.agreedTotal ? fmt(num(p.agreedTotal) - paid) : '')}</div><div class="paybox">${pv('إجمالي المبلغ المدفوع', paid ? fmt(paid) : '')}</div></div>
      ${pfoot('Motion Life - الخطة العلاجية ومتابعة 22 جلسة', 'الحركة تبدأ من هنا')}</div>`;
  }
  if (exOnly && p.exercises.length) {
    h += `<div class="pg sheet">${head('برنامج التمارين المنزلية', esc(p.name || ''))}
      <div class="hx">${p.exercises.map(x => { const e = EXM[x.code]; if (!e) return ''; return `<div class="hx-i"><img src="${fig(x.code)}" alt=""><div>
        <b>${esc(e.name_ar)}</b><div>${esc(e.steps)}</div><div><b style="font-size:9.5pt">الجرعة:</b> ${esc(x.dosage)}${x.note ? ' — ' + esc(x.note) : ''}</div><div style="color:#a4520f">⚠️ ${esc(e.caution)}</div></div></div>`; }).join('')}</div>
      ${pfoot('Motion Life - برنامج التمارين', phone)}</div>`;
  }
  $('#print').innerHTML = h;
  const imgs = $$('#print img'); let left = imgs.length;
  const go2 = () => setTimeout(() => window.print(), 150);
  if (!left) return go2();
  imgs.forEach(i => { if (i.complete) { if (--left === 0) go2(); } else i.onload = i.onerror = () => { if (--left === 0) go2(); }; });
}

render();
})();
