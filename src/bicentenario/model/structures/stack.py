"""Pila (LIFO) implementada con nodos enlazados (Parte A).

Se usa en el DFS, en la reconstrucción de caminos y en la detección de ciclos.
No se delega en ``list``: la pila es una estructura central del proyecto.
"""

from __future__ import annotations

from typing import Generic, Iterable, Iterator, TypeVar

from bicentenario.model.structures.node import Node

T = TypeVar("T")

__all__ = ["Stack"]


class Stack(Generic[T]):
    """Pila con operaciones O(1) en la cima."""

    __slots__ = ("_top", "_size")

    def __init__(self, values: Iterable[T] | None = None) -> None:
        self._top: Node[T] | None = None
        self._size = 0
        if values is not None:
            for value in values:
                self.push(value)

    def push(self, value: T) -> None:
        """Apila ``value``."""
        self._top = Node(value, next=self._top)
        self._size += 1

    def pop(self) -> T:
        """Desapila y devuelve la cima; falla si está vacía."""
        if self._top is None:
            raise IndexError("La pila está vacía.")
        node = self._top
        self._top = node.next
        self._size -= 1
        return node.value

    def peek(self) -> T:
        """Devuelve la cima sin quitarla."""
        if self._top is None:
            raise IndexError("La pila está vacía.")
        return self._top.value

    def is_empty(self) -> bool:
        """``True`` si no hay elementos."""
        return self._size == 0

    def clear(self) -> None:
        """Vacía la pila."""
        self._top = None
        self._size = 0

    def to_list(self) -> list[T]:
        """Copia de la cima al fondo."""
        return list(self)

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0

    def __iter__(self) -> Iterator[T]:
        node = self._top
        while node is not None:
            yield node.value
            node = node.next

    def __repr__(self) -> str:
        return f"Stack([{', '.join(repr(v) for v in self)}])"  # cima primero
