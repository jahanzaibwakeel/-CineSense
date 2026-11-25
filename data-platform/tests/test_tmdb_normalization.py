from data_platform.normalization.tmdb import NormalizationError, normalize_movie, normalize_search_text


def fixture():
    return (
        {"id": 42, "title": "  Amélie\n", "original_title": "Le Fabuleux Destin", "release_date": "2001-04-25",
         "original_language": "fr", "runtime": 122, "adult": False, "genres": [{"id": 35, "name": " Comedy "}],
         "production_countries": [{"iso_3166_1": "fr", "name": "France"}], "production_companies": [],
         "overview": "  A young woman changes lives.  ", "budget": 0, "revenue": 0},
        {"cast": [{"id": 8, "name": "Audrey Tautou", "character": "Amélie", "order": 0}],
         "crew": [{"id": 9, "name": "Jean-Pierre Jeunet", "job": "Director", "department": "Directing"}]},
        {"imdb_id": "tt0211915"},
    )


def test_normalizes_unicode_whitespace_metadata_people_and_roles():
    details, credits, ids = fixture()
    movie, warnings = normalize_movie(details, credits, ids, requested_locale="fr-FR")
    assert movie.title == "Amélie"
    assert movie.locale == "fr-FR"
    assert movie.release_date.isoformat() == "2001-04-25"
    assert movie.genres[0].provider_id == "35"
    assert movie.production_countries[0].code == "FR"
    assert [(item.name, item.job, item.character_name) for item in movie.credits] == [
        ("Audrey Tautou", "ACTING", "Amélie"), ("Jean-Pierre Jeunet", "Director", None)]
    assert movie.budget is None and movie.revenue is None
    assert movie.external_ids == {"imdb": "tt0211915"}
    assert warnings == []


def test_missing_optional_values_are_unknown_and_not_fabricated():
    movie, warnings = normalize_movie({"id": "12", "title": "A Film"}, {}, {}, requested_locale="en-US")
    assert movie.release_date is None and movie.runtime_minutes is None
    assert movie.credits == [] and movie.overview is None
    assert len(warnings) == 2


def test_bad_date_is_rejected_and_search_text_is_unicode_casefolded():
    details, credits, ids = fixture()
    details["release_date"] = "2001-02-31"
    try:
        normalize_movie(details, credits, ids, requested_locale="en-US")
        assert False, "invalid calendar date must be rejected"
    except NormalizationError as exc:
        assert "Release date" in str(exc)
    assert normalize_search_text("  STRAẞE\nFILM ") == "strasse film"
