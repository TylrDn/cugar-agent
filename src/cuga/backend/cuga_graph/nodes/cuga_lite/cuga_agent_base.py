"""
CugaAgent Base Class

Core CUGA agent that works with different tool providers through a unified interface.
"""

import ast
import asyncio
import contextlib
import inspect
import io
import json
import re
import textwrap
import time
import types
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.callbacks.usage import UsageMetadataCallbackHandler
from langchain_core.tools import StructuredTool
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from cuga.backend.cuga_graph.state.agent_state import AgentState

try:
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
except ImportError:
    try:
        from langfuse.callback.langchain import LangchainCallbackHandler as LangfuseCallbackHandler
    except ImportError:
        LangfuseCallbackHandler = None

from cuga.backend.cuga_graph.nodes.api.code_agent.code_act_agent import create_codeact
from cuga.backend.cuga_graph.state.agent_state import VariablesManager
from cuga.backend.llm.models import LLMManager
from cuga.backend.cuga_graph.nodes.cuga_lite.tool_provider_interface import (
    ToolProviderInterface,
    AppDefinition,
)
from cuga.config import settings

# E2B sandbox imports (optional)
try:
    from e2b_code_interpreter import Sandbox, Execution

    E2B_AVAILABLE = True
except ImportError:
    E2B_AVAILABLE = False
    Sandbox = None
    Execution = None


class CombinedMetricsCallback(BaseCallbackHandler):
    """Combined callback handler that tracks both timing and token usage."""

    def __init__(self):
        super().__init__()
        self.start_time = None
        self.end_time = None
        self.llm_calls = 0
        self.usage_callback = UsageMetadataCallbackHandler()

    def reset(self):
        """Reset all metrics."""
        self.start_time = time.time()
        self.end_time = None
        self.llm_calls = 0
        self.usage_callback.usage_metadata = {}

    def on_llm_start(self, serialized, prompts, **kwargs):
        """Called when LLM starts."""
        if self.start_time is None:
            self.start_time = time.time()
        self.llm_calls += 1

    def on_llm_end(self, response, **kwargs):
        """Called when LLM ends."""
        self.end_time = time.time()
        self.usage_callback.on_llm_end(response, **kwargs)

    def get_total_tokens(self):
        """Get total tokens across all models."""
        total = 0
        for model_usage in self.usage_callback.usage_metadata.values():
            if isinstance(model_usage, dict):
                if 'total_tokens' in model_usage:
                    total += model_usage['total_tokens']
                elif 'input_tokens' in model_usage and 'output_tokens' in model_usage:
                    total += model_usage['input_tokens'] + model_usage['output_tokens']
            elif hasattr(model_usage, 'total_tokens'):
                total += model_usage.total_tokens
            elif hasattr(model_usage, 'input_tokens') and hasattr(model_usage, 'output_tokens'):
                total += model_usage.input_tokens + model_usage.output_tokens
        return total

    def get_metrics(self):
        """Get current metrics."""
        duration = (self.end_time or time.time()) - (self.start_time or time.time())
        return {
            'duration_seconds': round(duration, 2),
            'llm_calls': self.llm_calls,
            'total_tokens': self.get_total_tokens(),
            'usage_by_model': self.usage_callback.usage_metadata,
        }

    def print_summary(self):
        """Print a summary of metrics."""
        metrics = self.get_metrics()
        print("\n📊 Execution Metrics:")
        print(f"   Duration: {metrics['duration_seconds']}s")
        print(f"   LLM Calls: {metrics['llm_calls']}")
        print(f"   Total Tokens: {metrics['total_tokens']}")
        if metrics['usage_by_model']:
            print(f"   Usage by model: {metrics['usage_by_model']}")
        return metrics


class CugaAgent:
    """
    Base CUGA agent that works with different tool providers.

    This agent supports multiple tool interfaces:
    - ToolRegistryProvider: Tools from MCP registry (separate process)
    - DirectLangChainToolsProvider: LangChain tools passed directly (in-process)

    Usage with Registry:
        ```python
        from cuga.backend.cuga_graph.nodes.cuga_lite.tool_registry_provider import ToolRegistryProvider

        provider = ToolRegistryProvider(app_names=["digital_sales"])
        agent = CugaAgent(tool_provider=provider)
        await agent.initialize()
        answer, metrics, state_messages, chat_messages = await agent.execute("Get top accounts")
        ```

    Usage with Direct Tools:
        ```python
        from cuga.backend.cuga_graph.nodes.cuga_lite.direct_langchain_tools_provider import DirectLangChainToolsProvider
        from langchain_core.tools import tool

        @tool
        def my_tool(query: str) -> str:
            '''Custom tool'''
            return "result"

        provider = DirectLangChainToolsProvider(tools=[my_tool])
        agent = CugaAgent(tool_provider=provider)
        await agent.initialize()
        answer, metrics, state_messages, chat_messages = await agent.execute("Use my tool")
        ```

    Usage with Custom Return Cases:
        ```python
        provider = ToolRegistryProvider(app_names=["digital_sales"])
        custom_cases = [
            "You have a complete final answer with all necessary data from code execution",
            "You need missing parameters or clarification from the user",
            "You need user approval before executing a destructive action",
            "You encounter an ambiguous situation that requires user decision"
        ]
        agent = CugaAgent(
            tool_provider=provider,
            allow_user_clarification=True,
            override_return_to_user_cases=custom_cases
        )
        await agent.initialize()
        answer, metrics, state_messages, chat_messages = await agent.execute("Delete account 123")
        ```
    """

    @staticmethod
    def create_langfuse_handler():
        """Create a Langfuse callback handler if tracing is enabled in settings."""
        if settings.advanced_features.langfuse_tracing:
            if LangfuseCallbackHandler is not None:
                return LangfuseCallbackHandler()
            else:
                logger.warning("Langfuse tracing enabled but langfuse package not available")
        return None

    def __init__(
        self,
        tool_provider: ToolProviderInterface,
        model_settings: Optional[Dict] = None,
        langfuse_handler: Optional[Any] = None,
        eval_fn: Optional[Any] = None,
        prompt_template: Optional[PromptTemplate] = None,
        allow_user_clarification: bool = True,
        override_return_to_user_cases: Optional[List[str]] = None,
        instructions: Optional[str] = None,
        task_loaded_from_file: bool = False,
        is_autonomous_subtask: bool = False,
    ):
        """
        Initialize CugaAgent.

        Args:
            tool_provider: Tool provider implementation (ToolRegistryProvider or DirectLangChainToolsProvider)
            model_settings: Optional model settings to override defaults
            langfuse_handler: Optional Langfuse callback handler for tracing
            eval_fn: Optional custom evaluation function for code execution
            prompt_template: Optional custom prompt template
            allow_user_clarification: If True, agent can ask user for clarification. If False, only final answers allowed.
            override_return_to_user_cases: Optional list of custom cases (in natural language) when agent should return to user.
                                  If None, uses default cases. Example: ["Request user approval for destructive actions"]
            instructions: Optional special instructions to include in the system prompt.
            task_loaded_from_file: If True, indicates that the task was loaded from a file (e.g., markdown file).
            is_autonomous_subtask: If True, indicates this is an autonomous subtask that should complete without user interaction.
        """
        self.tool_provider = tool_provider
        self.model_settings = model_settings
        self.langfuse_handler = langfuse_handler
        self.eval_fn = eval_fn
        self.allow_user_clarification = allow_user_clarification
        self.override_return_to_user_cases = override_return_to_user_cases
        self.instructions = instructions
        self.task_loaded_from_file = task_loaded_from_file
        self.is_autonomous_subtask = is_autonomous_subtask
        self.prompt_template = prompt_template
        self.prompt_template = prompt_template
        self.apps: List[AppDefinition] = []
        self.tools: List[StructuredTool] = []
        self.agent = None
        self.initialized = False

    def get_langfuse_trace_id(self) -> Optional[str]:
        """Get the current Langfuse trace ID if available."""
        if self.langfuse_handler and hasattr(self.langfuse_handler, 'last_trace_id'):
            return self.langfuse_handler.last_trace_id
        return None

    async def initialize(self):
        """Initialize the agent by loading tools from the provider."""
        logger.info("Initializing CugaAgent...")

        await self.tool_provider.initialize()

        all_apps = await self.tool_provider.get_apps()

        # Check if tool_provider has app_names filter set (for single-app mode)
        has_app_filter = hasattr(self.tool_provider, 'app_names') and self.tool_provider.app_names
        if has_app_filter and len(self.tool_provider.app_names) == 1:
            self.apps = [app for app in all_apps if app.name == self.tool_provider.app_names[0]]
            logger.info(f"Filtered to specific app: {self.apps[0].name if self.apps else 'not found'}")
            logger.info(f"Loading tools for specific app: {self.tool_provider.app_names[0]}")
            self.tools = await self.tool_provider.get_tools(self.tool_provider.app_names[0])
        else:
            self.apps = all_apps
            logger.info(f"Found {len(self.apps)} apps: {[app.name for app in self.apps]}")
            self.tools = await self.tool_provider.get_all_tools()

        if not self.tools:
            raise Exception("No tools available from tool provider")

        logger.info(f"Successfully loaded {len(self.tools)} tools")

        llm_manager = LLMManager()
        if self.model_settings:
            model_config = self.model_settings
        else:
            model_config = settings.agent.code.model.copy()
            model_config["streaming"] = False

        model = llm_manager.get_model(model_config)
        logger.info(f"Initialized LLM: {type(model).__name__}")

        custom_prompt = create_mcp_prompt(
            self.tools,
            allow_user_clarification=self.allow_user_clarification,
            return_to_user_cases=self.override_return_to_user_cases,
            instructions=self.instructions,
            apps=self.apps,
            task_loaded_from_file=self.task_loaded_from_file,
            is_autonomous_subtask=self.is_autonomous_subtask,
            prompt_template=self.prompt_template,
        )

        for tool in self.tools:
            if not hasattr(tool, 'func'):
                logger.warning(f"Tool {tool.name} missing .func attribute, attempting to add it")
                if hasattr(tool, 'coroutine') and tool.coroutine:
                    tool.func = tool.coroutine
                elif hasattr(tool, '_run'):
                    tool.func = tool._run

        # Create eval function wrapper that passes thread_id, apps_list, and state
        if self.eval_fn:
            base_eval_fn = self.eval_fn
        else:
            base_eval_fn = eval_with_tools_async

        # Wrap eval function to pass thread_id, apps_list, and state from configurable runtime
        async def eval_function_with_thread(code: str, context: dict, config=None) -> tuple:
            """Wrapper that passes thread_id, apps_list, and state to eval function from configurable runtime."""
            if config:
                configurable = config.get("configurable", {})
                thread_id = configurable.get("thread_id")
                apps_list = configurable.get("apps_list")
                state = configurable.get("state")
            else:
                # Fallback to instance attributes for backward compatibility (state only from config in execute)
                thread_id = getattr(self, 'thread_id', None)
                apps_list = [app.name for app in self.apps] if self.apps else None
                state = None  # State is only passed via config in execute, not from instance
            return await base_eval_fn(code, context, state=state, thread_id=thread_id, apps_list=apps_list)

        agent_graph = create_codeact(
            model=model, tools=self.tools, eval_fn=eval_function_with_thread, prompt=custom_prompt
        )

        self.agent = agent_graph.compile()
        self.initialized = True
        logger.info("CugaAgent initialized successfully")

    async def execute(
        self,
        task: str,
        recursion_limit: int = 15,
        show_progress: bool = True,
        state_messages: Optional[List] = None,
        chat_messages: Optional[List[BaseMessage]] = None,
        initial_context: Optional[Dict[str, Any]] = None,
        keep_last_n_vars: int = 5,
        thread_id: Optional[str] = None,
        state: Optional[AgentState] = None,
    ) -> Tuple[str, Dict[str, Any], Optional[List], Optional[List[BaseMessage]]]:
        """
        Execute a task using the CodeAct agent.

        Args:
            task: The task description to execute
            recursion_limit: Maximum number of reasoning steps
            show_progress: Whether to print progress messages
            state_messages: Optional list to append messages to (for graph visualization)
            chat_messages: Optional chat history to include in context
            initial_context: Optional initial context/variables for CodeAct state
            keep_last_n_vars: Number of most recent variables to keep in context (default: 2)
            thread_id: Thread ID for E2B sandbox caching (optional, for persistent sandboxes)

        Returns:
            Tuple of (answer, usage_metrics, state_messages, updated_chat_messages)
        """
        if not self.initialized:
            raise Exception("Agent not initialized. Call await agent.initialize() first")

        if show_progress:
            print(f"\n{'=' * 60}")
            print(f"🚀 CugaAgent executing: {task}")
            if thread_id:
                print(f"   Thread ID: {thread_id} (E2B sandbox will be cached)")
            print(f"{'=' * 60}")

        callbacks = []
        metrics_callback = CombinedMetricsCallback()
        callbacks.append(metrics_callback)

        agent = self.agent

        if self.langfuse_handler and settings.advanced_features.langfuse_tracing:
            callbacks.append(self.langfuse_handler)
            if show_progress:
                print("🔍 Langfuse tracing enabled")

        # Prepare configurable runtime values for eval function
        apps_list = [app.name for app in self.apps] if self.apps else None
        config = {
            "thread_id": thread_id or 1,
            "recursion_limit": recursion_limit,
            "callbacks": callbacks,
            "configurable": {
                "thread_id": thread_id,
                "apps_list": apps_list,
                "state": state,
            },
        }

        initial_messages = []
        if chat_messages:
            logger.debug(f"Chat messages: {chat_messages}")
            for msg in chat_messages:
                if isinstance(msg, HumanMessage):
                    initial_messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    initial_messages.append({"role": "assistant", "content": msg.content})
                elif hasattr(msg, 'content'):
                    role = getattr(msg, 'type', 'user')
                    if role == 'human' or role == 'user':
                        initial_messages.append({"role": "user", "content": msg.content})
                    elif role == 'ai' or role == 'assistant':
                        initial_messages.append({"role": "assistant", "content": msg.content})

        # Prepare task content with variables summary if needed
        task_content = task

        if initial_context and not chat_messages:
            var_manager = state.variables_manager
            for var_name, var_value in initial_context.items():
                var_manager.add_variable(
                    var_value, name=var_name, description="Passed from previous execution"
                )

            variable_names = list(initial_context.keys())
            if variable_names:
                variables_summary = var_manager.get_variables_summary(variable_names=variable_names)
                task_content = f"{task}\n\n## Available Variables\n\n{variables_summary}\n\nYou can use these variables directly by their names."
                logger.info(
                    f"Added variables summary for {len(variable_names)} variables to first user message"
                )

        initial_messages.append({"role": "user", "content": task_content})

        initial_state = {"messages": initial_messages, "context": initial_context or {}}

        if show_progress:
            print("🤖 Starting CodeAct Agent Execution")
            print("=" * 60)

        execution_steps = []
        all_code = []
        all_execution_outputs = []

        def extract_code_from_content(content: str) -> str:
            """Extract code from markdown code blocks in message content."""

            BACKTICK_PATTERN = r"```(.*?)(?:```(?:\n|$))"
            code_blocks = re.findall(BACKTICK_PATTERN, content, re.DOTALL)
            if not code_blocks:
                return ""

            processed_blocks = []
            for block in code_blocks:
                block = block.strip()
                lines = block.split("\n")
                if lines and (not lines[0].strip() or " " not in lines[0].strip()):
                    block = "\n".join(lines[1:])
                processed_blocks.append(block)
            return "\n\n".join(processed_blocks)

        try:
            step_count = 0
            final_state = None
            last_code = None

            async for chunk in agent.astream(initial_state, config=config, stream_mode="values"):
                step_count += 1
                final_state = chunk

                # logger.debug(f"Chunk keys: {list(chunk.keys())}")
                logger.debug(f"Has script: {'script' in chunk}")

                if "script" in chunk and chunk["script"]:
                    code = chunk["script"]
                    if code and code not in all_code:
                        all_code.append(code)
                        last_code = code
                        execution_steps.append(f"Step {step_count}: Code generation")
                        logger.debug(f"Captured code from script field (length: {len(code)})")

                if "messages" in chunk and chunk["messages"]:
                    last_msg = chunk["messages"][-1]
                    if hasattr(last_msg, "content"):
                        content = last_msg.content

                        if isinstance(content, str) and "Execution output:" in content:
                            execution_output = content.replace("Execution output:\n", "")
                            all_execution_outputs.append(execution_output)

                            if state_messages is not None:
                                import json

                                state_messages.append(
                                    AIMessage(
                                        content=json.dumps(
                                            {
                                                "status": "execution_output",
                                                "step": step_count,
                                                "code": last_code or "",
                                                "execution_output": execution_output,
                                                "message": f"Code execution and output for step {step_count}",
                                            }
                                        )
                                    )
                                )

                        if show_progress:
                            role = "AI" if "AIMessage" in str(last_msg.__class__) else "User"
                            display_content = content
                            if len(display_content) > 5000:
                                display_content = display_content[:5000] + "..."
                            print(f"\n[{role}]: {display_content}")

            if show_progress:
                print(f"\n{'=' * 60}")
                print(f"✅ Execution completed in {step_count} steps")
                print(f"{'=' * 60}")

            final_answer = "No answer found"
            if final_state and "messages" in final_state:
                # Find the last AI message with non-empty content
                for msg in reversed(final_state["messages"]):
                    logger.debug(f"Message: {msg}")
                    if hasattr(msg, "__class__") and "AIMessage" in str(msg.__class__):
                        content = msg.content if hasattr(msg, 'content') else str(msg)
                        logger.debug(f"Content: {content}")
                        # Only use non-empty content as final answer
                        if content and content.strip():
                            final_answer = content
                            break

                # If no text answer found, use the last execution output as the answer
                if final_answer == "No answer found" and all_execution_outputs:
                    # Extract the actual output (before the "New Variables" section)
                    last_output = all_execution_outputs[-1]
                    if "## New Variables Created:" in last_output:
                        actual_output = last_output.split("## New Variables Created:")[0].strip()
                    else:
                        actual_output = last_output.strip()

                    if actual_output:
                        final_answer = actual_output
                        logger.info(
                            "Using last execution output as final answer (no text answer provided by agent)"
                        )

            if show_progress:
                print(f"\n{'=' * 60}")
                print("FINAL ANSWER:")
                print(f"{'=' * 60}")
                print(final_answer)

            usage_metrics = metrics_callback.get_metrics()
            usage_metrics['step_count'] = step_count
            usage_metrics['tools_available'] = len(self.tools)
            usage_metrics['apps_used'] = [app.name for app in self.apps]

            if state_messages is not None:
                from cuga.backend.cuga_graph.nodes.cuga_lite.cuga_lite_node import CugaLiteOutput

                combined_code = "\n\n".join(all_code) if all_code else ""
                combined_execution_output = (
                    "\n\n".join(all_execution_outputs) if all_execution_outputs else ""
                )

                output = CugaLiteOutput(
                    code=combined_code,
                    execution_output=combined_execution_output,
                    steps_summary=execution_steps,
                    summary=f"Task completed successfully in {step_count} steps",
                    metrics=usage_metrics,
                    final_answer=final_answer,
                )

                final_context = {}
                if final_state and "context" in final_state:
                    full_context = final_state["context"]

                    # Separate initial context variables from newly created ones
                    initial_var_names = set(initial_context.keys()) if initial_context else set()
                    new_var_names = [k for k in full_context.keys() if k not in initial_var_names]

                    # Keep initial context variables (convert sets to lists for serialization)
                    final_context = {}
                    for k, v in full_context.items():
                        if k in initial_var_names:
                            if isinstance(v, set):
                                final_context[k] = list(v)
                                logger.debug(f"Converted set variable '{k}' to list in final_context")
                            else:
                                final_context[k] = v

                    # Apply keep_last_n_vars only to newly created variables
                    if keep_last_n_vars > 0 and len(new_var_names) > keep_last_n_vars:
                        # Keep only the last N newly created variables
                        vars_to_keep = new_var_names[-keep_last_n_vars:]
                        for var_name in vars_to_keep:
                            value = full_context[var_name]
                            if isinstance(value, set):
                                final_context[var_name] = list(value)
                                logger.debug(f"Converted set variable '{var_name}' to list in final_context")
                            else:
                                final_context[var_name] = value

                        # Remove newly created variables that are not being kept from var_manager
                        if state is not None:
                            var_manager = state.variables_manager
                            vars_to_remove = new_var_names[:-keep_last_n_vars]  # All except last N new vars
                            for var_name in vars_to_remove:
                                if var_manager.remove_variable(var_name):
                                    logger.debug(f"Removed variable '{var_name}' from var_manager")

                        logger.debug(
                            f"Kept last {keep_last_n_vars} of {len(new_var_names)} newly created variables (plus {len(initial_var_names)} initial vars)"
                        )
                    else:
                        # Keep all newly created variables
                        for var_name in new_var_names:
                            value = full_context[var_name]
                            if isinstance(value, set):
                                final_context[var_name] = list(value)
                                logger.debug(f"Converted set variable '{var_name}' to list in final_context")
                            else:
                                final_context[var_name] = value
                        logger.debug(
                            f"Preserving all {len(new_var_names)} newly created variables (plus {len(initial_var_names)} initial vars)"
                        )

                state_messages.append(
                    AIMessage(content=output.model_dump_json(), additional_kwargs={"context": final_context})
                )

            if show_progress:
                print("\n📊 Execution Metrics:")
                print(f"   Duration: {usage_metrics['duration_seconds']}s")
                print(f"   LLM Calls: {usage_metrics['llm_calls']}")
                print(f"   Total Tokens: {usage_metrics['total_tokens']}")
                print(f"   Steps: {step_count}")
                print(f"   Tools Available: {len(self.tools)}")

                trace_id = self.get_langfuse_trace_id()
                if trace_id:
                    print(f"   Langfuse Trace ID: {trace_id}")
                    logger.info(f"Langfuse Trace ID: {trace_id}")

            if state_messages is None:
                state_messages = []

            # Convert final_state["messages"] back to chat_messages format for conversation history
            updated_chat_messages = None
            if final_state and "messages" in final_state and chat_messages is not None:
                updated_chat_messages = []
                for msg in final_state["messages"]:
                    if isinstance(msg, dict):
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        if role == "user":
                            updated_chat_messages.append(HumanMessage(content=content))
                        elif role == "assistant":
                            updated_chat_messages.append(AIMessage(content=content))
                    elif isinstance(msg, (HumanMessage, AIMessage)):
                        updated_chat_messages.append(msg)
                logger.info(f"Converted {len(updated_chat_messages)} messages for chat history continuation")

            return final_answer, usage_metrics, state_messages, updated_chat_messages

        except asyncio.TimeoutError:
            logger.error("Execution timeout")
            usage_metrics = metrics_callback.get_metrics()
            usage_metrics['error'] = 'timeout'
            return "Error: Execution timeout", usage_metrics, state_messages, None
        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            usage_metrics = metrics_callback.get_metrics()
            usage_metrics['error'] = 'interrupted'
            return "Error: Interrupted by user", usage_metrics, state_messages, None
        except Exception as e:
            logger.error(f"Error during execution: {e}", exc_info=True)
            usage_metrics = metrics_callback.get_metrics()
            usage_metrics['error'] = str(e)
            return f"Error during execution: {e}", usage_metrics, state_messages, None

    def list_apps(self) -> List[Dict[str, str]]:
        """Get list of loaded apps."""
        return [
            {
                "name": app.name,
                "url": app.url if app.url else None,
                "description": app.description if app.description else None,
                "type": app.type,
            }
            for app in self.apps
        ]

    def list_tools(self) -> List[Dict[str, str]]:
        """Get list of loaded tools."""
        return [
            {"name": tool.name, "description": tool.description if tool.description else "No description"}
            for tool in self.tools
        ]


def _is_serializable(value: Any) -> bool:
    """Check if a value is serializable (can be safely stored in state context).

    Filters out modules, functions, classes, and other non-serializable objects.
    """
    # Allow basic types
    if isinstance(value, (str, int, float, bool, type(None))):
        return True

    # Allow lists and dicts (recursively check contents)
    if isinstance(value, (list, tuple)):
        return all(_is_serializable(item) for item in value)

    if isinstance(value, dict):
        return all(_is_serializable(k) and _is_serializable(v) for k, v in value.items())

    # Reject modules, functions, classes, and other non-serializable objects
    if isinstance(
        value, (types.ModuleType, types.FunctionType, types.BuiltinFunctionType, types.MethodType, type)
    ):
        return False

    # Sets are not JSON serializable, so reject them
    if isinstance(value, set):
        return False

    # For other objects, try to check if they're basic types wrapped
    try:
        # Try to convert to basic types
        if hasattr(value, '__dict__'):
            # Skip objects with __dict__ (likely custom classes)
            return False
    except Exception:
        pass

    return False


def _filter_new_variables(all_locals: dict[str, Any], original_keys: set[str]) -> dict[str, Any]:
    """Filter and return only new, serializable variables from locals.

    Args:
        all_locals: Dictionary of all local variables
        original_keys: Set of keys that existed before execution

    Returns:
        Dictionary of new serializable variables (preserves insertion order)
    """
    new_keys = set(all_locals.keys()) - original_keys
    new_vars = {}

    # Iterate over all_locals.keys() to preserve insertion order (creation order)
    # rather than iterating over the set which doesn't maintain order
    for key in all_locals.keys():
        if key not in new_keys:
            continue
        # Skip internal variables
        if key.startswith('_'):
            continue
        value = all_locals[key]
        if _is_serializable(value):
            new_vars[key] = value
        else:
            logger.debug(f"Skipping non-serializable variable '{key}': {type(value).__name__}")

    return new_vars


def _serialize_tools_for_e2b(locals_dict: dict[str, Any], apps_list: List[str] = None) -> str:
    """Serialize async tool functions into Python source code for E2B.

    For registry tools (HTTP-based), generates stubs that call the registry API.
    For native Python functions, extracts and includes their source code.

    Args:
        locals_dict: Dictionary containing tool functions (key=tool_name, value=tool_func)
        apps_list: Optional list of app names to help parse tool names correctly

    Returns:
        String of Python code defining these functions
    """
    lines = ["# Tool functions from previous execution"]

    # Sort apps by length (longest first) for better matching
    sorted_apps = sorted(apps_list or [], key=len, reverse=True)

    for tool_name, tool_func in locals_dict.items():
        # Skip non-functions
        if not callable(tool_func):
            continue

        # Skip internal functions
        if tool_name.startswith('_'):
            continue

        # Only serialize async functions (tools should be async)
        if not asyncio.iscoroutinefunction(tool_func):
            continue

        try:
            # Try to get the source code
            source = inspect.getsource(tool_func)
            dedented_source = textwrap.dedent(source)

            # Check if this looks like a real Python function (not a generic wrapper)
            # Real functions have the actual function name in their definition
            if f"def {tool_name}" in dedented_source or f"async def {tool_name}" in dedented_source:
                # This is a real Python function with source code, use it directly
                lines.append(dedented_source)
            else:
                # This is a dynamically created wrapper (registry tool)
                # Generate a stub using the KEY from the dict as the function name
                logger.debug(f"Tool '{tool_name}' is a registry wrapper, generating call_api stub")

                # Parse tool name to extract app_name and api_name
                # Format: {app_name}_{rest_of_name}
                # Try to match against known app names (sorted by length, longest first)
                app_name_guess = "unknown"
                for app in sorted_apps:
                    if tool_name.startswith(app + '_'):
                        app_name_guess = app
                        break

                # If no match found, fall back to splitting
                if app_name_guess == "unknown":
                    parts = tool_name.split('_', 1)
                    if len(parts) >= 2:
                        app_name_guess = parts[0]

                api_name_guess = tool_name

                # Generate stub function using **kwargs to match any call signature
                stub = f"""async def {tool_name}(**kwargs):
    \"\"\"Registry tool: {tool_name}\"\"\"
    # This stub was auto-generated for registry tool
    # Calls the registry API via call_api helper (synchronous)
    return await call_api("{app_name_guess}", "{api_name_guess}", kwargs)
"""
                lines.append(stub)

        except (OSError, TypeError) as e:
            # Can't get source (likely a built-in or C function)
            logger.debug(f"Could not get source for tool '{tool_name}': {e}")
            # Generate a minimal stub as fallback
            stub = f"""async def {tool_name}(*args, **kwargs):
    \"\"\"Tool stub for {tool_name}\"\"\"
    return await call_api("unknown", "{tool_name}", kwargs)
"""
            lines.append(stub)
            continue

    return "\n".join(lines) + "\n\n" if len(lines) > 1 else ""


global_sandbox_id = None


async def _execute_in_e2b_sandbox(
    user_code: str,
    context_locals: dict[str, Any] = None,
    thread_id: str = None,
    apps_list: List[str] = None,
    state: Optional[Any] = None,
) -> tuple[str, dict[str, Any]]:
    """Execute code in E2B remote sandbox with variables and tools from context (async).

    Args:
        user_code: User's Python code (already wrapped in async function)
        context_locals: Dictionary of variables and tools from previous execution
        thread_id: Thread ID for sandbox caching (if None, creates ephemeral sandbox)
        apps_list: List of app names for parsing tool names correctly
        state: Optional AgentState instance. If provided, uses state.variables_manager.

    Returns:
        Tuple of (stdout_result, parsed_locals)

    Raises:
        RuntimeError: If E2B execution or parsing fails
    """
    global global_sandbox_id

    if not E2B_AVAILABLE:
        raise RuntimeError("e2b-code-interpreter package not installed")

    if context_locals is None:
        context_locals = {}

    try:
        var_manager = state.variables_manager if state is not None else VariablesManager()
        variables_code = var_manager.get_variables_formatted()

        # Serialize tool functions (callable async functions)
        tools_code = _serialize_tools_for_e2b(context_locals, apps_list=apps_list)

        # Get function_call_host for E2B (needs publicly accessible URL)
        # Fallback: function_call_host -> registry_host -> "http://localhost:8001"
        function_call_url = getattr(settings.server_ports, 'function_call_host', None)
        if not function_call_url:
            function_call_url = getattr(settings.server_ports, 'registry_host', None)
        if not function_call_url:
            function_call_url = "http://localhost:8001"

        # Add call_api helper for registry tools (HTTP client)
        # Note: Using regular string with .format() to avoid f-string escaping issues
        call_api_helper = """
# HTTP client for calling registry tools
import asyncio
import json
import urllib.request
import urllib.error

async def call_api(app_name, api_name, args=None):
    \"\"\"Call registry API tool via HTTP (synchronous).\"\"\"
    if args is None:
        args = {{}}

    # Registry URL from CUGA settings
    url = "{registry_url}/functions/call"

    headers = {{
        "accept": "application/json",
        "Content-Type": "application/json"
    }}
    payload = {{
        "function_name": api_name,
        "app_name": app_name,
        "args": args
    }}

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')

    loop = asyncio.get_event_loop()

    def _sync_call():
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = response.read().decode('utf-8')
                try:
                    response_data = json.loads(response_data)
                except Exception as e:
                    pass
                return response_data
        except urllib.error.HTTPError as e:
            print(e)
            raise Exception(f"HTTP Error: {{e.code}} - {{e.reason}}")
        except urllib.error.URLError as e:
            print(e)
            raise Exception(f"URL Error: {{e.reason}}")
    
    return await loop.run_in_executor(None, _sync_call)
""".format(registry_url=function_call_url)

        # Combine: imports + call_api + tools + variables + user code
        complete_code = f"""
{call_api_helper}
{tools_code}
{variables_code}
{user_code}

# Execute and capture locals
async def main():
    __result_locals = await asyncio.wait_for(__async_main(), timeout=30)
    print("!!!===!!!")
    print(__result_locals)

if __name__ == "__main__":
    await main()
"""

        logger.debug(f"Executing in E2B with {var_manager.get_variable_count()} variables and tools")

        # Debug: Print the complete code being sent to E2B
        print("=" * 80)
        print("CODE SENT TO E2B SANDBOX:")
        print("=" * 80)
        print(complete_code)
        print("=" * 80)

        # Get or create sandbox based on thread_id
        loop = asyncio.get_event_loop()
        if settings.advanced_features.e2b_sandbox_mode == "per-session" and thread_id:
            # Use cached sandbox for this thread
            from cuga.backend.cuga_graph.nodes.cuga_lite.e2b_sandbox_cache import get_sandbox_cache

            cache = get_sandbox_cache()
            sandbox = cache.get_or_create(thread_id)
            logger.debug(f"Executing in E2B sandbox {sandbox.sandbox_id} for thread {thread_id}")
            execution = await loop.run_in_executor(None, sandbox.run_code, complete_code)
        elif settings.advanced_features.e2b_sandbox_mode == "single":
            if (
                global_sandbox_id is None
                or (sandbox := Sandbox.connect(global_sandbox_id))
                and not sandbox.is_running
            ):
                logger.debug("Creating new global E2B sandbox")
                sandbox = Sandbox.create("cuga-langchain")
                global_sandbox_id = sandbox.sandbox_id
            logger.debug(f"Executing in global E2B sandbox {sandbox.sandbox_id}")
            execution = await loop.run_in_executor(None, sandbox.run_code, complete_code)
        else:
            # Create ephemeral sandbox (no caching)
            logger.debug("Creating new ephemeral E2B sandbox")
            with Sandbox.create("cuga-langchain") as sandbox:
                logger.debug("Creating new ephemeral E2B sandbox")
                execution = await loop.run_in_executor(None, sandbox.run_code, complete_code)

        # Check for execution errors
        if execution.error:
            raise RuntimeError(f"E2B execution error: {execution.error}")

        # Process stdout
        stdout_lines = execution.logs.stdout
        raw_data = "\n".join(map(str.strip, stdout_lines))
        result, locals_str = raw_data.split("!!!===!!!")

        # Parse locals from stdout (last line with the dict)
        result_locals = {}
        lines = locals_str.split('\n')
        for line in reversed(lines):
            if line.strip().startswith('{'):
                try:
                    result_locals = ast.literal_eval(line.strip())
                    break
                except (ValueError, SyntaxError):
                    continue

        if not result_locals:
            logger.warning("E2B execution returned no parseable locals")

        return result, result_locals

    except Exception as e:
        raise RuntimeError(f"E2B sandbox execution failed: {e}")


async def eval_with_tools_async(
    code: str,
    _locals: dict[str, Any],
    state: AgentState,
    thread_id: str = None,
    apps_list: List[str] = None,
) -> tuple[str, dict[str, Any]]:
    """Execute code with async tools available in the local namespace.

    Args:
        code: Python code to execute
        _locals: Local variables/context for execution
        thread_id: Thread ID for E2B sandbox caching (optional)
        apps_list: List of app names for parsing tool names correctly (optional)
        state: Optional AgentState instance. If provided, uses state.variables_manager.

    Returns:
        Tuple of (execution result, new variables dictionary)
    """

    original_keys = set(_locals.keys())
    result = ""

    # Pre-execution security validation: Scan for dangerous imports
    dangerous_imports = {'os', 'sys', 'subprocess', 'pathlib', 'shutil', 'glob', 'importlib'}
    allowed_imports = {
        'asyncio',
        'json',
        'pandas',
        'numpy',
        'statistics',
        'datetime',
        'math',
        'collections',
        'itertools',
        'functools',
        're',
        'typing',
    }

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if module_name in dangerous_imports:
                        raise ImportError(
                            f"Import of '{module_name}' is not allowed in restricted execution context"
                        )
                    if module_name not in allowed_imports:
                        raise ImportError(
                            f"Import of '{module_name}' is not allowed in restricted execution context"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    if module_name in dangerous_imports:
                        raise ImportError(
                            f"Import from '{module_name}' is not allowed in restricted execution context"
                        )
                    if module_name not in allowed_imports:
                        raise ImportError(
                            f"Import from '{module_name}' is not allowed in restricted execution context"
                        )
    except SyntaxError as e:
        logger.warning(f"Syntax error in code during pre-validation: {e}. Will attempt execution anyway.")

    # Prepare wrapped code for execution
    indented_code = '\n'.join('    ' + line for line in code.split('\n'))
    lines = [line.strip() for line in code.split('\n') if line.strip()]
    if lines and not lines[-1].startswith(('print', 'return', '#')) and '=' not in lines[-1]:
        # Last line looks like a variable reference, add a print statement
        indented_code += f"\n    print({lines[-1]})"

    wrapped_code = f"""
import asyncio
async def __async_main():
{indented_code}
    return locals()

# Execute the wrapped function
"""

    # Additional validation: Scan wrapped_code for any dangerous imports
    # (defense in depth - should never trigger since we control the template)
    for dangerous_module in ['os', 'sys', 'subprocess', 'pathlib', 'shutil']:
        # Check for both "import os" and "from os import"
        if re.search(rf'\bimport\s+{dangerous_module}\b', wrapped_code) or re.search(
            rf'\bfrom\s+{dangerous_module}\b', wrapped_code
        ):
            raise PermissionError(
                f"Security violation: Dangerous module '{dangerous_module}' detected in wrapped code"
            )

    try:
        # Execute in E2B sandbox if enabled
        if settings.advanced_features.e2b_sandbox:
            result, parsed_locals = await _execute_in_e2b_sandbox(
                wrapped_code, context_locals=_locals, thread_id=thread_id, apps_list=apps_list, state=state
            )
            _locals.update(parsed_locals)
            new_vars = _filter_new_variables(_locals, original_keys)
            return result, new_vars

        # Local execution with restricted environment
        with contextlib.redirect_stdout(io.StringIO()) as f:
            # Create a restricted __import__ that only allows whitelisted modules
            _original_import = (
                __builtins__['__import__'] if isinstance(__builtins__, dict) else __builtins__.__import__
            )

            def restricted_import(name, globals=None, locals=_locals, fromlist=(), level=0):
                # Whitelist of allowed modules
                allowed_modules = {
                    'asyncio',
                    'json',
                    'pandas',
                    'numpy',
                    'datetime',
                    'math',
                    'collections',
                    'itertools',
                    'functools',
                    're',
                    'typing',
                }

                # Block access to dangerous modules
                if name.split('.')[0] not in allowed_modules:
                    raise ImportError(f"Import of '{name}' is not allowed in restricted execution context")

                return _original_import(name, globals, locals, fromlist, level)

            # Create restricted builtins - allow only safe operations
            # Exclude: compile, eval, exec, open, input, file operations
            safe_builtins = {
                # Type constructors
                'dict': dict,
                'list': list,
                'tuple': tuple,
                'set': set,
                'frozenset': frozenset,
                'str': str,
                'bytes': bytes,
                'bytearray': bytearray,
                'int': int,
                'float': float,
                'bool': bool,
                'complex': complex,
                # Utilities
                'len': len,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'map': map,
                'filter': filter,
                'sorted': sorted,
                'reversed': reversed,
                'sum': sum,
                'min': min,
                'max': max,
                'abs': abs,
                'round': round,
                'any': any,
                'all': all,
                # String operations
                'chr': chr,
                'ord': ord,
                'format': format,
                'repr': repr,
                # Type checking
                'isinstance': isinstance,
                'issubclass': issubclass,
                'type': type,
                'hasattr': hasattr,
                'getattr': getattr,
                'setattr': setattr,
                'delattr': delattr,
                # Iteration
                'iter': iter,
                'next': next,
                'slice': slice,
                # Exceptions (needed for error handling)
                'BaseException': BaseException,
                'Exception': Exception,
                'ValueError': ValueError,
                'TypeError': TypeError,
                'KeyError': KeyError,
                'IndexError': IndexError,
                'AttributeError': AttributeError,
                'RuntimeError': RuntimeError,
                'StopIteration': StopIteration,
                'AssertionError': AssertionError,
                'ImportError': ImportError,
                # Other essentials
                'print': print,
                'None': None,
                'True': True,
                'False': False,
                'locals': locals,
                'vars': vars,  # Variable introspection
                '__name__': '__restricted__',
                '__build_class__': __build_class__,
                '__import__': restricted_import,  # Restricted import
            }

            # Create restricted globals with limited module access
            # os, sys, subprocess, and other dangerous modules are completely excluded
            restricted_globals = {
                "__builtins__": safe_builtins,
                "asyncio": asyncio,  # Needed for async execution
                "json": json,  # Commonly needed for tool calls
            }

            # Add pandas if available
            try:
                import pandas as pd

                restricted_globals["pd"] = pd
                restricted_globals["pandas"] = pd
            except ImportError:
                pass  # pandas not installed, skip

            # Add tool functions from _locals (these are the callable tools)
            # Filter out any dangerous modules that might have been passed in _locals
            dangerous_module_names = {
                'os',
                'sys',
                'subprocess',
                'pathlib',
                'shutil',
                'glob',
                'importlib',
                '__import__',
                'eval',
                'exec',
                'compile',
            }
            safe_locals = {k: v for k, v in _locals.items() if k not in dangerous_module_names}

            # Merge tools and variables into restricted_globals so they're accessible
            # to the async function when it runs
            restricted_globals.update(safe_locals)

            # Safety check: Ensure no dangerous modules leaked into the execution environment
            assert 'os' not in restricted_globals, "Security violation: os module in restricted_globals!"
            assert 'sys' not in restricted_globals, "Security violation: sys module in restricted_globals!"
            assert 'subprocess' not in restricted_globals, (
                "Security violation: subprocess in restricted_globals!"
            )

            # Create a namespace for exec to populate with local definitions
            exec_locals = {}
            exec(wrapped_code, restricted_globals, exec_locals)

            # Get and run the async function (it's now in exec_locals)
            async_main = exec_locals['__async_main']
            result_locals = await asyncio.wait_for(async_main(), timeout=30)
            _locals.update(result_locals)

        result = f.getvalue()
        if not result:
            result = "<code ran, no output printed to stdout>"

    except asyncio.TimeoutError:
        result = "Error during execution: Execution timed out after 30 seconds"
    except Exception as e:
        result = f"Error during execution: {repr(e)}"
        import traceback

        result += f"\n{traceback.format_exc()}"

    # Filter new variables
    new_vars = _filter_new_variables(_locals, original_keys)

    # Find last print line and move variables that appear in it to the end
    if new_vars:
        lines = code.strip().split('\n')
        # Find last line with print(
        last_print_line = None
        for line in reversed(lines):
            stripped = line.strip()
            if 'print(' in stripped:
                last_print_line = stripped
                break

        # Reorder new_vars: move variables that appear in last_print_line to the end
        if last_print_line:
            reordered_vars = {}
            print_vars = {}

            for var_name, var_value in new_vars.items():
                # If variable name appears in last print line and is more than 3 letters, move to end
                if var_name in last_print_line and len(var_name) > 3:
                    print_vars[var_name] = var_value
                else:
                    reordered_vars[var_name] = var_value

            # Add print vars at the end
            reordered_vars.update(print_vars)
            new_vars = reordered_vars

    # Add new variables to VariablesManager and get their preview
    if new_vars:
        var_manager = state.variables_manager
        for var_name, var_value in new_vars.items():
            var_manager.add_variable(var_value, name=var_name, description="Created during code execution")

        # Get formatted summary of all new variables
        try:
            variables_summary = var_manager.get_variables_summary(variable_names=list(new_vars.keys()))
            if variables_summary and variables_summary != "# No variables stored":
                result += f"\n\n## New Variables Created:\n{variables_summary}"
        except Exception as e:
            logger.debug(f"Could not generate variables summary: {e}")

    return result, new_vars


def create_mcp_prompt(
    tools,
    base_prompt=None,
    allow_user_clarification=True,
    return_to_user_cases=None,
    instructions=None,
    apps=None,
    task_loaded_from_file=False,
    is_autonomous_subtask=False,
    prompt_template=None,
):
    """Create a prompt for CodeAct agent that works with MCP tools.

    Args:
        tools: List of available tools
        base_prompt: Optional base prompt to prepend
        allow_user_clarification: If True, agent can ask user for clarification. If False, only final answers allowed.
        return_to_user_cases: Optional list of custom cases (in natural language) when agent should return to user.
                             If None, uses default cases.
        instructions: Optional special instructions to include in the system prompt.
        apps: Optional list of connected apps with their descriptions
        task_loaded_from_file: If True, indicates that the task was loaded from a file
        is_autonomous_subtask: If True, indicates this is an autonomous subtask that should complete without user interaction
    """
    processed_tools = []
    for tool in tools:
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        tool_desc = tool.description if hasattr(tool, 'description') else "No description"

        response_schemas = {}
        if hasattr(tool, 'func') and hasattr(tool.func, '_response_schemas'):
            response_schemas = tool.func._response_schemas

        param_constraints = {}
        if hasattr(tool, 'func') and hasattr(tool.func, '_param_constraints'):
            param_constraints = tool.func._param_constraints

        if hasattr(tool, 'args_schema') and tool.args_schema:
            try:
                schema = tool.args_schema.schema()
                properties = schema.get('properties', {})
                required = schema.get('required', [])

                params = []
                for name, prop in properties.items():
                    param_type = prop.get('type', 'Any')

                    type_mapping = {
                        'string': 'str',
                        'integer': 'int',
                        'number': 'float',
                        'boolean': 'bool',
                        'array': 'list',
                        'object': 'dict',
                    }
                    python_type = type_mapping.get(param_type, param_type)

                    if name in required:
                        params.append(f"{name}: {python_type}")
                    else:
                        default_val = prop.get('default', None)
                        if default_val is not None:
                            if isinstance(default_val, str):
                                params.append(f"{name}: {python_type} = \"{default_val}\"")
                            else:
                                params.append(f"{name}: {python_type} = {default_val}")
                        else:
                            params.append(f"{name}: {python_type} = None")

                params_str = ', '.join(params) if params else ''
            except Exception as e:
                logger.debug(f"Failed to parse schema for tool {tool_name}: {e}")
                params_str = "**kwargs"
        else:
            params_str = "**kwargs"

        response_doc = ""
        if response_schemas and isinstance(response_schemas, dict):
            if 'success' in response_schemas:
                success_schema = json.dumps(response_schemas['success'], indent=4)
                response_doc += f"\n    \n    Returns (on success) - Response Schema:\n{success_schema}"

        if params_str:
            params_list = []
            if hasattr(tool, 'args_schema') and tool.args_schema:
                try:
                    schema = tool.args_schema.schema()
                    properties = schema.get('properties', {})
                    required = schema.get('required', [])

                    for name, prop in properties.items():
                        param_type = prop.get('type', 'string')
                        type_mapping = {
                            'string': 'str',
                            'integer': 'int',
                            'number': 'float',
                            'boolean': 'bool',
                            'array': 'list',
                            'object': 'dict',
                        }
                        python_type = type_mapping.get(param_type, param_type)

                        desc = prop.get('description', '')
                        required_mark = " (required)" if name in required else " (optional)"

                        constraints = param_constraints.get(name, []) or prop.get('constraints', [])
                        constraints_str = ""
                        if constraints:
                            constraints_str = f" [Constraints: {', '.join(constraints)}]"

                        params_list.append(
                            f"- `{name}`: {python_type}{required_mark} - {desc}{constraints_str}"
                        )
                except Exception:
                    params_list = [f"- {param.strip()}" for param in params_str.split(',') if param.strip()]

            params_doc = "\n".join(params_list) if params_list else "No parameters required"
        else:
            params_doc = "No parameters required"

        processed_tools.append(
            {
                'name': tool_name,
                'description': tool_desc,
                'params_str': params_str,
                'params_doc': params_doc,
                'response_doc': response_doc,
            }
        )

    processed_apps = []
    if apps:
        for app in apps:
            description = getattr(app, 'description', 'No description available')
            max_length = 300
            if len(description) > max_length:
                description = description[:max_length] + '...'
            processed_apps.append(
                {
                    'name': app.name,
                    'type': getattr(app, 'type', 'api'),
                    'description': description,
                }
            )

    prompt = prompt_template.format(
        base_prompt=base_prompt,
        apps=processed_apps,
        allow_user_clarification=allow_user_clarification,
        return_to_user_cases=return_to_user_cases,
        instructions=instructions,
        tools=processed_tools,
        task_loaded_from_file=task_loaded_from_file,
        is_autonomous_subtask=is_autonomous_subtask,
    )
    return prompt
