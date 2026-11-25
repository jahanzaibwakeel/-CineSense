import json

import httpx
import pytest

from data_platform.providers.tmdb.client import TmdbConfig, TmdbProvider
from data_platform.providers.tmdb.errors import ProviderAuthenticationError, ProviderNotFoundError, ProviderResponseError, ProviderServerError


def provider(handler, *, retries=0):
    client = httpx.Client(base_url="https://api.themoviedb.org/3", transport=httpx.MockTransport(handler),
                          headers={"Authorization": "Bearer token-never-log"})
    return TmdbProvider(TmdbConfig(read_access_token="token-never-log", max_retries=retries, min_request_interval_seconds=0),
                        client=client, sleep=lambda _: None, random_value=lambda: 0)


def test_discover_pagination_empty_results_and_bearer_auth():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"page": 2, "total_pages": 3, "total_results": 0, "results": []})
    api = provider(handler)
    result = api.discover_movies(page=2)
    assert (result.page, result.total_pages, result.results) == (2, 3, [])
    assert seen[0].headers["Authorization"] == "Bearer token-never-log"
    assert "api_key" not in str(seen[0].url)


def test_details_credits_genres_and_external_ids_routes():
    seen = []
    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200, json={"genres": [{"id": 1, "name": "Drama"}]})
    api = provider(handler)
    api.get_movie("18")
    api.get_credits("18")
    api.get_genres()
    api.get_external_ids("18")
    assert seen == ["/3/movie/18", "/3/movie/18/credits", "/3/genre/movie/list", "/3/movie/18/external_ids"]


@pytest.mark.parametrize("status,expected", [(401, ProviderAuthenticationError), (404, ProviderNotFoundError), (200, ProviderResponseError)])
def test_permanent_errors_and_malformed_json(status, expected):
    def handler(_):
        return httpx.Response(status, content=b"not-json" if status == 200 else b"{}")
    with pytest.raises(expected):
        provider(handler).get_movie("3")


def test_429_respects_retry_after_and_recovers():
    calls, delays = 0, []
    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "2"}) if calls == 1 else httpx.Response(200, json={"id": 1})
    api = TmdbProvider(TmdbConfig(read_access_token="secret", max_retries=1, min_request_interval_seconds=0),
                       client=httpx.Client(base_url="https://api.themoviedb.org/3", transport=httpx.MockTransport(handler),headers={"Authorization":"Bearer secret"}),
                       sleep=delays.append, random_value=lambda: 0)
    assert api.get_movie("1")["id"] == 1
    assert delays == [2.0]


def test_500_retry_exhaustion_is_bounded_and_credentials_are_not_exposed():
    calls = 0
    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"secret": "never include"})
    with pytest.raises(ProviderServerError) as exc:
        provider(handler, retries=2).get_movie("6")
    assert calls == 3
    assert "never include" not in str(exc.value)
    assert "token-never-log" not in str(exc.value)
