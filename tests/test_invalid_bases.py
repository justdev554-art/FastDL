import json
import os

import pytest

GAMEINFO_VALID = '\n'.join([
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

# Unparseable: not Source keyvalues, so gameinfo.txt exists but cannot be read.
GAMEINFO_INVALID = 'this is not source keyvalues'


def _build_server(base, name: str, gameinfo: str, maps: bool = True):
    root = base / name
    (root / "tf" / "maps").mkdir(parents=True)
    (root / "tf" / "gameinfo.txt").write_text(gameinfo, encoding="utf-8")
    if maps:
        (root / "tf" / "maps" / "arena.bsp").write_bytes(b"ARENA")
    return root


@pytest.fixture
def invalid_bases_config(tmp_path_factory):
    """
    One route with three entries: a valid install, an entry whose base
    directory does not exist, and an entry whose gameinfo.txt is unparseable.
    Startup must continue to serve the valid entry and log warnings for the
    other two.
    """
    base = tmp_path_factory.mktemp("invalid-bases-mixed")
    root_valid = _build_server(base, "server-valid", GAMEINFO_VALID)

    missing_base = (base / "server-missing-base") / "tf" / "gameinfo.txt"

    config_file = base / "configuration.json"
    config_file.write_text(json.dumps({
        "servers": [
            {
                "route": "/test",
                "path_base": str(root_valid).replace(os.sep, '/'),
                "path_mapping": {"gameinfo_path": "tf"},
            },
            {
                "route": "/test",
                "path_base": str(missing_base.parents[2]).replace(os.sep, '/'),
                "path_mapping": {"gameinfo_path": "tf"},
            },
            {
                "route": "/test",
                "path_base": str(_build_server(base, "server-bad-gameinfo", GAMEINFO_INVALID)).replace(os.sep, '/'),
                "path_mapping": {"gameinfo_path": "tf"},
            },
        ]
    }), encoding="utf-8")

    return base


@pytest.fixture(scope="module")
def only_invalid_config(tmp_path_factory):
    """
    A route whose every entry has a missing base directory: the route must be
    skipped entirely (404) instead of crashing startup.
    """
    base = tmp_path_factory.mktemp("invalid-bases-only")
    missing = (base / "missing-a" / "tf" / "gameinfo.txt")
    config_file = base / "configuration.json"
    config_file.write_text(json.dumps({
        "servers": [
            {
                "route": "/test",
                "path_base": str(missing.parents[2]).replace(os.sep, '/'),
                "path_mapping": {"gameinfo_path": "tf"},
            },
            {
                "route": "/test",
                "path_base": str((base / "missing-b" / "tf" / "gameinfo.txt").parents[2]).replace(os.sep, '/'),
                "path_mapping": {"gameinfo_path": "tf"},
            },
        ]
    }), encoding="utf-8")
    return base


def _make_client(fixture_value, monkeypatch):
    import fastdl.configuration as configuration
    from fastdl.main import lifespan
    from fastdl.middleware import PathSanitizeMiddleware, SecurityHeadersMiddleware
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.testclient import TestClient

    monkeypatch.setattr(
        configuration, "conf_path", str(fixture_value / "configuration.json")
    )
    app = Starlette(
        lifespan=lifespan,
        middleware=[
            Middleware(SecurityHeadersMiddleware),
            Middleware(PathSanitizeMiddleware),
        ],
    )
    app = CORSMiddleware(app=app, allow_origins=["*"])
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def mixed_client(invalid_bases_config, monkeypatch):
    with _make_client(invalid_bases_config, monkeypatch) as client:
        yield client


@pytest.fixture
def only_invalid_client(only_invalid_config, monkeypatch):
    with _make_client(only_invalid_config, monkeypatch) as client:
        yield client


def test_valid_root_still_served_alongside_invalid_ones(mixed_client):
    response = mixed_client.get("/test/maps/arena.bsp")
    assert response.status_code == 200
    assert response.content == b"ARENA"


def test_listing_still_available_when_other_entries_invalid(mixed_client):
    response = mixed_client.get("/test/maps/")
    assert response.status_code == 200
    assert b"arena.bsp" in response.content


def test_route_with_only_missing_bases_is_skipped(only_invalid_client):
    for path in ("/test", "/test/", "/test/maps/arena.bsp"):
        assert only_invalid_client.get(path).status_code == 404
