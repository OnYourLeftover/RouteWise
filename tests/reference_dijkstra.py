# Owned by Member 2 (Sneha, Role B). Placeholder - replace.
"""Reference Dijkstra. FOR TESTS ONLY: used to check A* and GBFS (SPEC.md section 10)."""
from __future__ import annotations

import heapq

from core.graph import GridGraph, Node


def dijkstra(graph: GridGraph, start: Node, goal: Node) -> float | None:
    """Optimal path cost from start to goal, or None if goal is unreachable."""
    best: dict[Node, float] = {start: 0.0}   # cheapest known cost to each node
    frontier: list[tuple[float, Node]] = [(0.0, start)]
    while frontier:
        dist, node = heapq.heappop(frontier)
        if dist > best[node]:
            continue  # stale entry: a cheaper route to this node was found later
        if node == goal:
            return dist
        for neighbor, step_cost in graph.neighbors(node):
            new_dist = dist + step_cost
            if neighbor not in best or new_dist < best[neighbor]:
                best[neighbor] = new_dist
                heapq.heappush(frontier, (new_dist, neighbor))
    return None