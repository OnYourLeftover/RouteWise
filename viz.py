"""
viz.py - Role C (UI & Visualization), Smart Delivery Route Optimizer

Follows SPEC.md section 9. Both functions return a Matplotlib Figure for display.

    draw_grid(graph, depot, order, legs=None, explored=None, title="")
    comparison_chart(plan_astar, plan_gbfs)

Data used (from SPEC.md):
  graph     : GridGraph  -> rows, cols, edges(), is_blocked(u, v), traffic(u, v)
  Node      : (row, col), (0, 0) is the TOP-LEFT corner
  order     : list[Node], stops in visit order (from order_stops)
  legs      : plan_route(...)["legs"], each leg dict has "path" and "found"
  explored  : list[Node], e.g. a leg's "explored_order" (or a slice of it for the slider)
  plan_*    : plan_route(...) dicts with "total_cost" (float | None),
              "total_nodes_explored" (int) and "total_time_ms" (float)
"""

import re
from collections.abc import Collection
from io import StringIO

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from core.graph import GridGraph, Node

# ---------------------------------------------------------------------------
# Chart palette
# ---------------------------------------------------------------------------
BG = "#FFFFFF"
PANEL = "#F3F7FA"
DEPOT = "#10151E"
DEPOT_BORDER = "#CBD5E1"
STOP = "#6741A3"
EXPLORED = "#137BA6"
ROUTE = "#078255"
BLOCKED = "#C33C4B"
TRAFFIC_LOW = "#E18D31"
TRAFFIC_HIGH = "#A34912"
TEXT = "#15283B"
SUBTEXT = "#526479"
ROAD = "#C9D4DF"

ASTAR_COLOR = "#126F79"
GBFS_COLOR = "#AC571E"

_DARK_COLORS = {
    BG: "#101827",
    PANEL: "#1E293B",
    TEXT: "#F8FAFC",
    SUBTEXT: "#A7B6C8",
    ROAD: "#475569",
    DEPOT_BORDER: "#F8FAFC",
    STOP: "#B9A4FA",
    EXPLORED: "#53C7EB",
    ROUTE: "#4ADE80",
    BLOCKED: "#F87171",
    ASTAR_COLOR: "#56C8C1",
    GBFS_COLOR: "#FB923C",
}
_DARK_COLORS = {light.lower(): dark for light, dark in _DARK_COLORS.items()}
_SVG_COLOR = re.compile(r"(fill|stroke): (#[0-9a-f]{6})\b")


def themed_svg(fig: Figure) -> str:
    """Serialize a figure that follows the embedding page's color scheme."""
    with StringIO() as output:
        fig.savefig(output, format="svg", metadata={"Date": None})
        svg = output.getvalue()

    def adaptive_color(match: re.Match[str]) -> str:
        property_name, light = match.groups()
        if light in _DARK_COLORS:
            return f"{property_name}: var(--routewise-{light[1:]}, {light})"
        return match[0]

    svg = _SVG_COLOR.sub(adaptive_color, svg)
    colors = "".join(f"--routewise-{light[1:]}: {dark};" for light, dark in _DARK_COLORS.items())
    style = f"<style>@media (prefers-color-scheme: dark) {{ :root {{ {colors} }} }}</style>"
    root_end = svg.index(">", svg.index("<svg")) + 1
    return svg[:root_end] + style + svg[root_end:]


def _xy(node: tuple[int, int]) -> tuple[int, int]:
    """(row, col) -> (x, y) for plotting. x = column, y = row."""
    row, col = node
    return col, row


def _traffic_level(multiplier: float, lowest: float, highest: float) -> float:
    """0.0 for the lightest traffic on the map, 1.0 for the heaviest."""
    if highest <= lowest:
        return 0.0
    return (multiplier - lowest) / (highest - lowest)


def _traffic_color(level: float) -> tuple[float, float, float]:
    """Blend light orange (level 0) -> dark orange (level 1)."""
    low, high = to_rgb(TRAFFIC_LOW), to_rgb(TRAFFIC_HIGH)
    return tuple(a + (b - a) * level for a, b in zip(low, high))


# ---------------------------------------------------------------------------
# Function 1: grid figure
# ---------------------------------------------------------------------------
def draw_grid(graph: GridGraph, depot: Node, order: list[Node],
              legs: list[dict] | None = None, explored: list[Node] | None = None,
              title: str = "", *, active_leg: int | None = None, show_all_legs: bool = True,
              unreachable_stops: Collection[Node] = ()) -> Figure:
    """Draw the grid city with roads, explored nodes, route, stops and depot."""
    rows, cols = graph.rows, graph.cols

    fig = Figure(figsize=(7, 7))
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)

    # Marker and line sizes shrink as the grid grows (SPEC: 10x10 to 30x30).
    # cell = width of one grid cell in points (about 6 inches of drawing area).
    cell = 6.0 * 72 / max(rows, cols)
    stop_size = (0.8 * cell) ** 2       # scatter "s" is in points squared
    explored_size = (0.5 * cell) ** 2
    route_width = max(1.5, 0.18 * cell)
    number_font = max(6, min(11, 0.42 * cell))

    # --- 1. Roads: normal, traffic, blocked ----------------------------------
    all_edges = graph.edges()
    open_segments, blocked_segments, traffic_segments, multipliers = [], [], [], []
    for u, v in all_edges:
        segment = (_xy(u), _xy(v))
        if graph.is_blocked(u, v):
            blocked_segments.append(segment)
            continue

        multiplier = graph.traffic(u, v)
        if multiplier > 1.0:
            traffic_segments.append(segment)
            multipliers.append(multiplier)
        else:
            open_segments.append(segment)

    ax.add_collection(LineCollection(open_segments, colors=ROAD, linewidths=0.75, zorder=1))
    if multipliers:
        lowest, highest = min(multipliers), max(multipliers)
        levels = [_traffic_level(multiplier, lowest, highest) for multiplier in multipliers]
        ax.add_collection(LineCollection(
            traffic_segments, colors=[_traffic_color(level) for level in levels],
            linewidths=[max(1.3, (0.06 + 0.08 * level) * cell) for level in levels],
            capstyle="round", zorder=2,
        ))
    ax.add_collection(LineCollection(blocked_segments, colors=BLOCKED, linestyles="--",
                                     linewidths=max(0.95, 0.065 * cell), zorder=2))

    # --- 2. Explored nodes ---------------------------------------------------
    if explored:
        points = [_xy(n) for n in explored]
        ax.scatter([p[0] for p in points], [p[1] for p in points],
                   s=explored_size, color=EXPLORED, alpha=0.55,
                   edgecolors="none", zorder=3)
        ax.scatter(*points[-1], s=1.5 * explored_size, facecolors="none", edgecolors=EXPLORED,
                   linewidths=1.6, zorder=5)

    # --- 3. Final route: the path of every leg that was found ----------------
    route_style = "--" if unreachable_stops else "-"
    for index, leg in enumerate(legs or []):
        if not leg["found"] or not leg["path"]:
            continue
        highlight = active_leg is None or index == active_leg
        if not (show_all_legs or highlight):
            continue
        x, y = zip(*map(_xy, leg["path"]))
        ax.plot(x, y, color=ROUTE, linestyle=route_style,
                linewidth=route_width if highlight else 0.7 * route_width,
                alpha=1 if highlight else 0.55, solid_capstyle="round", zorder=4 if highlight else 3.5)

    # --- 4. Delivery stops, numbered in visit order --------------------------
    for number, stop in enumerate(order, start=1):
        x, y = _xy(stop)
        unreachable = stop in unreachable_stops
        ax.scatter(x, y, s=stop_size, marker="D" if unreachable else "o",
                   color=BG if unreachable else STOP, edgecolors=BLOCKED if unreachable else BG,
                   linewidths=1.2, zorder=6)
        ax.text(x, y, str(number), color=BLOCKED if unreachable else BG, fontsize=number_font,
                fontweight="bold", ha="center", va="center", zorder=6)

    # --- 5. Depot: black square with a white border --------------------------
    x, y = _xy(depot)
    ax.scatter(x, y, s=stop_size, marker="s", color=DEPOT, edgecolors=DEPOT_BORDER,
               linewidths=1.8, zorder=6)

    # --- 6. Axes: (0, 0) at the top-left, labels, boundary -------------------
    ax.set_xlim(-0.5, cols - 0.5)
    ax.set_ylim(rows - 0.5, -0.5)     # reversed so row 0 is at the top
    ax.set_aspect("equal")

    ax.set_xticks(range(0, cols, 2 if cols > 20 else 1))
    ax.set_yticks(range(0, rows, 2 if rows > 20 else 1))
    tick_font = 10 if max(rows, cols) <= 20 else 8
    ax.tick_params(colors=SUBTEXT, labelsize=tick_font, length=3)
    ax.xaxis.tick_top()               # column numbers above the grid, like a table
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("Column", color=TEXT, fontsize=11, labelpad=8)
    ax.set_ylabel("Row", color=TEXT, fontsize=11, labelpad=8)

    for spine in ax.spines.values():  # the frame is the grid boundary
        spine.set_color(ROAD)
        spine.set_linewidth(1)

    if title:
        fig.suptitle(title, color=TEXT, fontsize=15, fontweight="bold", y=0.98)

    handles = [
        Line2D([], [], marker="s", linestyle="", markersize=8,
               markerfacecolor=DEPOT, markeredgecolor=DEPOT_BORDER, label="Depot"),
        Line2D([], [], marker="o", linestyle="", markersize=8,
               markerfacecolor=STOP, markeredgecolor=BG, label="Numbered stop"),
        Line2D([], [], marker="o", linestyle="", markersize=8,
               markerfacecolor=EXPLORED, markeredgecolor="none",
               label="Explored"),
        Line2D([], [], color=ROUTE, linewidth=3, linestyle=route_style,
               label="Partial leg" if unreachable_stops else "Route"),
        Line2D([], [], color=BLOCKED, linewidth=2, linestyle="--",
               label="Blocked road"),
        Line2D([], [], color=TRAFFIC_LOW, linewidth=2, label="Light traffic"),
        Line2D([], [], color=TRAFFIC_HIGH, linewidth=4, label="Heavy traffic"),
    ]
    if unreachable_stops:
        handles.append(Line2D([], [], marker="D", linestyle="", markersize=8,
                              markerfacecolor=BG, markeredgecolor=BLOCKED, label="Unreachable stop"))
    fig.legend(handles=handles, loc="lower center", ncols=4, frameon=False,
               labelcolor=TEXT, fontsize=9, columnspacing=1.3, bbox_to_anchor=(0.53, 0.025))
    fig.subplots_adjust(left=0.11, right=0.97, top=0.88 if title else 0.93, bottom=0.13)
    return fig


# ---------------------------------------------------------------------------
# Function 2: A* vs GBFS bar chart
# ---------------------------------------------------------------------------
def comparison_chart(plan_astar: dict, plan_gbfs: dict) -> Figure:
    """
    A* vs GBFS on three metrics: total cost, total nodes explored, total time (ms).

    Each metric gets its own small panel with its own y-axis, because the
    numbers have very different sizes (e.g. 300 nodes vs 2 ms). Inside each
    panel the A* bar and the GBFS bar stand side by side.
    total_cost=None (plan not complete) is shown as "N/A" with no bar.
    """
    metrics = [
        ("Total Route Cost", "total_cost"),
        ("Nodes Explored", "total_nodes_explored"),
        ("Search Time (ms)", "total_time_ms"),
    ]
    names = ["A*", "GBFS"]
    colors = [ASTAR_COLOR, GBFS_COLOR]

    fig = Figure(figsize=(10, 3.8))
    FigureCanvasAgg(fig)
    axes = fig.subplots(1, 3)
    fig.patch.set_facecolor(BG)

    for ax, (label, key) in zip(axes, metrics):
        values = [plan_astar.get(key), plan_gbfs.get(key)]
        heights = [0 if v is None else v for v in values]   # None -> no bar
        top = max(heights) or 1                             # avoid a 0-high axis

        ax.set_facecolor(PANEL)
        ax.bar([0, 1], heights, width=0.6, color=colors, zorder=3)

        # Value label above each bar
        for x, value, height in zip([0, 1], values, heights):
            if value is None:
                text = "N/A"
            elif key == "total_nodes_explored":
                text = f"{value:,}"
            elif key == "total_time_ms":
                text = f"{value:.2f}"
            else:
                text = f"{value:.1f}"
            ax.text(x, height + top * 0.03, text, ha="center", va="bottom",
                    color=TEXT, fontsize=11, fontweight="bold")

        ax.set_title(label, color=TEXT, fontsize=12, fontweight="bold", pad=10)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(names, color=TEXT, fontsize=11)
        ax.set_xlim(-0.6, 1.6)
        ax.set_ylim(0, top * 1.2)
        ax.tick_params(colors=SUBTEXT, labelsize=9)
        ax.yaxis.grid(True, color=ROAD, linewidth=0.8, zorder=0)
        if all(v is None for v in values):
            ax.set_yticks([])   # nothing to measure, so hide the empty scale
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(SUBTEXT)

    fig.tight_layout()
    return fig
