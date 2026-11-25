"""Registros "crudos" que produce el cargador y el informe de validación.
Los registros son inmutables (``frozen``) y solo contienen tipos básicos de
Python; no dependen de la interfaz gráfica ni de Excel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from bicentenario.errors import DataValidationError

SOURCES_SHEET = "Source(s)"
SINKS_SHEET = "Sink(s)"
PIPES_SHEET = "Pipe(s)"
BASIN_SHEET = "Drainage Basin"
SCENARIOS_SHEET = "Precipitation Scenarios"


def natural_key(text: str):
    """Clave de orden "natural": P2 < P10, y los números antes que las letras.

    >>> sorted(["P10", "P2", "P1"], key=natural_key)
    ['P1', 'P2', 'P10']
    """
    parts = re.split(r"(\d+)", str(text))
    return [(0, int(p), "") if p.isdigit() else (1, 0, p.casefold()) for p in parts if p != ""]


class Severity(str, Enum):
    ERROR = "ERROR"      # bloquea el uso de los datos
    WARNING = "AVISO"    # se puede continuar, pero hay que revisarlo
    INFO = "INFO"        # solo informativo


_SEVERITY_ORDER = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}


@dataclass(frozen=True)
class Issue:
    """Un problema encontrado, con su ubicación (hoja, fila, columna)."""

    severity: Severity
    message: str
    sheet: str | None = None
    row: int | None = None
    column: str | None = None

    @property
    def location(self) -> str:
        parts = []
        if self.sheet:
            parts.append(self.sheet)
        if self.row is not None:
            parts.append(f"fila {self.row}")
        if self.column:
            parts.append(f"columna '{self.column}'")
        return ", ".join(parts)

    def __str__(self) -> str:
        where = f" ({self.location})" if self.location else ""
        return f"[{self.severity.value}]{where} {self.message}"


@dataclass
class ValidationReport:
    """Lista de problemas encontrados al cargar y validar los datos."""

    issues: list[Issue] = field(default_factory=list)

    def add(self, severity: Severity, message: str, *, sheet=None, row=None, column=None) -> None:
        self.issues.append(Issue(severity, message, sheet, row, column))

    def error(self, message: str, **where) -> None:
        self.add(Severity.ERROR, message, **where)

    def warning(self, message: str, **where) -> None:
        self.add(Severity.WARNING, message, **where)

    def info(self, message: str, **where) -> None:
        self.add(Severity.INFO, message, **where)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    @property
    def infos(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.INFO]

    @property
    def has_errors(self) -> bool:
        return any(i.severity is Severity.ERROR for i in self.issues)

    def summary(self) -> str:
        return (f"{len(self.errors)} error(es), {len(self.warnings)} aviso(s), "
                f"{len(self.infos)} nota(s)")

    def format(self, min_severity: Severity = Severity.INFO) -> str:
        """Texto con un problema por línea (los más graves primero)."""
        minimum = _SEVERITY_ORDER[min_severity]
        chosen = [i for i in self.issues if _SEVERITY_ORDER[i.severity] >= minimum]
        chosen.sort(key=lambda i: -_SEVERITY_ORDER[i.severity])  # sort estable
        return "\n".join(str(i) for i in chosen)

    def raise_if_errors(self) -> None:
        """Lanza ``DataValidationError`` si hay al menos un error."""
        if self.has_errors:
            text = "\n".join(str(i) for i in self.errors)
            raise DataValidationError(
                f"Los datos tienen {len(self.errors)} error(es):\n{text}", report=self)


@dataclass(frozen=True)
class PipeRecord:
    """Una tubería (arista dirigida de ``from_node`` a ``to_node``)."""

    id: str                 # "P1", "P2", ...
    from_node: str          # ID del nodo inicial (siempre texto: "1", "C", ...)
    to_node: str            # ID del nodo final
    diameter_m: float       # diámetro en metros
    roughness_n: float      # coeficiente de rugosidad de Manning
    slope: float            # pendiente (m/m)
    qmax: float             # capacidad máxima de transporte (m³/s), dada por el docente
    length_m: float         # longitud en metros
    diameter_in: float | None = None   # diámetro en pulgadas (opcional, informativo)
    row: int | None = None  # fila de origen en el archivo (para mensajes de error)


@dataclass(frozen=True)
class BasinRecord:
    """Cuenca de drenaje: área y coeficiente de escorrentía.
    """

    runoff_coeff: float     # C (adimensional, entre 0 y 1)
    area_ha: float          # A en hectáreas
    node: str | None = None
    row: int | None = None


@dataclass(frozen=True)
class ScenarioRecord:
    """Escenario de precipitación."""

    id: str
    intensity_mm_h: float   # I en mm/h (0 = tiempo seco)
    condition: str = ""
    row: int | None = None


@dataclass
class RawDataset:
    """Todo lo leído del archivo del docente, ya convertido a tipos básicos."""

    sources: list[str]
    sinks: list[str]
    pipes: list[PipeRecord]
    basins: list[BasinRecord]
    scenarios: list[ScenarioRecord]
    origin: str = ""

    def node_ids(self) -> list[str]:
        """Todos los nodos: extremos de las tuberías + fuentes + sumideros.
        """
        found: set[str] = set(self.sources) | set(self.sinks)
        for pipe in self.pipes:
            found.add(pipe.from_node)
            found.add(pipe.to_node)
        return sorted(found, key=natural_key)

    def pipe_by_id(self) -> dict[str, PipeRecord]:
        return {p.id: p for p in self.pipes}

    def scenario_by_id(self) -> dict[str, ScenarioRecord]:
        return {s.id: s for s in self.scenarios}
