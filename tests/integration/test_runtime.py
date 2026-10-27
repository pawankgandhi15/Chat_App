"""Real ASGI transport and Redis tests, using isolated disposable containers."""
import asyncio
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import time

import httpx
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://localhost:8080"
REDIS_IMAGE = "redis@sha256:47b08295737773de3b711fb86f13ae802f5074e96a9a2d29f5f80164ac08c046"
pytestmark = pytest.mark.integration


def docker(*args, check=True):
    return subprocess.run(["docker", *args], text=True, capture_output=True, check=check).stdout.strip()


def port(name):
    return json.loads(docker("inspect", name))[0]["NetworkSettings"]["Ports"]["8000/tcp"][0]["HostPort"]


def wait_ready(url, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url + "/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise AssertionError("Backend did not become ready: " + url)


@pytest.fixture(scope="module")
def runtime(request):
    if not request.config.getoption("--integration"):
        pytest.skip("Use --integration for real Docker tests")
    suffix = secrets.token_hex(4)
    network = "baatchit-test-" + suffix
    names = []
    directory = ROOT / ".local" / network
    directory.mkdir(parents=True)
    password = secrets.token_hex(32)
    (directory / "url").write_text("redis://app:" + password + "@redis:6379/0")
    digest = hashlib.sha256(password.encode()).hexdigest()
    (directory / "users.acl").write_text(
        "user default off\nuser app on #" + digest
        + " &global_chat_channel +ping +publish +subscribe +unsubscribe\n")
    docker("network", "create", network)
    try:
        redis = network + "-redis"
        docker("run", "-d", "--name", redis, "--network", network, "--network-alias", "redis",
               "--mount", "type=bind,src=" + str(directory) + ",dst=/auth,readonly",
               REDIS_IMAGE, "redis-server", "--save", "", "--appendonly", "no",
               "--aclfile", "/auth/users.acl")
        names.append(redis)
        urls = []
        for index in range(2):
            name = network + "-backend-" + str(index)
            docker("run", "-d", "--name", name, "--network", network,
                   "-p", "127.0.0.1::8000", "--read-only", "--tmpfs", "/tmp",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--mount", "type=bind,src=" + str(directory) + ",dst=/auth,readonly",
                   "-e", "APP_ENV=test", "-e", "REDIS_URL_FILE=/auth/url",
                   "-e", "SUBSCRIBER_HEARTBEAT_SECONDS=1", "-e", "SUBSCRIBER_STALE_SECONDS=3",
                   "baatchit-backend:dev")
            names.append(name)
            urls.append("http://127.0.0.1:" + port(name))
        for url in urls:
            wait_ready(url)
        yield {"urls": urls, "redis": redis, "backends": names[1:]}
    finally:
        for name in reversed(names):
            docker("rm", "-f", name, check=False)
        docker("network", "rm", network, check=False)
        for name in ["url", "users.acl"]:
            (directory / name).unlink(missing_ok=True)
        directory.rmdir()


def ws(url, username="test", **kwargs):
    return connect(url.replace("http:", "ws:") + "/ws/" + username,
                   origin=ORIGIN, subprotocols=["chat.v1"], **kwargs)


async def event(socket, kind="chat"):
    async with asyncio.timeout(5):
        while True:
            value = json.loads(await socket.recv())
            if value["type"] == kind:
                return value


async def test_session_first_cross_replica_once(runtime):
    a, b = runtime["urls"]
    async with ws(a, "Alice") as left, ws(b, "Bob") as right:
        first_a, first_b = [json.loads(await socket.recv()) for socket in [left, right]]
        assert first_a["type"] == first_b["type"] == "session"
        assert first_a["container_id"] != first_b["container_id"]
        await left.send("  hello\r\nworld  ")
        x, y = await asyncio.gather(event(left), event(right))
        assert x == y and x["text"] == "hello\nworld"
        assert x["container_id"] == first_a["container_id"]
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.2):
                await event(left)


@pytest.mark.parametrize("payload,code", [(b"binary",1003), ("\x00",1008), ("x"*2001,1008),
                                          (["x"*9000, "x"*9000],1009)])
async def test_actual_transport_close_codes(runtime, payload, code):
    async with ws(runtime["urls"][0]) as socket:
        assert json.loads(await socket.recv())["type"] == "session"
        await socket.send(payload)
        with pytest.raises(ConnectionClosed) as closed:
            while True:
                await asyncio.wait_for(socket.recv(), 5)
        assert closed.value.rcvd.code == code


async def test_denied_handshakes(runtime):
    url = runtime["urls"][0].replace("http:", "ws:")
    for origin, protocols, username, expected in [
        ("https://evil.invalid", ["chat.v1"], "test", 403),
        (ORIGIN, [], "test", 400),
        (ORIGIN, ["chat.v1"], "bad%20name", 400),
    ]:
        with pytest.raises(InvalidStatus) as rejected:
            async with connect(url + "/ws/" + username, origin=origin, subprotocols=protocols):
                pass
        assert rejected.value.response.status_code == expected


async def test_redis_loss_and_recovery_without_backend_restart(runtime):
    a, b = runtime["urls"]
    async with ws(a) as socket:
        await socket.recv()
        docker("stop", "-t", "1", runtime["redis"])
        try:
            async with httpx.AsyncClient() as client:
                assert (await client.get(a + "/health")).status_code == 503
                assert (await client.get(a + "/live")).status_code == 200
            with pytest.raises(ConnectionClosed) as closed:
                async with asyncio.timeout(6):
                    while True:
                        await socket.recv()
            assert closed.value.rcvd.code == 1011
        finally:
            docker("start", runtime["redis"])
        for url in [a,b]:
            await asyncio.to_thread(wait_ready, url, 15)
    await test_session_first_cross_replica_once(runtime)


async def test_planned_signal_drain(runtime):
    url = runtime["urls"][1]
    async with ws(url) as socket:
        await socket.recv()
        docker("kill", "--signal", "TERM", runtime["backends"][1])
        with pytest.raises(ConnectionClosed) as closed:
            async with asyncio.timeout(10):
                while True:
                    await socket.recv()
        assert closed.value.rcvd.code == 1012
    # Restore the disposable test replica, not any user's cluster.
    subprocess.run(["docker", "wait", runtime["backends"][1]], check=True, capture_output=True, timeout=20)
    docker("start", runtime["backends"][1])
    url = "http://127.0.0.1:" + port(runtime["backends"][1])
    runtime["urls"][1] = url
    await asyncio.to_thread(wait_ready, url)


async def test_acl_rejects_admin_and_other_channels(runtime):
    code = (
        "import asyncio; from app.settings import Settings; from redis.asyncio import Redis; "
        "from redis.exceptions import NoPermissionError\n"
        "async def main():\n"
        " c=Redis.from_url(Settings().resolve_redis_url(),protocol=2,lib_name=None,lib_version=None)\n"
        " for command in [('FLUSHALL',),('PUBLISH','other_channel','x')]:\n"
        "  try: await c.execute_command(*command)\n"
        "  except NoPermissionError: pass\n"
        "  else: raise AssertionError('ACL allowed forbidden command')\n"
        " await c.aclose()\n"
        "asyncio.run(main())"
    )
    docker("exec", runtime["backends"][0], "python", "-c", code)
