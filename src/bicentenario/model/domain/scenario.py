"""Escenario de precipitación (intensidad constante en mm/h)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from bicentenario.errors import InputValidationError

__all__ = ["Scenario"]


@dataclass(frozen=True)
class Scenario:
    """Escenario ``id`` con intensidad ``I`` y condición descriptiva."""

    id: str
    intensity_mm_h: float
    condition: str = ""
    row: int | None = None

    @classmethod
    def from_record(cls, record: object) -> "Scenario":
        """Construye un ``Scenario`` desde ``ScenarioRecord`` o similar."""
        return cls(
            id=str(getattr(record, "id")),
            intensity_mm_h=float(getattr(record, "intensity_mm_h")),
            condition=str(getattr(record, "condition", "") or ""),
            row=getattr(record, "row", None),
        )

    def validate(self) -> None:
        """Comprueba que la intensidad sea finita y no negativa."""
        if not math.isfinite(self.intensity_mm_h) or self.intensity_mm_h < 0:
            raise InputValidationError(
                f"Escenario {self.id}: la intensidad debe ser finita y no negativa."
            )
