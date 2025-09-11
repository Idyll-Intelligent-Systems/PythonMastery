from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQS = Counter("veze_requests_total", "Total HTTP requests", ["path"])
REQ_LAT = Histogram(
    "veze_request_duration_seconds",
    "HTTP request duration in seconds",
    ["path", "method", "status"],
    buckets=(0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5)
)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
