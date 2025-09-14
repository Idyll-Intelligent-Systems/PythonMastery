FROM python:3.11-slim
WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser \
  && apt-get update && apt-get install -y --no-install-recommends build-essential curl \
  && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .
COPY . .
USER appuser
ENV PORT=8006
EXPOSE 8006
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8006","--log-level","warning"]
