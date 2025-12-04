import json

from collections.abc import Generator

from abc import ABC, abstractmethod

from cuga.backend.memory.agentic_memory.db.sqlite_manager import SQLiteManager
from cuga.backend.memory.agentic_memory.schema import Fact, RecordedFact, Message, Run, Namespace
from cuga.backend.memory.agentic_memory.utils.logging import Logging
from cuga.backend.memory.agentic_memory.llm.tips.cuga_tips import extract_cuga_tips_from_data

logger = Logging.get_logger()


class BaseMemoryBackend(ABC):
    @abstractmethod
    def ready(self):
        pass

    @abstractmethod
    def create_namespace(
        self,
        namespace_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
    ) -> Namespace:
        pass

    @abstractmethod
    def get_namespace_details(self, namespace_id: str) -> Namespace:
        pass

    @abstractmethod
    def all_namespaces(self) -> list[Namespace]:
        pass

    @abstractmethod
    def search_namespaces(
        self,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        limit: int = 10,
    ) -> Generator[Namespace]:
        pass

    @abstractmethod
    def delete_namespace(self, namespace_id: str):
        pass

    @abstractmethod
    def create_and_store_fact(self, namespace_id: str, fact: Fact) -> str:
        pass

    @abstractmethod
    def search_for_facts(
        self, namespace_id: str, query: str | None = None, filters: dict | None = None, limit: int = 10
    ) -> list[RecordedFact]:
        pass

    @abstractmethod
    def delete_fact_by_id(self, namespace_id: str, fact_id: str):
        pass

    @abstractmethod
    def extract_facts_from_messages(self, namespace_id: str, messages: list[Message]) -> str:
        pass

    @abstractmethod
    def create_run(self, namespace_id: str, run_id: str) -> Run:
        pass

    @abstractmethod
    def delete_run(self, namespace_id: str, run_id: str):
        pass

    @abstractmethod
    def add_step(self, namespace_id: str, run_id: str, step: dict, prompt: str):
        pass

    @abstractmethod
    def get_run(self, namespace_id: str, run_id: str) -> Run:
        pass

    @abstractmethod
    def search_runs(self, namespace_id: str, query: str, filters: dict[str, str]) -> Run | None:
        pass

    def end_run(self, namespace_id: str, run_id: str):
        _ = self.get_run(namespace_id, run_id)
        with SQLiteManager() as db_manager:
            db_manager.end_run(namespace_id=namespace_id, run_id=run_id)

    async def analyze_run(self, namespace_id: str, run_id: str):
        try:
            run = self.get_run(namespace_id, run_id)

            # Extract intent from the first step (all steps should have the same intent for a task)
            intent = "Unknown task"
            if run.steps and len(run.steps) > 0:
                first_step = run.steps[0].metadata.get('step', {})
                intent = first_step.get('intent', "Unknown task")
                logger.info(f"Extracted intent from step metadata: {intent[:100]}")

            trajectory = {"steps": [step.metadata['step'] for step in run.steps], "intent": intent}
            tips_by_agent, trajectory_id = await extract_cuga_tips_from_data(trajectory)

            # Check if extraction returned an error
            if isinstance(tips_by_agent, dict) and "error" in tips_by_agent:
                logger.error(
                    f"Tips extraction failed for run {run_id} in namespace {namespace_id}: "
                    f"{tips_by_agent['error']}"
                )
                return  # Exit gracefully without storing tips

            # Check for other non-error responses that don't contain tips
            if isinstance(tips_by_agent, dict) and "message" in tips_by_agent:
                logger.warning(
                    f"Tips extraction returned message for run {run_id}: {tips_by_agent['message']}"
                )
                return

            total_tips = 0
            for agent, tips in tips_by_agent.items():
                for tip in tips:
                    tip_data = {
                        "intent": tip.intent,
                        "task_status": tip.task_status,
                        "failure_reason": tip.failure_reason,
                        "tip": tip.tip_content,
                    }

                    # Store in memory using the existing store_facts function
                    self.create_and_store_fact(
                        namespace_id,
                        Fact(
                            content=json.dumps(tip_data, indent=4),
                            metadata={
                                "type": "tips",
                                "user_id": "100",  # tips are global
                                "tip_id": tip.tip_id,
                                "agent": agent,
                                "specific_checks": tip.specific_checks,
                                "intended_use": tip.intended_use,
                                "priority": tip.priority,
                                "trajectory_id": trajectory_id,
                                "tip_type": tip.tip_type,
                                "rationale": tip.rationale,
                                "application": tip.application,
                                "task_category": tip.task_category,
                            },
                        ),
                    )
                    total_tips += 1

            logger.info(f'number of tips stored: {total_tips}')
        except Exception as e:
            logger.error(f"Failed to analyze run {run_id} in namespace {namespace_id}: {e}", exc_info=True)
            # Don't re-raise - this runs in background, we want graceful degradation
