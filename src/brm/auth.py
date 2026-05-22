"""API-key authentication dependency for FastAPI endpoints.

The X-API-Key header is validated against the `api_key` setting.  All
review-queue and pull-delivery endpoints require this header.
"""

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from brm.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    """FastAPI dependency: validate the X-API-Key header.

    Raises:
        HTTPException(401): If the key is missing or does not match settings.api_key.
    """
    if not key or key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
