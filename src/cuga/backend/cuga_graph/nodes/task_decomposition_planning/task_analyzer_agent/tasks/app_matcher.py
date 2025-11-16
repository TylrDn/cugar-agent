from pydantic import BaseModel
from typing import List
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import PydanticOutputParser

from cuga.backend.llm.utils.helpers import load_prompt_simple
from cuga.backend.cuga_graph.nodes.shared.base_agent import BaseAgent
from cuga.backend.llm.models import LLMManager

llm_manager = LLMManager()


class AppMatch(BaseModel):
    """Model to define which apps are relevant for a user intent."""

    thoughts: str
    relevant_apps: List[str]


def match_apps_for_intent(model_config) -> Runnable:
    # Set up a parser
    llm = llm_manager.get_model(model_config)
    parser = PydanticOutputParser(pydantic_object=AppMatch)
    prompt_template = load_prompt_simple(
        "./prompts/app_matcher_system.jinja2",
        "./prompts/app_matcher_user.jinja2",
        model_config=model_config,
        format_instructions=BaseAgent.get_format_instructions(parser),
    )
    return BaseAgent.get_chain(prompt_template, llm, AppMatch)
