import json
import os
import threading
import time

import httpx
import pytest

from fastdl.ratelimit import DownloadLimiter

GAMEINFO = '\n'.join([
    '"GameInfo"',
    '{',
    '    "FileSystem"',
    '    {',
    '        "SearchPaths"',
    '        {',
    '            "mod"    "tf"',
    '        }',
    '    }',
    '}',
])


@pytest.fixture(scope="module")
def limited_config(tmp_path_factory):
    """
    A single-install config with max_concurrent_downloads_per_client = 1.
    """
    base = tmp_path_factory.mktemp("rate-limit")
    root = base / "server"
    (root / "tf" / "maps").mkdir(parents=True)
    (root / "tf" / "gameinfo.txt").write_text(GAMEINFO, encoding="utf-8")
    (root / "tf" / "maps" / "big.bsp").write_bytes(b"B" * (8 * 1024 * 1024))
    (root / "tf" / "maps" / "other.bsp").write_bytes(b"OTHER")

    config_file = base / "configuration.json"
    config_file.write_text(json.dumps({
        "servers": [
            {
                "route": "/test",
                "path_base": str(root).replace(os.sep, '/'),
                "path_mapping": {"gameinfo_path": "tf"},
            }
        ],
        "max_concurrent_downloads_per_client": 1,
    }), encoding="utf-8")

    return base


@pytest.fixture
def real_server(limited_config, monkeypatch):
    """
    Run the real app on uvicorn in a background thread so that mid-stream
    concurrency is observable over actual socket flow control.
    """
    import fastdl.configuration as configuration
    import uvicorn
    from fastdl.main import lifespan
    from fastdl.middleware import PathSanitizeMiddleware, SecurityHeadersMiddleware
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware

    monkeypatch.setattr(configuration, "conf_path", str(limited_config / "configuration.json"))

    app = Starlette(
        lifespan=lifespan,
        middleware=[
            Middleware(SecurityHeadersMiddleware),
            Middleware(PathSanitizeMiddleware),
        ],
    )
    app = CORSMiddleware(
        app=app,
        allow_origins=['*'],
        allow_methods=['GET', 'HEAD'],
    )

    server_config = uvicorn.Config(app=app, host="127.0.0.1", port=0, log_level="error", lifespan="on")
    server = uvicorn.Server(server_config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.02)

    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)


def test_limiter_caps_per_client():
    limiter = DownloadLimiter(2)
    first = limiter.try_acquire("1.2.3.4")
    second = limiter.try_acquire("1.2.3.4")
    assert first is not None
    assert second is not None
    assert limiter.try_acquire("1.2.3.4") is None


def test_limiter_allows_distinct_clients():
    limiter = DownloadLimiter(1)
    assert limiter.try_acquire("1.2.3.4") is not None
    assert limiter.try_acquire("5.6.7.8") is not None


def test_limiter_release_frees_slot():
    limiter = DownloadLimiter(1)
    token = limiter.try_acquire("1.2.3.4")
    assert token is not None
    assert limiter.try_acquire("1.2.3.4") is None
    limiter.release("1.2.3.4", token)
    assert limiter.try_acquire("1.2.3.4") is not None


def test_limiter_zero_disables_cap():
    limiter = DownloadLimiter(0)
    for _ in range(100):
        assert limiter.try_acquire("1.2.3.4") is not None


def test_second_download_rejected_while_first_streams(real_server):
    with httpx.Client() as client:
        with client.stream("GET", f"{real_server}/test/maps/big.bsp") as first:
            assert first.status_code == 200

            second = client.get(f"{real_server}/test/maps/other.bsp")
            assert second.status_code == 429

            head = client.head(f"{real_server}/test/maps/other.bsp")
            assert head.status_code == 200

            listing = client.get(f"{real_server}/test/maps/")
            assert listing.status_code == 200

        after = client.get(f"{real_server}/test/maps/other.bsp")
        assert after.status_code == 200