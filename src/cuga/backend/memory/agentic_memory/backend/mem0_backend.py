from collections.abc import Generator
from json import JSONDecodeError

import json
import uuid

from cuga.backend.memory.agentic_memory.backend.base import BaseMemoryBackend
from cuga.backend.memory.agentic_memory.db.sqlite_manager import SQLiteManager
from cuga.backend.memory.agentic_memory.config import get_config
from cuga.backend.memory.agentic_memory.schema import Fact, RecordedFact, Message, Run, Namespace
from cuga.backend.memory.agentic_memory.utils.utils import clean_llm_response
from fastapi import HTTPException
from mem0 import Memory
from mem0.configs.base import MemoryConfig
from mem0.llms.base import LLMBase
from pymilvus import MilvusClient


class Mem0MemoryBackend(BaseMemoryBackend):
    # Cache for backend namespaces
    namespaces: dict[str, Memory] = {}

    def ready(self) -> bool:
        return True

    def _cache_namespace(self, namespace_id: str) -> Memory:
        config = get_config(namespace_id)
        memory = Memory(config=MemoryConfig.model_validate(config))
        if namespace_id not in self.namespaces:
            self.namespaces[namespace_id] = memory
        return memory

    def _get_namespace(self, namespace_id: str) -> Memory:
        memory = self.namespaces.get(namespace_id)
        if memory is None:
            with SQLiteManager() as db_manager:
                namespace = db_manager.get_namespace(namespace_id)
            if namespace:
                memory = self._cache_namespace(namespace_id)
            else:
                raise LookupError(f"Namespace `{namespace_id}` not found")
        return memory

    def create_namespace(
        self,
        namespace_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
    ) -> Namespace:
        namespace_id = namespace_id or 'ns_' + str(uuid.uuid4()).replace('-', '_')
        self._cache_namespace(namespace_id)

        with SQLiteManager() as db_manager:
            return db_manager.create_namespace(namespace_id, user_id, agent_id, app_id)

    def get_namespace_details(self, namespace_id: str) -> Namespace:
        # TODO: add e.g. number of records
        # memory = self._get_namespace(namespace_id=namespace_id)

        with SQLiteManager() as db_manager:
            namespace = db_manager.get_namespace(namespace_id)
            if namespace is None:
                raise LookupError(f"Namespace `{namespace_id}` not found")
            return namespace

    def all_namespaces(self) -> list[Namespace]:
        with SQLiteManager() as db_manager:
            return db_manager.all_namespaces()

    def search_namespaces(
        self,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        limit: int = 10,
    ) -> Generator[Namespace]:
        with SQLiteManager() as db_manager:
            yield from db_manager.search_namespaces(user_id, agent_id, app_id, limit)

    def delete_namespace(self, namespace_id: str):
        try:
            memory = self._cache_namespace(namespace_id)
            milvus: MilvusClient = memory.vector_store.client
            milvus.drop_collection(collection_name=namespace_id)
        except Exception:
            pass
        self.namespaces.pop(namespace_id, None)
        with SQLiteManager() as db_manager:
            db_manager.delete_namespace(namespace_id)

    def create_and_store_fact(self, namespace_id: str, fact: Fact) -> str:
        memory = self._get_namespace(namespace_id=namespace_id)
        user_id = fact.metadata.get('user_id')
        added_fact = memory.add(fact.content, user_id=user_id, metadata=fact.metadata, infer=False)['results']
        if len(added_fact) > 0:
            return added_fact[0]['id']
        else:
            return memory.search(query=fact.content, user_id='default_user')['results'][0]['id']

    def _result_to_fact(self, result: dict) -> RecordedFact:
        return RecordedFact(
            id=result['id'],
            content=result['memory'],
            metadata=result['metadata'],
            created_at=result['created_at'],
            run_id=result.get('run_id'),
        )

    def search_for_facts(
        self, namespace_id: str, query: str | None = None, filters: dict | None = None, limit: int = 10
    ) -> list[RecordedFact]:
        memory = self._get_namespace(namespace_id=namespace_id)
        filters = filters or {}
        user_id = filters.get('user_id')
        agent_id = filters.get('agent_id')
        run_id = filters.get('run_id')
        if query is None:
            return [
                self._result_to_fact(result)
                for result in memory.get_all(
                    user_id=user_id, agent_id=agent_id, run_id=run_id, filters=filters, limit=limit
                )['results']
            ]
        else:
            return [
                self._result_to_fact(result)
                for result in memory.search(
                    query=query,
                    user_id=user_id,
                    agent_id=agent_id,
                    run_id=run_id,
                    filters=filters,
                    limit=limit,
                )['results']
            ]

    def delete_fact_by_id(self, namespace_id: str, fact_id: str):
        memory = self._get_namespace(namespace_id=namespace_id)
        # noinspection PyBroadException
        try:
            memory.delete(fact_id)
        except Exception:
            pass

    def extract_facts_from_messages(self, namespace_id: str, messages: list[Message]):
        memory = self._get_namespace(namespace_id=namespace_id)
        memory.add([m.model_dump() for m in messages], user_id='default_user', infer=True)

    def create_run(self, namespace_id: str, run_id: str | None = None) -> Run:
        run_id = run_id or 'run_' + str(uuid.uuid4()).replace('-', '_')
        with SQLiteManager() as db_manager:
            return db_manager.create_run(namespace_id, run_id)

    def delete_run(self, namespace_id: str, run_id: str):
        memory = self._get_namespace(namespace_id=namespace_id)
        memory.delete_all(user_id='default_user', run_id=run_id)
        with SQLiteManager() as db_manager:
            db_manager.delete_run(namespace_id=namespace_id, run_id=run_id)

    def add_step(self, namespace_id: str, run_id: str, step: dict, prompt: str) -> str:
        memory = self._get_namespace(namespace_id=namespace_id)
        llm: LLMBase = memory.llm

        messages = [
            {
                "role": "system",
                "content": prompt
                + '\n\nHere is the actual step you are working on:\n'
                + json.dumps(step, indent=4),
            }
        ]
        for attempt in range(3):
            extraction = llm.generate_response(messages)

            # Clean LLM response (removes markdown code blocks and thinking tags)
            cleaned_extraction = clean_llm_response(extraction)

            try:
                parsed_extraction = json.loads(cleaned_extraction)
            except JSONDecodeError:
                continue
            else:
                break
        else:
            raise HTTPException(
                status_code=500, detail=f"Unable to parse JSON output from llm prompt:\n{extraction}"
            )

        metadata = {**parsed_extraction, "step": step}
        added_step = memory.add(
            parsed_extraction['summary'],
            user_id='default_user',
            metadata=metadata,
            run_id=run_id,
            infer=False,
        )
        if len(added_step) > 0:
            return added_step['results'][0]['id']
        else:
            raise HTTPException(status_code=500, detail="Unable to add step.")

    def get_run(self, namespace_id: str, run_id: str) -> Run:
        memory = self._get_namespace(namespace_id=namespace_id)
        steps = [
            self._result_to_fact(step)
            for step in memory.get_all(user_id='default_user', run_id=run_id)['results']
        ]
        sorted_steps = sorted(steps, key=lambda step: step.created_at)

        with SQLiteManager() as db_manager:
            run = db_manager.get_run(namespace_id=namespace_id, run_id=run_id)
        run.steps = sorted_steps
        return run

    def search_runs(self, namespace_id: str, query: str, filters: dict[str, str]) -> Run | None:
        memory = self._get_namespace(namespace_id=namespace_id)
        results = memory.search(query=query, user_id='default_user', filters=filters)['results']
        if len(results) > 0:
            run_id = results[0]['run_id']
            steps = [
                self._result_to_fact(step)
                for step in memory.get_all(user_id='default_user', run_id=run_id)['results']
            ]
            sorted_steps = sorted(steps, key=lambda step: step.created_at)

            with SQLiteManager() as db_manager:
                run = db_manager.get_run(namespace_id=namespace_id, run_id=run_id)
            run.steps = sorted_steps
            return run
        else:
            return None
