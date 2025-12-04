from cuga.backend.memory.agentic_memory import V1MemoryClient
from cuga.backend.memory.agentic_memory.schema import Run, RecordedFact, Namespace
from typing import List, Dict, Optional, TYPE_CHECKING
import os
import json

from cuga.config import settings

if TYPE_CHECKING:
    from cuga.backend.cuga_graph.state.agent_state import AgentState


class Memory:
    _instance = None
    _initialized = False

    def __new__(cls, memory_config=None):
        if cls._instance is None:
            cls._instance = super(Memory, cls).__new__(cls)
        return cls._instance

    def __init__(self, memory_config=None):
        if not self._initialized:
            port = settings.server_ports.memory
            self.memory_client = V1MemoryClient(
                base_url=os.environ.get("MEMORY_BASE_URL", f"http://localhost:{port}"), timeout=600
            )
            self.user_id = None
            Memory._initialized = True

    def health_check(self) -> bool:
        return self.memory_client.health_check()

    def create_namespace(
        self,
        namespace_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
    ) -> Namespace:
        """Create a new namespace for facts to exist in."""
        return self.memory_client.create_namespace(
            namespace_id=namespace_id, user_id=user_id, agent_id=agent_id, app_id=app_id
        )

    def get_namespace_details(self, namespace_id: str) -> Namespace:
        """Get details about a specific namespace."""
        return self.memory_client.get_namespace_details(namespace_id=namespace_id)

    def search_namespaces(
        self,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        limit: int = 10,
    ) -> list[Namespace]:
        """Search namespace with filters."""
        return self.memory_client.search_namespaces(
            user_id=user_id, agent_id=agent_id, app_id=app_id, limit=limit
        )

    def delete_namespace(self, namespace_id: str):
        """Delete a namespace."""
        self.memory_client.delete_namespace(namespace_id=namespace_id)

    def create_and_store_fact(self, namespace_id: str, content: str, metadata: Optional[Dict] = None) -> str:
        """Add a single fact to a namespace."""
        return self.memory_client.create_and_store_fact(
            namespace_id=namespace_id, content=content, metadata=metadata
        )

    def search_for_facts(
        self, namespace_id: str, query: Optional[str] = None, filters: dict | None = None, limit: int = 10
    ) -> List[RecordedFact]:
        """Search for facts in a namespace."""
        return self.memory_client.search_for_facts(
            namespace_id=namespace_id, query=query, filters=filters, limit=limit
        )

    def get_all_facts(self, namespace_id: str, limit: int = 100) -> List[RecordedFact]:
        return self.memory_client.get_all_facts(namespace_id=namespace_id, limit=limit)

    def get_matching_tips(
        self,
        namespace_id: str,
        agent_id: str,
        query: str,
        limit: int = 3,
    ) -> list[str]:
        """Get matching facts and return them as JSON string.

        This provides backward compatibility with the old get_matching_facts function
        while using the new V1MemoryClient internally.
        """
        recorded_facts = self.search_for_facts(
            namespace_id=namespace_id, query=query, limit=limit, filters={"agent": agent_id, "user_id": "100"}
        )

        # Extract facts from the response (assuming similar structure to old implementation)
        facts = [fact.content for fact in recorded_facts]

        # Print debug info (maintaining original behavior)
        print(query)
        print("------ICLs--------")
        for f in facts:
            print(f)

        return facts

    def create_run(self, namespace_id: str, run_id: str | None = None) -> Run:
        """Create a new run to track Agent steps."""
        return self.memory_client.create_run(namespace_id, run_id)

    def get_run(self, namespace_id: str, run_id: str) -> Run:
        """Get an existing run."""
        return self.memory_client.get_run(namespace_id, run_id)

    def delete_run(self, namespace_id: str, run_id: str):
        """Delete an existing run."""
        return self.memory_client.delete_run(namespace_id, run_id)

    def search_runs(
        self, namespace_id: str, query: str | None = None, filters: dict[str, str] | None = None
    ) -> Run | None:
        """Search a namespace for a run based on it's step which best matches a query."""
        return self.memory_client.search_runs(namespace_id, query, filters)

    def end_run(self, namespace_id: str, run_id: str):
        """End an existing run."""
        return self.memory_client.end_run(namespace_id, run_id)

    def add_step(self, namespace_id: str, run_id: str, step: dict, prompt: str) -> str:
        """Add a new step into a run."""
        return self.memory_client.add_step(namespace_id, run_id, step, prompt)

    def _get_user_id(self, state: "AgentState") -> str:
        """Extract or generate user ID for memory scoping"""
        # Use the pi field from AgentState
        if hasattr(state, 'pi') and state.pi:
            pi_dict = json.loads(state.pi)
            state.user_id = str(f"{pi_dict["first_name"]}_{pi_dict["last_name"]}_{pi_dict["phone_number"]}")
        else:
            state.user_id = "default_user"
        self.user_id = state.user_id
        return state.user_id
