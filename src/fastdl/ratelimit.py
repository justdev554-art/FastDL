import itertools
from typing import Dict, Optional, Set


class DownloadLimiter:
    """
    Track the number of concurrently streaming file downloads per client IP.

    A slot is reserved before a file response starts and released once its
    stream finishes (including on client disconnect). All methods are meant to
    be called from the event loop, so no locking is required.
    """

    def __init__(self, max_per_client: int) -> None:
        self.max_per_client = max_per_client
        self._active: Dict[str, Set[int]] = {}
        self._counter = itertools.count(1)

    def try_acquire(self, client_ip: str) -> Optional[int]:
        """
        Reserve a download slot for the given client if one is available.

        Returns a token to release later, or None when the client is already
        downloading the maximum number of files. A limit of 0 disables the cap.
        """
        if self.max_per_client <= 0:
            return next(self._counter)

        active = self._active.setdefault(client_ip, set())
        if len(active) >= self.max_per_client:
            return None

        token = next(self._counter)
        active.add(token)
        return token

    def release(self, client_ip: str, token: int) -> None:
        """
        Free the download slot associated with the given token.
        """
        active = self._active.get(client_ip)
        if active is None:
            return
        active.discard(token)
        if not active:
            self._active.pop(client_ip, None)