from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./news.db"

    # "auto": use BERT/DistilBERT if torch+transformers are installed and models load,
    #         otherwise fall back to the lightweight CPU-only backend.
    # "transformers": require the transformer models (fail loudly otherwise).
    # "lite": VADER + extractive summarizer (no downloads, used for tests/demos).
    nlp_backend: str = "auto"

    sentiment_model: str = "distilbert-base-uncased-finetuned-sst-2-english"
    summary_model: str = "sshleifer/distilbart-cnn-12-6"
    # Optional: directory of a BERT model fine-tuned for left/center/right (see scripts/train_bias.py)
    bias_model_path: str = ""

    fetch_interval_minutes: int = 15
    max_per_feed: int = 25
    ingest_on_startup: bool = True
    fetch_full_text: bool = False  # needs `pip install trafilatura`

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
