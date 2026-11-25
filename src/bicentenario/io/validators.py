"""Validaciones de datos (al cargar) y de lo que escribe el usuario (en la GUI).

Dos partes independientes:

A) ``validate_dataset``
   - ERROR   -> hay que corregir el archivo; la aplicación no debe simular.
   - AVISO   -> se puede continuar, pero conviene revisarlo.
   - INFO    -> solo informativo.

B) Validadores de entradas de la interfaz: ``validate_simulation_params`` y
   ``validate_pipe_query``. Lanzan ``InputValidationError`` con un mensaje
   listo para mostrar al usuario.
"""

from __future__ import annotations

import difflib
import math
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass

from bicentenario.errors import InputValidationError
from bicentenario.io.records import (
    BASIN_SHEET, PIPES_SHEET, SCENARIOS_SHEET, SINKS_SHEET, SOURCES_SHEET,
    RawDataset, ValidationReport, natural_key,
)

# Umbrales de los avisos (no son errores: el docente puede usar otros valores).
ROUGHNESS_RANGE = (0.008, 0.050)   # n de Manning razonable para tuberías
MANNING_TOLERANCE = 0.01           # 1 % de diferencia entre Qmax y Manning a tubo lleno
INCH_TO_M = 0.0254
DIAMETER_TOLERANCE_M = 5e-4        # 0,5 mm entre ⌀ (in) y ⌀ (m)
AREA_SUSPICIOUS_HA = 5000          # un área mayor sugiere que viene en m² y no en ha
INTENSITY_SUSPICIOUS_MM_H = 500    # por encima de esto, probablemente hay un error
MAX_STEPS = 100_000                # tope de pasos de simulación (evita congelar la GUI)
RATIONAL_COEFFICIENT = 0.00278     # Q[m³/s] = 0.00278 · C · I[mm/h] · A[ha]  (método racional)
INFLOW_RATIO_WARNING = 10          # aviso si el caudal de entrada supera 10 veces la capacidad de salida


def manning_full_pipe_qmax(diameter_m: float, n: float, slope: float) -> float:
    """Capacidad de una tubería circular llena según Manning (m³/s).

    Solo se usa para COMPARAR con el Qmax del archivo; el enunciado indica que
    las capacidades no se recalculan.  Q = (1/n)·A·R^(2/3)·S^(1/2), con
    A = π·D²/4 y R = D/4.
    """
    area = math.pi * diameter_m ** 2 / 4
    radius = diameter_m / 4
    return (1 / n) * area * radius ** (2 / 3) * slope ** 0.5



def validate_dataset(dataset: RawDataset, report: ValidationReport | None = None) -> ValidationReport:
    """Ejecuta todas las validaciones y devuelve el informe (nuevo o ampliado)."""
    if report is None:
        report = ValidationReport()
    _check_pipes(dataset, report)
    nodes = _check_nodes(dataset, report)
    _check_topology(dataset, nodes, report)
    _check_basins(dataset, nodes, report)
    _check_scenarios(dataset, report)
    _check_inflow_scale(dataset, report)
    return report


def _check_pipes(dataset: RawDataset, report: ValidationReport) -> None:
    pipes = dataset.pipes
    if not pipes:
        report.error("No hay tuberías en el archivo", sheet=PIPES_SHEET)
        return

    # IDs únicos
    rows_by_id = defaultdict(list)
    for p in pipes:
        rows_by_id[p.id].append(p.row)
    for pipe_id, rows in rows_by_id.items():
        if len(rows) > 1:
            report.error(f"ID de tubería repetido '{pipe_id}' (filas {rows})", sheet=PIPES_SHEET)

    for p in pipes:
        where = dict(sheet=PIPES_SHEET, row=p.row)
        if p.from_node == p.to_node:
            report.error(f"Tubería {p.id}: empieza y termina en el mismo nodo '{p.from_node}'",
                         column="From/To", **where)
        positive_ok = True
        for label, value in (("longitud", p.length_m), ("diámetro (m)", p.diameter_m),
                             ("rugosidad n", p.roughness_n), ("pendiente S", p.slope),
                             ("capacidad Q", p.qmax)):
            if value <= 0:
                report.error(f"Tubería {p.id}: {label} debe ser mayor que 0 (es {value})", **where)
                positive_ok = False

        low, high = ROUGHNESS_RANGE
        if p.roughness_n > 0 and not low <= p.roughness_n <= high:
            report.warning(f"Tubería {p.id}: rugosidad n={p.roughness_n} fuera del rango "
                           f"habitual ({low}–{high})", **where)

        if p.diameter_in is not None and p.diameter_m > 0:
            if abs(p.diameter_in * INCH_TO_M - p.diameter_m) > DIAMETER_TOLERANCE_M:
                report.warning(f"Tubería {p.id}: ⌀ en pulgadas ({p.diameter_in}) y en metros "
                               f"({p.diameter_m}) no coinciden", **where)

        if positive_ok:
            reference = manning_full_pipe_qmax(p.diameter_m, p.roughness_n, p.slope)
            if abs(p.qmax - reference) / reference > MANNING_TOLERANCE:
                report.warning(
                    f"Tubería {p.id}: Q={p.qmax:.5f} m³/s difiere de Manning a tubo lleno "
                    f"({reference:.5f}). No se recalcula: se usa el valor del archivo", **where)

    # Tuberías en paralelo (mismo par de nodos)
    by_pair = defaultdict(list)
    for p in pipes:
        by_pair[(p.from_node, p.to_node)].append(p.id)
    for (a, b), ids in by_pair.items():
        if len(ids) > 1:
            report.warning(f"Varias tuberías conectan {a} → {b}: {', '.join(ids)}",
                           sheet=PIPES_SHEET)

    # Huecos en la numeración P1..Pn
    numbers = []
    for p in pipes:
        m = re.fullmatch(r"P(\d+)", p.id, flags=re.IGNORECASE)
        if m:
            numbers.append(int(m.group(1)))
    if numbers and len(numbers) == len(pipes):
        missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        if missing:
            shown = ", ".join(f"P{n}" for n in missing[:10]) + ("…" if len(missing) > 10 else "")
            report.warning(f"La numeración de tuberías tiene huecos: faltan {shown}",
                           sheet=PIPES_SHEET)


def _check_nodes(dataset: RawDataset, report: ValidationReport) -> set[str]:
    nodes = set(dataset.node_ids())
    endpoints = {p.from_node for p in dataset.pipes} | {p.to_node for p in dataset.pipes}

    for label, sheet, ids in (("fuente", SOURCES_SHEET, dataset.sources),
                              ("sumidero", SINKS_SHEET, dataset.sinks)):
        if not ids:
            report.error(f"No hay ningún {label} definido", sheet=sheet)
        for node, count in Counter(ids).items():
            if count > 1:
                report.warning(f"El {label} '{node}' aparece {count} veces", sheet=sheet)
        for node in dict.fromkeys(ids):
            if dataset.pipes and node not in endpoints:
                report.error(f"El {label} '{node}' no aparece en ninguna tubería "
                             f"(nodo aislado)", sheet=sheet)

    both = set(dataset.sources) & set(dataset.sinks)
    if both:
        report.error("Hay nodos que son fuente y sumidero a la vez: "
                     + ", ".join(sorted(both, key=natural_key)), sheet=SINKS_SHEET)

    # IDs que solo se diferencian por mayúsculas/minúsculas
    folded = defaultdict(set)
    for node in nodes:
        folded[node.casefold()].add(node)
    for variants in folded.values():
        if len(variants) > 1:
            report.warning("IDs de nodo que solo se diferencian por mayúsculas: "
                           + ", ".join(sorted(variants)), sheet=PIPES_SHEET)
    return nodes


def _reach(starts, adjacency) -> set[str]:
    """Nodos alcanzables desde ``starts`` siguiendo ``adjacency`` (con cola)."""
    seen = set(starts)
    queue = deque(starts)
    while queue:
        node = queue.popleft()
        for nxt in adjacency[node]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _nodes_in_or_after_cycles(nodes, outgoing, incoming) -> set[str]:
    """Nodos que quedan sin procesar al ordenar topológicamente (algoritmo de Kahn)."""
    pending = {n: len(incoming[n]) for n in nodes}
    queue = deque(n for n in nodes if pending[n] == 0)
    done = 0
    while queue:
        node = queue.popleft()
        done += 1
        for nxt in outgoing[node]:
            pending[nxt] -= 1
            if pending[nxt] == 0:
                queue.append(nxt)
    return {n for n, left in pending.items() if left > 0} if done < len(nodes) else set()


def _check_topology(dataset: RawDataset, nodes: set[str], report: ValidationReport) -> None:
    if not dataset.pipes:
        return
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for p in dataset.pipes:
        outgoing[p.from_node].append(p.to_node)
        incoming[p.to_node].append(p.from_node)

    def names(items) -> str:
        return ", ".join(sorted(items, key=natural_key))

    entering = [s for s in dict.fromkeys(dataset.sources) if incoming[s]]
    if entering:
        report.warning(f"Fuentes que además reciben agua de otras tuberías: {names(entering)}",
                       sheet=SOURCES_SHEET)
    leaving = [s for s in dict.fromkeys(dataset.sinks) if outgoing[s]]
    if leaving:
        report.warning(f"Sumideros con tuberías de salida: {names(leaving)}", sheet=SINKS_SHEET)

    sinks = set(dataset.sinks)
    dead_ends = {n for n in nodes if not outgoing[n] and n not in sinks}
    if dead_ends:
        report.error(f"Nodos sin tubería de salida que no son sumidero (el agua quedaría "
                     f"atrapada): {names(dead_ends)}", sheet=PIPES_SHEET)

    if dataset.sinks:
        reaches_sink = _reach(sinks, incoming)           # recorrido hacia atrás
        trapped = nodes - reaches_sink - dead_ends
        if trapped:
            report.error(f"Nodos desde los que no se puede llegar a ningún sumidero: "
                         f"{names(trapped)}", sheet=PIPES_SHEET)

    if dataset.sources:
        fed = _reach(set(dataset.sources), outgoing)
        orphans = nodes - fed
        if orphans:
            report.warning(f"Nodos a los que no llega agua desde ninguna fuente: "
                           f"{names(orphans)}", sheet=PIPES_SHEET)

    cyclic = _nodes_in_or_after_cycles(nodes, outgoing, incoming)
    if cyclic:
        report.warning(f"La red tiene ciclos: nodos involucrados o aguas abajo de un ciclo: "
                       f"{names(cyclic)}", sheet=PIPES_SHEET)


def _check_basins(dataset: RawDataset, nodes: set[str], report: ValidationReport) -> None:
    if not dataset.basins:
        report.error("No hay ninguna cuenca de drenaje", sheet=BASIN_SHEET)
        return
    for b in dataset.basins:
        where = dict(sheet=BASIN_SHEET, row=b.row)
        if not 0 <= b.runoff_coeff <= 1:
            report.error(f"Coeficiente de escorrentía C={b.runoff_coeff} debe estar entre 0 y 1",
                         column="C", **where)
        if b.area_ha <= 0:
            report.error(f"Área de drenaje A={b.area_ha} debe ser mayor que 0", column="A", **where)
        elif b.area_ha > AREA_SUSPICIOUS_HA:
            report.warning(f"Área A={b.area_ha:g} ha es muy grande: ¿está en m² en vez de ha?",
                           column="A", **where)
        if b.node is not None and b.node not in nodes:
            report.error(f"La cuenca apunta al nodo '{b.node}', que no existe", **where)

    if any(b.node is None for b in dataset.basins):
        report.warning("La cuenca no indica en qué nodo(s) entra el caudal de lluvia: la regla "
                       "de reparto debe definirla el docente", sheet=BASIN_SHEET)


def _check_scenarios(dataset: RawDataset, report: ValidationReport) -> None:
    if not dataset.scenarios:
        report.error("No hay escenarios de precipitación", sheet=SCENARIOS_SHEET)
        return
    for scenario_id, count in Counter(s.id for s in dataset.scenarios).items():
        if count > 1:
            report.error(f"Identificador de escenario repetido: {scenario_id}",
                         sheet=SCENARIOS_SHEET)
    for s in dataset.scenarios:
        where = dict(sheet=SCENARIOS_SHEET, row=s.row, column="Intensity")
        if s.intensity_mm_h < 0:
            report.error(f"Escenario {s.id}: la intensidad no puede ser negativa "
                         f"({s.intensity_mm_h} mm/h)", **where)
        elif s.intensity_mm_h > INTENSITY_SUSPICIOUS_MM_H:
            report.warning(f"Escenario {s.id}: intensidad muy alta ({s.intensity_mm_h:g} mm/h)",
                           **where)


def _check_inflow_scale(dataset: RawDataset, report: ValidationReport) -> None:
    """Aviso si la lluvia aporta muchísima más agua de la que la red puede evacuar.

    Compara el caudal total de entrada del escenario más fuerte (método racional,
    sumando todas las cuencas) con la capacidad de las tuberías que llegan al
    sumidero.
    """
    if not (dataset.basins and dataset.scenarios and dataset.pipes and dataset.sinks):
        return
    sinks = set(dataset.sinks)
    outlet_capacity = sum(p.qmax for p in dataset.pipes if p.to_node in sinks and p.qmax > 0)
    strongest = max(dataset.scenarios, key=lambda s: s.intensity_mm_h)
    if outlet_capacity <= 0 or strongest.intensity_mm_h <= 0:
        return
    weighted_area = sum(max(b.runoff_coeff, 0) * max(b.area_ha, 0) for b in dataset.basins)
    inflow = RATIONAL_COEFFICIENT * weighted_area * strongest.intensity_mm_h
    ratio = inflow / outlet_capacity
    if ratio > INFLOW_RATIO_WARNING:
        report.warning(
            f"Con el escenario más fuerte ({strongest.id}: {strongest.intensity_mm_h:g} mm/h) las "
            f"cuencas aportan {inflow:.2f} m³/s en total, unas {ratio:.0f} veces la capacidad de "
            f"las tuberías que llegan al sumidero ({outlet_capacity:.3f} m³/s). Casi toda la red "
            f"quedará sobrecargada: confirme con el docente la unidad del área (¿ha?) y cómo se "
            f"reparte el caudal entre los nodos", sheet=BASIN_SHEET)



def parse_positive_number(text: str, name: str) -> float:
    """Convierte el texto de un campo en un número > 0 (acepta ``0,5``).

    Lanza ``InputValidationError`` con un mensaje para el usuario.
    """
    cleaned = (text or "").strip().replace(",", ".")
    if not cleaned:
        raise InputValidationError(f"Escriba {name}.")
    try:
        number = float(cleaned)
    except ValueError:
        raise InputValidationError(f"{name.capitalize()}: '{text.strip()}' no es un número.") from None
    if not math.isfinite(number):
        raise InputValidationError(f"{name.capitalize()}: el valor no es válido.")
    if number <= 0:
        raise InputValidationError(f"{name.capitalize()} debe ser mayor que 0.")
    return number


@dataclass(frozen=True)
class SimulationParams:

    duration_min: float
    step_min: float
    n_steps: int


def validate_simulation_params(duration_text: str, step_text: str,
                               max_steps: int = MAX_STEPS) -> SimulationParams:
    """Valida duración e intervalo escritos por el usuario (en minutos).
    Ambos numéricos y > 0, intervalo ≤ duración, duración múltiplo
    exacto del intervalo y no más de ``max_steps`` pasos.
    """
    duration = parse_positive_number(duration_text, "la duración (en minutos)")
    step = parse_positive_number(step_text, "el intervalo de actualización (en minutos)")
    if step > duration:
        raise InputValidationError(
            f"El intervalo ({step:g} min) no puede ser mayor que la duración ({duration:g} min).")
    ratio = duration / step
    if abs(ratio - round(ratio)) > 1e-9:
        raise InputValidationError(
            f"La duración ({duration:g} min) debe ser múltiplo del intervalo ({step:g} min).")
    n_steps = int(round(ratio))
    if n_steps > max_steps:
        raise InputValidationError(
            f"Son demasiados pasos ({n_steps}). Use un intervalo mayor o una duración menor "
            f"(máximo {max_steps} pasos).")
    return SimulationParams(duration_min=duration, step_min=step, n_steps=n_steps)


def validate_pipe_query(text: str, known_ids) -> str:
    """Valida el ID de tubería escrito al buscar y devuelve el ID canonico
    """
    query = re.sub(r"\s+", "", text or "")
    if not query:
        raise InputValidationError("Escriba el ID de la tubería (por ejemplo P12).")
    by_folded = {pipe_id.casefold(): pipe_id for pipe_id in known_ids}
    for candidate in (query, f"P{query}"):
        if candidate.casefold() in by_folded:
            return by_folded[candidate.casefold()]
    close = difflib.get_close_matches(query.casefold(), list(by_folded), n=3, cutoff=0.6)
    hint = f" ¿Quiso decir {', '.join(by_folded[c] for c in close)}?" if close else ""
    raise InputValidationError(f"No existe la tubería '{query}'.{hint}")
