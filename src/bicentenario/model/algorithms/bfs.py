"""BFS (recorrido en amplitud) con la ``Queue`` de la Parte A.

La cola es propia: no se usa ``collections.deque`` ni la de Persona B.
"""

from __future__ import annotations

from collections.abc import Iterator

from bicentenario.errors import InputValidationError
from bicentenario.model.graph.directed_graph import DirectedGraph
from bicentenario.model.structures.queue import Queue
from bicentenario.model.structures.stack import Stack

__all__ = ["bfs", "bfs_parents", "shortest_path", "reconstruct_path"]


def _require_node(graph: DirectedGraph, node_id: object) -> str:
    identifier = str(node_id)
    if not graph.has_node(identifier):
        raise InputValidationError(f"El nodo '{identifier}' no existe en la red.")
    return identifier


def bfs_parents(graph: DirectedGraph, start: object) -> dict[str, str | None]:
    """Árbol de BFS: ``padre[nodo]`` (``None`` para la raíz)."""
    root = _require_node(graph, start)
    parent: dict[str, str | None] = {root: None}
    queue: Queue[str] = Queue()
    queue.enqueue(root)
    while not queue.is_empty():
        node = queue.dequeue()
        for nxt in graph.out_neighbors(node):
            if nxt not in parent:
                parent[nxt] = node
                queue.enqueue(nxt)
    return parent


def bfs(graph: DirectedGraph, start: object, *, goal: object | None = None) -> list[str]:
    """Recorrido en amplitud desde ``start``.

    Si se da ``goal``, se detiene en cuanto lo alcanza. El orden de visita es
    determinista porque las adyacencias se ordenan con ``natural_key``.
    """
    root = _require_node(graph, start)
    target = None if goal is None else _require_node(graph, goal)
    visited = {root}
    order = [root]
    queue: Queue[str] = Queue()
    queue.enqueue(root)
    while not queue.is_empty():
        node = queue.dequeue()
        if node == target:
            break
        for nxt in graph.out_neighbors(node):
            if nxt not in visited:
                visited.add(nxt)
                order.append(nxt)
                queue.enqueue(nxt)
                if nxt == target:
                    return order
    return order


def reconstruct_path(
    parent: dict[str, str | None], start: object, goal: object
) -> list[str] | None:
    """Reconstruye ``start → goal`` usando la ``Stack`` propia.

    Devuelve ``None`` si ``goal`` no es alcanzable desde ``start``.
    """
    origin, destination = str(start), str(goal)
    if origin not in parent:
        raise InputValidationError(f"El nodo '{origin}' no está en el recorrido.")
    if destination != origin and destination not in parent:
        return None
    reversed_path: Stack[str] = Stack()
    node = destination
    while node != origin:
        reversed_path.push(node)
        previous = parent.get(node)
        if previous is None:
            return None
        node = previous
    reversed_path.push(origin)
    # __iter__ de Stack va de la cima al fondo: queda start → goal.
    return list(reversed_path)


def shortest_path(
    graph: DirectedGraph, start: object, goal: object
) -> list[str] | None:
    """Camino más corto en número de tuberías (BFS + reconstrucción)."""
    root = _require_node(graph, start)
    target = _require_node(graph, goal)
    parent = bfs_parents(graph, root)
    return reconstruct_path(parent, root, target)


def iter_bfs(graph: DirectedGraph, start: object) -> Iterator[str]:
    """Versión perezosa de :func:`bfs` (útil para recorridos grandes)."""
    yield from bfs(graph, start)
