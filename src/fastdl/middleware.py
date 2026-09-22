from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.types import Scope, Receive, Send


class SecurityHeadersMiddleware:
    """
    Middleware that adds hardening response headers to every HTTP response.
    """

    def __init__(self, app: callable):
        """
        Initialize the middleware with the ASGI app.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """
        Intercept outgoing HTTP responses and inject security headers.
        """
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                headers['x-content-type-options'] = 'nosniff'
                headers['referrer-policy'] = 'no-referrer'
                headers['x-frame-options'] = 'DENY'
            await send(message)

        await self.app(scope, receive, send_wrapper)


class PathSanitizeMiddleware:
    """
    Middleware to sanitize incoming request paths by removing path traversal components
    (e.g., '..') and normalizing the path.
    """

    def __init__(self, app: callable):
        """
        Initialize the middleware with the ASGI app.
        """
        self.app = app

    @staticmethod
    def sanitize(path: str) -> str:
        """
        Sanitize the given path by normalizing it and removing path traversal components.
        """
        # Treat backslashes as path separators so they cannot be used to bypass sanitization
        path = path.replace('\\', '/')
        parts = path.split('/')

        # This list will collect the sanitized path segments
        cleaned_parts = []

        for part in parts:
            # Skip empty segments or “.” (current directory)
            if part in ('', '.'):
                continue
            # Handle “..” (parent directory): pop the last cleaned segment if any
            elif part == '..':
                if cleaned_parts:
                    cleaned_parts.pop()
            # Otherwise, this is a normal path segment—keep it
            else:
                cleaned_parts.append(part)

        # If the original path ended with a slash, preserve that trailing slash
        if path.endswith('/'):
            cleaned_parts.append('')

        # Rebuild the normalized path, ensuring it always starts with a “/”
        return '/' + '/'.join(cleaned_parts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """
        Intercept incoming HTTP requests, sanitize the path, and redirect if necessary.
        """
        if scope['type'] != 'http':
            # Pass non-HTTP requests to the next middleware or app
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive, send)

        # Sanitize the request path
        cleaned_path = self.sanitize(request.url.path)

        # Redirect if the sanitized path differs from the original
        if cleaned_path != request.url.path:
            url = request.url.replace(path=cleaned_path)
            response = RedirectResponse(url, status_code=307)
            await response(scope, receive, send)
            return

        # Proceed with the next middleware or app
        await self.app(scope, receive, send)
