from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

import requests

from cuga.mcp_servers._shared import RequestError, get_sandbox, run_main


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
    url_val = url if isinstance(url, str) else None
    html_val = html if isinstance(html, str) else None
    if not url_val and not html_val:
        raise RequestError("'url' or 'html' is required", details={"fields": ["url", "html"]})
    _ = get_sandbox()

    try:
        article = _extract_with_newspaper(
            url_val,
            html_val,
            language if isinstance(language, str) else None,
            timeout_ms if isinstance(timeout_ms, int) else None,
        )
    except RequestError as exc:
        fallback_allowed = exc.type in {"missing_dependency", "network", "bad_request"}
        if not fallback_allowed or html_val is None:
            if exc.type == "missing_dependency" and html_val is None:
                raise RequestError(
                    "newspaper4k dependency is required when only 'url' is provided",
                    type_="missing_dependency",
                    details={"fields": ["url"], "hint": "Provide 'html' to use fallback parser."},
                ) from exc
            raise
        extractor = _SimpleHTMLExtractor()
        extractor.feed(html_val)
        article = extractor.result()
    except (requests.RequestException, TimeoutError, ConnectionError, ValueError) as exc:
        if html_val is None:
            raise
        extractor = _SimpleHTMLExtractor()
        extractor.feed(html_val)
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
    run_main(_handle)


if __name__ == "__main__":
    main()
