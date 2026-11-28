"""Exportador TXT/CSV del reporte de resultados (RF12, Parte A).

No importa Tkinter ni controladores: solo recibe el historial (de Persona B),
el grafo/dataset (de Persona C) y los resultados calculados por los algoritmos
de la Parte A. Así se puede llamar tanto desde la interfaz como desde una
prueba o un script.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bicentenario.model.algorithms.critical_pipes import critical_pipes
from bicentenario.model.algorithms.mass_balance import MassBalanceReport
from bicentenario.model.algorithms.scenario_comparison import ScenarioComparison
from bicentenario.model.ordering import natural_key

__all__ = ["write_csv_report", "write_report"]


def _snapshots(history: object) -> list[object]:
    snapshots = list(history)  # type: ignore[arg-type]
    if not snapshots and hasattr(history, "get_at"):
        snapshots = [history.get_at(i) for i in range(len(history))]  # type: ignore[arg-type]
    return snapshots


def _pipe_pct(state: object) -> float:
    attribute = getattr(state, "utilization_pct", None)
    return float(attribute if attribute is not None else state)


def _scenario_text(scenario: Any) -> str:
    if scenario is None:
        return "No especificado"
    if isinstance(scenario, str):
        return scenario
    identifier = getattr(scenario, "id", "?")
    intensity = getattr(scenario, "intensity_mm_h", None)
    condition = getattr(scenario, "condition", "")
    text = f"{identifier} — {condition or 'Escenario'}"
    if intensity is not None:
        text += f" ({float(intensity):g} mm/h)"
    return text


def _critical_rows(history: object, critical: Any) -> list[Any]:
    if critical is None:
        return critical_pipes(history)
    return list(critical)


def write_report(
    path: str | Path,
    *,
    history: object,
    graph: object | None = None,
    dataset: object | None = None,
    scenario: Any = None,
    params: Any = None,
    critical: Any = None,
    comparison: ScenarioComparison | None = None,
    balance: MassBalanceReport | None = None,
    title: str = "Reporte de simulación — Ciudad Bicentenario",
) -> Path:
    """Escribe un reporte de texto y devuelve la ruta creada.

    Todos los argumentos excepto ``history`` son opcionales: el reporte se
    puede generar con solo el historial de la simulación.
    """
    if history is None:
        raise ValueError("Se necesita el historial de la simulación.")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    snapshots = _snapshots(history)
    rows = _critical_rows(history, critical)
    overloaded = [row for row in rows if getattr(row, "overloaded", False)]
    pipe_count = max((len(getattr(s, "pipes", {})) for s in snapshots), default=0)
    auto_critical = critical is None

    lines = [
        "=" * 72,
        title,
        "=" * 72,
        "",
        f"Escenario: {_scenario_text(scenario)}",
    ]
    if params is not None:
        duration = getattr(params, "duration_min", None)
        step = getattr(params, "step_min", None)
        steps = getattr(params, "n_steps", None)
        if duration is not None and step is not None:
            lines.append(f"Duración: {duration:g} min · Intervalo: {step:g} min")
        if steps is not None:
            lines.append(f"Pasos simulados: {steps}")
    if dataset is not None:
        origin = getattr(dataset, "origin", "")
        if origin:
            lines.append(f"Origen de los datos: {origin}")

    lines += [
        f"Instantes registrados: {len(snapshots)}",
        f"Tuberías en la red: {pipe_count}",
        "",
        "-" * 72,
        "TUBERÍAS CRÍTICAS (por utilización máxima)",
        "-" * 72,
        f"{'Tubería':<10}{'Máx. %':>10}{'Paso':>7}{'Nivel':>16}",
    ]
    if rows:
        for row in rows:
            lines.append(
                f"{str(getattr(row, 'pipe_id', '?')):<10}"
                f"{float(getattr(row, 'max_utilization_pct', 0.0)):>10.2f}"
                f"{int(getattr(row, 'peak_step', 0)):>7}"
                f"{str(getattr(row, 'level', '?')):>16}"
            )
    else:
        lines.append("(sin datos)")
    if auto_critical:
        lines.append("Clasificación: 0–25 verde, >25–50 amarillo, >50–75 naranja, "
                     ">75–100 rojo, >100 rojo oscuro.")

    lines += [
        "",
        "-" * 72,
        "SOBRECARGA",
        "-" * 72,
        f"Tuberías que superaron el 100 % de su capacidad: {len(overloaded)}",
    ]
    if overloaded:
        lines.append("IDs: " + ", ".join(
            sorted((str(getattr(row, "pipe_id")) for row in overloaded), key=natural_key)
        ))

    if balance is not None:
        lines += ["", "-" * 72, "BALANCE DE MASA", "-" * 72, balance.summary()]
        for issue in balance.issues[:20]:
            lines.append(f"  {issue}")
        if len(balance.issues) > 20:
            lines.append(f"  … y {len(balance.issues) - 20} incidencia(s) más.")

    if comparison is not None:
        lines += [
            "", "-" * 72, "COMPARACIÓN DE ESCENARIOS", "-" * 72,
            comparison.summary(),
        ]
        for row in comparison.per_pipe[:15]:
            lines.append(
                f"  {row.pipe_id:<8} {row.a_pct:8.2f} % → {row.b_pct:8.2f} % "
                f"({row.delta_pct:+8.2f} pp)"
            )
        if len(comparison.per_pipe) > 15:
            lines.append(f"  … y {len(comparison.per_pipe) - 15} tubería(s) más "
                         "(listado completo en comparacion_escenarios.csv).")

    lines += ["", "=" * 72, "Fin del reporte.", ""]
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


def write_csv_report(
    out_dir: str | Path,
    *,
    history: object,
    scenario: Any = None,
    critical: Any = None,
    comparison: ScenarioComparison | None = None,
    include_history: bool = True,
) -> list[Path]:
    """Escribe CSVs separados y devuelve las rutas creadas, en orden fijo.

    Archivos: ``resumen.csv``, ``tuberias_criticas.csv``,
    ``comparacion_escenarios.csv`` (si hay comparación) y
    ``historial_utilizacion.csv`` (si ``include_history``).
    """
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    snapshots = _snapshots(history)
    rows = _critical_rows(history, critical)

    summary_path = folder / "resumen.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["indicador", "valor"])
        writer.writerow(["escenario", _scenario_text(scenario)])
        writer.writerow(["instantes_registrados", len(snapshots)])
        writer.writerow(["tuberias_criticas", len(rows)])
        writer.writerow([
            "tuberias_sobrecapacidad",
            sum(1 for row in rows if getattr(row, "overloaded", False)),
        ])
    written.append(summary_path)

    critical_path = folder / "tuberias_criticas.csv"
    with critical_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "pipe_id", "max_utilizacion_pct", "peak_step", "sobrecargada", "nivel"
        ])
        for row in sorted(rows, key=lambda item: natural_key(getattr(item, "pipe_id", ""))):
            writer.writerow([
                getattr(row, "pipe_id", ""),
                f"{float(getattr(row, 'max_utilization_pct', 0.0)):.6f}",
                int(getattr(row, "peak_step", 0)),
                "si" if getattr(row, "overloaded", False) else "no",
                getattr(row, "level", ""),
            ])
    written.append(critical_path)

    if comparison is not None:
        comparison_path = folder / "comparacion_escenarios.csv"
        with comparison_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["pipe_id", "a_pct", "b_pct", "delta_pct"])
            for pipe_id, a_pct, b_pct, delta_pct in comparison.to_rows():
                writer.writerow([
                    pipe_id, f"{a_pct:.6f}", f"{b_pct:.6f}", f"{delta_pct:.6f}"
                ])
        written.append(comparison_path)

    if include_history:
        history_path = folder / "historial_utilizacion.csv"
        with history_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["paso", "tiempo_min", "pipe_id", "utilizacion_pct"])
            for snapshot in snapshots:
                step = int(getattr(snapshot, "step", 0))
                time_min = float(getattr(snapshot, "time_min", step))
                pipes: Mapping[str, object] = getattr(snapshot, "pipes", {})  # type: ignore[assignment]
                for pipe_id in sorted(pipes, key=natural_key):
                    writer.writerow([
                        step, f"{time_min:.6f}", pipe_id,
                        f"{_pipe_pct(pipes[pipe_id]):.6f}",
                    ])
        written.append(history_path)

    return written
