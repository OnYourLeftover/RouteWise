# RouteWise

Plan a delivery round trip through a seeded grid city with traffic and road closures. Compare A* and Greedy Best-First Search (GBFS) on the same trip and step through the nodes each algorithm explores.

## Run locally

Run these commands from the RouteWise repository root. You’ll need Python 3.11 or newer.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### macOS or Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Open the URL printed by Streamlit, usually [http://localhost:8501](http://localhost:8501). Press `Ctrl+C` in the terminal to stop the app.

Use the **⋮** menu in the top right to choose **Light**, **Dark**, or **System** under **Theme**. System follows your browser or device preference.

## Explore a route

1. Set the seed, grid size, traffic, blocked roads, depot, and stop count. Choose a heuristic and press **Run**. The same settings and stop shuffle reproduce the same city and route.
2. In **Route**, switch algorithms from the sidebar or choose a leg and move the exploration slider. Open **Full itinerary** to see each leg, including the return to the depot. A new scenario takes effect when you press **Run** again.
3. Use **Comparison** to see cost, nodes explored, and search time for both algorithms. The visit order uses nearest Manhattan distance. Both searches use that order, and traffic and road closures affect the individual paths.
4. Use **Benchmark** to compare results across 30 seeded cities. The overview shows completed runs, median nodes and search time, and the mean cost gap relative to A* with Manhattan. Detailed statistics and raw rows are available below.

**Randomize stops** changes the stop seed while keeping the city. **Demo presets** includes a disconnected depot and a case where inflated Manhattan leads A* to a higher-cost route. On an incomplete trip, dashed green lines mark individual legs with a path, and red diamonds mark stops unreachable from the depot.

## Test and benchmark

On Windows (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/
.\.venv\Scripts\python.exe benchmark.py
```

On macOS or Linux:

```sh
.venv/bin/python -m pytest tests/
.venv/bin/python benchmark.py
```

The tests exercise both search algorithms and the Streamlit controls. The benchmark command regenerates `data/benchmark_results.csv` from five timing trials per seed and configuration. Search times vary by machine.
