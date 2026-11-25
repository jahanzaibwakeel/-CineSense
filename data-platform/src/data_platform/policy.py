"""Fail-closed checks for provider access and catalog persistence."""
from __future__ import annotations

import os
from dataclasses import dataclass


class PolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourcePolicy:
    usage_scope: str
    policy_reviewed_on: str
    terms_uri: str
    attribution: str


TMDB_TERMS = "https://www.themoviedb.org/documentation/api/terms-of-use"
TMDB_ATTRIBUTION = "This product uses the TMDB API but is not endorsed or certified by TMDB."


def _enabled(env: dict[str, str], key: str) -> bool:
    return env.get(key, "").strip().lower() == "true"


def require_provider_access(env: dict[str, str] | None = None) -> SourcePolicy:
    values = os.environ if env is None else env
    scope = values.get("TMDB_USAGE_SCOPE", "").strip().lower()
    if scope != "non-commercial":
        raise PolicyError("Set TMDB_USAGE_SCOPE=non-commercial only after reviewing the current TMDB API terms for this use.")
    if not _enabled(values, "TMDB_TERMS_ACKNOWLEDGED"):
        raise PolicyError("Review TMDB terms, then set TMDB_TERMS_ACKNOWLEDGED=true before making provider requests.")
    if not _enabled(values, "TMDB_ATTRIBUTION_ACKNOWLEDGED"):
        raise PolicyError("Set TMDB_ATTRIBUTION_ACKNOWLEDGED=true after adding the exact required statement and completing the About/Credits attribution placement.")
    if not _enabled(values, "TMDB_LOGO_ACKNOWLEDGED"):
        raise PolicyError("TMDB's current FAQ requires its official logo for non-commercial use; add the approved logo in About/Credits, then set TMDB_LOGO_ACKNOWLEDGED=true.")
    return SourcePolicy(scope, values.get("TMDB_POLICY_REVIEWED_ON", "not-recorded"), TMDB_TERMS, TMDB_ATTRIBUTION)


def require_persistence(env: dict[str, str] | None = None) -> SourcePolicy:
    values = os.environ if env is None else env
    policy = require_provider_access(values)
    if values.get("TMDB_SOURCE_POLICY", "UNKNOWN").strip().upper() != "PERMITTED":
        raise PolicyError("Persistence is disabled: set TMDB_SOURCE_POLICY=PERMITTED only after verifying that the intended storage and retention comply with current TMDB terms.")
    if not _enabled(values, "TMDB_PERSISTENCE_ACKNOWLEDGED"):
        raise PolicyError("Set TMDB_PERSISTENCE_ACKNOWLEDGED=true only after reviewing retention and redistribution limits for this catalog.")
    return policy
