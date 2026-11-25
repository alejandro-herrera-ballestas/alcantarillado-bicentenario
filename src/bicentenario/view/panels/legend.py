"""Leyenda de colores (sección 9 del enunciado)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bicentenario.view.color_scale import NO_DATA_COLOR, legend_entries


class LegendPanel(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="Leyenda (% de utilización)", padding=8)
        rows = [(rng, f"{label}: {desc}", color) for rng, label, desc, color in legend_entries()]
        rows.append(("—", "Gris: sin datos (simulación no iniciada)", NO_DATA_COLOR))
        for i, (rng, text, color) in enumerate(rows):
            tk.Label(self, bg=color, width=3, relief="solid", borderwidth=1).grid(
                row=i, column=0, padx=(0, 6), pady=1)
            ttk.Label(self, text=f"{rng:<9} {text}").grid(row=i, column=1, sticky="w")
        ttk.Label(self, text="Círculo con borde azul = fuente · Cuadrado negro = sumidero (PTAR)",
                  wraplength=300, foreground="#555555").grid(
            row=len(rows), column=0, columnspan=2, sticky="w", pady=(6, 0))
