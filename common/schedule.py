from __future__ import annotations

import heapq
from typing import List, Iterable, Iterator
from itertools import count
from common.models import CommandBase


class Schedule:
    """Just a simple priority heap based on the scheduled time"""

    # Tie breaker is "irrelevant" as both entries will get processed
    # during the same simulation step if theyre ready

    def __init__(self,
                 items: Iterable[CommandBase] = ()):
        self._heap: List[tuple[float, int, CommandBase]] = []
        self._order = count()
        for sc in items:
            self.push(sc)

    def push(self, cb: CommandBase) -> None:
        heapq.heappush(self._heap,
                       (cb.time, next(self._order), cb))

    def peek_time(self) -> float:
        return self._heap[0][0] if self._heap else float('inf')

    def ready(self, up_to: float) -> Iterator[CommandBase]:
        """ Yield (and pop) every command with time <= `up_to`"""
        heap = self._heap
        while heap and heap[0][0] <= up_to:
            yield heapq.heappop(heap)[2]

    def __len__(self) -> int: return len(self._heap)
    def __bool__(self) -> bool: return bool(self._heap)
    def __iter__(self): return (t[2] for t in self._heap)
