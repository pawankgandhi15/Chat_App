"""React browser checks with intercepted WebSockets; no backend or Redis required."""
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.browser
STAMP = "2026-10-28T10:00:00.000Z"


class Room:
    def __init__(self):
        self.routes = []
        self.received = []
        self.auto_session = True

    def route(self, socket):
        self.routes.append(socket)
        socket.on_message(lambda message: self.receive(socket, message))
        if self.auto_session:
            self.greet(socket)

    def greet(self, socket=None):
        socket = socket or self.routes[-1]
        user = unquote(urlsplit(socket.url).path.rsplit("/", 1)[-1])
        socket.send(json.dumps({"schema_version": 1, "type": "session",
            "connection_id": str(uuid4()), "container_id": "browser-test",
            "user": user, "sent_at": STAMP}))

    def broadcast(self, text, user="Alice", kind="chat", socket=None):
        event = {"schema_version": 1, "type": kind, "event_id": str(uuid4()),
            "sent_at": STAMP, "user": user, "text": text,
            "container_id": "browser-test", "time": "10:00:00 UTC"}
        (socket or self.routes[-1]).send(json.dumps(event))

    def receive(self, socket, text):
        self.received.append(text)
        user = unquote(urlsplit(socket.url).path.rsplit("/", 1)[-1])
        self.broadcast(text, user, socket=socket)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def ui(browser, request):
    url = request.config.getoption("--browser-url")
    if not url:
        pytest.skip("Use --browser-url with the Vite server or built frontend")
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    room = Room()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route_web_socket("**/ws/*", room.route)
    yield page, room, url
    context.close()
    assert not errors


def test_react_messages_keyboard_drafts_and_mobile(ui):
    page, room, url = ui
    page.goto(url)
    expect(page.locator("#status")).to_have_text("Connected")
    expect(page).to_have_title("Baatchit · Live conversations")
    expect(page.get_by_role("link", name="Baatchit", exact=True)).to_be_visible()
    composer = page.get_by_label("Message general")
    send = page.get_by_role("button", name="Send", exact=True)
    expect(send).to_be_disabled()

    composer.fill("😀😀")
    expect(page.locator("#counter")).to_have_text("2 / 2,000")
    payload = "<img src=x onerror=alert(1)> hello 👋"
    composer.fill(payload)
    send.click()
    expect(page.locator(".message p").last).to_have_text(payload)
    expect(composer).to_have_value("")
    assert page.locator("#messages img").count() == 0
    assert room.received == [payload]

    composer.fill("first line")
    composer.press("Shift+Enter")
    composer.press("End")
    composer.press("A")
    composer.dispatch_event("keydown", {"key": "Enter", "isComposing": True})
    expect(composer).to_have_value("first line\nA")
    assert len(room.received) == 1
    composer.press("Enter")
    expect(page.locator(".message p").last).to_have_text("first line\nA")
    assert room.received[-1] == "first line\nA"

    composer.fill("a draft to keep")
    page.get_by_role("button", name="Disconnect", exact=True).click()
    expect(composer).to_be_disabled()
    expect(composer).to_have_value("a draft to keep")
    page.get_by_role("button", name="Reconnect", exact=True).click()
    expect(page.locator("#status")).to_have_text("Connected")
    expect(composer).to_have_value("a draft to keep")
    assert room.received == [payload, "first line\nA"]

    name = page.get_by_label("Display name", exact=True)
    name.fill("invalid name")
    assert not name.evaluate("el => el.checkValidity()")
    name.fill("Bob")
    page.get_by_role("button", name="Update name", exact=True).click()
    expect(page.locator("#status")).to_have_text("Connected")
    expect(composer).to_have_value("a draft to keep")
    assert room.routes[-1].url.endswith("/ws/Bob")

    output = Path("artifacts/react")
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / "desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    expect(composer).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(output / "mobile.png"), full_page=True)


def test_react_session_gate_and_protocol_error(ui):
    page, room, url = ui
    room.auto_session = False
    page.goto(url)
    expect(page.get_by_label("Message general")).to_be_disabled()
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_disabled()
    expect(page.locator("#status")).to_have_text("Connecting")
    room.greet()
    expect(page.locator("#status")).to_have_text("Connected")
    page.get_by_label("Message general").fill("preserved")
    room.routes[-1].send('{"type":"invalid"}')
    expect(page.locator("#status")).to_have_text("Protocol error")
    expect(page.get_by_label("Message general")).to_have_value("preserved")
    expect(page.get_by_label("Message general")).to_be_disabled()
    assert room.received == []


def test_react_bounded_history_preserves_reading_position(ui):
    page, room, url = ui
    page.goto(url)
    expect(page.locator("#status")).to_have_text("Connected")
    room.broadcast("Alice joined", kind="system")
    expect(page.locator(".system-message")).to_have_text("Alice joined")
    for index in range(500):
        room.broadcast(f"Message {index}")
    expect(page.locator("#messages > li")).to_have_count(500)
    expect(page.locator(".message p").last).to_have_text("Message 499")
    assert page.locator(".system-message").count() == 0
    page.locator(".conversation").evaluate("el => { el.scrollTop = 6000; }")
    anchor = page.locator(".conversation").evaluate("""el => {
        const top = el.getBoundingClientRect().top;
        const node = [...el.querySelectorAll('#messages > li')].find(n => n.getBoundingClientRect().bottom > top);
        return {id: node.dataset.id, offset: node.getBoundingClientRect().top - top};
    }""")
    for index in range(500, 510):
        room.broadcast(f"Message {index}")
    expect(page.locator(".message p").last).to_have_text("Message 509")
    expect(page.locator("#messages > li")).to_have_count(500)
    expect(page.locator(".message p").first).to_have_text("Message 10")
    after = page.locator(f'[data-id="{anchor["id"]}"]').evaluate("""el =>
        el.getBoundingClientRect().top - document.querySelector('.conversation').getBoundingClientRect().top""")
    assert abs(after - anchor["offset"]) < 2
    jump = page.get_by_role("button", name="New messages")
    expect(jump).to_be_visible()
    jump.click()
    expect(jump).to_be_hidden()
    assert page.locator(".conversation").evaluate("el => el.scrollHeight - el.scrollTop - el.clientHeight < 2")
