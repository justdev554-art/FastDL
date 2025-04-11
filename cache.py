import os

from anyio import Path
from gameinfo import extract_searchpaths, resolve_searchpaths
from typing import Mapping, Sequence


class FileCache:
    def __init__(self, path_base: str, path_mapping: Mapping[str, str]):
        assert os.path.isdir(path_base)
        for path in path_mapping.values():
            assert os.path.isdir(os.path.join(path_base, path))
        self.searchpaths: Sequence[str] = extract_searchpaths(
            path_base, path_mapping)
        self.searchpaths_resolved: Sequence[str] = tuple()
        self.cache: Mapping[str, str] = {}

    async def access(self, request: str) -> str | None:
        if path := await self._cache_get(request):
            return path
        else:
            return await self._cache_update(request)

    async def _cache_get(self, request: str) -> str:
        try:
            path = self.cache[request]
        except KeyError:
            return None
        if await Path(path).is_file():
            return path
        else:
            del self.cache[request]
            return None

    async def _cache_update(self, request: str) -> None:
        path = await self._get(request)
        if path:
            self.cache[request] = path
        return path

    async def _get(self, request: str) -> str | None:
        if path := await self._load(request):
            return path
        elif not await self._resolve():
            return None
        elif path := await self._load(request):
            return path
        else:
            return None

    async def _resolve(self) -> bool:
        resolved = [searchpath async for searchpath in resolve_searchpaths(self.searchpaths)]
        status = resolved != self.searchpaths_resolved
        self.searchpaths_resolved = resolved
        return status

    async def _load(self, request: str) -> str | None:
        for searchpath in self.searchpaths_resolved:
            path = os.path.join(searchpath, request)
            print(path)
            if await Path(path).is_file():
                return path
        return None
