# Registry Merge Semantics

This repository uses `mcp-foundation/scripts/merge_registry.py` to assemble the MCP registry from profile fragments.

## Path resolution
- Fragment paths are resolved relative to the profile file that declares them, not the shell's current working directory.
- The `--profiles-dir` flag defaults to `./configurations/profiles`; the loader returns the resolved profile path so orchestrators can build absolute fragment paths from that location.

## Conflict detection
- Duplicate `mcpServers` keys or service names across fragments cause the merge step to fail with a clear error listing the colliding key and both source files.
- Legacy Langflow prod fragments are allowed but emit a deprecation warning if they overlap with templated `langflow_prod_projects` entries.

## YAML validation
- YAML fragments are parsed with `yaml.safe_load`. Invalid YAML raises `ValueError` with the filename (and parser-provided context if available) to speed up debugging.

## Langflow templating
- Profiles can declare `[profiles.<name>.langflow_prod_projects]` to map project names to environment variable tokens (for example `trading = "${LF_TRADING_PROJECT_ID}"`).
- During merging, each mapping produces a `langflow_<project>` entry with the hardened API key guard and proxy invocation. Backwards-compatible prod fragments can remain temporarily but should be removed to silence the deprecation warning.

## Environment variables and hardening
- Production Langflow entries enforce a non-empty API key with shell parameter expansion: `${LF_API_KEY:?LF_API_KEY is required for prod services}`.

## Troubleshooting
- **Duplicate key error**: Remove or rename conflicting fragment entries; check the error message for the pair of files involved.
- **Invalid YAML**: Fix indentation or structure in the path listed in the error. The message includes any line hints available from the parser.
- **Missing fragment**: Ensure fragment paths are correct relative to the profile file (see the Path resolution section above).
