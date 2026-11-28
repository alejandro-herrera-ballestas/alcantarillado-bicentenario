"""Algoritmos de la Parte A: recorridos, consultas y análisis de resultados."""

from bicentenario.model.algorithms.bfs import (
    bfs,
    bfs_parents,
    reconstruct_path,
    shortest_path,
)
from bicentenario.model.algorithms.dfs import dfs, dfs_parents
from bicentenario.model.algorithms.search import (
    find_node,
    find_pipe,
    find_scenario,
    normalize_query,
    search_by_id,
)
from bicentenario.model.algorithms.critical_pipes import (
    CriticalPipe,
    classify_utilization,
    critical_pipes,
    max_utilization_per_pipe,
    overloaded_pipes,
)
from bicentenario.model.algorithms.mass_balance import (
    BalanceIssue,
    MassBalanceReport,
    mass_balance,
)
from bicentenario.model.algorithms.scenario_comparison import (
    PipeDelta,
    ScenarioComparison,
    compare_scenarios,
)

__all__ = [
    "bfs", "bfs_parents", "reconstruct_path", "shortest_path",
    "dfs", "dfs_parents",
    "find_node", "find_pipe", "find_scenario", "normalize_query", "search_by_id",
    "CriticalPipe", "classify_utilization", "critical_pipes",
    "max_utilization_per_pipe", "overloaded_pipes",
    "BalanceIssue", "MassBalanceReport", "mass_balance",
    "PipeDelta", "ScenarioComparison", "compare_scenarios",
]
