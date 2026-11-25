"""Controlador principal: une la carga de datos con la interfaz.
"""

from __future__ import annotations

from pathlib import Path

from bicentenario.errors import InvalidStateError
from bicentenario.io.loader import load_and_validate
from bicentenario.io.records import PipeRecord, RawDataset, ValidationReport
from bicentenario.io.validators import SimulationParams, validate_pipe_query
from bicentenario.view.graph_layout import layered_layout


class AppController:
    def __init__(self):
        self.dataset: RawDataset | None = None
        self.report: ValidationReport | None = None
        self.layout: dict[str, tuple[float, float]] = {}
        self.paths: dict[tuple[str, str], list[tuple[float, float]]] = {}   # puntos de tuberías largas
        self._pipes_by_id: dict[str, PipeRecord] = {}

    @property
    def loaded(self) -> bool:
        return self.dataset is not None

    def load(self, path: str | Path) -> ValidationReport:
        """Carga y valida el archivo (o carpeta de CSV).
        Si el informe trae errores, los datos cargados antes se descartan para
        no simular con datos a medias (``loaded`` pasa a ser False).
        """
        self.dataset, self.report, self.layout, self.paths, self._pipes_by_id = None, None, {}, {}, {}
        dataset, report = load_and_validate(path)
        self.report = report
        if report.has_errors:
            return report
        self.dataset = dataset
        self._pipes_by_id = dataset.pipe_by_id()
        self.layout, self.paths = layered_layout(
            dataset.node_ids(), [(p.from_node, p.to_node) for p in dataset.pipes])
        return report

    def _require_loaded(self) -> RawDataset:
        if self.dataset is None:
            raise InvalidStateError("Primero cargue los datos (botón «Abrir Excel…»).")
        return self.dataset

    def pipe(self, pipe_id: str) -> PipeRecord | None:
        return self._pipes_by_id.get(pipe_id)

    def find_pipe(self, text: str) -> str:
        """ID canónico de la tubería escrita en el buscador . Lanza si no existe."""
        self._require_loaded()
        return validate_pipe_query(text, self._pipes_by_id)

    def scenario_choices(self) -> list[tuple[str, str]]:
        """Pares ``(id, texto)`` para el selector de escenarios (RF04)."""
        dataset = self._require_loaded()
        return [(s.id, f"{s.id} — {s.condition or 'Escenario'} ({s.intensity_mm_h:g} mm/h)")
                for s in dataset.scenarios]

    def run_simulation(self, scenario_id: str, params: SimulationParams):
        """Ejecuta la simulación y devuelve su historial.
        """
        self._require_loaded()
        raise InvalidStateError(
            "La simulación todavía no está conectada: falta integrar el simulador. "
            "Mientras tanto solo se puede ver y consultar la red.")
