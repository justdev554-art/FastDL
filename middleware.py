from starlette.responses import RedirectResponse


class PathSanitizeMiddleware:
    def __init__(self, app):
        self.app = app

    @staticmethod
    def sanitize(path: str) -> str:
        parts = path.split('/')

        cleaned_parts = []
        for part in parts:
            if part == '':
                continue
            elif part == '.':
                continue
            elif part == '..':
                if cleaned_parts:
                    cleaned_parts.pop()
            else:
                cleaned_parts.append(part)
        if parts and part == '':
            cleaned_parts.append(part)

        return '/' + '/'.join(cleaned_parts)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        cleaned_path = PathSanitizeMiddleware.sanitize(scope['path'])
        if cleaned_path != scope['path']:
            response = RedirectResponse(cleaned_path, status_code=307)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
