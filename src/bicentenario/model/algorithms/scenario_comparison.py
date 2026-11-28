"""Comparación del comportamiento de la red bajo dos escenarios (RF11).

Función pura: recibe dos historiales y devuelve datos inmutables, sin tocar la
interfaz. La vista o el exportador deciden después cómo presentarlos.
"""

from __future__ import annotations

from dataclasses import dataclass

from bicentenario.model.algorithms.critical_pipes import max_utilization_per_pipe
from bicentenario.model.ordering import natural_key

__all__ = ["PipeDelta", "ScenarioComparison", "compare_scenarios"]


@dataclass(frozen=True)
class PipeDelta:
    """Diferencia de utilización máxima de una tubería entre dos escenarios."""

    pipe_id: str
    a_pct: float
    b_pct: float

    @property
    def delta_pct(self) -> float:
        """``B − A`` (positivo = el escenario B exige más)."""
        return self.b_pct - self.a_pct


@dataclass(frozen=True)
class ScenarioComparison:
    """Resumen comparativo de dos escenarios."""

    name_a: str
    name_b: str
    steps_a: int
    steps_b: int
    overloaded_a: int
    overloaded_b: int
    per_pipe: tuple[PipeDelta, ...]

    @property
    def max_pct_a(self) -> float:
        """Mayor utilización del escenario A."""
        return max((row.a_pct for row in self.per_pipe), default=0.0)

    @property
    def max_pct_b(self) -> float:
        """Mayor utilización del escenario B."""
        return max((row.b_pct for row in self.per_pipe), default=0.0)

    @property
    def most_affected(self) -> PipeDelta | None:
        """Tubería con mayor incremento de utilización (B respecto a A)."""
        return max(self.per_pipe, key=lambda row: (row.delta_pct, natural_key(row.pipe_id)),
                   default=None)

    def to_rows(self) -> list[tuple[str, float, float, float]]:
        """Filas ``(ID, A%, B%, diferencia%)`` listas para exportar."""
        return [
            (row.pipe_id, row.a_pct, row.b_pct, row.delta_pct)
            for row in self.per_pipe
        ]

    def summary(self) -> str:
        """Resumen legible."""
        worst = self.most_affected
        detail = (f" Mayor incremento: {worst.pipe_id} ({worst.delta_pct:+.1f} pp)."
                  if worst is not None else "")
        return (
            f"{self.name_a} vs {self.name_b}: máximo {self.max_pct_a:.1f} % → "
            f"{self.max_pct_b:.1f} %; sobrecargadas {self.overloaded_a} → "
            f"{self.overloaded_b}.{detail}"
        )


def compare_scenarios(
    history_a: object,
    history_b: object,
    *,
    name_a: str = "Escenario A",
    name_b: str = "Escenario B",
) -> ScenarioComparison:
    """Compara dos historiales usando la utilización máxima por tubería.

    Las filas se ordenan por diferencia absoluta descendente y, en empate, por
    ID natural, para que el resultado sea determinista (S6).
    """
    maxima_a = max_utilization_per_pipe(history_a)
    maxima_b = max_utilization_per_pipe(history_b)
    pipe_ids = sorted(set(maxima_a) | set(maxima_b), key=natural_key)
    rows = tuple(
        PipeDelta(
            pipe_id=pipe_id,
            a_pct=maxima_a.get(pipe_id, (0.0, 0))[0],
            b_pct=maxima_b.get(pipe_id, (0.0, 0))[0],
        )
        for pipe_id in pipe_ids
    )
    ordered = tuple(sorted(
        rows,
        key=lambda row: (-abs(row.delta_pct), natural_key(row.pipe_id)),
    ))
    return ScenarioComparison(
        name_a=name_a,
        name_b=name_b,
        steps_a=len(history_a),  # type: ignore[arg-type]
        steps_b=len(history_b),  # type: ignore[arg-type]
        overloaded_a=sum(1 for value, _ in maxima_a.values() if value > 100.0),
        overloaded_b=sum(1 for value, _ in maxima_b.values() if value > 100.0),
        per_pipe=ordered,
    )
