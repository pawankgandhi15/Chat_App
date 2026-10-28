from pathlib import Path
import re
from uuid import uuid4

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
        expect(left).to_have_title("Baatchit · Live conversations")
        expect(left.get_by_role("link", name="Baatchit", exact=True)).to_be_visible()
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


def test_real_direct_chat_excludes_third_browser(request):
    url = request.config.getoption("--browser-url")
    if not url:
        pytest.skip("Use --browser-url with the full app and Redis")
    suffix = uuid4().hex[:6]
    alice_name, bob_name, observer_name = (f"Alice_{suffix}", f"Bob_{suffix}", f"Observer_{suffix}")
    secret = f"direct message {uuid4()}"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        alice, bob, observer = (context.new_page() for _ in range(3))
        frames = []
        observer.on("websocket", lambda socket: socket.on("framereceived", lambda frame: frames.append(str(frame))))
        for page, name in ((alice, alice_name), (bob, bob_name), (observer, observer_name)):
            page.goto(url)
            expect(page.locator("#status")).to_have_text("Connected", timeout=20000)
            page.get_by_label("Display name", exact=True).fill(name)
            page.get_by_role("button", name="Update name", exact=True).click()
        alice_to_bob = alice.get_by_role("button", name=re.compile("^" + re.escape(bob_name)))
        bob_to_alice = bob.get_by_role("button", name=re.compile("^" + re.escape(alice_name)))
        expect(alice_to_bob).to_be_visible(timeout=20000)
        expect(bob_to_alice).to_be_visible(timeout=20000)
        alice_to_bob.click()
        alice.get_by_label(f"Message {bob_name}").fill(secret)
        alice.get_by_role("button", name="Send", exact=True).click()
        expect(alice.get_by_text(secret, exact=True)).to_be_visible(timeout=10000)
        bob_to_alice.click()
        expect(bob.get_by_text(secret, exact=True)).to_be_visible(timeout=10000)
        observer.wait_for_timeout(500)
        assert observer.get_by_text(secret, exact=True).count() == 0
        assert all(secret not in frame for frame in frames)
        context.close()
        browser.close()
