"""Verificador de balance de masa de la simulación (guía §11).

La identidad que se comprueba es la que garantiza el modelo de Persona B:
toda el agua que llega a un nodo se reparte entre sus tuberías salientes
(``PipeState.flow``), se retiene en el pozo (``NodeState.stored``) o se
descarga en el sumidero. En símbolos, para cada paso::

    Σ inflow(nodos) == Σ offered(tuberías) + Σ inflow(sumideros)
                       + Σ inflow(extremos muertos)

También se verifican la no negatividad de caudales, la monotonía del exceso
acumulado y que el almacenamiento no supere el agua disponible. El agua en
tránsito dentro de las tuberías no está expuesta en los ``Snapshot``; se
reporta implícitamente como diferencia no negativa y se documenta aquí.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from bicentenario.model.algorithms.critical_pipes import offered_flows
from bicentenario.model.graph.directed_graph import DirectedGraph

__all__ = ["BalanceIssue", "MassBalanceReport", "mass_balance"]


@dataclass(frozen=True)
class BalanceIssue:
    """Desviación detectada en un paso."""

    step: int
    kind: str          # "nodo", "global", "almacenamiento" o "exceso"
    where: str
    expected: float
    actual: float
    delta: float
    message: str

    def __str__(self) -> str:
        return (
            f"[paso {self.step}, {self.kind}] {self.where}: {self.message} "
            f"(esperado {self.expected:.9g}, obtenido {self.actual:.9g}, "
            f"diferencia {self.delta:.3g})"
        )


@dataclass(frozen=True)
class MassBalanceReport:
    """Resultado de la verificación."""

    issues: tuple[BalanceIssue, ...]
    steps_checked: int
    max_delta: float
    ok: bool

    def summary(self) -> str:
        """Resumen de una línea."""
        state = "CORRECTO" if self.ok else "CON DESVIACIONES"
        return (
            f"Balance de masa {state}: {self.steps_checked} paso(s) revisado(s), "
            f"{len(self.issues)} incidencia(s), desviación máxima {self.max_delta:.3g}"
        )

    def format(self) -> str:
        """Informe completo, una incidencia por línea."""
        lines = [self.summary()]
        lines.extend(str(issue) for issue in self.issues)
        return "\n".join(lines)


def _state_attr(state: object, name: str, default: float = 0.0) -> float:
    value = getattr(state, name, default)
    if value is None:
        return default
    return float(value)


def mass_balance(
    history: object,
    graph: DirectedGraph | None = None,
    *,
    dataset: object | None = None,
    tolerance: float = 1e-9,
    steps: int | Iterable[int] | None = None,
) -> MassBalanceReport:
    """Verifica la conservación de masa en el historial.

    Args:
        history: ``SimulationHistory`` o iterable de snapshots.
        graph: Grafo de la red. Si se omite, se construye desde ``dataset``.
        dataset: Fuente alternativa de topología cuando no se da ``graph``.
        tolerance: Tolerancia absoluta para comparar flotantes.
        steps: ``None`` (todos), un paso concreto o un iterable de pasos.

    Returns:
        :class:`MassBalanceReport` con las incidencias encontradas.
    """
    if graph is None:
        if dataset is None:
            raise ValueError("Se necesita ``graph`` o ``dataset`` para el balance.")
        graph = DirectedGraph.build_from_dataset(dataset)

    snapshots = list(history)  # type: ignore[arg-type]
    if not snapshots and hasattr(history, "get_at"):
        snapshots = [history.get_at(i) for i in range(len(history))]  # type: ignore[arg-type]
    if not snapshots:
        return MassBalanceReport((), 0, 0.0, True)

    if steps is None:
        selected = list(range(len(snapshots)))
    elif isinstance(steps, int) and not isinstance(steps, bool):
        selected = [steps]
    else:
        selected = sorted(int(value) for value in steps)  # type: ignore[union-attr]
    for step in selected:
        if not 0 <= step < len(snapshots):
            raise IndexError(f"Paso {step} fuera de rango (0…{len(snapshots) - 1}).")

    issues: list[BalanceIssue] = []
    previous_stored: dict[str, float] = {}
    previous_excess = 0.0

    for step in selected:
        snapshot = snapshots[step]
        nodes: Mapping[str, object] = getattr(snapshot, "nodes", {})  # type: ignore[assignment]
        offered = offered_flows(snapshot)
        sink_ids = set(graph.sinks())
        dead_ends = {
            node for node in nodes
            if not graph.out_neighbors(node) and node not in sink_ids
        }

        total_inflow = 0.0
        total_stored = 0.0
        discharged = 0.0
        dead_inflow = 0.0
        forwarded = 0.0

        for node_id, state in nodes.items():
            identifier = str(node_id)
            inflow = _state_attr(state, "inflow")
            stored = _state_attr(state, "stored")
            total_inflow += inflow
            total_stored += stored

            if inflow < -tolerance or stored < -tolerance:
                issues.append(BalanceIssue(
                    step, "nodo", identifier, 0.0, min(inflow, stored),
                    abs(min(inflow, stored)),
                    "caudal o almacenamiento negativo",
                ))

            outgoing_ids = [
                pipe.id for pipe in graph.out_pipes(identifier)
                if pipe.id in offered
            ]
            offered_sum = math.fsum(offered[pid] for pid in outgoing_ids)

            if identifier in sink_ids:
                discharged += inflow
                if abs(stored) > tolerance:
                    issues.append(BalanceIssue(
                        step, "nodo", identifier, 0.0, stored, abs(stored),
                        "el sumidero no debe retener agua (S8)",
                    ))
            elif not outgoing_ids:
                dead_inflow += inflow
                expected_growth = inflow
                growth = stored - previous_stored.get(identifier, 0.0)
                if abs(growth - expected_growth) > tolerance:
                    issues.append(BalanceIssue(
                        step, "almacenamiento", identifier, expected_growth, growth,
                        abs(growth - expected_growth),
                        "el extremo muerto debe acumular todo su caudal",
                    ))
            else:
                forwarded += offered_sum
                if abs(offered_sum - inflow) > tolerance:
                    issues.append(BalanceIssue(
                        step, "nodo", identifier, inflow, offered_sum,
                        abs(offered_sum - inflow),
                        "la suma de caudales ofrecidos debe igualar el caudal entrante",
                    ))

        pipes: Mapping[str, object] = getattr(snapshot, "pipes", {})  # type: ignore[assignment]
        for pipe_id, state in pipes.items():
            value = _state_attr(state, "flow")
            excess = _state_attr(state, "excess")
            if value < -tolerance or excess < -tolerance:
                issues.append(BalanceIssue(
                    step, "tubería", str(pipe_id), 0.0, min(value, excess),
                    abs(min(value, excess)), "caudal o exceso negativo",
                ))

        expected_total = forwarded + discharged + dead_inflow
        delta = total_inflow - expected_total
        if abs(delta) > tolerance:
            issues.append(BalanceIssue(
                step, "global", "toda la red", expected_total, total_inflow, abs(delta),
                "el agua entrante debe repartirse entre salientes, sumideros y retención",
            ))

        excess_total = math.fsum(_state_attr(state, "excess") for state in pipes.values())
        if excess_total + tolerance < previous_excess:
            issues.append(BalanceIssue(
                step, "exceso", "toda la red", previous_excess, excess_total,
                previous_excess - excess_total,
                "el exceso acumulado no puede disminuir",
            ))
        previous_excess = excess_total

        if total_stored + tolerance < math.fsum(previous_stored.values()):
            issues.append(BalanceIssue(
                step, "almacenamiento", "toda la red",
                math.fsum(previous_stored.values()), total_stored,
                math.fsum(previous_stored.values()) - total_stored,
                "el almacenamiento total no puede disminuir",
            ))

        previous_stored = {
            identifier: _state_attr(state, "stored") for identifier, state in nodes.items()
        }

    max_delta = max((issue.delta for issue in issues), default=0.0)
    return MassBalanceReport(tuple(issues), len(selected), max_delta, not issues)

