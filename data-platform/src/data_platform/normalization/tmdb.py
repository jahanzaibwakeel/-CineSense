from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from typing import Any

from pydantic import ValidationError

from data_platform.contracts.models import CompanyRef, CountryRef, Credit, GenreRef, NormalizedMovie


class NormalizationError(ValueError):
    pass


def normalize_search_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def normalize_display_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(unicodedata.normalize("NFKC", value).split())
    return cleaned or None


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_movie(
    details: dict[str, Any],
    credits_response: dict[str, Any],
    external_ids_response: dict[str, Any],
    *,
    requested_locale: str,
) -> tuple[NormalizedMovie, list[str]]:
    warnings: list[str] = []
    provider_id = _required_id(details.get("id"), "movie id")
    title = normalize_display_text(details.get("title"))
    if not title:
        raise NormalizationError("Movie title is missing or blank.")

    release_date = _parse_date(details.get("release_date"))
    language = _optional_language(details.get("original_language"))
    runtime = _optional_integer(details.get("runtime"), "runtime", minimum=1, maximum=1440)
    adult = details.get("adult") if isinstance(details.get("adult"), bool) else None
    if details.get("adult") is not None and adult is None:
        raise NormalizationError("Adult flag must be a boolean when provided.")

    genres: list[GenreRef] = []
    seen_genres: set[str] = set()
    raw_genres = details.get("genres") or []
    if not isinstance(raw_genres, list):
        raise NormalizationError("Genres must be an array when provided.")
    for item in raw_genres:
        if not isinstance(item, dict):
            raise NormalizationError("Genre entry must be an object.")
        genre_id = _required_id(item.get("id"), "genre id")
        name = normalize_display_text(item.get("name"))
        if not name:
            raise NormalizationError(f"Genre {genre_id} has no name.")
        if genre_id in seen_genres:
            warnings.append(f"duplicate genre identifier {genre_id}")
            continue
        seen_genres.add(genre_id)
        genres.append(GenreRef(provider_id=genre_id, name=name))

    countries: list[CountryRef] = []
    raw_countries = details.get("production_countries") or []
    if not isinstance(raw_countries, list):
        raise NormalizationError("Production countries must be an array when provided.")
    for item in raw_countries:
        if not isinstance(item, dict):
            raise NormalizationError("Production country entry must be an object.")
        code = item.get("iso_3166_1")
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z]{2}",code.strip()):
            raise NormalizationError("Production country contains an invalid ISO 3166-1 alpha-2 code.")
        countries.append(CountryRef(code=code.strip(), name=normalize_display_text(item.get("name"))))

    companies: list[CompanyRef] = []
    raw_companies = details.get("production_companies") or []
    if not isinstance(raw_companies, list):
        raise NormalizationError("Production companies must be an array when provided.")
    for item in raw_companies:
        if not isinstance(item, dict):
            raise NormalizationError("Production company entry must be an object.")
        company_id = _required_id(item.get("id"), "production company id")
        company_name = normalize_display_text(item.get("name"))
        if company_name:
            companies.append(CompanyRef(provider_id=company_id, name=company_name))

    normalized_credits = _normalize_credits(credits_response)
    source_language = language or requested_locale.split("-")[0].lower() or "und"
    locale = requested_locale if requested_locale else source_language
    external_ids: dict[str, str] = {}
    imdb_id = external_ids_response.get("imdb_id")
    if isinstance(imdb_id, str) and imdb_id.strip():
        external_ids["imdb"] = imdb_id.strip()

    # TMDB's details schema uses zero for several unavailable numeric fields.
    # Do not turn that sentinel into a verified budget/revenue claim.
    budget = _optional_integer(details.get("budget"), "budget", minimum=0)
    revenue = _optional_integer(details.get("revenue"), "revenue", minimum=0)
    if budget == 0:
        budget = None
    if revenue == 0:
        revenue = None

    try:
        movie = NormalizedMovie(
            provider_key="tmdb",
            provider_movie_id=provider_id,
            title=title,
            original_title=normalize_display_text(details.get("original_title")),
            locale=locale,
            release_date=release_date,
            original_language=language,
            runtime_minutes=runtime,
            adult_content=adult,
            status=normalize_display_text(details.get("status")),
            tagline=normalize_display_text(details.get("tagline")),
            overview=normalize_display_text(details.get("overview")),
            budget=budget,
            revenue=revenue,
            genres=genres,
            production_countries=countries,
            production_companies=companies,
            external_ids=external_ids,
            credits=normalized_credits,
            detail_payload_sha256=canonical_payload_hash(details),
            credits_payload_sha256=canonical_payload_hash(credits_response),
            external_ids_payload_sha256=canonical_payload_hash(external_ids_response),
            source_uri=f"https://api.themoviedb.org/3/movie/{provider_id}",
        )
    except ValidationError as exc:
        raise NormalizationError("Movie metadata failed canonical validation.") from exc

    if release_date is None and details.get("release_date"):
        warnings.append("release date was empty; no release-date assertion was created")
    if not normalized_credits:
        warnings.append("no cast or crew credits were provided")
    if movie.original_title is None:
        warnings.append("original title is missing")
    return movie, warnings


def _normalize_credits(payload: dict[str, Any]) -> list[Credit]:
    output: list[Credit] = []
    for collection, credit_type in (("cast", "CAST"), ("crew", "CREW")):
        records = payload.get(collection) or []
        if not isinstance(records, list):
            raise NormalizationError(f"Credits field '{collection}' must be an array.")
        for item in records:
            if not isinstance(item, dict):
                raise NormalizationError(f"Credits field '{collection}' contains a non-object entry.")
            person_id = _required_id(item.get("id"), "credit person id")
            name = normalize_display_text(item.get("name"))
            if not name:
                raise NormalizationError(f"Credit for person {person_id} has no name.")
            if credit_type == "CAST":
                job = "ACTING"
                character = normalize_display_text(item.get("character"))
                order = _optional_integer(item.get("order"), "cast billing order", minimum=0)
                department = None
            else:
                job = normalize_display_text(item.get("job")) or "CREW"
                character = None
                order = _optional_integer(item.get("order"), "crew billing order", minimum=0)
                department = normalize_display_text(item.get("department"))
            output.append(Credit(
                provider_person_id=person_id,
                name=name,
                credit_type=credit_type,
                job=job,
                character_name=character,
                billing_order=order,
                department=department,
            ))
    return output


def _required_id(value: Any, field: str) -> str:
    if isinstance(value, bool) or value is None or not str(value).strip().isdigit():
        raise NormalizationError(f"{field} must be a positive integer identifier.")
    result = str(value).strip()
    if int(result) <= 0 or len(result) > 20:
        raise NormalizationError(f"{field} must be a positive integer identifier.")
    return result


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise NormalizationError("Release date must use YYYY-MM-DD format.")
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as exc:
        raise NormalizationError("Release date must use YYYY-MM-DD format.") from exc
    if parsed.isoformat() != value.strip():
        raise NormalizationError("Release date must use YYYY-MM-DD format.")
    return parsed


def _optional_language(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{2,3}", value.strip()):
        raise NormalizationError("Original language must be a two or three letter language code.")
    return value.strip().lower()


def _optional_integer(value: Any, field: str, *, minimum: int, maximum: int | None = None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise NormalizationError(f"{field} must be an integer when provided.")
    if value < minimum or (maximum is not None and value > maximum):
        raise NormalizationError(f"{field} is outside the supported range.")
    return value
