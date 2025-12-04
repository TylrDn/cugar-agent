#!/usr/bin/env python3
"""
Tips Extractor for CUGA Agents
Analyzes trajectory outputs to generate specific tips for each agent based on failures and errors.
Provides actionable guidance to prevent future failures.
"""

import json
import re
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import uuid
from langchain_core.prompts import PromptTemplate

# Import LLM the same way as extract_tips.py
try:
    from cuga.backend.memory.agentic_memory.utils.utils import get_chat_model
    from cuga.backend.memory.agentic_memory.config import tips_extractor_config

    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("Warning: LLM not available for tips extraction.")


@dataclass
class AgentTip:
    """Represents a tip for a specific agent"""

    tip_id: str
    intent: str
    task_status: str
    failure_reason: str
    agent_name: str  # TaskAnalyzerAgent, TaskDecompositionAgent, PlanControllerAgent, APIPlannerAgent
    tip_type: str  # "error_prevention", "optimization", "validation", "recovery"
    tip_content: str  # The tip itself
    rationale: str  # Why this tip is important

    # Context
    application: Optional[str] = None  # e.g., "amazon", "gmail"
    task_category: Optional[str] = None  # e.g., "cart_management", "email_operations"
    specific_checks: List[str] = field(default_factory=list)

    # Goals/Motivation/Intended use
    intended_use: List[str] = field(default_factory=list)

    # Priority and metadata
    priority: str = "medium"  # "low", "medium", "high", "critical" - LLM's assessment of importance
    source_trajectory_id: str = ""
    source_failure: Optional[str] = None


@dataclass
class FailureAnalysis:
    """Analysis of a failure point in the trajectory"""

    failure_point: str
    failing_agent: str
    failure_description: str
    root_cause: str
    preventable_by: List[str]  # Which agents could have prevented this
    prevention_steps: Dict[str, str]  # Agent -> what they should have done


class TipsExtractor:
    """Extract actionable tips for agents from trajectory analysis"""

    AGENTS = [
        "TaskAnalyzerAgent",
        "TaskDecompositionAgent",
        "PlanControllerAgent",
        "APIPlannerAgent",
        "APIShortlisterAgent",
        "APICodePlannerAgent",
        "CodeAgent",
    ]

    def __init__(self):
        """Initialize with LLM from utils if available"""
        self.llm = None
        if LLM_AVAILABLE:
            try:
                self.llm = get_chat_model(tips_extractor_config)
            except Exception as e:
                print(f"Warning: Could not initialize LLM: {e}")

    async def extract_tips_from_trajectory(
        self,
        trajectory_text: str,
        trajectory_id: str,
        task_intent: str = "Unknown task",
        focus_on_failures: bool = True,
    ) -> Dict[str, List[AgentTip]]:
        """Extract tips for each agent from trajectory analysis"""

        if not self.llm:
            print("Error: LLM is required for tips extraction")
            return {}

        print(f"Extracting tips from trajectory {trajectory_id}")

        # First, analyze failures in the trajectory
        failures = await self._analyze_failures(trajectory_text, trajectory_id)

        # Then generate tips for each agent
        tips_by_agent = {}
        for agent in self.AGENTS:
            tips = await self._generate_tips_for_agent(
                agent, trajectory_text, failures, trajectory_id, task_intent
            )
            tips_by_agent[agent] = tips

        return tips_by_agent

    async def _analyze_failures(self, trajectory_text: str, trajectory_id: str) -> List[FailureAnalysis]:
        """Analyze failure points and determine root causes"""

        # Extract the last part of trajectory (often contains failure summaries)
        trajectory_lines = trajectory_text.split('\n')

        # Use full trajectory for context - no truncation
        # For very long trajectories, we'll let the LLM handle the context window
        full_trajectory = trajectory_text

        # Also look for FinalAnswerAgent and last APIPlannerAgent sections
        final_answer_section = ""
        last_planner_section = ""

        for i, line in enumerate(trajectory_lines):
            if "FinalAnswerAgent" in line:
                # Get the FinalAnswerAgent section (next 20 lines)
                final_answer_section = '\n'.join(trajectory_lines[i : min(i + 20, len(trajectory_lines))])
            elif "APIPlannerAgent" in line:
                # Keep updating to get the LAST APIPlannerAgent section
                last_planner_section = '\n'.join(trajectory_lines[i : min(i + 20, len(trajectory_lines))])

        # Create context with full trajectory plus highlighted key sections
        combined_context = f"""
FULL TRAJECTORY:
{full_trajectory}

--- KEY SECTIONS FOR FAILURE ANALYSIS ---

FINAL ANSWER AGENT SECTION:
{final_answer_section}

LAST API PLANNER SECTION:
{last_planner_section}
"""

        try:
            prompt_input = {"trajectory_id": trajectory_id, "combined_context": combined_context}
            current_dir = os.path.dirname(__file__)
            prompt_file = os.path.join(current_dir, "prompts/failure_analysis.jinja2")
            failure_analysis_prompt = PromptTemplate.from_file(
                prompt_file, template_format="jinja2", encoding='utf-8'
            )
            formatted_prompt = failure_analysis_prompt.format(**prompt_input)
            response = await self.llm.ainvoke(formatted_prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                failures_data = json.loads(json_match.group())
            else:
                failures_data = json.loads(content)

            failures = []
            for f in failures_data.get("failures", []):
                failures.append(
                    FailureAnalysis(
                        failure_point=f.get("failure_point", ""),
                        failing_agent=f.get("failing_agent", ""),
                        failure_description=f.get("failure_description", ""),
                        root_cause=f.get("root_cause", ""),
                        preventable_by=f.get("preventable_by", []),
                        prevention_steps=f.get("prevention_steps", {}),
                    )
                )

            return failures

        except Exception as e:
            print(f"Error analyzing failures: {e}")
            return []

    async def _generate_tips_for_agent(
        self,
        agent_name: str,
        trajectory_text: str,
        failures: List[FailureAnalysis],
        trajectory_id: str,
        task_intent: str = "Unknown task",
    ) -> List[AgentTip]:
        """Generate specific tips for an agent based on trajectory analysis"""

        # Filter failures relevant to this agent
        relevant_failures = [
            f for f in failures if agent_name in f.preventable_by or f.failing_agent == agent_name
        ]

        # Prepare failures summary - include ALL relevant failures
        failures_text = []
        for f in relevant_failures:  # No limit - use all failures for better analysis
            if agent_name in f.prevention_steps:
                failures_text.append(
                    f"- {f.failure_description}: Could have {f.prevention_steps[agent_name]}"
                )
            elif f.failing_agent == agent_name:
                failures_text.append(f"- Direct failure: {f.failure_description}")

        failures_text_joined = (
            chr(10).join(failures_text) if failures_text else 'No specific failures identified'
        )
        # Extract application and task info from trajectory
        app_context = self._extract_context(trajectory_text)

        agent_descriptions = {
            "TaskAnalyzerAgent": "Analyzes user utterances, understands task intent. Performs exactly one task -- shortlist all apps needed to accomplish utterance.",
            "TaskDecompositionAgent": "Breaks down tasks into manageable subtasks. Generally each subtask is assigned to a specific app.",
            "PlanControllerAgent": "Manages API execution and error handling across apps shortlisted by the TaskAnalyzerAgent",
            "APIPlannerAgent": "Plans API calls and data flow for a specific app",
            "APIShortlisterAgent": "Selects relevant APIs from available APIs for accomplishing the task. Critical for ensuring all necessary APIs are included.",
            "APICodePlannerAgent": "Responsible to translate a user's goal into a clear, narrative-style, step-by-step plan, describing *how* to achieve the goal using a given set of tool schemas (API definitions). This plan will guide a Coding Agent to write the actual code.",
            "CodeAgent": "AI coding agent specializing in generating Python code for API orchestration. Its primary function is to translate a detailed natural language **plan** into executable Python code that interacts with a predefined set of APIs using a specific helper function",
        }
        max_tips = tips_extractor_config.get("max_tips_per_agent", "1")

        current_dir = os.path.dirname(__file__)
        task_analyzer_prompt_file = os.path.join(current_dir, "prompts/task_analyzer.jinja2")
        api_shortlister_prompt_file = os.path.join(current_dir, "prompts/api_shortlister.jinja2")
        tips_prompt_file = os.path.join(current_dir, "prompts/tips.jinja2")
        task_analyzer_inst = PromptTemplate.from_file(
            task_analyzer_prompt_file, template_format="jinja2", encoding='utf-8'
        ).template

        api_shortlister_inst = PromptTemplate.from_file(
            api_shortlister_prompt_file, template_format="jinja2", encoding='utf-8'
        ).template

        # Add agent-specific context for better tip generation
        agent_specific_context = ""
        if agent_name == "TaskAnalyzerAgent":
            agent_specific_context = task_analyzer_inst
        elif agent_name == "APIShortlisterAgent":
            agent_specific_context = api_shortlister_inst

        # Generate tips using LLM with full trajectory context
        tips_prompt_inst = PromptTemplate.from_file(
            tips_prompt_file, template_format="jinja2", encoding='utf-8'
        )
        try:
            agent_role = agent_descriptions.get(agent_name, "Unknown")
            application = app_context.get("application", "general")
            task_category = app_context.get("task_category", "general")
            task_description = app_context.get("task_description", "")
            prompt_input = {
                "agent_name": agent_name,
                "agent_specific_context": agent_specific_context,
                "agent_role": agent_role,
                "application": application,
                "task_category": task_category,
                "task_description": task_description,
                "failures_text": failures_text_joined,
                "trajectory_snippet": trajectory_text,
                "max_tips": max_tips,
            }
            formatted_prompt = tips_prompt_inst.format(**prompt_input)
            response = await self.llm.ainvoke(formatted_prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                tips_data = json.loads(json_match.group())
            else:
                tips_data = json.loads(content)

            tips = []
            for tip_data in tips_data.get("tips", []):
                # TaskAnalyzerAgent tips should not be tied to specific applications or categories
                # since its job is to identify which apps are needed across domains
                if agent_name == "TaskAnalyzerAgent":
                    application = None
                    task_category = None
                else:
                    application = app_context.get("application")
                    task_category = app_context.get("task_category")

                tip = AgentTip(
                    tip_id=f"tip_{uuid.uuid4().hex[:8]}",
                    agent_name=agent_name,
                    task_status=tip_data.get('task_status', 'success'),
                    failure_reason=tip_data.get('failure_reason', 'completed'),
                    intent=task_intent,  # Use the task_intent from IR file instead of LLM response
                    tip_type=tip_data.get("tip_type", "error_prevention"),
                    tip_content=tip_data.get("tip_content", ""),
                    rationale=tip_data.get("rationale", ""),
                    application=application,
                    task_category=task_category,
                    specific_checks=tip_data.get("specific_checks", []),
                    intended_use=tip_data.get("intended_use", []),
                    priority=tip_data.get("priority", "medium"),
                    source_trajectory_id=trajectory_id,
                    source_failure=relevant_failures[0].failure_description if relevant_failures else None,
                )
                tips.append(tip)

            return tips

        except Exception as e:
            print(f"Error generating tips for {agent_name}: {e}")
            return []

    def _extract_context(self, trajectory_text: str) -> Dict[str, Any]:
        """Extract application and task context from trajectory"""

        context = {"application": None, "task_category": None, "task_description": None}

        # Look for application mentions
        text_lower = trajectory_text.lower()
        if "amazon" in text_lower:
            context["application"] = "amazon"
        elif "gmail" in text_lower:
            context["application"] = "gmail"
        elif "github" in text_lower:
            context["application"] = "github"

        # Look for task patterns
        if "cart" in text_lower or "shopping" in text_lower:
            context["task_category"] = "cart_management"
        elif "email" in text_lower or "message" in text_lower:
            context["task_category"] = "email_operations"
        elif "wishlist" in text_lower:
            context["task_category"] = "wishlist_management"

        # Extract task description
        task_match = re.search(r'TASK:\s*(.+?)(?:\n|$)', trajectory_text)
        if task_match:
            context["task_description"] = task_match.group(1).strip()

        return context
