# NewsLens – Advanced News Aggregator & Analyzer

Two front ends share one NLP + ingestion core (`backend/app`):

| | Streamlit app (`streamlit_app.py`) | FastAPI + React (`backend/`, `frontend/`) |
|---|---|---|
| Best for | **Hosting on Streamlit Community Cloud**, demos, interviews | Classic full-stack architecture |
| UI | Plotly dashboard: click/box-select bubble chart, topic drill-down, story comparison, live wire, sentence-level sentiment flow, loaded-word highlighting | Recharts dashboard + WebSocket live feed |

## Streamlit app

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py          # http://localhost:8501
```
First launch fetches the live RSS feeds; if they can't be reached it loads clearly-labelled **demo data** (fictional outlets) so the app is never empty.

### Deploy anywhere (Docker / Render / Railway / Fly)
```bash
docker build -t newslens .
docker run -p 8501:8501 newslens            # http://localhost:8501
# real BERT models: docker build --build-arg INSTALL_ML=true -t newslens-ml . && docker run -e NLP_BACKEND=auto -p 8501:8501 newslens-ml
```
* **Render:** New → Blueprint → select the repo (`render.yaml` is included).  **Railway/Heroku-style hosts:** the `Procfile` is included.
* Health check path: `/_stcore/health`. CI (`.github/workflows/ci.yml`) runs the tests on every push.

### Deploy on Streamlit Community Cloud
1. Push this repo to GitHub (the `.streamlit/config.toml` theme and `requirements.txt` are already set up).
2. Go to share.streamlit.io → **New app** → pick the repo, branch `main`, main file **`streamlit_app.py`** → Deploy.
3. Optional app **Secrets** (TOML): `NLP_BACKEND = "auto"` to use DistilBERT/DistilBART (also uncomment `torch`/`transformers` in `requirements.txt`).

Notes
* Default mode is **lite NLP** (VADER + extractive summaries) so the app starts fast and fits in a free tier's memory. Real DistilBERT/DistilBART need `torch` + `transformers` and noticeably more RAM; if the free tier is too small, deploy on a Hugging Face Space (Streamlit SDK) or your own VM with the same code.
* The SQLite file (`news.db`) is ephemeral on Streamlit Cloud: it is rebuilt after each restart, which is fine for a live-feed demo.
* Use the sidebar **Auto-refresh** toggle to keep pulling feeds while the page is open.

---

Full-stack project: multi-source news ingestion → BERT/DistilBERT NLP → live analytics dashboard.

| Layer | Tech |
|---|---|
| NLP | **DistilBERT** (SST-2) sentiment, **DistilBART** summarization, optional fine-tuned **BERT/DistilBERT** bias classifier, tokenization + keyword extraction |
| Backend | FastAPI, SQLAlchemy/SQLite, feedparser + httpx (async RSS), APScheduler, WebSockets |
| Frontend | React + Vite + Recharts (sentiment timeline, source tone, bias, trending topics, story-framing comparison, live feed, "analyze any text") |
| Ops | Docker Compose, pytest |

## Architecture
```
RSS feeds (9 outlets) ─► ingest.py ─► NLP engine ─► SQLite ─► REST API ─► React dashboard
                          (async)     tokenize → sentiment                    ▲
                                      → summarize → bias → keywords           │
                                                  └──── WebSocket /ws/stream ─┘ (live push)
```
Pipeline per article: clean HTML → BERT tokenization (chunked to fit 512 tokens) → DistilBERT sentiment
(signed score −1…+1, neutral band for low confidence) → DistilBART abstractive summary → bias (direction + loaded-language score) → keywords.
Trends compare keyword mentions in the latest window with the previous one; "Same story, different framing" clusters
articles from different outlets with TF-IDF cosine similarity and shows each outlet's sentiment/bias side by side.

## Run the FastAPI + React version
```bash
# 1. backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-ml.txt        # or requirements.txt for the lite (no-BERT) backend
cp .env.example .env
python -m scripts.seed_demo               # optional: demo data so the dashboard is populated offline
uvicorn app.main:app --reload             # http://localhost:8000/docs

# 2. frontend (new terminal)
cd frontend && npm install && npm run dev # http://localhost:5173
```
First start downloads the Hugging Face models (~1 GB). If they can't load, `NLP_BACKEND=auto` falls back to the lite
backend (VADER + extractive summaries) and `/api/health` says which models are active. Use **Fetch latest** (or wait for the
15-minute scheduler) to pull real feeds; demo rows are tagged "demo data" and removed with `python -m scripts.seed_demo --clear`.

Docker: `docker compose up --build` → dashboard on http://localhost:8080.

Tests: `cd backend && python -m pytest`

## API
`GET /api/articles` (q, source, sentiment, bias, keyword, hours, limit, offset) · `GET /api/stats/{overview,sentiment-timeline,sources,trends}` ·
`GET /api/stories` · `POST /api/analyze` · `POST /api/ingest` · `WS /ws/stream`

## About media-bias detection (read before quoting numbers)
* Out of the box, bias **direction** comes from each outlet's editorial-lean prior in `backend/app/feeds.json`. These values are
  approximate, based on public media-bias ratings – review and edit them.
* For text-level detection, fine-tune a BERT model on a labelled dataset: `python -m scripts.train_bias --csv data/bias.csv`.
  It prints held-out **accuracy and macro-F1** and saves the model; set `BIAS_MODEL_PATH` to use it.
* **Measure your own metrics** and put those on your resume. The numbers on the original resume bullets (40 % clarity, 85 % bias
  accuracy, etc.) belong to your own experiments; this repo does not produce them for you.

## Ideas to extend
Full-article extraction (`FETCH_FULL_TEXT=true`), PostgreSQL, topic modelling (BERTopic), NER, user accounts/saved topics, Celery workers.
