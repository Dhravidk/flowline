#!/usr/bin/env python3
"""Review-library journeys in an isolated Chrome session against a local app.
Usage: python tests/smoke/process_browser_gate.py [http://localhost:8000]
Requires playwright and an installed Chrome. Creates a local test workspace.
"""
from pathlib import Path
import sys

from playwright.sync_api import expect, sync_playwright
import process_gate as api

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
OUT = Path(".jac/process-review")


def layout(page):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Page overflows horizontally"
    collisions = page.locator(".process-map").evaluate_all("""maps => maps.flatMap(map => {
        const nodes = [...map.querySelectorAll('.process-node')];
        return nodes.flatMap((a, i) => nodes.slice(i+1).filter(b => {
            const r = a.getBoundingClientRect(), s = b.getBoundingClientRect();
            return Math.min(r.right,s.right)-Math.max(r.left,s.left)>1 &&
                Math.min(r.bottom,s.bottom)-Math.max(r.top,s.top)>1;
        }).map(b => [a.innerText,b.innerText]));
    })""")
    assert collisions == [], collisions


def run():
    api.BASE = BASE
    token = api.account()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE + "/login")
        # An isolated local test account; authentication itself is covered by api_gate.py.
        page.evaluate("token => localStorage.setItem('jac_token', token)", token)
        page.goto(BASE + "/processes")
        page.get_by_role("button", name="Add the four example flows", exact=True).click()
        expect(page.get_by_role("heading", name="React migration process · Current", exact=True)).to_be_visible()
        expect(page.get_by_text("Storyboards only", exact=True)).to_be_visible()
        print("ok   Chrome: UI installs the four persisted examples", flush=True)

        for family, family_title in (("react", "React migration process"), ("bau", "BAU process")):
            for version in ("current", "proposed"):
                page.goto(f"{BASE}/processes?family={family}&version={version}")
                expect(page.get_by_role("heading", name=family_title + " · " + version.capitalize(), exact=True)).to_be_visible()
                jump = page.get_by_role("combobox", name="Jump to step")
                jump.select_option("qa")
                inspector = page.get_by_role("complementary", name="Step details")
                expect(inspector.get_by_role("heading", name="QA + BAU regression", exact=True)).to_be_visible()
                expect(inspector).to_contain_text("48–96-hour")
                expect(inspector).to_contain_text("Retries never reset")
                layout(page)
                page.screenshot(path=str(OUT / f"{family}-{version}.png"), full_page=True)
        print("ok   all four direct links, QA details and node layouts", flush=True)

        page.get_by_role("button", name="Compare versions", exact=True).click()
        expect(page.locator(".process-diagram-panel")).to_have_count(2)
        page.get_by_role("button", name="Show step list", exact=True).click()
        expect(page.locator(".process-step-list")).to_have_count(2)
        layout(page)
        page.screenshot(path=str(OUT / "compare-desktop.png"), full_page=True)
        page.get_by_role("button", name="Single view", exact=True).click()
        print("ok   comparison and readable step-list views", flush=True)

        jump = page.get_by_role("combobox", name="Jump to step")
        jump.select_option("qa")
        note = "Confirm the feature-specific recovery scenarios before implementing the QA harness."
        page.get_by_label("Review note", exact=True).fill(note)
        page.get_by_role("button", name="Save note", exact=True).click()
        expect(page.get_by_text("Saved to this workspace", exact=True)).to_be_visible()
        jump.select_option("stories")
        jump.select_option("qa")
        expect(page.get_by_label("Review note", exact=True)).to_have_value(note)
        page.reload()
        expect(page.get_by_role("heading", name="BAU process · Proposed", exact=True)).to_be_visible()
        page.get_by_role("combobox", name="Jump to step").select_option("qa")
        expect(page.get_by_label("Review note", exact=True)).to_have_value(note)
        saved = [f for f in api.walker("ListProcesses", token=token) if f["template_key"] == "bau-proposed"][0]
        assert saved["review_notes"]["qa"] == note
        print("ok   saved note survives step changes and reload; server read confirms it", flush=True)

        page.get_by_role("combobox", name="Jump to step").select_option("uat")
        page.get_by_role("button", name="Create linked fix story →", exact=True).click()
        expect(page.get_by_role("complementary", name="Step details")).to_contain_text("Use a new PR")
        page.get_by_role("button", name="Shared QA & rules", exact=True).click()
        expect(page.get_by_role("heading", name="Independent code review", exact=True)).to_be_visible()
        expect(page.locator(".process-policy-grid")).to_contain_text("failed-then-passing")
        page.get_by_role("button", name="To configure", exact=True).click()
        expect(page.get_by_role("heading", name="Test-data provision", exact=True)).to_be_visible()
        expect(page.locator(".process-policy-grid")).to_contain_text("Chrome is required")
        expect(page.locator(".process-policy-grid")).to_contain_text("Numeric values are unset")
        print("ok   UAT rework, shared QA rules and explicit configuration gaps", flush=True)

        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("button", name="Flowchart", exact=True).click()
        page.get_by_role("button", name="Compare versions", exact=True).click()
        page.get_by_role("button", name="Show step list", exact=True).click()
        expect(page.locator(".process-step-list")).to_have_count(2)
        layout(page)
        expect(page.get_by_role("link", name="Processes", exact=True)).to_be_visible()
        page.screenshot(path=str(OUT / "compare-mobile.png"), full_page=True)
        print("ok   390px mobile layout and navigation", flush=True)

        page.route("**/walker/ListProcesses", lambda route: route.abort())
        page.goto(BASE + "/processes")
        expect(page.get_by_role("alert")).to_contain_text("Could not load")
        expect(page.get_by_role("button", name="Add the four example flows", exact=True)).to_have_count(0)
        page.unroute("**/walker/ListProcesses")
        page.get_by_role("button", name="Retry", exact=True).click()
        expect(page.get_by_role("heading", name="React migration process · Current", exact=True)).to_be_visible()
        assert errors == [], errors
        print("ok   load failure stays an error and Retry recovers; no browser exceptions", flush=True)
        browser.close()


if __name__ == "__main__":
    run()
