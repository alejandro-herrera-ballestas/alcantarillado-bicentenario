"""Simulador de la red 

Ejecuta un escenario paso a paso: aportes (método racional), reparto en pozos,
tránsito por tubería y retención de excesos. Devuelve el historial que consume
la vista. Supuestos S4–S12 en ``docs/supuestos.md``.

Integración: ``Simulator(dataset, params).run(scenario_id)``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Protocol

from bicentenario.errors import InputValidationError, InvalidStateError
from bicentenario.io.records import natural_key
from bicentenario.model.simulation.rational_method import compute_inflows
from bicentenario.model.simulation.rules import (
    REFERENCE_VELOCITY_M_S,
    split_capacity,
    split_flow,
    transit_steps,
)
from bicentenario.model.simulation.snapshot import (
    NodeState,
    PipeState,
    SimulationHistory,
    Snapshot,
)

__all__ = ["QueueLike", "Simulator", "simulate"]


# --- Tipos de entrada (compatibles con records.py) ---
class PipeLike(Protocol):
    id: str
    from_node: str
    to_node: str
    qmax: float
    length_m: float


class BasinLike(Protocol):
    runoff_coeff: float
    area_ha: float
    node: str | None


class ScenarioLike(Protocol):
    id: str
    intensity_mm_h: float


class ParamsLike(Protocol):
    step_min: float
    n_steps: int


class DatasetLike(Protocol):
    sources: Sequence[str]
    sinks: Sequence[str]
    pipes: Sequence[PipeLike]
    basins: Sequence[BasinLike]
    scenarios: Sequence[ScenarioLike]


class QueueLike(Protocol):
    def enqueue(self, item: float) -> None: ...

    def dequeue(self) -> float: ...

    def __len__(self) -> int: ...


# --- Cola de Persona A ---
_ENQUEUE_NAMES = ("enqueue", "push", "put", "add")
_DEQUEUE_NAMES = ("dequeue", "pop", "get", "poll", "remove", "popleft")


def _first_method(target: object, names: Sequence[str], action: str):
    for name in names:
        method = getattr(target, name, None)
        if callable(method):
            return method
    raise InvalidStateError(
        f"La Queue de Persona A no permite {action} "
        f"(se esperaba alguno de: {', '.join(names)})."
    )


def _positive(value: float, name: str) -> float:
    """Exige un número finito mayor que 0."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise InputValidationError(f"{name} debe ser un número mayor que 0 (recibido {value!r}).")
    return float(value)


class _QueueAdapter:
    """Normaliza la API de la ``Queue`` de Persona A."""

    def __init__(self, queue: object) -> None:
        self._queue = queue
        self._enqueue = _first_method(queue, _ENQUEUE_NAMES, "encolar")
        self._dequeue = _first_method(queue, _DEQUEUE_NAMES, "desencolar")

    def __len__(self) -> int:
        try:
            return len(self._queue)  # type: ignore[arg-type]
        except TypeError as exc:
            raise InvalidStateError("La Queue de Persona A no implementa __len__.") from exc

    def put(self, item: float) -> None:
        self._enqueue(item)

    def get(self) -> float:
        return self._dequeue()


def _default_queue_factory() -> QueueLike:
    try:
        from bicentenario.model.structures.queue import Queue
    except ImportError as exc:
        raise InvalidStateError(
            "La simulación necesita la Queue de Persona A "
            "(src/bicentenario/model/structures/queue.py), aún sin implementar. "
            "Mientras tanto, use Simulator(..., queue_factory=...)."
        ) from exc
    return _QueueAdapter(Queue())


def _as_queue(queue: object) -> _QueueAdapter:
    """Envuelve una cola cruda; deja intacto un adaptador ya construido."""
    return queue if isinstance(queue, _QueueAdapter) else _QueueAdapter(queue)


# --- Simulador ---
class Simulator:
    """Simula un escenario completo y entrega su historial."""

    def __init__(
        self,
        dataset: DatasetLike,
        params: ParamsLike,
        *,
        velocity_m_s: float = REFERENCE_VELOCITY_M_S,
        queue_factory: Callable[[], QueueLike] | None = None,
        history_factory: Callable[[], SimulationHistory] | None = None,
    ) -> None:
        """Valida los datos y precalcula topología, tránsitos y capacidades.

        ``queue_factory`` y ``history_factory`` permiten sustituir la ``Queue``
        y el historial de Persona A (útil mientras no estén implementados).
        """
        self._velocity = _positive(velocity_m_s, "La velocidad de referencia")
        self._step_min = _positive(params.step_min, "El paso de simulación")

        n_steps = params.n_steps
        if isinstance(n_steps, bool) or not isinstance(n_steps, int) or n_steps < 0:
            raise InputValidationError(
                f"El número de pasos debe ser un entero mayor o igual que 0 (recibido {n_steps!r})."
            )
        self._n_steps = n_steps

        pipes = sorted(dataset.pipes, key=lambda pipe: natural_key(pipe.id))
        if not pipes:
            raise InputValidationError("La red no tiene tuberías para simular.")
        seen: set[str] = set()
        for pipe in pipes:
            pipe_id = str(pipe.id)
            if pipe_id in seen:
                raise InputValidationError(f"La tubería '{pipe_id}' está repetida en los datos.")
            seen.add(pipe_id)
            _positive(pipe.qmax, f"La capacidad de la tubería {pipe_id}")
            _positive(pipe.length_m, f"La longitud de la tubería {pipe_id}")

        self._pipes = pipes
        self._sources = frozenset(str(source) for source in dataset.sources)
        self._sinks = frozenset(str(sink) for sink in dataset.sinks)
        self._basins = tuple(dataset.basins)
        self._scenarios = tuple(dataset.scenarios)

        nodes = {str(pipe.from_node) for pipe in pipes}
        nodes |= {str(pipe.to_node) for pipe in pipes}
        nodes |= self._sources | self._sinks
        nodes |= {
            str(basin.node).strip()
            for basin in dataset.basins
            if basin.node is not None and str(basin.node).strip()
        }
        self._nodes = sorted(nodes, key=natural_key)

        outgoing: dict[str, list[PipeLike]] = {}
        for pipe in pipes:
            outgoing.setdefault(str(pipe.from_node), []).append(pipe)
        self._outgoing = {node: tuple(items) for node, items in outgoing.items()}
        self._capacities = {
            node: tuple(pipe.qmax for pipe in items) for node, items in self._outgoing.items()
        }

        # S9: t_i = max(1, ceil(L / (V · 60 · Δt)))
        self._transit = {
            pipe.id: transit_steps(pipe.length_m, self._velocity, self._step_min)
            for pipe in pipes
        }

        self._queue_factory = queue_factory or _default_queue_factory
        self._history_factory = history_factory or SimulationHistory

    def run(self, scenario: str | ScenarioLike) -> SimulationHistory:
        """Devuelve ``n_steps + 1`` snapshots (el 0 es la condición inicial)."""
        record = self._resolve_scenario(scenario)
        inflows = self._inflows(record)

        queues = {pipe.id: _as_queue(self._queue_factory()) for pipe in self._pipes}
        history = self._history_factory()
        stored = dict.fromkeys(self._nodes, 0.0)
        cumulative_excess = dict.fromkeys((pipe.id for pipe in self._pipes), 0.0)

        history.append(self._snapshot(0, {}, {}, stored, cumulative_excess))
        for step in range(1, self._n_steps + 1):
            offered, demand, stored = self._advance(
                inflows, queues, stored, cumulative_excess
            )
            history.append(self._snapshot(step, offered, demand, stored, cumulative_excess))
        return history

    def _resolve_scenario(self, scenario: str | ScenarioLike) -> ScenarioLike:
        if not isinstance(scenario, str):
            if not hasattr(scenario, "intensity_mm_h"):
                raise InputValidationError(
                    "El escenario debe ser un id o un registro con 'intensity_mm_h' "
                    f"(recibido {scenario!r})."
                )
            return scenario
        wanted = scenario.strip()
        for candidate in self._scenarios:
            if str(candidate.id) == wanted:
                return candidate
        available = ", ".join(str(item.id) for item in self._scenarios)
        raise InputValidationError(
            f"No existe el escenario '{scenario}'. Disponibles: {available}."
        )

    def _inflows(self, scenario: ScenarioLike) -> dict[str, float]:
        try:
            return compute_inflows(
                scenario,
                self._basins,
                self._pipes,
                sorted(self._sources, key=natural_key),
            )
        except ValueError as exc:
            raise InputValidationError(str(exc)) from exc

    def _advance(
        self,
        inflows: dict[str, float],
        queues: dict[str, _QueueAdapter],
        stored: dict[str, float],
        cumulative_excess: dict[str, float],
    ) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
        """Un paso: llegadas, reparto, transporte y retención."""
        arrivals = self._arrivals(queues)
        offered = dict.fromkeys((pipe.id for pipe in self._pipes), 0.0)
        demand: dict[str, float] = {}

        for node in self._nodes:
            inflow = arrivals.get(node, 0.0) + inflows.get(node, 0.0)
            demand[node] = inflow

            if node in self._sinks:
                stored[node] = 0.0                     # S8: descarga fuera del modelo
                continue

            outlets = self._outgoing.get(node)
            if not outlets:
                stored[node] += inflow                 # S12c: sin salida, se acumula
                continue

            capacities = self._capacities[node]
            available = stored[node] + inflow
            shares = split_flow(available, capacities)
            demand_shares = split_flow(inflow, capacities)   # S12d: sin retenido

            retained = 0.0
            for pipe, share, demand_share in zip(outlets, shares, demand_shares):
                transported, excess = split_capacity(share, pipe.qmax)
                retained += excess
                cumulative_excess[pipe.id] += excess
                offered[pipe.id] = demand_share
                queues[pipe.id].put(transported)       # S11c: tarda t_i pasos
            stored[node] = retained                    # S12b: el exceso permanece

        return offered, demand, stored

    def _arrivals(self, queues: dict[str, _QueueAdapter]) -> dict[str, float]:
        """Extrae el agua que completa su tránsito en este paso."""
        arrivals: dict[str, float] = {}
        for pipe in self._pipes:
            queue = queues[pipe.id]
            if len(queue) >= self._transit[pipe.id]:
                value = queue.get()
                if value:
                    target = str(pipe.to_node)
                    arrivals[target] = arrivals.get(target, 0.0) + value
        return arrivals

    def _snapshot(
        self,
        step: int,
        offered: dict[str, float],
        demand: dict[str, float],
        stored: dict[str, float],
        cumulative_excess: dict[str, float],
    ) -> Snapshot:
        """Construye el estado visible del paso."""
        pipes = {
            pipe.id: PipeState.from_flow(
                pipe.id,
                offered.get(pipe.id, 0.0),
                pipe.qmax,
                excess=cumulative_excess[pipe.id],
            )
            for pipe in self._pipes
        }
        nodes = {
            node: NodeState(
                node_id=node,
                inflow=demand.get(node, 0.0),
                stored=stored[node],
                is_source=node in self._sources,
                is_sink=node in self._sinks,
            )
            for node in self._nodes
        }
        return Snapshot(
            step=step,
            time_min=step * self._step_min,
            pipes=pipes,
            nodes=nodes,
        )


def simulate(
    dataset: DatasetLike,
    scenario: str | ScenarioLike,
    params: ParamsLike,
    *,
    velocity_m_s: float = REFERENCE_VELOCITY_M_S,
    queue_factory: Callable[[], QueueLike] | None = None,
    history_factory: Callable[[], SimulationHistory] | None = None,
) -> SimulationHistory:
    """Atajo: ``Simulator(dataset, params).run(scenario)``."""
    return Simulator(
        dataset,
        params,
        velocity_m_s=velocity_m_s,
        queue_factory=queue_factory,
        history_factory=history_factory,
    ).run(scenario)
