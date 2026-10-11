/* مولّد شهادة HTTPS ذاتية التوقيع بدون مكتبات خارجية (لتفعيل الميكروفون على أجهزة الشبكة) */
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
module.exports = function generate(cn, ips, days) {
  const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 2048 });
  const spki = publicKey.export({ type: 'spki', format: 'der' });
  const sigAlg = seq(oid('1.2.840.113549.1.1.11'), Buffer.from([0x05, 0x00]));
  const name = seq(set(seq(oid('2.5.4.3'), utf8(cn))), set(seq(oid('2.5.4.10'), utf8('Motion Life'))));
  const now = new Date(Date.now() - 86400000), end = new Date(Date.now() + days * 86400000);
  const alt = [tlv(0x82, Buffer.from('localhost')), tlv(0x82, Buffer.from(cn))].concat(['127.0.0.1'].concat(ips).map(ip => tlv(0x87, ipBytes(ip))));
  const exts = tlv(0xa3, seq(
    seq(oid('2.5.29.17'), tlv(0x04, seq(...alt))),
    seq(oid('2.5.29.19'), tlv(0x04, seq()))));
  const tbs = seq(tlv(0xa0, int(Buffer.from([2]))), int(crypto.randomBytes(12)), sigAlg, name, seq(time(now), time(end)), name, spki, exts);
  const sig = crypto.sign('sha256', tbs, privateKey);
  const cert = seq(tbs, sigAlg, tlv(0x03, Buffer.concat([Buffer.from([0]), sig])));
  const pem = '-----BEGIN CERTIFICATE-----\n' + cert.toString('base64').match(/.{1,64}/g).join('\n') + '\n-----END CERTIFICATE-----\n';
  return { cert: pem, key: privateKey.export({ type: 'pkcs8', format: 'pem' }) };
};
