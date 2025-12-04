"""
V1 Memory Client for Self-Hosted Service
This client interfaces with the self-hosted Memory v1 API endpoints.
"""

import httpx
from typing import List, Dict, Optional, Any

from cuga.backend.memory.agentic_memory.schema import Fact, Message, RecordedFact, Run, Namespace
from cuga.backend.memory.agentic_memory.client.exceptions import (
    NamespaceNotFoundException,
    FactNotFoundException,
    APIRequestException,
)


class V1MemoryClient:
    """
    V1 client for self-hosted Memory service.
    Interfaces with the v1 API endpoints for namespace and fact management.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = 60.0):
        """
        Initialize the V1 Memory client.

        Args:
            base_url: Base URL of the self-hosted Memory service (e.g., "http://localhost:8000")
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds (default: 60.0)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

        # Prepare headers
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        # Add API key to headers if provided
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Initialize httpx client with headers and timeout configuration
        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout, connect=10.0),  # configurable timeout, 10s connect timeout
            transport=httpx.HTTPTransport(retries=3),
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close the client."""
        self.close()

    def close(self):
        """Close the httpx client and cleanup resources."""
        if hasattr(self, 'client'):
            self.client.close()

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Make a request to the Memory v1 service.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            **kwargs: Additional arguments for httpx

        Returns:
            Response data (json parsed or raw text for some endpoints)

        Raises:
            APIRequestException: If the request fails
            NamespaceNotFoundException: If namespace is not found (404)
            FactNotFoundException: If fact is not found (404)
        """
        try:
            response = self.client.request(method, endpoint, **kwargs)

            # Handle specific error cases
            if response.status_code == 404:
                if '/namespaces/' in endpoint and '/facts/' in endpoint:
                    raise FactNotFoundException(f"Fact not found: {endpoint}")
                elif '/namespaces/' in endpoint:
                    raise NamespaceNotFoundException(f"Namespace not found: {endpoint}")

            response.raise_for_status()

            # Handle different response types
            if response.status_code == 204:  # No content
                return None

            # Try to parse as JSON, fall back to text
            try:
                return response.json()
            except ValueError:
                return response.text

        except httpx.RequestError as e:
            raise APIRequestException(f"Memory v1 API request failed: {e}")
        except httpx.HTTPStatusError as e:
            try:
                error_detail = e.response.json()
            except ValueError:
                error_detail = e.response.text
            raise APIRequestException(
                f"Memory v1 API returned error status {e.response.status_code}: {error_detail}"
            )
        except (NamespaceNotFoundException, FactNotFoundException):
            # Re-raise these specific exceptions as-is
            raise
        except Exception as e:
            raise APIRequestException(f"Unexpected error during Memory v1 API request: {e}")

    def health_check(self) -> bool:
        """
        Check if the Memory v1 service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            result = self._make_request("GET", "/v1/health/live")
            return result.get("status") == "ok"
        except Exception:
            return False

    def create_namespace(
        self,
        namespace_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
    ) -> Namespace:
        """
        Create a new namespace for facts to exist in.

        Returns:
            The ID of the created namespace

        Raises:
            APIRequestException: If the request fails
        """
        json = {
            k: v
            for k, v in {
                "namespace_id": namespace_id,
                "user_id": user_id,
                "agent_id": agent_id,
                "app_id": app_id,
            }.items()
            if v is not None
        }
        result = self._make_request("POST", "/v1/namespaces", json=json)
        return Namespace.model_validate(result)

    def get_namespace_details(self, namespace_id: str) -> Namespace:
        """
        Get details about a specific namespace.

        Args:
            namespace_id: ID of the namespace

        Returns:
            A dictionary containing details about the namespace
        """
        result = self._make_request("GET", f"/v1/namespaces/{namespace_id}")
        return Namespace.model_validate(result)

    def search_namespaces(
        self,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        limit: int = 10,
    ) -> list[Namespace]:
        """Search namespace with filters."""
        params = {
            k: v
            for k, v in {"user_id": user_id, "agent_id": agent_id, "app_id": app_id, "limit": limit}.items()
            if v is not None
        }
        results = self._make_request("GET", "/v1/namespaces", params=params)
        return [Namespace.model_validate(result) for result in results]

    def delete_namespace(self, namespace_id: str) -> None:
        """
        Delete a namespace that facts exist in.

        Args:
            namespace_id: The namespace ID to delete

        Raises:
            NamespaceNotFoundException: If namespace doesn't exist
            APIRequestException: If the request fails
        """
        self._make_request("DELETE", f"/v1/namespaces/{namespace_id}")

    def create_and_store_fact(self, namespace_id: str, content: str, metadata: Optional[Dict] = None) -> str:
        """
        Add a single fact to a namespace.

        Args:
            namespace_id: The namespace to add the fact to
            content: The fact content
            metadata: Optional metadata for the fact

        Returns:
            The ID of the created fact

        Raises:
            NamespaceNotFoundException: If namespace doesn't exist
            APIRequestException: If the request fails
        """
        fact = Fact(content=content, metadata=metadata)

        return self._make_request("PUT", f"/v1/namespaces/{namespace_id}/facts", json=fact.model_dump())

    def search_for_facts(
        self, namespace_id: str, query: Optional[str] = None, filters: dict | None = None, limit: int = 10
    ) -> List[RecordedFact]:
        """
        Search for facts in a namespace.

        Args:
            namespace_id: The namespace to search in
            query: Optional search query. If None, returns all facts
            filters: Optional filters to apply to the fact's metadata.
            limit: Maximum number of facts to return

        Returns:
            List of recorded facts matching the query

        Raises:
            NamespaceNotFoundException: If namespace doesn't exist
            APIRequestException: If the request fails
        """
        json = {k: v for k, v in {"query": query, "filters": filters}.items() if v is not None}
        params = {"limit": limit}

        results = self._make_request("POST", f"/v1/namespaces/{namespace_id}/facts", json=json, params=params)

        # Convert raw dicts to RecordedFact objects
        return [RecordedFact.model_validate(fact) for fact in results]

    def get_all_facts(
        self, namespace_id: str, filters: dict | None = None, limit: int = 100
    ) -> List[RecordedFact]:
        """
        Get all facts from a namespace.

        Args:
            namespace_id: The namespace to get facts from
            filters: Optional filters to apply to the fact's metadata.
            limit: Maximum number of facts to return

        Returns:
            List of all recorded facts in the namespace

        Raises:
            NamespaceNotFoundException: If namespace doesn't exist
            APIRequestException: If the request fails
        """
        return self.search_for_facts(namespace_id, query=None, filters=filters, limit=limit)

    def delete_fact(self, namespace_id: str, fact_id: int) -> None:
        """
        Delete a specific fact by its ID.

        Args:
            namespace_id: The namespace containing the fact
            fact_id: The ID of the fact to delete

        Raises:
            NamespaceNotFoundException: If namespace doesn't exist
            FactNotFoundException: If fact doesn't exist
            APIRequestException: If the request fails
        """
        self._make_request("DELETE", f"/v1/namespaces/{namespace_id}/facts/{fact_id}")

    def extract_facts_from_messages(self, namespace_id: str, messages: List[Message]) -> str:
        """
        Extract facts from a list of messages and store them in the namespace.
        This is a background processing operation.

        Args:
            namespace_id: The namespace to store extracted facts in
            messages: List of messages to process

        Returns:
            Confirmation message about the number of messages processed

        Raises:
            NamespaceNotFoundException: If namespace doesn't exist
            APIRequestException: If the request fails
        """
        # Convert Message objects to dicts if needed
        message_dicts = []
        for msg in messages:
            if isinstance(msg, Message):
                message_dicts.append(msg.model_dump())
            else:
                message_dicts.append(msg)

        return self._make_request("POST", f"/v1/namespaces/{namespace_id}/messages", json=message_dicts)

    # Convenience methods for common patterns

    def create_namespace_and_add_facts(self, facts_content: List[str]) -> tuple[str, List[int]]:
        """
        Create a new namespace and add multiple facts to it.

        Args:
            facts_content: List of fact content strings

        Returns:
            Tuple of (namespace_id, list of fact_ids)
        """
        namespace = self.create_namespace()
        fact_ids = []

        for content in facts_content:
            fact_id = self.add_fact(namespace.id, content)
            fact_ids.append(fact_id)

        return namespace.id, fact_ids

    def namespace_exists(self, namespace_id: str) -> bool:
        """
        Check if a namespace exists.

        Args:
            namespace_id: The namespace ID to check

        Returns:
            True if namespace exists, False otherwise
        """
        try:
            self.get_all_facts(namespace_id, limit=1)
            return True
        except NamespaceNotFoundException:
            return False

    def create_run(self, namespace_id: str, run_id: str | None = None) -> Run:
        """
        Create a new agentic workflow run.

        Args:
            namespace_id: The namespace where the run will be created
            run_id: Optional ID to create the run with
        Returns:
            The new Run.
        """
        result = self._make_request(
            "POST",
            f"/v1/namespaces/{namespace_id}/runs",
            json={"run_id": run_id} if run_id is not None else None,
        )
        return Run.model_validate(result)

    def get_run(self, namespace_id: str, run_id: str) -> Run:
        """
        Get an existing agentic workflow run.
        Args:
            namespace_id: The namespace containing the run
            run_id: The ID of the run to get
        Returns:
            The Run
        """
        result = self._make_request("GET", f"/v1/namespaces/{namespace_id}/runs/{run_id}")
        return Run.model_validate(result)

    def delete_run(self, namespace_id: str, run_id: str):
        """
        Delete a specific run by its ID.
        Args:
            namespace_id: The namespace containing the run
            run_id: The ID of the run to delete
        """
        self._make_request("DELETE", f"/v1/namespaces/{namespace_id}/runs/{run_id}")

    def add_step(self, namespace_id: str, run_id: str, step: dict, prompt: str) -> str:
        """
        Save the results of a step into memory
        Args:
            namespace_id: The namespace containing the run
            run_id: The ID of the run
            step: An arbitrary dictionary that describes the step
            prompt: A prompt used by an LLM to parse the step into a consistent JSON schema.
        Returns:
        """
        return self._make_request(
            "POST",
            f"/v1/namespaces/{namespace_id}/runs/{run_id}/steps",
            json={
                "step": step,
                "prompt": prompt,
            },
        )

    def search_runs(
        self, namespace_id: str, query: str | None = None, filters: dict[str, str] | None = None
    ) -> Run | None:
        """
        Search a namespace for a step which best matches a query.
        Args:
            namespace_id: The namespace containing the run
            query: A sentence which best describes the desired outcome of the step.
            filters: filter based on a step's metadata which is a superset of this dictionary. Values are exact match.
        Returns:
            The entire Run containing the step which best matches the query.
        """
        result = self._make_request(
            "POST",
            f"/v1/namespaces/{namespace_id}/runs/search",
            json={
                "query": query,
                "filter": filters,
            },
        )
        return Run.model_validate(result)

    def end_run(self, namespace_id: str, run_id: str):
        """
        Declare a given run ended. This may trigger background tasks processing the data found in the run.
        Args:
            namespace_id: The namespace containing the run.
            run_id: The ID of the run.
        """
        self._make_request("POST", f"/v1/namespaces/{namespace_id}/runs/{run_id}/end")
