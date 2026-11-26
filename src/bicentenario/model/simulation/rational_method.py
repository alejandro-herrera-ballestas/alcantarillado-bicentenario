"""Método racional: genera caudales de escorrentía a partir de la intensidad de lluvia
y repartelos entre los nodos fuente según la capacidad de salida de sus tuberías.
Aplica los supuestos de ``docs/supuestos.md``:

Traduce la intensidad de lluvia de un escenario de precipitación en caudales de
entrada a la red, nodo por nodo, aplicando los supuestos de
``docs/supuestos.md``:

supuesto | descripción
--- | ---
S5 | La intensidad de lluvia es constante durante el escenario.
S6 | El reparto de caudales entre nodos fuente es determinista: no depende
    del orden de iteración ni de la precisión de coma flotante.
S10 | El caudal de escorrentía de una cuenca se calcula con el método racional.
S10b | El caudal de una cuenca sin nodo se reparte entre los nod
os fuente según la capacidad de salida de sus tuberías.
S10c | El caudal de una cuenca con nodo se asigna al nodo de la cuenca.
S11b | La suma de los caudales repartidos entre nodos fuente es igual al 
caudal total de la cuenca sin nodo.
S12 | La utilización de la capacidad de una tubería puede superar el 100 % 
si el caudal ofrecido supera la capacidad máxima.

los supuestos S1, S2, S3, S4, S7, S8 y S9 se aplican en el simulador y no aquí.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Protocol

from bicentenario.model.simulation.rules import split_flow

__all__ = [     #: supuestos aplicados en este módulo
    "RATIONAL_COEFFICIENT",
    "BasinLike",
    "PipeLike",
    "ScenarioLike",
    "compute_inflows",
    "distribute_basin_flow",
    "rational_flow",
    "source_capacity_weights",
]

#: Coeficiente del método racional (S10): 1 mm/h sobre 1 ha ≈ 0.00278 m³/s.
RATIONAL_COEFFICIENT: float = 0.00278


class BasinLike(Protocol):
    """Cuenca de drenaje compatible con ``BasinRecord`` (Persona C)."""

    runoff_coeff: float
    area_ha: float
    node: str | None


class PipeLike(Protocol):
    """Tubería compatible con ``PipeRecord`` (solo lo que usa el reparto)."""

    from_node: str
    qmax: float


class ScenarioLike(Protocol):
    """Escenario de precipitación compatible con ``ScenarioRecord``."""

    intensity_mm_h: float


# ---------------------------------------------------------------------------
# Validaciones internas
# ---------------------------------------------------------------------------
def _finite(value: float, name: str) -> float:
    """Convierte ``value`` en ``float`` y exige que sea un número finito."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} debe ser un número (recibido {value!r}).")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} debe ser un número finito (recibido {value!r}).")
    return number


def _non_negative(value: float, name: str) -> float:
    """Exige un número finito **mayor o igual que 0**."""
    number = _finite(value, name)
    if number < 0:
        raise ValueError(f"{name} no puede ser negativo (recibido {value!r}).")
    return number


# ---------------------------------------------------------------------------
# Fórmula del método racional (S10)
# ---------------------------------------------------------------------------
def rational_flow(runoff_coeff: float, intensity_mm_h: float, area_ha: float) -> float:
    """Caudal de escorrentía de una cuenca según el método racional (S10).

    Aplica ``Q = 0.00278 · C · I · A`` en m³/s, con ``C`` adimensional,
    ``I`` en mm/h y ``A`` en hectáreas. Los tres valores deben ser finitos y
    **no negativos**; ``I = 0`` (tiempo seco) produce ``Q = 0``.
    """
    coefficient = _non_negative(runoff_coeff, "El coeficiente de escorrentía (C)")
    intensity = _non_negative(intensity_mm_h, "La intensidad de lluvia (I, mm/h)")
    area = _non_negative(area_ha, "El área de drenaje (A, ha)")
    return RATIONAL_COEFFICIENT * coefficient * intensity * area


# ---------------------------------------------------------------------------
# Capacidad de salida de cada fuente (S10b, S6)
# ---------------------------------------------------------------------------
def source_capacity_weights(
    source_ids: Sequence[str],
    pipes: Iterable[PipeLike],
) -> dict[str, float]:
    """Capacidad total de salida de cada nodo fuente.

    Suma las ``qmax`` de las tuberías que **salen** de cada fuente (S10b). Las
    claves se devuelven ordenadas y cada suma usa ``math.fsum``, que es exacta
    e independiente del orden de iteración: el reparto es determinista (S6).
    """
    ordered_sources = sorted(dict.fromkeys(str(source) for source in source_ids))
    wanted = set(ordered_sources)
    contributions: dict[str, list[float]] = {source: [] for source in ordered_sources}

    for pipe in pipes:
        node = str(pipe.from_node)
        if node in wanted:
            contributions[node].append(
                _non_negative(pipe.qmax, f"La capacidad (Qmax) de una tubería que sale de '{node}'")
            )

    return {source: math.fsum(contributions[source]) for source in ordered_sources}


# ---------------------------------------------------------------------------
# Reparto de una cuenca sin nodo (S10b, S11b, S6)
# ---------------------------------------------------------------------------
def distribute_basin_flow(
    total_flow: float,
    source_ids: Sequence[str],
    pipes: Iterable[PipeLike],
) -> dict[str, float]:
    """Reparte el caudal de una cuenca sin nodo entre los nodos fuente (S10b).

    El reparto es proporcional a :func:`source_capacity_weights`; si todas las
    capacidades son 0 (o ninguna fuente tiene salidas), es uniforme. Se apoya
    en :func:`~bicentenario.model.simulation.rules.split_flow`, que conserva la
    masa (S11b), y devuelve las claves ordenadas (S6).
    """
    ordered_sources = sorted(dict.fromkeys(str(source) for source in source_ids))
    if not ordered_sources:
        raise ValueError(
            "No hay nodos fuente entre los que repartir el caudal de la cuenca sin nodo."
        )

    weights = source_capacity_weights(ordered_sources, pipes)
    shares = split_flow(total_flow, [weights[source] for source in ordered_sources])
    return {source: share for source, share in zip(ordered_sources, shares)}


# ---------------------------------------------------------------------------
# Aportes por nodo para un escenario (S5, S10, S10b, S10c, S6)
# ---------------------------------------------------------------------------
def compute_inflows(
    scenario: ScenarioLike,
    basins: Iterable[BasinLike],
    pipes: Iterable[PipeLike],
    source_ids: Sequence[str],
) -> dict[str, float]:
    """Aportes de caudal por nodo para un escenario de precipitación.

    Calcula el caudal de cada cuenca con :func:`rational_flow` y lo asigna:

    * cuenca con ``node`` → el 100 % a ese nodo (S10c), acumulando si varias
      cuencas apuntan al mismo pozo;
    * cuenca sin ``node`` (o con ``node`` vacío) → reparto entre las fuentes
      según :func:`distribute_basin_flow` (S10b).

    Como la intensidad es constante durante el escenario (S5), el resultado es
    el mismo en todos los pasos de simulación: se calcula una vez y el
    simulador lo reutiliza. El diccionario devuelto incluye **todas las
    fuentes** (aunque reciban ``0.0``) y los nodos explícitos de las cuencas,
    con las claves ordenadas (S6).
    """
    intensity = _non_negative(scenario.intensity_mm_h, "La intensidad del escenario (mm/h)")
    ordered_sources = sorted(dict.fromkeys(str(source) for source in source_ids))
    pipe_list = list(pipes)

    ordered_basins = sorted(
        basins,
        key=lambda basin: (
            basin.node is None,
            str(basin.node or ""),
            float(basin.runoff_coeff),
            float(basin.area_ha),
        ),
    )

    contributions: dict[str, list[float]] = {source: [] for source in ordered_sources}

    for basin in ordered_basins:
        flow = rational_flow(basin.runoff_coeff, intensity, basin.area_ha)
        node = basin.node
        if node is None or not str(node).strip():
            shares = distribute_basin_flow(flow, ordered_sources, pipe_list)
            for target, share in shares.items():
                contributions.setdefault(target, []).append(share)
        else:
            contributions.setdefault(str(node).strip(), []).append(flow)

    return {
        node: math.fsum(values)
        for node, values in sorted(contributions.items())
    }
