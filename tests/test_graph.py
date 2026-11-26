"""The search hot path follows the same costs and closures as the graph API."""

from core.graph import GridGraph


def test_neighbors_keep_direction_order_and_reflect_road_updates():
    center = (1, 1)
    up, right, down, left = (0, 1), (1, 2), (2, 1), (1, 0)
    graph = GridGraph(3, 3, {(right, center): 2.0})
    graph.set_traffic(right, center, 1.5)
    graph.block(down, center)

    assert graph.neighbors(center) == [(up, 1.0), (right, 3.0), (left, 1.0)]
    assert graph.cost(center, right) == graph.cost(right, center) == 3.0

    graph.unblock(center, down)
    assert graph.neighbors(center) == [(up, 1.0), (right, 3.0), (down, 1.0), (left, 1.0)]
