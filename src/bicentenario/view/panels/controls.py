"""Panel de controles: escenario, duración, intervalo, botones y tiempo (RF04, RF05, RF09)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bicentenario.controller.simulation_controller import PlaybackState


class ControlsPanel(ttk.LabelFrame):
    def __init__(self, parent, *, on_start, on_pause, on_resume, on_reset, on_seek):
        super().__init__(parent, text="Simulación", padding=8)
        self._on_seek = on_seek
        self._scenario_ids: list[str] = []
        self._shown_step = 0
        self._programmatic = False       # evita que set() del slider dispare on_seek

        self.scenario_var = tk.StringVar()
        self.duration_var = tk.StringVar(value="60")
        self.step_var = tk.StringVar(value="1")
        self.time_var = tk.StringVar(value="t = 0 min")

        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Escenario de lluvia:").grid(row=0, column=0, columnspan=2, sticky="w")
        self.scenario_box = ttk.Combobox(self, textvariable=self.scenario_var,
                                         state="readonly", width=36)
        self.scenario_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        ttk.Label(self, text="Duración (min):").grid(row=2, column=0, sticky="w")
        self.duration_entry = ttk.Entry(self, textvariable=self.duration_var, width=8)
        self.duration_entry.grid(row=2, column=1, sticky="e", pady=1)
        ttk.Label(self, text="Intervalo (min):").grid(row=3, column=0, sticky="w")
        self.step_entry = ttk.Entry(self, textvariable=self.step_var, width=8)
        self.step_entry.grid(row=3, column=1, sticky="e", pady=1)

        buttons = ttk.Frame(self)
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        self.start_btn = ttk.Button(buttons, text="Iniciar", command=on_start)
        self.pause_btn = ttk.Button(buttons, text="Pausar", command=on_pause)
        self.resume_btn = ttk.Button(buttons, text="Reanudar", command=on_resume)
        self.reset_btn = ttk.Button(buttons, text="Reiniciar", command=on_reset)
        for i, button in enumerate((self.start_btn, self.pause_btn, self.resume_btn, self.reset_btn)):
            buttons.columnconfigure(i, weight=1)
            button.grid(row=0, column=i, padx=2, sticky="ew")

        ttk.Label(self, textvariable=self.time_var).grid(row=5, column=0, columnspan=2, sticky="w")
        self.slider = ttk.Scale(self, from_=0, to=1, orient="horizontal", command=self._slider_moved)
        self.slider.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        ttk.Label(self, text="Arrastre la barra (con la simulación en pausa) para ver\n"
                             "instantes anteriores.", foreground="#555555").grid(
            row=7, column=0, columnspan=2, sticky="w")

        self.apply_state(False, PlaybackState.EMPTY)

    # ------------------------------------------------------------- lectura
    def set_scenarios(self, choices: list[tuple[str, str]]) -> None:
        """``choices``: lista de ``(id, texto)``."""
        self._scenario_ids = [cid for cid, _ in choices]
        self.scenario_box["values"] = [text for _, text in choices]
        self.scenario_var.set("")

    def get_scenario_id(self) -> str | None:
        index = self.scenario_box.current()
        return self._scenario_ids[index] if 0 <= index < len(self._scenario_ids) else None

    def get_params_text(self) -> tuple[str, str]:
        return self.duration_var.get(), self.step_var.get()

    # ----------------------------------------------------------- escritura
    def set_time(self, text: str) -> None:
        self.time_var.set(text)

    def set_range(self, last_step: int) -> None:
        self.slider.configure(to=max(last_step, 1))

    def set_position(self, step: int) -> None:
        self._shown_step = step
        self._programmatic = True
        try:
            self.slider.set(step)
        finally:
            self._programmatic = False

    def apply_state(self, data_loaded: bool, state: PlaybackState) -> None:
        """Habilita solo lo que tiene sentido en cada estado (evita acciones inválidas)."""
        idle = state in (PlaybackState.EMPTY, PlaybackState.READY, PlaybackState.FINISHED)
        self._enable(self.start_btn, data_loaded and idle)
        self._enable(self.pause_btn, state is PlaybackState.RUNNING)
        self._enable(self.resume_btn, state is PlaybackState.PAUSED)
        self._enable(self.reset_btn, state in (PlaybackState.RUNNING, PlaybackState.PAUSED,
                                               PlaybackState.FINISHED))
        self._enable(self.slider, state in (PlaybackState.READY, PlaybackState.PAUSED,
                                            PlaybackState.FINISHED))
        editable = data_loaded and idle
        for widget in (self.duration_entry, self.step_entry):
            self._enable(widget, editable)
        self.scenario_box.configure(state="readonly" if editable else "disabled")

    @staticmethod
    def _enable(widget, enabled: bool) -> None:
        widget.state(["!disabled"] if enabled else ["disabled"])

    # ------------------------------------------------------------- eventos
    def _slider_moved(self, value) -> None:
        if self._programmatic:
            return
        step = int(round(float(value)))
        if step != self._shown_step:
            self._shown_step = step
            self._on_seek(step)
