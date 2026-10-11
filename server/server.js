/* Motion Life — خادم المركز الداخلي (يعمل بدون إنترنت عبر شبكة الواي فاي المحلية)
   تشغيل: node server.js   ثم افتح على الأجهزة: http://<عنوان اللابتوب>:8080 */
'use strict';
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

const BASE = process.pkg ? path.dirname(process.execPath) : __dirname;
const SITE = fs.existsSync(path.join(BASE, 'site')) ? path.join(BASE, 'site') : path.join(__dirname, 'site');
const DATA = path.join(BASE, 'data');
const BACKUPS = path.join(DATA, 'backups');
const PORT = +process.env.PORT || 8080;
const HTTPS_PORT = +process.env.HTTPS_PORT || 8443;
const ROLES = ['admin', 'women', 'men'];
const SECS = ['women', 'men'];
const COLLS = ['patients', 'appts', 'meta'];
const DEFAULT_PW = { admin: 'Motion2026', women: 'Women2026', men: 'Men2026' };

fs.mkdirSync(BACKUPS, { recursive: true });
const readJSON = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) { return d; } };
const writeJSON = (f, o) => { const t = f + '.tmp'; fs.writeFileSync(t, JSON.stringify(o)); fs.renameSync(t, f); };

/* ---------- storage ---------- */
const DBF = path.join(DATA, 'db.json'), USERSF = path.join(DATA, 'users.json'), SESSF = path.join(DATA, 'sessions.json');
let db = readJSON(DBF, null);
if (!db) {
  const bk = fs.readdirSync(BACKUPS).filter(f => f.endsWith('.json')).sort().pop();     // استرجاع من آخر نسخة إن تلف الملف
  db = (bk && readJSON(path.join(BACKUPS, bk), null)) || {};
}
SECS.forEach(s => { db[s] = db[s] || {}; COLLS.forEach(c => { db[s][c] = db[s][c] || {}; }); });
let saveT = null;
function persist() {
  clearTimeout(saveT);
  saveT = setTimeout(() => {
    try { writeJSON(DBF, db); } catch (e) { console.error('save failed', e); }
    const day = new Date().toISOString().slice(0, 10), bf = path.join(BACKUPS, 'db-' + day + '.json');
    try { writeJSON(bf, db); const all = fs.readdirSync(BACKUPS).filter(f => f.startsWith('db-')).sort(); all.slice(0, -60).forEach(f => fs.unlinkSync(path.join(BACKUPS, f))); } catch (e) {}
  }, 400);
}
const hashPw = (pw, salt) => crypto.scryptSync(String(pw), salt, 32).toString('hex');
let users = readJSON(USERSF, null);
if (!users) { users = {}; ROLES.forEach(r => { const salt = crypto.randomBytes(8).toString('hex'); users[r] = { salt, hash: hashPw(DEFAULT_PW[r], salt) }; }); writeJSON(USERSF, users); }
let sessions = readJSON(SESSF, {});

/* ---------- realtime (Server-Sent Events) ---------- */
const clients = new Set();
function broadcast(sec, msg) {
  const line = 'data: ' + JSON.stringify(msg) + '\n\n';
  clients.forEach(c => { if (c.role === 'admin' || c.role === sec) { try { c.res.write(line); } catch (e) {} } });
}
setInterval(() => clients.forEach(c => { try { c.res.write(': ping\n\n'); } catch (e) {} }), 20000);

/* ---------- helpers ---------- */
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.json': 'application/json', '.png': 'image/png', '.ico': 'image/x-icon', '.webmanifest': 'application/manifest+json' };
const send = (res, code, obj) => { res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(obj)); };
const auth = req => { const h = req.headers.authorization || ''; const t = h.startsWith('Bearer ') ? h.slice(7) : new URL(req.url, 'http://x').searchParams.get('token'); return t && sessions[t] ? { token: t, role: sessions[t].role } : null; };
const allowed = (role, sec) => role === 'admin' || role === sec;
const body = req => new Promise((ok, bad) => { let b = ''; req.on('data', d => { b += d; if (b.length > 8e6) { bad(new Error('too big')); req.destroy(); } }); req.on('end', () => { try { ok(b ? JSON.parse(b) : {}); } catch (e) { bad(e); } }); });
function lanAddresses() {
  const out = [];
  Object.values(os.networkInterfaces()).forEach(list => (list || []).forEach(a => { if (a.family === 'IPv4' && !a.internal) out.push(a.address); }));
  return out;
}


/* ---------- تحويل الصوت إلى كتابة بدون إنترنت (whisper.cpp على هذا اللابتوب) ---------- */
const { spawn } = require('child_process');
const STT_DIR = path.join(BASE, 'stt');
const STT_PORT = 8178;
const sttFiles = () => { if (!fs.existsSync(STT_DIR)) return null;
  const exe = ['whisper-server.exe', 'whisper-server'].map(f => path.join(STT_DIR, f)).find(f => fs.existsSync(f));
  const model = fs.readdirSync(STT_DIR).filter(f => /^ggml-.*\.bin$/.test(f) && !/silero/.test(f)).sort((a, b) => fs.statSync(path.join(STT_DIR, b)).size - fs.statSync(path.join(STT_DIR, a)).size)[0];
  return exe && model ? { exe, model: path.join(STT_DIR, model) } : null; };
let sttProc = null, sttReady = false, sttTier = 0, sttFails = 0;
const STT_LOG = path.join(DATA, 'stt.log');
function sttLog(t) { try { if (fs.existsSync(STT_LOG) && fs.statSync(STT_LOG).size > 300000) fs.renameSync(STT_LOG, STT_LOG + '.old'); fs.appendFileSync(STT_LOG, new Date().toISOString() + ' ' + t + '\n'); } catch (e) {} }
function startSTT() {
  const f = sttFiles(); if (!f) { console.log('   (التسجيل الصوتي بدون إنترنت غير مثبت بعد — شغّل UPDATE-MOTION-LIFE.bat)'); return; }
  const threads = String(Math.max(2, Math.min(8, os.cpus().length - 1)));
  const vad = fs.readdirSync(STT_DIR).find(x => /^ggml-silero.*\.bin$/.test(x));
  const base = ['-m', f.model, '-l', 'ar', '-t', threads, '--host', '127.0.0.1', '--port', String(STT_PORT)];
  // إعدادات تمنع تكرار الكلمات وتتجاهل السكوت والضجة؛ إذا لم يقبلها الإصدار نرجع لإعدادات أبسط تلقائياً
  const tiers = [
    base.concat(['-mc', '0', '-bs', '5', '-bo', '5', '-sns'], vad ? ['--vad', '-vm', path.join(STT_DIR, vad)] : []),
    base.concat(['-mc', '0', '-bs', '5', '-bo', '5']),
    base];
  const args = tiers[Math.min(sttTier, tiers.length - 1)];
  const started = Date.now();
  sttReady = false;
  sttProc = spawn(f.exe, args, { cwd: STT_DIR, windowsHide: true });
  sttLog('START tier ' + sttTier + ': ' + path.basename(f.exe) + ' ' + args.join(' '));
  const onOut = d => { const t = String(d); sttLog(t.trim()); if (/listening/i.test(t)) sttReady = true; };
  sttProc.stdout.on('data', onOut); sttProc.stderr.on('data', onOut);
  sttProc.on('error', e => sttLog('SPAWN ERROR ' + e.message));
  sttProc.on('exit', (code, sig) => { sttLog('EXIT code=' + code + ' signal=' + sig + ' after ' + Math.round((Date.now() - started) / 1000) + 's');
    sttReady = false; sttProc = null;
    if (Date.now() - started < 15000 && sttTier < tiers.length - 1) { sttTier++; return startSTT(); }   // الخيارات غير مدعومة → إعدادات أبسط
    sttFails++; console.log('   (محرك الصوت توقف، إعادة تشغيل)'); setTimeout(startSTT, Math.min(60000, 5000 * sttFails));
  });
  setTimeout(() => { if (sttProc) sttReady = true; }, 30000);
  console.log('   التسجيل الصوتي بدون إنترنت: مفعّل (' + path.basename(f.model) + (vad && sttTier === 0 ? ' + كشف الكلام' : '') + ', مستوى ' + sttTier + ')');
}
process.on('exit', () => { try { sttProc && sttProc.kill(); } catch (e) {} });
async function transcribe(wav) {
  const fd = new FormData();
  fd.append('file', new Blob([wav], { type: 'audio/wav' }), 'audio.wav');
  fd.append('language', 'ar'); fd.append('response_format', 'json'); fd.append('temperature', '0.0'); fd.append('temperature_inc', '0.2');
  const r = await fetch('http://127.0.0.1:' + STT_PORT + '/inference', { method: 'POST', body: fd });
  if (!r.ok) throw new Error('stt ' + r.status);
  const j = await r.json(); return cleanText(j.text);
}
/* تنظيف النص: حذف التكرار المتتالي والعبارات الوهمية التي يولّدها النموذج عند السكوت */
const JUNK = [/ترجمة\s*نانسي\s*قنقر/g, /اشتركوا?\s*في\s*القناة/g, /شكرا\s*(لكم\s*)?(على|لل)\s*المشاهدة/g, /\(?\s*موسيقى\s*\)?/g, /نشكركم\s*على\s*المتابعة/g, /سبحان\s*الله/g];
function cleanText(t) {
  t = String(t || '').replace(/\[[^\]]*\]|\([^)]*\)/g, ' ');
  JUNK.forEach(re => { t = t.replace(re, ' '); });
  let w = t.split(/\s+/).filter(Boolean);
  for (let n = 1; n <= 8; n++) {            // كلمة أو عبارة (حتى 8 كلمات) مكررة متتالياً ← تبقى مرة واحدة
    const out = [];
    for (let i = 0; i < w.length; i++) {
      out.push(w[i]);
      if (out.length >= 2 * n) { const nz = x => x.map(y => y.replace(/[\u064B-\u0652\u0640.,،؛;:!?؟"'«»…-]/g, '')).join(' ');
        const a = nz(out.slice(-2 * n, -n)), b = nz(out.slice(-n)); if (a && a === b) out.splice(-n, n); }
    }
    w = out;
  }
  return w.join(' ').replace(/\s+([،.؟!,])/g, '$1').trim();
}
const rawBody = req => new Promise((ok, bad) => { const parts = []; let n = 0; req.on('data', d => { n += d.length; if (n > 60e6) { bad(new Error('too big')); req.destroy(); } else parts.push(d); }); req.on('end', () => ok(Buffer.concat(parts))); });

/* ---------- API ---------- */
async function api(req, res, url) {
  const p = url.pathname;
  if (p === '/api/ping') return send(res, 200, { ok: true, time: Date.now() });
  if (p === '/api/info') return send(res, 200, { addresses: lanAddresses(), port: PORT, httpsPort: HTTPS_PORT, stt: !!sttFiles(), sttRunning: !!sttProc && sttReady, sttTier });
  if (p === '/api/login' && req.method === 'POST') {
    const { user, pass } = await body(req); const u = String(user || '').trim().toLowerCase();
    if (!users[u] || hashPw(pass, users[u].salt) !== users[u].hash) return send(res, 401, { error: 'bad' });
    const token = crypto.randomBytes(24).toString('hex'); sessions[token] = { role: u, at: Date.now() }; writeJSON(SESSF, sessions);
    return send(res, 200, { token, role: u });
  }
  const a = auth(req); if (!a) return send(res, 401, { error: 'auth' });
  if (p === '/api/me') return send(res, 200, { role: a.role });
  if (p === '/api/stt' && req.method === 'POST') {
    if (!sttFiles()) return send(res, 503, { error: 'stt_off' });
    if (!sttProc) return send(res, 503, { error: 'stt_down' });
    const wav = await rawBody(req);
    try { return send(res, 200, { text: await transcribe(wav) }); } catch (e) { return send(res, 502, { error: sttReady ? 'stt_fail' : 'stt_loading' }); }
  }
  if (p === '/api/logout' && req.method === 'POST') { delete sessions[a.token]; writeJSON(SESSF, sessions); return send(res, 200, { ok: true }); }
  if (p === '/api/password' && req.method === 'POST') {
    const { old, pass } = await body(req); const u = users[a.role];
    if (hashPw(old, u.salt) !== u.hash) return send(res, 403, { error: 'wrong' });
    if (String(pass || '').length < 6) return send(res, 400, { error: 'short' });
    u.salt = crypto.randomBytes(8).toString('hex'); u.hash = hashPw(pass, u.salt); writeJSON(USERSF, users);
    Object.keys(sessions).forEach(t => { if (sessions[t].role === a.role && t !== a.token) delete sessions[t]; }); writeJSON(SESSF, sessions);
    return send(res, 200, { ok: true });
  }
  if (p === '/api/data') {
    const out = {}; SECS.forEach(s => { if (allowed(a.role, s)) out[s] = db[s]; });
    return send(res, 200, { data: out, time: Date.now() });
  }
  if (p === '/api/events') {
    res.writeHead(200, { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-store', Connection: 'keep-alive', 'X-Accel-Buffering': 'no' });
    res.write('retry: 2000\n\n');
    const c = { res, role: a.role }; clients.add(c); req.on('close', () => clients.delete(c));
    return;
  }
  if (p === '/api/backup' && a.role === 'admin') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Content-Disposition': 'attachment; filename="motion-life-server-backup-' + new Date().toISOString().slice(0, 10) + '.json"' });
    return res.end(JSON.stringify({ app: 'motion-life-server', at: new Date().toISOString(), db }));
  }
  const m = p.match(/^\/api\/doc\/(\w+)\/(\w+)\/([\w-]+)$/);
  if (m) {
    const [, sec, coll, id] = m;
    if (!SECS.includes(sec) || !COLLS.includes(coll)) return send(res, 400, { error: 'path' });
    if (!allowed(a.role, sec)) return send(res, 403, { error: 'forbidden' });
    const store = db[sec][coll];
    if (req.method === 'DELETE') { delete store[id]; persist(); broadcast(sec, { op: 'del', sec, coll, id, origin: req.headers['x-client'] || '' }); return send(res, 200, { ok: true }); }
    if (req.method === 'PUT') {
      const { doc, keys } = await body(req);
      if (!doc || typeof doc !== 'object') return send(res, 400, { error: 'doc' });
      delete doc.id;
      if (Array.isArray(keys) && keys.length && store[id]) { keys.concat(['updated']).forEach(k => { if (k in doc) store[id][k] = doc[k]; }); }
      else store[id] = doc;
      store[id].section = sec; persist();
      broadcast(sec, { op: 'put', sec, coll, id, doc: store[id], origin: req.headers['x-client'] || '' });
      return send(res, 200, { ok: true });
    }
  }
  send(res, 404, { error: 'not found' });
}

/* ---------- static site ---------- */
function serveStatic(req, res, url) {
  let f = decodeURIComponent(url.pathname); if (f === '/' || f === '') f = '/index.html';
  if (f === '/server-config.js') { res.writeHead(200, { 'Content-Type': MIME['.js'], 'Cache-Control': 'no-store' }); return res.end('window.ML_SERVER = { on: true };\n'); }
  const fp = path.normalize(path.join(SITE, f));
  if (!fp.startsWith(SITE)) { res.writeHead(403); return res.end(); }
  fs.readFile(fp, (err, buf) => {
    if (err) { res.writeHead(404); return res.end('not found'); }
    const ext = path.extname(fp).toLowerCase();
    if (ext === '.html') buf = Buffer.from(buf.toString('utf8').replace(/<script src="https:\/\/www\.gstatic\.com[^>]*><\/script>\n?/g, '').replace(/<link[^>]*fonts\.googleapis[^>]*>\n?/g, '').replace(/<link rel="preconnect"[^>]*>\n?/g, ''));
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream', 'Cache-Control': ext === '.svg' ? 'max-age=86400' : 'no-cache' });
    res.end(buf);
  });
}
const isLocal = req => { const a = (req.socket.remoteAddress || '').replace('::ffff:', ''); return a === '127.0.0.1' || a === '::1'; };
const handler = (req, res) => {
  const url = new URL(req.url, 'http://local');
  if (!req.socket.encrypted && httpsOn && !isLocal(req) && !url.pathname.startsWith('/api/') && req.method === 'GET') {   // الأجهزة الأخرى → الرابط الآمن (للميكروفون)
    const host = (req.headers.host || '').split(':')[0];
    res.writeHead(302, { Location: 'https://' + host + ':' + HTTPS_PORT + url.pathname + url.search }); return res.end();
  }
  if (url.pathname.startsWith('/api/')) return api(req, res, url).catch(e => { console.error(e); try { send(res, 500, { error: 'server' }); } catch (x) {} });
  serveStatic(req, res, url);
};

/* ---------- start ---------- */
const httpSrv = http.createServer(handler);
httpSrv.on('error', e => { if (e.code === 'EADDRINUSE') { console.log('\n   ⚠️ الخادم يعمل مسبقاً على هذا اللابتوب (المنفذ ' + PORT + ' مشغول). أغلق النافذة القديمة أولاً.\n'); process.exit(1); } throw e; });
httpSrv.listen(PORT, '0.0.0.0', () => {
  const ips = lanAddresses();
  console.log('\n  ==============================================');
  console.log('   Motion Life — خادم المركز يعمل الآن');
  console.log('  ==============================================');
  console.log('   على هذا اللابتوب:   http://localhost:' + PORT);
  ips.forEach(ip => console.log('   على باقي الأجهزة:   https://' + ip + ':' + HTTPS_PORT + '   (أو http://' + ip + ':' + PORT + ')'));
  console.log('   البيانات محفوظة في:  ' + DATA);
  console.log('   لا تغلق هذه النافذة أثناء العمل.\n');
  startSTT();
});
// HTTPS (needed by browsers for the microphone on other devices)
let httpsOn = false;
try {
  const kf = path.join(DATA, 'key.pem'), cf = path.join(DATA, 'cert.pem'), ipf = path.join(DATA, 'cert-ips.txt');
  const ips = lanAddresses().sort().join(',');
  if (!fs.existsSync(kf) || !fs.existsSync(cf) || (fs.existsSync(ipf) ? fs.readFileSync(ipf, 'utf8') : '') !== ips) {   // تُجدّد إذا تغيّر عنوان اللابتوب
    const pems = require('./selfcert')('motion-life.local', lanAddresses(), 3650);
    fs.writeFileSync(kf, pems.key); fs.writeFileSync(cf, pems.cert); fs.writeFileSync(ipf, ips);
  }
  https.createServer({ key: fs.readFileSync(kf), cert: fs.readFileSync(cf) }, handler).listen(HTTPS_PORT, '0.0.0.0');
  httpsOn = true;
} catch (e) { console.log('   (HTTPS غير مفعّل: ' + e.message + ')'); }
process.on('uncaughtException', e => console.error('error:', e && e.message));
