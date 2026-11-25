from __future__ import annotations

from datetime import date
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GenreRef(Contract):
    provider_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)


class CountryRef(Contract):
    code: str = Field(min_length=2, max_length=2)
    name: str | None = None

    @field_validator("code")
    @classmethod
    def uppercase_iso_code(cls, value: str) -> str:
        value = value.upper()
        if not re.fullmatch(r"[A-Za-z]{2}",value):
            raise ValueError("country code must contain two letters")
        return value


class CompanyRef(Contract):
    provider_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=300)


class Credit(Contract):
    provider_person_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=300)
    credit_type: str = Field(pattern="^(CAST|CREW)$")
    job: str = Field(min_length=1, max_length=200)
    character_name: str | None = Field(default=None, max_length=500)
    billing_order: int | None = Field(default=None, ge=0)
    department: str | None = Field(default=None, max_length=100)


class NormalizedMovie(Contract):
    provider_key: str = Field(min_length=1, max_length=80)
    provider_movie_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    original_title: str | None = Field(default=None, max_length=500)
    locale: str = Field(default="und", min_length=2, max_length=20)
    release_date: date | None = None
    original_language: str | None = Field(default=None, min_length=2, max_length=3)
    runtime_minutes: int | None = Field(default=None, ge=1, le=1440)
    adult_content: bool | None = None
    status: str | None = Field(default=None, max_length=100)
    tagline: str | None = Field(default=None, max_length=2000)
    overview: str | None = Field(default=None, max_length=20000)
    budget: int | None = Field(default=None, ge=0)
    revenue: int | None = Field(default=None, ge=0)
    genres: list[GenreRef] = Field(default_factory=list)
    production_countries: list[CountryRef] = Field(default_factory=list)
    production_companies: list[CompanyRef] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)
    credits: list[Credit] = Field(default_factory=list)
    detail_payload_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    credits_payload_sha256: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    external_ids_payload_sha256: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    source_uri: str = Field(min_length=1, max_length=1000)

    @field_validator("title", "original_title", "tagline", "overview", "status")
    @classmethod
    def normalize_whitespace(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("locale")
    @classmethod
    def normalize_locale(cls, value: str) -> str:
        value = value.replace("_", "-")
        if value == "und":
            return value
        chunks = value.split("-")
        if not chunks[0].isalpha() or not 2 <= len(chunks[0]) <= 3:
            raise ValueError("locale must begin with a two or three letter language code")
        if any(not part.isalnum() or len(part) > 8 for part in chunks[1:]):
            raise ValueError("locale contains an invalid subtag")
        return "-".join([chunks[0].lower(), *(part.upper() if len(part) == 2 else part for part in chunks[1:])])


class DiscoveryCandidate(Contract):
    provider_movie_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)


class ProviderPage(Contract):
    page: int = Field(ge=1)
    total_pages: int = Field(default=1, ge=0)
    total_results: int = Field(default=0, ge=0)
    results: list[dict[str, Any]] = Field(default_factory=list)


class IngestFailure(Contract):
    stage: str
    category: str
    summary: str = Field(max_length=1000)
    retryable: bool
    provider_external_id: str | None = None
