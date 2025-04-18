import asyncio
import os
from stat import S_ISDIR, S_ISREG
from typing import Mapping, List, Tuple, Optional

from anyio import to_thread
from .gameinfo import extract_searchpaths


class File:
    """
    Represents a file resolver that watches directories for changes and resolves paths.
    """

    def __init__(self, path_base: str, path_mapping: Mapping[str, str]):
        """
        Initialize the File object with a base path and a mapping of paths.
        """
        assert os.path.isdir(path_base), f"Invalid base directory: {path_base}"
        for path in path_mapping.values():
            assert os.path.isdir(os.path.join(path_base, path)), f"Invalid mapped directory: {path}"

        self.searchpaths = self._initialize_searchpaths(path_base, path_mapping)
        self.resolved_searchpaths: List[str] = []
        self._resolutions: List[Tuple[Optional[int], List[str]]] = []

        self.resolve()
        asyncio.get_running_loop().create_task(self.watch())

    def _initialize_searchpaths(self, path_base: str, path_mapping: Mapping[str, str]) -> List[Tuple[str, bool]]:
        """
        Extract and prepare search paths from the base path and mapping.
        """
        searchpaths = []
        for searchpath in extract_searchpaths(path_base, path_mapping):
            if os.path.basename(searchpath) == "*":
                searchpaths.append((os.path.dirname(searchpath), True))
            else:
                searchpaths.append((searchpath, False))
        return searchpaths

    def resolve(self) -> None:
        """
        Resolve all search paths and update the resolutions.
        """
        self._resolutions = [
                 (None, [])                       if not os.path.isdir(path)
            else (None, [os.path.realpath(path)]) if not wildcard
            else self._resolve_wildcard_path(path)
            for path, wildcard in self.searchpaths
        ]
        self._update_resolved_searchpaths()

    def _resolve_wildcard_path(self, path: str) -> Tuple[int, List[str]]:
        """
        Resolve a wildcard path by listing its subdirectories.
        """
        mtime = os.stat(path).st_mtime_ns
        subpaths = [
            os.path.realpath(os.path.join(path, subpath))
            for subpath in sorted(os.listdir(path))
            if os.path.isdir(os.path.join(path, subpath))
        ]
        return mtime, subpaths

    def _update_resolved_searchpaths(self) -> None:
        """
        Update the resolved search paths based on the current resolutions.
        """
        resolved_searchpaths = [
            subpath for _, subpaths in self._resolutions for subpath in subpaths
        ]
        self.resolved_searchpaths = resolved_searchpaths

    @staticmethod
    def resolve_wildcard(path: str, mtime: int, subpaths: List[str]) -> Tuple[int, List[str]]:
        """
        Resolve a wildcard path.
        """
        try:
            stat_result = os.stat(path)
        except (OSError, ValueError):
            return None, []
        if not S_ISDIR(stat_result.st_mode):
            return None, []
        current_mtime = stat_result.st_mtime_ns
        if current_mtime != mtime:
            return current_mtime, [
                os.path.realpath(os.path.join(path, subpath))
                for subpath in sorted(os.listdir(path))
                if os.path.isdir(os.path.join(path, subpath))
            ]
        return mtime, subpaths

    async def async_resolve(self) -> None:
        """
        Asynchronously resolve all wildcard paths and update resolutions.
        """
        tasks = []
        async with asyncio.TaskGroup() as group:
            for idx, (path, wildcard) in enumerate(self.searchpaths):
                if not wildcard:
                    continue
                mtime, subpaths = self._resolutions[idx]
                tasks.append((idx, group.create_task(to_thread.run_sync(self.resolve_wildcard, path, mtime, subpaths))))

        for idx, task in tasks:
            self._resolutions[idx] = task.result()

        resolved_searchpaths = [
            subpath for _, subpaths in self._resolutions for subpath in subpaths
        ]
        if self.resolved_searchpaths != resolved_searchpaths:
            self.resolved_searchpaths = resolved_searchpaths

    async def watch(self) -> None:
        """
        Continuously watch for changes in the search paths, handling shutdown cleanly.
        """
        try:
            while True:
                await asyncio.sleep(30)
                await self.async_resolve()
        except asyncio.CancelledError:
            pass

    async def __call__(self, url_path: str) -> Optional[Tuple[str, os.stat_result]]:
        """
        Resolve a URL path to a file path if it exists.
        """
        for searchpath in self.resolved_searchpaths:
            file_path = os.path.join(searchpath, url_path)
            stat_result = await to_thread.run_sync(self._stat, file_path)
            if stat_result and S_ISREG(stat_result.st_mode):
                return file_path, stat_result
        return None

    @staticmethod
    def _stat(path: str):
        try:
            return os.stat(path)
        except (OSError, ValueError):
            return None