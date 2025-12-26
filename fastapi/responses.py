from __future__ import annotations

from typing import Any, AsyncIterator, Dict


class JSONResponse:
    def __init__(self, content: Any, status_code: int = 200, headers: Dict[str, str] | None = None):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}


class StreamingResponse:
    def __init__(self, iterator: AsyncIterator[bytes], media_type: str = "text/plain"):
        self.iterator = iterator
        self.status_code = 200
        self.media_type = media_type
        self.headers: Dict[str, str] = {}

    async def iter_bytes(self) -> AsyncIterator[bytes]:
        async for chunk in self.iterator:
            yield chunk
