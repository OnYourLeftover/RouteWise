# Owned by Member 2 (Sneha, Role B). Placeholder - replace.
"""Tests for core/search.py (SPEC.md section 10)."""
from __future__ import annotations

import math
import random

import pytest

from core.graph import GridGraph, Node, edge, make_random_grid
from core.search import solve
from reference_dijkstra import dijkstra

NUM_GRIDS = 200
BLOCKED_DENSITIES = (0.05, 0.25, 0.45)  # last two give many unreachable pairs
ADMISSIBLE = ("manhattan", "euclidean")
RESULT_KEYS = {"found", "path", "cost", "nodes_explored", "explored_order", "time_ms"}


# ---- helpers -----------------------------------------------------------
def grid_and_pair(seed: int) -> tuple[GridGraph, Node, Node]:
    """A seeded 10x10 grid with traffic and blocked roads, plus two distinct nodes."""
    graph = make_random_grid(rows=10, cols=10, seed=seed, traffic_density=0.3,
                             blocked_density=BLOCKED_DENSITIES[seed % 3])
    rng = random.Random(seed)
    nodes = [(r, c) for r in range(graph.rows) for c in range(graph.cols)]
    start, goal = rng.sample(nodes, 2)
    return graph, start, goal


def same_cost(a: float, b: float) -> bool:
    """Float costs are sums in different orders, so compare with a tiny tolerance."""
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def two_row_graph() -> GridGraph:
    base = {}
    for c in range(4):
        base[edge((0, c), (0, c + 1))] = 2.0     # top row: cost 2 each
        base[edge((1, c), (1, c + 1))] = 1.0     # bottom row: cost 1 each
    return GridGraph(2, 5, base)                  # vertical edges default to 1.0


# ---- group 1: A* optimality -------------------------------------------
@pytest.mark.parametrize("heuristic", ADMISSIBLE)
def test_astar_matches_dijkstra(heuristic: str) -> None:
    for seed in range(NUM_GRIDS):
        graph, start, goal = grid_and_pair(seed)
        expected = dijkstra(graph, start, goal)
        result = solve(graph, start, goal, "astar", heuristic)
        if expected is None:
            assert result["found"] is False, f"seed {seed}: should be unreachable"
        else:
            assert result["found"] is True, f"seed {seed}: should be reachable"
            assert same_cost(result["cost"], expected), f"seed {seed}"


# ---- group 2: GBFS validity -------------------------------------------
@pytest.mark.parametrize("heuristic", ADMISSIBLE)
def test_gbfs_is_valid(heuristic: str) -> None:
    for seed in range(NUM_GRIDS):
        graph, start, goal = grid_and_pair(seed)
        optimal = dijkstra(graph, start, goal)
        result = solve(graph, start, goal, "gbfs", heuristic)
        if optimal is None:
            assert result["found"] is False, f"seed {seed}"
            continue
        assert result["found"] is True, f"seed {seed}"
        path = result["path"]
        assert path[0] == start and path[-1] == goal, f"seed {seed}"
        total = 0.0
        for u, v in zip(path, path[1:]):
            # is_blocked raises ValueError if u and v are not adjacent nodes
            assert not graph.is_blocked(u, v), f"seed {seed}: blocked edge used"
            total += graph.cost(u, v)
        assert same_cost(result["cost"], total), f"seed {seed}"
        assert result["cost"] >= optimal - 1e-9, f"seed {seed}: beat Dijkstra"


# ---- group 3: edge cases ----------------------------------------------
@pytest.mark.parametrize("algo", ["astar", "gbfs"])
def test_start_equals_goal(algo: str) -> None:
    graph = make_random_grid(rows=5, cols=5, seed=1)
    result = solve(graph, (2, 2), (2, 2), algo, "manhattan")
    assert set(result) == RESULT_KEYS
    assert result["found"] is True
    assert result["path"] == [(2, 2)]
    assert result["cost"] == 0.0
    assert result["nodes_explored"] == 0
    assert result["explored_order"] == []


@pytest.mark.parametrize("algo", ["astar", "gbfs"])
def test_unreachable_goal(algo: str) -> None:
    graph = GridGraph(1, 3)
    graph.block((0, 1), (0, 2))  # cuts (0, 2) off from the rest
    result = solve(graph, (0, 0), (0, 2), algo, "manhattan")
    assert set(result) == RESULT_KEYS
    assert result["found"] is False
    assert result["path"] == []
    assert result["cost"] is None
    assert result["explored_order"] == [(0, 0), (0, 1)]
    assert result["nodes_explored"] == len(result["explored_order"])


@pytest.mark.parametrize("algo", ["astar", "gbfs"])
def test_out_of_bounds_raises(algo: str) -> None:
    graph = GridGraph(3, 3)
    with pytest.raises(ValueError):
        solve(graph, (5, 5), (0, 0), algo, "manhattan")   # bad start
    with pytest.raises(ValueError):
        solve(graph, (0, 0), (-1, 0), algo, "manhattan")  # bad goal


def test_bad_algo_raises() -> None:
    with pytest.raises(ValueError):
        solve(GridGraph(3, 3), (0, 0), (2, 2), "dijkstra", "manhattan")


def test_bad_heuristic_raises() -> None:
    with pytest.raises(ValueError):
        solve(GridGraph(3, 3), (0, 0), (2, 2), "astar", "chebyshev")


# ---- group 4: deterministic inadmissible-heuristic demo ---------------
@pytest.mark.parametrize("algo, heuristic, expected_cost", [
    ("astar", "manhattan", 6.0),
    ("astar", "euclidean", 6.0),
    ("astar", "inflated_manhattan", 8.0),   # top row: inadmissible h misleads A*
    ("gbfs", "manhattan", 8.0),             # top row
    ("gbfs", "inflated_manhattan", 8.0),
])
def test_two_row_costs(algo: str, heuristic: str, expected_cost: float) -> None:
    result = solve(two_row_graph(), (0, 0), (0, 4), algo, heuristic)
    assert result["found"] is True
    assert result["cost"] == expected_cost


def test_two_row_gbfs_order_identical() -> None:
    """2 x Manhattan keeps the same ordering of nodes, so GBFS explores identically."""
    graph = two_row_graph()
    plain = solve(graph, (0, 0), (0, 4), "gbfs", "manhattan")
    inflated = solve(graph, (0, 0), (0, 4), "gbfs", "inflated_manhattan")
    assert inflated["explored_order"] == plain["explored_order"]