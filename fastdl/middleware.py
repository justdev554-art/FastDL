from starlette.requests import Request
from starlette.responses import RedirectResponse


class PathSanitizeMiddleware:
    def __init__(self, app):
        self.app = app

    @staticmethod
    def sanitize(path: str) -> str:
        parts = path.split('/')
        parts.reverse()

        cleaned_parts, depth = [], 0

        if parts and parts[0] in ('', '.'):
            cleaned_parts.append('')

        for part in parts:
            if part in ('', '.'):
                continue
            elif part == '..':
                depth += 1
            elif depth:
                depth -= 1
            else:
                cleaned_parts.append(part)

        cleaned_parts.reverse()

        return '/' + '/'.join(cleaned_parts)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive, send)

        cleaned_path = self.sanitize(request.url.path)
        if cleaned_path != request.url.path:
            url = request.url.replace(path=cleaned_path)
            response = RedirectResponse(url, status_code=307)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
