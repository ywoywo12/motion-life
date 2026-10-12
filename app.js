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
const PRG = Object.fromEntries(D.programs.map(p => [p.code, p]));
const today = () => new Date().toISOString().slice(0, 10);

/* ---------- data (via db.js: cloud sync or local) ---------- */
const DB = window.MLDB;
const SEC = { women: 'قسم النساء', men: 'قسم الرجال' };
const SEC_HOURS = { women: [9, 15], men: [15, 21] };
const allP = () => [...DB.patients.values()];
/* صلاحيات المعالج/المعالجة */
const TH = () => !!(DB.isTherapist && DB.isTherapist());
const myTid = () => (DB.me && DB.me.tid) || '';
const myName = () => (DB.me && DB.me.name) || '';
const secOf = () => TH() ? DB.me.section : DB.role;
const DEF_PERMS = { appts: true, patients: true, finance: true, library: true, devices: true, stats: false, phone: false, pay: false, allAppts: false, delFiles: false, bothSecs: false, editAll: true, editOwn: true, createFiles: true, prices: true, files: true };
const can = k => !TH() || !!((DB.me && DB.me.perms) || DEF_PERMS)[k];
const hidePhone = () => TH() && !can('phone');
const hidePrices = () => TH() && !can('prices');
const lockPay = () => TH() && (!can('pay') || !can('prices'));
const limAppt = () => TH() && !can('allAppts');
const multiSec = () => DB.sections().length > 1;
const canStats = () => DB.role === 'admin' || (TH() && can('stats'));
const pageOK = k => !TH() || ['home', 'settings', 'p', 'setup', ''].includes(k) || (k === 'stats' ? can('stats') : can(k));
const PERM_LIST = [['appts', 'المواعيد'], ['patients', 'ملفات المرضى'], ['finance', 'المتابعة المالية'], ['stats', 'إحصائيات المعالجين'], ['library', 'مكتبة التمارين'], ['devices', 'الأجهزة والبروتوكولات'],
  ['phone', 'رؤية أرقام هواتف المرضى'], ['pay', 'تعديل الدفعات (ورؤية كل الملفات في المتابعة المالية)'], ['allAppts', 'إدارة مواعيد كل المعالجين (حجز/تعديل/حذف)'], ['delFiles', 'حذف ملفات المرضى'], ['bothSecs', 'الوصول للقسمين (النساء والرجال)'],
  ['editAll', 'تعديل ملفات كل المرضى'], ['editOwn', 'تعديل ملفات مرضاه فقط (المرتبطين به بموعد أو جلسة)'], ['createFiles', 'إضافة ملف طبي جديد'], ['prices', 'رؤية أسعار الجلسات والدفعات (عدد الجلسات والمبلغ المتبقي يبقيان ظاهرين)'], ['files', 'مشاهدة ورفع الصور والتقارير والملفات (حتى لو كان الملف للعرض فقط)']];
/* هل يستطيع الحساب تعديل ملف هذا المريض؟ */
const canFiles = p => !TH() || can('files') || canEditP(p);
const canEditP = p => !TH() || can('editAll') || (can('editOwn') && !!p && linkedTo(p, myTid(), myName()));
/* الحالة المالية لكل ملف */
function payState(p) {
  if (hidePrices()) { const st = p._pstat || 'none'; return { total: 0, paid: 0, remain: num(p._remain), status: st }; }
  const total = totalOf(p), paid = paidOf(p);
  return { total, paid, remain: total - paid, status: !total ? 'none' : (paid >= total ? 'done' : 'due') };
}
function payBadge(p) {
  const s = payState(p);
  if (s.status === 'due') return `<span class="pay-dot due" title="متبقي ${fmt(s.remain)}${s.total ? ' من ' + fmt(s.total) : ''}">● متبقي ${fmt(s.remain)}</span>`;
  if (s.status === 'done') return `<span class="pay-dot done" title="الدفعات مكتملة">● مكتمل الدفع</span>`;
  return '';
}
/* الجلسات المنفذة لمريض: من المواعيد (حضر) + أسطر الجلسات المكتوبة يدوياً */
function sessionsOf(p) {
  const out = [], seen = new Set();
  [...DB.appts.values()].filter(a => a.patientId === p.id && a.status === 'done').forEach(a => {
    const t = thOf(p.section, a); out.push({ date: a.date, time: a.time, by: t ? t.name : (a.by || ''), tid: t ? t.id : (a.tid || ''), no: a.sessionNo || '', src: 'appt' });
    seen.add(a.date + '|' + (t ? t.name : a.by || ''));
  });
  (p.sessions || []).forEach((r, i) => { if (!r.date) return; const k = r.date + '|' + (r.by || ''); if (seen.has(k)) return; seen.add(k);
    const t = therapists(p.section).find(x => x.name === r.by); out.push({ date: r.date, time: '', by: r.by || '', tid: t ? t.id : '', no: String(i + 1), src: 'file' }); });
  return out.sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
}
const linkedTo = (p, tid, name) => [...DB.appts.values()].some(a => a.patientId === p.id && (a.tid === tid || (!a.tid && a.by === name))) || (p.sessions || []).some(r => r.by && r.by === name);
const getP = id => DB.patients.get(id);
const uid = pre => pre + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const store = { get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } } };

function newPatient(section, extra) {
  const same = allP().filter(p => p.section === section);
  const nums = same.map(p => parseInt(p.fileNo, 10)).filter(n => !isNaN(n));
  return Object.assign({
    id: uid('p'), section,
    created: new Date().toISOString(),
    serial: String(same.length + 1), shelf: '', cabinet: '', fileNo: String((nums.length ? Math.max(...nums) : 0) + 1),
    name: '', age: '', gender: section === 'women' ? 'أنثى' : 'ذكر', phone: '', job: '', evalDate: today(), iq_date: today(),
    complaint: '', chronic: '', history: '', clinical: '',
    symptoms: '', pain: null, painType: [], duration: '',
    strength: '', limits: '', notes: '', therapist: '',
    startDate: today(), plan: '', devices: [], exercises: [],
    sessions: Array.from({ length: 22 }, () => ({ date: '', note: '', by: '' })),
    eval6: '', eval12: '', agreedSessions: '', agreedTotal: '',
    payments: Array.from({ length: 4 }, () => ({ amount: '', date: '' }))
  }, extra || {});
}
function createPatient(extra) {
  const make = sec => { const p = newPatient(sec, extra); DB.savePatient(p); go('p/' + p.id + '/0'); return p; };
  if (!multiSec()) return make(DB.sections()[0]);
  openModal(`<div class="modal-h"><h3>ملف جديد — اختر القسم</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
    <div class="row"><button class="btn big sec-w" id="sw">👩 قسم النساء</button><button class="btn big sec-m" id="sm">👨 قسم الرجال</button></div>`);
  $('#mc').onclick = closeModal; $('#sw').onclick = () => { closeModal(); make('women'); }; $('#sm').onclick = () => { closeModal(); make('men'); };
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
window.addEventListener('hashchange', () => render());

function syncBadge() {
  if (DB.mode === 'server') { const n = DB.pending();
    return DB.online ? `<span class="sync on">● متصل بخادم المركز${n ? ' — جارٍ إرسال ' + n : ''}</span>`
      : `<span class="sync wait" title="التعديلات محفوظة على هذا الجهاز وستُرسل تلقائياً">● غير متصل بخادم المركز${n ? ' — ' + n + ' تعديل بانتظار الإرسال' : ''}</span>`; }
  if (DB.mode !== 'cloud') return `<span class="sync off" title="البيانات محفوظة على هذا الجهاز فقط">● حفظ محلي (بدون مزامنة)</span>`;
  return DB.online ? `<span class="sync on">● متزامن لحظياً</span>` : `<span class="sync wait">● بدون إنترنت — سيُرفع تلقائياً</span>`;
}
function shell(active, inner) {
  const nav = [['home', 'الرئيسية'], ['appts', 'المواعيد'], ['patients', 'المرضى'], ['finance', 'المتابعة المالية']].concat(canStats() ? [['stats', 'إحصائيات المعالجين']] : [], [['library', 'مكتبة التمارين'], ['devices', 'الأجهزة والبروتوكولات'], ['settings', 'الإعدادات']])
    .filter(([k]) => !TH() || ['home', 'settings', 'stats'].includes(k) || can(k));
  return `<header class="topbar role-${secOf()}"><div class="topbar-in">
    <div class="brand" data-go="home"><b>Motion Life</b><small>مركز الأخصائي يزن جهاد العلواني</small></div>
    <div class="who"><span class="role-tag">${esc(DB.label())}</span><span id="syncB">${syncBadge()}</span></div>
    <nav class="nav">${nav.map(([k, t]) => `<button data-go="${k}" class="${active === k ? 'on' : ''}">${t}</button>`).join('')}</nav>
  </div></header><main class="wrap">${inner}</main>`;
}

let current = '';
function render() {
  const app = $('#app');
  const h = (location.hash || '#home').slice(1).split('/');
  stopMic(); livePatient = null; liveRedraw = null; progRedraw = null; filesRedraw = null;
  if (h[0] === 'setup') { current = 'setup'; app.innerHTML = setupView(); bindSetup(); return; }
  if (!DB.role) { current = 'login'; app.innerHTML = loginView(); bindLogin(); return; }
  closeModal();
  current = h[0] || 'home';
  if (!pageOK(h[0]) || (h[0] === 'p' && !can('patients'))) { app.innerHTML = shell('', `<div class="empty" style="padding:30px">🔒 لا تملك صلاحية الوصول لهذا القسم. تواصل مع الإدارة.</div>`); $$('[data-go]').forEach(b => b.addEventListener('click', () => go(b.dataset.go))); return; }
  if (h[0] === 'p' && getP(h[1])) { const P = getP(h[1]); app.innerHTML = shell('patients', patientView(P, h[2] || '1')); bindPatient(P, h[2] || '1'); if (!canEditP(P)) makeReadOnly(); }
  else if (h[0] === 'p') { app.innerHTML = shell('patients', `<div class="empty">جارٍ تحميل الملف... إذا لم يظهر فقد يكون محذوفاً أو من قسم آخر.</div>`); }
  else if (h[0] === 'appts') { app.innerHTML = shell('appts', apptsView(h[1], h[2])); bindAppts(h[1], h[2]); }
  else if (h[0] === 'patients') { app.innerHTML = shell('patients', patientsView()); bindPatients(); if (TH() && !can('createFiles') && $('#newP')) $('#newP').remove(); }
  else if (h[0] === 'finance') { app.innerHTML = shell('finance', financeView()); bindFinance(); }
  else if (h[0] === 'stats' && canStats()) { app.innerHTML = shell('stats', statsView(h[1])); bindStats(h[1]); }
  else if (h[0] === 'library') { app.innerHTML = shell('library', libraryView()); bindLibrary(); }
  else if (h[0] === 'devices') { app.innerHTML = shell('devices', devicesView()); bindDevices(); }
  else if (h[0] === 'settings') { app.innerHTML = shell('settings', settingsView()); bindSettings(); }
  else { app.innerHTML = shell('home', homeView()); $$('.tile[data-go]').forEach(t => { if (!pageOK(t.dataset.go)) t.remove(); }); if (TH() && (!can('patients') || !can('createFiles')) && $('#newP')) $('#newP').remove(); }
  $$('[data-go]').forEach(b => b.addEventListener('click', () => go(b.dataset.go)));
  window.scrollTo(0, 0);
}

/* ---------- login ---------- */
function loginView() {
  const cloud = DB.mode === 'cloud';
  return `<div class="login"><form class="login-box" id="lf">
    <h1>Motion Life</h1><p>نظام ملف المريض والمواعيد</p>
    <div class="who-pick">
      <button type="button" class="wp w" data-u="women">👩<b>قسم النساء</b></button>
      <button type="button" class="wp m" data-u="men">👨<b>قسم الرجال</b></button>
      <button type="button" class="wp a" data-u="admin">🔑<b>الإدارة</b></button>
    </div>
    <div id="staffPick"></div>
    <label for="lu">اسم المستخدم</label><input id="lu" autocomplete="username" value="" dir="ltr">
    <label for="lp">كلمة المرور</label><input id="lp" type="password" autocomplete="current-password" dir="ltr">
    <button class="btn big" style="width:100%;margin-top:20px" id="lb">دخول</button>
    <div class="err" id="lerr"></div>
    <div class="login-foot">${DB.mode === 'server' ? '<span class="sync on">● نظام المركز الداخلي (يعمل بدون إنترنت)</span>' : (cloud ? '<span class="sync on">● المزامنة اللحظية مفعّلة</span>' : '<span class="sync off">● وضع الحفظ المحلي</span>') + ' · <a href="#setup">إعداد المزامنة</a>'}</div>
  </form></div>`;
}
function bindLogin() {
  if (DB.mode === 'server') DB.staff().then(list => { if (!list.length || !$('#staffPick')) return;
    $('#staffPick').innerHTML = `<label>المعالجون والمعالجات — اختر اسمك</label><select id="stSel" class="sel" style="width:100%"><option value="">—</option>${['women', 'men'].map(sec => `<optgroup label="${SEC[sec]}">${list.filter(x => x.section === sec).map(x => `<option value="${esc(x.user)}">${esc(x.name)}</option>`).join('')}</optgroup>`).join('')}</select>`;
    $('#stSel').onchange = e => { if (e.target.value) { $('#lu').value = e.target.value; $$('.wp').forEach(x => x.classList.remove('on')); $('#lp').focus(); } }; });
  $$('.wp').forEach(b => b.onclick = () => { $('#lu').value = b.dataset.u; $$('.wp').forEach(x => x.classList.toggle('on', x === b)); $('#lp').focus(); });
  $('#lu').focus();
  $('#lf').addEventListener('submit', async e => {
    e.preventDefault(); $('#lerr').textContent = ''; $('#lb').disabled = true; $('#lb').textContent = '...';
    try { await DB.login($('#lu').value, $('#lp').value); if (!location.hash || location.hash === '#login') location.hash = '#home'; render(); }
    catch (err) { $('#lerr').textContent = err && err.code === 'auth/network-request-failed' ? 'لا يوجد اتصال بالإنترنت' : 'اسم المستخدم أو كلمة المرور غير صحيحة'; $('#lb').disabled = false; $('#lb').textContent = 'دخول'; }
  });
}

/* ---------- home ---------- */
function homeView() {
  const patients = allP();
  const todayA = [...DB.appts.values()].filter(a => a.date === today() && a.status !== 'cancelled').length;
  const recent = [...patients].sort((a, b) => (b.updated || b.created).localeCompare(a.updated || a.created)).slice(0, 5);
  return `<div class="hello">أهلاً بك — ${esc(DB.label())} 👋 ماذا تريد أن تفعل؟</div>
  <div class="tiles">
    <div class="tile main" data-go="appts"><div class="ic">📅</div><div><b>مواعيد اليوم</b><span>${todayA} موعد محجوز اليوم</span></div></div>
    <div class="tile" id="newP"><div class="ic">➕</div><div><b>مريض جديد</b><span>افتح ملفاً وابدأ التقييم</span></div></div>
    <div class="tile" data-go="patients"><div class="ic">📁</div><div><b>ملفات المرضى</b><span>${patients.length} ملف محفوظ</span></div></div>
    <div class="tile" data-go="library"><div class="ic">🏃</div><div><b>مكتبة التمارين</b><span>${D.exercises.length} تمريناً مع رسوم توضيحية</span></div></div>
    <div class="tile" data-go="devices"><div class="ic">⚡</div><div><b>الأجهزة والبروتوكولات</b><span>${D.devices.length} جهازاً وبرامجها</span></div></div>
  </div>
  ${recent.length ? `<h3 style="color:var(--navy);margin:26px 0 6px">آخر الملفات</h3><div class="plist">${recent.map(pCard).join('')}</div>` : ''}`;
}
document.addEventListener('click', e => {
  if (e.target.closest('#newP')) { if (TH() && !can('createFiles')) return toast('🔒 لا تملك صلاحية إضافة ملف جديد'); createPatient(); }
  const pc = e.target.closest('.pcard'); if (pc) go('p/' + pc.dataset.id + '/1');
});
function pCard(p) {
  const ini = (p.name || '؟').trim().charAt(0);
  const done = p.sessions.filter(s => s.date).length;
  return `<div class="pcard" data-id="${p.id}"><div class="av">${esc(ini)}</div><div style="flex:1">
    <b>${esc(p.name || 'بدون اسم')}</b> ${payBadge(p)}<div class="m">رقم الملف: ${esc(p.fileNo)} ·${hidePhone() ? '' : ' ' + esc(p.phone || '—') + ' ·'} ${esc(reasonOf(p).slice(0, 40))}</div></div>
    ${multiSec() ? `<span class="badge sec-${p.section}">${SEC[p.section] || ''}</span>` : ''}<span class="badge">${done} / 22 جلسة</span></div>`;
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
    const list = allP().filter(p => !q || [p.name, p.fileNo, p.phone].join(' ').includes(q)).sort((a, b) => (b.updated || b.created).localeCompare(a.updated || a.created));
    $('#pl').innerHTML = list.length ? list.map(pCard).join('') : `<div class="empty">لا توجد ملفات بعد. اضغط «مريض جديد» للبدء.</div>`;
  };
  $('#ps').addEventListener('input', draw); draw();
  liveRedraw = draw;
}

/* ---------- patient file ---------- */
const head = (title, sub) => `<div class="sheet-head"><div class="logo"><b>Motion Life</b><small>مركز الأخصائي يزن جهاد العلواني</small></div>
  <div class="tag"><b>${title}</b>${sub}</div></div>`;
const inp = (k, label, type = 'text', v = '') => `<div class="f"><label>${label}:</label><input data-k="${k}" type="${type}" value="${esc(v)}"></div>`;
const ta = (k, rows, v) => `<textarea class="lined" data-k="${k}" rows="${rows}">${esc(v)}</textarea>`;
const PAIN_C = ['#2e9e5b','#4caf50','#7cb342','#c0ca33','#fdd835','#fbc02d','#ffa000','#f57c00','#ef6c00','#e64a19','#c62828'];

function patientView(p, tab) {
  const tabs = `<div class="pid-bar"><span class="pid-name">👤 <b data-live="name">${esc(p.name || 'مريض جديد')}</b></span><span>رقم الملف: <b data-live="fileNo">${esc(p.fileNo)}</b></span><span id="payB">${payBadge(p)}</span>${multiSec() ? `<span class="badge sec-${p.section}">${SEC[p.section]}</span>` : ''}</div>
  ${alertsHTML(p)}
  <div class="ptabs">
    <button class="tab ${tab === '0' ? 'on' : ''}" data-go="p/${p.id}/0">📝 الاستبيان الطبي السريع</button>
    <button class="tab ${tab === '1' ? 'on' : ''}" data-go="p/${p.id}/1">١- ملف المريض والتقييم</button>
    <button class="tab ${tab === '2' ? 'on' : ''}" data-go="p/${p.id}/2">٢- الخطة العلاجية والجلسات</button>
    <button class="tab ${tab === '3' ? 'on' : ''}" data-go="p/${p.id}/3">📈 ٣- تطور الحالة والصور</button>
    <span class="spacer"></span><span class="saved" id="sv"></span>
    <button class="btn ghost sm" id="prt">🖨️ طباعة الملف</button>
    <button class="btn ghost sm" id="prtEx">🖨️ ورقة تمارين للمريض</button>
    ${TH() && !can('delFiles') ? '' : '<button class="btn danger sm" id="delP">حذف</button>'}</div>`;
  return tabs + (tab === '3' ? page3(p) : tab === '2' ? page2(p) : tab === '0' ? page0(p) : page1(p));
}

/* ---------- الاستبيان الطبي السريع (قبل الفحص الأولي) ---------- */
const IQ = {
  onset: ['تدريجياً', 'فجأة', 'بعد إصابة/حادث', 'بعد عملية'],
  sym: ['ألم', 'تنميل/خدر', 'ضعف', 'تيبس/صعوبة حركة', 'تورم'],
  flags: ['تغير جديد بالتبول/التبرز أو خدر بين الفخذين', 'ضعف جديد أو سريع التفاقم بأحد الأطراف', 'ألم صدر/ضيق نفس/إغماء غير معتاد',
    'حرارة غير مفسرة أو نقص وزن غير مقصود', 'سقوط/رض مهم أو ألم شديد غير معتاد ليلاً', 'ألم أو تورم جديد غير معتاد بساق واحدة'],
  hx: ['لا أمراض معروفة', 'ضغط/قلب', 'سكري', 'مرض عصبي/جلطة', 'سرطان'],
};
const arrOf = (p, k) => Array.isArray(p[k]) ? p[k] : [];
const redFlags = p => arrOf(p, 'iq_flags').filter(x => x !== 'لا يوجد');
function alertsHTML(p) {
  const a = [];
  if (redFlags(p).length) a.push(`<b>⚠️ علامات خطر في الاستبيان:</b> ${redFlags(p).map(esc).join('، ')} — يجب إخبار المعالج قبل بدء العلاج.`);
  const c = [];
  if (p.iq_implant === 'نعم') c.push('منظم قلب أو معدن مزروع');
  if (p.iq_preg === 'نعم' || p.iq_preg === 'غير مؤكدة') c.push('حمل ' + (p.iq_preg === 'نعم' ? '' : '(غير مؤكد)'));
  if (p.iq_meds === 'نعم') c.push('أدوية منتظمة/مميعات/كورتيزون');
  if (p.iq_osteo === 'نعم') c.push('هشاشة عظام' + (p.iq_osteoGrade ? ' (' + p.iq_osteoGrade + ')' : ''));
  if (p.iq_allergy === 'نعم') c.push('حساسية');
  if (arrOf(p, 'iq_hx').includes('سرطان')) c.push('سرطان');
  if (c.length) a.push(`<b>ℹ️ انتبه قبل استخدام الأجهزة:</b> ${c.map(esc).join('، ')}`);
  return `<div id="alerts">${a.map((x, i) => `<div class="alert ${i === 0 && redFlags(p).length ? 'red' : 'amber'}">${x}</div>`).join('')}</div>`;
}
/* تحذيرات مهمة في صفحة الخطة العلاجية حسب الاستبيان */
function risksOf(p) {
  const r = [], hx = arrOf(p, 'iq_hx');
  if (redFlags(p).length) r.push(['red', 'علامات خطر من الاستبيان: ' + redFlags(p).join('، '), 'يجب مراجعة الطبيب أو المعالج المسؤول قبل بدء أي علاج.']);
  if (p.iq_implant === 'نعم') r.push(['red', 'منظم قلب أو جهاز/معدن مزروع' + (p.iq_details ? ' — ' + p.iq_details : ''), 'لا تستخدم العلاج الكهربائي أو التحفيز المغناطيسي قرب منظم القلب، ولا الترددات الراديوية (TR-Therapy) أو الموجات الصادمة فوق منطقة المعدن. تأكد من نوع الجهاز المزروع ومكانه.']);
  if (hx.includes('سرطان')) r.push(['red', 'سرطان (حالي أو سابق)', 'لا تطبّق الحرارة أو العلاج الكهربائي أو الليزر أو الموجات فوق الصوتية/الصادمة فوق منطقة الورم، واستشر الطبيب المعالج.']);
  if (p.iq_preg === 'نعم' || p.iq_preg === 'غير مؤكدة') r.push(['red', 'حمل' + (p.iq_preg === 'نعم' ? '' : ' (غير مؤكد)'), 'تجنب العلاج الكهربائي والتحفيز المغناطيسي والموجات الصادمة والليزر فوق البطن وأسفل الظهر والحوض.']);
  if (p.iq_osteo === 'نعم') r.push(['amber', 'هشاشة العظام' + (p.iq_osteoGrade ? ' (' + p.iq_osteoGrade + ')' : '') + (p.iq_tscore ? ' — T-score: ' + p.iq_tscore : ''), 'تجنب الشد الفقري القوي (DRX) والضغط اليدوي العنيف والموجات الصادمة على العظم الهش، وابدأ التمارين بأحمال خفيفة.']);
  if (p.iq_meds === 'نعم') r.push(['amber', 'أدوية منتظمة / مميعات دم / كورتيزون', 'انتبه للكدمات والنزف: خفّف شدة الموجات الصادمة والشفط (Vac) والتدليك العميق.']);
  if (hx.includes('ضغط/قلب')) r.push(['amber', 'ضغط / أمراض قلب', 'راقب الضغط والنبض أثناء التمارين وأجهزة التحمل.']);
  if (hx.includes('سكري')) r.push(['amber', 'سكري', 'افحص الإحساس قبل الحرارة أو التبريد، وانتبه لهبوط السكر أثناء التمرين.']);
  if (hx.includes('مرض عصبي/جلطة')) r.push(['amber', 'مرض عصبي / جلطة', 'انتبه لنقص الإحساس عند الحرارة والتبريد والعلاج الكهربائي.']);
  if (p.iq_allergy === 'نعم') r.push(['amber', 'حساسية من دواء أو مادة' + (p.iq_details ? ' — ' + p.iq_details : ''), 'تحقق من الحساسية قبل استخدام الجل أو اللاصقات أو المراهم.']);
  if (p.iq_surgery === 'نعم') r.push(['amber', 'عملية سابقة مهمة أو كسر سابق', 'راجع مكان العملية/الكسر وموعدها قبل تطبيق الأجهزة أو الأحمال.']);
  if (p.iq_other) r.push(['amber', 'أمراض أخرى: ' + p.iq_other, '']);
  return r;
}
function riskBoxHTML(p) {
  const r = risksOf(p); if (!r.length) return '';
  return `<div class="riskbox"><div class="riskbox-t">⚠️ تحذيرات قبل العلاج (من الاستبيان الطبي)</div>${r.map(([c, t, d]) => `<div class="risk ${c}"><b>${esc(t)}</b>${d ? `<span>${esc(d)}</span>` : ''}</div>`).join('')}</div>`;
}
function sessLogHTML(p) {
  const L = sessionsOf(p); if (!L.length) return '<div class="empty" style="padding:8px">لا توجد جلسات منفذة بعد. تُسجَّل الجلسة عند اختيار «حضر» في الموعد أو بكتابة تاريخها في جدول الجلسات.</div>';
  return `<table class="slog"><thead><tr><th>#</th><th>التاريخ</th><th>اليوم</th><th>الوقت</th><th>المعالج</th><th>رقم الجلسة</th></tr></thead><tbody>${L.map((x, i) => { const t = therapists(p.section).find(y => y.id === x.tid || y.name === x.by);
    return `<tr><td>${i + 1}</td><td>${esc(x.date)}</td><td>${DAYS[new Date(x.date + 'T12:00:00').getDay()] || ''}</td><td>${x.time ? t12(x.time) : '—'}</td><td><span class="dot" style="background:${t ? t.color : '#8a9aa6'}"></span> ${esc(x.by || '—')}</td><td>${esc(x.no || '')}</td></tr>`; }).join('')}</tbody></table>`;
}
const cb = (k, v, p, extra = '') => `<label class="chk"><input type="checkbox" data-arr="${k}" value="${esc(v)}" ${arrOf(p, k).includes(v) ? 'checked' : ''} ${extra}>${esc(v)}</label>`;
const rb = (k, opts, p) => opts.map(v => `<label class="chk"><input type="radio" name="${k}_${p.id}" data-k="${k}" value="${esc(v)}" ${p[k] === v ? 'checked' : ''}>${esc(v)}</label>`).join('');
function page0(p) {
  return `<div class="sheet iq">${head('استبيان المريض السريع — التاريخ الطبي', 'قبل الفحص الأولي • الوقت المستهدف: دقيقتان')}
  <div class="box"><div class="box-t">١ | معلومات أساسية</div><div class="box-b grid2">
    ${inp('name', 'الاسم الكامل', 'text', p.name)}<div class="f"><label>العمر:</label><input data-k="age" type="number" value="${esc(p.age)}"><span>سنة</span></div>
    ${hidePhone() ? '' : inp('phone', 'رقم الهاتف', 'tel', p.phone)}${inp('iq_date', 'التاريخ', 'date', p.iq_date || today())}
  </div></div>
  <div class="box"><div class="box-t">٢ | سبب الزيارة</div><div class="box-b">
    <div class="grid2">${inp('iq_where', 'وين المشكلة الأساسية؟', 'text', p.iq_where)}${inp('iq_since', 'من إمتى؟', 'text', p.iq_since)}</div>
    <div class="qrow"><span class="lbl">كيف بدأت؟</span>${IQ.onset.map(v => cb('iq_onset', v, p)).join('')}</div>
    <div class="qrow"><span class="lbl">شو الأعراض؟</span>${IQ.sym.map(v => cb('iq_sym', v, p)).join('')}</div>
    <div class="grid2"><div class="f" style="align-items:center"><label>شدة الألم حالياً:</label>
      <div class="pain" id="pain">${Array.from({ length: 11 }, (_, i) => `<button type="button" data-v="${i}" class="${p.pain === i ? 'on' : ''}" style="${p.pain === i ? 'background:' + PAIN_C[i] : ''}">${i}</button>`).join('')}</div><span>/ ١٠</span></div>
      ${inp('iq_activity', 'شو أهم نشاط صار صعب عليك؟', 'text', p.iq_activity)}</div>
  </div></div>
  <div class="box"><div class="box-t">٣ | أسئلة سلامة مهمة — ضع علامة إذا كان العرض موجوداً حديثاً أو حالياً</div><div class="box-b">
    <div class="grid2 flags">${IQ.flags.map(v => cb('iq_flags', v, p, 'data-flag="1"')).join('')}</div>
    <div class="qrow"><span class="lbl">إذا ما عندك أي عرض مما سبق:</span>${cb('iq_flags', 'لا يوجد', p, 'data-none="1"')}</div>
    <div class="alert red" style="margin:6px 0 0">إذا ظهر أي عرض مقلق، أخبر الفريق مباشرة قبل بدء العلاج. الاستبيان لا يغني عن تقييم السلامة لدى المعالج.</div>
  </div></div>
  <div class="box"><div class="box-t">٤ | التاريخ الطبي — ضع علامة على الموجود لديك</div><div class="box-b">
    <div class="qrow">${IQ.hx.map(v => cb('iq_hx', v, p)).join('')}<div class="f" style="flex:1;min-width:200px"><label>أمراض أخرى:</label><input data-k="iq_other" value="${esc(p.iq_other || '')}"></div></div>
    <div class="qrow"><span class="lbl">هشاشة العظام:</span>${rb('iq_osteo', ['لا', 'نعم', 'لا أعرف'], p)}</div>
    <div class="qrow"><span class="lbl">إذا نعم، حسب تقرير الطبيب/الكثافة:</span>${rb('iq_osteoGrade', ['خفيفة', 'متوسطة', 'شديدة', 'غير محددة'], p)}</div>
    <div class="qrow"><small class="hint">تُسجّل الدرجة كما وردت بتقرير الطبيب، ولا تُقدّر من الأعراض.</small><div class="f" style="flex:1;min-width:220px"><label>نتيجة قياس الكثافة (T-score) إن توفرت:</label><input data-k="iq_tscore" value="${esc(p.iq_tscore || '')}" dir="ltr"></div><small class="hint">(يفسرها المعالج/الطبيب)</small></div>
    <div class="grid2 yn">
      <div class="qrow"><span class="lbl">حساسية من دواء أو مادة؟</span>${rb('iq_allergy', ['لا', 'نعم'], p)}</div>
      <div class="qrow"><span class="lbl">أدوية منتظمة أو مميعات دم/كورتيزون؟</span>${rb('iq_meds', ['لا', 'نعم'], p)}</div>
      <div class="qrow"><span class="lbl">منظم قلب أو جهاز/معدن مزروع؟</span>${rb('iq_implant', ['لا', 'نعم'], p)}</div>
      <div class="qrow"><span class="lbl">عملية سابقة مهمة أو كسر سابق؟</span>${rb('iq_surgery', ['لا', 'نعم'], p)}</div>
      <div class="qrow"><span class="lbl">حمل أو احتمال حمل؟ (إن ينطبق)</span>${rb('iq_preg', ['لا', 'نعم', 'غير مؤكدة'], p)}</div>
      <div class="fcol"><span class="lbl">تفاصيل مهمة عند اختيار «نعم»:</span><input class="line-in" data-k="iq_details" value="${esc(p.iq_details || '')}"></div>
    </div>
  </div></div>
  <div class="box"><div class="box-t">٥ | تأكيد المعلومات</div><div class="box-b">
    <p style="margin:0 0 8px">أؤكد أن إجاباتي صحيحة بحسب معرفتي، وسأخبر الفريق عن أي تغير صحي مهم. أفهم أن هذا الاستبيان لا يحل محل الفحص أو الموافقة العلاجية المستنيرة.</p>
    <div class="grid2">${inp('iq_sign', 'توقيع المريض/الولي', 'text', p.iq_sign)}<div class="f"><label>رقم الملف (للاستقبال):</label><input value="${esc(p.fileNo)}" readonly tabindex="-1"></div></div>
  </div></div>
  <div class="box internal"><div class="box-t">للاستخدام الداخلي فقط — لا يعبئه المريض</div><div class="box-b">
    <div class="grid2 yn"><div class="qrow"><span class="lbl">هل يلزم استقصاء/إحالة قبل العلاج؟</span>${rb('iq_referral', ['نعم', 'لا'], p)}</div>
      <div class="qrow"><span class="lbl">تمت مراجعة الاستبيان مع المريض؟</span>${rb('iq_reviewed', ['نعم', 'لا'], p)}</div>
      ${inp('iq_therapist', 'اسم/توقيع المعالج', 'text', p.iq_therapist)}${inp('iq_notes', 'ملاحظات مختصرة', 'text', p.iq_notes)}</div>
  </div></div>
  </div>
  <div class="row"><span class="spacer"></span><button class="btn big" data-go="p/${p.id}/1">التالي: ملف المريض والتقييم ←</button></div>`;
}

/* ملخص نتائج الاستبيان الطبي السريع (يظهر في ملف التقييم بدل الشكوى والأمراض المزمنة) */
const reasonOf = p => [p.iq_where, p.complaint].filter(Boolean).join(' — ');
function iqSummary(p) {
  const yes = (k, t) => p[k] === 'نعم' ? t : null, j = a => a.filter(Boolean).join('، ');
  const R = [];
  const where = [p.iq_where, p.iq_since ? 'منذ ' + p.iq_since : '', arrOf(p, 'iq_onset').length ? 'بدأت ' + j(arrOf(p, 'iq_onset')) : ''].filter(Boolean).join(' · ');
  if (where) R.push(['المشكلة الأساسية وسبب الزيارة', where]);
  const sym = [j(arrOf(p, 'iq_sym')), isNum(p.pain) ? 'شدة الألم ' + p.pain + '/10' : '', p.iq_activity ? 'النشاط الصعب: ' + p.iq_activity : ''].filter(Boolean).join(' · ');
  if (sym) R.push(['الأعراض', sym]);
  const hx = j(arrOf(p, 'iq_hx').concat([p.iq_other,
    p.iq_osteo === 'نعم' ? 'هشاشة عظام' + (p.iq_osteoGrade ? ' (' + p.iq_osteoGrade + ')' : '') + (p.iq_tscore ? ' T-score ' + p.iq_tscore : '') : p.iq_osteo === 'لا أعرف' ? 'هشاشة العظام: لا يعرف' : '',
    yes('iq_allergy', 'حساسية'), yes('iq_meds', 'أدوية منتظمة/مميعات/كورتيزون'), yes('iq_implant', 'منظم قلب/معدن مزروع'), yes('iq_surgery', 'عملية أو كسر سابق'),
    p.iq_preg === 'نعم' ? 'حمل' : p.iq_preg === 'غير مؤكدة' ? 'حمل غير مؤكد' : '']));
  if (hx) R.push(['التاريخ الطبي', hx]);
  if (p.iq_details) R.push(['تفاصيل', p.iq_details]);
  const fl = arrOf(p, 'iq_flags');
  if (fl.length) R.push(['علامات الخطر', redFlags(p).length ? '⚠️ ' + j(redFlags(p)) : 'لا يوجد', redFlags(p).length ? 'red' : '']);
  if (p.complaint) R.push(['الشكوى (مسجلة سابقاً)', p.complaint]);
  if (p.chronic) R.push(['أمراض مزمنة/أدوية/عمليات (مسجلة سابقاً)', p.chronic]);
  return R;
}
function iqSummaryHTML(p) {
  const R = iqSummary(p);
  if (!R.length) return `<div class="empty" style="padding:10px">لم يُعبّأ الاستبيان الطبي السريع بعد — <a href="#p/${p.id}/0">افتح الاستبيان</a> وسيظهر ملخصه هنا تلقائياً.</div>`;
  return `<div class="iqsum">${R.map(([k, v, c]) => `<div class="${c || ''}"><b>${esc(k)}:</b> <span>${esc(v)}</span></div>`).join('')}</div>`;
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
    ${hidePhone() ? '' : inp('phone', 'رقم الهاتف', 'tel', p.phone)}${inp('job', 'المهنة', 'text', p.job)}${inp('evalDate', 'تاريخ التقييم', 'date', p.evalDate)}
  </div>
  <div class="box"><div class="box-t">📝 ملخص الاستبيان: المشكلة الأساسية وسبب الزيارة والتاريخ الطبي<span class="spacer"></span><button class="btn sm light keep" type="button" data-go="p/${p.id}/0">✏️ تعديل في الاستبيان</button></div><div class="box-b">
    <div id="iqSum">${iqSummaryHTML(p)}</div>
    <div class="fcol" style="margin-top:10px"><span class="lbl lbl-mic">القصة المرضية ${micBtn('history')}</span>${ta('history', 4, p.history)}</div>
  </div></div>
  <div class="box"><div class="box-t lbl-mic">التقييم السريري ${micBtn('clinical')}</div><div class="box-b">${ta('clinical', 6, p.clinical)}</div></div>
  <div class="box"><div class="box-t">الأعراض الحالية ومقياس الألم</div><div class="box-b grid2">
    <div class="fcol"><span class="lbl lbl-mic">الأعراض الحالية ${micBtn('symptoms')}</span>${ta('symptoms', 3, p.symptoms)}</div>
    <div class="fcol"><div class="f" style="align-items:center"><label>شدة الألم:</label>
      <div class="pain" id="pain">${Array.from({ length: 11 }, (_, i) => `<button type="button" data-v="${i}" class="${p.pain === i ? 'on' : ''}" style="${p.pain === i ? 'background:' + PAIN_C[i] : ''}">${i}</button>`).join('')}</div></div>
      <div style="margin-top:8px">${pt.map(t => `<label class="chk"><input type="checkbox" data-pt="${t}" ${p.painType.includes(t) ? 'checked' : ''}>${t}</label>`).join('')}</div>
      ${inp('duration', 'مدة الأعراض', 'text', p.duration)}
      <div class="f scale-f"><label>التشنج العضلي:</label>${scaleHTML('spasm', p.spasm)}<span>/ ١٠</span></div></div>
  </div></div>
  <div class="box"><div class="box-t">القوة العضلية والقيود الحالية</div><div class="box-b grid2">
    <div class="fcol"><span class="lbl">القوة العضلية (من 1 إلى 5) — اختر الطرف العلوي أو السفلي أو كليهما</span>
      <div class="mmt-row"><div class="mmt"><b>💪 طرف علوي</b>${scaleHTML('mmtU', p.mmtU)}</div><div class="mmt"><b>🦵 طرف سفلي</b>${scaleHTML('mmtL', p.mmtL)}</div></div>
      <textarea class="lined" data-k="strength" rows="2" placeholder="ملاحظات القوة العضلية (العضلة / الجهة...)">${esc(p.strength)}</textarea></div>
    <div class="fcol"><span class="lbl lbl-mic">القيود / الصعوبات الحالية ${micBtn('limits')}</span>${ta('limits', 3, p.limits)}</div>
  </div></div>
  <div class="sign">${inp('notes', 'ملاحظات عامة', 'text', p.notes)}${inp('therapist', 'اسم / توقيع المعالج', 'text', p.therapist)}</div>
  ${filesBoxHTML(p)}
  </div>
  <div class="row"><span class="spacer"></span><button class="btn big" data-go="p/${p.id}/2">التالي: الخطة العلاجية ←</button></div>`;
}

const paidOf = p => (p.payments || []).reduce((a, x) => a + num(x.amount), 0) + (p.payMode === 'session' ? (p.sessions || []).reduce((a, x) => a + num(x.amount), 0) : 0);
const totalOf = p => num(p.agreedTotal) || (p.payMode === 'session' ? num(p.sessionPrice) * num(p.agreedSessions) : 0);
const remainOf = p => totalOf(p) ? fmt(totalOf(p) - paidOf(p)) : '';
function page2(p) {
  const ps = p.payMode === 'session' && !hidePrices();
  const half = (from, to) => `<table class="sess"><thead><tr><th>الجلسة</th><th>التاريخ</th><th>الملاحظات / الاستجابة</th><th>المعالج</th>${ps ? '<th>المبلغ</th>' : ''}</tr></thead><tbody>
    ${p.sessions.slice(from, to).map((s, j) => { const i = from + j; return `<tr><td class="n">${i + 1}</td>
      <td><input type="date" data-s="${i}" data-f="date" value="${esc(s.date)}"></td>
      <td><input data-s="${i}" data-f="note" value="${esc(s.note)}"></td>
      <td><input data-s="${i}" data-f="by" value="${esc(s.by)}" style="width:90px"></td>${ps ? `<td><input data-s="${i}" data-f="amount" value="${esc(s.amount || '')}" inputmode="numeric" style="width:70px" ${lockPay() ? 'disabled title="قسم الدفعات للإدارة فقط"' : ''}></td>` : ''}</tr>`; }).join('')}</tbody></table>`;
  const paid = paidOf(p);
  const hist = patientAppts(p.id);
  return `<div class="sheet">${head('الخطة العلاجية ومتابعة الجلسات', 'حتى 22 جلسة')}
  <div class="grid3" style="margin-bottom:16px">
    ${inp('startDate', 'تاريخ بدء العلاج', 'date', p.startDate)}
    <div class="f"><label>رقم الملف:</label><div class="auto" data-live="fileNo">${esc(p.fileNo)}</div></div>
    <div class="f"><label>اسم المريض:</label><div class="auto" data-live="name">${esc(p.name)}</div></div>
  </div>
  <div id="riskBox">${riskBoxHTML(p)}</div>
  <div class="box"><div class="box-t lbl-mic">الخطة العلاجية ${micBtn('plan')}</div><div class="box-b">
    ${ta('plan', 4, p.plan)}
    <div class="plan-sub"><h4>⚡ الأجهزة العلاجية والبروتوكولات <span class="cnt">${p.devices.length}</span><span class="spacer"></span><button class="btn sm" id="addDev">➕ إضافة جهاز</button></h4>
      <div id="devList">${devListHTML(p)}</div></div>
    <div class="plan-sub"><h4>🏃 التمارين العلاجية <span class="cnt">${p.exercises.length}</span><span class="spacer"></span><button class="btn sm" id="addEx">➕ إضافة تمارين من المكتبة</button></h4>
      <div id="exList">${exListHTML(p)}</div></div>
  </div></div>
  <div class="sess-wrap">${half(0, 11)}${half(11, 22)}</div>
  <div class="box"><div class="box-t">🗓️ سجل الجلسات المنفذة <span class="cnt">${sessionsOf(p).length} جلسة</span><span class="spacer"></span><button class="btn sm" id="addMeas2" type="button">📈 تسجيل قياسات الجلسة</button></div><div class="box-b">${sessLogHTML(p)}
    <details class="hist-box" style="margin:10px 0 0"><summary>📋 كل المواعيد المحجوزة (${hist.length}) — يُعبّأ سطر الجلسة تلقائياً عند تأكيد «حضر»</summary>${histHTML(hist, p.section)}</details></div></div>
  <div class="grid2" style="margin-bottom:14px">
    <div class="fcol"><span class="lbl">التقييم بعد الجلسة السادسة:</span>${ta('eval6', 2, p.eval6)}</div>
    <div class="fcol"><span class="lbl">التقييم بعد الجلسة الثانية عشرة:</span>${ta('eval12', 2, p.eval12)}</div>
  </div>
  ${hidePrices() ? noPriceBox(p) : `<fieldset class="payarea" ${lockPay() ? 'disabled' : ''}>${lockPay() ? '<div class="alert amber" style="margin-bottom:8px">🔒 قسم الدفعات للعرض فقط — التعديل للإدارة والاستقبال.</div>' : ''}
  <div class="paymode"><span class="lbl">طريقة الدفع:</span>
    <label class="chk"><input type="radio" name="pm" data-k="payMode" value="" ${ps ? '' : 'checked'}>دفعات</label>
    <label class="chk"><input type="radio" name="pm" data-k="payMode" value="session" ${ps ? 'checked' : ''}>مبلغ مقابل كل جلسة</label>
    ${ps ? `<div class="f" style="flex:1;min-width:200px"><label>سعر الجلسة:</label><input data-k="sessionPrice" value="${esc(p.sessionPrice || '')}" inputmode="numeric"></div>
      <button class="btn" id="addSessPay" type="button">➕ إضافة جلسة مع دفعة</button>` : ''}</div>
  <div class="pay">
    <div class="paybox">${inp('agreedSessions', 'عدد الجلسات المتفق عليها', 'text', p.agreedSessions)}</div>
    <div class="paybox">${inp('agreedTotal', 'المبلغ الإجمالي المتفق عليه', 'text', p.agreedTotal)}</div>
    ${p.payments.map((x, i) => `<div class="paybox soft"><div class="row" style="flex-wrap:nowrap"><b style="white-space:nowrap">الدفعة ${i + 1}:</b>
      <div class="f" style="flex:1"><label>المبلغ</label><input data-pay="${i}" data-f="amount" value="${esc(x.amount)}" inputmode="numeric"></div>
      <div class="f" style="flex:1"><label>التاريخ</label><input type="date" data-pay="${i}" data-f="date" value="${esc(x.date)}"></div></div></div>`).join('')}
    <div class="paybox"><div class="f"><label>المبلغ المتبقي:</label><input id="remain" readonly value="${remainOf(p)}"></div></div>
    <div class="paybox"><div class="f"><label>إجمالي المبلغ المدفوع:</label><input id="paid" readonly value="${paid ? fmt(paid) : ''}"></div></div>
  </div></fieldset>`}</div>`;
}
/* المعالج بدون صلاحية رؤية الأسعار: عدد الجلسات + المبلغ المتبقي فقط */
function noPriceBox(p) {
  const s = payState(p);
  return `<div class="box"><div class="box-t">الجلسات والذمم المالية</div><div class="box-b pay">
    <div class="paybox"><div class="f"><label>عدد الجلسات المتفق عليها:</label><div class="auto">${esc(p.agreedSessions || '—')}</div></div></div>
    <div class="paybox"><div class="f"><label>الجلسات المنفذة:</label><div class="auto">${sessionsOf(p).length}</div></div></div>
    <div class="paybox"><div class="f"><label>المبلغ المتبقي:</label><div class="auto" id="remainNP">${s.status === 'due' ? `<b class="rem-red">${fmt(s.remain)}</b>` : s.status === 'done' ? '<b class="ok-green">✓ مكتمل الدفع</b>' : '—'}</div></div></div>
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

let livePatient = null, liveRedraw = null, curP = null;
function bindPatient(p, tab) {
  let t;
  const dirty = DB.dirty[p.id] = DB.dirty[p.id] || new Set();
  const touch = (...keys) => {
    keys.forEach(k => dirty.add(k)); clearTimeout(t); $('#sv').textContent = '...';
    t = setTimeout(() => { const ks = [...dirty]; dirty.clear();
      DB.savePatient(p, ks).then(() => { if ($('#sv')) $('#sv').textContent = '✓ تم الحفظ'; }).catch(() => { if ($('#sv')) $('#sv').textContent = '⚠️ لم يُحفظ — تحقق من الاتصال'; });
      if (DB.mode === 'cloud' && $('#sv')) $('#sv').textContent = DB.online ? '✓ تم الحفظ والمزامنة' : '✓ محفوظ — سيُزامن عند عودة الإنترنت';
    }, 400); };
  $$('[data-k]').forEach(el => el.addEventListener(el.type === 'radio' ? 'change' : 'input', () => { p[el.dataset.k] = el.value; touch(el.dataset.k);
    if (['agreedTotal', 'agreedSessions', 'sessionPrice'].includes(el.dataset.k)) calc();
    if (el.dataset.k === 'name' || el.dataset.k === 'fileNo') $$(`[data-live="${el.dataset.k}"]`).forEach(x => x.textContent = el.value || (el.dataset.k === 'name' ? 'مريض جديد' : ''));
    if (el.dataset.k === 'payMode') { clearTimeout(t); const ks = [...dirty]; dirty.clear(); DB.savePatient(p, ks); render(); } }));
  $$('[data-arr]').forEach(el => el.addEventListener('change', () => { const k = el.dataset.arr; let a = arrOf(p, k).filter(x => x !== el.value);
    if (el.checked) a.push(el.value);
    if (k === 'iq_flags') { if (el.dataset.none && el.checked) a = ['لا يوجد']; else if (el.checked) a = a.filter(x => x !== 'لا يوجد');
      $$('[data-arr="iq_flags"]').forEach(x => { x.checked = a.includes(x.value); }); }
    p[k] = a; touch(k); refreshAlerts(); }));
  const refreshAlerts = () => { const box = $('#alerts'); if (box) box.outerHTML = alertsHTML(p); const sm = $('#iqSum'); if (sm) sm.innerHTML = iqSummaryHTML(p); const rb = $('#riskBox'); if (rb) rb.innerHTML = riskBoxHTML(p); };
  curP = p;
  $$('[data-k^="iq_"]').forEach(el => el.addEventListener('change', refreshAlerts));
  $$('[data-pt]').forEach(el => el.addEventListener('change', () => { const v = el.dataset.pt; p.painType = p.painType.filter(x => x !== v); if (el.checked) p.painType.push(v); touch('painType'); }));
  const pain = $('#pain');
  const drawPain = () => $$('button', pain).forEach(x => { const on = +x.dataset.v === p.pain; x.classList.toggle('on', on); x.style.background = on ? PAIN_C[p.pain] : ''; });
  if (pain) pain.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; const v = +b.dataset.v; p.pain = p.pain === v ? null : v; drawPain(); touch('pain'); });
  $$('#app .scale[data-scale]').forEach(box => box.addEventListener('click', e => { const b = e.target.closest('button'); if (!b || b.disabled) return; const k = box.dataset.scale, v = +b.dataset.v;
    p[k] = p[k] === v ? null : v; paintScale(box, p[k]); touch(k); }));
  $$('[data-s]').forEach(el => el.addEventListener('input', () => { p.sessions[+el.dataset.s][el.dataset.f] = el.value; touch('sessions'); if (el.dataset.f === 'amount') calc(); }));
  const calc = () => { if ($('#remainNP')) { const b = $('#remainNP').closest('.box'); if (b) b.outerHTML = noPriceBox(p); } const paid = paidOf(p); if ($('#paid')) { $('#paid').value = paid ? fmt(paid) : ''; $('#remain').value = remainOf(p); } if ($('#payB')) $('#payB').innerHTML = payBadge(p); };
  $$('[data-pay]').forEach(el => el.addEventListener('input', () => { p.payments[+el.dataset.pay][el.dataset.f] = el.value; touch('payments'); calc(); }));
  bindMics();
  if ($('#addSessPay')) $('#addSessPay').onclick = () => {
    const i = p.sessions.findIndex(x => !x.date && !x.amount); if (i < 0) return toast('كل الجلسات الـ22 معبأة');
    const ths = therapists(p.section);
    openModal(`<div class="modal-h"><h3>إضافة جلسة مع دفعة — الجلسة ${i + 1}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
      <div class="pform">
        <div class="fcol"><span class="lbl">التاريخ</span><input type="date" id="sd" value="${today()}"></div>
        <div class="fcol"><span class="lbl">المبلغ المدفوع</span><input id="sa" value="${esc(p.sessionPrice || '')}" inputmode="numeric"></div>
        <div class="fcol" style="grid-column:1/-1"><span class="lbl">${p.section === 'women' ? 'المعالجة' : 'المعالج'}</span><div class="thpick">${ths.map(t => `<button type="button" class="thb" data-tid="${t.id}" style="--c:${t.color}"><span class="dot" style="background:${t.color}"></span>${esc(t.name)}</button>`).join('')}</div></div>
        <div class="fcol" style="grid-column:1/-1"><span class="lbl">ملاحظات / الاستجابة</span><input id="sn"></div>
      </div>
      <div class="modal-f"><button class="btn big" id="ok">✓ إضافة الجلسة والدفعة</button><button class="btn ghost" id="cn">إلغاء</button></div>`);
    let by = '';
    $$('[data-tid]').forEach(b => b.onclick = () => { by = b.textContent.trim(); $$('[data-tid]').forEach(x => x.classList.toggle('on', x === b)); });
    $('#mc').onclick = $('#cn').onclick = closeModal;
    $('#ok').onclick = () => { const amt = $('#sa').value.trim(); if (!amt) return toast('اكتب المبلغ');
      Object.assign(p.sessions[i], { date: $('#sd').value, amount: amt, by: by || p.sessions[i].by, note: $('#sn').value.trim() || p.sessions[i].note });
      clearTimeout(t); dirty.add('sessions'); const ks = [...dirty]; dirty.clear(); DB.savePatient(p, ks); closeModal(); render(); toast('تمت إضافة الجلسة ' + (i + 1) + ' مع الدفعة'); };
  };
  if ($('#addMeas2')) $('#addMeas2').onclick = () => progressModal(p);
  $('#prt').addEventListener('click', () => printPatient(p, false));
  $('#prtEx').addEventListener('click', () => p.exercises.length ? printPatient(p, true) : toast('أضف تمارين في الخطة العلاجية أولاً'));
  if ($('#delP')) $('#delP').addEventListener('click', () => {
    openModal(`<div class="modal-h"><h3>حذف ملف ${esc(p.name || 'المريض')}؟</h3></div><p>لا يمكن التراجع عن الحذف، وسيُحذف من كل الأجهزة.</p>
    <div class="row"><button class="btn danger" id="yes">نعم، احذف</button><button class="btn ghost" id="no">إلغاء</button></div>`);
    $('#yes').onclick = () => { clearTimeout(t); DB.deletePatient(p); closeModal(); go('patients'); }; $('#no').onclick = closeModal; });
  /* تحديث لحظي عند تعديل نفس الملف من جهاز آخر */
  let lastLists = JSON.stringify([p.devices, p.exercises]);
  livePatient = { id: p.id, apply() {
    $$('[data-k]').forEach(el => { if (el === document.activeElement) return; const v = p[el.dataset.k];
      if (el.type === 'radio') el.checked = el.value === v; else if (el.value !== (v == null ? '' : String(v))) el.value = v == null ? '' : v; });
    if (pain) drawPain();
    $$('#app .scale[data-scale]').forEach(box => paintScale(box, p[box.dataset.scale]));
    if ($('#modal').classList.contains('hidden')) { if (tab === '3' && progRedraw) progRedraw(); else if (filesRedraw) filesRedraw(); }
    $$('[data-arr]').forEach(el => { el.checked = arrOf(p, el.dataset.arr).includes(el.value); }); refreshAlerts();
    $$('[data-pt]').forEach(el => { el.checked = p.painType.includes(el.dataset.pt); });
    $$('[data-s]').forEach(el => { if (el !== document.activeElement) el.value = p.sessions[+el.dataset.s][el.dataset.f] || ''; });
    $$('[data-pay]').forEach(el => { if (el !== document.activeElement) el.value = p.payments[+el.dataset.pay][el.dataset.f] || ''; });
    calc();
    $$('[data-live]').forEach(x => { x.textContent = p[x.dataset.live] || ''; });
    const nl = JSON.stringify([p.devices, p.exercises]);
    if (tab === '2' && nl !== lastLists && $('#modal').classList.contains('hidden')) { lastLists = nl; redrawLists(); }
    $('#sv').textContent = '↻ تم التحديث من جهاز آخر';
  } };
  if (tab === '1') bindFiles(p);
  if (tab === '3') return bindProgress(p);
  if (tab !== '2') return;
  function redrawLists() { $('#devList').innerHTML = devListHTML(p); $('#exList').innerHTML = exListHTML(p); bindLists();
    $$('.plan-sub .cnt')[0].textContent = p.devices.length; $$('.plan-sub .cnt')[1].textContent = p.exercises.length; }
  const redraw = () => { redrawLists(); lastLists = JSON.stringify([p.devices, p.exercises]); touch('devices', 'exercises'); };
  function bindLists() {
    $$('[data-rdev]').forEach(b => b.onclick = () => { p.devices.splice(+b.dataset.rdev, 1); redraw(); });
    $$('[data-edev]').forEach(b => b.onclick = () => { const d = p.devices[+b.dataset.edev]; deviceParamsStep(DEVM[d.dev], d.program, d.values, d, v => { p.devices[+b.dataset.edev] = v; redraw(); }); });
    $$('[data-rex]').forEach(b => b.onclick = () => { p.exercises.splice(+b.dataset.rex, 1); redraw(); });
    $$('[data-exd]').forEach(el => el.oninput = () => { p.exercises[+el.dataset.exd].dosage = el.value; touch('exercises'); });
    $$('[data-exn]').forEach(el => el.oninput = () => { p.exercises[+el.dataset.exn].note = el.value; touch('exercises'); });
    $$('[data-exinfo]').forEach(el => el.onclick = () => exInfo(el.dataset.exinfo));
  }
  bindLists();
  $('#addDev').addEventListener('click', () => devicePicker(v => { p.devices.push(v); redraw(); toast('تمت إضافة الجهاز إلى الخطة'); }));
  $('#addEx').addEventListener('click', () => exercisePicker(p.exercises.map(x => x.code), codes => {
    codes.forEach(c => { if (!p.exercises.some(x => x.code === c)) p.exercises.push({ code: c, dosage: EXM[c].dosage, note: '' }); }); redraw(); toast('تمت إضافة ' + codes.length + ' تمرين'); }));
}

/* ---------- مقاييس الحالة وتطورها (الألم، التشنج، القوة العضلية) ---------- */
const SCALES = {
  pain: { min: 0, max: 10, low: true, name: 'الألم', unit: '/10' },
  spasm: { min: 1, max: 10, low: true, name: 'التشنج العضلي', unit: '/10' },
  mmtU: { min: 1, max: 5, low: false, name: 'القوة العضلية — طرف علوي', unit: '/5' },
  mmtL: { min: 1, max: 5, low: false, name: 'القوة العضلية — طرف سفلي', unit: '/5' }
};
const isNum = v => typeof v === 'number' && !isNaN(v);
const scaleColor = (k, v) => { const S = SCALES[k]; const t = (v - S.min) / ((S.max - S.min) || 1); return PAIN_C[Math.round((S.low ? t : 1 - t) * 10)]; };
const scaleHTML = (k, v) => { const S = SCALES[k]; return `<div class="scale" data-scale="${k}">${Array.from({ length: S.max - S.min + 1 }, (_, i) => { const n = S.min + i; return `<button type="button" data-v="${n}" class="${v === n ? 'on' : ''}" style="${v === n ? 'background:' + scaleColor(k, n) : ''}">${n}</button>`; }).join('')}</div>`; };
function paintScale(box, v) { const k = box.dataset.scale; $$('button', box).forEach(b => { const on = +b.dataset.v === v; b.classList.toggle('on', on); b.style.background = on ? scaleColor(k, +b.dataset.v) : ''; }); }
const STAGES = [['before', 'قبل العلاج'], ['during', 'أثناء العلاج'], ['after', 'بعد العلاج (إعادة التقييم)'], ['report', 'تقارير / صور أشعة'], ['other', 'أخرى']];
const STG = Object.fromEntries(STAGES);
let progRedraw = null, filesRedraw = null;

/* نقاط التطور: التقييم الأولي + قياسات الجلسات */
function progPoints(p) {
  const out = [];
  const base = { short: 'أولي', label: 'التقييم الأولي', date: p.evalDate || '', pain: p.pain, spasm: p.spasm, mmtU: p.mmtU, mmtL: p.mmtL, base: true };
  if (Object.keys(SCALES).some(k => isNum(base[k]))) out.push(base);
  [...(p.progress || [])].sort((a, b) => (a.date || '').localeCompare(b.date || '') || (+a.no || 0) - (+b.no || 0)).forEach(r => {
    out.push(Object.assign({}, r, { short: r.re ? 'إعادة' : (r.no ? 'ج' + r.no : '•'), label: r.re ? 'إعادة تقييم' + (r.no ? ' (الجلسة ' + r.no + ')' : '') : (r.no ? 'الجلسة ' + r.no : 'جلسة') }));
  });
  return out;
}
function progSummary(p) {
  const pts = progPoints(p);
  return Object.keys(SCALES).map(k => {
    const S = SCALES[k], vals = pts.filter(x => isNum(x[k]));
    if (!vals.length) return null;
    const first = vals[0], last = vals[vals.length - 1], d = last[k] - first[k];
    const better = vals.length > 1 && (S.low ? d < 0 : d > 0), worse = vals.length > 1 && (S.low ? d > 0 : d < 0);
    const pct = first[k] ? Math.round(Math.abs(d) / first[k] * 100) : (d ? 100 : 0);
    return { k, S, first, last, n: vals.length, better, worse, pct, d };
  }).filter(Boolean);
}
function summaryHTML(p) {
  const L = progSummary(p);
  if (!L.length) return '<div class="empty">لا توجد قياسات بعد. سجّل مقياس الألم والتشنج والقوة العضلية في «ملف المريض والتقييم» (التقييم الأولي)، ثم بعد كل جلسة من زر «تسجيل قياسات جلسة».</div>';
  return `<div class="pgsum">${L.map(x => `<div class="pgcard ${x.better ? 'good' : x.worse ? 'bad' : 'flat'}"><div class="pgk">${esc(x.S.name)}</div>
    <div class="pgv"><span title="${esc(x.first.label)}">${x.first[x.k]}</span><span class="arr">←</span><b title="${esc(x.last.label)}">${x.last[x.k]}</b><small>${x.S.unit}</small></div>
    <div class="pgst">${x.n < 2 ? 'قياس واحد فقط' : x.better ? `▲ تحسّن ${x.pct}%` : x.worse ? `▼ تراجع ${x.pct}%` : '■ بدون تغيير'}</div>
    <small class="hint">من ${esc(x.first.label)} إلى ${esc(x.last.label)}</small></div>`).join('')}</div>`;
}
/* رسم بياني خطي (SVG) لكل مقياس */
function chartSVG(title, pts, series, min, max) {
  const W = 440, H = 220, L = 28, R = 30, T = 14, B = 32, pw = W - L - R - 28, ph = H - T - B, n = pts.length;
  const x = i => L + 14 + (n <= 1 ? pw / 2 : i * pw / (n - 1)), y = v => T + (max - v) / (max - min) * ph;
  const step = max - min > 6 ? 2 : 1, every = Math.ceil(n / 8);
  let g = '';
  for (let v = max; v >= min; v -= step) g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="cg"/><text x="${L - 8}" y="${y(v) + 4}" class="ct" text-anchor="end">${v}</text>`;
  pts.forEach((pt, i) => { if (i % every === 0 || i === n - 1) g += `<text x="${x(i)}" y="${H - 12}" class="ct" text-anchor="middle">${esc(pt.short)}</text>`; });
  let marks = '', has = false;
  series.forEach(s => {
    const P = pts.map((pt, i) => isNum(pt[s.k]) ? [x(i), y(pt[s.k]), pt, i] : null).filter(Boolean); if (!P.length) return; has = true;
    if (P.length > 1) marks += `<polyline points="${P.map(q => q[0].toFixed(1) + ',' + q[1].toFixed(1)).join(' ')}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
    P.forEach(([cx, cy, pt]) => { marks += `<g class="cpt"><circle cx="${cx}" cy="${cy}" r="5" fill="${s.color}" stroke="#fff" stroke-width="2"/><circle cx="${cx}" cy="${cy}" r="13" fill="transparent"><title>${esc(pt.label)}${pt.date ? ' — ' + esc(pt.date) : ''}\n${esc(s.name)}: ${pt[s.k]}</title></circle></g>`; });
    const lq = P[P.length - 1]; marks += `<text x="${lq[0] + 11}" y="${lq[1] + 4}" class="cv">${lq[2][s.k]}</text>`;
  });
  const legend = series.length > 1 ? `<div class="clg">${series.map(s => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('')}</div>` : '';
  return `<div class="chart"><div class="chart-t">${esc(title)}</div>${legend}${has ? `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}" dir="ltr">${g}${marks}</svg>` : '<div class="empty" style="padding:18px">لا توجد قياسات لهذا المقياس بعد</div>'}</div>`;
}
function chartsHTML(p) {
  const pts = progPoints(p); if (!pts.length) return '';
  return `<div class="charts">
    ${chartSVG('📉 مقياس الألم (0 = بدون ألم، 10 = أشد ألم)', pts, [{ k: 'pain', name: 'الألم', color: '#13788a' }], 0, 10)}
    ${chartSVG('📉 مقياس التشنج العضلي (1 – 10)', pts, [{ k: 'spasm', name: 'التشنج', color: '#13788a' }], 1, 10)}
    ${chartSVG('📈 القوة العضلية (1 – 5)', pts, [{ k: 'mmtU', name: 'طرف علوي', color: '#2f7fd0' }, { k: 'mmtL', name: 'طرف سفلي', color: '#e07b12' }], 1, 5)}
  </div>`;
}
function progTableHTML(p, actions) {
  const pts = progPoints(p); if (!pts.length) return '';
  const c = (k, v) => isNum(v) ? `<span class="sv" style="--c:${scaleColor(k, v)}">${v}</span>` : '—';
  return `<table class="slog prog"><thead><tr><th>القياس</th><th>التاريخ</th><th>الألم</th><th>التشنج</th><th>قوة علوي</th><th>قوة سفلي</th><th>المعالج</th><th>ملاحظات</th>${actions ? '<th></th>' : ''}</tr></thead><tbody>
    ${pts.map(r => `<tr class="${r.base ? 'base' : r.re ? 're' : ''}"><td><b>${esc(r.label)}</b></td><td>${esc(r.date || '')}</td><td>${c('pain', r.pain)}</td><td>${c('spasm', r.spasm)}</td><td>${c('mmtU', r.mmtU)}</td><td>${c('mmtL', r.mmtL)}</td><td>${esc(r.base ? (p.therapist || '') : (r.by || ''))}</td><td>${esc(r.note || '')}</td>
      ${actions ? `<td style="white-space:nowrap">${r.base ? `<button class="btn light sm" data-go="p/${p.id}/1" type="button">تعديل</button>` : `<button class="btn light sm" data-pedit="${r.id}" type="button">تعديل</button><button class="x" data-pdel="${r.id}" type="button" title="حذف">×</button>`}</td>` : ''}</tr>`).join('')}</tbody></table>`;
}
function page3(p) {
  return `<div class="sheet" id="progPage">${head('تطور الحالة', 'القياسات بعد كل جلسة • الصور قبل وبعد العلاج')}
    <div class="row" style="margin-bottom:12px"><button class="btn" id="addMeas" type="button">➕ تسجيل قياسات جلسة</button><span class="spacer"></span><button class="btn light keep" id="prtProg" type="button">🖨️ تقرير تطور الحالة</button></div>
    <div id="progBody"></div>
    ${filesBoxHTML(p)}
  </div>`;
}
function filesBoxHTML(p) {
  return `<div class="box files-box" style="margin-top:16px"><div class="box-t">📷 الصور والتقارير والملفات <span class="cnt" data-fcnt>${(p.files || []).length}</span><span class="spacer"></span><button class="btn sm keep" data-cmp type="button">🔍 مقارنة قبل / بعد</button></div>
    <div class="box-b">${canFiles(p) ? `<div class="row upl" style="margin-bottom:10px"><span class="lbl">تصنيف الملف:</span><select data-fstage class="sel keep">${STAGES.map(([k, t]) => `<option value="${k}">${t}</option>`).join('')}</select>
      <label class="btn" style="cursor:pointer">⬆️ رفع صور أو ملفات<input type="file" data-fup class="keep" multiple accept="image/*,application/pdf,video/*,.doc,.docx" hidden></label><span data-fprog class="hint"></span></div>` : ''}
    <div data-fgal></div></div></div>`;
}
/* ربط قسم الصور والملفات (يعمل في صفحة التقييم وصفحة تطور الحالة) */
function bindFiles(p, after) {
  const box = $('#app .files-box'); if (!box) return;
  const draw = () => {
    $('[data-fgal]', box).innerHTML = galleryHTML(p); $('[data-fcnt]', box).textContent = (p.files || []).length;
    const me = DB.me && DB.me.user;
    $$('[data-fdel]', box).forEach(b => { const f = (p.files || []).find(x => x.id === b.dataset.fdel); if (!canEditP(p) && !(f && f.u && f.u === me)) b.remove(); });
    $$('[data-fopen]', box).forEach(a => a.onclick = e => { e.preventDefault(); const f = p.files.find(x => x.id === a.dataset.fopen); if (f) openFile(p, f); });
    $$('[data-fdel]', box).forEach(b => b.onclick = () => confirmDel('حذف هذا الملف من ملف المريض؟', () => { p.files = p.files.filter(x => x.id !== b.dataset.fdel); DB.savePatient(p, ['files']); draw(); }));
    hydrateImgs(p, box);
  };
  draw(); filesRedraw = draw;
  $('[data-cmp]', box).onclick = () => compareModal(p);
  const up = $('[data-fup]', box);
  if (up) up.onchange = async e => { const fs = [...e.target.files]; e.target.value = ''; if (fs.length) { await uploadFiles(p, fs, $('[data-fstage]', box).value, $('[data-fprog]', box)); draw(); after && after(); } };
}
function galleryHTML(p) {
  const F = p.files || []; if (!F.length) return '<div class="empty">لا توجد صور أو ملفات بعد. صوّر المريض قبل بدء العلاج، ثم بعد إعادة التقييم لمقارنة النتيجة.</div>';
  return STAGES.map(([k, t]) => { const L = F.filter(f => (f.stage || 'other') === k); if (!L.length) return '';
    return `<div class="fgrp"><div class="lbl">${t} <span class="cnt">${L.length}</span></div><div class="fgrid">${L.map(f => `<figure class="fitem">
      <a href="#" data-fopen="${f.id}">${/^image\//.test(f.type) ? `<img data-fimg="${f.id}" alt="">` : `<span class="fic">${/pdf/.test(f.type) ? '📄' : /video/.test(f.type) ? '🎬' : '📎'}</span>`}</a>
      <figcaption><b>${esc(f.name || '')}</b><small>${esc(f.date || '')}${f.by ? ' · ' + esc(f.by) : ''}</small></figcaption>
      <button class="x" data-fdel="${f.id}" type="button" title="حذف">×</button></figure>`).join('')}</div></div>`; }).join('');
}
async function hydrateImgs(p, root) {
  for (const el of $$('[data-fimg]', root)) { const f = (p.files || []).find(x => x.id === el.dataset.fimg); if (!f) continue; try { const u = await DB.fileSrc(p.section, p.id, f); if (u) el.src = u; } catch (e) {} }
}
async function openFile(p, f) {
  const u = await DB.fileSrc(p.section, p.id, f); if (!u) return toast('تعذّر فتح الملف');
  if (/^image\//.test(f.type)) { openModal(`<div class="modal-h"><h3>${esc(f.name || '')} <small class="hint">${esc(STG[f.stage] || '')} · ${esc(f.date || '')}</small></h3><span class="spacer"></span><button class="x" id="mc">×</button></div><img src="${u}" class="bigimg" alt="">`); $('#mc').onclick = closeModal; return; }
  let href = u; if (u.startsWith('data:')) { const b = await (await fetch(u)).blob(); href = URL.createObjectURL(b); }
  window.open(href, '_blank');
}
function shrinkImage(file, maxD, q) {
  return new Promise(ok => { const url = URL.createObjectURL(file), im = new Image();
    im.onload = () => { const s = Math.min(1, maxD / Math.max(im.width, im.height)); const c = document.createElement('canvas'); c.width = Math.round(im.width * s); c.height = Math.round(im.height * s);
      c.getContext('2d').drawImage(im, 0, 0, c.width, c.height); URL.revokeObjectURL(url); c.toBlob(b => ok(b || file), 'image/jpeg', q); };
    im.onerror = () => { URL.revokeObjectURL(url); ok(file); }; im.src = url; });
}
async function uploadFiles(p, files, stage, prog) {
  if (DB.mode === 'server' && !DB.online) return toast('رفع الملفات يحتاج الاتصال بخادم المركز');
  let n = 0;
  for (const f of files) {
    prog && (prog.textContent = `جارٍ رفع ${n + 1} من ${files.length}...`);
    let blob = f, name = f.name || 'file';
    if (/^image\/(jpeg|png|webp|bmp)/.test(f.type)) { blob = await shrinkImage(f, DB.mode === 'server' ? 1800 : 1100, DB.mode === 'server' ? 0.85 : 0.72); if (blob !== f) name = name.replace(/\.\w+$/, '') + '.jpg'; }
    if (blob.size > 50e6) { toast('الملف «' + name + '» أكبر من 50 ميغا'); continue; }
    try { const r = await DB.uploadFile(p.section, p.id, blob, name);
      p.files = p.files || []; p.files.push({ id: r.id, name, type: blob.type || f.type || '', size: r.size, stage, date: today(), by: myName() || DB.label(), u: (DB.me && DB.me.user) || DB.role || '', at: new Date().toISOString() });
      await DB.savePatient(p, ['files']); n++;
    } catch (e) { toast(e.code === 'denied' ? '🔒 لا تملك صلاحية تعديل هذا الملف' : e.code === 'big' ? 'الملف كبير جداً لهذه النسخة — استخدم نظام المركز' : e.code === 'offline' ? 'لا يوجد اتصال بخادم المركز' : 'تعذّر رفع «' + name + '»'); }
  }
  prog && (prog.textContent = '');
  if (n) toast('تم رفع ' + n + ' ملف وحفظه في ملف المريض');
}
function compareModal(p) {
  const imgs = (p.files || []).filter(f => /^image\//.test(f.type));
  if (imgs.length < 2) return toast('ارفع صورة «قبل العلاج» وصورة «بعد العلاج» أولاً');
  const opt = sel => imgs.map(f => `<option value="${f.id}" ${f.id === sel ? 'selected' : ''}>${esc(STG[f.stage] || '')} — ${esc(f.date || '')} — ${esc(f.name || '')}</option>`).join('');
  const bef = (imgs.find(f => f.stage === 'before') || imgs[0]).id;
  const aft = ([...imgs].reverse().find(f => f.stage === 'after') || [...imgs].reverse().find(f => f.stage === 'during') || imgs[imgs.length - 1]).id;
  openModal(`<div class="modal-h"><h3>🔍 مقارنة قبل / بعد — ${esc(p.name || '')}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
    <div class="cmp"><div><select class="sel" id="cA">${opt(bef)}</select><img id="iA" alt=""></div><div><select class="sel" id="cB">${opt(aft)}</select><img id="iB" alt=""></div></div>
    ${progSummary(p).length ? summaryHTML(p) : ''}`);
  const show = async (s, im) => { const f = imgs.find(x => x.id === $(s).value); $(im).src = f ? await DB.fileSrc(p.section, p.id, f) : ''; };
  $('#cA').onchange = () => show('#cA', '#iA'); $('#cB').onchange = () => show('#cB', '#iB'); show('#cA', '#iA'); show('#cB', '#iB');
  $('#mc').onclick = closeModal;
}
/* نافذة تسجيل قياسات الجلسة */
function progressModal(p, preset) {
  preset = preset || {};
  p.progress = p.progress || [];
  const ex = preset.id ? p.progress.find(r => r.id === preset.id) : (preset.date && preset.no ? p.progress.find(r => r.date === preset.date && String(r.no) === String(preset.no)) : null);
  const r = Object.assign({ date: today(), no: '', by: myName() || '', pain: null, spasm: null, mmtU: null, mmtL: null, note: '', re: false }, ex || {}, ex ? {} : preset);
  if (!r.no && !ex) { const mx = Math.max(0, ...p.progress.map(x => +x.no || 0)); r.no = String(Math.max(mx + 1, sessionsOf(p).length || 1)); }
  const v = Object.assign({}, r);
  const names = therapists(p.section).map(t => t.name); if (r.by && !names.includes(r.by)) names.unshift(r.by);
  openModal(`<div class="modal-h"><h3>📈 قياسات الجلسة — ${esc(p.name || '')}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
    ${preset.fromAppt ? '<div class="help" style="margin:0 0 10px">✓ تم تسجيل الحضور. سجّل قياسات هذه الجلسة لمتابعة تطور الحالة (أو اضغط «تخطي»).</div>' : ''}
    <div class="pform">
      <div class="fcol"><span class="lbl">التاريخ</span><input type="date" id="mD" value="${esc(r.date)}"></div>
      <div class="fcol"><span class="lbl">رقم الجلسة</span><select id="mN" class="sel"><option value="">—</option>${Array.from({ length: 40 }, (_, i) => `<option value="${i + 1}" ${String(r.no) === String(i + 1) ? 'selected' : ''}>الجلسة ${i + 1}</option>`).join('')}</select></div>
      <div class="fcol"><span class="lbl">${p.section === 'women' ? 'المعالجة' : 'المعالج'}</span><select id="mB" class="sel"><option value="">—</option>${names.map(n => `<option ${n === r.by ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></div>
      <div class="fcol"><label class="chk" style="margin-top:22px"><input type="checkbox" id="mR" ${r.re ? 'checked' : ''}>إعادة تقييم (نهاية العلاج)</label></div>
    </div>
    <div class="mscales">
      <div class="f scale-f"><label>الألم (0–10):</label>${scaleHTML('pain', r.pain)}</div>
      <div class="f scale-f"><label>التشنج العضلي (1–10):</label>${scaleHTML('spasm', r.spasm)}</div>
      <div class="mmt-row"><div class="mmt"><b>💪 قوة الطرف العلوي (1–5)</b>${scaleHTML('mmtU', r.mmtU)}</div><div class="mmt"><b>🦵 قوة الطرف السفلي (1–5)</b>${scaleHTML('mmtL', r.mmtL)}</div></div>
    </div>
    <div class="fcol" style="margin-top:10px"><span class="lbl">ملاحظات / الاستجابة للعلاج</span><input id="mT" value="${esc(r.note || '')}"></div>
    <div class="modal-f"><button class="btn big" id="ok">✓ حفظ القياسات</button><button class="btn ghost" id="cn">${preset.fromAppt ? 'تخطي' : 'إلغاء'}</button></div>`);
  $$('#modalBox .scale').forEach(box => box.onclick = e => { const b = e.target.closest('button'); if (!b) return; const k = box.dataset.scale, n = +b.dataset.v; v[k] = v[k] === n ? null : n; paintScale(box, v[k]); });
  $('#mc').onclick = $('#cn').onclick = closeModal;
  $('#ok').onclick = () => {
    if (!Object.keys(SCALES).some(k => isNum(v[k]))) return toast('اختر قيمة لمقياس واحد على الأقل');
    const rec = { id: ex ? ex.id : uid('m'), date: $('#mD').value || today(), no: $('#mN').value, by: $('#mB').value, re: $('#mR').checked, note: $('#mT').value.trim(),
      pain: isNum(v.pain) ? v.pain : null, spasm: isNum(v.spasm) ? v.spasm : null, mmtU: isNum(v.mmtU) ? v.mmtU : null, mmtL: isNum(v.mmtL) ? v.mmtL : null, at: new Date().toISOString() };
    if (ex) Object.assign(ex, rec); else p.progress.push(rec);
    DB.savePatient(p, ['progress']); closeModal(); toast('تم حفظ القياسات');
    if (current === 'p' && (location.hash.split('/')[1] || '') === p.id) { if (progRedraw) progRedraw(); else render(); }
  };
}
function bindProgress(p) {
  const draw = () => {
    $('#progBody').innerHTML = `${summaryHTML(p)}${chartsHTML(p)}${progPoints(p).length ? `<div class="lbl" style="margin:14px 0 6px">📋 جدول القياسات</div><div class="fin-tbl">${progTableHTML(p, canEditP(p))}</div>` : ''}`;
    if (!canEditP(p)) $$('[data-pedit], [data-pdel]').forEach(el => el.remove());
    $$('#progBody [data-go]').forEach(b => b.onclick = () => go(b.dataset.go));
    $$('[data-pedit]').forEach(b => b.onclick = () => progressModal(p, { id: b.dataset.pedit }));
    $$('[data-pdel]').forEach(b => b.onclick = () => { if (!confirmDel('حذف هذا القياس؟', () => { p.progress = p.progress.filter(x => x.id !== b.dataset.pdel); DB.savePatient(p, ['progress']); draw(); })) return; });
  };
  progRedraw = () => { draw(); filesRedraw && filesRedraw(); }; draw(); bindFiles(p);
  $('#addMeas').onclick = () => progressModal(p);
  $('#prtProg').onclick = () => printProgress(p);
}
function confirmDel(msg, fn) {
  openModal(`<div class="modal-h"><h3>${esc(msg)}</h3></div><div class="row"><button class="btn danger" id="yes">نعم، احذف</button><button class="btn ghost" id="no">إلغاء</button></div>`);
  $('#yes').onclick = () => { closeModal(); fn(); }; $('#no').onclick = closeModal; return true;
}
/* تقرير تطور الحالة للطباعة */
async function printProgress(p) {
  const imgs = (p.files || []).filter(f => /^image\//.test(f.type));
  const bef = imgs.filter(f => f.stage === 'before').slice(0, 2), aft = imgs.filter(f => f.stage === 'after').slice(-2);
  const src = async f => { try { return await DB.fileSrc(p.section, p.id, f); } catch (e) { return ''; } };
  const ph = async (L, t) => L.length ? `<div class="fcol"><span class="lbl">${t}</span>${(await Promise.all(L.map(async f => `<figure class="rimg"><img src="${await src(f)}" alt=""><figcaption>${esc(f.date || '')}</figcaption></figure>`))).join('')}</div>` : '';
  const photos = (bef.length || aft.length) ? `<div class="box"><div class="box-t">📷 صور قبل وبعد العلاج</div><div class="box-b grid2">${await ph(bef, 'قبل العلاج')}${await ph(aft, 'بعد العلاج')}</div></div>` : '';
  const ths = [...new Set(progPoints(p).map(r => r.by).filter(Boolean).concat(sessionsOf(p).map(x => x.by).filter(Boolean)))];
  $('#print').innerHTML = `<div class="pg sheet rep">${head('تقرير تطور الحالة', esc(p.name || ''))}
    <div class="grid3" style="margin-bottom:8px">${pv('اسم المريض', p.name)}${pv('رقم الملف', p.fileNo)}${pv('العمر', p.age)}${pv('تاريخ التقييم الأولي', p.evalDate)}${pv('الجلسات المنفذة', String(sessionsOf(p).length))}${pv('المعالج', ths.join('، ') || p.therapist)}</div>
    ${pv('سبب الزيارة', reasonOf(p))}
    <div class="box"><div class="box-t">ملخص التحسن</div><div class="box-b">${summaryHTML(p)}</div></div>
    ${chartsHTML(p)}
    ${progTableHTML(p, false)}
    ${p.eval6 || p.eval12 ? `<div class="grid2" style="margin-top:8px">${pv('التقييم بعد الجلسة السادسة', p.eval6)}${pv('التقييم بعد الجلسة الثانية عشرة', p.eval12)}</div>` : ''}
    ${photos}
    ${pfoot('Motion Life - تقرير تطور الحالة', 'الحركة تبدأ من هنا')}</div>`;
  const ims = $$('#print img'); let left = ims.length; const go2 = () => setTimeout(() => window.print(), 200);
  if (!left) return go2(); ims.forEach(i => { if (i.complete) { if (--left === 0) go2(); } else i.onload = i.onerror = () => { if (--left === 0) go2(); }; });
}

/* ملف للعرض فقط (حسب صلاحيات المعالج) */
function makeReadOnly() {
  const sh = $$('#app .sheet'); if (!sh.length) return;
  sh[0].insertAdjacentHTML('beforebegin', '<div class="alert amber">🔒 هذا الملف للعرض فقط — لا تملك صلاحية تعديله. تواصل مع الإدارة.</div>');
  const fileOK = curP && canFiles(curP);
  $$('#app .sheet input, #app .sheet textarea, #app .sheet select, #app .sheet button, #app .pain button, #app .mic').forEach(el => { if (!el.classList.contains('keep') && !(fileOK && el.closest('.files-box'))) el.disabled = true; });
  $$('#addDev, #addEx, [data-rdev], [data-edev], [data-rex], #addSessPay, #addMeas, #addMeas2, [data-pedit], [data-pdel]').forEach(el => el.remove());
  if (!fileOK) $$('#app .upl').forEach(el => el.remove());
  livePatient && (livePatient.apply = (orig => function () { orig.call(this); makeReadOnlyInputs(); })(livePatient.apply));
}
function makeReadOnlyInputs() { $$('#app .sheet input, #app .sheet textarea, #app .sheet select').forEach(el => { if (!el.closest('.files-box')) el.disabled = true; }); }
/* ---------- voice to text (التسجيل الصوتي وتحويله لكتابة) ----------
   على خادم المركز: التحويل يتم على لابتوب المركز بدون إنترنت (whisper).
   على النسخة الأونلاين: خدمة المتصفح (تحتاج إنترنت). */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const micBtn = k => `<button type="button" class="mic" data-mic="${k}" title="سجّل بصوتك وسيُكتب تلقائياً">🎤 <span>تسجيل صوتي</span></button>`;
let rec = null, recBtn = null, sttAvail = null;
const USE_LOCAL_STT = false;
function stopMic() { if (rec) { try { rec.stop(); } catch (e) {} } }
function micHelp(title, body) { openModal(`<div class="modal-h"><h3>${title}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>${body}`); $('#mc').onclick = closeModal; }
function needSecure() {
  const host = location.hostname, https = `https://${host}:8443${location.pathname}${location.hash}`;
  micHelp('التسجيل الصوتي يحتاج الرابط الآمن', `<p>المتصفح لا يسمح باستخدام الميكروفون إلا على الرابط الآمن الذي يبدأ بـ <b dir="ltr">https</b>.</p>
    <p>افتح هذا الرابط وسجّل الدخول مرة واحدة:</p><p><a class="btn big" href="${https}" dir="ltr">${https.split('#')[0]}</a></p>
    <p class="hint">أول مرة ستظهر رسالة «الاتصال ليس خاصاً»: اضغط «متقدم» ثم «متابعة». هذا طبيعي لأن الشهادة خاصة بالمركز.</p>`);
}
function wavFrom(chunks, rate) {
  let n = 0; chunks.forEach(c => n += c.length);
  const buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
  const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); w(8, 'WAVE'); w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, 'data'); v.setUint32(40, n * 2, true);
  let o = 44; chunks.forEach(c => { for (let i = 0; i < c.length; i++, o += 2) { const x = Math.max(-1, Math.min(1, c[i])); v.setInt16(o, x < 0 ? x * 0x8000 : x * 0x7fff, true); } });
  return new Blob([buf], { type: 'audio/wav' });
}
async function serverMic(b, ta) {
  if (!window.isSecureContext || !navigator.mediaDevices) return needSecure();
  let stream; try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } }); }
  catch (e) { return micHelp('الميكروفون غير مسموح', '<p>اسمح للموقع باستخدام الميكروفون: اضغط على رمز القفل 🔒 بجانب العنوان ← الأذونات ← الميكروفون ← سماح، ثم أعد المحاولة.</p>'); }
  const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  if (ctx.state === 'suspended') { try { await ctx.resume(); } catch (e) {} }
  const src = ctx.createMediaStreamSource(stream), proc = ctx.createScriptProcessor(4096, 1, 1);
  const rate = ctx.sampleRate;
  let seg = [], segLen = 0, silent = 0, voicedLen = 0, floor = 0.01, queue = Promise.resolve(), pending = 0, stopped = false, t0 = Date.now(), wake = null;
  try { wake = await navigator.wakeLock.request('screen'); } catch (e) {}   // منع انطفاء شاشة التاب أثناء الحديث
  const base = () => ta.value ? ta.value.replace(/\s*$/, '') + ' ' : '';
  const label = $('span', b);
  const status = () => { const s = Math.floor((Date.now() - t0) / 1000), mm = Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
    label.textContent = stopped ? (pending ? '⏳ جارٍ الكتابة...' : 'تسجيل صوتي') : `⏺ ${mm} — اضغط للإيقاف${pending ? ' (يكتب...)' : ''}`; };
  const timer = setInterval(() => { if (!stopped) status(); }, 1000);
  const flush = () => {
    const enough = voicedLen / rate >= 0.4;
    const wav = enough && segLen ? wavFrom(seg, rate) : null; seg = []; segLen = 0; voicedLen = 0;
    if (!wav) return;
    pending++; status();
    queue = queue.then(async () => {
      try { const r = await fetch('/api/stt', { method: 'POST', headers: { Authorization: 'Bearer ' + store.get('ml_srv_token', ''), 'Content-Type': 'audio/wav' }, body: wav });
        const j = await r.json().catch(() => ({}));
        if (r.ok && j.text) { ta.value = base() + j.text; ta.dispatchEvent(new Event('input')); }
        else if (!r.ok) toast(j.error === 'stt_loading' ? 'محرك الصوت يبدأ التشغيل... أعد المحاولة بعد نصف دقيقة' : j.error === 'stt_down' ? 'محرك الصوت لا يعمل الآن على لابتوب المركز — شغّل UPDATE-MOTION-LIFE.bat' : 'تعذّر تحويل هذا المقطع');
      } catch (e) { toast('لا يوجد اتصال بخادم المركز'); }
      pending--; status(); if (stopped && !pending) b.classList.remove('rec', 'busy');
    });
  };
  proc.onaudioprocess = e => {
    if (stopped) return;
    const d = new Float32Array(e.inputBuffer.getChannelData(0)); let sum = 0; for (let i = 0; i < d.length; i++) sum += d[i] * d[i];
    const rms = Math.sqrt(sum / d.length);
    if (rms < floor * 1.5) floor = floor * 0.95 + rms * 0.05;            // يتعلّم مستوى ضجة الغرفة
    const speech = rms > Math.max(0.012, floor * 2.5);
    seg.push(d); segLen += d.length;
    if (speech) { voicedLen += d.length; silent = 0; } else silent += d.length;
    const secs = segLen / rate, pause = silent / rate;
    // نقطع فقط عند وقفة واضحة بعد جملة كاملة، أو كل 25 ثانية كحد أقصى
    if ((secs >= 6 && pause >= 1.3) || secs >= 25) flush();
  };
  src.connect(proc); proc.connect(ctx.destination);
  const finish = () => { if (stopped) return; stopped = true; clearInterval(timer); flush();
    try { proc.disconnect(); src.disconnect(); stream.getTracks().forEach(t => t.stop()); ctx.close(); } catch (e) {}
    try { wake && wake.release(); } catch (e) {}
    rec = null; recBtn = null; if (!pending) b.classList.remove('rec'); else b.classList.add('busy'); status(); };
  stream.getAudioTracks().forEach(t => t.onended = () => { toast('توقف الميكروفون — تم حفظ ما سُجّل'); finish(); });
  rec = { stop: finish };
  recBtn = b; b.classList.add('rec'); status(); toast('🎤 تكلّم بشكل طبيعي... يُكتب الكلام بعد كل وقفة. اضغط الزر مرة ثانية عند الانتهاء');
}
function browserMic(b, ta) {
  if (!SR) return micHelp('التسجيل الصوتي غير مدعوم في هذا المتصفح', '<p>افتح الموقع من متصفح <b>Google Chrome</b> أو <b>Microsoft Edge</b>، أو استخدم زر الميكروفون 🎤 في لوحة مفاتيح الجوال.</p>');
  const android = /Android/i.test(navigator.userAgent);
  const base = ta.value ? ta.value.replace(/\s*$/, '') + ' ' : '';
  let done = '', userStop = false, r = null;
  const show = cur => { ta.value = base + done + cur; ta.dispatchEvent(new Event('input')); };
  const startOne = () => {
    r = new SR(); r.lang = 'ar-SY'; r.interimResults = true;
    r.continuous = !android;              // أندرويد: جملة واحدة لكل جولة لتجنب تكرار الكلمات
    let cur = '';
    r.onresult = ev => {
      if (android) { const last = ev.results[ev.results.length - 1]; cur = last[0].transcript.trim(); show(cur); return; }
      let fin = '', interim = '';
      for (let i = 0; i < ev.results.length; i++) { const x = ev.results[i]; if (x.isFinal) fin += x[0].transcript.trim() + ' '; else interim += x[0].transcript; }
      cur = fin; show(fin + interim);
    };
    r.onerror = ev => {
      if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') { userStop = true; if (!window.isSecureContext) needSecure(); else toast('اسمح للموقع باستخدام الميكروفون من إعدادات المتصفح'); }
      else if (ev.error === 'network') { userStop = true; micHelp('خدمة تحويل الصوت غير متاحة', '<p>هذه الخدمة تعتمد على Google وتحتاج إنترنت، وقد تكون محجوبة في منطقتك.</p><p>الحل: استخدم النظام من <b>خادم المركز</b>، فالتحويل هناك يعمل على لابتوب المركز بدون إنترنت.</p>'); }
      else if (ev.error !== 'no-speech' && ev.error !== 'aborted') toast('تعذّر التسجيل: ' + ev.error); };
    r.onend = () => {
      if (cur) done += cur.replace(/\s*$/, '') + ' ';
      show('');
      if (!userStop) { try { startOne(); return; } catch (e) {} }
      b.classList.remove('rec'); $('span', b).textContent = 'تسجيل صوتي'; rec = null; recBtn = null;
    };
    r.start();
  };
  try { startOne(); rec = { stop() { userStop = true; try { r.stop(); } catch (e) {} } }; recBtn = b; b.classList.add('rec'); $('span', b).textContent = '⏺ إيقاف التسجيل'; toast('🎤 تكلّم الآن... اضغط مرة ثانية للإيقاف'); }
  catch (e) { toast('تعذّر تشغيل الميكروفون'); }
}
function bindMics() {
  $$('[data-mic]').forEach(b => b.onclick = async () => {
    if (recBtn === b) return stopMic();
    if (b.classList.contains('busy')) return;
    stopMic();
    const ta = document.querySelector(`[data-k="${b.dataset.mic}"]`);
    // التسجيل عبر خدمة Google في المتصفح (حسب طلب المركز). محرك اللابتوب المحلي يبقى جاهزاً للتفعيل لاحقاً: USE_LOCAL_STT = true
    if (USE_LOCAL_STT && DB.mode === 'server') {
      if (sttAvail === null) { try { sttAvail = !!(await (await fetch('/api/info')).json()).stt; } catch (e) { sttAvail = null; return toast('لا يوجد اتصال بخادم المركز'); } }
      if (sttAvail) return serverMic(b, ta);
    }
    browserMic(b, ta);
  });
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
    ${curP && risksOf(curP).length ? `<div class="riskbox" style="margin-top:12px"><div class="riskbox-t">⚠️ انتبه — هذا المريض لديه:</div>${risksOf(curP).map(([c, t]) => `<div class="risk ${c}"><b>${esc(t)}</b></div>`).join('')}</div>` : ''}
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
  <div class="lbl-s">٢- نوع التمرين (الهدف)</div><div class="chips" id="${prefix}t"><button class="chip on" data-v="">الكل</button>${D.types.map(t => `<button class="chip" data-v="${t.code}">${t.ar}</button>`).join('')}</div>
  <div class="lbl-s">٣- البرامج التخصصية</div><div class="chips prg" id="${prefix}p"><button class="chip on" data-v="">الكل</button>${D.programs.map(p => `<button class="chip" data-v="${p.code}">${p.ar}</button>`).join('')}</div>
  <div id="${prefix}pinfo"></div>`;
}
function useFilters(prefix, onChange) {
  const st = { r: '', t: '', p: '', q: '' };
  ['r', 't', 'p'].forEach(k => $('#' + prefix + k).addEventListener('click', e => { const b = e.target.closest('.chip'); if (!b) return; st[k] = b.dataset.v;
    $$('.chip', $('#' + prefix + k)).forEach(c => c.classList.toggle('on', c === b));
    if (k === 'p') { const P = PRG[st.p]; $('#' + prefix + 'pinfo').innerHTML = P ? `<div class="help prg-info"><b>${esc(P.ar)}:</b> ${esc(P.about)}${prefix === 'm' ? ' <button class="btn sm" id="selAllP">✓ اختيار كل تمارين البرنامج</button>' : ''}</div>` : ''; }
    onChange(st); }));
  $('#' + prefix + 'q').addEventListener('input', e => { st.q = e.target.value.trim(); onChange(st); });
  return st;
}
const filterEx = st => D.exercises.filter(e => (!st.r || e.region === st.r) && (!st.t || e.type === st.t) && (!st.p || e.programs.includes(st.p)) && (!st.q || (e.name_ar + ' ' + e.name_en + ' ' + e.steps).toLowerCase().includes(st.q.toLowerCase())));
const exCard = (e, sel) => `<div class="card ${sel ? 'sel' : ''}" data-ex="${e.code}"><img src="${fig(e.code)}" alt="" loading="lazy">
  <div class="t">${esc(e.name_ar)}</div><div><span class="badge">${esc(REG[e.region])}</span> <span class="badge o">${esc(TYP[e.type])}</span>${e.programs.map(p => ` <span class="badge p">${esc(PRG[p].ar.split(' (')[0].split(' —')[0])}</span>`).join('')}</div><div class="d">${esc(e.dosage)}</div></div>`;

function exercisePicker(already, done) {
  const sel = new Set();
  openModal(`<div class="modal-h"><h3>اختيار التمارين</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
    ${libFilters('m')}<div class="lib" id="ml"></div>
    <div class="modal-f"><button class="btn big" id="ok" disabled>إضافة التمارين المختارة (0)</button><button class="btn ghost" id="cn">إلغاء</button>
    <span class="spacer"></span><small style="color:var(--muted)">اضغط على التمرين لاختياره، واضغط مرة ثانية لإلغائه</small></div>`);
  const draw = st => { const L = filterEx(st); $('#ml').innerHTML = L.length ? L.map(e => exCard(e, sel.has(e.code)).replace('</div></div>', (already.includes(e.code) ? '<span class="badge" style="background:#e7f6ee;color:var(--ok)">موجود في الخطة</span>' : '') + '</div></div>')).join('') : '<div class="empty">لا توجد تمارين بهذه المواصفات.</div>'; };
  const st = useFilters('m', draw); draw(st);
  const upd = () => { $('#ok').textContent = `إضافة التمارين المختارة (${sel.size})`; $('#ok').disabled = !sel.size; };
  $('#ml').addEventListener('click', e => { const c = e.target.closest('.card'); if (!c) return; const k = c.dataset.ex; sel.has(k) ? sel.delete(k) : sel.add(k); c.classList.toggle('sel'); upd(); });
  $('#mpinfo').addEventListener('click', e => { if (!e.target.closest('#selAllP')) return; filterEx(st).forEach(x => sel.add(x.code)); draw(st); upd(); });
  $('#mc').onclick = closeModal; $('#cn').onclick = closeModal;
  $('#ok').onclick = () => { done([...sel]); closeModal(); };
}
function exInfo(code) {
  const e = EXM[code];
  openModal(`<div class="modal-h"><h3>${esc(e.name_ar)}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
    <div class="exd"><img src="${fig(code)}" alt=""><div>
      <div><span class="badge">${esc(REG[e.region])}</span> <span class="badge o">${esc(TYP[e.type])}</span>${e.programs.map(p => ` <span class="badge p">${esc(PRG[p].ar)}</span>`).join('')} ${e.name_en ? `<small style="color:var(--muted)">${esc(e.name_en)}</small>` : ''}</div>
      <h4 style="margin:12px 0 4px;color:var(--teal-d)">طريقة الأداء</h4><p style="margin:0">${esc(e.steps)}</p>
      <h4 style="margin:12px 0 4px;color:var(--teal-d)">الجرعة المقترحة</h4><p style="margin:0">${esc(e.dosage)}</p>
      <div class="warn" style="margin-top:12px">⚠️ ${esc(e.caution)}</div></div></div>`);
  $('#mc').onclick = closeModal;
}
function libraryView() {
  return `<div class="row"><h2 style="margin:0;color:var(--navy)">مكتبة التمارين</h2><span class="badge" id="lc"></span></div>
  <div class="help" style="margin-top:10px">اختر منطقة الجسم ثم نوع التمرين (تقوية، إطالة، ثبات، توازن...) أو برنامجاً تخصصياً مثل ماكنزي ووليامز. اضغط على أي تمرين لرؤية طريقة الأداء. لإضافة تمارين لمريض: افتح ملفه ← الخطة العلاجية ← «إضافة تمارين».</div>
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

/* ---------- appointments (المواعيد) ---------- */
const DAYS = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
const ST = { booked: 'محجوز', done: 'حضر', absent: 'لم يحضر', cancelled: 'ملغى' };
const t12 = hm => { let [h, m] = hm.split(':').map(Number); const ap = h < 12 ? 'ص' : 'م'; h = h % 12 || 12; return `${h}:${String(m).padStart(2, '0')} ${ap}`; };
const slotsOf = sec => { const [a, b] = SEC_HOURS[sec], out = []; for (let h = a; h < b; h++) for (let m = 0; m < 60; m += 10) out.push(String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0')); return out; };
const addDays = (d, n) => { const x = new Date(d + 'T12:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10); };
const dayName = d => DAYS[new Date(d + 'T12:00:00').getDay()];
const nowHM = () => { const n = new Date(); return String(n.getHours()).padStart(2, '0') + ':' + String(n.getMinutes()).padStart(2, '0'); };
function apptsView(sec, date) {
  sec = DB.sections().includes(sec) ? sec : DB.sections()[0]; date = /^\d{4}-\d{2}-\d{2}$/.test(date || '') ? date : today();
  const [a, b] = SEC_HOURS[sec];
  return `<div class="appt-head sec-${sec}">
    ${multiSec() ? `<div class="sec-tabs">${['women', 'men'].map(s => `<button class="sec-tab ${s === sec ? 'on' : ''} t-${s}" data-go="appts/${s}/${date}">${s === 'women' ? '👩' : '👨'} ${SEC[s]} <small>${t12(SEC_HOURS[s][0] + ':00')} – ${t12(SEC_HOURS[s][1] + ':00')}</small></button>`).join('')}</div>` : ''}
    <h2>${sec === 'women' ? '👩' : '👨'} مواعيد ${SEC[sec]} <small>من ${t12(a + ':00')} حتى ${t12(b + ':00')} · موعد كل 10 دقائق</small></h2>
    <div class="datebar">
      <button class="btn ghost" data-go="appts/${sec}/${addDays(date, -1)}">→ اليوم السابق</button>
      <div class="dbox"><b>${dayName(date)}</b><input type="date" id="dpick" value="${date}"></div>
      <button class="btn ghost" data-go="appts/${sec}/${addDays(date, 1)}">اليوم التالي ←</button>
      ${date !== today() ? `<button class="btn light" data-go="appts/${sec}/${today()}">اليوم</button>` : '<span class="badge">اليوم</span>'}
    </div>
    <div class="appt-sum" id="asum"></div>
  </div>
  <div class="agrid" id="agrid"></div>`;
}
/* therapists (المعالجون) */
const therapists = sec => (DB.meta[sec] && DB.meta[sec].therapists) || [];
const thOf = (sec, a) => therapists(sec).find(t => t.id === a.tid) || therapists(sec).find(t => t.name === a.by) || null;
const thColor = (sec, a) => { const t = thOf(sec, a); return t ? t.color : '#8a9aa6'; };
const patientAppts = (pid, exceptId) => [...DB.appts.values()].filter(x => x.patientId === pid && x.id !== exceptId).sort((x, y) => (y.date + y.time).localeCompare(x.date + x.time));
const nextSessionNo = pid => { if (!pid) return 1; const n = patientAppts(pid).filter(x => x.status !== 'cancelled' && x.status !== 'absent').map(x => +x.sessionNo || 0); return (n.length ? Math.max(...n) : 0) + 1; };
const histHTML = (list, sec) => list.length ? `<div class="hist">${list.map(x => `<div class="hist-r st-${x.status || 'booked'}"><span class="dot" style="background:${thColor(sec, x)}"></span>
  <b>${esc(x.date)}</b><span>${t12(x.time)}</span><span>${x.sessionNo ? 'جلسة ' + esc(x.sessionNo) : ''}</span><span>${esc((thOf(sec, x) || {}).name || x.by || '')}</span><i>${ST[x.status || 'booked']}</i>${x.amount ? `<span>💵 ${esc(x.amount)}</span>` : ''}</div>`).join('')}</div>` : '<div class="empty" style="padding:6px">لا توجد مواعيد سابقة</div>';

function bindAppts(sec, date) {
  sec = DB.sections().includes(sec) ? sec : DB.sections()[0]; date = /^\d{4}-\d{2}-\d{2}$/.test(date || '') ? date : today();
  $('#dpick').onchange = e => e.target.value && go(`appts/${sec}/${e.target.value}`);
  let tf = '';
  const draw = () => {
    const all = [...DB.appts.values()].filter(x => x.section === sec && x.date === date);
    const list = tf ? all.filter(x => (thOf(sec, x) || {}).id === tf) : all;
    const by = {}; list.forEach(x => (by[x.time] = by[x.time] || []).push(x));
    const slots = slotsOf(sec), isToday = date === today(), now = nowHM();
    const cnt = k => all.filter(x => (x.status || 'booked') === k).length;
    const free = slots.filter(t => !all.some(x => x.time === t && x.status !== 'cancelled')).length;
    $('#asum').innerHTML = `<span class="sb booked">محجوز: ${cnt('booked')}</span><span class="sb done">حضر: ${cnt('done')}</span><span class="sb absent">لم يحضر: ${cnt('absent')}</span><span class="sb cancelled">ملغى: ${cnt('cancelled')}</span><span class="sb free">مواعيد متاحة: ${free} من ${slots.length}</span>
      <div class="legend"><span class="lg-t">المعالجون:</span><button class="lg ${tf ? '' : 'on'}" data-tf="">الكل</button>${therapists(sec).map(t => { const n = all.filter(x => (thOf(sec, x) || {}).id === t.id && x.status !== 'cancelled').length;
        return `<button class="lg ${tf === t.id ? 'on' : ''}" data-tf="${t.id}" style="--c:${t.color}"><span class="dot" style="background:${t.color}"></span>${esc(t.name)}${n ? ` <small>${n}</small>` : ''}</button>`; }).join('')}</div>`;
    let html = '', curHour = '';
    slots.forEach((t, i) => {
      const h = t.slice(0, 2);
      if (h !== curHour) { if (curHour) html += '</div>'; curHour = h; html += `<div class="hour"><div class="hour-t">${t12(h + ':00')}</div>`; }
      const items = (by[t] || []).sort((x, y) => (x.created || '').localeCompare(y.created || ''));
      const next = slots[i + 1] || '99:99';
      const isNow = isToday && now >= t && now < next;
      const past = isToday && now >= next || date < today();
      html += `<div class="slot ${items.length ? 'has' : ''} ${isNow ? 'now' : ''} ${past ? 'past' : ''}"><div class="slot-t">${t12(t)}</div><div class="slot-b">
        ${items.map(x => { const th = thOf(sec, x); return `<button class="ap st-${x.status || 'booked'}" data-ap="${x.id}" style="--c:${th ? th.color : '#8a9aa6'}">
          <b>${esc(x.name || 'بدون اسم')}</b>${x.sessionNo ? `<span class="sn">ج${esc(x.sessionNo)}</span>` : ''}${th ? `<span class="thn">${esc(th.name)}</span>` : (x.by ? `<span class="thn">${esc(x.by)}</span>` : '')}${x.note ? `<span>· ${esc(x.note)}</span>` : ''}<i>${ST[x.status || 'booked']}</i></button>`; }).join('')}
        <button class="add-ap ${items.length ? 'small' : ''}" data-add="${t}">${items.length ? '+' : '+ حجز موعد'}</button></div></div>`;
    });
    $('#agrid').innerHTML = html + '</div>';
    $$('[data-tf]').forEach(b => b.onclick = () => { tf = b.dataset.tf; draw(); });
    $$('[data-add]').forEach(b => b.onclick = () => apptModal({ section: sec, date, time: b.dataset.add, tid: tf || '' }));
    $$('[data-ap]').forEach(b => b.onclick = () => apptModal(DB.appts.get(b.dataset.ap)));
  };
  draw(); liveRedraw = draw;
  if (date === today()) { const n = $('.slot.now'); if (n) setTimeout(() => n.scrollIntoView({ block: 'center' }), 50); }
}

function apptModal(a) {
  const isNew = !a.id; a = Object.assign({ name: '', phone: '', note: '', by: '', tid: '', status: 'booked', patientId: '', sessionNo: '', amount: '' }, a);
  const sec = a.section;
  const pts = allP().filter(p => p.section === sec);
  let pid = a.patientId, st = a.status, tid = (thOf(sec, a) || {}).id || a.tid || '';
  if (limAppt() && isNew) tid = myTid();
  const mine = !limAppt() || tid === myTid();
  const ro = limAppt() && !isNew && !mine;                                        // موعد معالج آخر: عرض فقط
  const canDel = !isNew && (!limAppt() || (mine && (!a.createdBy || a.createdBy === DB.me.user)));
  openModal(`<div class="modal-h"><h3>${isNew ? 'حجز موعد جديد' : ro ? 'تفاصيل الموعد (عرض فقط)' : 'تفاصيل الموعد'} — ${SEC[sec]}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
    <div class="pform">
      <div class="fcol" style="grid-column:1/-1;position:relative"><span class="lbl">اسم المريض <small class="hint">اكتب أول الاسم وستظهر ملفات المرضى للاختيار</small></span>
        <input id="an" value="${esc(a.name)}" autocomplete="off" placeholder="مثال: أحمد"><div class="sugg hidden" id="sg"></div></div>
      <div class="fcol" style="grid-column:1/-1" id="linkp"></div>
      <div class="fcol" ${hidePhone() ? 'style="display:none"' : ''}><span class="lbl">رقم الهاتف</span><input id="ap" value="${esc(a.phone)}" dir="ltr" inputmode="tel"></div>
      <div class="fcol"><span class="lbl">رقم الجلسة</span><select id="asn" class="sel"><option value="">—</option>${Array.from({ length: 22 }, (_, i) => `<option value="${i + 1}">الجلسة ${i + 1}</option>`).join('')}</select></div>
      <div class="fcol"><span class="lbl">التاريخ</span><input type="date" id="ad" value="${a.date}"></div>
      <div class="fcol"><span class="lbl">الوقت</span><select id="at" class="sel">${slotsOf(sec).map(t => `<option value="${t}" ${t === a.time ? 'selected' : ''}>${t12(t)}</option>`).join('')}</select></div>
      <div class="fcol" style="grid-column:1/-1"><span class="lbl">${sec === 'women' ? 'المعالجة' : 'المعالج'}</span>
        <div class="thpick">${therapists(sec).filter(t => !limAppt() || t.id === tid).map(t => `<button type="button" class="thb ${t.id === tid ? 'on' : ''}" data-tid="${t.id}" style="--c:${t.color}"><span class="dot" style="background:${t.color}"></span>${esc(t.name)}</button>`).join('')}</div></div>
      <div class="fcol"><span class="lbl">ملاحظة (نوع الجلسة...)</span><input id="ano" value="${esc(a.note)}"></div>
      <div class="fcol" ${lockPay() ? 'style="display:none"' : ''}><span class="lbl">المبلغ المدفوع لهذه الجلسة <small class="hint">(اختياري)</small></span><input id="aam" value="${esc(a.amount)}" inputmode="numeric"></div>
      ${isNew ? '' : `<div class="fcol" style="grid-column:1/-1"><span class="lbl">حالة الموعد</span><div class="stbtns">${Object.entries(ST).map(([k, v]) => `<button type="button" class="stb st-${k} ${a.status === k ? 'on' : ''}" data-st="${k}">${v}</button>`).join('')}</div></div>`}
    </div>
    <div id="histBox"></div>
    ${ro ? '<div class="alert amber" style="margin-top:10px">🔒 هذا الموعد لمعالج آخر — يمكنك مشاهدته فقط.</div>' : ''}
    ${!ro && limAppt() && !isNew && !canDel ? '<div class="alert amber" style="margin-top:10px">🔒 هذا الموعد أضافه مستخدم آخر — يمكنك تعديله لكن لا يمكنك حذفه.</div>' : ''}
    <div class="modal-f">${ro ? '' : `<button class="btn big" id="ok">${isNew ? '✓ حجز الموعد' : 'حفظ'}</button>`}<button class="btn ghost" id="cn">${ro ? 'إغلاق' : 'إلغاء'}</button><span class="spacer"></span>${canDel ? '<button class="btn danger" id="del">حذف الموعد</button>' : ''}${!isNew && a.createdBy ? `<small class="hint">أضافه: ${esc(a.createdBy)}</small>` : ''}</div>`);
  if (ro) $$('#modalBox input, #modalBox select, #modalBox .thb, #modalBox .stb').forEach(x => x.disabled = true);
  $('#asn').value = a.sessionNo || (isNew && pid ? nextSessionNo(pid) : a.sessionNo || '');
  const linkUI = () => { const p = pid && getP(pid); const nm = $('#an').value.trim();
    $('#linkp').innerHTML = p ? `<div class="linked">✅ مرتبط بملف <b>${esc(p.name)}</b> — رقم الملف ${esc(p.fileNo)} <button class="btn light sm" id="openf">📁 فتح الملف</button> <button class="btn ghost sm" id="unl">تغيير</button></div>`
      : nm ? (TH() && !can('createFiles') ? `<div class="newp">🔒 اختر المريض من القائمة — لا تملك صلاحية إضافة ملف جديد</div>` : `<div class="newp">🆕 مريض جديد — سيُنشأ له ملف تلقائياً باسم «${esc(nm)}» عند الحفظ</div>`) : '';
    $('#histBox').innerHTML = p ? `<div class="lbl" style="margin:12px 0 4px">📋 سجل المواعيد السابقة لهذا المريض</div>${histHTML(patientAppts(pid, a.id), sec)}` : '';
    if ($('#openf')) $('#openf').onclick = () => { if (save(true)) go('p/' + pid + '/2'); };
    if ($('#unl')) $('#unl').onclick = () => { pid = ''; $('#an').value = ''; $('#an').focus(); linkUI(); };
  };
  const pick = p => { pid = p.id; $('#an').value = p.name; $('#ap').value = p.phone || ''; $('#sg').classList.add('hidden'); if (isNew || !a.sessionNo) $('#asn').value = nextSessionNo(pid); linkUI(); };
  linkUI();
  const norm = x => String(x || '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي').toLowerCase();
  $('#an').oninput = () => { const q = norm($('#an').value.trim()); pid = '';
    const m = q ? pts.filter(p => norm(p.name).split(/\s+/).some(w => w.startsWith(q)) || norm(p.name).startsWith(q) || (p.phone || '').includes(q)).slice(0, 8) : [];
    const last = id => { const l = patientAppts(id)[0]; return l ? 'آخر موعد ' + l.date : 'لا مواعيد سابقة'; };
    $('#sg').innerHTML = q ? m.map(p => `<button type="button" data-pid="${p.id}"><b>${esc(p.name)}</b> <small>ملف ${esc(p.fileNo)}${hidePhone() ? '' : ' · ' + esc(p.phone || '—')} · ${last(p.id)}</small></button>`).join('') +
      (TH() && !can('createFiles') ? '' : `<button type="button" class="sg-new" id="sgNew">➕ إضافة مريض جديد باسم «${esc($('#an').value.trim())}»</button>`) : '';
    $('#sg').classList.toggle('hidden', !q);
    $$('[data-pid]', $('#sg')).forEach(b => b.onclick = () => pick(getP(b.dataset.pid)));
    $('#sgNew') && ($('#sgNew').onclick = () => { $('#sg').classList.add('hidden'); $('#asn').value = 1; $('#ap').focus(); });
    linkUI(); };
  $$('[data-tid]').forEach(b => b.onclick = () => { tid = tid === b.dataset.tid ? '' : b.dataset.tid; $$('[data-tid]').forEach(x => x.classList.toggle('on', x.dataset.tid === tid)); });
  $$('[data-st]').forEach(b => b.onclick = () => { st = b.dataset.st; $$('[data-st]').forEach(x => x.classList.toggle('on', x === b)); });
  function save(silent) {
    const name = $('#an').value.trim(); if (!name) { if (!silent) toast('اكتب اسم المريض'); return false; }
    if (!pid && TH() && !can('createFiles')) { if (!silent) toast('🔒 اختر المريض من الملفات الموجودة'); return false; }
    if (!pid) { const np = newPatient(sec, { name, phone: $('#ap').value.trim() }); DB.savePatient(np); pid = np.id; }
    const th = therapists(sec).find(t => t.id === tid);
    const o = Object.assign({}, a, { id: a.id || uid('a'), created: a.created || new Date().toISOString(), date: $('#ad').value || a.date, time: $('#at').value,
      name, phone: hidePhone() ? (a.phone || '') : $('#ap').value.trim(), tid: tid || '', createdBy: a.createdBy || (DB.me && DB.me.user) || DB.role || '', by: th ? th.name : '', note: $('#ano').value.trim(), status: st, patientId: pid, sessionNo: $('#asn').value, amount: $('#aam').value.trim() });
    DB.saveAppt(o); a.id = o.id; a.created = o.created;
    syncSessionRow(o);
    if (liveRedraw && current === 'appts') liveRedraw(); return true;
  }
  const wasDone = a.status === 'done';
  if ($('#ok')) $('#ok').onclick = () => { if (limAppt() && tid !== myTid()) return toast('يمكنك حجز المواعيد باسمك فقط'); const dv = $('#ad').value || a.date, sn = $('#asn').value; if (save()) { closeModal(); toast(isNew ? 'تم حجز الموعد وربطه بملف المريض' : 'تم الحفظ');
    const pp = getP(pid); if (st === 'done' && !wasDone && pp && canEditP(pp)) { const th = therapists(sec).find(t => t.id === tid); setTimeout(() => progressModal(pp, { date: dv, no: sn, by: th ? th.name : '', fromAppt: true }), 250); } } };
  $('#cn').onclick = closeModal; $('#mc').onclick = closeModal;
  if ($('#del')) $('#del').onclick = () => { DB.deleteAppt(a); closeModal(); if (liveRedraw) liveRedraw(); toast('تم حذف الموعد'); };
  if (isNew) $('#an').focus();
}
/* عند تأكيد الحضور: تعبئة سطر الجلسة في ملف المريض تلقائياً */
function syncSessionRow(o) {
  const p = getP(o.patientId); const n = +o.sessionNo; if (!p || !n || o.status !== 'done' || !canEditP(p)) return;
  while (p.sessions.length < n) p.sessions.push({ date: '', note: '', by: '' });
  const r = p.sessions[n - 1];
  r.date = o.date; if (o.by) r.by = o.by; if (o.amount) r.amount = o.amount; if (!r.note && o.note) r.note = o.note;
  if (o.amount && p.payMode !== 'session') { p.payMode = 'session'; DB.savePatient(p, ['sessions', 'payMode']); }
  else DB.savePatient(p, ['sessions']);
}

/* ---------- المتابعة المالية ---------- */
function lastPayDate(p) {
  const d = (p.payments || []).filter(x => num(x.amount) && x.date).map(x => x.date).concat((p.sessions || []).filter(x => num(x.amount) && x.date).map(x => x.date));
  return d.sort().pop() || '';
}
function patientTherapists(p) {
  const names = new Set(); sessionsOf(p).forEach(x => x.by && names.add(x.by));
  [...DB.appts.values()].filter(a => a.patientId === p.id).forEach(a => { const t = thOf(p.section, a); if (t) names.add(t.name); else if (a.by) names.add(a.by); });
  return [...names];
}
function financeView() {
  return `<div class="row"><h2 style="margin:0;color:var(--navy)">💰 المتابعة المالية</h2><span class="spacer"></span><span class="badge" id="finCnt"></span></div>
  <div class="help" style="margin-top:10px">${lockPay() ? 'تظهر هنا ملفات مرضاك (المرتبطين بك بجلسة واحدة أو أكثر) التي لم تكتمل دفعاتها.' : 'تظهر هنا كل الملفات التي لم تكتمل دفعاتها من المبلغ الإجمالي المتفق عليه.'} يختفي الملف من هذه القائمة تلقائياً عند اكتمال الدفع.</div>
  <input class="search" id="fq" placeholder="🔍 ابحث بالاسم أو رقم الملف" style="margin:6px 0 12px"><div id="finList"></div>`;
}
function bindFinance() {
  const draw = () => {
    const q = $('#fq').value.trim();
    const all = allP().filter(p => !lockPay() || linkedTo(p, myTid(), myName()));
    const due = all.filter(p => payState(p).status === 'due' && (!q || (p.name + ' ' + p.fileNo).includes(q))).sort((a, b) => payState(b).remain - payState(a).remain);
    const none = all.filter(p => payState(p).status === 'none').length;
    const totalRemain = due.reduce((s, p) => s + payState(p).remain, 0);
    $('#finCnt').textContent = due.length + ' ملف';
    const secs = DB.sections();
    $('#finList').innerHTML = (due.length ? `<div class="fin-sum">إجمالي المبالغ المتبقية: <b>${fmt(totalRemain)}</b></div>` : '') + secs.map(sec => {
      const L = due.filter(p => p.section === sec); if (!L.length) return secs.length > 1 ? `<h3 class="fin-sec">${SEC[sec]}</h3><div class="empty">لا توجد مبالغ متبقية ✓</div>` : '<div class="empty">لا توجد ملفات عليها مبالغ متبقية ✓</div>';
      return (secs.length > 1 ? `<h3 class="fin-sec">${SEC[sec]}</h3>` : '') + `<div class="fin-tbl"><table class="slog fin"><thead><tr><th>المريض</th><th>رقم الملف</th>${hidePrices() ? '' : '<th>المتفق عليه</th><th>المدفوع</th>'}<th>المتبقي</th>${hidePrices() ? '' : '<th>آخر دفعة</th>'}<th>الجلسات</th><th>المعالجون</th></tr></thead><tbody>${L.map(p => { const st = payState(p);
        return `<tr data-open="${p.id}"><td><span class="pay-dot due">●</span> <b>${esc(p.name || 'بدون اسم')}</b></td><td>${esc(p.fileNo)}</td>${hidePrices() ? '' : `<td>${fmt(st.total)}</td><td>${fmt(st.paid)}</td>`}<td class="rem">${fmt(st.remain)}</td>${hidePrices() ? '' : `<td>${esc(lastPayDate(p) || '—')}</td>`}<td>${sessionsOf(p).length}${p.agreedSessions ? ' / ' + esc(p.agreedSessions) : ''}</td><td>${patientTherapists(p).map(esc).join('، ') || '—'}</td></tr>`; }).join('')}</tbody></table></div>`;
    }).join('') + (none && !lockPay() ? `<p class="hint" style="margin-top:12px">ℹ️ يوجد ${none} ملف لم يُكتب فيه «المبلغ الإجمالي المتفق عليه» أو «سعر الجلسة»، لذلك لا تظهر في المتابعة المالية.</p>` : '');
    $$('[data-open]').forEach(r => r.onclick = () => go('p/' + r.dataset.open + '/2'));
  };
  $('#fq').oninput = draw; draw(); liveRedraw = draw;
}

/* ---------- إحصائيات المعالجين (للإدارة فقط) ---------- */
const PERIODS = [['today', 'اليوم'], ['yesterday', 'الأمس'], ['7', 'آخر 7 أيام'], ['30', 'آخر 30 يوم']];
function periodRange(k) { const t = today(); if (k === 'yesterday') { const y = addDays(t, -1); return [y, y]; } if (k === '7') return [addDays(t, -6), t]; if (k === '30') return [addDays(t, -29), t]; return [t, t]; }
function statsView(per) {
  per = PERIODS.some(x => x[0] === per) ? per : 'today';
  return `<h2 style="margin:0 0 10px;color:var(--navy)">📊 إحصائيات المعالجين</h2>
  <div class="chips">${PERIODS.map(([k, t]) => `<button class="chip ${k === per ? 'on' : ''}" data-go="stats/${k}">${t}</button>`).join('')}</div>
  <div id="statsBody"></div>`;
}
function bindStats(per) {
  per = PERIODS.some(x => x[0] === per) ? per : 'today';
  const draw = () => {
    const [from, to] = periodRange(per), cutoff = addDays(today(), -30);
    $('#statsBody').innerHTML = `<p class="hint">الفترة: ${from === to ? from : from + ' ← ' + to} · تُحسب الجلسة المنفذة عند اختيار «حضر» في الموعد أو عند تسجيلها في جدول جلسات المريض.</p>` + DB.sections().map(sec => {
      const pts = allP().filter(p => p.section === sec);
      const sess = []; pts.forEach(p => sessionsOf(p).forEach(x => { if (x.date >= from && x.date <= to) sess.push(Object.assign({ p }, x)); }));
      const cards = therapists(sec).map(t => {
        const mine = sess.filter(x => x.tid === t.id || x.by === t.name).sort((a, b) => (b.date + b.time).localeCompare(a.date + a.time));
        const current = pts.filter(p => [...DB.appts.values()].some(a => a.patientId === p.id && (a.tid === t.id || a.by === t.name) && a.date >= cutoff && a.status !== 'cancelled') || sessionsOf(p).some(x => (x.tid === t.id || x.by === t.name) && x.date >= cutoff));
        return `<div class="stcard" style="--c:${t.color}"><div class="sth"><span class="dot" style="background:${t.color}"></span><b>${esc(t.name)}</b><span class="spacer"></span><span class="stn">${mine.length}</span><small>جلسة</small></div>
          ${mine.length ? `<details><summary>تفاصيل الجلسات</summary><div class="stl">${mine.map(x => `<div data-open="${x.p.id}"><span>${esc(x.date)} ${x.time ? t12(x.time) : ''}</span><b>${esc(x.p.name || '')}</b></div>`).join('')}</div></details>` : '<div class="hint">لا توجد جلسات في هذه الفترة</div>'}
          <div class="stcur"><span class="lbl">المرضى الحاليون (${current.length}):</span> ${current.map(p => `<button class="chip" data-open="${p.id}">${esc(p.name || 'بدون اسم')} ${payBadge(p).replace(/●[^<]*/, '●')}</button>`).join('') || '<span class="hint">—</span>'}</div></div>`;
      }).join('');
      const unk = sess.filter(x => !therapists(sec).some(t => t.id === x.tid || t.name === x.by)).length;
      return `<h3 class="fin-sec">${SEC[sec]} — مجموع الجلسات: ${sess.length}</h3><div class="stgrid">${cards}</div>${unk ? `<p class="hint">${unk} جلسة بدون اسم معالج.</p>` : ''}`;
    }).join('');
    $$('#statsBody [data-open]').forEach(el => el.onclick = () => go('p/' + el.dataset.open + '/2'));
  };
  draw(); liveRedraw = draw;
}

/* ---------- settings ---------- */
function settingsView() {
  if (TH()) return `<h2 style="margin:0 0 14px;color:var(--navy)">الإعدادات</h2>
  <div class="sheet"><h3 style="margin-top:0">🔑 تغيير كلمة المرور — ${esc(DB.label())}</h3>
    <div class="pform"><div class="fcol"><span class="lbl">كلمة المرور الحالية</span><input id="op" type="password" dir="ltr"></div>
    <div class="fcol"><span class="lbl">كلمة المرور الجديدة (4 أحرف أو أرقام على الأقل)</span><input id="np" type="password" dir="ltr"></div></div>
    <button class="btn" id="saveAuth" style="margin-top:12px">حفظ</button></div>
  <div class="sheet"><button class="btn ghost" id="out">🚪 تسجيل الخروج</button></div>`;
  return `<h2 style="margin:0 0 14px;color:var(--navy)">الإعدادات</h2>
  <div class="sheet"><h3 style="margin-top:0">🔑 تغيير كلمة المرور — ${esc(DB.label())}</h3>
    <div class="pform"><div class="fcol"><span class="lbl">كلمة المرور الحالية</span><input id="op" type="password" dir="ltr"></div>
    <div class="fcol"><span class="lbl">كلمة المرور الجديدة (6 أحرف على الأقل)</span><input id="np" type="password" dir="ltr"></div></div>
    <button class="btn" id="saveAuth" style="margin-top:12px">حفظ</button></div>
  ${DB.sections().map(sec => `<div class="sheet"><h3 style="margin-top:0">${sec === 'women' ? '👩 المعالجات — قسم النساء' : '👨 المعالجون — قسم الرجال'}</h3>
    <p style="color:var(--muted);margin-top:0">كل اسم له لون يظهر به في جدول المواعيد. اضغط على اللون لتغييره.</p>
    <div class="thlist" id="thl-${sec}"></div>
    <div class="row" style="margin-top:10px"><input class="search" style="flex:1;min-width:180px;padding:10px 14px" id="thn-${sec}" placeholder="${sec === 'women' ? 'اسم معالجة جديدة' : 'اسم معالج جديد'}"><button class="btn" data-addth="${sec}">➕ إضافة</button></div></div>`).join('')}
  <div class="sheet"><h3 style="margin-top:0">🔄 المزامنة</h3>
    ${DB.mode === 'server' ? `<p style="margin-top:0" class="sync on">● النظام يعمل من خادم المركز الداخلي (لابتوب المركز) عبر الواي فاي — لا يحتاج إنترنت.</p>
      <div id="srvInfo" class="help" style="margin:0">جارٍ قراءة عناوين الخادم...</div>
      ${DB.role === 'admin' ? '<a class="btn light" style="margin-top:10px" id="srvBk" href="#">⬇️ تنزيل نسخة كاملة من بيانات الخادم</a>' : ''}` :
    DB.mode === 'cloud' ? `<p style="margin:0" class="sync on">● المزامنة اللحظية مفعّلة — أي تعديل يظهر فوراً على كل الأجهزة المسجّلة بنفس القسم.</p>`
      : `<p style="margin-top:0" class="sync off">● الحفظ الآن على هذا الجهاز فقط.</p><a class="btn light" href="#setup">إعداد المزامنة بين الأجهزة</a>`}</div>
  <div class="sheet"><h3 style="margin-top:0">💾 نسخة احتياطية</h3>
    <p style="color:var(--muted);margin-top:0">تنزيل نسخة من ملفات ومواعيد ${esc(DB.label())} لحفظها عندك.</p>
    <div class="row"><button class="btn" id="exp">⬇️ تنزيل نسخة احتياطية</button>
    <label class="btn light" style="cursor:pointer">⬆️ استرجاع نسخة<input type="file" id="imp" accept=".json,application/json" hidden></label></div></div>
  <div class="sheet"><button class="btn ghost" id="out">🚪 تسجيل الخروج</button></div>`;
}
let accCache = null;
const permLevel = p => !p ? '' : PERM_LIST.every(([k]) => p[k]) ? 'full' : PERM_LIST.every(([k]) => !!p[k] === !!DEF_PERMS[k]) ? 'basic' : 'extra';
const permLabel = p => ({ full: 'كاملة', extra: 'مخصصة', basic: 'أساسية' })[permLevel(p)] || 'أساسية';
function permsModal(u) {
  if (!u) return;
  const p = Object.assign({}, u.perms || {});
  const draw = () => {
    openModal(`<div class="modal-h"><h3>🔐 صلاحيات ${esc(u.name)} <small class="hint" dir="ltr">${esc(u.user)}</small></h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
      <div class="row" style="margin-bottom:10px"><button class="btn" id="pFull">✓ صلاحية كاملة لكل الأقسام</button><button class="btn light" id="pBasic">↺ الصلاحيات الأساسية للمعالج</button></div>
      <div class="lbl-s">الأقسام التي تظهر له:</div>
      <div class="permgrid">${PERM_LIST.slice(0, 6).map(([k, t]) => `<label class="chk perm"><input type="checkbox" data-pk="${k}" ${p[k] ? 'checked' : ''}>${t}</label>`).join('')}</div>
      <div class="lbl-s" style="margin-top:10px">ملفات المرضى:</div>
      <div class="permgrid">${PERM_LIST.slice(11, 14).concat(PERM_LIST.slice(15)).map(([k, t]) => `<label class="chk perm"><input type="checkbox" data-pk="${k}" ${p[k] ? 'checked' : ''}>${t}</label>`).join('')}</div>
      <p class="hint" style="margin:4px 0 0">لمنع المعالج من تعديل أي ملف: أزل «تعديل ملفات كل المرضى» و«تعديل ملفات مرضاه فقط». يبقى قادراً على مشاهدة الملفات.</p>
      <div class="lbl-s" style="margin-top:10px">صلاحيات إضافية:</div>
      <div class="permgrid">${PERM_LIST.slice(6, 11).concat(PERM_LIST.slice(14, 15)).map(([k, t]) => `<label class="chk perm"><input type="checkbox" data-pk="${k}" ${p[k] ? 'checked' : ''}>${t}</label>`).join('')}</div>
      <p class="hint">بدون «إدارة مواعيد كل المعالجين»: يحجز ويعدّل مواعيده فقط ولا يحذف إلا ما أضافه بنفسه. تُطبَّق الصلاحيات فوراً على الخادم، وتظهر عنده عند تحديث الصفحة.</p>
      <div class="modal-f"><button class="btn big" id="ok">حفظ الصلاحيات</button><button class="btn ghost" id="cn">إلغاء</button></div>`);
    $$('[data-pk]').forEach(c => c.onchange = () => { p[c.dataset.pk] = c.checked; });
    $('#pFull').onclick = () => { PERM_LIST.forEach(([k]) => p[k] = true); draw(); };
    $('#pBasic').onclick = () => { Object.assign(p, DEF_PERMS); draw(); };
    $('#mc').onclick = $('#cn').onclick = closeModal;
    $('#ok').onclick = async () => { const r = await DB.userAction({ action: 'perms', user: u.user, perms: p }); if (r.ok) { closeModal(); toast('تم حفظ صلاحيات ' + u.name); bindTherapists(); } else toast('تعذّر الحفظ'); };
  };
  draw();
}
function showPw(user, pw) { openModal(`<div class="modal-h"><h3>بيانات الدخول</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
  <div class="help" style="font-size:18px">اسم المستخدم: <b dir="ltr">${esc(user)}</b><br>كلمة المرور: <b dir="ltr">${esc(pw)}</b></div><p class="hint">أعطها لصاحب الحساب، ويستطيع تغييرها من الإعدادات بعد الدخول.</p>`); $('#mc').onclick = closeModal; }
function makeAccount(sec, t) {
  openModal(`<div class="modal-h"><h3>إنشاء حساب دخول — ${esc(t.name)}</h3><span class="spacer"></span><button class="x" id="mc">×</button></div>
    <div class="fcol"><span class="lbl">اسم المستخدم (أحرف إنجليزية صغيرة بدون فراغات)</span><input id="nu2" dir="ltr" placeholder="مثال: lina" class="search" style="padding:10px"></div>
    <div class="modal-f"><button class="btn big" id="ok">إنشاء</button><button class="btn ghost" id="cn">إلغاء</button></div>`);
  $('#mc').onclick = $('#cn').onclick = closeModal; $('#nu2').focus();
  $('#ok').onclick = async () => { const u = $('#nu2').value.trim().toLowerCase(); if (!/^[a-z0-9_.-]{2,24}$/.test(u)) return toast('اكتب اسم مستخدم بأحرف إنجليزية فقط');
    const r = await DB.userAction({ action: 'create', user: u, name: t.name, section: sec, tid: t.id });
    if (r.ok) { showPw(r.user, r.password); bindTherapists(); } else toast(r.error === 'exists' ? 'اسم المستخدم مستخدم مسبقاً' : 'تعذّر إنشاء الحساب'); };
}
function bindTherapists() {
  DB.sections().forEach(sec => {
    const box = $('#thl-' + sec); if (!box) return;
    const list = therapists(sec);
    box.innerHTML = list.length ? list.map(t => `<div class="throw"><label class="thcol" style="background:${t.color}"><input type="color" value="${t.color}" data-thc="${sec}|${t.id}"></label>
      <b>${esc(t.name)}</b><span class="acc" data-acc="${sec}|${t.id}"></span><span class="spacer"></span><button class="x" data-thdel="${sec}|${t.id}" title="حذف">×</button></div>`).join('') : '<div class="empty">لا يوجد أسماء بعد</div>';
  });
  if (DB.mode === 'server') DB.users().then(us => { accCache = us; $$('[data-acc]').forEach(el => { const [sec, id] = el.dataset.acc.split('|'); const t = therapists(sec).find(x => x.id === id); const u = us.find(x => x.section === sec && (x.tid === id || x.name === (t && t.name)));
    el.innerHTML = u ? `<small dir="ltr" class="accu">👤 ${esc(u.user)}</small>${u.initialPw ? `<small class="accp">كلمة المرور: <b dir="ltr">${esc(u.initialPw)}</b></small>` : '<small class="hint">(غيّر كلمة مروره)</small>'}<button class="btn light sm" data-reset="${esc(u.user)}">كلمة مرور جديدة</button>${DB.role === 'admin' ? `<button class="btn sm perm-btn ${permLevel(u.perms)}" data-perm="${esc(u.user)}">🔐 الصلاحيات: ${permLabel(u.perms)}</button>` : ''}`
      : `<button class="btn sm" data-mkacc="${sec}|${id}">➕ إنشاء حساب دخول</button>`; });
    $$('[data-perm]').forEach(b => b.onclick = () => permsModal(us.find(x => x.user === b.dataset.perm)));
    $$('[data-reset]').forEach(b => b.onclick = async () => { const r = await DB.userAction({ action: 'reset', user: b.dataset.reset }); if (r.ok) { showPw(r.user, r.password); bindTherapists(); } else toast('تعذّر'); });
    $$('[data-mkacc]').forEach(b => b.onclick = () => { const [sec, id] = b.dataset.mkacc.split('|'); const t = therapists(sec).find(x => x.id === id); makeAccount(sec, t); }); });
  $$('[data-thc]').forEach(i => i.onchange = () => { const [sec, id] = i.dataset.thc.split('|'); const t = therapists(sec).find(x => x.id === id); if (t) { t.color = i.value; DB.saveMeta(sec); bindTherapists(); } });
  $$('[data-thdel]').forEach(b => b.onclick = () => { const [sec, id] = b.dataset.thdel.split('|'); const t = therapists(sec).find(x => x.id === id); if (!t) return;
    openModal(`<div class="modal-h"><h3>حذف «${esc(t.name)}» من القائمة؟</h3></div><p>المواعيد السابقة تبقى محفوظة باسمه، لكنه لن يظهر للاختيار في المواعيد الجديدة.</p>
      <div class="row"><button class="btn danger" id="yes">نعم، احذف</button><button class="btn ghost" id="no">إلغاء</button></div>`);
    $('#yes').onclick = async () => { DB.meta[sec].therapists = therapists(sec).filter(x => x.id !== id); DB.saveMeta(sec);
      const u = (accCache || []).find(x => x.section === sec && (x.tid === id || x.name === t.name)); if (u) await DB.userAction({ action: 'delete', user: u.user });
      closeModal(); bindTherapists(); toast('تم الحذف' + (u ? ' مع حساب الدخول' : '')); }; $('#no').onclick = closeModal; });
}
function bindSettings() {
  if (TH()) { $('#saveAuth').onclick = async () => { const o = $('#op').value, n = $('#np').value; if (n.length < 4) return toast('كلمة المرور الجديدة 4 خانات على الأقل');
      try { await DB.changePassword(o, n); $('#op').value = $('#np').value = ''; toast('تم تغيير كلمة المرور'); } catch (e) { toast('كلمة المرور الحالية غير صحيحة'); } };
    $('#out').onclick = async () => { await DB.logout(); location.hash = ''; render(); }; return; }
  bindTherapists(); liveRedraw = bindTherapists;
  if ($('#srvInfo')) fetch('/api/info').then(r => r.json()).then(i => { $('#srvInfo').innerHTML = '📶 لفتح النظام على أي جهاز متصل بواي فاي المركز اكتب في المتصفح:<br>' +
    i.addresses.map(ip => `<b dir="ltr" style="font-size:18px">https://${ip}:${i.httpsPort}</b>`).join('<br>') + '<br><small>أول مرة على كل جهاز: «متقدم» ثم «متابعة». التسجيل الصوتي بدون إنترنت: ' + (i.stt ? '✅ مفعّل' : '❌ غير مثبت (شغّل UPDATE-MOTION-LIFE.bat على اللابتوب)') + '</small>'; }).catch(() => { $('#srvInfo').textContent = 'الخادم غير متاح الآن.'; });
  if ($('#srvBk')) $('#srvBk').onclick = async e => { e.preventDefault(); const r = await fetch('/api/backup', { headers: { Authorization: 'Bearer ' + store.get('ml_srv_token', '') } }); const b = await r.blob();
    const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'motion-life-server-backup-' + today() + '.json'; document.body.appendChild(a); a.click(); a.remove(); };
  $$('[data-addth]').forEach(b => b.onclick = () => { const sec = b.dataset.addth, inp = $('#thn-' + sec), name = inp.value.trim(); if (!name) return toast('اكتب الاسم أولاً');
    const list = therapists(sec); if (list.some(t => t.name === name)) return toast('الاسم موجود مسبقاً');
    const used = list.map(t => t.color); const color = DB.PALETTE.find(c => !used.includes(c)) || DB.PALETTE[list.length % DB.PALETTE.length];
    DB.meta[sec] = DB.meta[sec] || { therapists: [] }; DB.meta[sec].therapists = list.concat([{ id: sec[0] + Date.now().toString(36), name, color }]);
    DB.saveMeta(sec); inp.value = ''; bindTherapists(); toast('تمت الإضافة');
    if (DB.mode === 'server') setTimeout(() => makeAccount(sec, therapists(sec).find(t => t.name === name)), 300); });
  $('#saveAuth').onclick = async () => { const o = $('#op').value, n = $('#np').value; if (n.length < 6) return toast('كلمة المرور الجديدة 6 أحرف على الأقل');
    try { await DB.changePassword(o, n); $('#op').value = $('#np').value = ''; toast('تم تغيير كلمة المرور'); } catch (e) { toast('كلمة المرور الحالية غير صحيحة'); } };
  $('#exp').onclick = () => { const blob = new Blob([JSON.stringify({ app: 'motion-life', v: 2, at: new Date().toISOString(), role: DB.role, patients: allP(), appts: [...DB.appts.values()] }, null, 1)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'motion-life-' + DB.role + '-' + today() + '.json'; document.body.appendChild(a); a.click(); a.remove(); toast('تم تنزيل النسخة الاحتياطية'); };
  $('#imp').onchange = e => { const f = e.target.files[0]; if (!f) return; const r = new FileReader();
    r.onload = () => { try { const d = JSON.parse(r.result); if (!Array.isArray(d.patients)) throw 0; let n = 0; const secs = DB.sections();
      d.patients.forEach(x => { if (!x || !x.id) return; if (!x.section) x.section = x.gender === 'ذكر' ? 'men' : 'women'; if (secs.includes(x.section)) { DB.savePatient(x); n++; } });
      (d.appts || []).forEach(x => { if (x && x.id && secs.includes(x.section)) DB.saveAppt(x); });
      toast('تم استرجاع ' + n + ' ملف'); } catch (err) { toast('الملف غير صالح'); } }; r.readAsText(f); };
  $('#out').onclick = async () => { await DB.logout(); location.hash = ''; render(); };
}

/* ---------- setup (إعداد المزامنة — مرة واحدة) ---------- */
const RULES = `rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    function role() { return request.auth.token.email.split('@')[0]; }
    function staff() { return request.auth != null
      && request.auth.token.email.matches('.*@motionlife[.]clinic$'); }
    match /sections/{sec}/{coll}/{id} {
      allow read, write: if staff() && (sec == 'women' || sec == 'men')
        && (role() == 'admin' || role() == sec);
    }
  }
}`;
function setupView() {
  const has = DB.mode === 'cloud';
  return `<main class="wrap" style="max-width:820px"><div class="row"><h2 style="color:var(--navy)">إعداد المزامنة بين الأجهزة</h2><span class="spacer"></span><a class="btn ghost sm" href="#home">رجوع</a></div>
  <div class="sheet">${has ? '<p class="sync on" style="margin:0">● Firebase متصل. الخطوة المتبقية: إنشاء الحسابات (في الأسفل) إن لم تُنشأ بعد.</p>'
    : '<p class="sync off" style="margin:0">● المزامنة غير مفعّلة بعد. اتبع الخطوات أدناه مرة واحدة فقط.</p>'}</div>
  <div class="sheet setup">
    <h3>١- أنشئ مشروع Firebase (مجاني)</h3>
    <p>افتح <a href="https://console.firebase.google.com" target="_blank" rel="noopener">console.firebase.google.com</a> بحساب Google ← <b>Create a project</b> ← اسم المشروع: <b>motion-life</b> ← أكمل (يمكن إيقاف Google Analytics).</p>
    <h3>٢- فعّل تسجيل الدخول</h3>
    <p>من القائمة: <b>Build ← Authentication ← Get started</b> ← اختر <b>Email/Password</b> ← فعّل الخيار الأول ← <b>Save</b>.</p>
    <h3>٣- أنشئ قاعدة البيانات</h3>
    <p><b>Build ← Firestore Database ← Create database</b> ← اختر الموقع <b>eur3 (Europe)</b> ← <b>Start in production mode</b>.<br>
    ثم افتح تبويب <b>Rules</b> وامسح الموجود والصق هذا النص كما هو، ثم <b>Publish</b>:</p>
    <pre class="code" id="rules">${esc(RULES)}</pre><button class="btn light sm" id="cpR">📋 نسخ النص</button>
    <h3>٤- اربط الموقع</h3>
    <p>اضغط ⚙️ <b>Project settings</b> ← في الأسفل اضغط أيقونة الويب <b>&lt;/&gt;</b> ← اكتب أي اسم ← <b>Register app</b> ← انسخ الجزء <code>firebaseConfig</code> وأرسله لي في المحادثة لأثبّته بالموقع لكل الأجهزة. <br>(أو الصقه هنا لتجربته فوراً على هذا الجهاز فقط)</p>
    <textarea id="cfg" class="lined" rows="5" dir="ltr" placeholder='const firebaseConfig = { apiKey: "...", authDomain: "...", projectId: "...", ... };'></textarea>
    <button class="btn" id="saveCfg" style="margin-top:8px">حفظ وتجربة على هذا الجهاز</button>
    <h3>٥- أنشئ الحسابات الثلاثة</h3>
    ${has ? `<div class="pform">
      <div class="fcol"><span class="lbl">كلمة مرور الإدارة (admin)</span><input id="pw_admin" dir="ltr"></div>
      <div class="fcol"><span class="lbl">كلمة مرور قسم النساء (women)</span><input id="pw_women" dir="ltr"></div>
      <div class="fcol"><span class="lbl">كلمة مرور قسم الرجال (men)</span><input id="pw_men" dir="ltr"></div></div>
      <p style="color:var(--muted)">6 أحرف على الأقل لكل كلمة. احفظها في مكان آمن.</p>
      <button class="btn" id="mkAcc">إنشاء الحسابات</button><div id="accRes" style="margin-top:10px"></div>` : '<p style="color:var(--muted)">تظهر هذه الخطوة بعد ربط Firebase.</p>'}
    <h3>٦- (للأمان) أغلق التسجيل الجديد</h3>
    <p>في Firebase: <b>Authentication ← Settings ← User actions</b> ← أزل علامة <b>Enable create (sign-up)</b> ← Save. هكذا لا يستطيع أحد إنشاء حساب جديد.</p>
  </div></main>`;
}
function bindSetup() {
  $('#cpR').onclick = () => { try { navigator.clipboard.writeText(RULES); toast('تم النسخ'); } catch (e) { toast('انسخه يدوياً'); } };
  $('#saveCfg').onclick = () => { const txt = $('#cfg').value; const o = {}; let m; const re = /(\w+)\s*:\s*["']([^"']+)["']/g;
    while ((m = re.exec(txt))) o[m[1]] = m[2];
    if (!o.apiKey || !o.projectId) return toast('النص غير مكتمل — انسخ firebaseConfig كاملاً');
    try { localStorage.setItem('ml_fb_cfg', JSON.stringify(o)); } catch (e) {} toast('تم الحفظ — جارٍ إعادة التحميل'); setTimeout(() => location.reload(), 800); };
  if ($('#mkAcc')) $('#mkAcc').onclick = async () => { const pw = { admin: $('#pw_admin').value, women: $('#pw_women').value, men: $('#pw_men').value };
    if (Object.values(pw).some(x => x.length < 6)) return toast('كل كلمة مرور 6 أحرف على الأقل');
    $('#mkAcc').disabled = true; const r = await DB.createAccounts(pw); $('#mkAcc').disabled = false;
    $('#accRes').innerHTML = Object.entries(r).map(([k, v]) => `<div>${esc(DB.ROLES[k])} (<b dir="ltr">${k}</b>): ${v === 'ok' ? '✅ تم الإنشاء' : v === 'exists' ? 'ℹ️ موجود مسبقاً' : '❌ ' + esc(v)}</div>`).join(''); };
}

/* ---------- printing ---------- */
const pv = (label, v) => `<div class="f"><label>${label}:</label><div class="pv">${esc(v)}</div></div>`;
const pt = (v, min) => `<div class="pt" style="min-height:${Math.round(min*0.9)}px">${esc(v)}</div>`;
const pfoot = (r, l) => `<div class="pfoot"><span>${r}</span><span>${l}</span></div>`;
function printPatient(p, exOnly) {
  const phone = 'دمشق - الميدان | 011 8838215 - 0945823770';
  let h = '';
  if (!exOnly) {
    const ck = (k, v) => (arrOf(p, k).includes(v) ? '☑ ' : '☐ ') + esc(v);
    const rd = (k, opts) => opts.map(v => (p[k] === v ? '☑ ' : '☐ ') + esc(v)).join(' &nbsp; ');
    h += `<div class="pg sheet iqp">${head('استبيان المريض السريع — التاريخ الطبي', 'قبل الفحص الأولي')}
      <div class="box"><div class="box-t">١ | معلومات أساسية</div><div class="box-b grid2">${pv('الاسم الكامل', p.name)}${pv('العمر', p.age ? p.age + ' سنة' : '')}${pv('رقم الهاتف', p.phone)}${pv('التاريخ', p.iq_date)}</div></div>
      <div class="box"><div class="box-t">٢ | سبب الزيارة</div><div class="box-b"><div class="grid2">${pv('وين المشكلة الأساسية؟', p.iq_where)}${pv('من إمتى؟', p.iq_since)}</div>
        <div><b>كيف بدأت؟</b> ${IQ.onset.map(v => ck('iq_onset', v)).join(' &nbsp; ')}</div><div><b>شو الأعراض؟</b> ${IQ.sym.map(v => ck('iq_sym', v)).join(' &nbsp; ')}</div>
        <div class="grid2">${pv('شدة الألم حالياً', p.pain == null ? '' : p.pain + ' / 10')}${pv('أهم نشاط صار صعب', p.iq_activity)}</div></div></div>
      <div class="box"><div class="box-t">٣ | أسئلة سلامة مهمة</div><div class="box-b"><div class="grid2">${IQ.flags.map(v => `<div>${ck('iq_flags', v)}</div>`).join('')}</div><div>${ck('iq_flags', 'لا يوجد')}</div></div></div>
      <div class="box"><div class="box-t">٤ | التاريخ الطبي</div><div class="box-b"><div>${IQ.hx.map(v => ck('iq_hx', v)).join(' &nbsp; ')} &nbsp; <b>أمراض أخرى:</b> ${esc(p.iq_other || '')}</div>
        <div><b>هشاشة العظام:</b> ${rd('iq_osteo', ['لا', 'نعم', 'لا أعرف'])} &nbsp; | <b>الدرجة:</b> ${rd('iq_osteoGrade', ['خفيفة', 'متوسطة', 'شديدة', 'غير محددة'])} &nbsp; | <b>T-score:</b> ${esc(p.iq_tscore || '')}</div>
        <div class="grid2"><div><b>حساسية:</b> ${rd('iq_allergy', ['لا', 'نعم'])}</div><div><b>أدوية/مميعات/كورتيزون:</b> ${rd('iq_meds', ['لا', 'نعم'])}</div>
        <div><b>منظم قلب/معدن مزروع:</b> ${rd('iq_implant', ['لا', 'نعم'])}</div><div><b>عملية/كسر سابق:</b> ${rd('iq_surgery', ['لا', 'نعم'])}</div>
        <div><b>حمل:</b> ${rd('iq_preg', ['لا', 'نعم', 'غير مؤكدة'])}</div><div><b>تفاصيل:</b> ${esc(p.iq_details || '')}</div></div></div></div>
      <div class="box"><div class="box-t">٥ | تأكيد المعلومات</div><div class="box-b"><div style="font-size:9pt">أؤكد أن إجاباتي صحيحة بحسب معرفتي، وسأخبر الفريق عن أي تغير صحي مهم. أفهم أن هذا الاستبيان لا يحل محل الفحص أو الموافقة العلاجية المستنيرة.</div>
        <div class="grid2">${pv('توقيع المريض/الولي', p.iq_sign)}${pv('رقم الملف', p.fileNo)}</div></div></div>
      <div class="box"><div class="box-t">للاستخدام الداخلي فقط</div><div class="box-b grid2"><div><b>يلزم استقصاء/إحالة؟</b> ${rd('iq_referral', ['نعم', 'لا'])}</div><div><b>تمت المراجعة مع المريض؟</b> ${rd('iq_reviewed', ['نعم', 'لا'])}</div>
        ${pv('اسم/توقيع المعالج', p.iq_therapist)}${pv('ملاحظات', p.iq_notes)}</div></div>
      ${pfoot('Motion Life - استبيان أولي مختصر — معلومات سرية', phone)}</div>`;
    h += `<div class="pg sheet">${head('الحركة تبدأ من هنا', 'ملف المريض والتقييم السريري')}
      <div class="box"><div class="box-b grid4">${pv('رقم الملف', p.fileNo)}${pv('الخزانة / الدرج', p.cabinet)}${pv('الرف', p.shelf)}${pv('رقم التسلسل', p.serial)}</div></div>
      <div class="grid3" style="margin-bottom:10px">${pv('الاسم الكامل', p.name)}${pv('العمر', p.age)}<div class="f"><label>الجنس:</label><div class="pv">${p.gender === 'ذكر' ? '☑' : '☐'} ذكر &nbsp; ${p.gender === 'أنثى' ? '☑' : '☐'} أنثى</div></div>
        ${pv('رقم الهاتف', p.phone)}${pv('المهنة', p.job)}${pv('تاريخ التقييم', p.evalDate)}</div>
      <div class="box"><div class="box-t">ملخص الاستبيان: المشكلة الأساسية وسبب الزيارة والتاريخ الطبي</div><div class="box-b">${iqSummary(p).map(([k, v]) => `<div class="pr-sum"><b>${esc(k)}:</b> ${esc(v)}</div>`).join('') || pt('', 44)}
        <div class="fcol" style="margin-top:6px"><span class="lbl">القصة المرضية</span>${pt(p.history, 88)}</div></div></div>
      <div class="box"><div class="box-t">التقييم السريري</div><div class="box-b">${pt(p.clinical, 132)}</div></div>
      <div class="box"><div class="box-t">الأعراض الحالية ومقياس الألم</div><div class="box-b grid2"><div class="fcol"><span class="lbl">الأعراض الحالية</span>${pt(p.symptoms, 66)}</div>
        <div class="fcol"><div class="f"><label>شدة الألم:</label><span class="pain" style="direction:ltr">${Array.from({ length: 11 }, (_, i) => `<span class="${p.pain === i ? 'on' : ''}">${i}</span>`).join('')}</span></div>
        <div>${['راحة', 'حركة', 'ليل', 'متقطع', 'مستمر'].map(t => (p.painType.includes(t) ? '☑ ' : '☐ ') + t).join(' &nbsp; ')}</div>${pv('مدة الأعراض', p.duration)}${pv('التشنج العضلي', isNum(p.spasm) ? p.spasm + ' / 10' : '')}</div></div></div>
      <div class="box"><div class="box-t">القوة العضلية والقيود الحالية</div><div class="box-b grid2"><div class="fcol"><span class="lbl">القوة العضلية</span><div class="grid2">${pv('طرف علوي', isNum(p.mmtU) ? p.mmtU + ' / 5' : '')}${pv('طرف سفلي', isNum(p.mmtL) ? p.mmtL + ' / 5' : '')}</div>${pt(p.strength, 40)}</div><div class="fcol"><span class="lbl">القيود / الصعوبات الحالية</span>${pt(p.limits, 66)}</div></div></div>
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
      ${hidePrices() ? `<div class="pay"><div class="paybox">${pv('عدد الجلسات المتفق عليها', p.agreedSessions)}</div><div class="paybox">${pv('المبلغ المتبقي', payState(p).status === 'due' ? fmt(payState(p).remain) : '')}</div></div>` : `<div class="pay"><div class="paybox">${pv('عدد الجلسات المتفق عليها', p.agreedSessions)}</div><div class="paybox">${pv('المبلغ الإجمالي المتفق عليه', p.agreedTotal)}</div>
        ${p.payments.map((x, i) => `<div class="paybox soft"><div class="row" style="flex-wrap:nowrap"><b>الدفعة ${i + 1}:</b>${pv('المبلغ', x.amount)}${pv('التاريخ', x.date)}</div></div>`).join('')}
        <div class="paybox">${pv('المبلغ المتبقي', p.agreedTotal ? fmt(num(p.agreedTotal) - paid) : '')}</div><div class="paybox">${pv('إجمالي المبلغ المدفوع', paid ? fmt(paid) : '')}</div></div>`}
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

/* ---------- live updates ---------- */
/* إعادة الرسم بهدوء: تجميع التحديثات المتتالية، وعدم إعادة الرسم أثناء لمس/نقر المستخدم (كان يضيّع النقرات) */
let ptrDown = false, rdT = null, rdFn = null;
document.addEventListener('pointerdown', () => { ptrDown = true; }, true);
['pointerup', 'pointercancel'].forEach(ev => document.addEventListener(ev, () => setTimeout(() => { ptrDown = false; }, 400), true));
function softRedraw(fn) {
  rdFn = fn; clearTimeout(rdT);
  const run = () => { if (ptrDown || (document.activeElement && /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && document.activeElement.closest('#app'))) { rdT = setTimeout(run, 500); return; } const f = rdFn; rdFn = null; f && f(); };
  rdT = setTimeout(run, 300);
}
DB.on((kind, info) => {
  if (kind === 'auth') return render();
  if (kind === 'denied') { toast('🔒 لا تملك صلاحية لهذا التعديل'); DB._pull && DB._pull(); return; }
  if (kind === 'net' || kind === 'pending') { const b = $('#syncB'); if (b) b.innerHTML = syncBadge(); return; }
  if (kind !== 'data' || !DB.role) return;
  if (current === 'p') {
    const id = (location.hash.split('/')[1] || '');
    if (!getP(id)) { if (info.ids && info.ids.includes(id)) render(); else if (!$('[data-k]')) render(); return; }
    if (!$('[data-k]') && !$('#progPage')) return render();
    if (info.remote && info.ids && info.ids.includes(id) && livePatient && livePatient.id === id) livePatient.apply();
    return;
  }
  if (['patients', 'appts', 'settings', 'finance', 'stats'].includes(current) && liveRedraw) return softRedraw(() => liveRedraw && liveRedraw());
  if (current === 'home') softRedraw(() => { if (current === 'home' && $('#modal').classList.contains('hidden')) render(); });
});
setInterval(() => { if (current === 'appts' && liveRedraw && $('#modal').classList.contains('hidden')) liveRedraw(); }, 60000);
DB.init().then(render);
})();
