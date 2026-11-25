from __future__ import annotations

import argparse
import json
import os
import sys

from data_platform.normalization.tmdb import NormalizationError, normalize_movie
from data_platform.policy import PolicyError, require_provider_access, require_persistence
from data_platform.providers.tmdb.client import TmdbConfig, TmdbProvider
from data_platform.database import database_connection
from data_platform.persistence.ingestion_repository import IngestionRepository


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="cinesense-data", description="Bounded CineSense movie catalog ingestion")
    commands = root.add_subparsers(dest="provider", required=True)
    tmdb = commands.add_parser("tmdb", help="Use The Movie Database API")
    operations = tmdb.add_subparsers(dest="operation", required=True)
    for name in ("discover", "search"):
        command = operations.add_parser(name)
        command.add_argument("--limit", type=int, default=20)
        command.add_argument("--page", type=int, default=1)
        command.add_argument("--language", default="en-US")
        if name == "search":
            command.add_argument("--query", required=True)
        command.add_argument("--execute", action="store_true", help="Persist records after the source-policy gate passes")
        command.add_argument("--dry-run", action="store_true", help="Explicitly select read-only planning mode (the default)")
    genres = operations.add_parser("genres")
    genres.add_argument("--language", default="en")
    genres.add_argument("--execute", action="store_true")
    genres.add_argument("--dry-run", action="store_true")
    retry = operations.add_parser("retry-failures")
    retry.add_argument("--limit", type=int, default=20)
    retry.add_argument("--execute", action="store_true")
    retry.add_argument("--dry-run", action="store_true")
    return root


def _limit(value: int) -> None:
    if not 1 <= value <= 250:
        raise ValueError("--limit must be between 1 and 250.")


def run(args: argparse.Namespace) -> dict[str, object]:
    _limit(args.limit) if hasattr(args, "limit") else None
    if args.operation == "retry-failures":
        require_provider_access()
        if not args.execute:
            return {"operation": "retry-failures", "mode": "dry-run", "failures": 0,
                    "message": "No database reads or writes in dry-run mode; failure count not assessed."}
        policy=require_persistence()
        config=TmdbConfig.from_environment()
        provider=TmdbProvider(config)
        connection=database_connection()
        try:
            repo=IngestionRepository(connection)
            with connection.transaction():
                source=repo.ensure_source(policy="PERMITTED",attribution=policy.attribution,terms_url=policy.terms_uri)
                run_id=repo.create_run(source,"RETRY_FAILURES",{"limit":args.limit,"terms_uri":policy.terms_uri,"policy_reviewed_on":policy.policy_reviewed_on})
                with connection.cursor() as cursor:
                    cursor.execute("SELECT DISTINCT provider_external_id FROM ingestion_failures WHERE catalog_source_id=%s AND status='OPEN' AND retryable AND provider_external_id IS NOT NULL ORDER BY provider_external_id LIMIT %s",(source,args.limit))
                    external_ids=[row[0] for row in cursor.fetchall()]
            succeeded=failed=inserted=updated=skipped=0
            for external_id in external_ids:
                try:
                    detail=provider.get_movie(external_id)
                    credits=provider.get_credits(external_id)
                    ids=provider.get_external_ids(external_id)
                    movie,_=normalize_movie(detail,credits,ids,requested_locale="en-US")
                    with connection.transaction():
                        result=repo.ingest_movie(source,movie)
                        connection.execute("UPDATE ingestion_failures SET status='RESOLVED',resolved_at=now(),attempt_count=attempt_count+1 WHERE catalog_source_id=%s AND provider_external_id=%s AND status='OPEN' AND retryable",(source,external_id))
                    inserted += result == "inserted"
                    updated += result == "updated"
                    skipped += result == "skipped"
                    succeeded+=1
                except Exception as exc:
                    with connection.transaction():
                        connection.execute("UPDATE ingestion_failures SET attempt_count=attempt_count+1,error_summary=%s WHERE catalog_source_id=%s AND provider_external_id=%s AND status='OPEN' AND retryable",(str(exc)[:1000],source,external_id))
                    failed+=1
            with connection.transaction():
                repo.finish_run(run_id,status="PARTIAL" if failed else "COMPLETED",pages=0,discovered=len(external_ids),inserted=inserted,updated=updated,skipped=skipped,failed=failed)
            return {"provider":"tmdb","operation":"retry-failures","mode":"execute","attempted":len(external_ids),"succeeded":succeeded,"failed":failed,"run_id":run_id}
        finally:
            provider.close()
            connection.close()
    require_provider_access()
    config = TmdbConfig.from_environment()
    if args.execute:
        policy = require_persistence()
        connection = database_connection()
    else:
        policy = None
        connection = None
        if any(os.getenv(key) for key in ("CINESENSE_DATABASE_URL","DATABASE_URL","SPRING_DATASOURCE_URL")):
            try:
                connection=database_connection()
                connection.execute("SET default_transaction_read_only=on")
            except Exception:
                if connection is not None:
                    connection.close()
                connection=None

    provider = TmdbProvider(config)
    repository = IngestionRepository(connection) if connection is not None else None
    source_id = run_id = None
    pages = inserted = updated = skipped = failed = 0
    job_key = f"{args.operation}:{getattr(args, 'query', '')}:{args.language}"
    if repository and policy:
        with connection.transaction():
            source_id = repository.ensure_source(policy="PERMITTED", attribution=policy.attribution, terms_url=policy.terms_uri)
            job_type = {"discover":"DISCOVER","search":"SEARCH","genres":"GENRES"}[args.operation]
            run_id = repository.create_run(source_id, job_type, {"limit":getattr(args,"limit",None),"page":getattr(args,"page",None),"language":args.language,"usage_scope":policy.usage_scope,"terms_uri":policy.terms_uri,"policy_reviewed_on":policy.policy_reviewed_on})
            with connection.cursor() as cursor:
                cursor.execute("SELECT cursor_state->>'page' FROM ingestion_checkpoints WHERE catalog_source_id=%s AND job_key=%s",(source_id,job_key))
                checkpoint = cursor.fetchone()
                if checkpoint and checkpoint[0]:
                    args.page = max(args.page, int(checkpoint[0]))
    try:
        if args.operation == "genres":
            genres = provider.get_genres(language=args.language)
            if repository and run_id and source_id:
                with connection.transaction():
                    count=repository.ingest_genres(source_id,genres,args.language)
                    repository.add_quality_metrics(run_id,{"records_discovered":len(genres),"records_accepted":count})
                    repository.finish_run(run_id,status="COMPLETED",pages=1,discovered=len(genres),inserted=count,updated=0,skipped=0,failed=len(genres)-count)
            return {"provider": "tmdb", "operation": "genres", "mode": "execute" if args.execute else "dry-run", "fetched": len(genres),
                    "genres": [{"id": row.get("id"), "name": row.get("name")} for row in genres],"persisted":bool(args.execute),"run_id":run_id}
        page = args.page
        remaining = args.limit
        results: list[dict[str, object]] = []
        seen_movie_ids: set[str] = set()
        total_pages: int | None = None
        while remaining > 0 and (total_pages is None or page <= total_pages):
            batch = provider.discover_movies(page=page, language=args.language) if args.operation == "discover" else provider.search_movies(query=args.query, page=page, language=args.language)
            total_pages = batch.total_pages
            candidates = batch.results[:remaining]
            normalized_movies = []
            page_failures = []
            page_duplicate_count=0
            for candidate in candidates:
                raw_id = candidate.get("id")
                if raw_id is None:
                    results.append({"id": None, "status": "rejected", "reason": "missing provider movie id"})
                    page_failures.append((None,"VALIDATION","missing provider movie id",False))
                    continue
                if str(raw_id) in seen_movie_ids:
                    results.append({"id":str(raw_id),"status":"potential_duplicate","reason":"duplicate provider ID in fetched pages"})
                    page_duplicate_count+=1
                    continue
                seen_movie_ids.add(str(raw_id))
                try:
                    movie_id = str(raw_id)
                    details = provider.get_movie(movie_id, language=args.language)
                    credits = provider.get_credits(movie_id, language=args.language)
                    external_ids = provider.get_external_ids(movie_id)
                    movie, warnings = normalize_movie(details, credits, external_ids, requested_locale=args.language)
                    normalized_movies.append(movie)
                    record={"id": movie.provider_movie_id, "title": movie.title, "status": "valid", "warnings": warnings,
                            "payload_sha256": movie.detail_payload_sha256}
                    if repository and not args.execute:
                        record.update(repository.preview_movie(movie))
                    results.append(record)
                except NormalizationError as exc:
                    results.append({"id": str(raw_id), "status": "rejected", "reason": str(exc)})
                    page_failures.append((str(raw_id),"VALIDATION",str(exc),False))
                except Exception as exc:
                    # Provider exceptions are already sanitized and never contain response bodies.
                    results.append({"id": str(raw_id), "status": "failed", "reason": str(exc)})
                    page_failures.append((str(raw_id),"PROVIDER",str(exc)[:1000],True))
            if repository and run_id and source_id:
                with connection.transaction():
                    last_id = None
                    page_inserted = 0
                    page_updated = 0
                    page_skipped = page_duplicate_count
                    for movie in normalized_movies:
                        result = repository.ingest_movie(source_id,movie)
                        page_inserted += result == "inserted"
                        page_updated += result == "updated"
                        page_skipped += result == "skipped"
                        last_id = movie.provider_movie_id
                    for external_id,category,summary,retryable in page_failures:
                        with connection.cursor() as cursor:
                            cursor.execute("""INSERT INTO ingestion_failures(run_id,catalog_source_id,provider_external_id,
                                processing_stage,failure_category,error_summary,retryable) VALUES (%s,%s,%s,'movie',%s,%s,%s)""",
                                (run_id,source_id,external_id,"PROVIDER" if category=="PROVIDER" else "VALIDATION",summary,retryable))
                    repository.save_checkpoint(source_id,job_key,page+1,run_id,last_id)
                    repository.add_quality_metrics(run_id,{
                        "records_discovered":len(candidates),"records_accepted":len(normalized_movies),
                        "records_rejected":sum(item[1] == "VALIDATION" for item in page_failures),
                        "records_failed":sum(item[1] == "PROVIDER" for item in page_failures),
                        "invalid_dates":sum("date" in item[2].lower() for item in page_failures),
                        "missing_fields":sum(len(row.get("warnings",[])) for row in results if row.get("status")=="valid"),
                        "duplicate_identities":page_updated+page_skipped,
                        "source_mapping_failures":0,
                        "missing_credits":sum(not item.credits for item in normalized_movies),
                        "missing_release_dates":sum(item.release_date is None for item in normalized_movies),
                    })
                    with connection.cursor() as cursor:
                        cursor.execute("UPDATE ingestion_runs SET pages_processed=pages_processed+1,records_discovered=records_discovered+%s,records_inserted=records_inserted+%s,records_updated=records_updated+%s,records_skipped=records_skipped+%s,records_failed=records_failed+%s WHERE id=%s",(len(candidates),page_inserted,page_updated,page_skipped,len(page_failures),run_id))
                    inserted += page_inserted
                    updated += page_updated
                    skipped += page_skipped
                pages += 1
            remaining -= len(candidates)
            page += 1
            if not candidates:
                break
        if repository and run_id:
            failed = sum(row["status"] in ("failed","rejected") for row in results)
            with connection.transaction():
                repository.finish_run(run_id,status="PARTIAL" if failed else "COMPLETED",pages=pages,discovered=len(results),inserted=inserted,updated=updated,skipped=skipped,failed=failed)
        return {"provider": "tmdb", "operation": args.operation, "mode": "execute" if args.execute else "dry-run", "fetched": len(results),
                "valid": sum(row["status"] == "valid" for row in results),
                "rejected": sum(row["status"] == "rejected" for row in results),
                "failed": sum(row["status"] == "failed" for row in results), "potential_duplicates":sum(row["status"]=="potential_duplicate" for row in results), "results": results,
                "would_insert":sum(row.get("would")=="insert" for row in results),
                "would_update":sum(row.get("would")=="update" for row in results),
                "would_skip":sum(row.get("would")=="skip" for row in results),
                "database_duplicate_candidates":sum(len(row.get("duplicate_candidates",[])) for row in results),
                "database_assessment":"read-only" if connection is not None and not args.execute else ("not configured/unavailable" if not args.execute else "persisted"),
                "inserted": inserted,"updated":updated,"skipped":skipped,"run_id":run_id,
                "persistence": "enabled" if args.execute else "disabled; dry-run never writes"}
    except Exception as exc:
        if repository and run_id and connection is not None:
            with connection.transaction():
                repository.finish_run(run_id,status="FAILED",pages=pages,discovered=len(results) if 'results' in locals() else 0,
                    inserted=inserted,updated=updated,skipped=skipped,failed=failed,failure_summary=str(exc)[:1000])
        raise
    finally:
        provider.close()
        if connection is not None:
            connection.close()


def main() -> None:
    try:
        args = parser().parse_args()
        print(json.dumps(run(args), ensure_ascii=False, indent=2))
    except (PolicyError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
