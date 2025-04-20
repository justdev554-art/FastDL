import bz2
import os
from mimetypes import guess_file_type
from typing import AsyncGenerator, Callable, List, Tuple

from aiofile import AIOFile
from anyio import open_file, to_thread
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response, StreamingResponse
from starlette.routing import Mount, Route

from fastdl.configuration import Server
from fastdl.file import File


class Suffix:
    """
    A predicate class to check if a file path ends with specific extensions.
    """
    def __init__(self, *extensions: str):
        self.extensions = extensions + tuple(f"{ext}.bz2" for ext in extensions)

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
    (r'/sound',         r'sound',         Suffix('.mp3', '.wav')),
]

CHUNK_SIZE = 64 * 1024  # 64 KiB

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

def make_endpoint(server: Server, share: str, access: File, predicate: Callable[[str], bool]) -> Callable:
    """
    Create an endpoint for serving files based on a share path and predicate.
    """
    compress_max_size = server.compress_max_size

    async def endpoint(request: Request) -> Response:
        # Build the target path by joining the share directory with the requested subpath
        url_path = os.path.join(share, request.path_params['path'])

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


def make_routes(server: Server) -> List[Route]:
    """
    Create routes based on the base path, mapping, and predefined subroutes.
    """
    access = File(server.path_base, server.path_mapping)

    return Mount(
        path=server.route,
        routes=[
            Route(
                path=f"{subroute}/{{path:path}}",
                endpoint=make_endpoint(server, share, access, predicate),
                methods=['GET', 'HEAD'],
            )
            for subroute, share, predicate in SUBROUTES
        ]
    )


def display_subroutes() -> None:
    """
    Display the configured subroutes in a human-readable format.
    """
    print("\nConfigured subroutes:")
    for subroute, share, predicate in SUBROUTES:
        print(f"  - subroute: {subroute}")
        print(f"    share: {share}")
        print(f"    predicate: {predicate}")
