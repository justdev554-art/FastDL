import bz2
import html
import os
from mimetypes import guess_file_type
from typing import AsyncGenerator, Callable, List, Tuple
from urllib.parse import quote

from aiofile import AIOFile
from anyio import open_file, to_thread
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, Response, StreamingResponse
from starlette.routing import Mount, Route

from fastdl.configuration import Server
from fastdl.file import DirEntry, File


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

def render_server_index(server_route: str) -> str:
    """
    Render the root index page listing all configured subroutes.
    """
    rows: List[str] = []
    for subroute, share, _ in SUBROUTES:
        href = _join_url(server_route, subroute)
        rows.append(
            f'<tr><td><a href="{href}/">{html.escape(subroute.strip("/"))}/</a></td>'
            f'<td class="size">{html.escape(share)}</td></tr>'
        )
    return _page(server_route, rows)

def render_directory_listing(server_route: str, subroute: str, subpath: str, entries: List[DirEntry], predicate: Callable[[str], bool]) -> str:
    """
    Render a directory listing page for the given subroute and relative path.
    """
    subpath = subpath.strip('/')
    title_parts = [part for part in (subroute, subpath) if part]
    title = '/'.join(title_parts)
    base = _join_url(server_route, subroute, subpath)

    rows: List[str] = []

    segments = [segment for segment in subpath.split('/') if segment]
    if segments:
        parent = _join_url(server_route, subroute, *segments[:-1])
        rows.append(f'<tr><td><a href="{parent}/">../</a></td><td class="size">-</td></tr>')
    else:
        rows.append(f'<tr><td><a href="/{server_route.strip("/")}/">../</a></td><td class="size">-</td></tr>')

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

async def compress_file(file_path: str, stat_result: os.stat_result) -> bytes:
    """
    Asynchronously compress a file.
    """
    async with await open_file(file_path, mode="rb") as fp, AIOFile.from_fp(fp.wrapped) as file:
        data = await file.read_bytes(stat_result.st_size)
    return await to_thread.run_sync(bz2.compress, data)

def make_endpoint(server: Server, share: str, subroute: str, access: File, predicate: Callable[[str], bool]) -> Callable:
    """
    Create an endpoint for serving files based on a share path and predicate.
    """
    compress_max_size = server.compress_max_size

    async def endpoint(request: Request) -> Response:
        # Build the target path by joining the share directory with the requested subpath
        subpath = request.path_params.get('path') or ''
        url_path = os.path.normpath(os.path.join(share, subpath))

        # If the target is a directory, present a browsable listing of it
        if request.method == 'GET' and (listing := await access.list_dir(url_path)) is not None:
            return HTMLResponse(
                render_directory_listing(server.route, subroute, subpath, listing, predicate),
                status_code=200,
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

            # Return the file stream
            return StreamingResponse(
                content=stream_file(file_path),
                headers=headers,
                media_type=media_type,
            )
        
        if url_path.endswith('.bz2') and (pair := await access(url_path[:-4])):
            file_path, stat_result = pair

            if stat_result.st_size < compress_max_size:
                if request.method == "HEAD":
                    # If the request method is HEAD, return headers only
                    return Response(
                        media_type="application/x-bzip2",
                    )

                return Response(
                    content=await compress_file(file_path, stat_result),
                    media_type="application/x-bzip2",
                )

        # If the file wasn’t found, return a standard 404 Not Found
        return PlainTextResponse('Not Found', status_code=404)

    return endpoint


def make_index_endpoint(server: Server) -> Callable:
    """
    Create an endpoint that renders the root index page for a server.
    """
    async def index_endpoint(request: Request) -> Response:
        return HTMLResponse(
            render_server_index(server.route),
            status_code=200,
        )

    return index_endpoint


def make_routes(server: Server) -> List[Route]:
    """
    Create routes based on the base path, mapping, and predefined subroutes.
    """
    access = File(server.path_base, server.path_mapping)

    return [
        Route(
            path=server.route,
            endpoint=make_index_endpoint(server),
            methods=['GET'],
        ),
        Route(
            path=f"{server.route}/",
            endpoint=make_index_endpoint(server),
            methods=['GET'],
        ),
        Mount(
            path=server.route,
            routes=[
                Route(
                    path=f"{subroute}",
                    endpoint=make_endpoint(server, share, subroute, access, predicate),
                    methods=['GET', 'HEAD'],
                )
                for subroute, share, predicate in SUBROUTES
            ]
            + [
                Route(
                    path=f"{subroute}/{{path:path}}",
                    endpoint=make_endpoint(server, share, subroute, access, predicate),
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
