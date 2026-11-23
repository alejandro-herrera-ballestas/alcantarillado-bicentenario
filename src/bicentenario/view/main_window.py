"""Ventana principal .
La ventana no contiene logica de simulación: pide datos a ``AppController`` y
reproduce el historial con ``PlaybackController``. Todo lo que puede fallar por
una acción del usuario pasa por ``_safe``, que muestra el mensaje en un cuadro
de diálogo en vez de cerrar la aplicación con un traceback.
"""

from __future__ import annotations

import sys
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from bicentenario.controller.app_controller import AppController
from bicentenario.controller.simulation_controller import PlaybackController, PlaybackState
from bicentenario.errors import BicentenarioError, InputValidationError, InvalidStateError
from bicentenario.io.records import Severity
from bicentenario.io.validators import validate_simulation_params
from bicentenario.view.color_scale import classify, utilization_color
from bicentenario.view.graph_canvas import GraphCanvas
from bicentenario.view.panels.controls import ControlsPanel
from bicentenario.view.panels.critical_table import CriticalTable
from bicentenario.view.panels.legend import LegendPanel
from bicentenario.view.panels.pipe_info import PipeInfoPanel
from bicentenario.view.panels.summary import SummaryPanel

DEMO_MODE = True
DEMO_NOTICE = "DEMOSTRACIÓN: los porcentajes son inventados para probar la interfaz, NO son resultados reales."
PLAYBACK_INTERVAL_MS = 250


class MainWindow:
    def __init__(self, root: tk.Tk, default_data: str | Path | None = None):
        self.root = root
        root.title("Red de alcantarillado – Ciudad Bicentenario" + ("  [DEMO]" if DEMO_MODE else ""))
        root.geometry("1280x800")
        root.minsize(1000, 680)
        root.report_callback_exception = self._on_unexpected_error

        self.app = AppController()
        self.playback = PlaybackController(root, self._on_frame, self._on_state,
                                           interval_ms=PLAYBACK_INTERVAL_MS)
        self._history = None
        self._frame: dict[str, float] | None = None
        self._step_min = 1.0
        self._scenario_label = ""

        self._build()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._on_state(PlaybackState.EMPTY)
        if default_data is not None and Path(default_data).exists():
            root.after(100, lambda: self._load(default_data))     # tras mostrarse la ventana
        else:
            self._status("Abra el archivo de datos del docente para comenzar.")

    # ============================================================== construcción
    def _build(self) -> None:
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        # --- barra superior: abrir datos y buscar tubería
        top = ttk.Frame(root, padding=(8, 6))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Button(top, text="Abrir Excel…", command=lambda: self._safe(self._open_excel)).pack(side="left")
        ttk.Button(top, text="Abrir carpeta CSV…", command=lambda: self._safe(self._open_csv_folder)).pack(
            side="left", padx=(6, 0))
        self.report_btn = ttk.Button(top, text="Ver avisos de los datos",
                                     command=lambda: self._safe(self._show_report_dialog))
        self.report_btn.pack(side="left", padx=(6, 0))
        self.search_var = tk.StringVar()
        ttk.Button(top, text="Buscar", command=lambda: self._safe(self._search_pipe)).pack(side="right")
        search_entry = ttk.Entry(top, textvariable=self.search_var, width=10)
        search_entry.pack(side="right", padx=4)
        search_entry.bind("<Return>", lambda _e: self._safe(self._search_pipe))
        ttk.Label(top, text="Buscar tubería (ej. P12):").pack(side="right")

        # --- zona central: grafo a la izquierda, paneles a la derecha
        middle = ttk.Frame(root)
        middle.grid(row=1, column=0, sticky="nsew")
        middle.columnconfigure(0, weight=1)
        middle.rowconfigure(0, weight=1)

        self.tk_canvas = tk.Canvas(middle, bg="white", highlightthickness=1, highlightbackground="#bbbbbb")
        self.tk_canvas.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=4)
        self.graph = GraphCanvas(self.tk_canvas, on_pipe_selected=self._pipe_clicked)

        side = ttk.Frame(middle)
        side.grid(row=0, column=1, sticky="ns", padx=(4, 8), pady=4)
        self.controls = ControlsPanel(
            side,
            on_start=lambda: self._safe(self._start),
            on_pause=lambda: self._safe(self.playback.pause),
            on_resume=lambda: self._safe(self.playback.resume),
            on_reset=lambda: self._safe(self.playback.reset),
            on_seek=lambda step: self._safe(self.playback.seek, step))
        self.controls.pack(fill="x")
        LegendPanel(side).pack(fill="x", pady=6)
        self.pipe_info = PipeInfoPanel(side)
        self.pipe_info.pack(fill="x")

        # --- parte inferior: críticas y resumen
        bottom = ttk.Frame(root)
        bottom.grid(row=2, column=0, sticky="ew", padx=8)
        bottom.columnconfigure(0, weight=1)
        self.critical = CriticalTable(bottom, on_select=self._critical_chosen)
        self.critical.grid(row=0, column=0, sticky="ew")
        self.summary = SummaryPanel(bottom)
        self.summary.grid(row=0, column=1, sticky="ns", padx=(6, 0))

        # --- barra de estado
        self.status_var = tk.StringVar()
        ttk.Label(root, textvariable=self.status_var, anchor="w", relief="sunken",
                  padding=(6, 2)).grid(row=3, column=0, sticky="ew", pady=(6, 0))

    # =================================================================== datos
    def _open_excel(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root, title="Abrir DataSetBicentenario.xlsx",
            filetypes=[("Libro de Excel", "*.xlsx *.xlsm"), ("Todos los archivos", "*.*")])
        if path:
            self._load(path)

    def _open_csv_folder(self) -> None:
        path = filedialog.askdirectory(parent=self.root, title="Carpeta con los CSV")
        if path:
            self._load(path)

    def _load(self, path) -> None:
        self.playback.clear()
        self._history, self._frame = None, None
        self.graph.select_pipe(None)
        self.pipe_info.clear()
        self.critical.set_rows([])
        try:
            report = self.app.load(path)
        except BicentenarioError as exc:
            messagebox.showerror("No se pudo cargar el archivo", str(exc), parent=self.root)
            self.graph.set_network({}, [], [], [])
            self._status("No se cargaron datos.")
            self._on_state(PlaybackState.EMPTY)
            return

        if not self.app.loaded:
            self.graph.set_network({}, [], [], [])
            self._on_state(PlaybackState.EMPTY)
            self._status(f"Datos con errores: {report.summary()}")
            self._show_report_dialog()
            return

        dataset = self.app.dataset
        self.graph.set_network(self.app.layout, dataset.pipes, dataset.sources, dataset.sinks,
                               paths=self.app.paths)
        self.controls.set_scenarios(self.app.scenario_choices())
        self.summary.set_text("Seleccione un escenario y pulse «Iniciar».")
        self._on_state(PlaybackState.EMPTY)
        warn = f" · {len(report.warnings)} aviso(s): pulse «Ver avisos de los datos»" if report.warnings else ""
        self._status(f"Datos cargados: {len(dataset.pipes)} tuberías, {len(dataset.node_ids())} nodos, "
                     f"{len(dataset.sources)} fuentes, {len(dataset.sinks)} sumidero(s){warn}")

    def _show_report_dialog(self) -> None:
        report = self.app.report
        if report is None:
            raise InvalidStateError("Todavía no se ha cargado ningún archivo.")
        text = report.format(Severity.INFO) or "Sin observaciones."
        lines = text.splitlines()
        if len(lines) > 25:
            text = "\n".join(lines[:25]) + f"\n… y {len(lines) - 25} más."
        show = messagebox.showerror if report.has_errors else messagebox.showinfo
        show("Revisión de los datos", f"{report.summary()}\n\n{text}", parent=self.root)

    # ============================================================== simulación
    def _start(self) -> None:
        if not self.app.loaded:
            raise InvalidStateError("Primero cargue los datos (botón «Abrir Excel…»).")
        scenario_id = self.controls.get_scenario_id()
        if scenario_id is None:
            raise InputValidationError("Seleccione un escenario de lluvia.")
        params = validate_simulation_params(*self.controls.get_params_text())

        # ⚠ AQUÍ se conectará la simulación real .
        history = self.app.run_simulation(scenario_id, params)

        self._history = history
        self._step_min = params.step_min
        self._scenario_label = self.controls.scenario_var.get()
        self.playback.load(history)
        self.controls.set_range(self.playback.last_step)
        self.playback.start()

    def _on_frame(self, step: int, frame) -> None:
        """Se llama en cada instante mostrado (avance, salto o reinicio)."""
        self._frame = frame
        self.graph.set_colors({pid: utilization_color(pct) for pid, pct in frame.items()})
        last = self.playback.last_step
        self.controls.set_time(f"t = {step * self._step_min:g} min   (paso {step} de {last})")
        self.controls.set_position(step)
        self._refresh_pipe_info()
        self._refresh_summary(step, frame)
        if self._history is not None and hasattr(self._history, "critical_rows"):
            self.critical.set_rows(self._history.critical_rows(step))

    def _on_state(self, state: PlaybackState) -> None:
        self.controls.apply_state(self.app.loaded, state)
        messages = {
            PlaybackState.RUNNING: "Simulación en curso…",
            PlaybackState.PAUSED: "Simulación en pausa. Puede consultar instantes anteriores.",
            PlaybackState.FINISHED: "Simulación terminada. Puede revisar cualquier instante.",
        }
        if state in messages:
            self._status(messages[state] + (f"  [{DEMO_NOTICE}]" if DEMO_MODE else ""))

    def _refresh_summary(self, step: int, frame: dict[str, float]) -> None:
        over = sum(1 for pct in frame.values() if classify(pct).key == "exceeded")
        worst_id, worst_pct = max(frame.items(), key=lambda item: (item[1], item[0]))
        lines = [
            f"Escenario: {self._scenario_label}",
            f"Instante: t = {step * self._step_min:g} min (paso {step} de {self.playback.last_step})",
            f"Tuberías sobre su capacidad (>100 %): {over} de {len(frame)}",
            f"Mayor utilización ahora: {worst_id} ({worst_pct:.1f} %)",
        ]
        if DEMO_MODE:
            lines += ["", DEMO_NOTICE]
        self.summary.set_text("\n".join(lines))

    # ================================================================= tubería
    def _pipe_clicked(self, pipe_id: str | None) -> None:
        self._refresh_pipe_info()

    def _critical_chosen(self, pipe_id: str) -> None:
        self.graph.select_pipe(pipe_id)
        self._refresh_pipe_info()

    def _search_pipe(self) -> None:
        pipe_id = self.app.find_pipe(self.search_var.get())       # lanza si está vacío o no existe
        self.graph.select_pipe(pipe_id)
        self._refresh_pipe_info()

    def _refresh_pipe_info(self) -> None:
        pipe_id = self.graph.selected
        pipe = self.app.pipe(pipe_id) if pipe_id else None
        if pipe is None:
            self.pipe_info.clear()
            return
        time_text, pct = None, None
        if self._frame is not None:
            pct = self._frame.get(pipe.id)
            time_text = f"t = {self.playback.step * self._step_min:g} min"
        self.pipe_info.show(pipe, time_text=time_text, pct=pct)

    # ================================================================= soporte
    def _status(self, text: str) -> None:
        self.status_var.set(text)

    def _safe(self, func, *args) -> None:
        """Ejecuta una acción del usuario; los errores controlados salen en un dialogo."""
        try:
            func(*args)
        except BicentenarioError as exc:
            messagebox.showwarning("No se pudo completar la acción", str(exc), parent=self.root)

    def _on_unexpected_error(self, exc_type, exc, tb) -> None:
        traceback.print_exception(exc_type, exc, tb, file=sys.stderr)
        messagebox.showerror(
            "Error inesperado",
            f"{exc_type.__name__}: {exc}\n\nLa aplicación sigue abierta. "
            "Los detalles están en la consola.", parent=self.root)

    def _on_close(self) -> None:
        self.playback.dispose()
        self.root.destroy()
