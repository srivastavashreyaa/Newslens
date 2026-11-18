"""Smoke tests for the Streamlit app (no browser needed)."""
import os
import tempfile
from pathlib import Path

os.environ.setdefault("NLP_BACKEND", "lite")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'smoke.db'}"

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def test_app_renders_and_filters():
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception
    at.radio(key="data_mode").set_value("Demo data").run()
    assert not at.exception and [m for m in at.metric if m.label == "Articles"]
    at.text_input(key="f_q").set_value("won ipl in 2024").run()           # nothing matches -> friendly empty state, no crash
    assert not at.exception and any("Nothing matches" in m.value for m in at.markdown)
    at.button[[b.label for b in at.button].index("↺ Reset filters")].click().run()
    assert not at.exception and [m for m in at.metric if m.label == "Articles"]
    at.selectbox(key="theme").set_value("Emerald").run()
    assert not at.exception


def test_search_word_matching_and_partial():
    import pandas as pd

    from ui.data import search_df

    d = pd.DataFrame({"title": ["Solar farm approved", "Flood warning issued"], "summary": ["power for homes", "heavy rain"], "source": ["A", "B"],
                      "keywords": [["solar"], ["flood"]]})
    assert len(search_df(d, "solar farm")[0]) == 1 and search_df(d, "solar farm")[1] == "all"
    assert search_df(d, "solar flood")[1] == "partial"
    assert search_df(d, "won ipl in 2024")[1] == "none"
