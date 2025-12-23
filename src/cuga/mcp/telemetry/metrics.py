from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass
class Counter:
    name: str
    count: int = 0

    def inc(self, value: int = 1) -> None:
        self.count += value


@dataclass
class Histogram:
    name: str
    values: list[float] = field(default_factory=list)

    def observe(self, value: float) -> None:
        self.values.append(value)


class Metrics:
    def __init__(self) -> None:
        self.counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Counter] = {}
        self.histograms: Dict[str, Histogram] = {}

    def counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> Counter:
        key = (name, tuple(sorted((labels or {}).items())))
        if key not in self.counters:
            self.counters[key] = Counter(name)
        return self.counters[key]

    def histogram(self, name: str) -> Histogram:
        if name not in self.histograms:
            self.histograms[name] = Histogram(name)
        return self.histograms[name]

    def time_block(self, name: str):
        start = time.perf_counter()

        def _done() -> None:
            self.histogram(name).observe((time.perf_counter() - start) * 1000)

        return _done


metrics = Metrics()
