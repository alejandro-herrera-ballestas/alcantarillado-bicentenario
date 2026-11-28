"""Cuenca de drenaje (área y coeficiente de escorrentía)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from bicentenario.errors import InputValidationError

__all__ = ["Basin"]


@dataclass(frozen=True)
class Basin:
    """Cuenca usada por el método racional ``Q = 0.00278 · C · I · A``."""

    runoff_coeff: float
    area_ha: float
    node: str | None = None
    row: int | None = None

    @classmethod
    def from_record(cls, record: object) -> "Basin":
        """Construye una ``Basin`` desde ``BasinRecord`` o similar."""
        node = getattr(record, "node", None)
        return cls(
            runoff_coeff=float(getattr(record, "runoff_coeff")),
            area_ha=float(getattr(record, "area_ha")),
            node=None if node is None else str(node).strip(),
            row=getattr(record, "row", None),
        )

    def validate(self) -> None:
        """Comprueba rangos de ``C`` y ``A``."""
        if not math.isfinite(self.runoff_coeff) or not 0 <= self.runoff_coeff <= 1:
            raise InputValidationError(
                f"El coeficiente de escorrentía C={self.runoff_coeff!r} debe estar entre 0 y 1."
            )
        if not math.isfinite(self.area_ha) or self.area_ha <= 0:
            raise InputValidationError(
                f"El área de drenaje A={self.area_ha!r} debe ser mayor que 0."
            )
