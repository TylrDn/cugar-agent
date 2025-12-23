class MCPError(Exception):
    """Base class for MCP-related issues."""


class StartupError(MCPError):
    pass


class CallTimeout(MCPError):
    pass


class ToolUnavailable(MCPError):
    pass


class CircuitOpen(MCPError):
    pass
