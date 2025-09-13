from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    REGISTRY,
    generate_latest,
)


def _get_or_create_counter(name: str, doc: str, labels: list[str]) -> Counter:
    try:
        existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
        if isinstance(existing, Counter):
            return existing
    except Exception:
        pass
    return Counter(name, doc, labels)


def _get_or_create_histogram(
    name: str, doc: str, labels: list[str], buckets: tuple[float, ...]
) -> Histogram:
    try:
        existing = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
        if isinstance(existing, Histogram):
            return existing
    except Exception:
        pass
    return Histogram(name, doc, labels, buckets=buckets)


REQS = _get_or_create_counter("veze_requests_total", "Total HTTP requests", ["path"])
REQ_LAT = _get_or_create_histogram(
    "veze_request_duration_seconds",
    "HTTP request duration in seconds",
    ["path", "method", "status"],
    buckets=(0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5),
)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
