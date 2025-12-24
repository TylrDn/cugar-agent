import pytest

from cuga.mcp_servers.extract_article import server


def test_extract_article_from_html(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    html = """
    <html>
      <head><title>Sample Story</title></head>
      <body>
        <p>Hello world.</p>
        <p>Extra text.</p>
      </body>
    </html>
    """
    response = server._handle({"method": "extract", "params": {"html": html}})
    assert response["ok"] is True
    article = response["result"]["article"]
    assert article["title"] == "Sample Story"
    assert "Hello" in article["text"]


def test_extract_article_invalid(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    with pytest.raises(server.RequestError):
        server._handle({"method": "extract", "params": {}})
