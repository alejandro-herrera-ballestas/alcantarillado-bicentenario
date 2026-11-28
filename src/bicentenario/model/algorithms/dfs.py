"""DFS (recorrido en profundidad) con la ``Stack`` de la Parte A.

Se apilan los vecinos en orden inverso para que la pila saque primero el de
menor clave natural; así el recorrido coincide con una DFS recursiva que
visitara las adyacencias ordenadas.
"""

from __future__ import annotations

from collections.abc import Iterator

from bicentenario.errors import InputValidationError
from bicentenario.model.graph.directed_graph import DirectedGraph
from bicentenario.model.structures.stack import Stack

__all__ = ["dfs", "dfs_parents", "iter_dfs"]


def _require_node(graph: DirectedGraph, node_id: object) -> str:
    identifier = str(node_id)
    if not graph.has_node(identifier):
        raise InputValidationError(f"El nodo '{identifier}' no existe en la red.")
    return identifier


def dfs_parents(graph: DirectedGraph, start: object) -> dict[str, str | None]:
    """Árbol de DFS: ``padre[nodo]`` (``None`` para la raíz)."""
    root = _require_node(graph, start)
    parent: dict[str, str | None] = {root: None}
    stack: Stack[str] = Stack()
    stack.push(root)
    while not stack.is_empty():
        node = stack.pop()
        for nxt in reversed(graph.out_neighbors(node)):
            if nxt not in parent:
                parent[nxt] = node
                stack.push(nxt)
    return parent


def dfs(graph: DirectedGraph, start: object, *, goal: object | None = None) -> list[str]:
    """Recorrido en profundidad desde ``start`` (iterativo, sin recursión)."""
    root = _require_node(graph, start)
    target = None if goal is None else _require_node(graph, goal)
    visited: set[str] = set()
    order: list[str] = []
    stack: Stack[str] = Stack()
    stack.push(root)
    while not stack.is_empty():
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        if node == target:
            break
        for nxt in reversed(graph.out_neighbors(node)):
            if nxt not in visited:
                stack.push(nxt)
    return order


def iter_dfs(graph: DirectedGraph, start: object) -> Iterator[str]:
    """Versión perezosa de :func:`dfs`."""
    yield from dfs(graph, start)
