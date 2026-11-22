"""
viz.py - Role C (UI & Visualization), Smart Delivery Route Optimizer

Follows SPEC.md section 9. Both functions return a matplotlib Figure, which
app.py can show with st.pyplot(fig).

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

import matplotlib

matplotlib.use("Agg")  # draw off-screen (works in Streamlit and on servers)

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

# ---------------------------------------------------------------------------
# Colour theme (Dark Tech)
# ---------------------------------------------------------------------------
BG = "#101827"            # main background
PANEL = "#1E293B"         # grid / panel background
DEPOT = "#000000"         # depot fill (drawn with a white border)
STOP = "#A78BFA"          # delivery stops
EXPLORED = "#38BDF8"      # explored nodes
ROUTE = "#22C55E"         # final route
BLOCKED = "#EF4444"       # blocked roads
TRAFFIC_LOW = "#F97316"   # light traffic
TRAFFIC_HIGH = "#C2410C"  # heavy traffic
TEXT = "#F8FAFC"          # main text
SUBTEXT = "#94A3B8"       # secondary text
ROAD = "#334155"          # normal road lines (a little lighter than PANEL)

# Bar colours in the comparison chart (as in the reference image)
ASTAR_COLOR = EXPLORED
GBFS_COLOR = TRAFFIC_LOW


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
def draw_grid(graph, depot, order, legs=None, explored=None, title="") -> Figure:
    """Draw the grid city with roads, explored nodes, route, stops and depot."""
    rows, cols = graph.rows, graph.cols

    fig, ax = plt.subplots(figsize=(10, 7.5))
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
    # Range of traffic multipliers on this map (only roads with traffic > 1.0)
    jams = [graph.traffic(u, v) for u, v in all_edges if graph.traffic(u, v) > 1.0]
    lowest, highest = min(jams, default=1.0), max(jams, default=1.0)

    for u, v in all_edges:
        (x1, y1), (x2, y2) = _xy(u), _xy(v)

        if graph.is_blocked(u, v):
            # Blocked road: red dashed line
            ax.plot([x1, x2], [y1, y2], color=BLOCKED, linestyle="--",
                    linewidth=max(1.2, 0.09 * cell), zorder=2)
            continue

        multiplier = graph.traffic(u, v)
        if multiplier > 1.0:
            # Traffic: orange, darker and thicker for a higher multiplier
            level = _traffic_level(multiplier, lowest, highest)
            ax.plot([x1, x2], [y1, y2], color=_traffic_color(level),
                    linewidth=max(1.5, (0.08 + 0.12 * level) * cell),
                    solid_capstyle="round", zorder=2)
        else:
            # Normal road: faint line
            ax.plot([x1, x2], [y1, y2], color=ROAD, linewidth=0.8, zorder=1)

    # --- 2. Explored nodes ---------------------------------------------------
    if explored:
        points = [_xy(n) for n in explored]
        ax.scatter([p[0] for p in points], [p[1] for p in points],
                   s=explored_size, color=EXPLORED, alpha=0.9,
                   edgecolors="none", zorder=3)

    # --- 3. Final route: the path of every leg that was found ----------------
    if legs:
        for leg in legs:
            path = leg.get("path", [])
            if not leg.get("found", False) or not path:
                continue  # unreachable leg: nothing to draw
            points = [_xy(n) for n in path]
            ax.plot([p[0] for p in points], [p[1] for p in points],
                    color=ROUTE, linewidth=route_width,
                    solid_capstyle="round", solid_joinstyle="round", zorder=4)

    # --- 4. Delivery stops, numbered in visit order --------------------------
    for number, stop in enumerate(order, start=1):
        x, y = _xy(stop)
        ax.scatter(x, y, s=stop_size, color=STOP, edgecolors=TEXT,
                   linewidths=1.2, zorder=5)
        ax.text(x, y, str(number), color=BG, fontsize=number_font,
                fontweight="bold", ha="center", va="center", zorder=6)

    # --- 5. Depot: black square with a white border --------------------------
    x, y = _xy(depot)
    ax.scatter(x, y, s=stop_size, marker="s", color=DEPOT, edgecolors=TEXT,
               linewidths=1.8, zorder=6)

    # --- 6. Axes: (0, 0) at the top-left, labels, boundary -------------------
    ax.set_xlim(-0.5, cols - 0.5)
    ax.set_ylim(rows - 0.5, -0.5)     # reversed so row 0 is at the top
    ax.set_aspect("equal")

    ax.set_xticks(range(cols))
    ax.set_yticks(range(rows))
    tick_font = 10 if max(rows, cols) <= 20 else 8
    ax.tick_params(colors=SUBTEXT, labelsize=tick_font, length=3)
    ax.xaxis.tick_top()               # column numbers above the grid, like a table
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("Column", color=TEXT, fontsize=11, labelpad=8)
    ax.set_ylabel("Row", color=TEXT, fontsize=11, labelpad=8)

    for spine in ax.spines.values():  # the frame is the grid boundary
        spine.set_color(SUBTEXT)
        spine.set_linewidth(1.5)

    fig.suptitle(title or "Delivery Grid", color=TEXT, fontsize=15,
                 fontweight="bold", x=0.40, y=0.97)

    # --- 7. Legend, outside the grid on the right ----------------------------
    handles = [
        Line2D([], [], marker="s", linestyle="", markersize=12,
               markerfacecolor=DEPOT, markeredgecolor=TEXT, label="Depot"),
        Line2D([], [], marker="o", linestyle="", markersize=12,
               markerfacecolor=STOP, markeredgecolor=TEXT,
               label="Delivery stop\n(number = visit order)"),
        Line2D([], [], marker="o", linestyle="", markersize=10,
               markerfacecolor=EXPLORED, markeredgecolor="none",
               label="Explored node"),
        Line2D([], [], color=ROUTE, linewidth=4, label="Final route"),
        Line2D([], [], color=BLOCKED, linewidth=2, linestyle="--",
               label="Blocked road"),
        Line2D([], [], color=TRAFFIC_LOW, linewidth=3, label="Traffic (low)"),
        Line2D([], [], color=TRAFFIC_HIGH, linewidth=6, label="Traffic (high)"),
    ]
    legend = ax.legend(handles=handles, loc="upper left",
                       bbox_to_anchor=(1.04, 1.0), frameon=True,
                       facecolor=PANEL, edgecolor=SUBTEXT, labelcolor=TEXT,
                       fontsize=10, title="Legend", borderpad=1,
                       labelspacing=1.1)
    legend.get_title().set_color(TEXT)
    legend.get_title().set_fontweight("bold")

    # Leave space for the legend (tight_layout does not account for it)
    fig.subplots_adjust(left=0.07, right=0.72, top=0.86, bottom=0.04)
    return fig


# ---------------------------------------------------------------------------
# Function 2: A* vs GBFS bar chart
# ---------------------------------------------------------------------------
def comparison_chart(plan_astar, plan_gbfs) -> Figure:
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
        ("Total Time (ms)", "total_time_ms"),
    ]
    names = ["A*", "GBFS"]
    colors = [ASTAR_COLOR, GBFS_COLOR]

    fig, axes = plt.subplots(1, 3, figsize=(10, 4.8))
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
            elif isinstance(value, int):
                text = str(value)
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

    # One shared legend for the whole figure
    handles = [Line2D([], [], color=c, linewidth=8, label=n)
               for n, c in zip(names, colors)]
    fig.legend(handles=handles, loc="upper right", ncol=2, frameon=True,
               facecolor=PANEL, edgecolor=SUBTEXT, labelcolor=TEXT, fontsize=10)
    fig.suptitle("A* vs GBFS Comparison", color=TEXT, fontsize=15,
                 fontweight="bold", x=0.05, ha="left", y=0.97)

    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return fig
