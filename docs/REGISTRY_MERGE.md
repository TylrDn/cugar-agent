
# 🧩 Registry Merge Semantics

This document explains how agent **tool registries are assembled** from YAML profile fragments using the merge logic in:

```
mcp-foundation/scripts/merge_registry.py
```

This script powers all registry generation via `make profile-*`.

---

## 📁 Path Resolution

- All fragment paths are resolved **relative to the profile YAML file** that declares them (not the shell’s working directory).
- The `--profiles-dir` flag defaults to:
  ```
  ./configurations/profiles/
  ```
- The loader **returns the resolved profile path**, enabling absolute resolution of fragments.

📌 This makes builds **profile-portable** and robust in dev/prod environments.

---

## 🧱 Conflict Detection

- Duplicate `mcpServers` keys or service names across any fragments will cause the **merge step to fail**.
- The error includes:
  - The **conflicting key**
  - The two **source file paths**
- Legacy Langflow prod fragments are allowed temporarily, but:
  - Emit a **deprecation warning**
  - Must not conflict with new templated projects

---

## ✅ YAML Validation

All fragments are parsed with `yaml.safe_load`.

On failure:
- A `ValueError` is raised
- The error includes the file name
- Parser-provided context (e.g. line number, bad indentation) is included when available

**Examples of fatal YAML issues**:
- Tabs instead of spaces
- Trailing commas
- Misaligned keys

---

## 🧠 Langflow Templating

Profiles can declare templated Langflow projects like:

```toml
[profiles.trading.langflow_prod_projects]
analytics = "${LF_ANALYTICS_PROJECT_ID}"
trading = "${LF_TRADING_PROJECT_ID}"
```

During registry merge:
- Each mapping produces a `langflow_<project>` entry
- Entries include:
  - **Hardened API key checks**
  - Proxy-based invocation
  - Langflow config setup

🚨 Legacy `langflow_prod.yaml` fragments may co-exist temporarily, but should be **phased out** to remove deprecation warnings.

---

## 🔐 Environment Variable Hardening

Langflow prod services enforce secret presence like:

```bash
${LF_API_KEY:?LF_API_KEY is required for prod services}
```

If not set, the shell will:
- Exit immediately
- Output a readable error

🧪 Test locally using:

```bash
make env-dev
source .env.mcp
```

---

## 🛠️ Troubleshooting

| Problem | Resolution |
|--------|------------|
| **❌ Duplicate key error** | Remove or rename conflicting `mcpServers` or `tools` fragments. |
| **❌ Invalid YAML** | Fix indentation or structure. Look at the file path and error line in traceback. |
| **❌ Missing fragment** | Ensure all fragment paths are correct **relative to the profile file**. |
| **❌ Deprecated Langflow entry** | Migrate to `[profiles.*.langflow_prod_projects]` in TOML. |

---

## 📘 Related Docs

- `AGENTS.md` – contributor onboarding + pipeline flow
- `TOOLS.md` – how tools are defined and registered
- `SECURITY.md` – safe secret handling in fragments

---

🔁 Return to [Agents.md](../AGENTS.md)
