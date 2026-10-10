"""Real-browser check of autosave, branching, offline failure + retry, and local recovery (dev DB)."""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = "docs/screenshots"


def bar(page):
    return page.locator("#savebar .txt").inner_text()


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 860}, locale="ar-SY", bypass_csp=True)  # test tooling only
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(BASE + "/login")
    page.fill("#username", "therapist.w")
    page.fill("#password", "Motion-Demo-2026")
    page.click("button[type=submit]")
    page.wait_for_url("**/dashboard")
    page.goto(BASE + "/patients")
    page.click("text=ريم تجريبية الثالثة")
    page.fill("#ep-t", "ألم أسفل الظهر مع امتداد للساق")
    page.click("text=فتح حلقة وبدء التقييم")
    page.wait_for_url("**/assessment")
    print("1 opened assessment:", page.url.split("/")[-2][:8])

    # safety answer -> autosave
    page.locator('.q[data-code="SF_CHEST_PAIN"] .opt:has-text("لا")').click()
    page.wait_for_function("document.querySelector('#savebar').dataset.state === 'saved'", timeout=10000)
    print("2 autosave:", bar(page))

    # branching: neuro branch hidden until distribution beyond back
    hidden_before = page.locator('.q[data-code="LB_NEURO_DISTRIBUTION"]').is_hidden()
    page.locator('.q[data-code="LB_DISTRIBUTION"] .opt:has-text("أسفل الركبة")').click()
    visible_after = page.locator('.q[data-code="LB_NEURO_DISTRIBUTION"]').is_visible()
    print("3 branching neuro hidden->visible:", hidden_before, visible_after)
    page.wait_for_function("document.querySelector('#savebar').dataset.state === 'saved'", timeout=10000)

    # unknown status on a safety question keeps it missing
    page.locator('.q[data-code="SF_SADDLE_NUMBNESS"] .opt.status:has-text("غير معروف")').click()
    page.wait_for_function("document.querySelector('#savebar').dataset.state === 'saved'", timeout=10000)
    print("4 safety banner:", page.locator("#safety-live h3").inner_text())

    # offline -> failed save (no false 'saved')
    ctx.set_offline(True)
    page.locator('.q[data-code="SF_FEVER"] .opt:has-text("لا")').click()
    page.wait_for_function("document.querySelector('#savebar').dataset.state === 'failed'", timeout=10000)
    print("5 offline:", bar(page))
    page.screenshot(path=f"{OUT}/16-offline-failed-save-mobile.png")
    stored = page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('ml_pending'))")
    print("6 local backup keys:", stored)

    # reload while offline is impossible; simulate a crash: new tab after reconnect shows recovery banner
    ctx.set_offline(False)
    page2 = ctx.new_page()
    page2.goto(page.url)
    rec = page2.locator("#recover").is_visible()
    print("7 recovery banner on reopen:", rec)
    page2.click("[data-restore]")
    page2.wait_for_function("document.querySelector('#savebar').dataset.state === 'saved'", timeout=10000)
    print("8 restored & saved:", bar(page2))
    page2.reload()
    checked = page2.locator('.q[data-code="SF_FEVER"] input[value="NO"]').is_checked()
    print("9 value persisted on server after reload:", checked)
    print("page errors:", errs or "none")
    b.close()
