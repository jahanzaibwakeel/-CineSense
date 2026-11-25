import pytest
from argparse import Namespace
from unittest.mock import Mock

from data_platform.cli import main as cli
from data_platform.contracts.models import ProviderPage
from data_platform.policy import PolicyError, require_persistence, require_provider_access


def test_provider_access_fails_closed_until_terms_and_attribution_acknowledged():
    with pytest.raises(PolicyError):
        require_provider_access({})
    env={"TMDB_USAGE_SCOPE":"non-commercial","TMDB_TERMS_ACKNOWLEDGED":"true","TMDB_ATTRIBUTION_ACKNOWLEDGED":"true","TMDB_LOGO_ACKNOWLEDGED":"true"}
    assert require_provider_access(env).terms_uri.endswith("terms-of-use")
    with pytest.raises(PolicyError):
        require_persistence(env)


def test_persistence_requires_separate_source_and_retention_acknowledgements():
    env={"TMDB_USAGE_SCOPE":"non-commercial","TMDB_TERMS_ACKNOWLEDGED":"true","TMDB_ATTRIBUTION_ACKNOWLEDGED":"true","TMDB_LOGO_ACKNOWLEDGED":"true","TMDB_SOURCE_POLICY":"PERMITTED"}
    with pytest.raises(PolicyError):
        require_persistence(env)
    env["TMDB_PERSISTENCE_ACKNOWLEDGED"]="true"
    assert require_persistence(env).usage_scope == "non-commercial"


def test_cli_dry_run_does_not_open_database_or_persist(monkeypatch):
    class FakeProvider:
        def __init__(self,_): pass
        def discover_movies(self,**_): return ProviderPage(page=1,total_pages=1,total_results=0,results=[])
        def close(self): pass
    monkeypatch.setattr(cli.TmdbConfig,"from_environment",classmethod(lambda cls: object()))
    monkeypatch.setattr(cli,"TmdbProvider",FakeProvider)
    database=Mock(side_effect=AssertionError("dry-run must not open PostgreSQL"))
    monkeypatch.setattr(cli,"database_connection",database)
    monkeypatch.setenv("TMDB_USAGE_SCOPE","non-commercial")
    monkeypatch.setenv("TMDB_TERMS_ACKNOWLEDGED","true")
    monkeypatch.setenv("TMDB_ATTRIBUTION_ACKNOWLEDGED","true")
    monkeypatch.setenv("TMDB_LOGO_ACKNOWLEDGED","true")
    monkeypatch.delenv("CINESENSE_DATABASE_URL",raising=False)
    monkeypatch.delenv("DATABASE_URL",raising=False)
    monkeypatch.delenv("SPRING_DATASOURCE_URL",raising=False)
    result=cli.run(Namespace(operation="discover",execute=False,limit=5,page=1,language="en-US"))
    assert result["mode"] == "dry-run" and result["fetched"] == 0
    database.assert_not_called()
