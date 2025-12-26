from __future__ import annotations

from typing import Any, Callable, Dict


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: Any = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def Header(default=None):
    return default


class FastAPI:
    def __init__(self, title: str | None = None):
        self.title = title
        self.routes: Dict[str, Callable] = {}
        self.middleware_fn = None

    def get(self, path: str):
        def decorator(fn: Callable):
            self.routes[("GET", path)] = fn
            return fn
        return decorator

    def post(self, path: str):
        def decorator(fn: Callable):
            self.routes[("POST", path)] = fn
            return fn
        return decorator

    def middleware(self, _):
        def decorator(fn: Callable):
            self.middleware_fn = fn
            return fn
        return decorator

    async def _call(self, method: str, path: str, payload: Any, headers: Dict[str, str]):
        handler = self.routes.get((method, path))
        if not handler:
            raise HTTPException(status_code=404, detail="not found")
        if self.middleware_fn:
            async def call_next(request):
                return await _invoke(handler, payload, headers)
            response = await self.middleware_fn(SimpleRequest(headers), call_next)
            return response
        return await _invoke(handler, payload, headers)


async def _invoke(handler, payload: Any, headers: Dict[str, str]):
    if getattr(handler, "__name__", "").startswith("health"):
        return await handler()
    return await handler(payload, x_trace_id=headers.get("X-Trace-Id"))


class SimpleRequest:
    def __init__(self, headers: Dict[str, str]):
        self.headers = headers


class Response:
    def __init__(self, content: Any, status_code: int = 200, headers: Dict[str, str] | None = None):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}


from .responses import JSONResponse, StreamingResponse  # noqa: E402
