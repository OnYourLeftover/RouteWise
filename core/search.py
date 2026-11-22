"""A* and Greedy Best-First Search on a GridGraph (SPEC.md section 6)."""
from __future__ import annotations

import heapq
import time
from typing import Callable

from core.graph import GridGraph, Node
from core.heuristics import HEURISTICS

_ALGOS = ("astar", "gbfs")
_Heuristic = Callable[[Node, Node], float]
_Parents = dict[Node, Node | None]


def _validate(graph: GridGraph, start: Node, goal: Node,
              algo: str, heuristic: str) -> None:
    """Raise ValueError for a bad algo, bad heuristic, or out-of-bounds node."""
    if algo not in _ALGOS:
        raise ValueError(f"unknown algo {algo!r}, expected one of {_ALGOS}")
    if heuristic not in HEURISTICS:
        raise ValueError(f"unknown heuristic {heuristic!r}")
    for node in (start, goal):
        if not graph.in_bounds(node):
            raise ValueError(f"node {node} is out of bounds")


def _build_path(parent: _Parents, goal: Node) -> list[Node]:
    """Walk parent links back from goal to start, then reverse to start..goal."""
    path: list[Node] = []
    node: Node | None = goal
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()
    return path


def _path_cost(graph: GridGraph, path: list[Node]) -> float:
    """Sum of graph.cost along the path (0.0 for a one-node path)."""
    total = 0.0
    for u, v in zip(path, path[1:]):
        total += graph.cost(u, v)
    return total


def _astar(graph: GridGraph, start: Node, goal: Node,
           h_fn: _Heuristic) -> tuple[list[Node], list[Node]]:
    """A*. Returns (path, explored_order); path is [] if the goal is unreachable.

    Heap entries are (f, h, counter, node, g). The counter is unique, so Python
    never has to compare nodes. There is no closed set: if a cheaper g to a node
    is found later, the node is pushed again and may be expanded again
    (re-opening). Older, costlier entries are skipped when popped (lazy deletion).
    """
    best_g: dict[Node, float] = {start: 0.0}
    parent: _Parents = {start: None}
    explored: list[Node] = []
    counter = 0
    h_start = h_fn(start, goal)
    frontier = [(h_start, h_start, counter, start, 0.0)]
    while frontier:
        _f, _h, _count, node, g = heapq.heappop(frontier)
        if g > best_g[node]:
            continue  # stale entry: a cheaper g for this node was pushed later
        explored.append(node)
        if node == goal:
            return _build_path(parent, goal), explored
        for neighbor, step_cost in graph.neighbors(node):
            new_g = g + step_cost
            if neighbor not in best_g or new_g < best_g[neighbor]:
                best_g[neighbor] = new_g
                parent[neighbor] = node
                h = h_fn(neighbor, goal)
                counter += 1
                heapq.heappush(frontier, (new_g + h, h, counter, neighbor, new_g))
    return [], explored


def _gbfs(graph: GridGraph, start: Node, goal: Node,
          h_fn: _Heuristic) -> tuple[list[Node], list[Node]]:
    """Greedy best-first. Returns (path, explored_order); [] if unreachable.

    Priority is h only. A node is marked visited (and gets its parent) the first
    time it is discovered, so it is pushed once and therefore expanded at most once.
    """
    parent: _Parents = {start: None}
    visited = {start}
    explored: list[Node] = []
    counter = 0
    frontier = [(h_fn(start, goal), counter, start)]
    while frontier:
        _h, _count, node = heapq.heappop(frontier)
        explored.append(node)
        if node == goal:
            return _build_path(parent, goal), explored
        for neighbor, _step_cost in graph.neighbors(node):
            if neighbor not in visited:
                visited.add(neighbor)
                parent[neighbor] = node
                counter += 1
                heapq.heappush(frontier, (h_fn(neighbor, goal), counter, neighbor))
    return [], explored


def solve(graph: GridGraph, start: Node, goal: Node, algo: str, heuristic: str) -> dict:
    """Find a path from start to goal with A* ("astar") or GBFS ("gbfs").

    Returns the dict described in SPEC.md section 6. Raises ValueError for a bad
    algo, bad heuristic, or out-of-bounds node.
    """
    t0 = time.perf_counter()
    _validate(graph, start, goal, algo, heuristic)
    if start == goal:
        path: list[Node] = [start]
        explored: list[Node] = []
    else:
        search = _astar if algo == "astar" else _gbfs
        path, explored = search(graph, start, goal, HEURISTICS[heuristic])
    found = len(path) > 0
    # Cost is always recomputed from the final path, so it matches the path exactly.
    cost = _path_cost(graph, path) if found else None
    return {
        "found": found,
        "path": path,
        "cost": cost,
        "nodes_explored": len(explored),
        "explored_order": explored,
        "time_ms": (time.perf_counter() - t0) * 1000.0,
    }