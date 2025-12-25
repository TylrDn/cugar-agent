from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import List

from .agents import CoordinatorAgent, PlannerAgent, WorkerAgent, build_default_registry
from .config import AgentConfig
from .memory import VectorMemory
from .rag import RagLoader, RagRetriever

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
LOGGER = logging.getLogger(__name__)


def _load_memory(state_path: Path, backend: str, profile: str) -> VectorMemory:
    memory = VectorMemory(backend_name=backend, profile=profile)
    if state_path.exists():
        data = json.loads(state_path.read_text())
        for record in data.get("records", []):
            memory.remember(record["text"], metadata=record.get("metadata"))
    return memory


def _persist_memory(memory: VectorMemory, state_path: Path) -> None:
    state = {"records": [record.__dict__ for record in memory.store]}
    state_path.write_text(json.dumps(state, indent=2))


def handle_ingest(args: argparse.Namespace) -> None:
    state_path = Path(args.state)
    loader = RagLoader(backend=args.backend, profile=args.profile)
    added = loader.ingest(Path(p) for p in args.paths)
    _persist_memory(loader.memory, state_path)
    LOGGER.info(json.dumps({"event": "ingest", "added": added, "trace_id": args.trace_id}))


def handle_query(args: argparse.Namespace) -> None:
    state_path = Path(args.state)
    memory = _load_memory(state_path, backend=args.backend, profile=args.profile)
    retriever = RagRetriever(backend=args.backend, profile=args.profile)
    retriever.memory = memory
    hits = retriever.query(args.query, top_k=args.top_k)
    payload = [hit.__dict__ for hit in hits]
    LOGGER.info(json.dumps({"event": "query", "hits": payload, "trace_id": args.trace_id}))


def handle_plan(args: argparse.Namespace) -> None:
    state_path = Path(args.state)
    memory = _load_memory(state_path, backend=args.backend, profile=args.profile)
    registry = build_default_registry()
    planner = PlannerAgent(registry=registry, memory=memory, config=AgentConfig())
    worker = WorkerAgent(registry=registry, memory=memory)
    coordinator = CoordinatorAgent(planner=planner, workers=[worker], memory=memory)
    result = coordinator.dispatch(args.goal, trace_id=args.trace_id)
    _persist_memory(memory, state_path)
    LOGGER.info(json.dumps({"event": "plan", "output": result.output, "trace": result.trace, "trace_id": args.trace_id}))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cuga", description="Modular cuga CLI")
    parser.add_argument("--state", default=".cuga_modular_state.json")
    parser.add_argument("--backend", default="local")
    parser.add_argument("--profile", default="default")
    parser.add_argument("--trace-id", dest="trace_id", default=str(uuid.uuid4()))
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="ingest files")
    ingest.add_argument("paths", nargs="+")
    ingest.set_defaults(func=handle_ingest)

    query = subparsers.add_parser("query", help="query memory")
    query.add_argument("query")
    query.add_argument("--top-k", dest="top_k", type=int, default=3)
    query.set_defaults(func=handle_query)

    plan = subparsers.add_parser("plan", help="plan and execute")
    plan.add_argument("goal")
    plan.set_defaults(func=handle_plan)
    return parser


def main(argv: List[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
