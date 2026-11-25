from __future__ import annotations

from difflib import SequenceMatcher

from data_platform.normalization.tmdb import normalize_search_text


def candidate_score(incoming_title: str, incoming_year: int | None, existing_title: str, existing_year: int | None) -> tuple[float, dict[str, float | int | None]]:
    title_similarity=SequenceMatcher(None,normalize_search_text(incoming_title),normalize_search_text(existing_title)).ratio()
    year_delta=abs(incoming_year-existing_year) if incoming_year and existing_year else None
    year_similarity=(1.0 if year_delta == 0 else 0.5 if year_delta == 1 else 0.0) if year_delta is not None else 0.0
    score=round(0.8*title_similarity+0.2*year_similarity,4)
    return score,{"title_similarity":round(title_similarity,4),"year_delta":year_delta}
