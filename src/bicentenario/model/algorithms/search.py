"""Búsqueda y consulta por identificador usando la ``HashTable`` propia.

Da soporte a RF08/RF11: buscar tuberías, nodos y escenarios con tolerancia a
mayúsculas, espacios y al prefijo ``P`` (p. ej. ``"12"`` → ``"P12"``).
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable

from bicentenario.errors import InputValidationError
from bicentenario.model.domain import Manhole, Pipe, Scenario
from bicentenario.model.graph.directed_graph import DirectedGraph
from bicentenario.model.structures.hash_table import HashTable

__all__ = ["find_node", "find_pipe", "find_scenario", "normalize_query", "search_by_id"]


def normalize_query(text: object) -> str:
    """Quita espacios internos y normaliza mayúsculas."""
    return "".join(str(text).split()).casefold()


def _build_index(ids: Iterable[str]) -> HashTable[str, str]:
    """Índice canónico → ID original, con clave normalizada."""
    table: HashTable[str, str] = HashTable()
    for identifier in ids:
        table.put(normalize_query(identifier), identifier)
    return table


def _suggest(query: str, canonical: Iterable[str]) -> str:
    close = difflib.get_close_matches(query, list(canonical), n=3, cutoff=0.6)
    return f" ¿Quiso decir {', '.join(close)}?" if close else ""


def search_by_id(
    graph: DirectedGraph, text: object, *, kind: str = "pipe"
) -> Pipe | Manhole | None:
    """Busca por ID; devuelve ``None`` si no existe.

    ``kind`` es ``"pipe"``, ``"node"`` o ``"manhole"``.
    """
    query = normalize_query(text)
    if not query:
        return None
    if kind in ("pipe", "tubería", "tuberias"):
        index = _build_index(graph.pipe_ids())
        for candidate in (query, f"p{query}"):
            found = index.get(candidate)
            if found is not None:
                return graph.get_pipe(found)
        return None
    if kind in ("node", "manhole", "nodo"):
        index = _build_index(graph.node_ids())
        found = index.get(query)
        return None if found is None else graph.get_node(found)
    raise ValueError(f"Tipo de búsqueda desconocido: {kind!r}")


def find_pipe(graph: DirectedGraph, text: object) -> Pipe:
    """Tubería por ID; lanza ``InputValidationError`` si no existe."""
    query = normalize_query(text)
    if not query:
        raise InputValidationError("Escriba el ID de la tubería (por ejemplo P12).")
    found = search_by_id(graph, query, kind="pipe")
    if found is None:
        hint = _suggest(query, [normalize_query(i) for i in graph.pipe_ids()])
        raise InputValidationError(f"No existe la tubería '{str(text).strip()}'.{hint}")
    return found  # type: ignore[return-value]


def find_node(graph: DirectedGraph, text: object) -> Manhole:
    """Nodo por ID; lanza ``InputValidationError`` si no existe."""
    query = normalize_query(text)
    if not query:
        raise InputValidationError("Escriba el ID del nodo.")
    found = search_by_id(graph, query, kind="node")
    if found is None:
        hint = _suggest(query, [normalize_query(i) for i in graph.node_ids()])
        raise InputValidationError(f"No existe el nodo '{str(text).strip()}'.{hint}")
    return found  # type: ignore[return-value]


def find_scenario(scenarios: Iterable[Scenario], text: object) -> Scenario:
    """Escenario por ID; lanza ``InputValidationError`` si no existe."""
    query = normalize_query(text)
    index = _build_index([scenario.id for scenario in scenarios])
    found = index.get(query)
    if found is None:
        hint = _suggest(query, [normalize_query(s.id) for s in scenarios])
        raise InputValidationError(f"No existe el escenario '{str(text).strip()}'.{hint}")
    for scenario in scenarios:
        if scenario.id == found:
            return scenario
    raise InputValidationError(f"No existe el escenario '{str(text).strip()}'.")
