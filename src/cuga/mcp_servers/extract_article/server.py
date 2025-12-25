from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional


class RequestError(Exception):
    def __init__(self, message: str, *, type_: str = "bad_request", details: Dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.type = type_
        self.details = details or {}


@dataclass
class ArticleResult:
    title: Optional[str]
    authors: List[str]
    publish_date: Optional[str]
    text: str
    top_image: Optional[str]
    keywords: List[str]
    summary: Optional[str]


class _SimpleHTMLExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self._texts: List[str] = []
        self.title_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: D401
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        content = data.strip()
        if not content:
            return
        if self._in_title:
            self.title_parts.append(content)
        self._texts.append(content)

    def result(self) -> ArticleResult:
        title = " ".join(self.title_parts) if self.title_parts else None
        body = " ".join(self._texts).strip()
        return ArticleResult(
            title=title,
            authors=[],
            publish_date=None,
            text=body,
            top_image=None,
            keywords=[],
            summary=None,
        )


def _get_sandbox() -> str:
    sandbox = os.getenv("CUGA_PROFILE_SANDBOX")
    if not sandbox:
        raise RequestError("CUGA_PROFILE_SANDBOX is required for sandboxed execution", type_="missing_env")
    return sandbox


def _load_payload() -> Dict[str, Any]:
    if "--json" in sys.argv:
        try:
            idx = sys.argv.index("--json") + 1
            return json.loads(sys.argv[idx])
        except Exception as exc:  # noqa: BLE001
            raise RequestError("Invalid JSON payload", details={"error": str(exc)}) from exc
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise RequestError("Invalid JSON payload", details={"error": str(exc)}) from exc


def _extract_with_newspaper(url: Optional[str], html: Optional[str], language: Optional[str], timeout_ms: Optional[int]) -> ArticleResult:
    try:
        from newspaper import Article  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RequestError("newspaper4k is not available", type_="missing_dependency", details={"error": str(exc)}) from exc

    article = Article(url if url else "http://localhost", language=language)
    if timeout_ms:
        try:
            article.config.request_timeout = timeout_ms / 1000.0
        except Exception:  # noqa: BLE001
            pass
    if html:
        article.set_html(html)
    else:
        try:
            article.download()
        except Exception as exc:  # noqa: BLE001
            raise RequestError("Failed to download article", type_="network", details={"error": str(exc)}) from exc
    try:
        article.parse()
    except Exception as exc:  # noqa: BLE001
        raise RequestError("Failed to parse article", details={"error": str(exc)}) from exc

    summary = None
    keywords: list[str] = []
    try:
        article.nlp()
        summary = getattr(article, "summary", None)
        keywords = getattr(article, "keywords", []) or []
    except Exception:
        summary = None
        keywords = []
    publish_date = None
    date_val = getattr(article, "publish_date", None)
    if date_val:
        try:
            publish_date = date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val)
        except Exception:  # noqa: BLE001
            publish_date = None
    return ArticleResult(
        title=getattr(article, "title", None),
        authors=getattr(article, "authors", []) or [],
        publish_date=publish_date,
        text=getattr(article, "text", ""),
        top_image=getattr(article, "top_image", None),
        keywords=keywords,
        summary=summary,
    )


def _extract_article(params: Dict[str, Any]) -> Dict[str, Any]:
    url = params.get("url")
    html = params.get("html")
    language = params.get("language")
    timeout_ms = params.get("timeout_ms")
    if not url and not html:
        raise RequestError("'url' or 'html' is required", details={"fields": ["url", "html"]})
    _ = _get_sandbox()

    try:
        article = _extract_with_newspaper(
            url if isinstance(url, str) else None,
            html if isinstance(html, str) else None,
            language if isinstance(language, str) else None,
            timeout_ms if isinstance(timeout_ms, int) else None,
        )
    except RequestError as exc:
        if exc.type != "missing_dependency":
            raise
        extractor = _SimpleHTMLExtractor()
        extractor.feed(html or "")
        article = extractor.result()
    except Exception:  # noqa: BLE001
        extractor = _SimpleHTMLExtractor()
        extractor.feed(html or "")
        article = extractor.result()
    return {"article": asdict(article)}


def _handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    method = payload.get("method")
    params = payload.get("params", {}) if isinstance(payload.get("params", {}), dict) else {}
    if method == "health":
        return {"ok": True, "result": {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}}
    if method != "extract":
        raise RequestError("Unsupported method", details={"method": method})
    result = _extract_article(params)
    return {"ok": True, "result": result, "meta": {"tool": "extract_article"}}


def main() -> None:
    try:
        payload = _load_payload()
        response = _handle(payload)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
    except RequestError as exc:
        error_body = {"ok": False, "error": {"type": exc.type, "message": str(exc), "details": exc.details}}
        sys.stdout.write(json.dumps(error_body) + "\n")
        sys.stdout.flush()
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        error_body = {"ok": False, "error": {"type": "unexpected", "message": str(exc)}}
        sys.stdout.write(json.dumps(error_body) + "\n")
        sys.stdout.flush()
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
