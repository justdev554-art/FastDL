import asyncio
import os
from dataclasses import dataclass
from stat import S_ISDIR, S_ISREG
from typing import Dict, Mapping, List, Tuple, Optional

from anyio import to_thread
from .gameinfo import extract_searchpaths


@dataclass(frozen=True, slots=True)
class DirEntry:
    """
    A single entry within a directory listing.
    """
    name: str
    is_dir: bool
    size: int


class File:
    """
    Represents a file resolver that watches directories for changes and resolves paths.
    """

    def __init__(self, path_bases: List[Tuple[str, Mapping[str, str]]]):
        """
        Initialize the File object with a list of (path_base, path_mapping) roots.

        Each root contributes its own search paths (parsed from its own
        gameinfo.txt), concatenated in the given order. Root paths later in the
        list shadow files from earlier roots only fall through resolution order.
        """
        for path_base, path_mapping in path_bases:
            assert os.path.isdir(path_base), f"Invalid base directory: {path_base}"
            for path in path_mapping.values():
                assert os.path.isdir(os.path.join(path_base, path)), f"Invalid mapped directory: {path}"

        self.searchpaths = self._dedupe_searchpaths([
            searchpath
            for path_base, path_mapping in path_bases
            for searchpath in self._initialize_searchpaths(path_base, path_mapping)
        ])
        self.resolved_searchpaths: List[str] = []
        self._resolutions: List[Tuple[Optional[int], List[str]]] = []

        self.resolve()
        asyncio.get_running_loop().create_task(self.watch())

    @staticmethod
    def _dedupe_searchpaths(searchpaths: List[Tuple[str, bool]]) -> List[Tuple[str, bool]]:
        """
        Remove duplicate search paths while preserving their order.
        """
        return list(dict.fromkeys(searchpaths))

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

    async def watch(self) -> None:
        """
        Continuously watch for changes in the search paths, handling shutdown cleanly.
        """
        try:
            while True:
                await asyncio.sleep(30)
                await self.resolve_wildcard_paths()
        except asyncio.CancelledError:
            pass

    async def resolve_wildcard_paths(self) -> None:
        """
        Asynchronously resolve all wildcard paths and update resolutions.
        """
        tasks = []
        async with asyncio.TaskGroup() as group:
            for idx, (path, wildcard) in enumerate(self.searchpaths):
                if not wildcard:
                    continue
                mtime, subpaths = self._resolutions[idx]
                tasks.append((idx, group.create_task(to_thread.run_sync(self.resolve_wildcard_path, path, mtime, subpaths))))

        for idx, task in tasks:
            self._resolutions[idx] = task.result()

        resolved_searchpaths = [
            subpath for _, subpaths in self._resolutions for subpath in subpaths
        ]
        if self.resolved_searchpaths != resolved_searchpaths:
            self.resolved_searchpaths = resolved_searchpaths

    @staticmethod
    def resolve_wildcard_path(path: str, mtime: int, subpaths: List[str]) -> Tuple[int, List[str]]:
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

    async def list_dir(self, url_path: str) -> Optional[List[DirEntry]]:
        """
        Resolve a URL path to a directory listing if it exists.
        """
        return await to_thread.run_sync(self._list_dir, url_path, self.resolved_searchpaths)

    @staticmethod
    def _within(root: str, path: str) -> bool:
        """
        Return True if the given path stays within the search path root.
        """
        root = os.path.realpath(root)
        try:
            return os.path.commonpath((root, path)) == root
        except ValueError:
            return False

    @staticmethod
    def _list_dir(url_path: str, searchpaths: List[str]) -> Optional[List[DirEntry]]:
        """
        Collect a merged directory listing across all search paths.
        """
        entries: Dict[str, DirEntry] = {}
        found = False
        for searchpath in searchpaths:
            dir_path = os.path.realpath(os.path.join(searchpath, url_path))
            try:
                if not File._within(searchpath, dir_path):
                    continue
                if not S_ISDIR(os.stat(dir_path).st_mode):
                    continue
            except (OSError, ValueError):
                continue
            found = True
            try:
                with os.scandir(dir_path) as iterator:
                    for entry in iterator:
                        if entry.name in entries:
                            continue
                        try:
                            is_dir = entry.is_dir()
                            size = 0 if is_dir else entry.stat().st_size
                        except OSError:
                            is_dir = False
                            size = 0
                        entries[entry.name] = DirEntry(entry.name, is_dir, size)
            except OSError:
                continue
        if not found:
            return None
        return list(entries.values())

    async def __call__(self, url_path: str) -> Optional[Tuple[str, os.stat_result]]:
        """
        Resolve a URL path to a file path if it exists.
        """
        return await to_thread.run_sync(self._get, url_path, self.resolved_searchpaths)
    
    def _get(self, url_path: str, searchpaths: List[str]) -> Optional[Tuple[str, os.stat_result]]:
        """
        Get the file path and stat result for a given URL path.
        """
        for searchpath in searchpaths:
            # Resolve the full path and verify it stays within the search path
            file_path = os.path.realpath(os.path.join(searchpath, url_path))
            if not File._within(searchpath, file_path):
                continue

            # Check if the file exists and is a regular file
            try:
                stat_result = os.stat(file_path)
                if S_ISREG(stat_result.st_mode):
                    return file_path, stat_result
            except (OSError, ValueError):
                continue
        return None
