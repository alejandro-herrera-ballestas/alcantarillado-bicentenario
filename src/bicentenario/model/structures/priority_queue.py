"""Cola de prioridad con heap binario propio (mejora «avanzada», Parte A).

No es una estructura obligatoria de la guía (la obligatoria es ``Queue``),
pero ``heapq`` se usa solo como referencia conceptual: el heap aquí se
implementa con una lista y los métodos de burbujeo. Los empates se resuelven
por orden de inserción, para que el resultado sea determinista (S6).
"""

from __future__ import annotations

from itertools import count
from typing import Generic, Iterator, TypeVar

T = TypeVar("T")

__all__ = ["PriorityQueue"]


class PriorityQueue(Generic[T]):
    """Heap binario mínimo: menor prioridad sale primero."""

    __slots__ = ("_heap", "_counter")

    def __init__(self) -> None:
        self._heap: list[tuple[float, int, T]] = []
        self._counter = count()

    def push(self, item: T, priority: float) -> None:
        """Inserta ``item`` con ``priority`` (menor = antes)."""
        priority = float(priority)
        if priority != priority:  # NaN
            raise ValueError("La prioridad no puede ser NaN.")
        self._heap.append((priority, next(self._counter), item))
        self._sift_up(len(self._heap) - 1)

    def pop(self) -> T:
        """Quita y devuelve el elemento de menor prioridad."""
        if not self._heap:
            raise IndexError("La cola de prioridad está vacía.")
        smallest = self._heap[0]
        last = self._heap.pop()
        if self._heap:
            self._heap[0] = last
            self._sift_down(0)
        return smallest[2]

    def peek(self) -> T:
        """Elemento de menor prioridad sin quitarlo."""
        if not self._heap:
            raise IndexError("La cola de prioridad está vacía.")
        return self._heap[0][2]

    def is_empty(self) -> bool:
        """``True`` si no hay elementos."""
        return not self._heap

    def clear(self) -> None:
        """Vacía la cola."""
        self._heap.clear()

    def _sift_up(self, index: int) -> None:
        while index > 0:
            parent = (index - 1) // 2
            if self._heap[parent] <= self._heap[index]:
                break
            self._heap[parent], self._heap[index] = self._heap[index], self._heap[parent]
            index = parent

    def _sift_down(self, index: int) -> None:
        size = len(self._heap)
        while True:
            left = 2 * index + 1
            right = left + 1
            smallest = index
            if left < size and self._heap[left] < self._heap[smallest]:
                smallest = left
            if right < size and self._heap[right] < self._heap[smallest]:
                smallest = right
            if smallest == index:
                break
            self._heap[index], self._heap[smallest] = self._heap[smallest], self._heap[index]
            index = smallest

    def to_list(self) -> list[T]:
        """Elementos ordenados por prioridad (copia, sin modificar el heap)."""
        return [entry[2] for entry in sorted(self._heap)]

    def __len__(self) -> int:
        return len(self._heap)

    def __iter__(self) -> Iterator[T]:
        return iter(self.to_list())

    def __repr__(self) -> str:
        return f"PriorityQueue({self.to_list()!r})"
