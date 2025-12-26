from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict

from . import HTTPException


class _Response:
    def __init__(self, status_code: int, json_data: Any = None, content: Any = None, headers: Dict[str, str] | None = None):
        self.status_code = status_code
        self._json = json_data or content
        self._content = content if content is not None else json_data
        self.headers = headers or {}

    def json(self):
        return self._json

    def iter_text(self):
        if isinstance(self._content, (bytes, str)):
            return self._content if isinstance(self._content, str) else self._content.decode()
        return ""


class TestClient:
    def __init__(self, app):
        self.app = app

    def _run(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    async def _collect_stream(self, stream: AsyncIterator[bytes]):
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
        return chunks

    def get(self, path: str, headers: Dict[str, str] | None = None):
        headers = headers or {}
        try:
            result = self._run(self.app._call("GET", path, {}, headers))
        except HTTPException as exc:
            return _Response(exc.status_code, json_data={"detail": exc.detail})
        return _Response(getattr(result, "status_code", 200), json_data=getattr(result, "content", result), headers=getattr(result, "headers", {}))

    def post(self, path: str, headers: Dict[str, str] | None = None, json: Any | None = None):
        headers = headers or {}
        try:
            result = self._run(self.app._call("POST", path, json or {}, headers))
        except HTTPException as exc:
            return _Response(exc.status_code, json_data={"detail": exc.detail})
        if hasattr(result, "iter_bytes"):
            stream = result.iter_bytes()
            chunks = self._run(self._collect_stream(stream))
            return _Response(getattr(result, "status_code", 200), content=b"".join(chunks), headers=result.headers)
        return _Response(getattr(result, "status_code", 200), json_data=getattr(result, "content", result), headers=getattr(result, "headers", {}))
