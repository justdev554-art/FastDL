from functools import partial
import os
import json

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import Mount, Route

from cache import FileCache
from middleware import PathSanitizeMiddleware


def predicate_suffix(*extensions: str):
    extensions = (
        *extensions, *map(lambda extension: extension + '.bz2', extensions))

    def check(path: str):
        path = path.casefold()
        return any(map(path.endswith, extensions))
    return check


METHODS = [
    'GET',
    'HEAD',
]
ROUTES = [
    ('/maps',      'maps',      predicate_suffix('.bsp', '.nav')),
    ('/materials', 'materials', predicate_suffix('.vmt', '.vtf')),
    ('/models',    'models',    predicate_suffix('.mdl', '.phy', '.vmt', '.vtf', '.vtx', '.vvd')),
    ('/sound',     'sound',     predicate_suffix('.mp3', '.wav')),
]


async def base_endpoint(request: Request, *, share, access, predicate):
    path = os.path.join(share, request.path_params['path'])
    if not predicate(path):
        return Response(status_code=415)
    elif file := await access(path):
        return FileResponse(file)
    else:
        return Response(status_code=404)

with open('configuration.json', encoding='UTF-8') as f:
    paths = json.load(f)

routes = []

for route, (path_base, path_mapping) in paths.items():
    cache = FileCache(path_base, path_mapping)

    subroutes = []

    for prefix, share, predicate in ROUTES:
        endpoint = partial(base_endpoint, share=share, access=cache.access, predicate=predicate)

        subroutes.append(
            Route(
                path=prefix + r'/{path:path}',
                endpoint=endpoint,
                methods=METHODS,
            )
        )

    routes.append(Mount(route, routes=subroutes))


middleware = [
    Middleware(PathSanitizeMiddleware),
]

app = Starlette(
    routes=routes,
    middleware=middleware
)

app = CORSMiddleware(
    app=app,
    allow_origins=['*'],
    allow_methods=['GET', 'HEAD']
)
