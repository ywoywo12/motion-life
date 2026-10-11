/* Motion Life — طبقة الحفظ والمزامنة
   - إذا وُجد إعداد Firebase: حفظ سحابي ومزامنة لحظية بين كل الأجهزة + حسابات حقيقية.
   - وإلا: حفظ محلي على هذا المتصفح فقط. */
(function () {
'use strict';
const DOMAIN = 'motionlife.clinic';
const ROLES = { admin: 'الإدارة', women: 'قسم النساء', men: 'قسم الرجال' };
const LOCAL_DEFAULT = { admin: 'Motion2026', women: 'Women2026', men: 'Men2026' };

const ls = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
};
async function hash(s) {
  try { const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('motionlife|' + s));
    return Array.from(new Uint8Array(b)).map(x => x.toString(16).padStart(2, '0')).join(''); } catch (e) { return 'p:' + s; }
}
const PALETTE = ['#d6457f', '#2f7fd0', '#22955f', '#e07b12', '#8a55d0', '#d23c32', '#159c9c', '#b08400', '#5f7d1e', '#b84aa0', '#4457d4', '#8a5a2b', '#e0607a', '#3a9bd8'];
const DEF_T = {
  women: ['نور الهدى', 'جمان', 'علا', 'تقى', 'صفا', 'رهف', 'إسراء', 'هيا', 'فاطمة'],
  men: ['ابو علاء', 'ابو معاذ', 'خالد', 'علي', 'عبدالرحمن', 'عبدو صوان', 'زكريا']
};
const defMeta = sec => ({ therapists: DEF_T[sec].map((n, i) => ({ id: sec[0] + (i + 1), name: n, color: PALETTE[i % PALETTE.length] })) });
const cfg = () => window.ML_FIREBASE || ls.get('ml_fb_cfg', null);

const M = {
  ROLES, PALETTE, mode: 'local', meta: { women: defMeta('women'), men: defMeta('men') }, role: null, user: null,
  patients: new Map(), appts: new Map(),
  dirty: {}, listeners: [], online: navigator.onLine, unsub: [],
  on(fn) { this.listeners.push(fn); },
  emit(kind, info) { this.listeners.forEach(f => { try { f(kind, info || {}); } catch (e) { console.error(e); } }); },
  sections() { return this.role === 'admin' ? ['women', 'men'] : this.role ? [this.role] : []; },
  hasConfig() { return !!cfg(); }
};

/* ---------------- init ---------------- */
M.init = async function () {
  if (window.ML_SERVER && window.ML_SERVER.on) { this.mode = 'server'; return this._initServer(); }
  const c = cfg();
  if (c && window.firebase) {
    try {
      firebase.initializeApp(c);
      this.auth = firebase.auth(); this.fs = firebase.firestore();
      try { await this.fs.enablePersistence({ synchronizeTabs: true }); } catch (e) { /* offline cache optional */ }
      this.mode = 'cloud';
      await new Promise(res => { const u = this.auth.onAuthStateChanged(user => { u(); this._setUser(user); res(); }); });
      this.auth.onAuthStateChanged(user => { const was = this.role; this._setUser(user); if (was !== this.role) this.emit('auth'); });
      return;
    } catch (e) { console.error('firebase init failed', e); this.mode = 'local'; }
  }
  const s = (() => { try { return sessionStorage.getItem('ml_role'); } catch (e) { return null; } })();
  if (s && ROLES[s]) { this.role = s; this._startLocal(); }
  window.addEventListener('storage', e => { if (e.key === 'ml_patients' || e.key === 'ml_appts' || e.key === 'ml_meta') { this._loadLocal(); this.emit('data', { remote: true }); } });
};
M._setUser = function (user) {
  this.user = user;
  const r = user && user.email ? user.email.split('@')[0] : null;
  this.role = r && ROLES[r] ? r : null;
  this.unsub.forEach(u => u()); this.unsub = [];
  this.patients.clear(); this.appts.clear();
  if (this.role) this._startCloud();
};

/* ---------------- auth ---------------- */
M.login = async function (username, password) {
  username = String(username || '').trim().toLowerCase();
  if (this.mode === 'server') return this._srvLogin(username, password);
  if (this.mode === 'cloud') {
    if (!ROLES[username]) throw new Error('bad');
    await this.auth.signInWithEmailAndPassword(username + '@' + DOMAIN, password);
    return;
  }
  const auth = ls.get('ml_auth_v2', {});
  const ok = auth[username] ? (await hash(password)) === auth[username] : LOCAL_DEFAULT[username] === password;
  if (!ok) throw new Error('bad');
  this.role = username; try { sessionStorage.setItem('ml_role', username); } catch (e) {}
  this._startLocal();
};
M.logout = async function () {
  if (this.mode === 'server') return this._srvLogout();
  if (this.mode === 'cloud') await this.auth.signOut();
  else { this.role = null; try { sessionStorage.removeItem('ml_role'); } catch (e) {} }
};
M.changePassword = async function (oldPw, newPw) {
  if (this.mode === 'server') { const r = await this._req('POST', '/api/password', { old: oldPw, pass: newPw }); if (!r.ok) throw new Error('wrong'); return; }
  if (this.mode === 'cloud') {
    const cred = firebase.auth.EmailAuthProvider.credential(this.user.email, oldPw);
    await this.user.reauthenticateWithCredential(cred);
    await this.user.updatePassword(newPw);
    return;
  }
  const auth = ls.get('ml_auth_v2', {});
  const ok = auth[this.role] ? (await hash(oldPw)) === auth[this.role] : LOCAL_DEFAULT[this.role] === oldPw;
  if (!ok) throw new Error('wrong');
  auth[this.role] = await hash(newPw); ls.set('ml_auth_v2', auth);
};
/* إنشاء الحسابات الثلاثة (مرة واحدة من صفحة الإعداد) */
M.createAccounts = async function (pw) {
  const out = {};
  for (const r of Object.keys(ROLES)) {
    try { await this.auth.createUserWithEmailAndPassword(r + '@' + DOMAIN, pw[r]); out[r] = 'ok'; }
    catch (e) { out[r] = e.code === 'auth/email-already-in-use' ? 'exists' : (e.code || e.message); }
  }
  try { await this.auth.signOut(); } catch (e) {}
  return out;
};

/* ---------------- local mode ---------------- */
M._loadLocal = function () {
  this.patients.clear(); this.appts.clear();
  const secs = this.sections();
  ls.get('ml_patients', []).forEach(p => {
    if (!p.section) p.section = p.gender === 'ذكر' ? 'men' : 'women';   // ترحيل الملفات القديمة
    if (secs.includes(p.section)) this.patients.set(p.id, p);
  });
  ls.get('ml_appts', []).forEach(a => { if (secs.includes(a.section)) this.appts.set(a.id, a); });
  const mt = ls.get('ml_meta', {}); ['women', 'men'].forEach(s => { if (mt[s]) this.meta[s] = mt[s]; });
};
M._startLocal = function () { this._loadLocal(); };
const lsUpsert = (key, obj, del) => {
  const all = ls.get(key, []); const i = all.findIndex(x => x.id === obj.id);
  if (del) { if (i >= 0) all.splice(i, 1); } else if (i >= 0) all[i] = obj; else all.push(obj);
  return ls.set(key, all);
};

/* ---------------- cloud mode ---------------- */
const col = (sec, name) => M.fs.collection('sections').doc(sec).collection(name);
M._startCloud = function () {
  for (const sec of this.sections()) {
    this.unsub.push(col(sec, 'meta').doc('config').onSnapshot(d => { if (d.exists) { const m = d.data(); if (m && m.therapists) this.meta[sec] = m; } this.emit('data', { kind: 'meta', ids: [], remote: true }); }, err => console.error(err)));
    [['patients', this.patients], ['appts', this.appts]].forEach(([name, map]) => {
      const u = col(sec, name).onSnapshot({ includeMetadataChanges: false }, snap => {
        const ids = [];
        const remote = !snap.metadata.hasPendingWrites;
        snap.docChanges().forEach(ch => {
          const d = ch.doc.data(); d.id = ch.doc.id; d.section = sec;
          const cur = map.get(d.id);
          if (ch.type === 'removed') map.delete(d.id);
          else if (cur && !remote) { /* our own write: local object is already up to date */ }
          else if (cur) { const dirty = this.dirty[d.id]; Object.keys(d).forEach(k => { if (!dirty || !dirty.has(k)) cur[k] = d[k]; }); }
          else map.set(d.id, d);
          ids.push(d.id);
        });
        this.emit('data', { kind: name, ids, remote });
      }, err => { console.error(err); this.emit('error', { err }); });
      this.unsub.push(u);
    });
  }
};

/* ---------------- writes ---------------- */
const clean = o => JSON.parse(JSON.stringify(o));
M.savePatient = function (p, keys) {
  p.updated = new Date().toISOString();
  this.patients.set(p.id, p);
  if (this.mode === 'local') return Promise.resolve(lsUpsert('ml_patients', p));
  if (this.mode === 'server') return this._put(p.section, 'patients', p.id, p, keys);
  const ref = col(p.section, 'patients').doc(p.id);
  if (keys && keys.length) { const u = { updated: p.updated }; keys.forEach(k => { u[k] = clean(p[k] === undefined ? null : p[k]); }); return ref.set(u, { merge: true }); }
  const d = clean(p); delete d.id; return ref.set(d);
};
M.deletePatient = function (p) {
  this.patients.delete(p.id);
  if (this.mode === 'local') return Promise.resolve(lsUpsert('ml_patients', p, true));
  if (this.mode === 'server') return this._del(p.section, 'patients', p.id);
  return col(p.section, 'patients').doc(p.id).delete();
};
M.saveAppt = function (a) {
  this.appts.set(a.id, a);
  if (this.mode === 'local') return Promise.resolve(lsUpsert('ml_appts', a));
  if (this.mode === 'server') return this._put(a.section, 'appts', a.id, a);
  const d = clean(a); delete d.id; return col(a.section, 'appts').doc(a.id).set(d);
};
M.saveMeta = function (sec) {
  const m = JSON.parse(JSON.stringify(this.meta[sec]));
  if (this.mode === 'local') { const all = ls.get('ml_meta', {}); all[sec] = m; return Promise.resolve(ls.set('ml_meta', all)); }
  if (this.mode === 'server') return this._put(sec, 'meta', 'config', m);
  return col(sec, 'meta').doc('config').set(m);
};
M.deleteAppt = function (a) {
  this.appts.delete(a.id);
  if (this.mode === 'local') return Promise.resolve(lsUpsert('ml_appts', a, true));
  if (this.mode === 'server') return this._del(a.section, 'appts', a.id);
  return col(a.section, 'appts').doc(a.id).delete();
};


/* ---------------- server mode (خادم المركز الداخلي عبر الواي فاي) ---------------- */
const CID = Math.random().toString(36).slice(2, 10);
M._token = () => ls.get('ml_srv_token', null);
M._req = async function (method, url, body) {
  const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + (this._token() || ''), 'X-Client': CID }, body: body ? JSON.stringify(body) : undefined, cache: 'no-store' });
  let j = {}; try { j = await r.json(); } catch (e) {}
  return Object.assign({ ok: r.ok, status: r.status }, j);
};
M._setOnline = function (v) { if (this.online !== v) { this.online = v; this.emit('net'); } };
M._initServer = async function () {
  this.online = false;
  const t = this._token(), role = ls.get('ml_srv_role', null);
  if (!t || !ROLES[role]) return;
  this.role = role;
  try { const r = await this._req('GET', '/api/me'); if (r.status === 401) { this._clearSrv(); return; } } catch (e) { /* الخادم غير متاح الآن: نعمل من النسخة المحفوظة */ }
  await this._startServer();
};
M._clearSrv = function () { this.role = null; ls.set('ml_srv_token', null); ls.set('ml_srv_role', null); };
M._srvLogin = async function (u, pw) {
  let r; try { r = await this._req('POST', '/api/login', { user: u, pass: pw }); } catch (e) { const er = new Error('net'); er.code = 'auth/network-request-failed'; throw er; }
  if (!r.ok) throw new Error('bad');
  ls.set('ml_srv_token', r.token); ls.set('ml_srv_role', r.role); this.role = r.role;
  await this._startServer();
};
M._srvLogout = async function () { try { await this._req('POST', '/api/logout'); } catch (e) {} this._clearSrv(); this.patients.clear(); this.appts.clear(); };
M._applyAll = function (data) {
  this.patients.clear(); this.appts.clear();
  Object.keys(data || {}).forEach(sec => {
    const d = data[sec] || {};
    Object.entries(d.patients || {}).forEach(([id, p]) => { p.id = id; p.section = sec; this.patients.set(id, p); });
    Object.entries(d.appts || {}).forEach(([id, a]) => { a.id = id; a.section = sec; this.appts.set(id, a); });
    if (d.meta && d.meta.config && d.meta.config.therapists) this.meta[sec] = d.meta.config;
  });
};
M._cacheKey = () => 'ml_srv_cache_' + M.role;
M._saveCache = function () {
  clearTimeout(this._cT);
  this._cT = setTimeout(() => { const out = {}; this.sections().forEach(s => out[s] = { patients: {}, appts: {}, meta: { config: this.meta[s] } });
    this.patients.forEach(p => { if (out[p.section]) out[p.section].patients[p.id] = p; }); this.appts.forEach(a => { if (out[a.section]) out[a.section].appts[a.id] = a; });
    ls.set(this._cacheKey(), out); }, 800);
};
M._startServer = async function () {
  const cached = ls.get(this._cacheKey(), null);
  if (cached) this._applyAll(cached);
  await this._pull();
  this._connectEvents();
  if (!this._flushTimer) this._flushTimer = setInterval(() => this._flush(), 3000);
};
M._pull = async function () {
  try { await this._flush(); const r = await this._req('GET', '/api/data');
    if (r.ok) { this._applyAll(r.data); this._seq = r.seq || 0; this._applyOutbox(); this._saveCache(); this._setOnline(true); this.emit('data', { remote: true, ids: [...this.patients.keys()] }); }
    else if (r.status === 401) { this._clearSrv(); this.emit('auth'); }
  } catch (e) { this._setOnline(false); }
};
/* استقبال التحديثات اللحظية: استعلام طويل عبر fetch (يعمل على كل المتصفحات والتابات حتى مع شهادة المركز الخاصة) */
M._applyMsg = function (m) {
  const remote = m.origin !== CID;
  if (m.coll === 'meta') { if (m.op === 'put' && m.doc && m.doc.therapists) this.meta[m.sec] = m.doc; this.emit('data', { kind: 'meta', ids: [], remote }); return; }
  const map = m.coll === 'patients' ? this.patients : this.appts;
  if (m.op === 'del') map.delete(m.id);
  else if (remote) {
    const d = JSON.parse(JSON.stringify(m.doc)); d.id = m.id; d.section = m.sec; const cur = map.get(m.id);
    if (cur) { const dirty = this.dirty[m.id]; Object.keys(d).forEach(k => { if (!dirty || !dirty.has(k)) cur[k] = d[k]; }); } else map.set(m.id, d);
  }
  if (remote) this.emit('data', { kind: m.coll, ids: [m.id], remote: true });
};
M._connectEvents = function () {
  if (this._polling) return; this._polling = true;
  const loop = async () => {
    while (this.role && this.mode === 'server') {
      try {
        const ctl = new AbortController(); const to = setTimeout(() => ctl.abort(), 35000);
        const r = await fetch('/api/changes?since=' + (this._seq || 0), { headers: { Authorization: 'Bearer ' + (this._token() || ''), 'X-Client': CID }, cache: 'no-store', signal: ctl.signal });
        clearTimeout(to);
        if (r.status === 401) { this._clearSrv(); this.emit('auth'); break; }
        if (!r.ok) throw new Error('changes ' + r.status);
        const j = await r.json();
        this._setOnline(true);
        if (j.reset) { await this._pull(); continue; }
        (j.changes || []).forEach(m => this._applyMsg(m));
        if (j.changes && j.changes.length) this._saveCache();
        this._seq = j.seq;
        this._flush();
      } catch (e) {
        await new Promise(r => setTimeout(r, 3000));
        await this._pull();          // يحدد حالة الاتصال بنفسه
      }
    }
    this._polling = false;
  };
  loop();
};
/* طابور الإرسال: لا يضيع أي تعديل إذا انقطع الاتصال بالخادم */
M._outbox = () => ls.get('ml_srv_outbox', []);
M._queue = function (item) {
  const ob = this._outbox();
  if (item.op === 'put' && item.keys) { const last = ob[ob.length - 1]; const prev = last && last.op === 'put' && last.sec === item.sec && last.coll === item.coll && last.id === item.id && last.keys ? last : null; if (prev) { prev.doc = item.doc; prev.keys = [...new Set(prev.keys.concat(item.keys))]; ls.set('ml_srv_outbox', ob); return; } }
  ob.push(item); ls.set('ml_srv_outbox', ob);
};
M._applyOutbox = function () {   // تعديلات لم تصل الخادم بعد تبقى ظاهرة محلياً
  this._outbox().forEach(it => { const map = it.coll === 'patients' ? this.patients : it.coll === 'appts' ? this.appts : null; if (!map) return;
    if (it.op === 'del') map.delete(it.id); else { const cur = map.get(it.id); if (cur && it.keys) it.keys.forEach(k => cur[k] = it.doc[k]); else { const d = clean(it.doc); d.id = it.id; d.section = it.sec; map.set(it.id, d); } } });
};
M._flush = async function () {
  if (this._flushing) return; this._flushing = true;
  try {
    let ob = this._outbox();
    while (ob.length) {
      const it = ob[0];
      const r = it.op === 'del' ? await this._req('DELETE', `/api/doc/${it.sec}/${it.coll}/${it.id}`) : await this._req('PUT', `/api/doc/${it.sec}/${it.coll}/${it.id}`, { doc: it.doc, keys: it.keys });
      if (r.status === 401) { this._clearSrv(); this.emit('auth'); break; }
      ob = this._outbox(); ob.shift(); ls.set('ml_srv_outbox', ob);
      this._setOnline(true);
    }
  } catch (e) { this._setOnline(false); }
  this._flushing = false;
  this.emit('pending', { n: this._outbox().length });
};
M._put = function (sec, coll, id, obj, keys) {
  const doc = {}; if (keys && keys.length) { keys.concat(['updated']).forEach(k => { doc[k] = clean(obj[k] === undefined ? null : obj[k]); }); } else Object.assign(doc, clean(obj));
  delete doc.id;
  this._queue({ op: 'put', sec, coll, id, doc, keys: keys && keys.length ? keys : null });
  this._saveCache();
  return this._flush();
};
M._del = function (sec, coll, id) { this._queue({ op: 'del', sec, coll, id }); this._saveCache(); return this._flush(); };
M.pending = () => M.mode === 'server' ? M._outbox().length : 0;

window.addEventListener('online', () => { if (M.mode !== 'server') { M.online = true; M.emit('net'); } });
window.addEventListener('offline', () => { if (M.mode !== 'server') { M.online = false; M.emit('net'); } });
window.MLDB = M;
})();
