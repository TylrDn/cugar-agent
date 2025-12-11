import json
import uuid
import time
from uuid import UUID

from langgraph.types import Command

from cuga.backend.activity_tracker.tracker import ActivityTracker
from cuga.backend.browser_env.browser.extension_env_async import ExtensionEnv
from cuga.backend.cuga_graph.nodes.browser.action_agent.tools.tools import format_tools
from cuga.backend.cuga_graph.nodes.task_decomposition_planning.plan_controller_agent.prompts.load_prompt import (
    PlanControllerOutput,
)
from cuga.backend.cuga_graph.nodes.browser.browser_planner_agent.prompts.load_prompt import NextAgentPlan
from cuga.backend.cuga_graph.nodes.browser.qa_agent.prompts.load_prompt import QaAgentOutput
from cuga.backend.cuga_graph.nodes.task_decomposition_planning.task_decomposition_agent.prompts.load_prompt import (
    TaskDecompositionPlan,
    TaskDecompositionMultiOutput,
)
from cuga.backend.browser_env.browser.gym_env_async import BrowserEnvGymAsync
from cuga.config import settings
from pydantic import TypeAdapter
import logging
from typing import Generator, List, Optional, Union, Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.outputs import LLMResult
from langgraph.graph.state import CompiledStateGraph
from loguru import logger
from pydantic import BaseModel
from enum import Enum

from cuga.backend.cuga_graph.state.agent_state import AgentState


class OutputFormat(str, Enum):
    WXO = "wxo"
    DEFAULT = "default"


class TokenUsageTracker(AsyncCallbackHandler):
    def __init__(self, tracker: ActivityTracker):
        self.tracker = tracker

    async def on_llm_end(self, response: LLMResult, **kwargs):
        generation = response.generations[0][0].text
        self.tracker.collect_prompt(role="assistant", value=generation)
        self.tracker.collect_tokens_usage(response.llm_output.get("token_usage").get("total_tokens"))

    def split_system_human(self, text):
        """
        Splits text into system and human parts based on 'System: ' and '\nHuman: ' markers.

        Args:
            text (str): Input text to split

        Returns:
            tuple: (system_part, human_part) where markers and newlines are removed
        """
        system_part = ""
        human_part = ""

        # Check if text contains the required markers
        has_system = "System: " in text
        has_human = "\nHuman: " in text

        if has_system and has_human:
            # Find the positions of the markers
            system_pos = text.find("System: ")
            human_pos = text.find("\nHuman: ")

            # Extract system part (remove "System: ")
            if system_pos < human_pos:
                system_start = system_pos + len("System: ")
                system_part = text[system_start:human_pos].strip()

            # Extract human part (remove "\nHuman: ")
            human_start = human_pos + len("\nHuman: ")
            human_part = text[human_start:].strip()

        elif has_system:
            # Only system marker found
            system_pos = text.find("System: ")
            system_start = system_pos + len("System: ")
            system_part = text[system_start:].strip()

        elif has_human:
            # Only human marker found
            human_pos = text.find("\nHuman: ")
            human_start = human_pos + len("\nHuman: ")
            human_part = text[human_start:].strip()

        return system_part, human_part

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        pmt = prompts[0]
        result1 = self.split_system_human(pmt)
        if result1:
            system1, human1 = result1
            self.tracker.collect_prompt(role="system", value=system1)
            self.tracker.collect_prompt(role="human", value=human1)
        else:
            self.tracker.collect_prompt(role="system", value=pmt)


class AgentLoopAnswer(BaseModel):
    """
    Model representing the answer from the agent loop.
    """

    end: bool
    interrupt: bool = False
    answer: Optional[Any] = None
    has_tools: bool = False
    tools: List[ToolCall]
    flow_generalized: Optional[bool] = False


class StreamEvent(BaseModel):
    """
    Model representing a stream event.
    """

    name: str
    data: str

    @staticmethod
    def format_data(data_str: str) -> str:
        """
        - If data_str isn’t valid JSON, returns it unchanged.
        - If it’s a JSON object with exactly one key whose value is a string, returns that string.
        - Otherwise, returns a markdown-formatted JSON code block.
        """
        try:
            parsed: Any = json.loads(data_str)
        except (ValueError, TypeError):
            return data_str

        if isinstance(parsed, dict) and len(parsed.keys()) == 1:
            value = next(iter(parsed.values()))
            if isinstance(value, str):
                return value

        pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        return f"```json\n{pretty}\n```"

    @staticmethod
    def parse(formatted_str: str) -> 'StreamEvent':
        """
        Parses a formatted string back into a StreamEvent.
        Handles formats like:
            event: EventName
            data: some data

        Now correctly handles data that contains newlines by parsing from the last \n\n.
        """

        # Find the last occurrence of \n\n to split the string
        last_double_newline = formatted_str.rfind('\n\n')

        if last_double_newline == -1:
            raise ValueError("No double newline (\\n\\n) found in formatted string")

        # Split at the last \n\n - everything before is the event block
        event_block = formatted_str[:last_double_newline].strip()
        lines = event_block.split('\n', 1) if event_block else []

        name = None
        data = None

        # Parse the event block (everything before the last \n\n)
        for line in lines:
            if line.startswith('event: '):
                name = line[7:].strip()  # Remove 'event: '
            elif line.startswith('data: '):
                # For data lines, we need to handle the case where data might span multiple lines
                # Everything after 'data: ' in the event block, plus everything after the last \n\n
                data_start = line[6:]  # Remove 'data: ', preserve any leading spaces

                # Append everything after the last \n\n as part of the data
                remaining_data = formatted_str[last_double_newline + 2 :]
                data = data_start + '\n' + remaining_data if data_start else remaining_data
                break  # Found data line, no need to continue

        # If we didn't find data in the event block, check if everything after last \n\n is data
        if data is None:
            data = formatted_str[last_double_newline + 2 :]

        if name is None:
            raise ValueError("No 'event:' line found in formatted string")
        if data is None:
            data = ""

        return StreamEvent(name=name, data=data)

    @staticmethod
    def format_event(raw_event: str) -> str:
        """
        Takes a string like:
            event: Foo
            data: {...}

        Parses only what comes after 'data: ', runs format_data on it,
        and then reconstructs the full event block.
        """
        if not hasattr(raw_event, "partition"):
            if hasattr(raw_event, "answer"):
                head = "FinalAnswer"
                answer = StreamEvent.format_data(raw_event.answer)
                return f"---\n\n{head}data: \n\n{answer}"

        head, sep, tail = raw_event.partition("data: ")
        if not sep:
            return raw_event

        data_part, nl, rest = tail.partition("\n")
        formatted = StreamEvent.format_data(data_part)
        head = head.split(":")[1]
        return f"---\n\n{head}\n\ndata: {formatted}{nl}{rest}"

    @staticmethod
    def prepare_message(event, thread_id):
        message = {
            "id": f"msg-{uuid.uuid4()}",
            "object": "thread.message.delta",
            "thread_id": thread_id,
            "model": "langgraph-agent",
            "created": int(time.time()),
            "choices": [{"delta": {"role": "assistant", "content": StreamEvent.format_event(event)}}],
        }
        return message

    def format(self, format: OutputFormat = None, **kwargs) -> str:
        """
        Formats the stream event for output.

        :return: Formatted string of the event.
        """
        if format is OutputFormat.WXO:
            thread_id = kwargs.get("thread_id")
            message = StreamEvent.prepare_message(self.data, thread_id)
            return f"data: {json.dumps(message)}\n\n"
        elif format is OutputFormat.DEFAULT:
            if self.name == "Answer":
                return f"event: {self.name}\ndata: {self.data}\n\n"
            return self.data
        return f"event: {self.name}\ndata: {self.data}\n\n"


class AgentLoop:
    """
    A class to handle the agent loop process, managing events, streaming responses,
    and interacting with the compiled state graph.
    """

    def __init__(
        self,
        thread_id: str,
        langfuse_handler: Optional[Any],
        graph: CompiledStateGraph,
        tracker: ActivityTracker,
        env_pointer: Optional[BrowserEnvGymAsync | ExtensionEnv] = None,
        logger_name: str = 'agent_loop',
    ):
        self.env_pointer = env_pointer
        self.thread_id = thread_id
        self.langfuse_handler = langfuse_handler
        self.graph = graph
        self.tracker = tracker
        self.logger = logging.getLogger(logger_name)

    async def stream_event(self, event: StreamEvent) -> Generator[str, None, None]:
        yield event.format()

    def get_event_message(self, event: dict) -> StreamEvent:
        first_key = list(event.keys())[0]
        logger.info("Current Node: {}".format(first_key))
        if first_key == "__interrupt__":
            return StreamEvent(name=str(first_key), data="")
        state_obj = AgentState(**event[first_key])
        messages = state_obj.messages
        if messages:
            event_val = messages[-1].content
        else:
            event_val = None
        if first_key == "BrowserPlannerAgent":
            event_val = json.dumps(state_obj.previous_steps[-1].model_dump())
        if first_key == "ActionAgent":
            event_val = json.dumps(messages[-1].tool_calls)
        if first_key == 'ReuseAgent':
            event_val = messages[-1].content
        # Override CugaLite to display as CodeAgent for consistency
        if first_key == "CugaLite":
            first_key = "CodeAgent"
        logger.debug("Current Agent: {}".format(list(event.keys())))
        return StreamEvent(name=str(first_key), data=event_val or "")

    def get_stream(self, state, resume=None):
        both_none = state is None and resume is None

        callbacks = [TokenUsageTracker(self.tracker)]
        if settings.advanced_features.langfuse_tracing and self.langfuse_handler is not None:
            callbacks.insert(0, self.langfuse_handler)

        return self.graph.astream(
            state if state else Command(resume=resume.model_dump()) if not both_none else None,
            config={
                "recursion_limit": 135,
                "callbacks": callbacks,
                "thread_id": self.thread_id,
            },
            stream_mode="updates",
        )

    def get_langfuse_trace_id(self) -> Optional[str]:
        """Get the current Langfuse trace ID if available."""
        if self.langfuse_handler and hasattr(self.langfuse_handler, 'last_trace_id'):
            return self.langfuse_handler.last_trace_id
        return None

    def get_output(self, event):
        state: AgentState = AgentState(
            **self.graph.get_state({"configurable": {"thread_id": self.thread_id}}).values
        )
        msg: AIMessage = state.messages[-1] if len(state.messages) > 0 else None
        logger.info("Calling get output {}".format(",".join(list(event.keys()))))

        # Print Langfuse trace ID if available
        trace_id = self.get_langfuse_trace_id()
        if trace_id:
            print(f"Langfuse Trace ID: {trace_id}")
            logger.info(f"Langfuse Trace ID: {trace_id}")
        if "__interrupt__" in list(event.keys()):
            answer = ""
            if msg.tool_calls and len(msg.tool_calls) > 0:
                return AgentLoopAnswer(
                    end=False, interrupt=True, has_tools=True, answer=msg.content, tools=msg.tool_calls
                )
            else:
                return AgentLoopAnswer(end=True, interrupt=True, has_tools=False, answer=answer, tools=[])

        if "ReuseAgent" in list(event.keys()):
            return AgentLoopAnswer(
                end=True,
                has_tools=False,
                answer=f"Done!\n---\n [Click here for an explained walkthrough of the flow](http://localhost:{settings.server_ports.demo}/flows/flow.html)",
                flow_generalized=True,
                tools=msg.tool_calls,
            )

        if "FinalAnswerAgent" in list(event.keys()) or "CodeAgent" in list(event.keys()):
            return AgentLoopAnswer(end=True, has_tools=False, answer=state.final_answer, tools=msg.tool_calls)
        else:
            return AgentLoopAnswer(end=False, has_tools=True, answer=msg.content, tools=msg.tool_calls)

    async def run_stream(self, state: Optional[AgentState] = None, resume=None):
        event_stream = self.get_stream(state, resume)
        event = {}
        async for event in event_stream:
            event_msg = self.get_event_message(event)
            # logger.debug(f"current event: {event_msg.format()}")
            yield event_msg.format()
        yield self.get_output(event)

    def get_output_of_obj(self, dict):
        msg = ""
        for key, val in dict.items():
            if isinstance(val, list):
                list_items = '\n'.join([f'{i}. {va}' for i, va in enumerate(val)])
                msg += f"**{key}**: {list_items}\n\n"
            else:
                msg += f"**{key}**: {val}\n\n"
        return msg

    async def show_chat_even(self, event: StreamEvent):
        if self.env_pointer and self.env_pointer.chat:
            if event.name == "TaskDecompositionAgent":
                msg = "TaskDecompositionAgent\n:"
                DataType = TypeAdapter(Union[TaskDecompositionPlan, TaskDecompositionMultiOutput])
                task_decomposition_plan = DataType.validate_json(event.data)
                msg += self.get_output_of_obj(task_decomposition_plan.model_dump())
                await self.env_pointer.send_chat_message(
                    role="assistant",
                    content=msg,
                )
            if event.name == "BrowserPlannerAgent":
                msg = "PlannerAgent:\n"
                p = NextAgentPlan(**json.loads(event.data))
                msg += self.get_output_of_obj(p.model_dump())
                await self.env_pointer.send_chat_message(
                    role="assistant",
                    content=msg,
                )
            if event.name == "ActionAgent":
                p = json.loads(event.data)
                await self.env_pointer.send_chat_message(
                    role="assistant", content="Actions:\n {}".format(format_tools(p))
                )
            if event.name == "QaAgent":
                p = QaAgentOutput(**json.loads(event.data))
                await self.env_pointer.send_chat_message(
                    role="assistant", content="{} - {}".format(p.name, p.answer)
                )
            if event.name == "PlanControllerAgent":
                p = PlanControllerOutput(**json.loads(event.data))
                await self.env_pointer.send_chat_message(
                    role="assistant", content="Plan Controller - next subtask is: {}".format(p.next_subtask)
                )

    async def run(self, state: Optional[AgentState] = None, resume=None):
        event_stream = self.get_stream(state, resume)
        event = {}
        async for event in event_stream:
            event_msg = self.get_event_message(event)
            await self.show_chat_even(event_msg)
            # logger.debug(f"current event: {event_msg.format()}")
        return self.get_output(event)
