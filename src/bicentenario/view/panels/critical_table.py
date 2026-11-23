"""Tabla de tuberías críticas (RF10)."""

from __future__ import annotations

from tkinter import ttk

from bicentenario.view.color_scale import LEVELS, classify


class CriticalTable(ttk.LabelFrame):
    def __init__(self, parent, on_select=None):
        """``on_select(pipe_id)`` se llama al elegir una fila."""
        super().__init__(parent, text="Tuberías críticas (mayor utilización hasta el instante actual)",
                         padding=6)
        self._on_select = on_select
        self._updating = False
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(self, columns=("pipe", "pct", "state"), show="headings", height=6)
        for column, heading, width in (("pipe", "Tubería", 80), ("pct", "Utilización máx. (%)", 140),
                                       ("state", "Estado", 220)):
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor="w")
        for level in LEVELS:
            self.tree.tag_configure(level.key, background=level.color,
                                    foreground="white" if level.key in ("near", "exceeded") else "black")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._selected)

    def set_rows(self, rows: list[tuple[str, float]]) -> None:
        """``rows``: lista de ``(id_tubería, porcentaje)``, ya ordenada."""
        self._updating = True            # borrar/insertar filas dispara <<TreeviewSelect>>
        try:
            self.tree.delete(*self.tree.get_children())
            for pipe_id, pct in rows:
                level = classify(pct)
                self.tree.insert("", "end", iid=pipe_id, values=(pipe_id, f"{pct:.1f}", level.description),
                                 tags=(level.key,))
        finally:
            self._updating = False

    def _selected(self, _event) -> None:
        if self._updating or self._on_select is None:
            return
        chosen = self.tree.selection()
        if chosen:
            self._on_select(chosen[0])
