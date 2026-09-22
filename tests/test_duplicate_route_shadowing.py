import json
import os

import pytest

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
def duplicate_config(tmp_path_factory):
    """
    Build two independent game installs configured under the SAME route.

    server-a and server-b both declare gameinfo-path "tf", and both contain a
    file named shared.bsp (with different content), while only server-b owns
    only_in_b.bsp.
    """
    base = tmp_path_factory.mktemp("dup-route")
    root_a = base / "server-a"
    root_b = base / "server-b"

    for root in (root_a, root_b):
        (root / "tf" / "maps").mkdir(parents=True)
        (root / "tf" / "gameinfo.txt").write_text(GAMEINFO, encoding="utf-8")

    (root_a / "tf" / "maps" / "shared.bsp").write_bytes(b"FROM-A-ROOT")
    (root_b / "tf" / "maps" / "shared.bsp").write_bytes(b"FROM-B-ROOT")
    (root_b / "tf" / "maps" / "only_in_b.bsp").write_bytes(b"ONLY-IN-B")

    config_file = base / "configuration.json"
    config_file.write_text(json.dumps({
        "servers": [
            {
                "route": "/test",
                "path_base": str(root_a).replace(os.sep, '/'),
                "path_mapping": {"gameinfo_path": "tf"},
            },
            {
                "route": "/test",
                "path_base": str(root_b).replace(os.sep, '/'),
                "path_mapping": {"gameinfo_path": "tf"},
            },
        ]
    }), encoding="utf-8")

    return base


@pytest.fixture
def shadow_client(duplicate_config, monkeypatch):
    import fastdl.configuration as configuration
    from fastdl.main import lifespan
    from fastdl.middleware import PathSanitizeMiddleware, SecurityHeadersMiddleware
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.testclient import TestClient

    monkeypatch.setattr(configuration, "conf_path", str(duplicate_config / "configuration.json"))

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
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


def test_file_unique_to_second_server_is_served(shadow_client):
    response = shadow_client.get('/test/maps/only_in_b.bsp')
    assert response.status_code == 200
    assert response.content == b'ONLY-IN-B'


def test_first_config_wins_for_shared_filename(shadow_client):
    response = shadow_client.get('/test/maps/shared.bsp')
    assert response.status_code == 200
    assert response.content == b'FROM-A-ROOT'


def test_listing_merges_files_from_both_servers(shadow_client):
    response = shadow_client.get('/test/maps/')
    assert response.status_code == 200
    assert 'href="/test/maps/only_in_b.bsp"' in response.text
    assert 'href="/test/maps/shared.bsp"' in response.text