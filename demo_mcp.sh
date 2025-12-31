#!/bin/bash
# MCP GitHub Demo Script
# Demonstrates loading and executing MCP tools

set -e

echo "╔══════════════════════════════════════════════════╗"
echo "║   CUGAR MCP GitHub Integration Demo            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Set PYTHONPATH
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"

echo "📦 Step 1: Loading MCP registry..."
python3 << 'PYTHON_EOF'
from cuga.tools.mcp_registry import load_mcp_manifest

manifest = load_mcp_manifest()
print(f"✓ Registry version: {manifest.version}")
print(f"✓ Total tools in registry: {len(manifest.entries)}")
print(f"✓ Tier breakdown: {manifest.get_tier_counts()}")
PYTHON_EOF

echo ""
echo "🔧 Step 2: Creating MCP toolbox (Tier 1 only)..."
python3 << 'PYTHON_EOF'
from cuga.tools.mcp_toolbox import create_mcp_toolbox

toolbox = create_mcp_toolbox(allowed_tiers=[1], deny_by_default=True)
tool_ids = toolbox.list_tool_ids()

print(f"✓ Loaded {len(tool_ids)} tools:")
for tool_id in tool_ids[:5]:  # Show first 5
    tool = toolbox.get_tool(tool_id)
    print(f"  - {tool_id} (tier {tool.tool_entry.tier}, sandbox: {tool.tool_entry.sandbox})")
if len(tool_ids) > 5:
    print(f"  ... and {len(tool_ids) - 5} more")
PYTHON_EOF

echo ""
echo "🎯 Step 3: Executing mcp.github demo..."
python3 << 'PYTHON_EOF'
from cuga.tools.mcp_toolbox import create_mcp_toolbox
import json

toolbox = create_mcp_toolbox(allowed_tiers=[1])

# Check if mcp.github is available
if "mcp.github" in toolbox.list_tool_ids():
    print("✓ mcp.github tool is available")
    
    # Execute demo
    result = toolbox.execute_tool(
        tool_id="mcp.github",
        input={"action": "demo", "repo": "TylrDn/cugar-agent"},
        context={"trace_id": "demo_123", "profile": "demo"}
    )
    
    print("\n📊 Execution Result:")
    print(json.dumps(result, indent=2))
else:
    print("⚠ mcp.github not available in tier 1")
    print("Available tools:", toolbox.list_tool_ids())
PYTHON_EOF

echo ""
echo "📝 Step 4: Checking audit log..."
if [ -f "logs/mcp_audit.jsonl" ]; then
    echo "✓ Audit log created: logs/mcp_audit.jsonl"
    echo "Latest entries:"
    tail -n 3 logs/mcp_audit.jsonl | python3 -m json.tool --compact
else
    echo "⚠ No audit log found (logs/mcp_audit.jsonl)"
fi

echo ""
echo "📊 Step 5: Audit statistics..."
python3 << 'PYTHON_EOF'
from pathlib import Path
from cuga.observability.mcp_audit import get_audit_logger

audit_file = Path("logs/mcp_audit.jsonl")
if audit_file.exists():
    logger = get_audit_logger(audit_file=audit_file)
    stats = logger.get_statistics()
    
    print(f"✓ Total invocations: {stats['total_invocations']}")
    print(f"✓ Successful: {stats['successful']}")
    print(f"✓ Failed: {stats['failed']}")
    print(f"✓ Success rate: {stats['success_rate']:.1%}")
    if stats['tools']:
        print(f"✓ Tools used: {', '.join(stats['tools'].keys())}")
else:
    print("⚠ No audit log available yet")
PYTHON_EOF

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   Demo Complete!                                 ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  • Run tests: make test-mcp"
echo "  • View audit log: cat logs/mcp_audit.jsonl | jq"
echo "  • Explore registry: cat docs/mcp/registry.yaml"
echo "  • Try Langflow: examples/langflow/mcp_github_flow.json"
echo ""
