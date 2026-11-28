"""Pruebas del grafo, BFS/DFS, críticas, balance, comparación y reporte (Parte A)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bicentenario.errors import InputValidationError  # noqa: E402
from bicentenario.model.algorithms import (  # noqa: E402
    bfs,
    classify_utilization,
    compare_scenarios,
    critical_pipes,
    dfs,
    find_pipe,
    mass_balance,
    shortest_path,
)
from bicentenario.model.domain import Pipe  # noqa: E402
from bicentenario.model.graph import (  # noqa: E402
    DirectedGraph,
    dead_ends,
    detect_cycles,
    has_cycle,
    reachable_from_sources,
    reachable_to_sinks,
    topological_order,
)
from bicentenario.model.ordering import natural_key  # noqa: E402
from bicentenario.io.report_writer import write_csv_report, write_report  # noqa: E402


@dataclass
class FakePipeState:
    flow: float
    utilization_pct: float
    excess: float = 0.0


@dataclass
class FakeNodeState:
    inflow: float
    stored: float = 0.0
    is_source: bool = False
    is_sink: bool = False


@dataclass
class FakeSnapshot:
    step: int
    time_min: float
    pipes: dict[str, FakePipeState] = field(default_factory=dict)
    nodes: dict[str, FakeNodeState] = field(default_factory=dict)


def small_graph() -> DirectedGraph:
    """Grafo resuelto a mano: 1→2, 1→3, 2→4, 3→4, 4→5."""
    graph = DirectedGraph()
    graph.add_source("1")
    graph.add_sink("5")
    for pipe_id, source, target in [
        ("P1", "1", "2"), ("P2", "1", "3"), ("P3", "2", "4"),
        ("P4", "3", "4"), ("P5", "4", "5"),
    ]:
        graph.add_pipe(Pipe(pipe_id, source, target, 0.3, 0.015, 0.01, 1.0, 10.0))
    return graph


def fake_dataset() -> SimpleNamespace:
    return SimpleNamespace(
        sources=["1"], sinks=["5"],
        pipes=small_graph().pipes(),
        node_ids=lambda: small_graph().node_ids(),
    )


class TestDirectedGraph(unittest.TestCase):
    def test_structure_and_order(self):
        graph = small_graph()
        self.assertEqual(len(graph), 5)
        self.assertEqual(graph.edge_count(), 5)
        self.assertEqual(graph.node_ids(), ["1", "2", "3", "4", "5"])
        self.assertEqual(graph.pipe_ids(), ["P1", "P2", "P3", "P4", "P5"])
        self.assertEqual(graph.sources(), ["1"])
        self.assertEqual(graph.sinks(), ["5"])
        self.assertEqual(graph.out_neighbors("1"), ["2", "3"])
        self.assertEqual(graph.in_neighbors("4"), ["2", "3"])
        self.assertEqual([pipe.id for pipe in graph.out_pipes("1")], ["P1", "P2"])
        self.assertEqual(graph.degree("4"), (2, 1))

    def test_build_from_dataset(self):
        graph = DirectedGraph.build_from_dataset(fake_dataset())
        self.assertEqual(len(graph), 5)
        self.assertEqual(graph.edge_count(), 5)

    def test_duplicate_pipe(self):
        graph = small_graph()
        with self.assertRaises(InputValidationError):
            graph.add_pipe(Pipe("P1", "2", "3", 0.3, 0.015, 0.01, 1.0, 10.0))

    def test_natural_key(self):
        self.assertEqual(sorted(["P10", "P2", "P1"], key=natural_key),
                         ["P1", "P2", "P10"])


class TestTraversals(unittest.TestCase):
    def test_bfs(self):
        self.assertEqual(bfs(small_graph(), "1"), ["1", "2", "3", "4", "5"])

    def test_dfs(self):
        self.assertEqual(dfs(small_graph(), "1"), ["1", "2", "4", "5", "3"])

    def test_goal_stops_early(self):
        self.assertEqual(bfs(small_graph(), "1", goal="4"), ["1", "2", "3", "4"])
        self.assertEqual(dfs(small_graph(), "1", goal="4"), ["1", "2", "4"])

    def test_shortest_path(self):
        self.assertEqual(shortest_path(small_graph(), "1", "5"), ["1", "2", "4", "5"])

    def test_unknown_node(self):
        with self.assertRaises(InputValidationError):
            bfs(small_graph(), "99")


class TestTopology(unittest.TestCase):
    def test_acyclic_network(self):
        graph = small_graph()
        self.assertEqual(detect_cycles(graph), [])
        self.assertFalse(has_cycle(graph))
        self.assertIsNotNone(topological_order(graph))
        self.assertEqual(reachable_from_sources(graph), {"1", "2", "3", "4", "5"})
        self.assertEqual(reachable_to_sinks(graph), {"1", "2", "3", "4", "5"})
        self.assertEqual(dead_ends(graph), set())

    def test_cycle_detection(self):
        graph = small_graph()
        graph.add_pipe(Pipe("P6", "5", "2", 0.3, 0.015, 0.01, 1.0, 10.0))
        cycles = detect_cycles(graph)
        self.assertTrue(cycles)
        self.assertEqual(cycles[0][0], cycles[0][-1])
        self.assertTrue(has_cycle(graph))
        self.assertIsNone(topological_order(graph))

    def test_dead_end(self):
        graph = small_graph()
        graph.add_pipe(Pipe("P6", "4", "9", 0.3, 0.015, 0.01, 1.0, 10.0))
        self.assertEqual(dead_ends(graph, sinks=["5"]), {"9"})
        self.assertEqual(reachable_to_sinks(graph), {"1", "2", "3", "4", "5"})


class TestSearch(unittest.TestCase):
    def test_find_pipe_without_prefix(self):
        self.assertEqual(find_pipe(small_graph(), " 2 ").id, "P2")
        self.assertEqual(find_pipe(small_graph(), "p2").id, "P2")

    def test_unknown_pipe(self):
        with self.assertRaises(InputValidationError):
            find_pipe(small_graph(), "P99")


class TestCriticalPipes(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(classify_utilization(0), "low")
        self.assertEqual(classify_utilization(25), "low")
        self.assertEqual(classify_utilization(25.001), "moderate")
        self.assertEqual(classify_utilization(50), "moderate")
        self.assertEqual(classify_utilization(75), "high")
        self.assertEqual(classify_utilization(100), "near")
        self.assertEqual(classify_utilization(100.001), "exceeded")

    def test_ranking_and_limit(self):
        history = [FakeSnapshot(
            step=0, time_min=0.0,
            pipes={
                "P1": FakePipeState(1.2, 120.0),
                "P2": FakePipeState(0.3, 30.0),
                "P10": FakePipeState(1.2, 120.0),
            },
        )]
        rows = critical_pipes(history)
        self.assertEqual([row.pipe_id for row in rows], ["P1", "P10", "P2"])
        self.assertTrue(rows[0].overloaded)
        self.assertEqual([row.pipe_id for row in critical_pipes(history, limit=2)],
                         ["P1", "P10"])


class TestMassBalance(unittest.TestCase):
    def test_consistent_snapshot(self):
        snapshot = FakeSnapshot(
            step=0, time_min=0.0,
            pipes={
                "P1": FakePipeState(1.0, 100.0),
                "P2": FakePipeState(0.5, 50.0),
                "P3": FakePipeState(1.0, 100.0),
                "P4": FakePipeState(0.5, 50.0),
                "P5": FakePipeState(1.5, 150.0),
            },
            nodes={
                "1": FakeNodeState(1.5, is_source=True),
                "2": FakeNodeState(1.0),
                "3": FakeNodeState(0.5),
                "4": FakeNodeState(1.5),
                "5": FakeNodeState(1.5, is_sink=True),
            },
        )
        report = mass_balance([snapshot], small_graph())
        self.assertTrue(report.ok, report.format())
        self.assertEqual(report.steps_checked, 1)

    def test_detects_leak(self):
        snapshot = FakeSnapshot(
            step=0, time_min=0.0,
            pipes={
                "P1": FakePipeState(0.2, 20.0),  # debería ser 1.0
                "P2": FakePipeState(0.0, 0.0),
            },
            nodes={
                "1": FakeNodeState(1.0, is_source=True),
                "2": FakeNodeState(0.0),
                "5": FakeNodeState(0.0, is_sink=True),
            },
        )
        report = mass_balance([snapshot], graph=None, dataset=fake_dataset())
        self.assertFalse(report.ok)
        self.assertTrue(any(issue.kind == "nodo" for issue in report.issues))
        self.assertTrue(any(issue.kind == "global" for issue in report.issues))

    def test_dead_end_must_accumulate(self):
        graph = small_graph()
        graph.add_pipe(Pipe("P6", "4", "9", 0.3, 0.015, 0.01, 1.0, 10.0))
        snapshot = FakeSnapshot(
            step=0, time_min=0.0,
            pipes={
                "P1": FakePipeState(1.0, 100.0), "P2": FakePipeState(1.0, 100.0),
                "P3": FakePipeState(1.0, 100.0), "P4": FakePipeState(1.0, 100.0),
                "P5": FakePipeState(0.0, 0.0), "P6": FakePipeState(0.0, 0.0),
            },
            nodes={
                "1": FakeNodeState(1.0, is_source=True),
                "2": FakeNodeState(1.0),
                "3": FakeNodeState(1.0),
                "4": FakeNodeState(2.0),
                "5": FakeNodeState(0.0, is_sink=True),
                "9": FakeNodeState(0.7, stored=0.0),
            },
        )
        report = mass_balance([snapshot], graph)
        self.assertFalse(report.ok)
        self.assertTrue(any(issue.kind == "almacenamiento" for issue in report.issues))


class TestComparison(unittest.TestCase):
    def test_comparison(self):
        history_a = [FakeSnapshot(0, 0.0, {"P1": FakePipeState(0.5, 50.0)})]
        history_b = [FakeSnapshot(0, 0.0, {
            "P1": FakePipeState(1.2, 120.0), "P2": FakePipeState(0.1, 10.0),
        })]
        result = compare_scenarios(history_a, history_b, name_a="2", name_b="5")
        self.assertEqual(result.max_pct_a, 50.0)
        self.assertEqual(result.max_pct_b, 120.0)
        self.assertEqual(result.overloaded_a, 0)
        self.assertEqual(result.overloaded_b, 1)
        self.assertEqual(result.most_affected.pipe_id, "P1")
        self.assertEqual(result.steps_a, 1)
        self.assertIn("P1", result.summary())


class TestReportWriter(unittest.TestCase):
    def test_txt_and_csv(self):
        history = [FakeSnapshot(
            step=0, time_min=0.0,
            pipes={"P1": FakePipeState(0.1, 10.0)},
            nodes={"1": FakeNodeState(0.1)},
        )]
        with tempfile.TemporaryDirectory() as folder:
            report_path = write_report(
                Path(folder) / "reporte.txt", history=history, scenario="2",
                title="Prueba",
            )
            self.assertTrue(report_path.exists())
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("Prueba", text)
            self.assertIn("TUBERÍAS CRÍTICAS", text)
            self.assertIn("P1", text)

            paths = write_csv_report(folder, history=history, scenario="2")
            self.assertEqual([path.name for path in paths], [
                "resumen.csv", "tuberias_criticas.csv", "historial_utilizacion.csv",
            ])
            self.assertIn("pipe_id", paths[1].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
