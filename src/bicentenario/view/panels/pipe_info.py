"""Información de la tubería seleccionada (RF08)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bicentenario.io.records import PipeRecord
from bicentenario.view.color_scale import NO_DATA_COLOR, classify

_FIELDS = (
    ("id", "Tubería"), ("nodes", "Conexión"), ("length", "Longitud"), ("diameter", "Diámetro"),
    ("roughness", "Rugosidad n"), ("slope", "Pendiente S"), ("qmax", "Capacidad máx."),
    ("time", "Instante"), ("util", "Utilización"),
)


class PipeInfoPanel(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="Tubería seleccionada", padding=8)
        self._vars = {key: tk.StringVar(value="—") for key, _ in _FIELDS}
        for row, (key, label) in enumerate(_FIELDS):
            ttk.Label(self, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=(0, 8))
            ttk.Label(self, textvariable=self._vars[key]).grid(row=row, column=1, sticky="w")
        self._chip = tk.Label(self, bg=NO_DATA_COLOR, width=3, relief="solid", borderwidth=1)
        self._chip.grid(row=len(_FIELDS) - 1, column=2, padx=(6, 0))
        ttk.Label(self, text="Haga clic en una tubería del grafo, en la tabla de críticas, "
                             "o búsquela por ID.", wraplength=300, foreground="#555555").grid(
            row=len(_FIELDS), column=0, columnspan=3, sticky="w", pady=(6, 0))

    def show(self, pipe: PipeRecord, *, time_text: str | None = None, pct: float | None = None) -> None:
        diameter = f"{pipe.diameter_m:g} m"
        if pipe.diameter_in is not None:
            diameter += f" ({pipe.diameter_in:g} in)"
        self._vars["id"].set(pipe.id)
        self._vars["nodes"].set(f"{pipe.from_node} → {pipe.to_node}")
        self._vars["length"].set(f"{pipe.length_m:,.2f} m")
        self._vars["diameter"].set(diameter)
        self._vars["roughness"].set(f"{pipe.roughness_n:g}")
        self._vars["slope"].set(f"{pipe.slope:g} m/m")
        self._vars["qmax"].set(f"{pipe.qmax:.4f} m³/s")
        self._vars["time"].set(time_text or "—")
        if pct is None:
            self._vars["util"].set("—")
            self._chip.configure(bg=NO_DATA_COLOR)
        else:
            level = classify(pct)
            self._vars["util"].set(f"{pct:.1f} %  ({level.description})")
            self._chip.configure(bg=level.color)

    def clear(self) -> None:
        for var in self._vars.values():
            var.set("—")
        self._chip.configure(bg=NO_DATA_COLOR)
