# Data ingestion diagrams

These diagrams describe the Phase 3 data platform. They deliberately stop at canonical source assertions; semantic document generation and recommendation retrieval are later phases.

## Provider adapter boundary

```mermaid
flowchart LR
  Pipeline[Provider-independent ingestion CLI] --> Contract[MovieProvider contract]
  Contract --> TMDB[TMDB adapter]
  Contract -. future adapter .-> Next[Future provider]
  TMDB --> HTTP[HTTPX timeout / bounded retry / Retry-After / pacing]
  HTTP --> Endpoint[Official TMDB API]
```

## Ingestion lifecycle

```mermaid
stateDiagram-v2
  [*] --> PolicyCheck
  PolicyCheck --> DryRun: default / no DB writes
  PolicyCheck --> Discover: --execute + explicit source policy
  Discover --> Normalize
  Normalize --> PersistPage: valid records + sanitized failures
  Normalize --> Quarantine: invalid records
  PersistPage --> Checkpoint: same transaction
  Checkpoint --> Discover: next bounded page
  Checkpoint --> Complete: no more requested records
  PersistPage --> Rollback: database error
  Rollback --> Discover: saved cursor unchanged
  Complete --> [*]
```

## Failure recovery and provenance

```mermaid
flowchart TD
  Candidate --> Fetch[Fetch detail / credits / IDs]
  Fetch -->|Provider or schema error| Failure[Sanitized ingestion_failures row]
  Fetch -->|Valid| Source[Stable provider source_record]
  Source --> Evidence[Field evidence locator + payload hash]
  Evidence --> Prov[PROVIDER assertion_provenance]
  Prov --> Claim[Canonical field assertion]
  Claim --> Commit[Page transaction commits with cursor]
  Failure --> Retry[Retry by external ID in a later run]
```

The retry table and schema support individual-ID recovery, but the Phase 3 CLI's `retry-failures` execution is intentionally not enabled until its bounded retry workflow is complete.
