"""Escala de colores de utilización (RF07, sección 7 del enunciado).

    0–25 %   Verde         Baja utilización
    >25–50 % Amarillo      Utilización moderada
    >50–75 % Naranja       Utilización alta
    >75–100 % Rojo         Cercana a la capacidad máxima
    >100 %   Rojo oscuro   Capacidad excedida


Este modulo es una función pura: no depende de Tkinter, así que se prueba sola.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_TOLERANCE = 1e-9

NO_DATA_COLOR = "#B0B0B0"   # gris: tubería sin dato (simulación no iniciada)


@dataclass(frozen=True)
class UtilizationLevel:
    key: str
    label: str            # nombre del color
    description: str      # estado
    lower: float          # límite inferior (excluido, salvo en el primer nivel)
    upper: float | None   # límite superior (incluido); None = sin límite
    color: str            # color hexadecimal

    @property
    def range_text(self) -> str:
        if self.upper is None:
            return f">{self.lower:g} %"
        if self.lower == 0:
            return f"0–{self.upper:g} %"
        return f">{self.lower:g}–{self.upper:g} %"


LEVELS: tuple[UtilizationLevel, ...] = (
    UtilizationLevel("low", "Verde", "Baja utilización", 0, 25, "#2E9E44"),
    UtilizationLevel("moderate", "Amarillo", "Utilización moderada", 25, 50, "#F2C811"),
    UtilizationLevel("high", "Naranja", "Utilización alta", 50, 75, "#F28C28"),
    UtilizationLevel("near", "Rojo", "Cercana a la capacidad máxima", 75, 100, "#D62728"),
    UtilizationLevel("exceeded", "Rojo oscuro", "Capacidad excedida", 100, None, "#7A0B0B"),
)


def classify(utilization_pct: float) -> UtilizationLevel:
    """Nivel de la escala al que pertenece un porcentaje de utilización.

    Lanza ``ValueError`` si el valor es NaN, infinito o negativo (eso indicaría
    un error en la simulación, no un caso normal). Negativos de ruido numérico
    (> -1e-9) se tratan como 0.
    """
    value = float(utilization_pct)
    if not math.isfinite(value):
        raise ValueError(f"Utilización no válida: {utilization_pct!r}")
    if value < -_TOLERANCE:
        raise ValueError(f"La utilización no puede ser negativa: {utilization_pct!r}")
    value = max(value, 0.0)
    for level in LEVELS:
        if level.upper is None or value <= level.upper + _TOLERANCE:
            return level
    raise AssertionError("unreachable")  # pragma: no cover


def utilization_color(utilization_pct: float) -> str:
    """Color hexadecimal para un porcentaje de utilización."""
    return classify(utilization_pct).color


def legend_entries() -> list[tuple[str, str, str, str]]:
    """Filas de la leyenda: (rango, nombre del color, estado, color hex)."""
    return [(lv.range_text, lv.label, lv.description, lv.color) for lv in LEVELS]
