"""Stop ordering and multi-leg route planning (SPEC.md section 7)."""
from __future__ import annotations

from core.graph import GridGraph, Node
from core.heuristics import manhattan
from core.search import solve


def order_stops(depot: Node, stops: list[Node]) -> list[Node]:
    """Nearest neighbor by Manhattan distance from the CURRENT position.

    Duplicates and the depot are dropped. Ties are broken by (distance, row, col).
    Ignores traffic and blocked roads (documented limitation).
    """
    remaining = set(stops) - {depot}
    current = depot
    order: list[Node] = []
    while remaining:
        # (distance, row, col) tuple gives the required tie-break.
        nxt = min(remaining, key=lambda s: (manhattan(current, s), s[0], s[1]))
        order.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return order


def plan_route(graph: GridGraph, depot: Node, order: list[Node],
               algo: str, heuristic: str) -> dict:
    """Solve depot -> order[0] -> ... -> order[-1] -> depot, one leg at a time."""
    route_nodes = [depot, *order, depot]
    legs = []
    for a, b in zip(route_nodes, route_nodes[1:]):
        legs.append({"from": a, "to": b, **solve(graph, a, b, algo, heuristic)})

    complete = all(leg["found"] for leg in legs)

    full_path: list[Node] = []
    for leg in legs:
        if not leg["found"]:
            continue  # unreachable leg contributes no path
        path = leg["path"]
        if full_path and full_path[-1] == path[0]:
            path = path[1:]  # avoid duplicating the joint node
        full_path.extend(path)

    return {
        "route_nodes": route_nodes,
        "legs": legs,
        "complete": complete,
        "total_cost": sum(leg["cost"] for leg in legs) if complete else None,
        "total_nodes_explored": sum(leg["nodes_explored"] for leg in legs),
        "total_time_ms": sum(leg["time_ms"] for leg in legs),
        "full_path": full_path,
    }
