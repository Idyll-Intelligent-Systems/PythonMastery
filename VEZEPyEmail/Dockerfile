FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8000 25 465 587
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
