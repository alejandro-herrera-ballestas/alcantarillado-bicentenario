"""Resumen de resultados del escenario."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class SummaryPanel(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="Resumen del escenario", padding=8)
        self._text = tk.StringVar(value="Cargue los datos y ejecute un escenario.")
        ttk.Label(self, textvariable=self._text, justify="left", anchor="nw",
                  wraplength=330).grid(row=0, column=0, sticky="nw")

    def set_text(self, text: str) -> None:
        self._text.set(text)
