#!/usr/bin/env python3
"""
Trajectory Intermediate Representation (IR) Generator

Converts raw CUGA trajectory logs into structured IR format suitable for tips extraction.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict

from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)

# Import LLM for optional evaluation analysis
try:
    from cuga.backend.memory.agentic_memory.config import tips_extractor_config
    from cuga.backend.memory.agentic_memory.utils.utils import get_chat_model

    LLM_AVAILABLE = True
except ImportError as e:
    LLM_AVAILABLE = False
    logger.warning(f"LLM functionality not available for IR generation: {e}")


def extract_content_from_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """Extract thoughts, status, analysis, and other content from a trajectory step."""
    agent_name = step.get("name", "unknown")
    result = {
        "thoughts": None,
        "status": None,
        "analysis": None,
        "other": None,
        "evaluation_report": None,
        "test_analysis": None,
        "task_decomposition_result": None,
        "prompts_content": None,
    }
    # Handle TaskAnalyzerAgent special case: output is in the last prompt
    if agent_name == "TaskAnalyzerAgent" and step.get("prompts"):
        prompts = step["prompts"]
        if prompts and len(prompts) > 0:
            last_prompt = prompts[-1]
            if last_prompt.get("role") == "assistant" and last_prompt.get("value"):
                try:
                    # Parse the assistant's response which is typically JSON
                    assistant_data = json.loads(last_prompt["value"])
                    if isinstance(assistant_data, dict):
                        if "thoughts" in assistant_data:
                            thoughts = assistant_data["thoughts"]
                            if isinstance(thoughts, list):
                                result["thoughts"] = " ".join(thoughts)
                            elif isinstance(thoughts, str):
                                result["thoughts"] = thoughts
                        if "relevant_apps" in assistant_data:
                            result["analysis"] = (
                                f"Selected apps: {', '.join(assistant_data['relevant_apps'])}"
                            )
                except (json.JSONDecodeError, TypeError):
                    result["other"] = last_prompt["value"]

    # Handle EvaluationResult special case: extract the report
    if agent_name == "EvaluationResult" and step.get("data"):
        try:
            data = json.loads(step["data"]) if isinstance(step["data"], str) else step["data"]
            if isinstance(data, dict) and "report" in data:
                # Decode the report which contains evaluation details
                report = data["report"]
                # Clean up unicode escape sequences
                report = report.replace("\u2500", "-")
                result["evaluation_report"] = report

                # Flag for LLM analysis of the complete evaluation report
                result["needs_llm_evaluation_analysis"] = True  # Flag for LLM analysis
                result["analysis"] = "Evaluation attempted using LLM - see output for details"
        except Exception:
            result["other"] = str(step.get("data", ""))

    # Process the data field for all other agents
    if step.get("data") and agent_name not in ["TaskAnalyzerAgent", "EvaluationResult"]:
        try:
            # Parse data field
            data = json.loads(step["data"]) if isinstance(step["data"], str) else step["data"]

            if isinstance(data, dict):
                # TaskDecompositionAgent - extract task_decomposition
                if agent_name == "TaskDecompositionAgent" and "task_decomposition" in data:
                    tasks = data["task_decomposition"]
                    if isinstance(tasks, list):
                        task_descriptions = [
                            task.get("task", str(task)) for task in tasks if isinstance(task, dict)
                        ]
                        result["task_decomposition_result"] = (
                            f"Decomposed into {len(task_descriptions)} tasks: {'; '.join(task_descriptions)}"
                        )

                # Extract thoughts from various formats
                if "thoughts" in data:
                    thoughts = data["thoughts"]
                    if isinstance(thoughts, list):
                        result["thoughts"] = " ".join(str(t) for t in thoughts)
                    elif isinstance(thoughts, str):
                        result["thoughts"] = thoughts

                # Extract status and analysis fields
                analysis_fields = ["Overall Status/Analysis", "overall_status", "status", "summary", "answer"]
                for field in analysis_fields:
                    if field in data and not result["analysis"]:
                        result["analysis"] = str(data[field])
                        break

                # Reasoning field
                if "reasoning" in data and not result["thoughts"]:
                    result["thoughts"] = str(data["reasoning"])

                # Plan field
                if "plan" in data:
                    plan_data = data["plan"]
                    if isinstance(plan_data, dict) and "reasoning" in plan_data and not result["thoughts"]:
                        result["thoughts"] = str(plan_data["reasoning"])
                    elif isinstance(plan_data, str) and not result["analysis"]:
                        result["analysis"] = plan_data

                # Code execution results
                if "code" in data and "output" in data:
                    output_info = data.get("output", {})
                    if isinstance(output_info, dict):
                        vars_saved = output_info.get("variables_saved", [])
                        result["status"] = (
                            f"Code executed. Variables: {', '.join(vars_saved) if vars_saved else 'none'}"
                        )

                # API responses and results
                if "result" in data and not result["analysis"]:
                    result_data = data["result"]
                    if isinstance(result_data, list):
                        result["analysis"] = f"Found {len(result_data)} results"
                    elif isinstance(result_data, dict):
                        result["status"] = "API call successful"
                    else:
                        result["status"] = f"Result: {str(result_data)}"

                # Report field (common in evaluation agents)
                if "report" in data and not result["analysis"]:
                    report = str(data["report"])
                    result["analysis"] = report

            elif isinstance(data, list) and len(data) > 0:
                # List of thoughts (APIPlannerAgent format)
                if all(isinstance(item, str) for item in data):
                    result["thoughts"] = " ".join(data)
                # List of results
                else:
                    result["analysis"] = f"List of {len(data)} items"

            elif isinstance(data, str):
                # Direct string data
                result["analysis"] = data

        except Exception:
            # If parsing fails, show raw data
            data_str = str(step.get("data", ""))
            result["other"] = data_str

    # If no data field but has prompts (fallback for some agents)
    if not any(
        [
            result["thoughts"],
            result["analysis"],
            result["status"],
            result["other"],
            result["evaluation_report"],
            result["task_decomposition_result"],
        ]
    ):
        if step.get("prompts") and len(step["prompts"]) > 0:
            # Check if there are any human or assistant messages with content
            content_messages = []
            for prompt in step["prompts"]:
                if prompt.get("role") in ["human", "assistant"] and prompt.get("value"):
                    content_messages.append(f"{prompt['role']}: {prompt['value']}")
            if content_messages:
                result["prompts_content"] = " | ".join(content_messages)

    return result


def analyze_evaluation_with_llm(evaluation_report: str, llm) -> Dict[str, Any]:
    """Use LLM to analyze the complete evaluation report and provide intelligent synopsis."""
    if not llm or not evaluation_report:
        return {"error": "No LLM available or no evaluation report"}

    # Load prompt template from Jinja2 file
    current_dir = os.path.dirname(__file__)
    prompt_file = os.path.join(current_dir, "prompts/trajectory_eval_analysis.jinja2")
    evaluation_analysis_prompt = PromptTemplate.from_file(
        prompt_file, template_format="jinja2", encoding="utf-8"
    )

    # Format prompt with evaluation report
    prompt_input = {"evaluation_report": evaluation_report}
    formatted_prompt = evaluation_analysis_prompt.format(**prompt_input)

    try:
        response = llm.invoke(formatted_prompt)
        # Handle the response content
        if hasattr(response, "content"):
            content = response.content
        else:
            content = str(response)

        # Try to extract JSON from the response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            llm_analysis = json.loads(json_match.group())
        else:
            # Try direct parse
            llm_analysis = json.loads(content)

        return llm_analysis

    except Exception as e:
        return {
            "error": f"LLM analysis failed: {str(e)}",
            "test_summary": {"passed_count": 0, "failed_count": 0, "total_count": 0},
            "passed_tests": [],
            "failed_tests": [],
            "overall_assessment": "Could not analyze evaluation report with LLM",
        }


def generate_trajectory_ir(
    trajectory_data: Dict[str, Any], analyze_evaluations: bool = True
) -> Dict[str, Any]:
    """
    Generate intermediate representation from raw trajectory data.

    This is the main function to call for IR generation without printing/saving files.

    Args:
        trajectory_data: Raw trajectory JSON data (must have 'steps' and 'intent')
        analyze_evaluations: Whether to use LLM to analyze evaluation reports (default: True)

    Returns:
        Dictionary containing structured IR with steps_analyzed array
    """
    logger.info("Generating trajectory intermediate representation...")

    # Create output IR structure
    output_data = {
        "analysis_timestamp": datetime.now().isoformat(),
        "task_intent": trajectory_data.get("intent", "Unknown task"),
        "total_steps": len(trajectory_data.get("steps", [])),
        "steps_analyzed": [],
    }

    # Initialize LLM if needed for evaluation analysis
    llm = None
    if analyze_evaluations and LLM_AVAILABLE:
        try:
            llm = get_chat_model(tips_extractor_config)
            logger.info("LLM initialized for evaluation analysis")
        except Exception as e:
            logger.warning(f"Could not initialize LLM for evaluation analysis: {e}")

    steps = trajectory_data.get("steps", [])

    for i, step in enumerate(steps):
        step_name = step.get("name", "unknown")
        content = extract_content_from_step(step)

        # Create step data for IR
        step_data = {
            "step_index": i,
            "agent_name": step_name,
            "thoughts": content["thoughts"],
            "status": content["status"],
            "analysis": content["analysis"],
            "raw_data": content["other"],
            "evaluation_report": content["evaluation_report"],
            "test_analysis": content["test_analysis"],
            "task_decomposition_result": content["task_decomposition_result"],
            "prompts_content": content["prompts_content"],
        }

        # Perform LLM evaluation analysis if this is an EvaluationResult
        if content.get("needs_llm_evaluation_analysis") and llm and content.get("evaluation_report"):
            try:
                llm_analysis = analyze_evaluation_with_llm(content["evaluation_report"], llm)
                step_data["llm_evaluation_analysis"] = llm_analysis
                logger.debug(f"Added LLM evaluation analysis for step {i}")
            except Exception as e:
                logger.warning(f"LLM evaluation analysis failed for step {i}: {e}")
                step_data["llm_evaluation_analysis"] = {
                    "overall_assessment": "LLM analysis failed",
                    "passed_tests": [],
                    "failed_tests": [],
                }

        output_data["steps_analyzed"].append(step_data)

    logger.info(f"Generated IR for {len(steps)} steps")
    return output_data
