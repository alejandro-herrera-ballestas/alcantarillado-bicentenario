"""Nodo de las estructuras enlazadas de la Parte A.

Es la celda mínima con valor y referencias al siguiente y al anterior.
El atributo se llama ``value`` porque el adaptador de ``SimulationHistory``
(Persona B) busca ``value``, ``data`` o ``item`` al desempaquetar nodos.
"""

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")

__all__ = ["Node"]


class Node(Generic[T]):
    """Celda de una lista enlazada (simple o doble).

    Attributes:
        value: Dato almacenado.
        next: Referencia al nodo siguiente, o ``None``.
        prev: Referencia al nodo anterior, o ``None`` (listas dobles).
    """

    __slots__ = ("value", "next", "prev")

    def __init__(
        self,
        value: T,
        next: Node[T] | None = None,
        prev: Node[T] | None = None,
    ) -> None:
        self.value = value
        self.next = next
        self.prev = prev

    def __repr__(self) -> str:
        return f"Node({self.value!r})"
