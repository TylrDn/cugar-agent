# WordPress HITL & Approval Policy

- **Drafting**: All new content must be created via `wordpress__post_draft` with `dry_run=true` unless a human explicitly toggles it off.
- **Review workflow**: Drafts require editorial review for tone, branding, and legal compliance before publication.
- **Publishing**: `wordpress__post_publish` cannot run without an affirmative approval signal that captures approver identity and timestamp.
- **Rollback**: Provide a rollback or unpublish strategy for every publish action and log the resulting permalink/reference.
- **Data handling**: Strip PII from prompts and responses; only store minimal metadata needed for audit trails.
- **Credentials**: Use header-based tokens injected at runtime; never store passwords or tokens in YAML or prompts.
