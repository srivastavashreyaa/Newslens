FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
# Lite NLP (VADER + extractive). For real DistilBERT/DistilBART build with:  --build-arg INSTALL_ML=true
ARG INSTALL_ML=false
RUN pip install -r requirements.txt && \
    if [ "$INSTALL_ML" = "true" ]; then pip install --extra-index-url https://download.pytorch.org/whl/cpu torch transformers sentencepiece; fi
COPY . .
ENV NLP_BACKEND=lite PORT=8501
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"8501\")}/_stcore/health')"
CMD ["sh", "-c", "streamlit run streamlit_app.py --server.port=${PORT} --server.address=0.0.0.0"]
