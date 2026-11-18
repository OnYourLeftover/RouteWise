"""Weighted grid graph for the delivery-route project (SPEC.md section 4)."""
from __future__ import annotations

import random

Node = tuple[int, int]   # (row, col), (0, 0) is top-left
Edge = tuple[Node, Node]  # always normalized: (min(u, v), max(u, v))

# Fixed neighbor order (determinism): up, right, down, left.
_DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))


def edge(u: Node, v: Node) -> Edge:
    """Normalize an undirected edge so (u, v) and (v, u) give the same key."""
    return (u, v) if u <= v else (v, u)


class GridGraph:
    """4-connected grid with undirected edges.

    Effective edge cost = base_cost * traffic. Both are >= 1.0, which keeps
    Manhattan and Euclidean distance admissible. A blocked edge is unavailable.
    """

    def __init__(self, rows: int, cols: int,
                 base_cost: dict[Edge, float] | None = None) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("rows and cols must be >= 1")
        self.rows = rows
        self.cols = cols
        self._base: dict[Edge, float] = {}
        self._traffic: dict[Edge, float] = {}
        self._blocked: set[Edge] = set()
        for (u, v), c in (base_cost or {}).items():
            self._check_edge(u, v)
            if c < 1.0:
                raise ValueError(f"base cost must be >= 1.0, got {c} for {(u, v)}")
            self._base[edge(u, v)] = float(c)

    # ---- helpers -------------------------------------------------------
    def in_bounds(self, node: Node) -> bool:
        r, c = node
        return 0 <= r < self.rows and 0 <= c < self.cols

    def _check_edge(self, u: Node, v: Node) -> None:
        """Raise ValueError unless u and v are in-bounds, adjacent nodes."""
        if not (self.in_bounds(u) and self.in_bounds(v)):
            raise ValueError(f"edge {(u, v)} is out of bounds")
        if abs(u[0] - v[0]) + abs(u[1] - v[1]) != 1:
            raise ValueError(f"nodes {u} and {v} are not adjacent")

    # ---- queries -------------------------------------------------------
    def neighbors(self, node: Node) -> list[tuple[Node, float]]:
        """(neighbor, effective_cost) pairs in fixed order: up, right, down, left."""
        if not self.in_bounds(node):
            raise ValueError(f"node {node} is out of bounds")
        result: list[tuple[Node, float]] = []
        for dr, dc in _DIRECTIONS:
            nb = (node[0] + dr, node[1] + dc)
            if self.in_bounds(nb) and edge(node, nb) not in self._blocked:
                result.append((nb, self.cost(node, nb)))
        return result

    def cost(self, u: Node, v: Node) -> float:
        """Effective cost of a usable edge. ValueError if not adjacent or blocked."""
        self._check_edge(u, v)
        e = edge(u, v)
        if e in self._blocked:
            raise ValueError(f"edge {(u, v)} is blocked")
        return self._base.get(e, 1.0) * self._traffic.get(e, 1.0)

    def traffic(self, u: Node, v: Node) -> float:
        self._check_edge(u, v)
        return self._traffic.get(edge(u, v), 1.0)

    def is_blocked(self, u: Node, v: Node) -> bool:
        self._check_edge(u, v)
        return edge(u, v) in self._blocked

    def edges(self) -> list[Edge]:
        """All edges (including blocked ones, for drawing), in row-major order."""
        result: list[Edge] = []
        for r in range(self.rows):
            for c in range(self.cols):
                if c + 1 < self.cols:
                    result.append(((r, c), (r, c + 1)))
                if r + 1 < self.rows:
                    result.append(((r, c), (r + 1, c)))
        return result

    # ---- updates -------------------------------------------------------
    def set_traffic(self, u: Node, v: Node, multiplier: float) -> None:
        self._check_edge(u, v)
        if multiplier < 1.0:
            raise ValueError(f"traffic multiplier must be >= 1.0, got {multiplier}")
        self._traffic[edge(u, v)] = float(multiplier)

    def block(self, u: Node, v: Node) -> None:
        self._check_edge(u, v)
        self._blocked.add(edge(u, v))

    def unblock(self, u: Node, v: Node) -> None:
        self._check_edge(u, v)
        self._blocked.discard(edge(u, v))


def make_random_grid(rows: int = 20, cols: int = 20, seed: int = 0,
                     traffic_density: float = 0.2, max_traffic: float = 3.0,
                     blocked_density: float = 0.05) -> GridGraph:
    """Seeded random city. Each edge is blocked, trafficked, or left plain.

    Traffic multipliers are uniform in [1.5, max_traffic], rounded to 1 decimal.
    Blocked takes precedence over traffic.
    """
    if not (0.0 <= traffic_density <= 1.0 and 0.0 <= blocked_density <= 1.0):
        raise ValueError("densities must be in [0, 1]")
    if max_traffic < 1.5:
        raise ValueError("max_traffic must be >= 1.5")
    rng = random.Random(seed)
    graph = GridGraph(rows, cols)
    for u, v in graph.edges():
        # Always draw 3 numbers per edge so one edge never shifts the next.
        blocked_roll = rng.random()
        traffic_roll = rng.random()
        multiplier = round(rng.uniform(1.5, max_traffic), 1)
        if blocked_roll < blocked_density:
            graph.block(u, v)
        elif traffic_roll < traffic_density:
            graph.set_traffic(u, v, multiplier)
    return graph


def random_stops(graph: GridGraph, k: int, seed: int, exclude: list[Node]) -> list[Node]:
    """k distinct random nodes, none in `exclude`. Seeded and deterministic."""
    excluded = set(exclude)
    candidates = [(r, c) for r in range(graph.rows) for c in range(graph.cols)
                  if (r, c) not in excluded]
    if k < 0 or k > len(candidates):
        raise ValueError(f"cannot pick {k} stops from {len(candidates)} candidates")
    return random.Random(seed).sample(candidates, k)
