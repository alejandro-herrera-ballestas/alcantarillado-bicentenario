"""Cola (FIFO) implementada con nodos enlazados (Parte A).

El simulador de Persona B la importa directamente:

    from bicentenario.model.structures.queue import Queue
    Queue().enqueue(valor) / Queue().dequeue() / len(cola)

También se usan alias habituales (``push``/``pop``, ``put``/``get``) para
maximizar compatibilidad con adaptadores externos.
"""

from __future__ import annotations

from typing import Generic, Iterable, Iterator, TypeVar

from bicentenario.model.structures.node import Node

T = TypeVar("T")

__all__ = ["Queue"]


class Queue(Generic[T]):
    """Cola FIFO con frente, cola y contador de tamaño."""

    __slots__ = ("_front", "_back", "_size")

    def __init__(self, values: Iterable[T] | None = None) -> None:
        self._front: Node[T] | None = None
        self._back: Node[T] | None = None
        self._size = 0
        if values is not None:
            for value in values:
                self.enqueue(value)

    def enqueue(self, value: T) -> None:
        """Agrega ``value`` al final (O(1))."""
        node = Node(value)
        if self._back is None:
            self._front = self._back = node
        else:
            self._back.next = node
            self._back = node
        self._size += 1

    def dequeue(self) -> T:
        """Quita y devuelve el frente (O(1)); falla si está vacía."""
        if self._front is None:
            raise IndexError("La cola está vacía.")
        node = self._front
        self._front = node.next
        if self._front is None:
            self._back = None
        self._size -= 1
        return node.value

    def peek(self) -> T:
        """Devuelve el frente sin quitarlo."""
        if self._front is None:
            raise IndexError("La cola está vacía.")
        return self._front.value

    # Alias para los adaptadores de Persona B.
    push = enqueue
    put = enqueue
    pop = dequeue
    get = dequeue
    popleft = dequeue

    def is_empty(self) -> bool:
        """``True`` si no hay elementos."""
        return self._size == 0

    def clear(self) -> None:
        """Vacía la cola."""
        self._front = self._back = None
        self._size = 0

    def to_list(self) -> list[T]:
        """Copia de los valores del frente al final."""
        return list(self)

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0

    def __iter__(self) -> Iterator[T]:
        node = self._front
        while node is not None:
            yield node.value
            node = node.next

    def __repr__(self) -> str:
        return f"Queue([{', '.join(repr(v) for v in self)}])"
