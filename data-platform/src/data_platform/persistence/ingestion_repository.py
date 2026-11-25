from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from data_platform.contracts.models import NormalizedMovie
from data_platform.deduplication.scoring import candidate_score
from data_platform.normalization.tmdb import canonical_payload_hash, normalize_search_text


class IngestionRepository:
    """Persists one normalized movie and its field-level provider evidence atomically."""

    def __init__(self, connection: Connection[Any]):
        self.connection = connection

    def ensure_source(self, *, policy: str, attribution: str, terms_url: str) -> str:
        if policy != "PERMITTED":
            raise ValueError("TMDB source policy must be explicitly PERMITTED before persistence.")
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute("""INSERT INTO catalog_sources(source_key,display_name,source_type,base_uri,attribution,
                license_name,terms_uri,content_policy) VALUES ('tmdb','The Movie Database (TMDB)',
                'OFFICIAL_PROVIDER','https://api.themoviedb.org/3',%s,'TMDB API terms of use',%s,%s)
                ON CONFLICT(source_key) DO UPDATE SET attribution=excluded.attribution,
                terms_uri=excluded.terms_uri,content_policy=excluded.content_policy,updated_at=now()
                RETURNING id::text""", (attribution, terms_url, policy))
            return cur.fetchone()["id"]

    def preview_movie(self, movie: NormalizedMovie) -> dict[str, Any]:
        revision=hashlib.sha256("".join((movie.detail_payload_sha256,movie.credits_payload_sha256 or "",movie.external_ids_payload_sha256 or "")).encode()).digest()
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT sr.payload_sha256,msl.movie_id::text FROM catalog_sources cs
                JOIN source_records sr ON sr.catalog_source_id=cs.id LEFT JOIN movie_source_links msl ON msl.source_record_id=sr.id
                WHERE cs.source_key='tmdb' AND sr.entity_type='MOVIE' AND sr.external_id=%s""",(movie.provider_movie_id,))
            existing=cur.fetchone()
            if existing:
                same=existing["payload_sha256"]==revision
                return {"would":"skip" if same else "update","existing_movie_id":existing["movie_id"],"duplicate_candidates":[]}
            year=movie.release_date.year if movie.release_date else None
            cur.execute("""SELECT mt.movie_id::text,mt.title,
                (SELECT value_date FROM movie_fact_assertions mf WHERE mf.movie_id=mt.movie_id AND mf.fact_key='RELEASE_DATE' AND mf.valid_to IS NULL ORDER BY mf.valid_from DESC LIMIT 1) AS release_date
                FROM movie_titles mt WHERE mt.title_type='PRIMARY' AND mt.locale=%s ORDER BY similarity(mt.normalized_title,%s) DESC LIMIT 50""",
                (movie.locale,normalize_search_text(movie.title).lower()))
            candidates=[]
            for row in cur.fetchall():
                existing_year=row["release_date"].year if row["release_date"] else None
                score,signals=candidate_score(movie.title,year,row["title"],existing_year)
                if score>=0.62 and signals["title_similarity"]>=0.65:
                    candidates.append({"movie_id":row["movie_id"],"title":row["title"],"score":score,"signals":signals})
            return {"would":"insert","existing_movie_id":None,"duplicate_candidates":candidates}

    def create_run(self, source_id: str, job_type: str, scope: dict[str, Any]) -> str:
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute("INSERT INTO ingestion_runs(catalog_source_id,job_type,status,requested_scope) VALUES (%s,%s,'RUNNING',%s) RETURNING id::text",
                        (source_id, job_type, json.dumps(scope)))
            return cur.fetchone()["id"]

    def save_checkpoint(self, source_id: str, job_key: str, page: int, run_id: str, last_id: str | None) -> None:
        with self.connection.cursor() as cur:
            cur.execute("""INSERT INTO ingestion_checkpoints(catalog_source_id,job_key,cursor_state,last_successful_external_id,run_id)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT(catalog_source_id,job_key) DO UPDATE SET
                cursor_state=excluded.cursor_state,last_successful_external_id=excluded.last_successful_external_id,
                run_id=excluded.run_id,updated_at=now()""",(source_id,job_key,json.dumps({"page":page}),last_id,run_id))

    def finish_run(self, run_id: str, *, status: str, pages: int, discovered: int, inserted: int,
                   updated: int, skipped: int, failed: int, failure_summary: str | None = None) -> None:
        with self.connection.cursor() as cur:
            cur.execute("""UPDATE ingestion_runs SET status=%s,finished_at=now(),pages_processed=%s,
                records_discovered=%s,records_inserted=%s,records_updated=%s,records_skipped=%s,
                records_failed=%s,failure_summary=%s WHERE id=%s AND status='RUNNING'""",
                (status,pages,discovered,inserted,updated,skipped,failed,failure_summary,run_id))

    def add_quality_metrics(self, run_id: str, metrics: dict[str, int]) -> None:
        with self.connection.cursor() as cur:
            for key, value in metrics.items():
                cur.execute("""INSERT INTO ingestion_quality_metrics(run_id,metric_key,metric_value)
                    VALUES (%s,%s,%s) ON CONFLICT(run_id,metric_key) DO UPDATE SET
                    metric_value=ingestion_quality_metrics.metric_value+excluded.metric_value,updated_at=now()""",
                    (run_id,key,max(0,int(value))))

    def ingest_movie(self, source_id: str, movie: NormalizedMovie) -> str:
        # The caller commits the enclosing transaction at the page boundary with its checkpoint.
        revision_hash = hashlib.sha256("".join((movie.detail_payload_sha256, movie.credits_payload_sha256 or "", movie.external_ids_payload_sha256 or "")).encode()).digest()
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id::text,encode(payload_sha256,'hex') AS payload_hash FROM source_records WHERE catalog_source_id=%s AND entity_type='MOVIE' AND external_id=%s",(source_id,movie.provider_movie_id))
            existing_record = cur.fetchone()
            revision_changed = existing_record is None or existing_record["payload_hash"] != revision_hash.hex()
            cur.execute("""INSERT INTO source_records(catalog_source_id,entity_type,external_id,source_uri,
                source_revision,payload_sha256) VALUES (%s,'MOVIE',%s,%s,%s,%s)
                ON CONFLICT(catalog_source_id,entity_type,external_id) DO UPDATE SET source_uri=excluded.source_uri,
                retrieved_at=now(),source_revision=excluded.source_revision,payload_sha256=excluded.payload_sha256
                RETURNING id::text""", (source_id,movie.provider_movie_id,movie.source_uri,revision_hash.hex(),revision_hash))
            source_record = cur.fetchone()["id"]
            cur.execute("SELECT movie_id::text FROM movie_source_links WHERE source_record_id=%s", (source_record,))
            row = cur.fetchone()
            inserted = row is None
            if inserted:
                self._record_identity_candidates(cur,source_record,movie)
                cur.execute("INSERT INTO movies DEFAULT VALUES RETURNING id::text")
                movie_id = cur.fetchone()["id"]
                provenance = self._provenance(source_record,"movie.identity",movie.detail_payload_sha256)
                cur.execute("INSERT INTO movie_source_links(source_record_id,movie_id,linked_by_provenance_id) VALUES (%s,%s,%s)",(source_record,movie_id,provenance))
            else:
                movie_id = row["movie_id"]
            if revision_changed:
                cur.execute("UPDATE movie_semantic_documents SET stale=true,stale_marked_at=now(),stale_reason='provider_catalog_change' WHERE movie_id=%s AND stale=false",(movie_id,))
            self._title(source_record,movie_id,movie)
            self._fact(source_record,movie_id,"RELEASE_DATE",movie.release_date.isoformat() if movie.release_date else None,movie.detail_payload_sha256)
            self._fact(source_record,movie_id,"RUNTIME_MINUTES",movie.runtime_minutes,movie.detail_payload_sha256)
            self._fact(source_record,movie_id,"ORIGINAL_LANGUAGE",movie.original_language,movie.detail_payload_sha256)
            self._fact(source_record,movie_id,"ADULT_CONTENT",movie.adult_content,movie.detail_payload_sha256)
            self._fact(source_record,movie_id,"STATUS",movie.status,movie.detail_payload_sha256)
            self._fact(source_record,movie_id,"BUDGET",movie.budget,movie.detail_payload_sha256)
            self._fact(source_record,movie_id,"REVENUE",movie.revenue,movie.detail_payload_sha256)
            self._text(source_record,movie_id,"OVERVIEW",movie.overview,movie.locale,movie.detail_payload_sha256)
            self._text(source_record,movie_id,"TAGLINE",movie.tagline,movie.locale,movie.detail_payload_sha256)
            self._genres(source_id,source_record,movie_id,movie,revision_changed)
            self._countries(source_record,movie_id,movie,revision_changed)
            self._companies(source_id,source_record,movie_id,movie,revision_changed)
            self._people_and_credits(source_id,source_record,movie_id,movie,revision_changed)
            self._external_ids(source_record,movie_id,movie)
            if revision_changed:
                cur.execute("UPDATE movies SET updated_at=now() WHERE id=%s",(movie_id,))
            return "inserted" if inserted else ("updated" if revision_changed else "skipped")

    @staticmethod
    def _record_identity_candidates(cur: Any, source_record: str, movie: NormalizedMovie) -> None:
        year=movie.release_date.year if movie.release_date else None
        cur.execute("""SELECT mt.movie_id::text,mt.title,
            (SELECT value_date FROM movie_fact_assertions mf WHERE mf.movie_id=mt.movie_id AND mf.fact_key='RELEASE_DATE' AND mf.valid_to IS NULL ORDER BY mf.valid_from DESC LIMIT 1) AS release_date
            FROM movie_titles mt WHERE mt.title_type='PRIMARY' AND mt.locale=%s ORDER BY similarity(mt.normalized_title,%s) DESC LIMIT 50""",
            (movie.locale,normalize_search_text(movie.title).lower()))
        for row in cur.fetchall():
            existing_year=row["release_date"].year if row["release_date"] else None
            score,signals=candidate_score(movie.title,year,row["title"],existing_year)
            if score >= 0.62 and signals["title_similarity"] >= 0.65:
                cur.execute("INSERT INTO identity_match_candidates(incoming_source_record_id,candidate_movie_id,match_score,match_signals) VALUES (%s,%s,%s,%s) ON CONFLICT(incoming_source_record_id,candidate_movie_id) DO NOTHING",
                    (source_record,row["movie_id"],score,json.dumps(signals)))

    def ingest_genres(self, source_id: str, genres: list[dict[str, Any]], language: str) -> int:
        digest=canonical_payload_hash({"genres":genres,"language":language})
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id::text FROM taxonomy_categories WHERE category_key='genre'")
            category=cur.fetchone()["id"]
            count=0
            for item in genres:
                provider_id=str(item.get("id", ""))
                name=" ".join(unicodedata.normalize("NFKC",str(item.get("name", ""))).split())
                if not provider_id.isdigit() or not name:
                    continue
                cur.execute("""INSERT INTO source_records(catalog_source_id,entity_type,external_id,source_uri,source_revision,payload_sha256)
                    VALUES (%s,'GENRE',%s,'https://api.themoviedb.org/3/genre/movie/list',%s,%s)
                    ON CONFLICT(catalog_source_id,entity_type,external_id) DO UPDATE SET retrieved_at=now(),source_revision=excluded.source_revision,payload_sha256=excluded.payload_sha256 RETURNING id::text""",
                    (source_id,provider_id,digest,bytes.fromhex(digest)))
                source_record=cur.fetchone()["id"]
                provenance=self._provenance(source_record,"genre.name",digest)
                cur.execute("INSERT INTO taxonomy_terms(category_id,term_key,display_name) VALUES (%s,%s,%s) ON CONFLICT(category_id,term_key) DO UPDATE SET display_name=excluded.display_name RETURNING id::text",
                    (category,f"tmdb-{provider_id}",name))
                term=cur.fetchone()["id"]
                cur.execute("INSERT INTO taxonomy_source_links(source_record_id,taxonomy_term_id,linked_by_provenance_id) VALUES (%s,%s,%s) ON CONFLICT(source_record_id) DO UPDATE SET taxonomy_term_id=excluded.taxonomy_term_id,linked_by_provenance_id=excluded.linked_by_provenance_id",
                    (source_record,term,provenance))
                count+=1
            return count

    def _evidence(self, source_record: str, key: str, locator: str) -> str:
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute("INSERT INTO evidence_records(source_record_id,evidence_key,locator) VALUES (%s,%s,%s) ON CONFLICT(source_record_id,evidence_key,locator) DO UPDATE SET observed_at=evidence_records.observed_at RETURNING id::text",(source_record,key,locator))
            return cur.fetchone()["id"]

    def _provenance(self, source_record: str, key: str, payload_hash: str, locator_suffix: str = "") -> str:
        evidence = self._evidence(source_record,key,f"json-field:{key};sha256:{payload_hash}{locator_suffix}")
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute("INSERT INTO assertion_provenance(evidence_record_id,origin,review_state) VALUES (%s,'PROVIDER','UNREVIEWED') ON CONFLICT(evidence_record_id) WHERE evidence_record_id IS NOT NULL DO UPDATE SET evidence_record_id=excluded.evidence_record_id RETURNING id::text",(evidence,))
            return cur.fetchone()["id"]

    def _title(self, source: str, movie_id: str, movie: NormalizedMovie) -> None:
        key = "movie.title"
        prov = self._provenance(source,key,movie.detail_payload_sha256)
        normalized = normalize_search_text(movie.title).lower()
        with self.connection.cursor() as cur:
            cur.execute("UPDATE movie_titles SET title_type='ALTERNATIVE' WHERE movie_id=%s AND locale=%s AND title_type='PRIMARY' AND title<>%s",(movie_id,movie.locale,movie.title))
            cur.execute("UPDATE movie_titles SET title=%s,normalized_title=%s,provenance_id=%s WHERE movie_id=%s AND locale=%s AND title_type='PRIMARY'",(movie.title,normalized,prov,movie_id,movie.locale))
            cur.execute("INSERT INTO movie_titles(movie_id,title,normalized_title,locale,title_type,provenance_id) VALUES (%s,%s,%s,%s,'PRIMARY',%s) ON CONFLICT(movie_id,title,normalized_title,locale,title_type,provenance_id) DO NOTHING",(movie_id,movie.title,normalized,movie.locale,prov))
            if movie.original_title and movie.original_title != movie.title:
                original_prov = self._provenance(source,"movie.original_title",movie.detail_payload_sha256)
                cur.execute("INSERT INTO movie_titles(movie_id,title,normalized_title,locale,title_type,provenance_id) VALUES (%s,%s,%s,%s,'ORIGINAL',%s) ON CONFLICT(movie_id,title,normalized_title,locale,title_type,provenance_id) DO NOTHING",(movie_id,movie.original_title,normalize_search_text(movie.original_title).lower(),movie.locale,original_prov))

    def _fact(self, source: str, movie_id: str, field: str, value: Any, digest: str) -> None:
        if value is None:
            return
        prov = self._provenance(source,f"movie.{field.lower()}",digest)
        col = {"RELEASE_DATE":"value_date","RUNTIME_MINUTES":"value_integer","ORIGINAL_LANGUAGE":"value_text","ADULT_CONTENT":"value_boolean","STATUS":"value_text","BUDGET":"value_numeric","REVENUE":"value_numeric"}[field]
        with self.connection.cursor() as cur:
            cur.execute(f"UPDATE movie_fact_assertions SET valid_to=now() WHERE movie_id=%s AND fact_key=%s AND valid_to IS NULL AND provenance_id<>%s AND provenance_id IN (SELECT ap.id FROM assertion_provenance ap JOIN evidence_records er ON er.id=ap.evidence_record_id JOIN source_records sr ON sr.id=er.source_record_id WHERE sr.catalog_source_id=(SELECT catalog_source_id FROM source_records WHERE id=%s))",(movie_id,field,prov,source))
            cur.execute(f"INSERT INTO movie_fact_assertions(movie_id,fact_key,{col},provenance_id) VALUES (%s,%s,%s,%s) ON CONFLICT(movie_id,fact_key,provenance_id) DO NOTHING",(movie_id,field,value,prov))

    def _text(self, source: str, movie_id: str, field: str, value: str | None, locale: str, digest: str) -> None:
        if not value:
            return
        prov=self._provenance(source,f"movie.{field.lower()}",digest)
        value_hash=hashlib.sha256(value.encode("utf-8")).digest()
        with self.connection.cursor() as cur:
            cur.execute("UPDATE movie_text_assertions SET valid_to=now() WHERE movie_id=%s AND text_type=%s AND locale=%s AND valid_to IS NULL AND provenance_id<>%s AND provenance_id IN (SELECT ap.id FROM assertion_provenance ap JOIN evidence_records er ON er.id=ap.evidence_record_id JOIN source_records sr ON sr.id=er.source_record_id WHERE sr.catalog_source_id=(SELECT catalog_source_id FROM source_records WHERE id=%s))",(movie_id,field,locale,prov,source))
            cur.execute("INSERT INTO movie_text_assertions(movie_id,text_type,locale,text_value,content_sha256,provenance_id,source_asserted_at) VALUES (%s,%s,%s,%s,%s,%s,now()) ON CONFLICT(movie_id,text_type,locale,provenance_id) DO UPDATE SET valid_to=NULL",(movie_id,field,locale,value,value_hash,prov))

    def _genres(self, catalog_source: str, movie_source: str, movie_id: str, movie: NormalizedMovie, revision_changed: bool) -> None:
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id::text FROM taxonomy_categories WHERE category_key='genre'")
            category = cur.fetchone()["id"]
            if revision_changed:
                cur.execute("UPDATE movie_taxonomy_assertions SET valid_to=now() WHERE movie_id=%s AND valid_to IS NULL AND provenance_id IN (SELECT ap.id FROM assertion_provenance ap JOIN evidence_records er ON er.id=ap.evidence_record_id JOIN source_records sr ON sr.id=er.source_record_id WHERE sr.catalog_source_id=%s)",(movie_id,catalog_source))
            for item in movie.genres:
                cur.execute("""INSERT INTO source_records(catalog_source_id,entity_type,external_id,source_uri,source_revision,payload_sha256)
                    VALUES (%s,'GENRE',%s,%s,%s,%s) ON CONFLICT(catalog_source_id,entity_type,external_id) DO UPDATE SET retrieved_at=now(),source_revision=excluded.source_revision,payload_sha256=excluded.payload_sha256 RETURNING id::text""",(catalog_source,item.provider_id,movie.source_uri,movie.detail_payload_sha256,bytes.fromhex(movie.detail_payload_sha256)))
                genre_record=cur.fetchone()["id"]
                prov=self._provenance(genre_record,"genre.name",movie.detail_payload_sha256)
                cur.execute("INSERT INTO taxonomy_terms(category_id,term_key,display_name) VALUES (%s,%s,%s) ON CONFLICT(category_id,term_key) DO UPDATE SET display_name=excluded.display_name RETURNING id::text",(category,f"tmdb-{item.provider_id}",item.name))
                term=cur.fetchone()["id"]
                cur.execute("INSERT INTO taxonomy_source_links(source_record_id,taxonomy_term_id,linked_by_provenance_id) VALUES (%s,%s,%s) ON CONFLICT(source_record_id) DO UPDATE SET taxonomy_term_id=excluded.taxonomy_term_id,linked_by_provenance_id=excluded.linked_by_provenance_id",(genre_record,term,prov))
                evidence=self._provenance(movie_source,f"movie.genre.{item.provider_id}",movie.detail_payload_sha256)
                cur.execute("INSERT INTO movie_taxonomy_assertions(movie_id,taxonomy_term_id,provenance_id) VALUES (%s,%s,%s) ON CONFLICT(movie_id,taxonomy_term_id,provenance_id) DO NOTHING",(movie_id,term,evidence))

    def _countries(self, source: str, movie_id: str, movie: NormalizedMovie, revision_changed: bool) -> None:
        with self.connection.cursor() as cur:
            prov=self._provenance(source,"movie.production_countries",movie.detail_payload_sha256)
            if revision_changed:
                cur.execute("UPDATE movie_production_countries SET valid_to=now() WHERE movie_id=%s AND valid_to IS NULL AND provenance_id IN (SELECT ap.id FROM assertion_provenance ap JOIN evidence_records er ON er.id=ap.evidence_record_id WHERE er.source_record_id=%s) AND provenance_id<>%s",(movie_id,source,prov))
            for country in movie.production_countries:
                cur.execute("INSERT INTO movie_production_countries(movie_id,country_code,provenance_id) VALUES (%s,%s,%s) ON CONFLICT(movie_id,country_code,provenance_id) DO NOTHING",(movie_id,country.code,prov))

    def _companies(self, catalog_source: str, movie_source: str, movie_id: str, movie: NormalizedMovie, revision_changed: bool) -> None:
        if revision_changed:
            with self.connection.cursor() as cur:
                cur.execute("UPDATE movie_production_companies SET valid_to=now() WHERE movie_id=%s AND valid_to IS NULL AND provenance_id IN (SELECT ap.id FROM assertion_provenance ap JOIN evidence_records er ON er.id=ap.evidence_record_id WHERE er.source_record_id=%s)",(movie_id,movie_source))
        for company in movie.production_companies:
            with self.connection.cursor(row_factory=dict_row) as cur:
                cur.execute("""INSERT INTO source_records(catalog_source_id,entity_type,external_id,source_uri,source_revision,payload_sha256)
                    VALUES (%s,'COMPANY',%s,%s,%s,%s) ON CONFLICT(catalog_source_id,entity_type,external_id) DO UPDATE SET
                    source_uri=excluded.source_uri,retrieved_at=now(),source_revision=excluded.source_revision,payload_sha256=excluded.payload_sha256 RETURNING id::text""",
                    (catalog_source,company.provider_id,movie.source_uri,movie.detail_payload_sha256,bytes.fromhex(movie.detail_payload_sha256)))
                company_source=cur.fetchone()["id"]
                prov=self._provenance(company_source,"company.name",movie.detail_payload_sha256)
                cur.execute("SELECT production_company_id::text FROM production_company_source_links WHERE source_record_id=%s",(company_source,))
                link=cur.fetchone()
                if link:
                    company_id=link["production_company_id"]
                else:
                    cur.execute("INSERT INTO production_companies DEFAULT VALUES RETURNING id::text")
                    company_id=cur.fetchone()["id"]
                    cur.execute("INSERT INTO production_company_source_links(source_record_id,production_company_id,linked_by_provenance_id) VALUES (%s,%s,%s)",(company_source,company_id,prov))
                cur.execute("UPDATE production_company_names SET name=%s,normalized_name=%s,provenance_id=%s WHERE production_company_id=%s AND locale='und'",
                    (company.name,normalize_search_text(company.name).lower(),prov,company_id))
                cur.execute("INSERT INTO production_company_names(production_company_id,name,normalized_name,provenance_id) VALUES (%s,%s,%s,%s) ON CONFLICT(production_company_id,normalized_name,locale,provenance_id) DO NOTHING",
                    (company_id,company.name,normalize_search_text(company.name).lower(),prov))
                movie_prov=self._provenance(movie_source,f"movie.production_company.{company.provider_id}",movie.detail_payload_sha256)
                cur.execute("INSERT INTO movie_production_companies(movie_id,production_company_id,provenance_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",(movie_id,company_id,movie_prov))

    def _people_and_credits(self, catalog_source: str, movie_source: str, movie_id: str, movie: NormalizedMovie, revision_changed: bool) -> None:
        digest=movie.credits_payload_sha256 or movie.detail_payload_sha256
        with self.connection.cursor(row_factory=dict_row) as cur:
            if revision_changed:
                cur.execute("UPDATE movie_credits SET valid_to=now() WHERE movie_id=%s AND valid_to IS NULL AND provenance_id IN (SELECT ap.id FROM assertion_provenance ap JOIN evidence_records er ON er.id=ap.evidence_record_id WHERE er.source_record_id=%s)",(movie_id,movie_source))
            for credit in movie.credits:
                cur.execute("""INSERT INTO source_records(catalog_source_id,entity_type,external_id,source_uri,source_revision,payload_sha256)
                    VALUES (%s,'PERSON',%s,%s,%s,%s) ON CONFLICT(catalog_source_id,entity_type,external_id) DO UPDATE SET source_uri=excluded.source_uri,retrieved_at=now(),source_revision=excluded.source_revision,payload_sha256=excluded.payload_sha256 RETURNING id::text""",(catalog_source,credit.provider_person_id,movie.source_uri+"/credits",digest,bytes.fromhex(digest)))
                person_source=cur.fetchone()["id"]
                person_prov=self._provenance(person_source,"person.name",digest)
                cur.execute("SELECT person_id::text FROM person_source_links WHERE source_record_id=%s",(person_source,))
                person_link=cur.fetchone()
                if person_link:
                    person_id=person_link["person_id"]
                else:
                    cur.execute("INSERT INTO people DEFAULT VALUES RETURNING id::text")
                    person_id=cur.fetchone()["id"]
                    cur.execute("INSERT INTO person_source_links(source_record_id,person_id,linked_by_provenance_id) VALUES (%s,%s,%s)",(person_source,person_id,person_prov))
                cur.execute("UPDATE person_names SET name_type='ALTERNATIVE' WHERE person_id=%s AND locale='und' AND name_type='PRIMARY' AND name<>%s",(person_id,credit.name))
                cur.execute("UPDATE person_names SET name=%s,normalized_name=%s,provenance_id=%s WHERE person_id=%s AND locale='und' AND name_type='PRIMARY'",(credit.name,normalize_search_text(credit.name).lower(),person_prov,person_id))
                cur.execute("INSERT INTO person_names(person_id,name,normalized_name,locale,name_type,provenance_id) VALUES (%s,%s,%s,'und','PRIMARY',%s) ON CONFLICT(person_id,normalized_name,locale,name_type,provenance_id) DO NOTHING",(person_id,credit.name,normalize_search_text(credit.name).lower(),person_prov))
                prov=self._provenance(movie_source,"movie.credit",digest,f":{credit.provider_person_id}:{credit.credit_type}:{credit.job}:{credit.billing_order}")
                cur.execute("INSERT INTO movie_credits(movie_id,person_id,credit_type,job,character_name,billing_order,provenance_id) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(movie_id,person_id,credit_type,job,coalesce(character_name,''),coalesce(billing_order,-1),provenance_id) DO NOTHING",(movie_id,person_id,credit.credit_type,credit.job,credit.character_name,credit.billing_order,prov))

    def _external_ids(self, source: str, movie_id: str, movie: NormalizedMovie) -> None:
        digest=movie.external_ids_payload_sha256 or movie.detail_payload_sha256
        for identifier_type, external_id in movie.external_ids.items():
            prov=self._provenance(source,f"movie.external_id.{identifier_type}",digest)
            with self.connection.cursor() as cur:
                cur.execute("INSERT INTO movie_external_identifiers(movie_id,identifier_type,external_id,provenance_id) VALUES (%s,%s,%s,%s) ON CONFLICT(identifier_type,external_id) DO NOTHING",(movie_id,identifier_type,external_id,prov))
