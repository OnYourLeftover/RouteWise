"""Regression coverage for RouteWise’s Streamlit controls and result views."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def widget(widgets, label):
    return next(item for item in widgets if item.label == label)


def table(app, column):
    return next(item.value for item in app.dataframe if column in item.value.columns)


def test_route_inspection_keeps_the_saved_run():
    app = AppTest.from_file(APP_PATH, default_timeout=15).run()
    widget(app.button, "Run").click().run()
    assert not app.exception
    saved_run = app.session_state["last_run"]
    metrics = [metric.value for metric in app.metric]
    assert metrics[:2] == ["77.5", "102"]

    widget(app.selectbox, "Leg to step through").select_index(1).run()
    widget(app.slider, "Explored nodes shown").set_value(0).run()
    widget(app.checkbox, "Show other legs").uncheck().run()
    assert [metric.value for metric in app.metric] == metrics

    widget(app.radio, "Algorithm").set_value("gbfs").run()
    assert app.metric[0].value == "100.6"
    assert app.session_state["last_run"] is saved_run
    assert not app.info

    widget(app.button, "Randomize stops").click().run()
    assert any("Showing the last run" in notice.value for notice in app.info)
    assert app.session_state["last_run"] is saved_run
    widget(app.button, "Run").click().run()
    settings, result = app.session_state["last_run"]
    assert settings["stop_seed"] == 1
    assert result.order != saved_run[1].order
    assert widget(app.selectbox, "Leg to step through").index == 0
    assert not app.exception


def test_disconnected_preset_labels_partial_legs():
    app = AppTest.from_file(APP_PATH, default_timeout=15).run()
    widget(app.button, "Disconnected depot").click().run()
    assert [app.slider(key=key).value for key in ("size", "blocked_density")] == [10, 0.3]
    widget(app.button, "Run").click().run()

    assert not app.exception
    assert app.metric[0].value == "N/A"
    assert any("Unreachable from the depot: Stop 1, Stop 2, Stop 3, Stop 4, Stop 5" in notice.value
               for notice in app.warning)
    assert table(app, "Leg")["Status"].tolist() == [
        "Unreachable", "Path found", "Path found", "Path found", "Path found", "Unreachable",
    ]


def test_inflated_preset_and_benchmark_baselines():
    app = AppTest.from_file(APP_PATH, default_timeout=15).run()
    widget(app.button, "Inflated A*").click().run()
    widget(app.button, "Run").click().run()

    assert not app.exception
    assert any("can make A* miss the lowest-cost path" in notice.value for notice in app.info)
    comparison = table(app, "Metric").set_index("Metric")
    assert comparison.loc["Total cost"].tolist() == ["92.1", "89.9"]
    assert comparison.loc["Cost difference vs A*", "GBFS"] == "-2.2 (-2.4%)"
    benchmark = table(app, "Median nodes")
    assert benchmark["Completed"].tolist() == [30, 30, 30, 30]
    assert benchmark["Mean cost gap (%)"].tolist() == [0.0, 0.0, 20.36, 18.64]
