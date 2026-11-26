"""
app.py - RouteWise Streamlit app (SPEC.md section 9). Owned by Member 3 (Srishti, Role C).

Run from the repo root:  streamlit run app.py

Flow when Run is pressed:
  1. build the grid and the stops from the sidebar settings
  2. order_stops ONCE
  3. plan_route TWICE (astar and gbfs) with the same order, graph and heuristic
The Route tab switches between the saved results; the Comparison tab shows both.
"""

from io import BytesIO
from math import isclose
from pathlib import Path
from typing import NamedTuple

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
    "manhattan": "Manhattan",
    "euclidean": "Euclidean",
    "inflated_manhattan": "Inflated Manhattan (inadmissible, demo only)",
}
DEFAULT_SCENARIO = {
    "seed": 0,
    "size": 20,
    "traffic_density": 0.2,
    "blocked_density": 0.05,
    "depot_row": 0,
    "depot_col": 0,
    "stop_count": 5,
    "stop_seed": 0,
    "heuristic": "manhattan",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def show_figure(fig: Figure) -> None:
    """Render a figure at a readable size without relying on pyplot state."""
    with BytesIO() as png:
        fig.savefig(png, format="png", dpi=120)
        st.image(png.getvalue(), width="stretch")


def node_name(node: Node, depot: Node, order: list[Node]) -> str:
    """Return the depot label or the numbered stop name."""
    if node == depot:
        return "Depot"
    return f"Stop {order.index(node) + 1}"


def format_cost(cost: float | None) -> str:
    """Cost with one decimal, or 'N/A' when the route is not complete."""
    return "N/A" if cost is None else f"{cost:.1f}"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def load_preset(**overrides) -> None:
    st.session_state.update({**DEFAULT_SCENARIO, **overrides})


def sidebar_settings() -> tuple[dict, str, bool]:
    """Return the scenario settings, displayed algorithm, and Run state."""
    st.sidebar.header("Scenario")
    for key, value in DEFAULT_SCENARIO.items():
        st.session_state.setdefault(key, value)

    run_clicked = st.sidebar.button("Run", type="primary", width="stretch")
    algo = st.sidebar.radio("Algorithm", list(ALGO_LABELS), horizontal=True,
                            format_func=ALGO_LABELS.__getitem__,
                            help="Choose which result the Route tab displays.")
    st.sidebar.divider()

    with st.sidebar.expander("Demo presets"):
        st.button("Disconnected depot", on_click=load_preset,
                  kwargs={"seed": 1, "size": 10, "blocked_density": 0.3})
        st.button("Inflated A*", on_click=load_preset,
                  kwargs={"seed": 12, "heuristic": "inflated_manhattan"})
        st.caption("Load a preset, then press Run.")

    seed = int(st.sidebar.number_input("Seed", min_value=0, step=1, key="seed",
                                      help="Reuse this seed to recreate a city."))
    size = st.sidebar.slider("Grid size", min_value=10, max_value=30, key="size")
    traffic_density = st.sidebar.slider("Traffic density", 0.0, 0.5, step=0.05, key="traffic_density",
                                        help="Chance of traffic on an open road.")
    blocked_density = st.sidebar.slider("Blocked density", 0.0, 0.3, step=0.01, key="blocked_density",
                                        help="Chance that a road is closed.")

    # Keep the depot inside the grid when the grid gets smaller.
    depot_inputs = st.sidebar.columns(2)
    for key in ("depot_row", "depot_col"):
        if st.session_state[key] >= size:
            st.session_state[key] = size - 1
    depot_row = int(depot_inputs[0].number_input("Depot row", 0, size - 1, key="depot_row"))
    depot_col = int(depot_inputs[1].number_input("Depot col", 0, size - 1, key="depot_col"))

    stop_count = st.sidebar.slider("Number of stops", min_value=1, max_value=10, key="stop_count")

    # "Randomize stops" only changes the seed used to pick stops (UI state).
    if st.sidebar.button("Randomize stops", help="Keep this city and draw a new set of stops."):
        st.session_state.stop_seed += 1

    heuristic = st.sidebar.selectbox("Heuristic", list(HEURISTICS), key="heuristic",
                                     format_func=HEURISTIC_LABELS.__getitem__)

    settings = {
        "seed": seed,
        "size": size,
        "traffic_density": traffic_density,
        "blocked_density": blocked_density,
        "depot": (depot_row, depot_col),
        "stop_count": stop_count,
        "stop_seed": st.session_state.stop_seed,
        "heuristic": heuristic,
    }
    return settings, algo, run_clicked


# ---------------------------------------------------------------------------
# Route computation
# ---------------------------------------------------------------------------
class RouteResults(NamedTuple):
    graph: GridGraph
    order: list[Node]
    astar: dict
    gbfs: dict
    unreachable: set[Node]


def compute(settings: dict) -> RouteResults:
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
    unreachable = set()
    if not plan_astar["complete"]:
        reachable = {depot}
        pending = [depot]
        while pending:
            for neighbor, _ in graph.neighbors(pending.pop()):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    pending.append(neighbor)
        unreachable = set(order) - reachable
    return RouteResults(graph, order, plan_astar, plan_gbfs, unreachable)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
@st.fragment
def route_tab(result: RouteResults, scenario: dict, algo: str) -> None:
    """Show the saved trip and let users inspect one leg at a time."""
    depot, order = scenario["depot"], result.order
    plan = result.astar if algo == "astar" else result.gbfs
    legs = plan["legs"]
    leg_names = [(node_name(leg["from"], depot, order), node_name(leg["to"], depot, order))
                 for leg in legs]

    st.subheader(f"{ALGO_LABELS[algo]} route")
    scenario_details = [f"{result.graph.rows} × {result.graph.cols} grid",
                        f"Seed {scenario['seed']}", f"{len(order)} stops",
                        HEURISTIC_LABELS[scenario["heuristic"]]]
    if scenario["stop_seed"]:
        scenario_details.append(f"Stop seed {scenario['seed'] + scenario['stop_seed']}")
    st.caption(" · ".join(scenario_details))
    if not plan["complete"]:
        names = ", ".join(node_name(stop, depot, order) for stop in order
                          if stop in result.unreachable)
        st.warning(f"**Route incomplete.** Unreachable from the depot: {names}. "
                   "Dashed green lines show individual legs with a path.")

    col1, col2, col3 = st.columns(3, border=True)
    col1.metric("Total cost", format_cost(plan["total_cost"]),
                help="Sum of road costs, including traffic, for the round trip.")
    col2.metric("Nodes explored", plan["total_nodes_explored"],
                help="Total search expansions across all legs.")
    col3.metric("Search time (ms)", f"{plan['total_time_ms']:.2f}",
                help="Time spent finding paths for the legs.")

    map_column, inspector = st.columns([3, 2], gap="large", border=True)
    with inspector:
        st.markdown("**Inspect a leg**")
        labels = [f"{i + 1} · {start} → {end}" + ("" if leg["found"] else " (unreachable)")
                  for i, ((start, end), leg) in enumerate(zip(leg_names, legs))]
        leg_index = st.selectbox("Leg to step through", range(len(legs)), key="route_leg",
                                 format_func=labels.__getitem__)
        leg = legs[leg_index]
        explored_order = leg["explored_order"]
        st.caption(f"{leg['from']} → {leg['to']} · Cost {format_cost(leg['cost'])} · "
                   f"{leg['nodes_explored']} explored")
        step = 0
        if explored_order:
            step = st.slider("Explored nodes shown", min_value=0, max_value=len(explored_order),
                             value=len(explored_order), key=f"step_{algo}_{leg_index}")
        else:
            st.caption("This leg explored no nodes.")
        show_all = st.checkbox("Show other legs", value=True)
        with st.expander("Full itinerary"):
            itinerary = pd.DataFrame({
                "Leg": [f"{start} → {end}" for start, end in leg_names],
                "Cost": [format_cost(item["cost"]) for item in legs],
                "Status": ["Path found" if item["found"] else "Unreachable" for item in legs],
            })
            st.dataframe(itinerary, hide_index=True, width="stretch")

    with map_column:
        st.markdown("**Delivery grid**")
        show_figure(draw_grid(result.graph, depot, order, legs, explored_order[:step],
                              active_leg=leg_index, show_all_legs=show_all,
                              unreachable_stops=result.unreachable))


def comparison_tab(plan_astar: dict, plan_gbfs: dict, heuristic: str) -> None:
    """Compare path searches on the same stop order and road network."""
    st.subheader("A* vs Greedy Best-First Search")
    st.caption("Both algorithms search the same roads between stops in the same order. "
               "The visit order is chosen separately by nearest Manhattan distance.")
    st.caption(f"Heuristic for this run · {HEURISTIC_LABELS[heuristic]}")
    if heuristic == "inflated_manhattan":
        st.info("Inflated Manhattan can make A* miss the lowest-cost path. "
                "The cost difference uses the A* result from this run as its reference.")
    if not (plan_astar["complete"] and plan_gbfs["complete"]):
        st.warning("The stop order includes unreachable legs. Search metrics include attempts "
                   "on those legs, and trip cost is unavailable.")

    cost_a, cost_g = plan_astar["total_cost"], plan_gbfs["total_cost"]
    diff_text = "N/A"
    if cost_a is not None and cost_g is not None and isclose(cost_a, cost_g, abs_tol=1e-9):
        diff_text = "0.0 (0.0%)"
    elif cost_a is not None and cost_g is not None:
        diff = cost_g - cost_a
        pct = f"{diff / cost_a * 100:+.1f}%" if cost_a > 0 else "N/A"
        diff_text = f"{diff:+.1f} ({pct})"

    table = pd.DataFrame({
        "Metric": ["Total cost", "Nodes explored", "Search time (ms)", "Cost difference vs A*"],
        "A*": [format_cost(cost_a), str(plan_astar["total_nodes_explored"]),
               f"{plan_astar['total_time_ms']:.2f}", "0.0" if cost_a is not None else "N/A"],
        "GBFS": [format_cost(cost_g), str(plan_gbfs["total_nodes_explored"]),
                 f"{plan_gbfs['total_time_ms']:.2f}", diff_text],
    })
    show_figure(comparison_chart(plan_astar, plan_gbfs))
    st.dataframe(table, hide_index=True, width="stretch")


@st.cache_data(show_spinner=False)
def read_benchmark(content: bytes) -> pd.DataFrame:
    return pd.read_csv(BytesIO(content))


def benchmark_tab() -> None:
    """Summary of data/benchmark_results.csv, if the file exists yet."""
    st.subheader("Benchmark results")
    try:
        df = read_benchmark(BENCHMARK_CSV.read_bytes())
    except FileNotFoundError:
        st.info("No benchmark results yet. Run `python benchmark.py` to create "
                "data/benchmark_results.csv, then reload this page.")
        return

    except (OSError, UnicodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
        st.warning(f"Could not read the benchmark file: {error}")
        return

    missing = [c for c in BENCHMARK_COLUMNS if c not in df.columns]
    if missing:
        st.warning(f"The benchmark file is missing columns: {', '.join(missing)}")
        return
    if df.empty:
        st.info("The benchmark file has no rows yet.")
        return

    metrics = ["total_cost", "nodes_explored", "median_time_ms", "gap_pct"]
    try:
        df[metrics] = df[metrics].apply(pd.to_numeric)
    except (ValueError, TypeError):
        st.warning("The benchmark file contains invalid numeric values.")
        return

    st.caption(f"{df['seed'].nunique()} seeded 20 × 20 cities · 5 stops per city · "
               "20% traffic density · 5% blocked-road probability")
    st.markdown("Cost gaps use **A* with Manhattan** as the reference on each city’s fixed stop order. "
                "Search time is the median of five trials per city and configuration.")
    groups = df.assign(completed=df["complete"].astype(str).str.lower().eq("true")).groupby(
        ["algo", "heuristic"], sort=False,
    )
    summary = groups[metrics].agg(["mean", "median"]).round(2)
    summary.columns = [f"{metric} ({stat})" for metric, stat in summary.columns]
    summary.insert(0, "runs", groups.size())
    summary.insert(1, "completed", groups["completed"].sum())
    overview = summary[["completed", "runs", "nodes_explored (median)",
                        "median_time_ms (median)", "gap_pct (mean)"]].reset_index()
    overview["algo"] = overview["algo"].replace(ALGO_LABELS)
    overview["heuristic"] = overview["heuristic"].replace(HEURISTIC_LABELS)
    overview.columns = ["Algorithm", "Heuristic", "Completed", "Runs", "Median nodes",
                        "Median search time (ms)", "Mean cost gap (%)"]
    st.dataframe(overview, hide_index=True, width="stretch")

    with st.expander("Detailed statistics"):
        st.dataframe(summary, width="stretch")
    with st.expander("All benchmark rows"):
        st.dataframe(df, hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def main() -> None:
    """Keep the most recent successful run available during inspection."""
    st.set_page_config(page_title="RouteWise", layout="wide")
    st.title("RouteWise")
    st.caption("Explore delivery routes through traffic and road closures with A* and Greedy Best-First Search.")

    settings, algo, run_clicked = sidebar_settings()
    route, comparison, benchmark = st.tabs(["Route", "Comparison", "Benchmark"])

    if run_clicked:
        try:
            st.session_state.last_run = (settings, compute(settings))
            st.session_state.pop("route_leg", None)
        except ValueError as error:
            route.error(f"Could not plan the route: {error}")
            comparison.error(f"Could not plan the route: {error}")

    if "last_run" not in st.session_state:
        route.info("Choose settings in the sidebar and press Run.")
        comparison.info("Choose settings in the sidebar and press Run.")
    else:
        run_settings, result = st.session_state.last_run
        if run_settings != settings:
            message = "Showing the last run. Press Run to apply your settings."
            route.info(message)
            comparison.info(message)
        with route:
            route_tab(result, run_settings, algo)
        with comparison:
            comparison_tab(result.astar, result.gbfs, run_settings["heuristic"])

    with benchmark:
        benchmark_tab()


main()
