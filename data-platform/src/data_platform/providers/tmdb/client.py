from __future__ import annotations

import email.utils
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from data_platform.contracts.models import ProviderPage
from data_platform.contracts.provider import MovieProvider, ProviderMetadata
from data_platform.providers.tmdb.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
    ProviderTransportError,
)

logger = logging.getLogger(__name__)

TMDB_ATTRIBUTION = "This product uses the TMDB API but is not endorsed or certified by TMDB."
TMDB_TERMS_URL = "https://www.themoviedb.org/documentation/api/terms-of-use"


@dataclass(frozen=True)
class TmdbConfig:
    read_access_token: str | None = field(default=None, repr=False)
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.themoviedb.org/3"
    timeout_seconds: float = 15.0
    max_retries: int = 3
    min_request_interval_seconds: float = 0.25

    @classmethod
    def from_environment(cls) -> "TmdbConfig":
        token = os.getenv("TMDB_API_READ_ACCESS_TOKEN", "").strip()
        key = os.getenv("TMDB_API_KEY", "").strip()
        if not token and not key:
            raise ProviderConfigurationError(
                "TMDB credentials are missing. Set TMDB_API_READ_ACCESS_TOKEN (preferred) "
                "or TMDB_API_KEY in the process environment / ignored .env."
            )
        try:
            timeout = float(os.getenv("TMDB_TIMEOUT_SECONDS", "15"))
            retries = int(os.getenv("TMDB_MAX_RETRIES", "3"))
            interval = float(os.getenv("TMDB_MIN_REQUEST_INTERVAL_SECONDS", "0.25"))
        except ValueError as exc:
            raise ProviderConfigurationError("TMDB timeout/retry settings must be numeric.") from exc
        if timeout <= 0 or not 0 <= retries <= 5 or interval < 0:
            raise ProviderConfigurationError("TMDB timeout must be positive, retries 0–5, and interval non-negative.")
        return cls(
            read_access_token=token or None,
            api_key=key or None,
            timeout_seconds=timeout,
            max_retries=retries,
            min_request_interval_seconds=interval,
        )


class _DiscoverResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page: int = Field(ge=1)
    total_pages: int = Field(default=1, ge=0)
    total_results: int = Field(default=0, ge=0)
    results: list[dict[str, Any]] = Field(default_factory=list)


class TmdbProvider(MovieProvider):
    metadata = ProviderMetadata(
        key="tmdb",
        display_name="The Movie Database (TMDB)",
        base_url="https://api.themoviedb.org/3",
        terms_url=TMDB_TERMS_URL,
        attribution=TMDB_ATTRIBUTION,
        usage_scope="non-commercial only unless separately licensed",
        license_name="TMDB API terms of use; operator must review before persistence",
    )

    def __init__(
        self,
        config: TmdbConfig,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        self._config = config
        self._sleep = sleep
        self._clock = clock
        self._random = random_value
        self._last_request_at: float | None = None
        self._owns_client = client is None
        headers = {"Accept": "application/json", "User-Agent": "CineSenseDataPlatform/0.1 (+local development)"}
        if config.read_access_token:
            headers["Authorization"] = f"Bearer {config.read_access_token}"
        self._client = client or httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=httpx.Timeout(config.timeout_seconds),
            headers=headers,
            follow_redirects=False,
        )

    def discover_movies(self, *, page: int, language: str = "en-US", sort_by: str = "popularity.desc") -> ProviderPage:
        response = self._get("discover/movie", {"page": page, "language": language, "sort_by": sort_by, "include_adult": "false"})
        return self._page(response)

    def search_movies(self, *, query: str, page: int, language: str = "en-US") -> ProviderPage:
        response = self._get("search/movie", {"query": query, "page": page, "language": language, "include_adult": "false"})
        return self._page(response)

    def get_movie(self, provider_movie_id: str, *, language: str = "en-US") -> dict[str, Any]:
        return self._get(f"movie/{self._safe_id(provider_movie_id) }", {"language": language})

    def get_credits(self, provider_movie_id: str, *, language: str = "en-US") -> dict[str, Any]:
        return self._get(f"movie/{self._safe_id(provider_movie_id)}/credits", {"language": language})

    def get_genres(self, *, language: str = "en") -> list[dict[str, Any]]:
        response = self._get("genre/movie/list", {"language": language})
        genres = response.get("genres")
        if not isinstance(genres, list):
            raise ProviderResponseError("TMDB genre response is missing its genres list.")
        return genres

    def get_external_ids(self, provider_movie_id: str) -> dict[str, Any]:
        return self._get(f"movie/{self._safe_id(provider_movie_id)}/external_ids", {})

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    @staticmethod
    def _safe_id(value: str) -> str:
        if not value.isdigit() or len(value) > 20:
            raise ProviderResponseError("TMDB movie identifier must be a positive integer.")
        return value

    @staticmethod
    def _page(payload: dict[str, Any]) -> ProviderPage:
        try:
            response = _DiscoverResponse.model_validate(payload)
            return ProviderPage.model_validate(response.model_dump())
        except ValidationError as exc:
            raise ProviderResponseError("TMDB returned a malformed paginated response.") from exc

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._config.read_access_token and self._config.api_key:
            params = {**params, "api_key": self._config.api_key}
        attempts = self._config.max_retries + 1
        for attempt in range(1, attempts + 1):
            self._pace_request()
            try:
                response = self._client.get(path, params=params)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                logger.warning("tmdb transport failure operation=%s attempt=%s", self._operation(path), attempt)
                if attempt == attempts:
                    raise ProviderTransportError(f"TMDB request failed after {attempts} attempts ({type(exc).__name__}).") from None
                self._sleep(self._backoff(attempt))
                continue

            logger.info("tmdb response operation=%s status=%s attempt=%s", self._operation(path), response.status_code, attempt)
            if response.status_code == 401:
                raise ProviderAuthenticationError("TMDB rejected the configured credentials (HTTP 401). Check the read access token or API key.")
            if response.status_code == 403:
                raise ProviderAuthenticationError("TMDB denied this request (HTTP 403). Check account permissions and current API terms.")
            if response.status_code == 404:
                raise ProviderNotFoundError(f"TMDB resource was not found for operation {self._operation(path)}.")
            if response.status_code == 429:
                if attempt == attempts:
                    raise ProviderRateLimitError(f"TMDB rate limit persisted after {attempts} attempts.")
                self._sleep(self._retry_after(response, attempt))
                continue
            if response.status_code == 408 or response.status_code >= 500:
                if attempt == attempts:
                    raise ProviderServerError(f"TMDB returned HTTP {response.status_code} after {attempts} attempts.")
                self._sleep(self._retry_after(response, attempt))
                continue
            if response.status_code >= 400:
                raise ProviderError(f"TMDB rejected operation {self._operation(path)} with HTTP {response.status_code}; check request parameters.")
            try:
                payload = response.json()
            except ValueError as exc:
                raise ProviderResponseError("TMDB returned invalid JSON.") from exc
            if not isinstance(payload, dict):
                raise ProviderResponseError("TMDB response must be a JSON object.")
            return payload
        raise ProviderTransportError("TMDB request ended without a response.")

    def _pace_request(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            delay = self._config.min_request_interval_seconds - (now - self._last_request_at)
            if delay > 0:
                self._sleep(delay)
        self._last_request_at = self._clock()

    def _backoff(self, attempt: int) -> float:
        return min(30.0, 0.5 * (2 ** (attempt - 1)) + self._random() * 0.25)

    def _retry_after(self, response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("Retry-After")
        if header:
            try:
                return max(0.0, min(60.0, float(header)))
            except ValueError:
                try:
                    retry_at = email.utils.parsedate_to_datetime(header)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    return max(0.0, min(60.0, (retry_at - datetime.now(timezone.utc)).total_seconds()))
                except (TypeError, ValueError, OverflowError):
                    pass
        return self._backoff(attempt)

    @staticmethod
    def _operation(path: str) -> str:
        if path.startswith("discover/"):
            return "discover_movies"
        if path.startswith("search/"):
            return "search_movies"
        if path.startswith("genre/"):
            return "get_genres"
        if path.endswith("/credits"):
            return "get_credits"
        if path.endswith("/external_ids"):
            return "get_external_ids"
        return "get_movie"
