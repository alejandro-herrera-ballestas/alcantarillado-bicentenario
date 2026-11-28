"""Tubería (arista dirigida del grafo).

Los nombres de campo son idénticos a los de ``io.records.PipeRecord`` y a los
que Persona B espera en su protocolo ``PipeLike``. ``from_record`` hace la
conversión por atributos, sin importar el paquete ``io``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from bicentenario.errors import InputValidationError

__all__ = ["Pipe"]


@dataclass(frozen=True)
class Pipe:
    """Arista dirigida ``from_node -> to_node`` con datos hidráulicos."""

    id: str
    from_node: str
    to_node: str
    diameter_m: float
    roughness_n: float
    slope: float
    qmax: float
    length_m: float
    diameter_in: float | None = None
    row: int | None = None

    @classmethod
    def from_record(cls, record: object) -> "Pipe":
        """Construye una ``Pipe`` desde ``PipeRecord`` o cualquier objeto similar."""
        return cls(
            id=str(getattr(record, "id")),
            from_node=str(getattr(record, "from_node")),
            to_node=str(getattr(record, "to_node")),
            diameter_m=float(getattr(record, "diameter_m")),
            roughness_n=float(getattr(record, "roughness_n")),
            slope=float(getattr(record, "slope")),
            qmax=float(getattr(record, "qmax")),
            length_m=float(getattr(record, "length_m")),
            diameter_in=(
                None if getattr(record, "diameter_in", None) is None
                else float(getattr(record, "diameter_in"))
            ),
            row=getattr(record, "row", None),
        )

    def validate(self) -> None:
        """Comprueba que los datos numéricos sean finitos y positivos."""
        if not self.id or self.from_node == self.to_node:
            raise InputValidationError(
                f"Tubería {self.id!r}: se necesitan extremos distintos."
            )
        for name in ("diameter_m", "roughness_n", "slope", "qmax", "length_m"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise InputValidationError(
                    f"Tubería {self.id}: {name} debe ser finito y mayor que 0."
                )
