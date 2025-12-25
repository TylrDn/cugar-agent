# Profile Policy Enforcement

CUGAR agents use **profile-scoped policies** to decide which tools can run and what shape their inputs and metadata must take. Policies live in `configurations/policies/` and are resolved by profile name (for example, `demo.yaml` for the `demo` profile). If no profile-specific file is found, the framework falls back to `default.yaml`.

## File layout

Each policy file is plain YAML with the following top-level keys:

- `profile`: Optional name override for documentation.
- `summary`: Free-form description for human readers.
- `allow_unknown_tools`: When `false`, any tool not listed in `allowed_tools` is rejected.
- `metadata_schema`: Optional JSON-Schema-inspired map describing expected metadata for every step.
- `allowed_tools`: Map of tool name to validation rules.
  - `input_schema`: Schema applied to the step `input` payload.
  - `metadata_schema`: Optional override for metadata validation specific to the tool.

Schema fragments understand a subset of JSON Schema keywords:

- `required`: List of field names that must be present.
- `properties`: Map of field name to `type` (one of `string`, `integer`, `number`, `boolean`, `object`, `array`, `null`).
- `additionalProperties`: When `false`, fields outside `properties` are rejected.

## Templates

Two starter templates are included to make authoring easier:

- `default.yaml`: Permissive baseline that allows any tool and demonstrates how to document fields.
- `restricted_template.yaml`: Strict example that requires metadata and blocks tools not explicitly listed.

Copy one of the templates, rename it to match your profile (for example, `sales.yaml`), and customize `allowed_tools` to describe the payloads and metadata you expect.

## Execution flow

The `PolicyEnforcer` validates metadata inside the controller before planning begins, then validates each plan step inside the executor. Violations raise structured `PolicyViolation` errors that include the profile, tool, failure code, and validation details, ensuring disallowed tools or malformed payloads are rejected before any handler runs.
