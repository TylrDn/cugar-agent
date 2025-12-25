# Branch Cleanup, Rebase, and Outstanding Issue Requests

This repository currently has a single local branch (`work`) and no configured remotes. The steps below describe how to rebase, merge, and clean up Codex-generated branches when they exist, followed by ready-to-file issue requests for remaining gaps.

## Rebase and Merge Workflow
1. **Fetch all branches**
   - `git remote add origin <git@github.com:TylrDn/cugar-agent.git>` (if not already configured).
   - `git fetch --all --prune` to surface remote Codex branches.
2. **Inspect Codex branches**
   - `git branch -r | grep codex/` to list automation-created branches.
3. **Rebase in date order**
   - Checkout each Codex branch in chronological order and rebase onto `main` (or `work` if `main` is absent):
     - `git checkout codex/<branch>`
     - `git rebase main` (or `work`)
     - Resolve conflicts, ensuring registry and profile files remain deterministic and isolated.
4. **Merge after validation**
   - Run `make test` (or targeted suites) before merging.
   - Merge back via fast-forward where possible: `git checkout main && git merge --ff-only codex/<branch>`.
5. **Delete merged branches**
   - Local: `git branch -d codex/<branch>`
   - Remote: `git push origin --delete codex/<branch>`
6. **Update CHANGELOG and tags**
   - Add entries under the appropriate version section using the mandated emoji prefixes.
   - Tag after merges if a release is cut.

## Outstanding Issue Requests
Use the templates below to open GitHub issues for work that remains after consolidation:

1. **CLI Runner Test Scaffolding**
   - _Summary_: Build automated tests for the CLI runner to prevent regressions noted in current gaps.
   - _Acceptance Criteria_: Coverage for basic invocation, JSON export, and error handling paths.

2. **Tool Schema Validation Contract**
   - _Summary_: Strengthen schema validation for tool inputs/outputs to enforce stricter contracts across profiles.
   - _Acceptance Criteria_: Validation layer with unit tests and documented failure modes.

3. **Logging Verbosity Defaults**
   - _Summary_: Harden logging defaults to avoid excessive verbosity in production runs.
   - _Acceptance Criteria_: Sensible defaults, CLI flags to override, and updated docs.

4. **CI and Coverage Enablement**
   - _Summary_: Add GitHub Actions for tests and coverage reports to guard against regression when merging Codex branches.
   - _Acceptance Criteria_: Passing CI workflow with coverage publication.

5. **Langflow Project Inspector**
   - _Summary_: Implement the Langflow project inspection tooling referenced in `vNext` to aid profile validation.
   - _Acceptance Criteria_: CLI or script that validates Langflow project assets with tests and documentation.

6. **MCP Tool Hardening Follow-ups**
   - _Summary_: Track any remaining edge cases for the new MCP tools (`scrape_tweets`, `extract_article`, `crypto_wallet`, `moon_agents`, `vault_tools`) introduced in `vNext`.
   - _Acceptance Criteria_: Issue-specific checklists for error handling, dependency management, and sandbox isolation per tool.

These issue stubs can be pasted into GitHub to keep the backlog synchronized after branch cleanup.
