"""Validaciones de topología para Persona C (detección de ciclos y alcanzabilidad).

C ya tenía funciones privadas equivalentes en ``io/validators.py``; estas son
las versiones de la Parte A, apoyadas en el grafo propio, la ``Queue`` y la
``Stack``. Devuelven conjuntos/listas simples para que C pueda llamarlas sin
adaptar sus mensajes de validación.
"""

from __future__ import annotations

from collections.abc import Iterable

from bicentenario.model.graph.directed_graph import DirectedGraph
from bicentenario.model.structures.queue import Queue
from bicentenario.model.structures.stack import Stack

__all__ = [
    "dead_ends",
    "detect_cycles",
    "has_cycle",
    "reachable_from_sources",
    "reachable_to",
    "reachable_to_sinks",
    "topological_order",
]


def reachable_from(graph: DirectedGraph, starts: Iterable[object]) -> set[str]:
    """Nodos alcanzables desde ``starts`` siguiendo las aristas salientes."""
    known = set(graph.node_ids())
    seen: set[str] = set()
    queue: Queue[str] = Queue()
    for start in starts:
        identifier = str(start)
        if identifier in known and identifier not in seen:
            seen.add(identifier)
            queue.enqueue(identifier)
    while not queue.is_empty():
        node = queue.dequeue()
        for nxt in graph.out_neighbors(node):
            if nxt not in seen:
                seen.add(nxt)
                queue.enqueue(nxt)
    return seen


def reachable_to(graph: DirectedGraph, targets: Iterable[object]) -> set[str]:
    """Nodos que pueden llegar a ``targets`` (BFS sobre aristas entrantes)."""
    known = set(graph.node_ids())
    seen: set[str] = set()
    queue: Queue[str] = Queue()
    for target in targets:
        identifier = str(target)
        if identifier in known and identifier not in seen:
            seen.add(identifier)
            queue.enqueue(identifier)
    while not queue.is_empty():
        node = queue.dequeue()
        for previous in graph.in_neighbors(node):
            if previous not in seen:
                seen.add(previous)
                queue.enqueue(previous)
    return seen


def reachable_from_sources(
    graph: DirectedGraph, sources: Iterable[object] | None = None
) -> set[str]:
    """Nodos a los que llega agua desde las fuentes."""
    return reachable_from(graph, graph.sources() if sources is None else sources)


def reachable_to_sinks(
    graph: DirectedGraph, sinks: Iterable[object] | None = None
) -> set[str]:
    """Nodos desde los que se puede llegar a algún sumidero."""
    return reachable_to(graph, graph.sinks() if sinks is None else sinks)


def dead_ends(graph: DirectedGraph, sinks: Iterable[object] | None = None) -> set[str]:
    """Nodos sin salida que no son sumidero (el agua quedaría atrapada)."""
    sink_ids = {str(value) for value in (graph.sinks() if sinks is None else sinks)}
    return {
        node for node in graph.node_ids()
        if not graph.out_neighbors(node) and node not in sink_ids
    }


def detect_cycles(graph: DirectedGraph) -> list[list[str]]:
    """Ciclos simples del grafo mediante DFS con colores (blanco/gris/negro).

    Cada ciclo se devuelve como lista de nodos cerrada (el primero y el último
    coinciden). El recorrido es iterativo: usa la ``Stack`` propia en lugar de
    recursión, para no depender del límite de pila de Python.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in graph.node_ids()}
    cycles: list[list[str]] = []

    for start in graph.node_ids():
        if color[start] != WHITE:
            continue
        path: list[str] = [start]
        color[start] = GRAY
        stack: Stack[tuple[str, object]] = Stack()
        stack.push((start, iter(graph.out_neighbors(start))))

        while not stack.is_empty():
            node, neighbours = stack.peek()
            descended = False
            for nxt in neighbours:  # type: ignore[union-attr]
                state = color.get(nxt, WHITE)
                if state == WHITE:
                    color[nxt] = GRAY
                    path.append(nxt)
                    stack.push((nxt, iter(graph.out_neighbors(nxt))))
                    descended = True
                    break
                if state == GRAY:
                    cycle = path[path.index(nxt):] + [nxt]
                    if cycle not in cycles:
                        cycles.append(cycle)
            if not descended:
                color[node] = BLACK
                stack.pop()
                path.pop()

    return cycles


def has_cycle(graph: DirectedGraph) -> bool:
    """``True`` si el grafo tiene al menos un ciclo."""
    return bool(detect_cycles(graph))


def topological_order(graph: DirectedGraph) -> list[str] | None:
    """Orden topológico (Kahn) o ``None`` si el grafo tiene ciclos."""
    pending: dict[str, int] = {}
    for node in graph.node_ids():
        pending[node] = len(graph.in_neighbors(node))
    queue: Queue[str] = Queue()
    for node in graph.node_ids():
        if pending[node] == 0:
            queue.enqueue(node)
    order: list[str] = []
    while not queue.is_empty():
        node = queue.dequeue()
        order.append(node)
        for nxt in graph.out_neighbors(node):
            pending[nxt] -= 1
            if pending[nxt] == 0:
                queue.enqueue(nxt)
    return order if len(order) == len(graph) else None
