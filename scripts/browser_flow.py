"""Real-browser check of plan revision -> review/approval -> session form (dev DB, demo patient سامر)."""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def login(ctx, user):
    page = ctx.new_page()
    page.goto(BASE + "/login")
    page.fill("#username", user)
    page.fill("#password", "Motion-Demo-2026")
    page.click("button[type=submit]")
    page.wait_for_url("**/dashboard")
    return page


with sync_playwright() as p:
    b = p.chromium.launch()
    errs = []
    t = login(b.new_context(viewport={"width": 1280, "height": 900}), "therapist.a")
    t.on("pageerror", lambda e: errs.append(str(e)))
    t.goto(BASE + "/patients")
    t.click("text=سامر تجريبي الأول")
    t.click("text=فتح")
    ep = t.url.split("/episodes/")[1].split("/")[0]
    t.goto(f"{BASE}/episodes/{ep}/plan")
    t.click("button:has-text('إنشاء الإصدار 2')")
    t.wait_for_selector("#plan-form")
    t.click("button:has-text('＋ إضافة بند')")
    rows = t.locator("#items .item-row")
    n = rows.count()
    last = rows.nth(n - 1)
    last.locator("select[name$='.category']").select_option("MANUAL")
    last.locator("input[name$='.title']").fill("تحريك مفصلي قطني")
    last.locator("input[name$='.target']").fill("تحسين مدى الانثناء")
    last.locator("input[name$='.dosage']").fill("درجة II–III، 3 مجموعات")
    # devices need re-confirmation of contraindications in a new version
    for i in range(n):
        cb = rows.nth(i).locator("input[name$='.contraindications_reviewed']")
        if rows.nth(i).locator("select[name$='.category']").input_value() == "DEVICE":
            cb.check()
    t.click("#plan-form button[type=submit]")
    t.wait_for_load_state("networkidle")
    print("1 draft saved; blockers shown:", t.locator(".notice.warn li").count())
    t.click("button:has-text('إرسال الإصدار 2 للمراجعة')")
    t.wait_for_load_state("networkidle")
    print("2 status:", t.locator("details.item-row summary").first.inner_text()[:60])

    h = login(b.new_context(viewport={"width": 1280, "height": 900}), "head.men")
    h.on("pageerror", lambda e: errs.append(str(e)))
    h.goto(BASE + "/reviews")
    h.click("a.btn:has-text('مراجعة')")
    h.wait_for_selector("text=القرار")
    print("3 diff shown:", h.locator("text=التغييرات عن الإصدار 1").count() == 1)
    h.click("button[value=APPROVE]")
    h.wait_for_timeout(800)
    print("4 approve without evidence checkbox ->", h.locator(".form-errors").inner_text()[:70])
    h.check("input[name=evidence_reviewed]")
    h.fill("#d-c", "معتمد مع إضافة التحريك")
    h.click("button[value=APPROVE]")
    h.wait_for_url("**/reviews")
    print("5 approved, queue empty:", h.locator("text=لا توجد خطط بانتظار المراجعة").count() == 1)

    t.goto(f"{BASE}/episodes/{ep}/sessions")
    print("6 session form on plan:", t.locator("h2:has-text('تسجيل الجلسة')").inner_text())
    t.fill("#s-d", "2026-10-10")
    t.fill("#s-pb", "4")
    t.fill("#s-pa", "3")
    t.fill("#s-r", "تحمل جيد للتحريك")
    t.click("form[data-api$='/sessions'] button.primary")
    t.wait_for_load_state("networkidle")
    last_row = t.locator("table tbody tr").filter(has_text="2026").last.inner_text()
    print("7 last session row:", " ".join(last_row.split())[:90])
    print("page errors:", errs or "none")
    b.close()
