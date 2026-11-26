"""Estado instantáneo e historial de la simulación (

Define:
* :class:`PipeState` / :class:`NodeState` — estado de una tubería y de un pozo
  en un instante (caudal, utilización, sobrecarga y exceso acumulado; S12).
* :class:`Snapshot` — estado completo de la red en un paso. Se comporta como
  un **mapeo ``pipe_id -> utilización (%)``** para que ``PlaybackController`` y
  la vista lo consuman sin adaptaciones (contrato verificado en
  ``controller/simulation_controller.py`` y ``view/main_window.py``).
* :class:`SimulationHistory` — historial de snapshots apoyado en la
  ``DoublyLinkedList`` de Persona A, con navegación temporal (``get_at``,
  ``anterior``, ``siguiente``, ``reiniciar``) y la tabla de tuberías críticas
  (RF10).

Contrato mínimo esperado de la ``DoublyLinkedList`` de Persona A
(``model/structures/doubly_linked_list.py``): ``append(item)`` (o
``push_back`` / ``add_last`` / ``insert_last``), ``__len__`` y ``__iter__`` en
orden de inserción. El adaptador :class:`_DllAdapter` normaliza esas variantes;
mientras Persona A no entregue su implementación, el historial puede
construirse con cualquier objeto que cumpla el protocolo
:class:`DoublyLinkedListLike` (útil para pruebas).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from bicentenario.errors import InputValidationError, InvalidStateError
from bicentenario.model.simulation.rules import utilization_pct

__all__ = [
    "DoublyLinkedListLike",
    "NodeState",
    "PipeState",
    "SimulationHistory",
    "Snapshot",
]


# ---------------------------------------------------------------------------
# Estados por elemento
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PipeState:
    """Estado de una tubería en un instante de la simulación (S12, S12b, S12d).

    Attributes:
        pipe_id: Identificador de la tubería (``"P1"``, …).
        flow: Caudal **ofrecido** a la tubería en el paso (m³/s); es el que
            define la utilización (S12d).
        utilization_pct: ``O = Q / Qmax · 100``; puede superar 100 (S12).
        overloaded: ``True`` si el caudal ofrecido excede ``Qmax`` (S12b).
        excess: Exceso retenido acumulado atribuido a esta tubería (m³); el
            agua retenida no desaparece del modelo (S12b).
    """

    pipe_id: str
    flow: float
    utilization_pct: float
    overloaded: bool
    excess: float

    @classmethod
    def from_flow(cls, pipe_id: str, flow: float, qmax: float, excess: float = 0.0) -> "PipeState":
        """Construye el estado a partir del caudal ofrecido y su ``Qmax`` (S12).

        Calcula la utilización con
        :func:`~bicentenario.model.simulation.rules.utilization_pct` y marca la
        sobrecarga cuando ``flow > qmax`` (S12b).

        Args:
            pipe_id: Identificador de la tubería.
            flow: Caudal ofrecido en el paso (m³/s, >= 0).
            qmax: Capacidad máxima de la tubería (m³/s, > 0).
            excess: Exceso retenido acumulado atribuido (m³, >= 0).

        Returns:
            El estado inmutable de la tubería.

        Examples:
            >>> state = PipeState.from_flow("P1", 0.10, 0.08, excess=12.5)
            >>> round(state.utilization_pct, 6), state.overloaded, state.excess
            (125.0, True, 12.5)
            >>> PipeState.from_flow("P2", 0.06, 0.08).overloaded
            False
        """
        return cls(
            pipe_id=str(pipe_id),
            flow=float(flow),
            utilization_pct=utilization_pct(flow, qmax),
            overloaded=flow > qmax,
            excess=float(excess),
        )


@dataclass(frozen=True)
class NodeState:
    """Estado de un pozo de inspección en un instante (S8, S12b, S12c).

    Attributes:
        node_id: Identificador del nodo.
        inflow: Caudal que llega al nodo en el paso (m³/s).
        stored: Exceso retenido acumulado en el pozo (m³); no desaparece del
            modelo y se reintenta evacuar en pasos posteriores (S12b).
        is_source: ``True`` si el nodo es una fuente (recibe escorrentía).
        is_sink: ``True`` si el nodo es sumidero: descarga fuera del modelo (S8).
    """

    node_id: str
    inflow: float
    stored: float
    is_source: bool = False
    is_sink: bool = False


# ---------------------------------------------------------------------------
# Snapshot: estado completo de la red en un paso
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Snapshot(Mapping[str, float]):
    """Estado completo de la red en un paso de simulación.

    Además de los estados detallados por tubería y por nodo, se comporta como
    un :class:`~collections.abc.Mapping` ``pipe_id -> utilización (%)``: eso es
    exactamente lo que espera ``MainWindow._on_frame`` (``frame.items()``,
    ``frame.get(pipe_id)``, ``frame.values()``) y lo que valida
    ``PlaybackController`` con ``len(history)`` y ``history.get_at(step)``.

    Attributes:
        step: Índice del paso (0 … ``n_steps``; S4).
        time_min: Instante simulado en minutos (``step · Δt``).
        pipes: Estados de todas las tuberías, indexados por ``pipe_id``.
        nodes: Estados de todos los nodos, indexados por ``node_id``.
    """

    step: int
    time_min: float
    pipes: Mapping[str, PipeState]
    nodes: Mapping[str, NodeState]

    def __post_init__(self) -> None:
        # Copia inmutable: un snapshot del historial no debe poder alterarse.
        object.__setattr__(self, "pipes", MappingProxyType(dict(self.pipes)))
        object.__setattr__(self, "nodes", MappingProxyType(dict(self.nodes)))

    # --- interfaz Mapping: el "frame" que consume la vista ---
    def __getitem__(self, pipe_id: str) -> float:
        return self.pipes[pipe_id].utilization_pct

    def __iter__(self) -> Iterator[str]:
        return iter(self.pipes)

    def __len__(self) -> int:
        return len(self.pipes)


# ---------------------------------------------------------------------------
# Contrato mínimo de la DoublyLinkedList de Persona A
# ---------------------------------------------------------------------------
class DoublyLinkedListLike(Protocol):
    """Contrato mínimo que debe cumplir la ``DoublyLinkedList`` de Persona A."""

    def append(self, item: Snapshot) -> None:
        """Agrega ``item`` al final de la lista."""

    def __len__(self) -> int:
        """Cantidad de elementos almacenados."""

    def __iter__(self) -> Iterator[Snapshot]:
        """Recorre los elementos en orden de inserción."""


_APPEND_METHODS = ("append", "push_back", "add_last", "insert_last")


class _DllAdapter:
    """Adapta la ``DoublyLinkedList`` de Persona A al contrato del historial.

    Persona A aún no ha publicado su implementación, así que se aceptan los
    nombres habituales para insertar al final (``append``, ``push_back``,
    ``add_last`` o ``insert_last``) y se usa ``__iter__`` (o ``to_list``) para
    recorrer. Si el recorrido devuelve los **nodos** en lugar de los elementos,
    :meth:`_unwrap` extrae el snapshot de los atributos habituales (``value``,
    ``data`` o ``item``). Si su API final difiere, basta con ampliar estas
    tuplas.
    """

    def __init__(self, linked_list: object) -> None:
        self._linked = linked_list
        self._append = self._find_append(linked_list)

    @staticmethod
    def _find_append(linked_list: object):
        for name in _APPEND_METHODS:
            method = getattr(linked_list, name, None)
            if callable(method):
                return method
        raise InvalidStateError(
            "La DoublyLinkedList de Persona A no expone un método para agregar al final "
            f"(se esperaba alguno de: {', '.join(_APPEND_METHODS)})."
        )

    @staticmethod
    def _unwrap(item: object) -> Snapshot:
        """Devuelve el snapshot contenido en ``item`` si es un nodo de la lista."""
        if isinstance(item, Snapshot):
            return item
        for attribute in ("value", "data", "item"):
            candidate = getattr(item, attribute, None)
            if isinstance(candidate, Snapshot):
                return candidate
        raise InvalidStateError(
            "La DoublyLinkedList de Persona A devolvió un elemento que no es un Snapshot "
            f"(recibido {type(item).__name__}); se esperaba el snapshot o un nodo con "
            "atributo 'value', 'data' o 'item'."
        )

    def append(self, item: Snapshot) -> None:
        self._append(item)

    def __len__(self) -> int:
        return len(self._linked)  # type: ignore[arg-type]

    def __iter__(self) -> Iterator[Snapshot]:
        if hasattr(self._linked, "__iter__"):
            source = iter(self._linked)  # type: ignore[call-overload]
        else:
            to_list = getattr(self._linked, "to_list", None)
            if not callable(to_list):
                raise InvalidStateError(
                    "La DoublyLinkedList de Persona A no se puede recorrer: "
                    "falta __iter__ (o to_list)."
                )
            source = iter(to_list())
        return (self._unwrap(item) for item in source)


def _default_storage() -> DoublyLinkedListLike:
    """Crea la ``DoublyLinkedList`` de Persona A, si ya está disponible."""
    try:
        from bicentenario.model.structures.doubly_linked_list import DoublyLinkedList
    except ImportError as exc:
        raise InvalidStateError(
            "El historial requiere la DoublyLinkedList de Persona A "
            "(src/bicentenario/model/structures/doubly_linked_list.py), que todavía no está "
            "implementada. Mientras tanto, construya SimulationHistory(storage=...) con un "
            "objeto compatible (append, __len__ y __iter__)."
        ) from exc
    return DoublyLinkedList()


# ---------------------------------------------------------------------------
# Historial de la simulación
# ---------------------------------------------------------------------------
class SimulationHistory:
    """Historial de snapshots con navegación temporal (PARTE 3).

    Almacena los snapshots en la ``DoublyLinkedList`` de Persona A (o en
    cualquier objeto que cumpla :class:`DoublyLinkedListLike`) y mantiene un
    índice de solo lectura para que ``get_at`` sea O(1) durante la reproducción
    (el historial es de solo-anexado: el índice se invalida únicamente al
    agregar).

    Cumple el contrato que espera ``PlaybackController`` de Persona C:
    ``len(history)`` y ``history.get_at(step)`` (con ``step`` entre ``0`` y
    ``len(history) - 1``), y ofrece ``critical_rows(step)`` para la tabla de
    tuberías críticas (RF10).
    """

    def __init__(
        self,
        storage: DoublyLinkedListLike | None = None,
        snapshots: Iterable[Snapshot] | None = None,
    ) -> None:
        """Crea el historial.

        Args:
            storage: Lista doblemente enlazada donde guardar los snapshots. Si
                es ``None`` se intenta crear la de Persona A (y se lanza
                ``InvalidStateError`` con un mensaje claro si aún no existe).
            snapshots: Snapshots iniciales opcionales (se agregan en orden).
        """
        self._storage: DoublyLinkedListLike = _DllAdapter(
            storage if storage is not None else _default_storage()
        )
        self._index: list[Snapshot] | None = None
        self._cursor = 0
        if snapshots is not None:
            self.extend(snapshots)

    # ------------------------------------------------------------- consultas
    @property
    def storage(self) -> DoublyLinkedListLike:
        """Adaptador de solo lectura sobre la lista de Persona A."""
        return self._storage

    @property
    def step(self) -> int:
        """Paso en el que está el cursor de navegación."""
        return self._cursor

    def __len__(self) -> int:
        return len(self._storage)

    def __iter__(self) -> Iterator[Snapshot]:
        return iter(self._ensure_index())

    def _ensure_index(self) -> list[Snapshot]:
        """Construye (una sola vez) el índice de acceso aleatorio."""
        if self._index is None:
            self._index = list(self._storage)
        return self._index

    # -------------------------------------------------------------- llenado
    def append(self, snapshot: Snapshot) -> None:
        """Agrega un snapshot al final del historial."""
        self._storage.append(snapshot)
        if self._index is not None:
            self._index.append(snapshot)

    def extend(self, snapshots: Iterable[Snapshot]) -> None:
        """Agrega varios snapshots en orden."""
        for snapshot in snapshots:
            self.append(snapshot)

    # ---------------------------------------------------------- navegación
    def _check_step(self, step: int) -> int:
        """Valida un índice de paso y devuelve el último paso disponible."""
        if isinstance(step, bool) or not isinstance(step, int):
            raise InputValidationError(
                f"El paso debe ser un número entero (recibido {step!r})."
            )
        last = len(self) - 1
        if last < 0:
            raise InvalidStateError("El historial de la simulación está vacío.")
        if not 0 <= step <= last:
            raise InputValidationError(
                f"El paso debe estar entre 0 y {last} (recibido {step})."
            )
        return step

    def get_at(self, step: int) -> Snapshot:
        """Snapshot del paso ``step`` (``0 … len(history) - 1``).

        Es el método que usa ``PlaybackController`` para mostrar cada instante.
        """
        return self._ensure_index()[self._check_step(step)]

    def current(self) -> Snapshot:
        """Snapshot del paso actual del cursor."""
        if len(self) == 0:
            raise InvalidStateError("El historial de la simulación está vacío.")
        return self._ensure_index()[self._cursor]

    def anterior(self) -> Snapshot:
        """Retrocede un paso (en el paso 0 se queda en 0) y devuelve el snapshot."""
        if len(self) == 0:
            raise InvalidStateError("El historial de la simulación está vacío.")
        if self._cursor > 0:
            self._cursor -= 1
        return self._ensure_index()[self._cursor]

    def siguiente(self) -> Snapshot:
        """Avanza un paso (en el último se queda en el último) y lo devuelve."""
        if len(self) == 0:
            raise InvalidStateError("El historial de la simulación está vacío.")
        last = len(self) - 1
        if self._cursor < last:
            self._cursor += 1
        return self._ensure_index()[self._cursor]

    def reiniciar(self) -> Snapshot:
        """Vuelve al paso 0 y devuelve su snapshot."""
        if len(self) == 0:
            raise InvalidStateError("El historial de la simulación está vacío.")
        self._cursor = 0
        return self._ensure_index()[0]

    def seek(self, step: int) -> Snapshot:
        """Salta al paso ``step`` (0 … último) y devuelve su snapshot."""
        self._cursor = self._check_step(step)
        return self._ensure_index()[self._cursor]

    # ------------------------------------------------- tuberías críticas
    def critical_rows(self, step: int) -> list[tuple[str, float]]:
        """Tuberías ordenadas por su utilización **máxima hasta** ``step`` (RF10).

        Para cada tubería se toma el mayor porcentaje de utilización entre los
        pasos ``0 … step`` (la tabla de la vista se titula "mayor utilización
        hasta el instante actual"). El orden es descendente por porcentaje y,
        en empate, por identificador ascendente (determinista, S6).

        Args:
            step: Último paso a considerar (0 … ``len(history) - 1``).

        Returns:
            Lista de ``(pipe_id, porcentaje)`` lista para
            ``CriticalTable.set_rows``.
        """
        self._check_step(step)
        index = self._ensure_index()
        maxima: dict[str, float] = {}
        for position in range(step + 1):
            for pipe_id, pct in index[position].items():
                if pct > maxima.get(pipe_id, -1.0):
                    maxima[pipe_id] = pct
        return sorted(maxima.items(), key=lambda item: (-item[1], item[0]))
