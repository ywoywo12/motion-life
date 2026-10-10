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
const cfg = () => window.ML_FIREBASE || ls.get('ml_fb_cfg', null);

const M = {
  ROLES, mode: 'local', role: null, user: null,
  patients: new Map(), appts: new Map(),
  dirty: {}, listeners: [], online: navigator.onLine, unsub: [],
  on(fn) { this.listeners.push(fn); },
  emit(kind, info) { this.listeners.forEach(f => { try { f(kind, info || {}); } catch (e) { console.error(e); } }); },
  sections() { return this.role === 'admin' ? ['women', 'men'] : this.role ? [this.role] : []; },
  hasConfig() { return !!cfg(); }
};

/* ---------------- init ---------------- */
M.init = async function () {
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
  window.addEventListener('storage', e => { if (e.key === 'ml_patients' || e.key === 'ml_appts') { this._loadLocal(); this.emit('data', { remote: true }); } });
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
  if (this.mode === 'cloud') await this.auth.signOut();
  else { this.role = null; try { sessionStorage.removeItem('ml_role'); } catch (e) {} }
};
M.changePassword = async function (oldPw, newPw) {
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
  const ref = col(p.section, 'patients').doc(p.id);
  if (keys && keys.length) { const u = { updated: p.updated }; keys.forEach(k => { u[k] = clean(p[k] === undefined ? null : p[k]); }); return ref.set(u, { merge: true }); }
  const d = clean(p); delete d.id; return ref.set(d);
};
M.deletePatient = function (p) {
  this.patients.delete(p.id);
  if (this.mode === 'local') return Promise.resolve(lsUpsert('ml_patients', p, true));
  return col(p.section, 'patients').doc(p.id).delete();
};
M.saveAppt = function (a) {
  this.appts.set(a.id, a);
  if (this.mode === 'local') return Promise.resolve(lsUpsert('ml_appts', a));
  const d = clean(a); delete d.id; return col(a.section, 'appts').doc(a.id).set(d);
};
M.deleteAppt = function (a) {
  this.appts.delete(a.id);
  if (this.mode === 'local') return Promise.resolve(lsUpsert('ml_appts', a, true));
  return col(a.section, 'appts').doc(a.id).delete();
};

window.addEventListener('online', () => { M.online = true; M.emit('net'); });
window.addEventListener('offline', () => { M.online = false; M.emit('net'); });
window.MLDB = M;
})();
