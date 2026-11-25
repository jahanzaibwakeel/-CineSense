# Delivery phases

1. **Phase 1 — foundation (complete):** repository inspection, architecture, source/rights research, service foundations, and design system.
2. **Phase 2 — database (implemented):** PostgreSQL 17 + pgvector 0.8.7, Flyway, provenance-aware catalog schema, search indexes, readiness checks, and Testcontainers integration tests. See [data dictionary](../DATA_DICTIONARY.md) and [progress](PROGRESS.md).
3. **Phase 3 — data pipeline (implemented, review pending):** rights-gated TMDB adapter, normalization, conservative review candidates, checkpoints, field-level provenance, retries, and validation. No live provider import has been run.
4. **Phase 4 — enrichment:** structured AI enrichment with evidence, verification state, and semantic document versioning.
5. **Phase 5 — embedding:** lazy Hugging Face model adapters, batch embeddings, cache/idempotency, and versioned indexes.
6. **Phase 6 — MLOps workflow:** DVC, MLflow, Prefect, and dataset/model lineage.
7. **Phase 7 — discovery:** query interpretation, hard/preferred/excluded intent, conversational refinement, hybrid retrieval, and reranking.
8. **Phase 8 — grounded explanations:** retrieval augmented responses tied to verified evidence and explicit uncertainty.
9. **Phase 9 — application backend:** authentication, user isolation, sessions, preferences, watchlists, feedback, and APIs.
10. **Phase 10 — product experience:** connect the premium Next.js experience to working APIs; add movie detail, history, collections, group and memory discovery.
11. **Phase 11 — quality/operations:** evaluation gates, Evidently, Prometheus, Grafana, and deployment CI/CD.
12. **Phase 12 — integration:** regression, performance, recovery, security, and documentation closeout.

No real movie data or model weights are bundled. Credentials belong in process environments, local ignored `.env` files loaded by the caller, or managed deployment secrets. Phase 3 includes a configurable adapter and persistence pipeline, but the default policy remains closed until a person reviews current provider terms and permitted storage/retention.
