from __future__ import annotations
import os


def resolve(service_name: str, default_url: str) -> str:
    # Shared convention: VEZE_SERVICE_<NAME>=URL
    env_key = f"VEZE_SERVICE_{service_name.upper()}"
    return os.getenv(env_key) or default_url
