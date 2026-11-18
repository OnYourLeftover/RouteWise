# SPEC.md — RouteWise (Smart Delivery Route Optimizer)

Single source of truth. Paste into every AI coding session. Nothing here changes without the team lead.

## 1. Scope

A Streamlit app where the user sets a depot and delivery stops on a weighted grid "city", picks A* or Greedy Best-First Search (GBFS) and a heuristic, and sees the route, the nodes each algorithm explored, and a side-by-side comparison.

Three separate layers. Never mix them:
1. **Pathfinding** (A*, GBFS): path between two nodes.
2. **Stop ordering** (nearest neighbor): the order of deliveries.
3. **Comparison**: A* vs GBFS on identical legs.

## 2. Frozen decisions

| Topic | Decision |
|---|---|
| Stack | Python 3.11+, streamlit, matplotlib, pandas, pytest. **No other dependencies.** |
| Graph | Own `GridGraph` class, 4-connected grid, undirected edges. Node = `(row, col)`, `(0, 0)` top-left. Default 20x20. |
| Edge cost | `cost = base_cost * traffic`. Both are **>= 1.0** (enforced). Main app: base = 1.0. Blocked road = edge unavailable. |
| Heuristics | `manhattan`, `euclidean` (admissible and consistent), `inflated_manhattan` = 2 x Manhattan (**inadmissible, demo only**). |
| Stop ordering | Nearest neighbor by **Manhattan distance**, computed **once** and reused for both algorithms. Route = depot -> stops -> depot. |
| Dijkstra | **Tests only** (`tests/reference_dijkstra.py`). Not in `core/`, not selectable in the app. |
| Out of scope | OSMnx / real maps, time windows, 2-opt (2-opt only if Day 5 is ahead and Lead approves). |

## 3. Structure and ownership

```
RouteWise/
├── app.py                  # Member 3
├── core/
│   ├── graph.py            # Lead
│   ├── heuristics.py       # Lead (tiny, frozen Day 1)
│   ├── search.py           # Member 2   (A* and GBFS only)
│   └── multistop.py        # Lead
├── viz.py                  # Member 3
├── tests/
│   ├── reference_dijkstra.py   # Member 2
│   └── test_search.py          # Member 2
├── benchmark.py            # Lead  -> writes data/benchmark_results.csv
├── data/
├── requirements.txt        # Lead
├── SPEC.md  README.md      # Lead
```

You edit only your own files. If you need a change in someone else's file, ask them (or the Lead).

## 4. Graph API (`core/graph.py`)

```python
Node = tuple[int, int]                 # (row, col)
Edge = tuple[Node, Node]               # always normalized: (min(u, v), max(u, v))

def edge(u: Node, v: Node) -> Edge: ...        # normalizer

class GridGraph:
    rows: int
    cols: int
    def __init__(self, rows: int, cols: int, base_cost: dict[Edge, float] | None = None): ...
        # missing edges default to base 1.0; any value < 1.0 -> ValueError
    def in_bounds(self, node: Node) -> bool: ...
    def neighbors(self, node: Node) -> list[tuple[Node, float]]: ...
        # (neighbor, effective_cost); skips blocked/out-of-bounds;
        # FIXED order: up, right, down, left  (determinism)
    def cost(self, u: Node, v: Node) -> float: ...             # effective cost; ValueError if not adjacent/blocked
    def set_traffic(self, u: Node, v: Node, multiplier: float) -> None: ...   # >= 1.0
    def block(self, u: Node, v: Node) -> None: ...
    def unblock(self, u: Node, v: Node) -> None: ...
    def is_blocked(self, u: Node, v: Node) -> bool: ...
    def traffic(self, u: Node, v: Node) -> float: ...
    def edges(self) -> list[Edge]: ...                         # all edges, for drawing

def make_random_grid(rows: int = 20, cols: int = 20, seed: int = 0,
                     traffic_density: float = 0.2, max_traffic: float = 3.0,
                     blocked_density: float = 0.05) -> GridGraph: ...
    # uses random.Random(seed). Traffic multipliers uniform in [1.5, max_traffic], 1 decimal.

def random_stops(graph: GridGraph, k: int, seed: int, exclude: list[Node]) -> list[Node]: ...
```

Blocked roads may disconnect the grid. That is allowed, and `found=False` handles it.

## 5. Heuristics (`core/heuristics.py`)

```python
def manhattan(n: Node, goal: Node) -> float
def euclidean(n: Node, goal: Node) -> float
def inflated_manhattan(n: Node, goal: Node) -> float     # 2 * manhattan
HEURISTICS: dict[str, Callable[[Node, Node], float]] = {
    "manhattan": manhattan, "euclidean": euclidean, "inflated_manhattan": inflated_manhattan }
```

Why the first two are admissible and consistent: every edge costs >= 1, and one grid step changes Manhattan or Euclidean distance by at most 1.

## 6. Search contract (`core/search.py`) — FROZEN

```python
def solve(graph: GridGraph, start: Node, goal: Node, algo: str, heuristic: str) -> dict
# algo: "astar" | "gbfs"      heuristic: key of HEURISTICS
# bad algo / heuristic / out-of-bounds node -> ValueError
```

Return value (exactly these keys):
```python
{
  "found": bool,
  "path": list[Node],          # start..goal inclusive; [] if not found
  "cost": float | None,        # sum of graph.cost along path; None if not found
  "nodes_explored": int,       # == len(explored_order)
  "explored_order": list[Node],# nodes in the order they were EXPANDED (popped from frontier)
  "time_ms": float,            # time.perf_counter() around the whole solve() body
}
```

Rules:
- **start == goal**: `found=True, path=[start], cost=0.0, nodes_explored=0, explored_order=[]`.
- A node is "explored" when popped from the frontier (and not stale). The goal is appended to `explored_order` when popped, then the search returns.
- **A\***: priority `f = g + h`; heap entries `(f, h, counter, ...)` (counter = insertion count, a deterministic tie-break). Lazy deletion of stale entries. **Re-opening allowed**: no closed set that blocks re-expansion when a cheaper g is found (needed for the inadmissible heuristic).
- **GBFS**: priority `h` only; heap entries `(h, counter, ...)`. A visited set: each node is expanded at most once; the parent is set when a node is first discovered. `cost` is recomputed from the returned path.
- Neighbors are always taken in `graph.neighbors()` order.
- No global state. No printing.

## 7. Stop ordering (`core/multistop.py`)

```python
def order_stops(depot: Node, stops: list[Node]) -> list[Node]
# Dedupe stops, drop any equal to depot. Nearest neighbor by Manhattan distance from the
# CURRENT position. Tie-break: (distance, row, col). Ignores traffic and blocked roads (documented limitation).

def plan_route(graph: GridGraph, depot: Node, order: list[Node], algo: str, heuristic: str) -> dict
# Legs: depot->order[0], order[0]->order[1], ..., order[-1]->depot   (len(order)+1 legs)
{
  "route_nodes": [depot, *order, depot],
  "legs": [ {"from": Node, "to": Node, **solve_result}, ... ],
  "complete": bool,              # every leg found
  "total_cost": float | None,    # None if not complete
  "total_nodes_explored": int,
  "total_time_ms": float,
  "full_path": list[Node],       # concatenated found-leg paths, no duplicated joints
}
```

**Fair comparison rule:** call `order_stops` once, then call `plan_route` twice (astar, gbfs) with the same `order`, graph and heuristic.

## 8. Benchmark (`benchmark.py`, Lead)

- Seeds 0..29, 20x20 grid, 5 random stops, `traffic_density=0.2`, `blocked_density=0.05`.
- For each seed x {astar, gbfs} x {manhattan, euclidean}: run `plan_route` 5 times, record the **median** `total_time_ms`.
- CSV `data/benchmark_results.csv`, columns: `seed, algo, heuristic, complete, total_cost, nodes_explored, median_time_ms, gap_pct`.
- `gap_pct` = `(total_cost / astar_manhattan_total_cost - 1) * 100`. The A*+Manhattan result is the optimum reference, so Dijkstra is not needed here.

## 9. UI (`app.py`, `viz.py`, Member 3)

App title (page title and header): **RouteWise**. Sidebar: seed, grid size (10-30), traffic density, blocked density, depot row/col, stop count (1-10), "Randomize stops" button, algorithm (A*/GBFS), heuristic (label `inflated_manhattan` as "inadmissible - demo only"), Run button. Optional (cut first): manual stop list and manual road blocking.

Tabs:
1. **Route**: grid figure with the route, the delivery order numbers, and a **slider over `explored_order`** of a selected leg (this is the step-through, no animation).
2. **Comparison**: A* vs GBFS side by side (same order, same heuristic): total cost, nodes explored, runtime, cost difference vs A*, bar chart.
3. **Benchmark**: load `data/benchmark_results.csv` if it exists and show a summary table (mean/median per algo+heuristic).

Drawing: depot = black square, stops = numbered in visit order, explored = light blue, final path = green, blocked = red dashed, traffic = orange (darker = higher multiplier).

```python
# viz.py
def draw_grid(graph, depot, order, legs=None, explored=None, title="") -> "matplotlib.figure.Figure"
def comparison_chart(plan_astar: dict, plan_gbfs: dict) -> "matplotlib.figure.Figure"
```

## 10. Tests (Member 2)

`tests/reference_dijkstra.py`: `dijkstra(graph, start, goal) -> float | None` (the optimal cost or None).

`tests/test_search.py` must include:
1. **A\* optimality**: on 200 seeded random grids (with traffic and blocked roads), `astar` cost == Dijkstra cost for `manhattan` and `euclidean`. `found` agrees with Dijkstra on unreachable pairs.
2. **GBFS validity**: path starts at start and ends at goal, consecutive nodes are real unblocked edges, the reported cost equals the recomputed sum, and cost >= Dijkstra.
3. **Edge cases**: start == goal, unreachable goal (found False, path [], cost None), out-of-bounds (ValueError), bad algo name (ValueError).
4. **Deterministic inadmissible demo** (two-row grid):

```python
def two_row_graph():
    base = {}
    for c in range(4):
        base[edge((0, c), (0, c + 1))] = 2.0     # top row: cost 2 each
        base[edge((1, c), (1, c + 1))] = 1.0     # bottom row: cost 1 each
    return GridGraph(2, 5, base)                  # vertical edges default to 1.0
# start (0,0), goal (0,4). Optimal = 6 (down, 4 across the bottom, up). Top row = 8.
```

| algo | heuristic | expected cost |
|---|---|---|
| astar | manhattan | 6 |
| astar | euclidean | 6 |
| astar | inflated_manhattan | **8** (top row) |
| gbfs | manhattan | 8 (top row) |
| gbfs | inflated_manhattan | 8, and `explored_order` **identical** to gbfs + manhattan |

## 11. Schedule and gates

| Day | Lead | Member 2 | Member 3 | Gate (end of day) |
|---|---|---|---|---|
| 1 | Repo, this SPEC, `graph.py`, `heuristics.py`, stub `search.py` + `multistop.py` returning valid dummy dicts | Read SPEC, write `reference_dijkstra.py`, test skeleton | Streamlit skeleton + `viz.py` against stubs | Everyone's code runs against stubs |
| 2 | Graph tests, seeded generator | A*, GBFS, tests 1-4 | Grid rendering: route, explored nodes | **All tests pass, or no UI polish** |
| 3 | `order_stops`, `plan_route` | Edge-case tests, bug fixes | Input panel, selectors | Real solver in the app (rough) |
| 4 | Merge, integrate | Support | Wire real results | **End-to-end demo works** |
| 5 | `benchmark.py` | Optional 2-opt (only with Lead approval); viva Q&A notes | Comparison tab, slider, Benchmark tab | Comparison and benchmark done |
| 6 | Report draft | Algorithm section of the report | Polish, screenshots, error states | Feature freeze |
| 7 | README, rehearsal | Rehearsal | Rehearsal | Buffer. Everyone explains any module. |

**Cut order if behind:** 2-opt, then manual stops/blocking UI, then the slider (keep the static explored view), then the Benchmark tab. Never cut: correct A* and GBFS, the fair comparison, the explored-nodes view.

## 12. Git rules

- `main` must always run. Feature branches: `lead/*`, `algo/*`, `ui/*`. Merge to `main` daily, Lead reviews.
- Commit every working state. Run `python -m pytest tests/` before every merge.

## 13. Known limitations (state them in the report)

- Stop ordering uses Manhattan distance, so it ignores traffic and blocked roads. It is not globally optimal.
- Nearest neighbor may pick a stop that is unreachable. Its leg returns `found=False`, and the plan is marked `complete=False`.
- Synthetic grid, not real road data.
- GBFS is not optimal and has no cost guarantee. Its results are measured, not assumed.
