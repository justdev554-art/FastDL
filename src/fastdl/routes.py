import html
import logging
import os
from mimetypes import guess_file_type
from typing import AsyncGenerator, Callable, List, Tuple
from urllib.parse import quote

from aiofile import AIOFile
from anyio import open_file
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, Response, StreamingResponse
from starlette.routing import Mount, Route

from fastdl.configuration import Server
from fastdl.file import DirEntry, File
from fastdl.ratelimit import DownloadLimiter

logger = logging.getLogger("fastdl")


class Suffix:
    """
    A predicate class to check if a file path ends with specific extensions.
    """
    def __init__(self, *extensions: str):
        self.extensions = tuple(f"{ext}.bz2" for ext in extensions) + extensions

    def __call__(self, path: str) -> bool:
        # Return True if the path ends with any allowed extension
        # (self.extensions includes both original extensions and their “.bz2” variants)
        return any(path.endswith(ext) for ext in self.extensions)

    def __str__(self) -> str:
        return f"only with the following extensions: {', '.join(self.extensions)}"


# Define subroutes with their respective share paths and predicates
SUBROUTES: List[Tuple[str, str, Callable[[str], bool]]] = [
    (r'/maps',          r'maps',          Suffix('.bsp', '.nav')),
    (r'/materials',     r'materials',     Suffix('.vmt', '.vtf')),
    (r'/models',        r'models',        Suffix('.mdl', '.phy', '.vmt', '.vtf', '.vtx', '.vvd')),
    (r'/scripts/items', r'scripts/items', Suffix('.txt')),
    (r'/shaders',       r'shaders',       Suffix('.vcs')),
    (r'/sound',         r'sound',         Suffix('.mp3', '.wav')),
]

CHUNK_SIZE = 64 * 1024  # 64 KiB

# Hardening headers for the HTML listing pages (self-contained, no scripts)
LISTING_HEADERS = {
    "content-security-policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; "
        "media-src 'none'; object-src 'none'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'"
    ),
}

def _join_url(*parts: str) -> str:
    """
    Join URL path segments into an application-rooted absolute path.
    """
    cleaned = [part.strip('/') for part in parts if part.strip('/')]
    return '/' + '/'.join(cleaned)

def format_size(size: int) -> str:
    """
    Format a byte count into a human-readable string.
    """
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in ('KiB', 'MiB', 'GiB', 'TiB', 'PiB'):
        value /= 1024
        if value < 1024:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} PiB"

def _page(title: str, rows: List[str]) -> str:
    """
    Render a minimal HTML page wrapping the given table rows.
    """
    body = '\n'.join(rows)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; margin: 2rem; color: #222; }}
  a {{ color: #0645ad; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  table {{ border-collapse: collapse; }}
  th, td {{ padding: 0.15rem 1.5rem 0.15rem 0; text-align: left; }}
  td.size {{ color: #666; }}
  h1 {{ font-size: 1.2rem; font-weight: 600; }}
</style>
</head>
<body>
<h1>Index of {html.escape(title)}</h1>
<table>
<thead><tr><th>Name</th><th>Size</th></tr></thead>
<tbody>
{body}
</tbody>
</table>
</body>
</html>'''

def render_server_index(server_route: str, subroutes: List[Tuple[str, str]]) -> str:
    """
    Render the root index page listing the given subroutes.

    Only subroutes whose share directory exists and is non-empty should be passed here;
    missing or completely empty directories are omitted from the index.
    """
    rows: List[str] = []
    for subroute, share in subroutes:
        href = _join_url(server_route, subroute)
        rows.append(
            f'<tr><td><a href="{href}/">{html.escape(subroute.strip("/"))}/</a></td>'
            f'<td class="size">{html.escape(share)}</td></tr>'
        )
    if not rows:
        rows.append('<tr><td colspan="2"><em>(no content)</em></td></tr>')
    return _page(server_route, rows)

def render_directory_listing(server_route: str, subroute: str, subpath: str, entries: List[DirEntry], predicate: Callable[[str], bool]) -> str:
    """
    Render a directory listing page for the given subroute and relative path.
    """
    subpath = subpath.strip('/')
    segments = [segment for segment in subpath.split('/') if segment]
    quoted_segments = [quote(segment) for segment in segments]
    title_parts = [part for part in (subroute, subpath) if part]
    title = '/'.join(title_parts)
    base = _join_url(server_route, subroute, *quoted_segments)

    rows: List[str] = []

    if segments:
        parent = _join_url(server_route, subroute, *quoted_segments[:-1])
        rows.append(f'<tr><td><a href="{parent}/">../</a></td><td class="size">-</td></tr>')
    else:
        root = quote(server_route.strip('/'))
        rows.append(f'<tr><td><a href="/{root}/">../</a></td><td class="size">-</td></tr>')

    directories = sorted((entry for entry in entries if entry.is_dir), key=lambda entry: entry.name.lower())
    files = sorted(
        (entry for entry in entries if not entry.is_dir and predicate(entry.name)),
        key=lambda entry: entry.name.lower(),
    )

    for entry in directories:
        href = f"{base}/{quote(entry.name)}/"
        rows.append(f'<tr><td><a href="{href}">{html.escape(entry.name)}/</a></td><td class="size">-</td></tr>')

    for entry in files:
        href = f"{base}/{quote(entry.name)}"
        rows.append(
            f'<tr><td><a href="{href}">{html.escape(entry.name)}</a></td>'
            f'<td class="size">{format_size(entry.size)}</td></tr>'
        )

    if not entries:
        rows.append('<tr><td colspan="2"><em>(empty)</em></td></tr>')

    return _page(title, rows)

async def stream_file(file_path: str) -> AsyncGenerator[bytes, None]:
    """
    Asynchronously stream a file in chunks.
    """
    async with await open_file(file_path, mode="rb") as fp, AIOFile.from_fp(fp.wrapped) as file:
        offset = 0
        while chunk := await file.read_bytes(CHUNK_SIZE, offset):
            offset += len(chunk)
            yield chunk

def make_endpoint(server_route: str, share: str, subroute: str, access: File, predicate: Callable[[str], bool], limiter: DownloadLimiter) -> Callable:
    """
    Create an endpoint for serving files based on a share path and predicate.
    """
    async def endpoint(request: Request) -> Response:
        # Build the target path by joining the share directory with the requested subpath
        subpath = request.path_params.get('path') or ''
        url_path = os.path.normpath(os.path.join(share, subpath))

        # If the target is a directory, present a browsable listing of it
        if request.method == 'GET' and (listing := await access.list_dir(url_path)) is not None:
            # Hide completely empty subdirectories so the listing only shows folders with content
            listing = [
                entry for entry in listing
                if not entry.is_dir
                or await access.list_dir(os.path.join(url_path, entry.name))
            ]
            return HTMLResponse(
                render_directory_listing(server_route, subroute, subpath, listing, predicate),
                status_code=200,
                headers=LISTING_HEADERS,
            )

        # If the path does not satisfy our file‐extension predicate, reject the request
        if not predicate(url_path):
            # 422 Unprocessable Entity: the file exists but is not of an allowed type
            return Response(status_code=422)

        # Attempt to locate (and possibly fetch) the file asynchronously
        if pair := await access(url_path):
            file_path, stat_result = pair

            # Determine the MIME type from the file extension, defaulting if unknown
            guess = guess_file_type(file_path)
            media_type = f"application/x-{guess[1]}" if guess[1] else guess[0] or "application/octet-stream"

            content_length = str(stat_result.st_size)

            headers = {
                "content-length": content_length,
            }

            if request.method == "HEAD":
                # If the request method is HEAD, return headers only
                return Response(
                    headers=headers,
                    media_type=media_type,
                )

            # Reject the download if this client already holds the maximum
            # number of concurrently streaming files
            client_ip = request.client.host if request.client else "unknown"
            token = limiter.try_acquire(client_ip)
            if token is None:
                return PlainTextResponse('Too Many Requests', status_code=429)

            async def guarded_stream():
                try:
                    async for chunk in stream_file(file_path):
                        yield chunk
                finally:
                    limiter.release(client_ip, token)

            # Return the file stream
            return StreamingResponse(
                content=guarded_stream(),
                headers=headers,
                media_type=media_type,
            )

        # If the file wasn’t found, return a standard 404 Not Found
        return PlainTextResponse('Not Found', status_code=404)

    return endpoint


def make_index_endpoint(server_route: str, access: File) -> Callable:
    """
    Create an endpoint that renders the root index page for a server.

    Subroutes whose share directory is missing or completely empty are omitted.
    """
    async def index_endpoint(request: Request) -> Response:
        present = [
            (subroute, share)
            for subroute, share, _ in SUBROUTES
            if await access.list_dir(share)
        ]
        return HTMLResponse(
            render_server_index(server_route, present),
            status_code=200,
            headers=LISTING_HEADERS,
        )

    return index_endpoint


def make_routes(servers: List[Server], limiter: DownloadLimiter) -> List[Route]:
    """
    Create routes for a group of servers sharing the same route.

    All servers in the group are merged into a single route that resolves
    files by falling through each server's search paths in configuration order.
    """
    route = servers[0].route
    access = File([(server.path_base, server.path_mapping) for server in servers])

    if not access.searchpaths:
        logger.warning("Skipping route %s: no valid server roots", route)
        return []

    return [
        Route(
            path=route,
            endpoint=make_index_endpoint(route, access),
            methods=['GET'],
        ),
        Route(
            path=f"{route}/",
            endpoint=make_index_endpoint(route, access),
            methods=['GET'],
        ),
        Mount(
            path=route,
            routes=[
                Route(
                    path=f"{subroute}",
                    endpoint=make_endpoint(route, share, subroute, access, predicate, limiter),
                    methods=['GET', 'HEAD'],
                )
                for subroute, share, predicate in SUBROUTES
            ]
            + [
                Route(
                    path=f"{subroute}/{{path:path}}",
                    endpoint=make_endpoint(route, share, subroute, access, predicate, limiter),
                    methods=['GET', 'HEAD'],
                )
                for subroute, share, predicate in SUBROUTES
            ],
        ),
    ]


def display_subroutes() -> None:
    """
    Display the configured subroutes in a human-readable format.
    """
    print("\nConfigured subroutes:")
    for subroute, share, predicate in SUBROUTES:
        print(f"  - subroute: {subroute}")
        print(f"    share: {share}")
        print(f"    predicate: {predicate}")
