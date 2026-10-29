"""Real browser + HTTP/WebSocket + SQLite persistence; Redis publishing is stubbed.

Runs independently of --browser-url against the built frontend in frontend/dist.
"""
import asyncio
from pathlib import Path
import socket
import threading
import time
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright
from starlette.staticfiles import StaticFiles
from uvicorn import Config, Server

from app.main import create_app
from app.settings import Settings

PASSWORD = "my-long-test-password"


@pytest.fixture
def saved_app(tmp_path):
    bundle = Path("frontend/dist")
    if not (bundle / "index.html").exists():
        pytest.skip("Run npm run build before the saved-chat browser tests")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    origin = "http://127.0.0.1:" + str(listener.getsockname()[1])
    app = create_app(Settings(app_env="test", redis_url="redis://127.0.0.1:1/0", allowed_origins=origin,
        database_url="sqlite:///" + (tmp_path / "browser.db").as_posix()))
    app.state.runtime.accounts.storage.migrate()
    app.state.runtime.broker.start = AsyncMock()
    app.state.runtime.broker.publish = AsyncMock(return_value=1)
    app.mount("/", StaticFiles(directory=bundle, html=True))
    server = Server(Config(app, log_level="error", access_log=False, lifespan="on",
                           ws="websockets", timeout_graceful_shutdown=3))
    async def serve():
        app.state.test_loop = asyncio.get_running_loop()
        await server.serve(sockets=[listener])
    thread = threading.Thread(target=lambda: asyncio.run(serve()), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(.02)
    assert server.started
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            yield browser, origin, app.state.runtime.accounts.storage
        finally:
            browser.close()
    # Use the application's production drain path before stopping the test server.
    app.state.test_loop.call_soon_threadsafe(app.state.runtime.drain)
    server.should_exit = True
    thread.join(timeout=10)
    listener.close()
    assert not thread.is_alive()


def register(page, origin, name):
    page.goto(origin)
    page.get_by_role("button", name="Sign in for saved chats").click()
    page.get_by_role("button", name="New here? Create an account").click()
    page.get_by_label("Username", exact=True).fill(name)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Create account", exact=True).click()
    expect(page.get_by_text("Signed-in account", exact=True)).to_be_visible()


def login(page, origin, name):
    page.goto(origin)
    page.get_by_role("button", name="Sign in for saved chats").click()
    page.get_by_label("Username", exact=True).fill(name)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.get_by_text("Signed-in account", exact=True)).to_be_visible()


def test_accounts_history_refresh_logout_offline_and_isolation(saved_app):
    browser, origin, storage = saved_app
    alice, bob, observer = [browser.new_context() for _ in range(3)]
    a, b, o = [context.new_page() for context in (alice, bob, observer)]
    errors = []
    a.on("pageerror", lambda error: errors.append(str(error)))
    register(a, origin, "Alice")
    register(b, origin, "Bob")
    register(o, origin, "Observer")
    a.get_by_label("START A CONVERSATION").fill("bo")
    a.locator(".account-results button").filter(has_text="bob").click()
    expect(a.get_by_role("heading", name="bob", exact=True)).to_be_visible()
    a.get_by_label("Message bob", exact=True).fill("<script>alert('hello')</script> saved hello")
    a.get_by_role("button", name="Send", exact=True).click()
    expect(a.locator(".saved-message p")).to_have_text("<script>alert('hello')</script> saved hello")
    b.locator(".peer-list button").filter(has_text="alice").click()
    expect(b.locator(".saved-message p")).to_have_text("<script>alert('hello')</script> saved hello")
    conversation = alice.request.get(origin + "/api/conversations").json()["items"][0]["id"]
    denied = observer.request.get(origin + f"/api/conversations/{conversation}/messages")
    assert denied.status == 404
    assert o.locator(".saved-message").count() == 0
    assert a.locator(".saved-message script").count() == 0
    a.reload()
    a.locator(".peer-list button").filter(has_text="bob").click()
    expect(a.locator(".saved-message p")).to_have_text("<script>alert('hello')</script> saved hello")
    a.get_by_role("button", name="Sign out", exact=True).click()
    expect(a.get_by_role("button", name="Sign in for saved chats")).to_be_visible()
    login(a, origin, "ALICE")
    a.locator(".peer-list button").filter(has_text="bob").click()
    expect(a.locator(".saved-message p")).to_have_count(1)
    bob.close()
    a.get_by_label("Message bob", exact=True).fill("Saved while you were away")
    a.get_by_role("button", name="Send", exact=True).click()
    expect(a.locator(".saved-message p")).to_have_count(2)
    returned = browser.new_context()
    b = returned.new_page()
    login(b, origin, "bob")
    b.locator(".peer-list button").filter(has_text="alice").click()
    expect(b.locator(".saved-message p").last).to_have_text("Saved while you were away")
    artifacts = Path("artifacts/accounts")
    artifacts.mkdir(parents=True, exist_ok=True)
    a.screenshot(path=str(artifacts / "desktop.png"))
    a.set_viewport_size({"width": 390, "height": 844})
    expect(a.get_by_label("Message bob", exact=True)).to_be_visible()
    assert a.evaluate("document.documentElement.scrollWidth <= innerWidth")
    a.screenshot(path=str(artifacts / "mobile.png"))
    assert not errors


def test_ambiguous_send_retry_and_older_history(saved_app):
    browser, origin, storage = saved_app
    bob, _ = storage.register("Bob", PASSWORD)
    context = browser.new_context()
    page = context.new_page()
    register(page, origin, "Alice")
    page.get_by_label("START A CONVERSATION").fill("bo")
    page.locator(".account-results button").filter(has_text="bob").click()
    expect(page.get_by_label("Message bob", exact=True)).to_be_enabled()
    def lose_response(route):
        response = route.fetch()
        assert response.status == 200
        route.abort("failed")
    page.route("**/api/conversations/*/messages", lambda route: lose_response(route) if route.request.method == "POST" else route.continue_(), times=1)
    page.get_by_label("Message bob", exact=True).fill("retry this once")
    page.get_by_role("button", name="Send", exact=True).click()
    expect(page.get_by_role("button", name="Send", exact=True)).to_be_enabled()
    expect(page.get_by_label("Message bob", exact=True)).to_have_value("retry this once")
    page.get_by_role("button", name="Send", exact=True).click()
    expect(page.get_by_label("Message bob", exact=True)).to_have_value("")
    expect(page.locator(".saved-message p")).to_have_count(1)
    token = next(cookie["value"] for cookie in context.cookies() if cookie["name"] == "baatchit_session")
    conversation = storage.list_conversations(token)["items"][0]["id"]
    for index in range(55):
        storage.send(token, conversation, str(uuid4()), "history " + str(index))
    page.reload()
    page.locator(".peer-list button").filter(has_text="bob").click()
    expect(page.locator(".saved-message p")).to_have_count(50)
    page.get_by_role("button", name="Load older messages").click()
    expect(page.locator(".saved-message p")).to_have_count(56)
    expect(page.locator(".saved-message p").first).to_have_text("retry this once")
    page.get_by_role("button", name="Return to latest messages").click()
    expect(page.locator(".saved-message p").last).to_have_text("history 54")


def test_component_search_drafts_copy_and_auth_controls(saved_app):
    browser, origin, storage = saved_app
    storage.register("Bob", PASSWORD)
    storage.register("Charlie", PASSWORD)
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    page.goto(origin)
    page.get_by_role("button", name="Sign in for saved chats").click()
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Show password", exact=True).click()
    expect(page.get_by_label("Password", exact=True)).to_have_attribute("type", "text")
    page.get_by_role("button", name="Hide password", exact=True).click()
    expect(page.get_by_label("Password", exact=True)).to_have_attribute("type", "password")
    artifacts = Path("artifacts/accounts")
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts / "signin-components.png"))
    page.get_by_role("button", name="New here? Create an account").click()
    page.get_by_label("Username", exact=True).fill("Alice")
    page.get_by_role("button", name="Create account", exact=True).click()
    search = page.get_by_label("START A CONVERSATION", exact=True)
    search.fill("nobody_here")
    expect(page.get_by_text("No accounts found. Check the username and try again.")).to_be_visible()
    search.fill("bo")
    page.locator(".account-results button").filter(has_text="bob").click()
    page.get_by_label("Message bob", exact=True).fill("a draft for bob")
    expect(page.locator(".peer-list button").filter(has_text="bob")).to_contain_text("Draft: a draft for bob")
    search.fill("ch")
    page.locator(".account-results button").filter(has_text="charlie").click()
    expect(page.get_by_label("Message charlie", exact=True)).to_have_value("")
    chat_filter = page.get_by_label("Filter loaded conversations", exact=True)
    chat_filter.fill("bob")
    expect(page.locator(".peer-list button")).to_have_count(1)
    page.locator(".peer-list button").click()
    expect(page.get_by_label("Message bob", exact=True)).to_have_value("a draft for bob")
    page.get_by_role("button", name="Clear filter loaded conversations").click()
    expect(page.locator(".peer-list button")).to_have_count(2)
    page.get_by_role("button", name="Send", exact=True).click()
    expect(page.locator(".saved-message p")).to_have_text("a draft for bob")
    expect(page.locator(".date-divider")).to_have_count(1)
    page.get_by_role("button", name="Copy message 1", exact=True).click()
    expect(page.get_by_text("Message copied to clipboard.")).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == "a draft for bob"
    page.get_by_role("button", name="Activity", exact=True).click()
    expect(page.get_by_text("You're all caught up in this tab.")).to_be_visible()
    page.get_by_role("button", name="All chats", exact=True).click()
    expect(page.locator(".peer-list button")).to_have_count(2)
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.get_by_label("Message bob", exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_failed_history_has_retry_instead_of_empty_conversation(saved_app):
    browser, origin, storage = saved_app
    bob, _ = storage.register("Bob", PASSWORD)
    alice, token = storage.register("Alice", PASSWORD)
    conversation = storage.open_conversation(token, bob["id"])["id"]
    storage.send(token, conversation, str(uuid4()), "still saved in the database")
    context = browser.new_context()
    page = context.new_page()
    login(page, origin, "alice")
    pattern = "**/api/conversations/*/messages"
    page.route(pattern, lambda route: route.fulfill(status=503, content_type="application/json", body='{"detail":"Please retry."}'))
    page.locator(".peer-list button").filter(has_text="bob").click()
    retry = page.get_by_role("button", name="Retry message history")
    expect(retry).to_be_visible()
    assert page.get_by_text("Say hello to bob.", exact=True).count() == 0
    page.unroute(pattern)
    retry.click()
    expect(page.locator(".saved-message p")).to_have_text("still saved in the database")


def test_saved_conversation_tools_search_details_and_modal_focus(saved_app):
    browser, origin, storage = saved_app
    bob, _ = storage.register("Bob", PASSWORD)
    _, token = storage.register("Alice", PASSWORD)
    conversation = storage.open_conversation(token, bob["id"])["id"]
    storage.send(token, conversation, str(uuid4()), "<script>launch</script> notes")
    storage.send(token, conversation, str(uuid4()), "a different topic")
    page = browser.new_page()
    login(page, origin, "alice")
    page.locator(".peer-list button").filter(has_text="bob").click()
    expect(page.locator(".saved-message")).to_have_count(2)
    trigger = page.get_by_role("button", name="Conversation tools", exact=True)
    trigger.click()
    dialog = page.get_by_role("dialog", name="Conversation tools", exact=True)
    close = dialog.get_by_role("button", name="Close conversation tools")
    expect(close).to_be_focused()
    close.press("Shift+Tab")
    assert page.evaluate("document.querySelector('dialog').contains(document.activeElement)")
    dialog.get_by_label("Search loaded messages", exact=True).fill("LAUNCH")
    expect(dialog.locator(".search-results p")).to_have_text("<script>launch</script> notes")
    assert dialog.locator("script").count() == 0
    dialog.get_by_role("button", name="Details", exact=True).click()
    expect(dialog.get_by_text("You and the other account", exact=True)).to_be_visible()
    expect(dialog.get_by_text("2 in the current view", exact=True)).to_be_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    assert dialog.evaluate("el => el.getBoundingClientRect().right <= innerWidth && el.scrollWidth <= el.clientWidth")
    artifacts = Path("artifacts/accounts")
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts / "conversation-tools-mobile.png"))
    dialog.press("Escape")
    expect(dialog).to_have_count(0)
    expect(trigger).to_be_focused()
    expect(page.get_by_label("Message bob", exact=True)).to_be_visible()
