"""Identificación y clasificación de tuberías críticas (RF10).

Los umbrales son los de la sección 7 de la guía y coinciden con
``view/color_scale.py``: 0–25 verde, >25–50 amarillo, >50–75 naranja,
>75–100 rojo, >100 rojo oscuro. Se definen aquí como constantes propias para
que ``model`` no importe la vista; si se cambia la escala, hay que sincronizar
ambos módulos.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from bicentenario.model.ordering import natural_key

__all__ = [
    "LEVELS",
    "CriticalPipe",
    "classify_utilization",
    "critical_pipes",
    "max_utilization_per_pipe",
    "overloaded_pipes",
]

_TOLERANCE = 1e-9

#: (clave, límite superior inclusivo; ``None`` = sin límite)
LEVELS: tuple[tuple[str, float | None], ...] = (
    ("low", 25.0),
    ("moderate", 50.0),
    ("high", 75.0),
    ("near", 100.0),
    ("exceeded", None),
)


def classify_utilization(utilization_pct: float) -> str:
    """Clave del nivel de utilización (``low``…``exceeded``).

    Los límites son inclusivos en el nivel superior, igual que en
    ``color_scale.classify``: 25 → ``low``, 50 → ``moderate``, 75 → ``high``,
    100 → ``near`` y 100.0001 → ``exceeded``.
    """
    value = float(utilization_pct)
    if not math.isfinite(value):
        raise ValueError(f"Utilización no válida: {utilization_pct!r}")
    if value < -_TOLERANCE:
        raise ValueError(f"La utilización no puede ser negativa: {utilization_pct!r}")
    value = max(value, 0.0)
    for key, upper in LEVELS:
        if upper is None or value <= upper + _TOLERANCE:
            return key
    raise AssertionError("unreachable")  # pragma: no cover


@dataclass(frozen=True)
class CriticalPipe:
    """Tubería crítica: mayor utilización observada y su clasificación."""

    pipe_id: str
    max_utilization_pct: float
    peak_step: int
    overloaded: bool
    level: str

    @property
    def label(self) -> str:
        """Etiqueta legible del nivel."""
        return {
            "low": "Baja utilización",
            "moderate": "Utilización moderada",
            "high": "Utilización alta",
            "near": "Cercana a la capacidad",
            "exceeded": "Capacidad excedida",
        }[self.level]


def _snapshots(history: object) -> list[object]:
    """Acepta un historial iterable o con ``get_at``/``__len__``."""
    snapshots = list(history)  # type: ignore[arg-type]
    if snapshots:
        return snapshots
    if hasattr(history, "get_at") and hasattr(history, "__len__"):
        return [history.get_at(i) for i in range(len(history))]  # type: ignore[arg-type]
    return []


def _utilization(value: object) -> float:
    """Utilización de un valor que puede ser ``PipeState`` o un ``float``."""
    attribute = getattr(value, "utilization_pct", None)
    return float(attribute if attribute is not None else value)


def _flow(value: object) -> float:
    """Caudal ofrecido de un valor tipo ``PipeState``."""
    attribute = getattr(value, "flow", None)
    return float(attribute) if attribute is not None else 0.0


def max_utilization_per_pipe(history: object) -> dict[str, tuple[float, int]]:
    """``pipe_id -> (máxima utilización %, paso en que ocurrió)``."""
    maxima: dict[str, tuple[float, int]] = {}
    for index, snapshot in enumerate(_snapshots(history)):
        step = int(getattr(snapshot, "step", index))
        pipes: Mapping[str, object] = getattr(snapshot, "pipes", {})  # type: ignore[assignment]
        for pipe_id, state in pipes.items():
            value = _utilization(state)
            current = maxima.get(str(pipe_id))
            if current is None or value > current[0]:
                maxima[str(pipe_id)] = (value, step)
    return maxima


def critical_pipes(
    history: object,
    *,
    limit: int | None = None,
    min_utilization: float = 0.0,
) -> list[CriticalPipe]:
    """Tuberías ordenadas por utilización máxima (desc) y ID (asc).

    ``limit=None`` devuelve todas; ``min_utilization`` filtra por debajo de
    ese porcentaje. El desempate por ID es determinista (S6).
    """
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        raise ValueError("``limit`` debe ser un entero no negativo o ``None``.")
    rows = [
        CriticalPipe(
            pipe_id=pipe_id,
            max_utilization_pct=value,
            peak_step=step,
            overloaded=value > 100.0 + _TOLERANCE,
            level=classify_utilization(value),
        )
        for pipe_id, (value, step) in max_utilization_per_pipe(history).items()
        if value >= min_utilization
    ]
    rows.sort(key=lambda row: (-row.max_utilization_pct, natural_key(row.pipe_id)))
    return rows[:limit] if limit is not None else rows


def overloaded_pipes(history: object, *, step: int | None = None) -> list[CriticalPipe]:
    """Tuberías por encima del 100 % en un paso o en todo el historial."""
    if step is None:
        return [row for row in critical_pipes(history) if row.overloaded]
    snapshots = _snapshots(history)
    if not 0 <= step < len(snapshots):
        raise IndexError(f"Paso {step} fuera de rango (0…{len(snapshots) - 1}).")
    pipes: Mapping[str, object] = getattr(snapshots[step], "pipes", {})  # type: ignore[assignment]
    rows = [
        CriticalPipe(
            pipe_id=str(pipe_id),
            max_utilization_pct=_utilization(state),
            peak_step=step,
            overloaded=_utilization(state) > 100.0 + _TOLERANCE,
            level=classify_utilization(_utilization(state)),
        )
        for pipe_id, state in pipes.items()
    ]
    rows.sort(key=lambda row: (-row.max_utilization_pct, natural_key(row.pipe_id)))
    return [row for row in rows if row.overloaded]


def offered_flows(snapshot: object) -> dict[str, float]:
    """Caudal ofrecido por tubería en un instante (para balance de masa)."""
    pipes: Mapping[str, object] = getattr(snapshot, "pipes", {})  # type: ignore[assignment]
    return {str(pipe_id): _flow(state) for pipe_id, state in pipes.items()}
