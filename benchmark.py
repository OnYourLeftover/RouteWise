"""Benchmark A* and GBFS on the same delivery routes."""

import csv
import os
import statistics

from core.graph import make_random_grid, random_stops
from core.multistop import order_stops, plan_route


OUTPUT_PATH = "data/benchmark_results.csv"
CSV_COLUMNS = (
    "seed",
    "algo",
    "heuristic",
    "complete",
    "total_cost",
    "nodes_explored",
    "median_time_ms",
    "gap_pct",
)
CONFIGURATIONS = (
    ("astar", "manhattan"),
    ("astar", "euclidean"),
    ("gbfs", "manhattan"),
    ("gbfs", "euclidean"),
)


def run_benchmark() -> list[dict]:
    """Return one benchmark row per seed and search configuration."""
    rows = []
    depot = (0, 0)
    for seed in range(30):
        graph = make_random_grid(
            rows=20, cols=20, seed=seed, traffic_density=0.2, blocked_density=0.05
        )
        stops = random_stops(graph, 5, seed=seed + 100, exclude=[depot])
        order = order_stops(depot, stops)
        reference_cost = None

        for algo, heuristic in CONFIGURATIONS:
            first_plan = plan_route(graph, depot, order, algo, heuristic)
            times_ms = [first_plan["total_time_ms"]]
            for _ in range(4):
                plan = plan_route(graph, depot, order, algo, heuristic)
                times_ms.append(plan["total_time_ms"])

            complete = first_plan["complete"]
            cost = first_plan["total_cost"] if complete else None
            # The baseline runs first so every gap uses this seed's unrounded cost.
            if (algo, heuristic) == ("astar", "manhattan"):
                reference_cost = cost
            gap_pct = None
            if cost is not None and reference_cost is not None:
                gap_pct = round((cost / reference_cost - 1) * 100, 4)

            rows.append({
                "seed": seed,
                "algo": algo,
                "heuristic": heuristic,
                "complete": complete,
                "total_cost": round(cost, 6) if cost is not None else None,
                "nodes_explored": first_plan["total_nodes_explored"],
                "median_time_ms": round(statistics.median(times_ms), 4),
                "gap_pct": gap_pct,
            })
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    """Write benchmark rows with the required column order."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Run the benchmark and write its CSV report."""
    rows = run_benchmark()
    write_csv(rows, OUTPUT_PATH)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
