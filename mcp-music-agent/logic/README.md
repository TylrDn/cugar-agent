# Music Subagent Logic

## Purpose
Manage music discovery, recommendations, and playlist workflows with isolated tool packs.

## Enrolled Tools
- `music__search_catalog` (read-only): Query catalog metadata by artist, track, or genre.
- `music__playlist_propose` (read-only): Generate playlist drafts for human review.
- `music__playlist_publish` (write): Publish approved playlists to downstream targets with `dry_run` available.

## Prompt Examples
- "Search the catalog for lo-fi focus tracks and summarize top five results."
- "Draft a 45-minute upbeat playlist for a morning workout; keep it read-only."
- "With approval, publish the curated playlist to the shared channel and log the publish ID."

## Guardrails & HITL Policies
- Publishing requires a human approval step and should default to `dry_run=true` until approved.
- Tool descriptions must include side-effect notes and tag `read-only` vs `write`.
- Keep credentials outside YAML; rely on environment variables passed via runtime.
- Logs should omit full track metadata when unnecessary; prefer hashed identifiers for audit trails.
