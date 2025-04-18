from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount

from .configuration import configure, display_configuration
from .middleware import PathSanitizeMiddleware
from .routes import display_subroutes, make_subroutes


@asynccontextmanager
async def lifespan(app: Starlette):
    configuration = configure()

    for server in configuration.servers:
        app.router.routes.append(Mount(
            path=server.route,
            routes=make_subroutes(server.path_base, server.path_mapping),
        ))

    display_configuration(configuration)
    display_subroutes()

    yield

middleware = [
    Middleware(PathSanitizeMiddleware),
]

application = Starlette(
    lifespan=lifespan,
    middleware=middleware,
)

application = CORSMiddleware(
    app=application,
    allow_origins=['*'],
    allow_methods=['GET', 'HEAD'],
)
