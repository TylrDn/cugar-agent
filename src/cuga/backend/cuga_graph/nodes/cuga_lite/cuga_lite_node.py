"""
CugaLite Node - Fast execution node using CugaAgent
"""

import json
from typing import Literal, Dict, Any, List, Optional
from langgraph.types import Command
from loguru import logger
from pydantic import BaseModel, Field

from cuga.backend.cuga_graph.nodes.cuga_lite import CugaAgent
from cuga.backend.cuga_graph.nodes.shared.base_node import BaseNode
from cuga.backend.cuga_graph.state.agent_state import AgentState, SubTaskHistory
from cuga.backend.activity_tracker.tracker import ActivityTracker
from cuga.backend.cuga_graph.nodes.api.api_planner_agent.prompts.load_prompt import ActionName
from cuga.backend.cuga_graph.state.api_planner_history import CoderAgentHistoricalOutput
from cuga.config import settings
from langchain_core.messages import AIMessage
from cuga.backend.llm.utils.helpers import load_one_prompt

try:
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
except ImportError:
    try:
        from langfuse.callback.langchain import LangchainCallbackHandler as LangfuseCallbackHandler
    except ImportError:
        LangfuseCallbackHandler = None


from cuga.configurations.instructions_manager import get_all_instructions_formatted


tracker = ActivityTracker()


def _convert_sets_to_lists(value: Any) -> Any:
    """Recursively convert sets to lists for JSON serialization."""
    if isinstance(value, set):
        return list(value)
    elif isinstance(value, dict):
        return {k: _convert_sets_to_lists(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [_convert_sets_to_lists(item) for item in value]
    else:
        return value


class CugaLiteOutput(BaseModel):
    """Output model for CugaLite execution (similar to CodeAgentOutput)."""

    code: str = ""
    execution_output: str = ""
    steps_summary: List[str] = Field(default_factory=list)
    summary: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)
    final_answer: str = ""


class CugaLiteNode(BaseNode):
    """Node wrapper for CugaAgent - fast execution mode."""

    def __init__(self, langfuse_handler: Optional[Any] = None, prompt_template: Optional[str] = None):
        super().__init__()
        self.name = "CugaLite"
        self.prompt_template = load_one_prompt('prompts/mcp_prompt.jinja2')
        self.langfuse_handler = langfuse_handler

    @staticmethod
    async def read_text_file(file_path: str) -> Optional[str]:
        """Read text file content using filesystem tool via registry.

        Args:
            file_path: Path to the file to read

        Returns:
            File content as string, or None if failed
        """
        try:
            from cuga.backend.cuga_graph.nodes.cuga_lite.tool_registry_provider import call_api

            result = await call_api(
                app_name="filesystem", api_name="filesystem_read_text_file", args={"path": file_path}
            )

            if isinstance(result, dict):
                if "error" in result:
                    logger.error(f"Error reading file {file_path}: {result['error']}")
                    return None
                if "result" in result:
                    return result["result"]
                if "content" in result:
                    return result["content"]
                return str(result)
            elif isinstance(result, str):
                return result
            else:
                logger.error(f"Unexpected result type from read_text_file: {type(result)}")
                return None

        except Exception as e:
            logger.error(f"Exception reading file {file_path}: {e}")
            return None

    async def create_agent(self, app_names=None, task_loaded_from_file=False, is_autonomous_subtask=False):
        """Create and initialize a new CugaAgent with optional app filtering."""
        logger.info("Initializing new CugaLite agent instance...")

        langfuse_handler = self.langfuse_handler
        if langfuse_handler is None and settings.advanced_features.langfuse_tracing:
            if LangfuseCallbackHandler is not None:
                langfuse_handler = LangfuseCallbackHandler()
                logger.info("Langfuse tracing enabled for CugaLite")
            else:
                logger.warning("Langfuse tracing enabled but langfuse package not available")

        agent = CugaAgent(
            app_names=app_names,
            langfuse_handler=langfuse_handler,
            instructions=get_all_instructions_formatted(),
            task_loaded_from_file=task_loaded_from_file,
            is_autonomous_subtask=is_autonomous_subtask,
            prompt_template=self.prompt_template,
        )
        await agent.initialize()
        logger.info(f"CugaLite agent initialized with {len(agent.tools)} tools")
        return agent

    async def node(self, state: AgentState) -> Command[Literal['FinalAnswerAgent']]:
        """Execute the CugaAgent for fast task execution.

        Args:
            state: Current agent state

        Returns:
            Command to proceed to FinalAnswerAgent with the result
        """
        logger.info(f"CugaLite executing - state.input: {state.input}")
        logger.info(f"CugaLite executing - state.sub_task: {state.sub_task}")

        # Add initialization message
        # state.messages.append(
        #     AIMessage(
        #         content=json.dumps(
        #             {
        #                 "status": "initializing",
        #                 "message": f"Initializing CugaLite with {len(state.api_intent_relevant_apps) if state.api_intent_relevant_apps else 'all'} apps",
        #             }
        #         )
        #     )
        # )

        # Extract app names if available
        app_names = None

        # Use sub_task as the input if available (preferred over state.input)
        task_input = state.sub_task if state.sub_task else state.input
        is_autonomous_subtask = bool(state.sub_task)
        logger.info(f"Using task_input: {task_input}")
        logger.info(f"is_autonomous_subtask: {is_autonomous_subtask}")

        # Check if task_input is just a markdown file path and replace with file content
        task_loaded_from_file = False
        task_input_stripped = task_input.strip()
        if (
            task_input_stripped.endswith('.md')
            and '\n' not in task_input_stripped
            and ' ' not in task_input_stripped
        ):
            logger.info(f"Detected markdown file path: {task_input_stripped}")
            try:
                file_content = await self.read_text_file(task_input_stripped)
                if file_content:
                    task_input = file_content
                    task_input += "\n\nDo not use cuga_kowledge.md for the above task."
                    task_loaded_from_file = True
                    logger.info(f"Replaced task input with file content from {task_input_stripped}")
                else:
                    logger.warning(f"Failed to read file {task_input_stripped}, using original task input")
            except Exception as e:
                logger.warning(
                    f"Error reading markdown file {task_input_stripped}: {e}, using original task input"
                )

        # Determine app configuration
        if state.sub_task_app:
            app_names = [state.sub_task_app]
            logger.info(f"Using app from state.sub_task_app: {app_names}")
        elif state.api_intent_relevant_apps:
            app_names = [app.name for app in state.api_intent_relevant_apps if app.type == 'api']
            logger.info(f"Using apps from state.api_intent_relevant_apps: {app_names}")

        # Create a local agent instance for this execution
        agent = await self.create_agent(
            app_names=app_names,
            task_loaded_from_file=task_loaded_from_file,
            is_autonomous_subtask=is_autonomous_subtask,
        )

        # Add execution start message
        state.messages.append(
            AIMessage(
                content=json.dumps(
                    {
                        "status": "executing",
                        "message": f"Executing task with {len(agent.tools)} available tools",
                        "tools_count": len(agent.tools),
                    }
                )
            )
        )

        # Get current variables from state to pass as initial context
        initial_var_names = state.variables_manager.get_variable_names()
        initial_context = {}
        for name in initial_var_names:
            value = state.variables_manager.get_variable(name)
            # Convert sets to lists for JSON serialization (recursively)
            converted_value = _convert_sets_to_lists(value)
            if value is not converted_value and isinstance(value, set):
                logger.debug(f"Converted set variable '{name}' to list for serialization")
            initial_context[name] = converted_value

        logger.info(f"Passing {len(initial_context)} variables to CugaAgent as initial context")
        logger.info(f"Variable names: {initial_var_names}")
        for var_name in initial_var_names:
            logger.info(
                f"  - {var_name}: {type(initial_context[var_name]).__name__} = {str(initial_context[var_name])[:100]}"
            )
        logger.info(f"Variables summary: {state.variables_manager.get_variables_summary()}")

        # Execute the task - messages will be added automatically by CugaAgent
        # Always pass chat_messages (even if empty list) to enable conversation tracking
        # Only pass None if explicitly not set
        chat_messages_to_pass = state.chat_messages
        logger.info(
            f"Before execute: state.chat_messages has {len(chat_messages_to_pass) if chat_messages_to_pass is not None else 'None'} messages"
        )
        logger.debug(f"chat_messages content: {chat_messages_to_pass}")
        answer, metrics, updated_state_messages, updated_chat_messages = await agent.execute(
            task_input,
            recursion_limit=15,
            show_progress=False,
            state_messages=state.messages,
            chat_messages=chat_messages_to_pass,
            initial_context=initial_context,
            thread_id=state.thread_id,  # Pass thread_id for E2B sandbox caching
            state=state,
        )
        logger.info(
            f"After execute: updated_chat_messages has {len(updated_chat_messages) if updated_chat_messages is not None else 'None'} messages"
        )

        # Check if execution failed (graph-level errors or code execution errors)
        has_error = metrics is not None and metrics.get('error') is not None

        # Also check if the answer itself indicates an error
        if not has_error and answer:
            error_indicators = ['Error during execution:', 'Error:', 'Exception:', 'Traceback', 'Failed to']
            has_error = any(indicator in answer for indicator in error_indicators)
            if has_error:
                logger.warning(f"Detected error in answer content: {answer[:200]}...")

        if has_error:
            error_msg = (
                metrics.get('error', 'Code execution error detected in output')
                if metrics
                else 'Code execution error detected in output'
            )
            logger.error(f"CugaLite execution failed with error: {error_msg}")
            logger.error(f"Full answer: {answer}")

            # Update state with error information
            if state.sub_task:
                # For sub-tasks, add error to history and return to plan controller
                if state.api_planner_history:
                    state.api_planner_history[-1].agent_output = CoderAgentHistoricalOutput(
                        variables_summary="Execution failed",
                        final_output=answer,  # This already contains the error message
                    )

                state.stm_all_history.append(
                    SubTaskHistory(
                        sub_task=state.format_subtask(),
                        steps=[],
                        final_answer=answer,  # Contains error message
                    )
                )
                state.last_planner_answer = answer
                state.sender = "CugaLiteNode"
                logger.info("CugaLite sub-task execution failed, returning error to PlanControllerAgent")
                return Command(update=state.model_dump(), goto="PlanControllerAgent")
            else:
                # For regular execution, set final answer with error
                state.final_answer = answer  # Contains error message
                state.sender = self.name
                logger.info("CugaLite execution failed, proceeding to FinalAnswerAgent with error")
                return Command(update=state.model_dump(), goto="FinalAnswerAgent")

        # Update chat_messages with the updated chat conversation messages from execution
        if updated_chat_messages is not None:
            state.chat_messages = updated_chat_messages
            logger.info(
                f"Updated chat_messages with {len(updated_chat_messages)} messages for conversation history"
            )

        # Extract updated context from state messages (not chat messages) and sync to var_manager
        updated_variables = {}
        if updated_state_messages:
            for msg in reversed(updated_state_messages):
                if (
                    isinstance(msg, AIMessage)
                    and hasattr(msg, 'additional_kwargs')
                    and 'context' in msg.additional_kwargs
                ):
                    updated_variables = msg.additional_kwargs['context']
                    logger.debug(
                        f"Extracted {len(updated_variables)} updated variables from CodeAct execution"
                    )
                    break

        # Sync new variables from CodeAct execution to var_manager
        initial_var_set = set(initial_var_names)
        new_var_names = []

        if updated_variables:
            # Identify newly created variables
            for var_name, var_value in updated_variables.items():
                if not var_name.startswith('_') and var_name not in initial_var_set:
                    new_var_names.append(var_name)

            # Add all variables to state (changed from keeping only last variable for subtasks)
            vars_to_add = new_var_names
            logger.info(f"Adding {len(vars_to_add)} new variables to variables_manager")

            # Add the variables to state
            for var_name in vars_to_add:
                var_value = updated_variables[var_name]
                state.variables_manager.add_variable(
                    var_value, name=var_name, description="Generated by CugaLite"
                )
                logger.info(f"Added new variable '{var_name}' to variables_manager")

        logger.info(
            f"After execution, variables_manager now has {state.variables_manager.get_variable_count()} variables"
        )
        logger.info(f"Variable names after execution: {state.variables_manager.get_variable_names()}")

        logger.info(f"CugaLite completed in {metrics.get('duration_seconds', 0) if metrics else 0}s")
        logger.info(f"Used {metrics.get('total_tokens', 0) if metrics else 0} tokens")
        logger.info(
            f"Steps: {metrics.get('step_count', 0) if metrics else 0}, Tokens: {metrics.get('total_tokens', 0) if metrics else 0}"
        )

        # Check if answer is empty and provide a fallback
        if not answer or not answer.strip():
            logger.warning("Empty final answer detected from CugaAgent, using fallback")
            # Use the last variable's value as fallback answer
            if new_var_names and updated_variables:
                last_var_name = new_var_names[-1]
                last_var_value = updated_variables.get(last_var_name)
                if last_var_value is not None:
                    # Format the value nicely
                    if isinstance(last_var_value, (list, dict)):
                        try:
                            answer = json.dumps(last_var_value, indent=2, default=str)
                        except Exception:
                            answer = str(last_var_value)
                    else:
                        answer = str(last_var_value)
                    logger.info(f"Using last variable '{last_var_name}' value as fallback answer")
                else:
                    answer = "Task completed successfully."
                    logger.info("Using generic fallback answer (variable value is None)")
            else:
                answer = "Task completed successfully."
                logger.info("Using generic fallback answer (no variables)")

        # Log Langfuse trace ID if available
        if agent and self.langfuse_handler:
            trace_id = agent.get_langfuse_trace_id()
            if trace_id:
                logger.info(f"Langfuse Trace ID: {trace_id}")
                print(f"🔍 Langfuse Trace ID: {trace_id}")

        # Check if we're executing a sub-task
        if state.sub_task:
            # Sub-task execution - return to PlanControllerAgent
            state.api_last_step = ActionName.CONCLUDE_TASK
            state.guidance = None

            # Add to previous steps

            # Update api_planner_history with CoderAgentHistoricalOutput
            if state.api_planner_history:
                # Use the new variable names that were actually added to variables_manager
                state.api_planner_history[-1].agent_output = CoderAgentHistoricalOutput(
                    variables_summary=state.variables_manager.get_variables_summary(
                        new_var_names, max_length=5000
                    )
                    if new_var_names
                    else "No new variables",
                    final_output=answer,
                )

            state.stm_all_history.append(
                SubTaskHistory(
                    sub_task=state.format_subtask(),
                    steps=[],
                    final_answer=answer,
                )
            )
            logger.debug(
                "finished task stm_all_history last object: {}".format(
                    state.stm_all_history[-1].model_dump_json()
                )
            )
            state.last_planner_answer = answer
            state.sender = "CugaLiteNode"

            logger.info("CugaLite sub-task execution successful, proceeding to PlanControllerAgent")
            logger.info(f"Variables before return - Count: {state.variables_manager.get_variable_count()}")
            logger.info(f"Variables before return - Names: {state.variables_manager.get_variable_names()}")
            logger.info(f"Variables before return - Storage keys: {list(state.variables_storage.keys())}")
            logger.info(f"Variables before return - Counter: {state.variable_counter_state}")
            logger.info(f"Variables before return - Creation order: {state.variable_creation_order}")

            return Command(update=state.model_dump(), goto="PlanControllerAgent")
        else:
            # Regular execution - proceed to FinalAnswerAgent
            state.final_answer = answer
            state.sender = self.name
            logger.info("CugaLite execution successful, proceeding to FinalAnswerAgent")
            return Command(update=state.model_dump(), goto="FinalAnswerAgent")
