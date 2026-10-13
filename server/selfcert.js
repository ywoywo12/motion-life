/* شهادات HTTPS لخادم المركز بدون مكتبات خارجية:
   - «شهادة المركز» (جهة إصدار خاصة بالمركز) تُنشأ مرة واحدة وتُثبَّت على كل جهاز ليثق بالخادم.
   - شهادة الخادم تُوقَّع منها، وتتجدد تلقائياً إذا تغيّرت عناوين اللابتوب دون الحاجة لإعادة التثبيت على الأجهزة. */
'use strict';
const crypto = require('crypto');
const len = n => n < 128 ? Buffer.from([n]) : n < 256 ? Buffer.from([0x81, n]) : Buffer.from([0x82, n >> 8, n & 255]);
const tlv = (tag, ...parts) => { const b = Buffer.concat(parts); return Buffer.concat([Buffer.from([tag]), len(b.length), b]); };
const seq = (...p) => tlv(0x30, ...p);
const set = (...p) => tlv(0x31, ...p);
const int = buf => { if (buf[0] & 0x80) buf = Buffer.concat([Buffer.from([0]), buf]); return tlv(0x02, buf); };
const oid = s => { const a = s.split('.').map(Number); const out = [40 * a[0] + a[1]];
  a.slice(2).forEach(v => { const st = []; do { st.unshift(v & 127); v >>= 7; } while (v); st.forEach((x, i) => out.push(i < st.length - 1 ? x | 128 : x)); });
  return tlv(0x06, Buffer.from(out)); };
const utf8 = s => tlv(0x0c, Buffer.from(s, 'utf8'));
const time = d => { const s = d.toISOString().replace(/[-:T]/g, '').slice(2, 14) + 'Z'; return tlv(0x17, Buffer.from(s)); };
const ipBytes = ip => Buffer.from(ip.split('.').map(Number));
const TRUE = Buffer.from([0x01, 0x01, 0xff]);
const ext = (id, critical, value) => seq(oid(id), ...(critical ? [TRUE] : []), tlv(0x04, value));
const sigAlg = seq(oid('1.2.840.113549.1.1.11'), Buffer.from([0x05, 0x00]));
const nameOf = cn => seq(set(seq(oid('2.5.4.3'), utf8(cn))), set(seq(oid('2.5.4.10'), utf8('Motion Life'))));
const toPem = der => '-----BEGIN CERTIFICATE-----\n' + der.toString('base64').match(/.{1,64}/g).join('\n') + '\n-----END CERTIFICATE-----\n';
const skiOf = spki => crypto.createHash('sha1').update(spki).digest();
function build({ subject, issuer, spki, signKey, days, exts }) {
  const now = new Date(Date.now() - 86400000), end = new Date(Date.now() + days * 86400000);
  const tbs = seq(tlv(0xa0, int(Buffer.from([2]))), int(crypto.randomBytes(12)), sigAlg, issuer, seq(time(now), time(end)), subject, spki, tlv(0xa3, seq(...exts)));
  const sig = crypto.sign('sha256', tbs, signKey);
  return seq(tbs, sigAlg, tlv(0x03, Buffer.concat([Buffer.from([0]), sig])));
}
const CA_CN = 'Motion Life - Center CA';
/* شهادة المركز (تُنشأ مرة واحدة، صالحة 20 سنة) */
function makeCA() {
  const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 2048 });
  const spki = publicKey.export({ type: 'spki', format: 'der' });
  const der = build({ subject: nameOf(CA_CN), issuer: nameOf(CA_CN), spki, signKey: privateKey, days: 7300, exts: [
    ext('2.5.29.19', true, seq(TRUE)),                                   // CA:TRUE
    ext('2.5.29.15', true, Buffer.from([0x03, 0x02, 0x01, 0x06])),       // keyCertSign, cRLSign
    ext('2.5.29.14', false, tlv(0x04, skiOf(spki)))] });
  return { cert: toPem(der), key: privateKey.export({ type: 'pkcs8', format: 'pem' }) };
}
/* شهادة الخادم موقّعة من شهادة المركز (صالحة 397 يوماً وتتجدد تلقائياً) */
function makeServer(ca, cn, ips) {
  const caKey = crypto.createPrivateKey(ca.key), caSpki = crypto.createPublicKey(ca.key).export({ type: 'spki', format: 'der' });
  const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 2048 });
  const spki = publicKey.export({ type: 'spki', format: 'der' });
  const alt = [tlv(0x82, Buffer.from('localhost')), tlv(0x82, Buffer.from(cn))].concat([...new Set(['127.0.0.1'].concat(ips))].map(ip => tlv(0x87, ipBytes(ip))));
  const der = build({ subject: nameOf(cn), issuer: nameOf(CA_CN), spki, signKey: caKey, days: 397, exts: [
    ext('2.5.29.17', false, seq(...alt)),
    ext('2.5.29.19', true, seq()),                                        // CA:FALSE
    ext('2.5.29.15', true, Buffer.from([0x03, 0x02, 0x05, 0xa0])),       // digitalSignature, keyEncipherment
    ext('2.5.29.37', false, seq(oid('1.3.6.1.5.5.7.3.1'))),              // serverAuth
    ext('2.5.29.14', false, tlv(0x04, skiOf(spki))),
    ext('2.5.29.35', false, seq(tlv(0x80, skiOf(caSpki))))] });
  return { cert: toPem(der) + ca.cert, key: privateKey.export({ type: 'pkcs8', format: 'pem' }) };
}
module.exports = { makeCA, makeServer };
