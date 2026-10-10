"""Visit pages as different roles in headless Chromium; save screenshots and report JS/CSP errors.
Usage: python -m scripts.screenshots [base_url] [out_dir]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
PW = "Motion-Demo-2026"


def login(page, user):
    page.goto(BASE + "/login")
    page.fill("#username", user)
    page.fill("#password", PW)
    page.click("button[type=submit]")
    page.wait_for_url("**/dashboard")


def main():
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for width, tag in ((1366, "desktop"), (390, "mobile")):
            ctx = b.new_context(viewport={"width": width, "height": 900}, locale="ar-SY")
            page = ctx.new_page()
            page.on("console", lambda m: errors.append(f"[{tag}] console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e: errors.append(f"[{tag}] pageerror: {e}"))
            page.goto(BASE + "/login")
            page.screenshot(path=str(OUT / f"01-login-{tag}.png"), full_page=True)
            login(page, "therapist.a")
            page.screenshot(path=str(OUT / f"02-dashboard-therapist-{tag}.png"), full_page=True)
            page.goto(BASE + "/patients")
            page.screenshot(path=str(OUT / f"03-patients-{tag}.png"), full_page=True)
            page.click("text=سامر تجريبي الأول")
            page.wait_for_load_state()
            page.screenshot(path=str(OUT / f"04-patient-{tag}.png"), full_page=True)
            pid = page.url.rsplit("/", 1)[1]
            page.goto(BASE + f"/patients/{pid}/history")
            page.screenshot(path=str(OUT / f"05-history-{tag}.png"), full_page=False)
            page.goto(BASE + f"/patients/{pid}")
            page.click("text=فتح")
            page.wait_for_load_state()
            page.screenshot(path=str(OUT / f"06-assessment-{tag}.png"), full_page=False)
            page.goto(page.url + "#s4")
            page.screenshot(path=str(OUT / f"07-assessment-exam-{tag}.png"), full_page=False)
            ep_url = page.url.split("/assessment")[0]
            page.goto(ep_url + "/plan")
            page.screenshot(path=str(OUT / f"08-plan-{tag}.png"), full_page=True)
            page.goto(ep_url + "/sessions")
            page.screenshot(path=str(OUT / f"09-sessions-{tag}.png"), full_page=True)
            page.goto(ep_url + "/outcomes")
            page.screenshot(path=str(OUT / f"10-outcomes-{tag}.png"), full_page=True)
            ctx.close()
            if tag == "desktop":
                ctx = b.new_context(viewport={"width": width, "height": 900}, locale="ar-SY")
                page = ctx.new_page()
                page.on("console", lambda m: errors.append(f"[head] console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
                login(page, "head.men")
                page.screenshot(path=str(OUT / "11-dashboard-head.png"), full_page=True)
                page.goto(BASE + "/reviews")
                page.click("text=مراجعة")
                page.wait_for_load_state()
                page.screenshot(path=str(OUT / "12-review.png"), full_page=True)
                for path in ("/admin/users", "/reports"):
                    page.goto(BASE + path)
                    page.screenshot(path=str(OUT / f"13{path.replace('/', '-')}.png"), full_page=True)
                ctx.close()
                ctx = b.new_context(viewport={"width": width, "height": 900}, locale="ar-SY")
                page = ctx.new_page()
                login(page, "reception")
                page.goto(BASE + "/patients")
                page.click("text=سامر تجريبي الأول")
                page.wait_for_load_state()
                page.screenshot(path=str(OUT / "14-reception-patient.png"), full_page=True)
                ctx.close()
                ctx = b.new_context(viewport={"width": width, "height": 900}, locale="ar-SY")
                page = ctx.new_page()
                login(page, "director")
                for path in ("/admin/catalogs", "/admin/audit"):
                    page.goto(BASE + path)
                    page.screenshot(path=str(OUT / f"15{path.replace('/', '-')}.png"), full_page=False)
                ctx.close()
        b.close()
    print("\n".join(errors) if errors else "no console errors")


if __name__ == "__main__":
    main()
