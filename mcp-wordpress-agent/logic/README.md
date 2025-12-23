# WordPress Subagent Logic

## Purpose
Handle content creation and publishing tasks for WordPress properties with strict isolation from other domains.

## Enrolled Tools
- `wordpress__post_fetch` (read-only): Retrieve posts or pages for review.
- `wordpress__post_draft` (write with dry-run): Create drafts while keeping `dry_run` enabled by default.
- `wordpress__post_publish` (write): Publish approved drafts after human confirmation.

## Prompt Examples
- "Fetch the latest draft posts tagged 'product-release' and summarize status."
- "Create a draft announcing the new trading feature; mark it as requiring editorial approval."
- "With approval, publish the draft titled 'Q3 highlights' and report the permalink."

## Guardrails & HITL Policies
- All write actions require human approval; drafts should remain in `draft` state until explicitly promoted.
- Tool descriptions must highlight side effects and indicate `read-only` vs `write` tags.
- Authentication flows should rely on proxied headers and environment variables—no secrets in registry fragments.
- Enable rollback-friendly parameters like `dry_run` and keep detailed yet redacted invocation logs.
