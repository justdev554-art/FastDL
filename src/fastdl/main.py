from contextlib import asynccontextmanager

import anyio.to_thread
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from .configuration import configure, display_configuration
from .middleware import PathSanitizeMiddleware
from .routes import display_subroutes, make_routes


@asynccontextmanager
async def lifespan(app: Starlette):
    configuration = configure()

    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = configuration.max_threads

    for server in configuration.servers:
        app.router.routes.append(make_routes(server))

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
