import pytest

from cuga.mcp_servers.crypto_wallet import server


def test_crypto_generate_and_sign(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    gen = server._handle({"method": "operate", "params": {"operation": "generate_mnemonic", "params": {"seed": 5}}})
    mnemonic = gen["result"]["data"]["mnemonic"]
    assert isinstance(mnemonic, str)
    derived = server._handle({"method": "operate", "params": {"operation": "derive_address", "params": {"mnemonic": mnemonic}}})
    assert derived["result"]["data"]["address"].startswith("0x")
    signature = server._handle({"method": "operate", "params": {"operation": "sign_message", "params": {"mnemonic": mnemonic, "message": "hi"}}})
    assert len(signature["result"]["data"]["signature"]) > 0


def test_crypto_invalid_operation(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    with pytest.raises(server.RequestError):
        server._handle({"method": "operate", "params": {"operation": "unknown", "params": {}}})
