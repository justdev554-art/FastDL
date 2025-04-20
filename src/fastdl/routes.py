import bz2
import os
from mimetypes import guess_type
from typing import List, Tuple, Callable

from anyio import open_file, to_thread
from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse, Response
from starlette.routing import Route, Mount

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
            media_type = guess_type(file_path)[0] or "application/octet-stream"
            # Return the file with the correct content type
            return FileResponse(file_path, media_type=media_type, stat_result=stat_result)
        
        if url_path.endswith('.bz2') and (pair := await access(url_path[:-4])):
            file_path, stat_result = pair
            if stat_result.st_size < compress_max_size:
                async with await open_file(file_path, mode="rb") as file:
                    data = await file.read()
                compressed_data = await to_thread.run_sync(bz2.compress, data)
                return Response(compressed_data, media_type='application/x-bzip2')

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
