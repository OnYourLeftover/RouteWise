"""Heuristics for grid search (SPEC.md section 5)."""
from __future__ import annotations

import math
from typing import Callable

Node = tuple[int, int]


def manhattan(n: Node, goal: Node) -> float:
    """|dr| + |dc|. Admissible and consistent when every edge costs >= 1."""
    return float(abs(n[0] - goal[0]) + abs(n[1] - goal[1]))


def euclidean(n: Node, goal: Node) -> float:
    """Straight-line distance. Admissible and consistent when every edge costs >= 1."""
    return math.hypot(n[0] - goal[0], n[1] - goal[1])


def inflated_manhattan(n: Node, goal: Node) -> float:
    """2 x Manhattan. INADMISSIBLE: demo only."""
    return 2.0 * manhattan(n, goal)


HEURISTICS: dict[str, Callable[[Node, Node], float]] = {
    "manhattan": manhattan,
    "euclidean": euclidean,
    "inflated_manhattan": inflated_manhattan,
}
