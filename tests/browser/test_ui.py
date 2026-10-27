from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

pytestmark = pytest.mark.browser


def test_browser_chat_and_mobile(request):
    url = request.config.getoption("--browser-url")
    if not url:
        pytest.skip("Use --browser-url http://localhost:8080")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        left, right = context.new_page(), context.new_page()
        errors = []
        left.on("pageerror", lambda error: errors.append(str(error)))
        left.goto(url)
        right.goto(url)
        expect(left.locator("#status")).to_have_text("Connected", timeout=20000)
        expect(right.locator("#status")).to_have_text("Connected", timeout=20000)
        left.get_by_label("Message general").fill("<img src=x onerror=alert(1)> hello 👋")
        left.get_by_role("button", name="Send", exact=True).click()
        expect(right.locator(".message p").last).to_have_text("<img src=x onerror=alert(1)> hello 👋")
        assert right.locator("#messages img").count() == 0
        left.get_by_label("Message general").fill("a draft to keep")
        left.get_by_role("button", name="Disconnect", exact=True).click()
        expect(left.get_by_label("Message general")).to_have_value("a draft to keep")
        expect(left.get_by_role("button", name="Send", exact=True)).to_be_disabled()
        left.get_by_role("button", name="Reconnect", exact=True).click()
        expect(left.locator("#status")).to_have_text("Connected")
        expect(left.get_by_label("Message general")).to_have_value("a draft to keep")
        assert right.get_by_text("a draft to keep", exact=True).count() == 0
        output = Path("artifacts")
        output.mkdir(exist_ok=True)
        left.screenshot(path=str(output / "desktop.png"), full_page=True)
        left.set_viewport_size({"width":390,"height":844})
        expect(left.get_by_label("Message general")).to_be_visible()
        assert left.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        left.screenshot(path=str(output / "mobile.png"), full_page=True)
        assert not errors
        browser.close()
