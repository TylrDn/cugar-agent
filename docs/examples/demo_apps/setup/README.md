# CUGA Demo Setup

## Installation
```bash
uvx --from git+https://github.com/cuga-project/cuga-agent.git#subdirectory=docs/examples/demo_apps/setup create-cuga-demo [--cache] [--local]
```

## Local Development
```bash
uv run create-cuga-demo [--cache] [--local]
# or
CUGA_LOCAL=1 CUGA_SOURCE_DIR=/path/to/cuga-agent/docs/examples/demo_apps uvx --from git+https://github.com/cuga-project/cuga-agent.git#subdirectory=docs/examples/demo_apps/setup create-cuga-demo [--cache]

```
CUGA_LOCAL=1 CUGA_SOURCE_DIR=/Users/samimarreed/dev/cuga-agent/docs/examples/demo_apps uvx --from /Users/samimarreed/dev/cuga-agent/docs/examples/demo_apps/setup create-cuga-demo
```


## Environment Variables
- `CUGA_LOCAL=1` - Use local demo apps instead of git installs
- `CUGA_SOURCE_DIR=/path/to/demo_apps` - Path to the demo_apps directory (when running from uvx temp directory)
