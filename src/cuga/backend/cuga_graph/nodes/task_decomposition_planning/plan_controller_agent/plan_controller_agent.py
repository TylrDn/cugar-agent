import json
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from cuga.backend.activity_tracker.tracker import ActivityTracker
from cuga.backend.cuga_graph.nodes.shared.base_agent import BaseAgent
from cuga.backend.cuga_graph.state.agent_state import AgentState
from cuga.backend.cuga_graph.nodes.task_decomposition_planning.plan_controller_agent.prompts.load_prompt import (
    PlanControllerOutput,
    parser,
)
from cuga.backend.llm.models import LLMManager
from cuga.backend.llm.utils.helpers import load_prompt_simple
from cuga.config import settings
from cuga.configurations.instructions_manager import InstructionsManager
from loguru import logger

instructions_manager = InstructionsManager()
tracker = ActivityTracker()
llm_manager = LLMManager()


class PlanControllerAgent(BaseAgent):
    def __init__(self, prompt_template: ChatPromptTemplate, llm: BaseChatModel, tools: Any = None):
        super().__init__()
        self.name = "PlanControllerAgent"
        parser = RunnableLambda(PlanControllerAgent.output_parser)
        # if not enable_format:
        self.chain = BaseAgent.get_chain(prompt_template, llm, PlanControllerOutput) | (
            parser.bind(name=self.name)
        )

        # else:
        # self.chain = prompt_template | llm | controller_step_parser | (parser.bind(name=self.name))

    @staticmethod
    def output_parser(result: PlanControllerOutput, name) -> Any:
        logger.debug(
            f"\n\n------\n\nPlanControllerOutput: {json.dumps(result.model_dump(), indent=4)} \n\n------\n\n"
        )
        result = AIMessage(content=json.dumps(result.model_dump()), name=name)
        return result

    async def run(self, input_variables: AgentState) -> AIMessage:
        logger.info(
            f"PlanControllerAgent received - Variables count: {input_variables.variables_manager.get_variable_count()}"
        )
        logger.info(
            f"PlanControllerAgent received - Variables names: {input_variables.variables_manager.get_variable_names()}"
        )
        logger.info(
            f"PlanControllerAgent received - Storage keys: {list(input_variables.variables_storage.keys())}"
        )
        logger.info(f"PlanControllerAgent received - Counter: {input_variables.variable_counter_state}")
        logger.info(
            f"PlanControllerAgent received - Creation order: {input_variables.variable_creation_order}"
        )

        task_input = {
            "task_decomposition": input_variables.task_decomposition.format_as_list(),
            "stm_all_history": [item.model_dump() for item in input_variables.stm_all_history]
            if input_variables.stm_all_history
            else [],
        }
        data = input_variables.model_dump()
        if tracker.images and len(tracker.images) > 0:
            data["img"] = tracker.images[-1]
        data["task_decomposition"] = task_input["task_decomposition"]
        data["stm_all_history"] = task_input["stm_all_history"]
        data["sub_tasks_progress"] = input_variables.sub_tasks_progress or []
        data["variables_history"] = input_variables.variables_manager.get_variables_summary(last_n=15)
        logger.info(
            f"Variables history being passed to prompt (length: {len(data['variables_history'])} chars):"
        )
        logger.info(
            f"{data['variables_history'][:500]}..."
            if len(data['variables_history']) > 500
            else data['variables_history']
        )
        data["instructions"] = instructions_manager.get_instructions(self.name)
        # Add API applications list
        data["api_applications_list"] = [
            app.name for app in input_variables.api_intent_relevant_apps or [] if app.type == 'api'
        ]
        result = await self.chain.ainvoke(data)
        return result

    @staticmethod
    def create():
        dyna_model = settings.agent.plan_controller.model
        return PlanControllerAgent(
            prompt_template=load_prompt_simple(
                "./prompts/system.jinja2",
                "./prompts/user.jinja2",
                model_config=dyna_model,
                format_instructions=BaseAgent.get_format_instructions(parser),
            ),
            llm=llm_manager.get_model(dyna_model),
        )
