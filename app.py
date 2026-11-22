"""
app.py - RouteWise Streamlit app (SPEC.md section 9). Owned by Member 3 (Srishti, Role C).

Run from the repo root:  streamlit run app.py

Flow on every Run:
  1. build the grid and the stops from the sidebar settings
  2. order_stops ONCE
  3. plan_route TWICE (astar and gbfs) with the same order, graph and heuristic
The Route tab shows the algorithm picked in the sidebar; the Comparison tab shows both.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from matplotlib.figure import Figure

from core.graph import GridGraph, Node, make_random_grid, random_stops
from core.heuristics import HEURISTICS
from core.multistop import order_stops, plan_route
from viz import comparison_chart, draw_grid

BENCHMARK_CSV = Path(__file__).parent / "data" / "benchmark_results.csv"
BENCHMARK_COLUMNS = ["seed", "algo", "heuristic", "complete", "total_cost",
                     "nodes_explored", "median_time_ms", "gap_pct"]

ALGO_LABELS = {"astar": "A*", "gbfs": "GBFS"}
HEURISTIC_LABELS = {
    "manhattan": "manhattan",
    "euclidean": "euclidean",
    "inflated_manhattan": "inflated_manhattan (inadmissible - demo only)",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def show_figure(fig: Figure) -> None:
    """Show a matplotlib figure, then close it so open figures don't pile up."""
    st.pyplot(fig)
    plt.close(fig)


def node_name(node: Node, depot: Node, order: list[Node]) -> str:
    """Readable name for a node: 'Depot (r, c)' or 'Stop 3 (r, c)'."""
    if node == depot:
        return f"Depot {node}"
    return f"Stop {order.index(node) + 1} {node}"


def format_cost(cost: float | None) -> str:
    """Cost with one decimal, or 'N/A' when the route is not complete."""
    return "N/A" if cost is None else f"{cost:.1f}"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def sidebar_settings() -> tuple[dict, bool]:
    """Draw the sidebar. Returns (settings, run_clicked)."""
    st.sidebar.header("Settings")

    seed = int(st.sidebar.number_input("Seed", min_value=0, value=0, step=1))
    size = st.sidebar.slider("Grid size", min_value=10, max_value=30, value=20)
    traffic_density = st.sidebar.slider("Traffic density", 0.0, 0.5, 0.2, 0.05)
    blocked_density = st.sidebar.slider("Blocked density", 0.0, 0.3, 0.05, 0.01)

    # Keep the depot inside the grid when the grid gets smaller.
    for key in ("depot_row", "depot_col"):
        if st.session_state.get(key, 0) > size - 1:
            st.session_state[key] = size - 1
    depot_row = int(st.sidebar.number_input("Depot row", 0, size - 1, 0, key="depot_row"))
    depot_col = int(st.sidebar.number_input("Depot col", 0, size - 1, 0, key="depot_col"))

    stop_count = st.sidebar.slider("Number of stops", min_value=1, max_value=10, value=5)

    # "Randomize stops" only changes the seed used to pick stops (UI state).
    if "stop_seed" not in st.session_state:
        st.session_state.stop_seed = 0
    if st.sidebar.button("Randomize stops"):
        st.session_state.stop_seed += 1

    algo = st.sidebar.radio("Algorithm", list(ALGO_LABELS),
                            format_func=lambda a: ALGO_LABELS[a])
    heuristic = st.sidebar.selectbox("Heuristic", list(HEURISTICS),
                                     format_func=lambda h: HEURISTIC_LABELS.get(h, h))
    run_clicked = st.sidebar.button("Run", type="primary")

    settings = {
        "seed": seed,
        "size": size,
        "traffic_density": traffic_density,
        "blocked_density": blocked_density,
        "depot": (depot_row, depot_col),
        "stop_count": stop_count,
        "stop_seed": st.session_state.stop_seed,
        "algo": algo,
        "heuristic": heuristic,
    }
    return settings, run_clicked


# ---------------------------------------------------------------------------
# Computation (always recomputed from the settings, never cached in session_state)
# ---------------------------------------------------------------------------
def compute(settings: dict) -> tuple[GridGraph, list[Node], dict, dict]:
    """Build the grid, order the stops once, and plan the route with both algorithms."""
    size = settings["size"]
    depot = settings["depot"]
    graph = make_random_grid(rows=size, cols=size, seed=settings["seed"],
                             traffic_density=settings["traffic_density"],
                             blocked_density=settings["blocked_density"])
    stops = random_stops(graph, settings["stop_count"],
                         seed=settings["seed"] + settings["stop_seed"], exclude=[depot])

    # Fair comparison rule (SPEC section 7): one order, two plans.
    order = order_stops(depot, stops)
    heuristic = settings["heuristic"]
    plan_astar = plan_route(graph, depot, order, "astar", heuristic)
    plan_gbfs = plan_route(graph, depot, order, "gbfs", heuristic)
    return graph, order, plan_astar, plan_gbfs


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def route_tab(graph: GridGraph, depot: Node, order: list[Node], plan: dict,
              algo: str, heuristic: str) -> None:
    """Grid with the route, and a slider over explored_order of one leg."""
    if not order:
        st.info("There are no delivery stops. Add stops in the sidebar and press Run.")

    unreachable = [leg for leg in plan["legs"] if not leg["found"]]
    for leg in unreachable:
        st.warning(f"No road connects {node_name(leg['from'], depot, order)} to "
                   f"{node_name(leg['to'], depot, order)} (blocked roads). "
                   "That leg is skipped.")
    if not plan["complete"]:
        st.warning("The route is not complete, so the total cost is N/A.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total cost", format_cost(plan["total_cost"]))
    col2.metric("Nodes explored", plan["total_nodes_explored"])
    col3.metric("Time (ms)", f"{plan['total_time_ms']:.2f}")

    # Pick a leg, then step through the nodes it explored.
    legs = plan["legs"]
    leg_labels = [f"Leg {i + 1}: {node_name(leg['from'], depot, order)} -> "
                  f"{node_name(leg['to'], depot, order)}"
                  + ("" if leg["found"] else "  (unreachable)")
                  for i, leg in enumerate(legs)]
    leg_index = st.selectbox("Leg to step through", range(len(legs)),
                             format_func=lambda i: leg_labels[i])
    explored_order = legs[leg_index]["explored_order"]

    if len(explored_order) > 0:
        step = st.slider("Explored nodes shown", min_value=0,
                         max_value=len(explored_order), value=len(explored_order))
    else:
        step = 0
        st.caption("This leg explored no nodes.")

    title = f"Route ({ALGO_LABELS[algo]}, {heuristic})"
    show_figure(draw_grid(graph, depot, order, legs, explored_order[:step], title))


def comparison_tab(plan_astar: dict, plan_gbfs: dict, heuristic: str) -> None:
    """A* vs GBFS on the same order and heuristic."""
    st.caption(f"Same stop order and heuristic ({heuristic}) for both algorithms.")
    if not (plan_astar["complete"] and plan_gbfs["complete"]):
        st.warning("At least one route is not complete, so some costs are N/A.")

    cost_a, cost_g = plan_astar["total_cost"], plan_gbfs["total_cost"]
    if cost_a is not None and cost_g is not None:
        diff = cost_g - cost_a
        pct = f"{diff / cost_a * 100:+.1f}%" if cost_a > 0 else "N/A"
        diff_text = f"{diff:+.1f} ({pct})"
    else:
        diff_text = "N/A"

    table = pd.DataFrame({
        "Metric": ["Total cost", "Nodes explored", "Runtime (ms)", "Cost difference vs A*"],
        "A*": [format_cost(cost_a), str(plan_astar["total_nodes_explored"]),
               f"{plan_astar['total_time_ms']:.2f}", "0.0"],
        "GBFS": [format_cost(cost_g), str(plan_gbfs["total_nodes_explored"]),
                 f"{plan_gbfs['total_time_ms']:.2f}", diff_text],
    })
    st.dataframe(table, hide_index=True, width="stretch")
    show_figure(comparison_chart(plan_astar, plan_gbfs))


def benchmark_tab() -> None:
    """Summary of data/benchmark_results.csv, if the file exists yet."""
    if not BENCHMARK_CSV.exists():
        st.info("No benchmark results yet. Run `python benchmark.py` to create "
                "data/benchmark_results.csv, then reload this page.")
        return

    try:
        df = pd.read_csv(BENCHMARK_CSV)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as error:
        st.warning(f"Could not read the benchmark file: {error}")
        return

    missing = [c for c in BENCHMARK_COLUMNS if c not in df.columns]
    if missing:
        st.warning(f"The benchmark file is missing columns: {', '.join(missing)}")
        return
    if df.empty:
        st.info("The benchmark file has no rows yet.")
        return

    # Mean and median per algorithm + heuristic (costs of incomplete runs are blank).
    summary = (df.groupby(["algo", "heuristic"])
                 [["total_cost", "nodes_explored", "median_time_ms", "gap_pct"]]
                 .agg(["mean", "median"])
                 .round(2))
    summary.columns = [f"{metric} ({stat})" for metric, stat in summary.columns]
    summary.insert(0, "runs", df.groupby(["algo", "heuristic"]).size())
    st.dataframe(summary, width="stretch")

    with st.expander("All rows"):
        st.dataframe(df, hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="RouteWise", layout="wide")
    st.title("RouteWise")

    settings, run_clicked = sidebar_settings()

    # Only the settings of the last Run are kept (UI state); results are recomputed.
    if run_clicked:
        st.session_state.run_settings = settings
    run_settings = st.session_state.get("run_settings")

    route, comparison, benchmark = st.tabs(["Route", "Comparison", "Benchmark"])

    if run_settings is None:
        route.info("Choose settings in the sidebar and press Run.")
        comparison.info("Choose settings in the sidebar and press Run.")
    else:
        if run_settings != settings:
            st.caption("Settings changed. Press Run to update the results.")
        try:
            graph, order, plan_astar, plan_gbfs = compute(run_settings)
        except ValueError as error:
            route.error(f"Could not plan the route: {error}")
            comparison.error(f"Could not plan the route: {error}")
        else:
            algo, heuristic = run_settings["algo"], run_settings["heuristic"]
            plan = plan_astar if algo == "astar" else plan_gbfs
            with route:
                route_tab(graph, run_settings["depot"], order, plan, algo, heuristic)
            with comparison:
                comparison_tab(plan_astar, plan_gbfs, heuristic)

    with benchmark:
        benchmark_tab()


main()
