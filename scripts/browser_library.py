"""Browser check: plan picker (exercise + device program), library pages, home-program PDF. Dev DB, patient ريم."""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = "docs/screenshots"
with sync_playwright() as p:
    b = p.chromium.launch()
    errs = []
    for w, tag in ((1366, "desktop"), (390, "mobile")):
        ctx = b.new_context(viewport={"width": w, "height": 900}, locale="ar-SY")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto(BASE + "/login"); pg.fill("#username", "therapist.w"); pg.fill("#password", "Motion-Demo-2026")
        pg.click("button[type=submit]"); pg.wait_for_url("**/dashboard")
        pg.goto(BASE + "/library")
        pg.screenshot(path=f"{OUT}/17-library-exercises-{tag}.png", full_page=False)
        pg.goto(BASE + "/library?region=SHOULDER&type=STRENGTH")
        print(tag, "shoulder strength cards:", pg.locator(".ex-card").count())
        pg.goto(BASE + "/library?tab=devices&q=lumbalgia")
        pg.screenshot(path=f"{OUT}/18-library-devices-{tag}.png", full_page=False)
        if tag == "desktop":
            pg.goto(BASE + "/patients"); pg.click("text=ريم تجريبية الثالثة"); pg.click("text=فتح")
            ep = pg.url.split("/episodes/")[1].split("/")[0]
            pg.goto(f"{BASE}/episodes/{ep}/plan")
            pg.wait_for_selector(".pick-row")
            print("picker default region:", pg.locator('[data-f="region"]').input_value(), "rows:", pg.locator('[data-list="ex"] .pick-row').count())
            pg.select_option('[data-f="type"]', "STABILITY")
            pg.locator('[data-list="ex"] .pick-row button').first.click()
            pg.click('[data-tab="dev"]')
            pg.fill('[data-f="dq"]', "Lumbalgia")
            pg.locator('[data-add-prog]').first.click()
            pg.screenshot(path=f"{OUT}/19-plan-picker.png", full_page=True)
            pg.fill("#c-imp", "ألم ظهر ميكانيكي")
            pg.click("#plan-form button[type=submit]")
            pg.wait_for_load_state("networkidle")
            print("saved items:", pg.locator("#items .item-row").count(),
                  "| program badge:", pg.locator("#items [data-prog-label]:not([hidden])").first.inner_text()[:60])
        ctx.close()
    print("errors:", errs or "none")
    b.close()
