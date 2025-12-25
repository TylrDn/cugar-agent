import textwrap

import yaml

from build.gen_tiers_table import _auth_env, _fs_scope, _rows, _titleize


def test_auth_env_extracts_and_dedupes():
    env = {
        "LANGFLOW_API_KEY": "${LANGFLOW_API_KEY:?}",
        "ALT": "${ALT:-default}",
        "PLAIN": "value",
    }
    assert _auth_env(env) == "ALT, LANGFLOW_API_KEY, PLAIN"


def test_rows_sorted_by_tier_then_tool():
    registry = yaml.safe_load(
        textwrap.dedent(
            """
            defaults:
              tier: 1
              env: {}
              mounts: []
            entries:
              - id: b.tool
                enabled: true
              - id: a.tool
                enabled: true
              - id: opt.tool
                tier: 2
                enabled: false
            """
        )
    )
    rows = _rows(registry)
    assert [r["id"] for r in rows] == ["a.tool", "b.tool", "opt.tool"]


def test_empty_fields_render_none():
    assert _fs_scope([]) == "none"
    assert _auth_env({}) == "none"
    assert _titleize("mcp.fs") == "Mcp Fs"
