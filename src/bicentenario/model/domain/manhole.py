"""Pozo de inspección / alcantarilla (vértice del grafo).

``node_id`` coincide con el campo que Persona B usa en ``NodeState``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["Manhole", "NodeKind"]


class NodeKind(str, Enum):
    """Clasificación del nodo dentro de la red."""

    SOURCE = "source"    # alcantarilla: entrada de escorrentía
    SINK = "sink"        # punto de descarga (PTAR Punta Canoa)
    MANHOLE = "manhole"  # pozo de inspección intermedio


@dataclass(frozen=True)
class Manhole:
    """Vértice de la red de alcantarillado."""

    node_id: str
    kind: NodeKind = NodeKind.MANHOLE

    @classmethod
    def from_id(
        cls,
        node_id: object,
        *,
        sources: tuple[str, ...] | list[str] | set[str] = (),
        sinks: tuple[str, ...] | list[str] | set[str] = (),
    ) -> "Manhole":
        """Crea el vértice clasificándolo según las listas de fuentes/sumideros."""
        identifier = str(node_id).strip()
        if identifier in {str(item) for item in sinks}:
            return cls(identifier, NodeKind.SINK)
        if identifier in {str(item) for item in sources}:
            return cls(identifier, NodeKind.SOURCE)
        return cls(identifier, NodeKind.MANHOLE)

    @property
    def is_source(self) -> bool:
        """``True`` si es fuente."""
        return self.kind is NodeKind.SOURCE

    @property
    def is_sink(self) -> bool:
        """``True`` si es sumidero."""
        return self.kind is NodeKind.SINK
