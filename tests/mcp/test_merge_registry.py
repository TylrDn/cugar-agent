import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "mcp-foundation" / "scripts" / "merge_registry.py"


def load_merge_module():
    spec = importlib.util.spec_from_file_location("merge_registry", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


merge_registry = load_merge_module()


def test_duplicate_mcp_servers_raise(tmp_path):
    frag1 = tmp_path / "a.yaml"
    frag1.write_text("mcpServers:\n  demo: {}\nservices: []\n", encoding="utf-8")
    frag2 = tmp_path / "b.yaml"
    frag2.write_text("mcpServers:\n  demo: {}\nservices: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"Duplicate mcpServers entry 'demo' found in .*a.yaml and .*b.yaml"):
        merge_registry.merge_fragments([frag1, frag2])


def test_duplicate_services_raise(tmp_path):
    frag1 = tmp_path / "a.yaml"
    frag1.write_text("services:\n  - svc: {}\nmcpServers: {}\n", encoding="utf-8")
    frag2 = tmp_path / "b.yaml"
    frag2.write_text("services:\n  - svc: {}\nmcpServers: {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"Duplicate service entry 'svc' found in .*a.yaml and .*b.yaml"):
        merge_registry.merge_fragments([frag1, frag2])


def test_fragment_paths_resolve_relative_to_profile(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "configurations" / "profiles"
    fragments_dir = profiles_dir / "fragments"
    fragments_dir.mkdir(parents=True)

    fragment = fragments_dir / "fragment.yaml"
    fragment.write_text("mcpServers:\n  alpha: {}\nservices: []\n", encoding="utf-8")

    profile_file = profiles_dir / "demo.toml"
    profile_file.write_text(
        """
[profiles.demo]
fragments = ["./fragments/fragment.yaml"]
output = "./build/out.yaml"
""",
        encoding="utf-8",
    )

    profile, profile_path = merge_registry.load_profile("demo", profiles_dir)
    monkeypatch.chdir(tmp_path / "unrelated")
    (tmp_path / "unrelated").mkdir(exist_ok=True)

    fragment_paths = [
        Path(path) if Path(path).is_absolute() else profile_path.parent / path for path in profile["fragments"]
    ]
    merged = merge_registry.merge_fragments(fragment_paths)
    assert "alpha" in merged["mcpServers"]


def test_yaml_error_surfaces_filename(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("mcpServers: [unclosed\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc:
        merge_registry.merge_fragments([bad])
    assert "Invalid YAML in" in str(exc.value)
    assert "bad.yaml" in str(exc.value)


def test_langflow_generation_from_profile(tmp_path):
    base = tmp_path / "base.yaml"
    base.write_text("mcpServers: {}\nservices: []\n", encoding="utf-8")

    merged = merge_registry.merge_fragments(
        [base], langflow_prod_projects={"trading": "${LF_TRADING_PROJECT_ID}"}
    )

    servers = merged["mcpServers"]
    assert "langflow_trading" in servers
    args = servers["langflow_trading"]["args"]
    assert "${LF_API_KEY:?LF_API_KEY is required for prod services}" in args
    assert any("${LF_TRADING_PROJECT_ID}" in arg for arg in args)
