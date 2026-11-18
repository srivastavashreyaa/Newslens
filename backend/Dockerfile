FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt requirements-ml.txt ./
ARG INSTALL_ML=false
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-ml.txt; fi
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
