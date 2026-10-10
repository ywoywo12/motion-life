"""Build a standalone HTML preview of the exercise library + device programs (for sharing as a link).
Usage: python -m scripts.build_library_preview OUT.html
"""
import json
import sys

from app.clinical import device_programs as D, exercises as X, figures as F

TEMPLATE = r'''<title>مكتبة Motion Life العلاجية</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;700&family=Readex+Pro:wght@500;700&display=swap">
<style>
/* Layout: clinic catalogue — sticky filter bar, dense card grid; devices as an expandable program index */
:root{--bg:#f3f7fa;--surface:#ffffff;--ink:#0d2238;--muted:#4f6276;--line:#d3dee8;--navy:#0f2c4c;--sky:#2f8fbd;--accent:#e0761f;--chip:#e7f1f8;--fig:#ffffff;
--display:"Readex Pro","IBM Plex Sans Arabic",Tahoma,sans-serif;--body:"IBM Plex Sans Arabic","Segoe UI",Tahoma,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0b1724;--surface:#11243a;--ink:#e6eef6;--muted:#9fb3c6;--line:#24405c;--navy:#8fc9ee;--sky:#5bb9e6;--accent:#f0954a;--chip:#173352;--fig:#f4f8fb;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0b1724;--surface:#11243a;--ink:#e6eef6;--muted:#9fb3c6;--line:#24405c;--navy:#8fc9ee;--sky:#5bb9e6;--accent:#f0954a;--chip:#173352;--fig:#f4f8fb;color-scheme:dark}
*{box-sizing:border-box}body{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:15px;line-height:1.6;direction:rtl;margin:0}
.wrap{max-width:1180px;margin:0 auto;padding-inline:16px;padding-block:20px 48px}
header h1{font-family:var(--display);font-size:clamp(1.5rem,4vw,2.1rem);margin:0;color:var(--navy);text-wrap:balance}
header .brand{font-family:var(--display);letter-spacing:.12em;font-size:.8rem;color:var(--sky)}
header p{color:var(--muted);margin:.3rem 0 0;max-width:70ch}
.stats{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px;color:var(--muted);font-size:.9rem;font-variant-numeric:tabular-nums}.stats b{color:var(--ink);font-size:1.1rem}
.note{border:1px solid var(--line);background:var(--surface);border-radius:10px;padding:10px 14px;margin:14px 0;font-size:.88rem;color:var(--muted)}
.tabs{display:flex;gap:8px;margin:16px 0 0}
.tabs button{font:inherit;border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:9px 18px;border-radius:999px;cursor:pointer;min-height:42px}
.tabs button[aria-selected="true"]{background:var(--navy);color:var(--bg);border-color:var(--navy)}
.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:3;background:var(--bg);padding-block:12px;display:grid;gap:8px;grid-template-columns:2fr 1fr 1fr}
.bar.one{grid-template-columns:1fr}
.bar input,.bar select{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px;min-height:44px;width:100%}
.count{color:var(--muted);font-size:.85rem;margin:0 0 10px;font-variant-numeric:tabular-nums}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px;display:grid;grid-template-columns:120px 1fr;gap:12px;align-items:start}
.card>div{min-width:0}.fig{background:var(--fig);border-radius:8px;border:1px solid var(--line);line-height:0}.fig svg{max-width:100%;height:auto}
.card h2{font-family:var(--display);font-size:1rem;margin:0;color:var(--navy)}
.en{direction:ltr;text-align:right;color:var(--muted);font-size:.8rem;margin:0}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}.chip{background:var(--chip);border-radius:999px;padding:1px 10px;font-size:.78rem;font-weight:500}
.chip.t{background:transparent;border:1px solid var(--line)}
.card p{margin:3px 0;font-size:.88rem}.dose{font-weight:700}.warn{color:var(--muted);font-size:.8rem}
details.dev{background:var(--surface);border:1px solid var(--line);border-radius:12px;margin-bottom:10px}
details.dev summary{cursor:pointer;padding:12px 14px;display:flex;justify-content:space-between;gap:10px;align-items:center;list-style:none}
details.dev summary::-webkit-details-marker{display:none}
.dev b{font-family:var(--display);color:var(--navy)}.n{background:var(--chip);border-radius:999px;padding:2px 10px;font-variant-numeric:tabular-nums;font-size:.85rem;white-space:nowrap}
.progs{border-top:1px solid var(--line)}.prog{display:flex;justify-content:space-between;gap:12px;padding:7px 14px;border-bottom:1px dashed var(--line);font-size:.9rem}
.prog span:first-child{min-width:0}.prog span:last-child{direction:ltr;color:var(--muted);font-size:.8rem;text-align:left}
.src{padding:8px 14px;color:var(--muted);font-size:.8rem}
:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
@media (max-width:640px){.bar{grid-template-columns:1fr 1fr}.bar input{grid-column:1/-1}.card{grid-template-columns:96px 1fr}.prog{flex-direction:column;gap:0}.prog span:last-child{text-align:right}}
</style>
<div class="wrap">
<header><div class="brand">MOTION LIFE · الحركة تبدأ من هنا</div><h1>المكتبة العلاجية</h1>
<p>معاينة لمكتبة التمارين وبرامج الأجهزة كما تظهر داخل نظام Motion Life. داخل النظام يضيف المعالج أي تمرين أو برنامج جهاز إلى الخطة بنقرة، ثم يعدّل الجرعة قبل إرسالها للاعتماد.</p>
<div class="stats"><span><b>__NEX__</b> تمريناً</span><span><b>__NREG__</b> منطقة</span><span><b>__NDEV__</b> جهازاً</span><span><b>__NPROG__</b> برنامج جهاز</span></div></header>
<div class="tabs" role="tablist"><button id="t-ex" role="tab" aria-selected="true">التمارين</button><button id="t-dev" role="tab" aria-selected="false">الأجهزة والبرامج</button></div>
<section id="p-ex">
<div class="bar"><input id="q" type="search" placeholder="بحث في التمارين (عربي أو إنجليزي)…" aria-label="بحث"><select id="region" aria-label="المنطقة"><option value="">كل المناطق</option></select><select id="type" aria-label="النوع"><option value="">كل الأنواع</option></select></div>
<p class="count" id="cnt"></p><div class="grid" id="grid"></div></section>
<section id="p-dev" hidden>
<div class="bar one"><input id="dq" type="search" placeholder="بحث بالحالة أو اسم البرنامج على الجهاز…" aria-label="بحث في البرامج"></div>
<div class="note">البرنامج هو الإعداد المسبق المخزّن في الجهاز كما يظهر على شاشته (من ملفات المركز). الشدة والزمن والجرعة يضبطها المختص حسب دليل الشركة والحالة، بعد مراجعة الموانع لكل مريض.</div>
<div id="devs"></div></section>
<p class="note">الجرعات المعروضة نقطة بداية شائعة فقط، ويحددها المعالج لكل مريض حسب التقييم. محتوى المكتبة يحتاج اعتماد المختص في المركز قبل الاستخدام الفعلي.</p>
</div>
<script>const D=__DATA__;
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const R=document.getElementById("region"),T=document.getElementById("type"),Q=document.getElementById("q");
R.insertAdjacentHTML("beforeend",D.regions.map(r=>`<option value="${r.code}">${esc(r.ar)}</option>`).join(""));
T.insertAdjacentHTML("beforeend",D.types.map(t=>`<option value="${t.code}">${esc(t.ar)}</option>`).join(""));
function ex(){const q=Q.value.trim().toLowerCase(),r=R.value,t=T.value;
const rows=D.exercises.filter(e=>(!r||e.region===r)&&(!t||e.type===t)&&(!q||e.name_ar.includes(q)||e.name_en.toLowerCase().includes(q)));
document.getElementById("cnt").textContent="يظهر "+rows.length+" تمريناً";
document.getElementById("grid").innerHTML=rows.map(e=>`<article class="card"><div class="fig">${e.svg}</div><div><h2>${esc(e.name_ar)}</h2><p class="en">${esc(e.name_en)}</p>
<div class="chips"><span class="chip">${esc(e.region_ar)}</span><span class="chip t">${esc(e.type_ar)}</span></div><p>${esc(e.steps)}</p><p><span class="dose">جرعة بداية مقترحة:</span> ${esc(e.dosage)}</p><p class="warn">⚠ ${esc(e.caution)}</p></div></article>`).join("")||"<p>لا توجد تمارين مطابقة.</p>";}
function dev(){const q=document.getElementById("dq").value.trim().toLowerCase();
document.getElementById("devs").innerHTML=D.devices.map(d=>{const ps=d.programs.filter(p=>!q||p.ar.includes(q)||p.en.toLowerCase().includes(q));if(q&&!ps.length)return"";
return `<details class="dev" ${q?"open":""}><summary><span><b>${esc(d.name_ar)}</b><br><span class="en">${esc(d.name)} · ${esc(d.category_ar)}</span></span><span class="n">${d.programs.length?(q?ps.length:d.programs.length)+" برنامج":"إعداد يدوي"}</span></summary>
<div class="progs">${ps.map(p=>`<div class="prog"><span>${esc(p.ar)}</span><span>${esc(p.en)}</span></div>`).join("")}<div class="src">${d.source?"المصدر: "+esc(d.source):esc(d.status_note)}</div></div></details>`}).join("");}
[Q,R,T].forEach(el=>el.addEventListener("input",ex));document.getElementById("dq").addEventListener("input",dev);
const P=[["t-ex","p-ex"],["t-dev","p-dev"]];
for(const[b,p]of P)document.getElementById(b).addEventListener("click",()=>{for(const[b2,p2]of P){document.getElementById(b2).setAttribute("aria-selected",String(b2===b));document.getElementById(p2).hidden=p2!==p}});
if(location.hash==="#devices")document.getElementById("t-dev").click();
ex();dev();</script>'''


def build(out):
    exs = []
    for e in X.catalog_rows():
        exs.append({k: e[k] for k in ("code", "region", "region_ar", "type", "type_ar", "name_ar", "name_en", "steps", "dosage", "caution")}
                   | {"svg": F.svg(e["pose"], e["hl"], 120)})
    devs = [{k: d[k] for k in ("code", "name", "name_ar", "category_ar", "programs", "source", "status_note")} for d in D.equipment_rows()]
    data = {"regions": [{"code": c, "ar": a} for c, a in X.REGIONS], "types": [{"code": c, "ar": a} for c, a in X.TYPES],
            "exercises": exs, "devices": devs}
    html = (TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__NEX__", str(len(exs))).replace("__NREG__", str(len(X.REGIONS))).replace("__NDEV__", str(len(devs)))
            .replace("__NPROG__", str(sum(len(d["programs"]) for d in devs))))
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return len(html)


if __name__ == "__main__":
    print(build(sys.argv[1]))
