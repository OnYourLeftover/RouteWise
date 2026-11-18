"""STUB - replaced by Member 2 (Sneha, Role B). Do not build on this logic."""
from __future__ import annotations

from core.graph import GridGraph, Node


def solve(graph: GridGraph, start: Node, goal: Node, algo: str, heuristic: str) -> dict:
    """Dummy result with the exact SPEC.md section 6 keys (an L-shaped path)."""
    path = [start]
    r, c = start
    while r != goal[0]:
        r += 1 if goal[0] > r else -1
        path.append((r, c))
    while c != goal[1]:
        c += 1 if goal[1] > c else -1
        path.append((r, c))
    return {
        "found": True,
        "path": path,
        "cost": float(len(path) - 1),
        "nodes_explored": len(path),
        "explored_order": list(path),
        "time_ms": 0.0,
    }
