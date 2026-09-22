import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

ROOT = Path(tempfile.mkdtemp(prefix="fastdl-tests-"))
SECRET_FILE = ROOT.parent / "secret.bsp"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


_write(ROOT / "tf" / "gameinfo.txt", '\n'.join([
    '"GameInfo"',
    '{',
    '    "FileSystem"',
    '    {',
    '        "SearchPaths"',
    '        {',
    '            "mod"    "tf"',
    '            "mod"    "."',
    '            "mod"    "tf/maps/*"',
    '        }',
    '    }',
    '}',
]))
_write(ROOT / "tf" / "maps" / "foolish" / "arena.bsp", "ARENA-BSP")
_write(ROOT / "tf" / "maps" / "foolish" / "arena.nav", "ARENA-NAV")
_write(ROOT / "tf" / "maps" / "de_test" / "de_dust.bsp", "DE-DUST")
_write(ROOT / "tf" / "maps" / "space dir" / "payload.vmt", "MOCK")
_write(ROOT / "tf" / "maps" / "space dir" / "100%odd.vtf", "MOCK")
_write(ROOT / "tf" / "maps" / "space dir" / "notes.txt", "MOCK")
_write(ROOT / "tf" / "maps" / "space dir" / "usable.nav", "MOCK")
_write(ROOT / "sound" / "vo" / "hello.wav", "HELLO-WAV")
_write(SECRET_FILE, "TOP-SECRET")

CONFIG = ROOT / "configuration.json"
CONFIG.write_text(json.dumps({
    "servers": [
        {
            "route": "/test",
            "path_base": str(ROOT).replace(os.sep, '/'),
            "path_mapping": {"gameinfo_path": "tf"},
        }
    ]
}), encoding="utf-8")

os.environ["FASTDL_CONFIG"] = str(CONFIG)


@pytest.fixture
def searchpath() -> str:
    return os.path.realpath(str(ROOT / "tf" / "maps"))


@pytest.fixture
def client():
    from fastdl.main import lifespan
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.testclient import TestClient

    from fastdl.middleware import PathSanitizeMiddleware

    app = Starlette(
        lifespan=lifespan,
        middleware=[Middleware(PathSanitizeMiddleware)],
    )
    app = CORSMiddleware(
        app=app,
        allow_origins=['*'],
        allow_methods=['GET', 'HEAD'],
    )
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


def pytest_sessionfinish(session, exitstatus) -> None:
    shutil.rmtree(ROOT, ignore_errors=True)
    if SECRET_FILE.exists():
        SECRET_FILE.unlink()