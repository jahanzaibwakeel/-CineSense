from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from data_platform.contracts.models import ProviderPage


@dataclass(frozen=True)
class ProviderMetadata:
    key: str
    display_name: str
    base_url: str
    terms_url: str
    attribution: str
    usage_scope: str
    license_name: str


class MovieProvider(ABC):
    """Replaceable provider contract used by the normalization and ingest layers."""

    metadata: ProviderMetadata

    @abstractmethod
    def discover_movies(self, *, page: int, language: str, sort_by: str) -> ProviderPage: ...

    @abstractmethod
    def search_movies(self, *, query: str, page: int, language: str) -> ProviderPage: ...

    @abstractmethod
    def get_movie(self, provider_movie_id: str, *, language: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_credits(self, provider_movie_id: str, *, language: str) -> dict[str, Any]: ...

    @abstractmethod
    def get_genres(self, *, language: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_external_ids(self, provider_movie_id: str) -> dict[str, Any]: ...

    @abstractmethod
    def close(self) -> None: ...
