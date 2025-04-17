import os
from typing import Mapping, Sequence

from anyio import Path
from aiorwlock import RWLock

from .gameinfo import extract_searchpaths, resolve_searchpaths


class FileCache:
    def __init__(self, path_base: str, path_mapping: Mapping[str, str]):
        assert os.path.isdir(path_base)
        for path in path_mapping.values():
            assert os.path.isdir(os.path.join(path_base, path))
        self._searchpaths: Sequence[str] = extract_searchpaths(
            path_base, path_mapping)
        self._searchpaths_resolved: Sequence[str] = tuple()
        self._cache: Mapping[str, str] = {}
        self._rwlock: RWLock = RWLock()

    async def access(self, request: str) -> str | None:
        if path := await self._cache_get(request):
            return path
        else:
            return await self._cache_update(request)

    async def _cache_get(self, request: str) -> str:
        try:
            async with self._rwlock.reader_lock:        
                path = self._cache[request]
        except KeyError:
            return None
        if not await Path(path).is_file():
            return None
        return path

    async def _cache_update(self, request: str) -> str | None:
        path = await self._get(request)

        async with self._rwlock.writer_lock:
            if path:
                self._cache[request] = path
            elif request in self._cache:
                del self._cache[request]

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
        resolved = await resolve_searchpaths(self._searchpaths)
        status = resolved != self._searchpaths_resolved
        self._searchpaths_resolved = resolved
        return status

    async def _load(self, request: str) -> str | None:
        for searchpath in self._searchpaths_resolved:
            path = os.path.join(searchpath, request)
            if await Path(path).is_file():
                return path
        return None
