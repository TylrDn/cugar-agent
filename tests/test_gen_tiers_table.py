import textwrap

from build.gen_tiers_table import extract_auth_env, render_table, tier_key


def test_extract_auth_env_parses_embedded_vars():
    env_map = {
        "A": "${TOKEN:?}",
        "B": "prefix-${API_KEY:?}-suffix",
        "C": None,
    }
    assert extract_auth_env(env_map) == ["API_KEY", "TOKEN"]


def test_tier_sorting_prefers_lower_tier_then_alpha():
    entries = [
        {"id": "b", "name": "Bravo", "tier": 2},
        {"id": "a", "name": "Alpha", "tier": 1},
        {"id": "c", "name": "Charlie", "tier": 1},
    ]
    sorted_ids = [e["id"] for e in sorted(entries, key=tier_key)]
    assert sorted_ids == ["a", "c", "b"]


def test_render_table_handles_empty_fields():
    entries = [
        {
            "id": "sample",
            "name": "Sample",
            "tier": 1,
            "enabled": False,
            "env": {},
            "mounts": [],
        }
    ]
    table = render_table(entries)
    assert "- |" in table  # empty env renders '-'
    assert "disabled" in table
