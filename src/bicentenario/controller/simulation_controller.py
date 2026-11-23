"""Control de reproducción de la simulación (RF09): iniciar, pausar, reanudar
y consultar instantes anteriores.

Contrato mínimo con el historial (lo que debe ofrecer el de la Persona B):

Estados:  EMPTY → READY → RUNNING ⇄ PAUSED → FINISHED

El controlador no importa Tkinter: recibe el ``scheduler``, así que se prueba
con uno falso (ver tests/test_playback_controller.py).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable

from bicentenario.errors import InputValidationError, InvalidStateError


class PlaybackState(str, Enum):
    EMPTY = "empty"          # no hay historial cargado
    READY = "ready"          # historial cargado, en el paso 0
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"    # llegó al último paso


class PlaybackController:
    def __init__(self, scheduler, on_frame: Callable[[int, Any], None],
                 on_state: Callable[[PlaybackState], None] | None = None,
                 interval_ms: int = 300):
        """``scheduler`` debe tener ``after(ms, callback) -> id`` y ``after_cancel(id)``."""
        self._scheduler = scheduler
        self._on_frame = on_frame
        self._on_state = on_state
        self._interval_ms = self._check_interval(interval_ms)
        self._history = None
        self._step = 0
        self._job = None
        self._state = PlaybackState.EMPTY

    # ------------------------------------------------------------ consultas
    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def step(self) -> int:
        return self._step

    @property
    def last_step(self) -> int:
        return len(self._history) - 1 if self._history is not None else 0

    # -------------------------------------------------------------- acciones
    def load(self, history) -> None:
        """Carga un historial nuevo y muestra el instante 0."""
        if len(history) == 0:
            raise InputValidationError("El historial de la simulación está vacío.")
        self._cancel_timer()
        self._history = history
        self._step = 0
        self._set_state(PlaybackState.READY)
        self._emit()

    def start(self) -> None:
        """Inicia la reproducción (o la repite desde el principio si ya terminó)."""
        self._require(PlaybackState.READY, PlaybackState.FINISHED, action="iniciar")
        if self._state is PlaybackState.FINISHED:
            self._step = 0
            self._emit()
        self._run()

    def pause(self) -> None:
        self._require(PlaybackState.RUNNING, action="pausar")
        self._cancel_timer()
        self._set_state(PlaybackState.PAUSED)

    def resume(self) -> None:
        self._require(PlaybackState.PAUSED, action="reanudar")
        self._run()

    def reset(self) -> None:
        """Detiene todo y vuelve al instante 0."""
        self._require(PlaybackState.READY, PlaybackState.RUNNING, PlaybackState.PAUSED,
                      PlaybackState.FINISHED, action="reiniciar")
        self._cancel_timer()
        self._step = 0
        self._set_state(PlaybackState.READY)
        self._emit()

    def seek(self, step: int) -> None:
        """Salta a un instante (0 .. último). Solo con la simulación detenida."""
        self._require(PlaybackState.READY, PlaybackState.PAUSED, PlaybackState.FINISHED,
                      action="consultar un instante", hint="Pause la simulación primero.")
        if isinstance(step, bool) or not isinstance(step, int):
            raise InputValidationError(f"El instante debe ser un número entero (recibido {step!r}).")
        if not 0 <= step <= self.last_step:
            raise InputValidationError(
                f"El instante debe estar entre 0 y {self.last_step} (recibido {step}).")
        self._step = step
        if step == self.last_step:
            new_state = PlaybackState.FINISHED
        elif self._state is PlaybackState.FINISHED:
            new_state = PlaybackState.PAUSED
        else:
            new_state = self._state
        self._set_state(new_state)
        self._emit()

    def clear(self) -> None:
        """Descarta el historial (p. ej. al cargar otro archivo de datos)."""
        self._cancel_timer()
        self._history = None
        self._step = 0
        self._set_state(PlaybackState.EMPTY)

    def set_interval(self, interval_ms: int) -> None:
        """Cambia la velocidad de reproducción (milisegundos entre pasos)."""
        self._interval_ms = self._check_interval(interval_ms)

    def dispose(self) -> None:
        """Cancela el temporizador pendiente (llamar al cerrar la ventana)."""
        self._cancel_timer()

    # --------------------------------------------------------------- internos
    def _run(self) -> None:
        self._set_state(PlaybackState.RUNNING)
        if self._step >= self.last_step:
            self._set_state(PlaybackState.FINISHED)
            return
        self._job = self._scheduler.after(self._interval_ms, self._tick)

    def _tick(self) -> None:
        self._job = None
        if self._state is not PlaybackState.RUNNING:
            return
        self._step += 1
        self._emit()
        if self._step >= self.last_step:
            self._set_state(PlaybackState.FINISHED)
        else:
            self._job = self._scheduler.after(self._interval_ms, self._tick)

    def _emit(self) -> None:
        self._on_frame(self._step, self._history.get_at(self._step))

    def _set_state(self, state: PlaybackState) -> None:
        changed = state is not self._state
        self._state = state
        if changed and self._on_state is not None:
            self._on_state(state)

    def _cancel_timer(self) -> None:
        if self._job is not None:
            self._scheduler.after_cancel(self._job)
            self._job = None

    def _require(self, *allowed: PlaybackState, action: str, hint: str = "") -> None:
        if self._state not in allowed:
            if self._state is PlaybackState.EMPTY:
                raise InvalidStateError(f"No se puede {action}: primero ejecute una simulación.")
            raise InvalidStateError(
                f"No se puede {action} con la simulación en estado '{self._state.value}'. {hint}".strip())

    @staticmethod
    def _check_interval(interval_ms: int) -> int:
        if isinstance(interval_ms, bool) or not isinstance(interval_ms, (int, float)) or interval_ms <= 0:
            raise InputValidationError("La velocidad de reproducción debe ser mayor que 0.")
        return int(interval_ms)
