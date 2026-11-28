"""Grafo dirigido propio de la Parte A (RF02, guía §5.1).

No se usa NetworkX ni ``dict`` como grafo: la red se guarda como **listas de
adyacencia** salientes y entrantes. Un ``dict`` nativo se usa únicamente como
contenedor indexado por ID, y la ``HashTable`` propia para consultas por
identificador. Las listas de adyacencia se devuelven ordenadas con
``natural_key`` para que BFS/DFS sean deterministas (supuesto S6).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from bicentenario.errors import InputValidationError
from bicentenario.model.domain import Manhole, NodeKind, Pipe
from bicentenario.model.ordering import natural_key
from bicentenario.model.structures.hash_table import HashTable

__all__ = ["DirectedGraph"]


class DirectedGraph:
    """Grafo dirigido de la red de alcantarillado.

    Attributes:
        _nodes: Vértices indexados por ID.
        _out: Lista de adyacencia saliente (origen → destinos).
        _in: Lista de adyacencia entrante (destino → orígenes).
        _pipes: Tuberías indexadas por ID con la ``HashTable`` propia.
    """

    __slots__ = ("_nodes", "_out", "_in", "_pipes")

    def __init__(self) -> None:
        self._nodes: dict[str, Manhole] = {}
        self._out: dict[str, list[str]] = {}
        self._in: dict[str, list[str]] = {}
        self._pipes: HashTable[str, Pipe] = HashTable()

    # ------------------------------------------------------------ construcción
    def add_node(self, node: str | Manhole) -> None:
        """Agrega un vértice; si ya existe, se conserva la clasificación previa."""
        manhole = node if isinstance(node, Manhole) else Manhole(str(node).strip())
        if not manhole.node_id:
            raise InputValidationError("El ID de nodo no puede estar vacío.")
        if manhole.node_id in self._nodes:
            previous = self._nodes[manhole.node_id]
            if manhole.kind is not NodeKind.MANHOLE:
                self._nodes[manhole.node_id] = Manhole(manhole.node_id, manhole.kind)
            elif previous.kind is NodeKind.MANHOLE:
                return
            else:
                manhole = previous
        identifier = manhole.node_id
        self._nodes[identifier] = manhole
        self._out.setdefault(identifier, [])
        self._in.setdefault(identifier, [])

    def add_source(self, node_id: object) -> None:
        """Marca un vértice como fuente."""
        self.add_node(Manhole(str(node_id).strip(), NodeKind.SOURCE))

    def add_sink(self, node_id: object) -> None:
        """Marca un vértice como sumidero."""
        self.add_node(Manhole(str(node_id).strip(), NodeKind.SINK))

    def add_pipe(self, pipe: Pipe) -> None:
        """Agrega una arista dirigida (y crea sus extremos si faltan)."""
        if not pipe.id:
            raise InputValidationError("El ID de tubería no puede estar vacío.")
        if pipe.id in self._pipes:
            raise InputValidationError(f"La tubería '{pipe.id}' ya está en el grafo.")
        self.add_node(pipe.from_node)
        self.add_node(pipe.to_node)
        self._pipes.put(pipe.id, pipe)
        self._out[pipe.from_node].append(pipe.to_node)
        self._in[pipe.to_node].append(pipe.from_node)

    @classmethod
    def build_from_dataset(
        cls,
        dataset: object,
        *,
        sources: Sequence[object] | None = None,
        sinks: Sequence[object] | None = None,
    ) -> "DirectedGraph":
        """Construye la red a partir de ``RawDataset`` o cualquier objeto similar.

        Se aceptan ``sources``/``sinks`` explícitos para poder usar el grafo con
        datasets de prueba que no tengan esos atributos.
        """
        graph = cls()
        source_ids = [str(value) for value in (
            sources if sources is not None else getattr(dataset, "sources", [])
        )]
        sink_ids = [str(value) for value in (
            sinks if sinks is not None else getattr(dataset, "sinks", [])
        )]
        for identifier in getattr(dataset, "node_ids", lambda: [])():
            graph.add_node(Manhole.from_id(identifier, sources=source_ids, sinks=sink_ids))
        for identifier in source_ids:
            graph.add_source(identifier)
        for identifier in sink_ids:
            graph.add_sink(identifier)
        for record in getattr(dataset, "pipes", []):
            graph.add_pipe(record if isinstance(record, Pipe) else Pipe.from_record(record))
        return graph

    # --------------------------------------------------------------- consultas
    def node_ids(self) -> list[str]:
        """Todos los vértices en orden natural."""
        return sorted(self._nodes, key=natural_key)

    def pipe_ids(self) -> list[str]:
        """Todas las tuberías en orden natural (P1, P2, …, P10)."""
        return sorted(self._pipes.keys(), key=natural_key)

    def nodes(self) -> list[Manhole]:
        """Objetos ``Manhole`` en orden natural."""
        return [self._nodes[identifier] for identifier in self.node_ids()]

    def pipes(self) -> list[Pipe]:
        """Objetos ``Pipe`` en orden natural por ID."""
        return [self._pipes[identifier] for identifier in self.pipe_ids()]

    def sources(self) -> list[str]:
        """IDs de las fuentes."""
        return [n.node_id for n in self.nodes() if n.is_source]

    def sinks(self) -> list[str]:
        """IDs de los sumideros."""
        return [n.node_id for n in self.nodes() if n.is_sink]

    def has_node(self, node_id: object) -> bool:
        """¿Existe el vértice?"""
        return str(node_id) in self._nodes

    def has_pipe(self, pipe_id: object) -> bool:
        """¿Existe la tubería?"""
        return str(pipe_id) in self._pipes

    def get_node(self, node_id: object) -> Manhole | None:
        """Vértice por ID, o ``None``."""
        return self._nodes.get(str(node_id))

    def get_pipe(self, pipe_id: object) -> Pipe | None:
        """Tubería por ID usando la ``HashTable``, o ``None``."""
        return self._pipes.get(str(pipe_id))

    def out_neighbors(self, node_id: object) -> list[str]:
        """Destinos de las tuberías que salen de ``node_id``."""
        return sorted(self._out.get(str(node_id), []), key=natural_key)

    def in_neighbors(self, node_id: object) -> list[str]:
        """Orígenes de las tuberías que llegan a ``node_id``."""
        return sorted(self._in.get(str(node_id), []), key=natural_key)

    def out_pipes(self, node_id: object) -> list[Pipe]:
        """Tuberías salientes, ordenadas por ID."""
        targets = set(self.out_neighbors(node_id))
        return [p for p in self.pipes() if p.from_node == str(node_id) and p.to_node in targets]

    def in_pipes(self, node_id: object) -> list[Pipe]:
        """Tuberías entrantes, ordenadas por ID."""
        return [p for p in self.pipes() if p.to_node == str(node_id)]

    def degree(self, node_id: object) -> tuple[int, int]:
        """Par ``(grado de entrada, grado de salida)``."""
        identifier = str(node_id)
        return len(self._in.get(identifier, [])), len(self._out.get(identifier, []))

    def edge_count(self) -> int:
        """Número de tuberías."""
        return len(self._pipes)

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node_id: object) -> bool:
        return self.has_node(node_id)

    def __iter__(self):
        return iter(self.node_ids())

    def __repr__(self) -> str:
        return f"DirectedGraph(nodes={len(self._nodes)}, pipes={len(self._pipes)})"

    # ----------------------------------------------------------- adyacencias
    def adjacency(self) -> dict[str, list[str]]:
        """Copia de la lista de adyacencia saliente."""
        return {node: list(self.out_neighbors(node)) for node in self.node_ids()}

    def reverse_adjacency(self) -> dict[str, list[str]]:
        """Copia de la lista de adyacencia entrante."""
        return {node: list(self.in_neighbors(node)) for node in self.node_ids()}
