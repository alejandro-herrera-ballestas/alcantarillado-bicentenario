"""Cargador de datos: lee ``DataSetBicentenario.xlsx`` (o una carpeta de CSV).

1. Lee las 5 hojas (Source(s), Sink(s), Pipe(s), Drainage Basin,
   Precipitation Scenarios) y las convierte en ``RawDataset``.
2. Localiza las columnas por su nombre de encabezado y
   tolera variantes.
3. Normaliza los IDs de nodo a texto (en el archivo conviven ``1`` y ``'C'``).
4. Ignora las filas de totales y notas que hay debajo de la tabla de tuberías.
5. Reporta cada celda problemática con hoja, fila y columna.

"""

from __future__ import annotations

import csv
import math
import re
from collections import namedtuple
from pathlib import Path
from typing import Any

from bicentenario.errors import DataLoadError
from bicentenario.io.records import (
    BASIN_SHEET, PIPES_SHEET, SCENARIOS_SHEET, SINKS_SHEET, SOURCES_SHEET,
    BasinRecord, PipeRecord, RawDataset, ScenarioRecord, ValidationReport,
    natural_key,
)

Sheet = namedtuple("Sheet", ["title", "rows"])

# --------------------------------------------------------------------------
# Nombres aceptados (ya "normalizados" con _key) para hojas y columnas
# --------------------------------------------------------------------------
_SHEET_ALIASES = {
    "sources": {"sources", "source", "fuentes", "fuente"},
    "sinks": {"sinks", "sink", "sumideros", "sumidero"},
    "pipes": {"pipes", "pipe", "tuberias", "tuberia"},
    "basin": {"drainagebasin", "basin", "basins", "cuenca", "cuencas", "cuencadedrenaje"},
    "scenarios": {"precipitationscenarios", "scenarios", "escenarios",
                  "escenariosdeprecipitacion"},
}
_SHEET_LABELS = {
    "sources": SOURCES_SHEET, "sinks": SINKS_SHEET, "pipes": PIPES_SHEET,
    "basin": BASIN_SHEET, "scenarios": SCENARIOS_SHEET,
}
CSV_FILE_NAMES = {key: f"{key}.csv" for key in _SHEET_ALIASES}

_NODE_HEADERS = {"nodes", "node", "nodos", "nodo", "id"}

_PIPE_COLUMNS = {
    "id": {"pipe", "id", "pipeid", "tuberia", "idtuberia"},
    "from_node": {"fromi", "from", "desde", "inicio", "origen", "nodoinicial"},
    "to_node": {"toi", "to", "hasta", "fin", "destino", "nodofinal"},
    "diameter_in": {"⌀in", "øin", "diameterin", "diametroin", "diametropulgadas"},
    "diameter_m": {"⌀m", "øm", "diameterm", "diametrom", "diametro"},
    "roughness": {"n", "manning", "rugosidad"},
    "slope": {"s", "slope", "pendiente"},
    "qmax": {"q", "qmax", "capacidad", "capacidadmaxima"},
    "length": {"lenghtm", "lengthm", "longitudm", "length", "longitud", "lenght"},
}
_PIPE_REQUIRED = ("id", "from_node", "to_node", "diameter_m", "roughness",
                  "slope", "qmax", "length")

_BASIN_COLUMNS = {
    "c": {"c", "runoffcoefficient", "coeficientedeescorrentia", "coeficiente",
          "escorrentia"},
    "a": {"a", "area", "areaha", "areadedrenaje", "areadedrenajeha", "ha"},
    "node": {"node", "nodes", "nodo", "nodos"},
}
_BASIN_REQUIRED = ("c", "a")

_SCENARIO_COLUMNS = {
    "id": {"scenario", "escenario", "id"},
    "intensity": {"intensity", "intensidad", "i"},
    "condition": {"condition", "condicion", "descripcion", "description", "estado"},
}
_SCENARIO_REQUIRED = ("id", "intensity")

_EXCEL_HINT = " (¿es una fórmula sin valor calculado? Abra y guarde el archivo en Excel)"


# --------------------------------------------------------------------------
# Utilidades de conversión
# --------------------------------------------------------------------------
def _key(value: Any) -> str:
    """Normaliza un texto para compararlo: minúsculas y solo letras/números."""
    return re.sub(r"[^0-9a-záéíóúüñø⌀]+", "", str(value).casefold())


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def normalize_id(value: Any) -> str | None:
    """Convierte un ID de la celda a texto limpio; ``None`` si está vacío.

    >>> normalize_id(1), normalize_id(14.0), normalize_id(" C ")
    ('1', '14', 'C')
    """
    if _is_empty(value):
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return re.sub(r"\s+", " ", str(value).strip())


def parse_number(value: Any) -> float:
    """Convierte una celda en número (acepta coma decimal y separador de miles).

    Lanza ``ValueError`` si no es un número finito.

    >>> parse_number("0,05"), parse_number("1.234,5"), parse_number(" 7 ")
    (0.05, 1234.5, 7.0)
    """
    if isinstance(value, bool):
        raise ValueError("no es un número")
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip().replace(" ", "").replace(" ", "")
        if not text:
            raise ValueError("celda vacía")
        if "," in text and "." in text:
            # el separador que aparece más a la derecha es el decimal
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            number = float(text)
        except ValueError:
            raise ValueError("no es un número") from None
    else:
        raise ValueError("no es un número")
    if not math.isfinite(number):
        raise ValueError("no es un número finito")
    return number


_INTENSITY_RE = re.compile(r"^\s*([-+]?\d+(?:[.,]\d+)?)\s*(.*?)\s*$")
_MM_PER_HOUR = {"mm/h", "mm/hr", "mmh", "mmh-1", "mm/hora", "mmperhour", "mm/h."}


def parse_intensity(value: Any) -> float:
    """Intensidad de lluvia en mm/h. Acepta ``10``, ``"10"`` o ``"10 mm/h"``.

    Lanza ``ValueError`` si la unidad no es mm/h (p. ej. ``mm/min``).
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return parse_number(value)
    if not isinstance(value, str):
        raise ValueError("no es una intensidad válida")
    match = _INTENSITY_RE.match(value)
    if not match:
        raise ValueError("no es una intensidad válida (ej. '10 mm/h')")
    number = parse_number(match.group(1))
    unit = match.group(2).replace(" ", "").casefold()
    if unit and unit not in _MM_PER_HOUR:
        raise ValueError(f"unidad no soportada '{match.group(2)}' (se espera mm/h)")
    return number


def _fmt_rows(rows: list[int]) -> str:
    """[61, 62, 63, 65] -> '61–63, 65'."""
    if not rows:
        return ""
    rows = sorted(rows)
    groups, start, prev = [], rows[0], rows[0]
    for r in rows[1:]:
        if r != prev + 1:
            groups.append((start, prev))
            start = r
        prev = r
    groups.append((start, prev))
    return ", ".join(str(a) if a == b else f"{a}–{b}" for a, b in groups)


# --------------------------------------------------------------------------
# Lectura de archivos -> filas crudas
# --------------------------------------------------------------------------
def read_sheets(path: str | Path) -> dict[str, Sheet]:
    """Lee el archivo (.xlsx) o la carpeta de CSV y devuelve las 5 hojas.
    """
    source = Path(path)
    if not source.exists():
        raise DataLoadError(f"No existe el archivo o la carpeta: {source}", path=source)
    if source.is_dir():
        sheets = _read_csv_folder(source)
    elif source.suffix.lower() in (".xlsx", ".xlsm"):
        sheets = _read_workbook(source)
    else:
        raise DataLoadError(
            f"Formato no soportado '{source.suffix}'. Use un archivo .xlsx o una "
            f"carpeta con los CSV ({', '.join(CSV_FILE_NAMES.values())}).", path=source)

    missing = [_SHEET_LABELS[k] for k in _SHEET_ALIASES if k not in sheets]
    if missing:
        raise DataLoadError(
            "Faltan hojas/archivos obligatorios: " + ", ".join(missing), path=source)
    return sheets


def _read_workbook(path: Path) -> dict[str, Sheet]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise DataLoadError("Falta la librería openpyxl (pip install openpyxl)",
                            path=path) from exc
    try:
        workbook = load_workbook(path, data_only=True)
    except Exception as exc:  # archivo dañado, no es xlsx, bloqueado...
        raise DataLoadError(f"No se pudo abrir el archivo Excel: {exc}", path=path) from exc
    try:
        found: dict[str, Sheet] = {}
        for ws in workbook.worksheets:
            title_key = _key(ws.title)
            for logical, aliases in _SHEET_ALIASES.items():
                if title_key in aliases and logical not in found:
                    found[logical] = Sheet(ws.title, [list(r) for r in ws.iter_rows(values_only=True)])
        return found
    finally:
        workbook.close()


def _read_csv_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise DataLoadError(f"No se pudo leer '{path.name}': codificación desconocida", path=path)


def _read_csv_folder(folder: Path) -> dict[str, Sheet]:
    found: dict[str, Sheet] = {}
    for file in sorted(folder.glob("*.csv")):
        stem_key = _key(file.stem)
        for logical, aliases in _SHEET_ALIASES.items():
            if stem_key in aliases and logical not in found:
                text = _read_csv_text(file)
                first_line = text.splitlines()[0] if text.strip() else ""
                delimiter = max(",;\t", key=first_line.count) if first_line else ","
                reader = csv.reader(text.splitlines(), delimiter=delimiter)
                rows = [[(c.strip() or None) for c in row] for row in reader]
                found[logical] = Sheet(file.name, rows)
    return found


# --------------------------------------------------------------------------
# Interpretación de cada hoja
# --------------------------------------------------------------------------
def _find_header(sheet: Sheet, columns: dict[str, set], required: tuple[str, ...]):
    """Busca la fila de encabezados. Devuelve (índice_fila, {nombre: columna}, textos)."""
    best: tuple[int, dict, dict] | None = None
    for r, row in enumerate(sheet.rows[:15]):
        mapping: dict[str, int] = {}
        texts: dict[str, str] = {}
        for c, cell in enumerate(row):
            if _is_empty(cell):
                continue
            cell_key = _key(cell)
            for name, aliases in columns.items():
                if cell_key in aliases and name not in mapping:
                    mapping[name] = c
                    texts[name] = str(cell).strip()
        if all(name in mapping for name in required):
            return r, mapping, texts
        if best is None or len(mapping) > len(best[1]):
            best = (r, mapping, texts)

    seen = [str(c).strip() for c in (sheet.rows[0] if sheet.rows else []) if not _is_empty(c)]
    missing = [n for n in required if best is None or n not in best[1]]
    raise DataLoadError(
        f"En '{sheet.title}' no se encontraron las columnas obligatorias: "
        f"{', '.join(missing)}. Encabezados leídos en la primera fila: "
        f"{seen if seen else 'ninguno'}", sheet=sheet.title)


def _cell(row: list, mapping: dict[str, int], name: str) -> Any:
    index = mapping.get(name)
    return row[index] if index is not None and index < len(row) else None


def _parse_node_list(sheet: Sheet, report: ValidationReport) -> list[str]:
    first = next((i for i, r in enumerate(sheet.rows) if any(not _is_empty(c) for c in r)), None)
    if first is None:
        report.error("La hoja está vacía", sheet=sheet.title)
        return []
    head = sheet.rows[first][0] if sheet.rows[first] else None
    if not _is_empty(head) and _key(head) in _NODE_HEADERS:
        start = first + 1
    else:
        start = first
        report.warning("No se encontró el encabezado 'Node(s)'; se leyó la primera fila "
                       "como dato", sheet=sheet.title, row=first + 1)
    nodes = []
    for r in range(start, len(sheet.rows)):
        row = sheet.rows[r]
        node = normalize_id(row[0] if row else None)
        if node is not None:
            nodes.append(node)
    return nodes


def _parse_pipes(sheet: Sheet, report: ValidationReport, from_excel: bool) -> list[PipeRecord]:
    header_row, cols, labels = _find_header(sheet, _PIPE_COLUMNS, _PIPE_REQUIRED)
    hint = _EXCEL_HINT if from_excel else ""
    pipes: list[PipeRecord] = []
    ignored: list[int] = []

    for r in range(header_row + 1, len(sheet.rows)):
        row, excel_row = sheet.rows[r], r + 1
        pipe_id = normalize_id(_cell(row, cols, "id"))

        if pipe_id is None:
            # Sin ID: normalmente totales o notas al pie ("Source: https://...").
            if any(not _is_empty(c) for c in row):
                filled = sum(not _is_empty(_cell(row, cols, k))
                             for k in ("diameter_m", "roughness", "slope", "qmax"))
                if filled >= 3:
                    report.error("La fila tiene datos de tubería pero no tiene ID",
                                 sheet=sheet.title, row=excel_row, column=labels["id"])
                else:
                    ignored.append(excel_row)
            continue

        ok = True
        values: dict[str, float] = {}
        for name in ("diameter_m", "roughness", "slope", "qmax", "length"):
            raw = _cell(row, cols, name)
            if _is_empty(raw):
                report.error(f"Tubería {pipe_id}: celda vacía{hint}",
                             sheet=sheet.title, row=excel_row, column=labels[name])
                ok = False
                continue
            try:
                values[name] = parse_number(raw)
            except ValueError as exc:
                report.error(f"Tubería {pipe_id}: '{raw}' {exc}",
                             sheet=sheet.title, row=excel_row, column=labels[name])
                ok = False

        nodes = {}
        for name in ("from_node", "to_node"):
            nodes[name] = normalize_id(_cell(row, cols, name))
            if nodes[name] is None:
                report.error(f"Tubería {pipe_id}: falta el nodo",
                             sheet=sheet.title, row=excel_row, column=labels[name])
                ok = False

        diameter_in = None
        if "diameter_in" in cols and not _is_empty(_cell(row, cols, "diameter_in")):
            try:
                diameter_in = round(parse_number(_cell(row, cols, "diameter_in")), 9)
            except ValueError as exc:
                report.warning(f"Tubería {pipe_id}: diámetro en pulgadas ilegible ({exc})",
                               sheet=sheet.title, row=excel_row, column=labels["diameter_in"])

        if ok:
            pipes.append(PipeRecord(
                id=pipe_id, from_node=nodes["from_node"], to_node=nodes["to_node"],
                diameter_m=values["diameter_m"], roughness_n=values["roughness"],
                slope=values["slope"], qmax=values["qmax"], length_m=values["length"],
                diameter_in=diameter_in, row=excel_row))

    if ignored:
        report.info(f"Se ignoraron {len(ignored)} fila(s) sin ID de tubería "
                    f"(filas {_fmt_rows(ignored)}): suelen ser totales o notas al pie",
                    sheet=sheet.title)
    pipes.sort(key=lambda p: natural_key(p.id))
    return pipes


def _parse_basins(sheet: Sheet, report: ValidationReport) -> list[BasinRecord]:
    header_row, cols, labels = _find_header(sheet, _BASIN_COLUMNS, _BASIN_REQUIRED)
    basins: list[BasinRecord] = []
    for r in range(header_row + 1, len(sheet.rows)):
        row, excel_row = sheet.rows[r], r + 1
        if all(_is_empty(c) for c in row):
            continue
        values, ok = {}, True
        for name in ("c", "a"):
            raw = _cell(row, cols, name)
            try:
                values[name] = parse_number(raw)
            except ValueError as exc:
                shown = "" if _is_empty(raw) else f"'{raw}' "
                report.error(f"Cuenca: {shown}{exc}", sheet=sheet.title,
                             row=excel_row, column=labels[name])
                ok = False
        if ok:
            basins.append(BasinRecord(runoff_coeff=values["c"], area_ha=values["a"],
                                      node=normalize_id(_cell(row, cols, "node")),
                                      row=excel_row))
    return basins


def _parse_scenarios(sheet: Sheet, report: ValidationReport) -> list[ScenarioRecord]:
    header_row, cols, labels = _find_header(sheet, _SCENARIO_COLUMNS, _SCENARIO_REQUIRED)
    scenarios: list[ScenarioRecord] = []
    for r in range(header_row + 1, len(sheet.rows)):
        row, excel_row = sheet.rows[r], r + 1
        if all(_is_empty(c) for c in row):
            continue
        scenario_id = normalize_id(_cell(row, cols, "id"))
        if scenario_id is None:
            report.error("Escenario sin identificador", sheet=sheet.title,
                         row=excel_row, column=labels["id"])
            continue
        raw = _cell(row, cols, "intensity")
        try:
            intensity = parse_intensity(raw)
        except ValueError as exc:
            shown = "celda vacía" if _is_empty(raw) else f"'{raw}' {exc}"
            report.error(f"Escenario {scenario_id}: {shown}", sheet=sheet.title,
                         row=excel_row, column=labels["intensity"])
            continue
        condition = _cell(row, cols, "condition")
        scenarios.append(ScenarioRecord(
            id=scenario_id, intensity_mm_h=intensity,
            condition="" if _is_empty(condition) else str(condition).strip(), row=excel_row))
    scenarios.sort(key=lambda s: natural_key(s.id))
    return scenarios


# --------------------------------------------------------------------------
# API pública
# --------------------------------------------------------------------------
def load_dataset(path: str | Path) -> tuple[RawDataset, ValidationReport]:
    """Lee el archivo y devuelve ``(datos, informe)``.

    El informe solo trae los problemas de LECTURA (celdas vacías o ilegibles).
    Las reglas de negocio las revisa ``validators.validate_dataset``.
    Lanza ``DataLoadError`` ante problemas que impiden seguir leyendo.
    """
    source = Path(path)
    sheets = read_sheets(source)
    from_excel = source.is_file()
    report = ValidationReport()

    dataset = RawDataset(
        sources=_parse_node_list(sheets["sources"], report),
        sinks=_parse_node_list(sheets["sinks"], report),
        pipes=_parse_pipes(sheets["pipes"], report, from_excel),
        basins=_parse_basins(sheets["basin"], report),
        scenarios=_parse_scenarios(sheets["scenarios"], report),
        origin=str(source),
    )
    return dataset, report


def load_and_validate(path: str | Path) -> tuple[RawDataset, ValidationReport]:
    """Carga + validación completa. Es lo que debe llamar el controlador."""
    from bicentenario.io.validators import validate_dataset  # evita import circular

    dataset, report = load_dataset(path)
    validate_dataset(dataset, report)
    return dataset, report


def export_csv(source: str | Path, out_dir: str | Path) -> list[Path]:
    """Convierte el Excel en 5 CSV limpios (``data/csv/``).
    """
    sheets = read_sheets(source)
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for logical, sheet in sheets.items():
        rows = [r for r in sheet.rows if any(not _is_empty(c) for c in r)]
        if logical == "pipes":
            header_row, cols, _ = _find_header(sheet, _PIPE_COLUMNS, _PIPE_REQUIRED)
            header = sheet.rows[header_row]
            width = max(i for i, c in enumerate(header) if not _is_empty(c)) + 1
            body = [r for r in sheet.rows[header_row + 1:]
                    if normalize_id(_cell(r, cols, "id")) is not None]
            rows = [header] + body
            rows = [(list(r) + [None] * width)[:width] for r in rows]

        target = folder / CSV_FILE_NAMES[logical]
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for row in rows:
                writer.writerow(["" if c is None else (repr(c) if isinstance(c, float) else c)
                                 for c in row])
        written.append(target)
    return written