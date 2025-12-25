import json
import logging
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Optional

from .types import Cost, Usage

DEFAULT_LEDGER = Path.home() / ".cuga" / "billing.json"
DEFAULT_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "mistral": {"input": 0.0, "output": 0.0},
}


@dataclass
class BudgetConfig:
    run_budget_usd: Optional[float] = None
    daily_budget_usd: Optional[float] = None
    enforce: str = "warn"


class BudgetExceeded(Exception):
    """Raised when budget enforcement is blocking."""


class BudgetManager:
    _lock = threading.Lock()

    def __init__(
        self,
        config: BudgetConfig,
        ledger_path: Path = DEFAULT_LEDGER,
        pricing: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        self.config = config
        self.ledger_path = ledger_path
        self.pricing = pricing or DEFAULT_PRICING
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def _ledger(self) -> Dict[str, float]:
        if self.ledger_path.exists():
            with self.ledger_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        return {}

    def _persist(self, ledger: Dict[str, float]) -> None:
        with self.ledger_path.open("w", encoding="utf-8") as handle:
            json.dump(ledger, handle)

    def _estimate(self, usage: Usage, model: str, is_local: bool) -> Cost:
        prices = (
            {"input": 0.0, "output": 0.0}
            if is_local
            else self.pricing.get(model, {"input": 0.0, "output": 0.0})
        )
        return Cost(
            input_cost=(usage.prompt_tokens / 1000) * prices.get("input", 0.0),
            output_cost=(usage.completion_tokens / 1000) * prices.get("output", 0.0),
        )

    def _check(self, incremental: float, today_total: float) -> None:
        if self.config.run_budget_usd and incremental > self.config.run_budget_usd:
            if self.config.enforce == "block":
                raise BudgetExceeded("Per-run budget exceeded")
            logging.getLogger(__name__).warning(
                "Per-run budget exceeded: %.3f > %.3f",
                incremental,
                self.config.run_budget_usd,
            )

        if self.config.daily_budget_usd and today_total > self.config.daily_budget_usd:
            if self.config.enforce == "block":
                raise BudgetExceeded("Daily budget exceeded")
            logging.getLogger(__name__).warning(
                "Daily budget exceeded: %.3f > %.3f",
                today_total,
                self.config.daily_budget_usd,
            )

    def record(self, usage: Usage, model: str, is_local: bool) -> Cost:
        with BudgetManager._lock:
            cost = self._estimate(usage, model, is_local)
            ledger = self._ledger()
            today_key = date.today().isoformat()
            current_total = ledger.get(today_key, 0.0)

            self._check(cost.total, current_total + cost.total)

            ledger[today_key] = current_total + cost.total
            self._persist(ledger)
            return cost


def budget_from_env(env: Dict[str, str]) -> BudgetConfig:
    run_budget = env.get("AGENT_RUN_BUDGET_USD")
    daily_budget = env.get("AGENT_DAILY_BUDGET_USD")
    return BudgetConfig(
        run_budget_usd=float(run_budget) if run_budget else None,
        daily_budget_usd=float(daily_budget) if daily_budget else None,
        enforce=env.get("AGENT_BUDGET_ENFORCE", "warn"),
    )

