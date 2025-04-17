import os
from functools import partial

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route

from .cache import FileCache
from .configuration import configuration
from .middleware import PathSanitizeMiddleware
from .routes import ROUTES


async def base_endpoint(request: Request, *, share, access, predicate):
    path = os.path.join(share, request.path_params['path'])
    if not predicate(path):
        return Response(status_code=422)
    elif file := await access(path):
        return FileResponse(file)
    else:
        return PlainTextResponse('Not Found', status_code=404)

routes = []

for server in configuration['servers']:
    route = server['route']
    path_base = server['path_base']
    path_mapping = server['path_mapping']

    cache = FileCache(path_base, path_mapping)

    subroutes = []

    for prefix, share, predicate in ROUTES:
        endpoint = partial(
            base_endpoint,
            share=share,
            access=cache.access,
            predicate=predicate,
        )

        subroutes.append(Route(
            path=prefix + r'/{path:path}',
            endpoint=endpoint,
            methods=['GET', 'HEAD'],
        ))

    routes.append(Mount(route, routes=subroutes))


middleware = [
    Middleware(PathSanitizeMiddleware),
]

application = Starlette(
    routes=routes,
    middleware=middleware
)

application = CORSMiddleware(
    app=application,
    allow_origins=['*'],
    allow_methods=['GET', 'HEAD']
)
