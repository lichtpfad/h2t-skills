---
title: "Research Artifact Roles, Retention, and Routing"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-26"
milestone: ""
---
# Research Artifact Roles, Retention, and Routing

## Metadata

- Issue: `#71`
- Scope: `h2t-ops:research`
- Status: design
- Date: `2026-05-26`

## Goal

Define a stable local contract for `h2t-ops:research` artifacts so that:

- agents can navigate prior research without scanning ad hoc files;
- machine-readable JSON is the canonical local source of truth;
- Markdown remains a secondary human-review surface;
- routing and lookup work across multiple keys and multiple iterations;
- the local model is compatible with later POS ingestion without forcing POS integration now.

This spec is about **artifact semantics, retention, and navigation structure**. It is not a fetch-provider redesign and not a POS transport spec.

## Non-goals

This wave does **not** include:

- bulk migration of all legacy research artifacts;
- POS ingestion or network sync implementation;
- semantic search infrastructure;
- graph/context-graph implementation;
- redesign of existing providers (`direct`, `jina`, `visual-ocr`, Exa, YouTube, etc.);
- UI work or operator-facing browsing tools.

## Problem

`h2t-ops:research` already produces a growing set of outputs:

- fetch artifacts;
- provider-specific normalized text;
- summaries;
- OCR recovery artifacts;
- author resolution results;
- research-side notes and role docs.

But the current storage semantics are still too loose:

- JSON and Markdown are not sharply separated by role;
- retention policy is not explicit;
- routing identity can drift between URL, canonical URL, query, entity, and project context;
- iterative research has no formal thread/run/synthesis model;
- agents lack a shared, structured navigation layer for prior research work;
- later POS ingestion would be forced to reverse-engineer local storage decisions.

The result is unnecessary re-research, unstable lookup, and a risk of turning the research layer into a directory of files rather than a structured evidence system.

## Design Principles

1. **JSON-first for machine use**
   - Canonical local truth must be machine-readable JSON.

2. **Markdown is presentation, not authority**
   - Markdown may be useful for review and operator reading, but routing and runtime logic must not depend on it.

3. **Identity must separate object types**
   - A document, research thread, run, synthesis, and project attachment are different things and must not share one overloaded key.

4. **Routing must distinguish identity from lookup aliases**
   - Canonical identity is not the same as all searchable aliases.

5. **Research is iterative**
   - Some work is one-shot, but the model must support append-only iteration, superseded syntheses, and unresolved questions.

6. **Provenance is first-class**
   - Claims and syntheses should remain evidence-backed and review-aware.

7. **Indexes are caches, not truth**
   - Shared indexes may accelerate agent navigation, but must be rebuildable from canonical JSON objects.

8. **POS compatibility matters now**
   - Local IDs, roles, and envelopes should be chosen so later POS ingestion is additive, not a rewrite.

## Core Object Model

Local research storage should converge on four canonical object families, plus explicit link objects.

### 1. ResearchDocument

Represents a source/evidence object.

Examples:

- fetched article;
- video transcript source;
- GitHub page/source;
- paper page;
- normalized OCR-backed source document.

This is not the same as a summary or a thread.

### 2. ResearchThread

Represents the question or research line being investigated.

Examples:

- "What is the real current surface of Exa in `h2t-ops:research`?"
- "What evidence exists for LynxCap background and positioning?"
- "What sources support a specific proposal or competitive analysis?"

A thread is the question/context line, not one source.

### 3. ResearchRun

Represents one concrete iteration/pass within a thread.

Examples:

- one query batch;
- one provider combination run;
- one follow-up pass after a previous synthesis;
- one author resolution cascade execution.

A thread can have many runs.

### 4. ResearchSynthesis

Represents a derived conclusion over one or more runs/documents.

Examples:

- accepted synthesis for a project proposal;
- reviewed summary of findings;
- confidence-tagged set of claims backed by evidence refs.

A synthesis is never raw truth by default. It is a derived object, and only becomes the canonical current view when reviewed/accepted.

### 5. Link Objects

Explicit links connect research to the rest of the system.

At minimum:

- `ResearchEntityLink`
- `ProjectResearchLink`

These preserve separation between:

- what was found;
- what question was researched;
- what entity is involved;
- what project/task this informed.

## Artifact Taxonomy

Each canonical object may have multiple local artifacts. Artifact roles must be explicit.

Artifact roles describe **storage/view artifacts associated with an object**.

They do **not** redefine the object's canonical type.

For example:

- `ResearchDocument` remains a document object;
- its associated artifacts may include `metadata`, `normalized_text`, `citation_bundle`, and Markdown mirrors;
- a document must not become ambiguously “a summary” or “a citation bundle” just because those artifact views exist.

### Canonical or Persistent Roles

- `metadata`
  - stable normalized metadata about an object.

- `normalized_text`
  - normalized readable text extracted from the source.

- `citation_bundle`
  - evidence locators, quote-safe references, claim support refs.

- `cache_index`
  - structured navigation/index entries derived from canonical objects.

### Derived or Secondary Roles

- `summary`
  - readable summary view or model-generated synopsis.

- `operator_notes`
  - annotations, review notes, manual observations.

- Markdown mirrors
  - human-readable renders of object state.

### Ephemeral or Provider-Transient Roles

- temp OCR intermediates;
- provider debug payloads;
- transient search result sets;
- crawler noise;
- screenshots or raw traces not intended for long-term truth.

## Canonicality Rules

### Local Truth

In v1:

- **Canonical local truth** = machine-readable JSON artifacts
- **Secondary mirror** = Markdown

### Runtime Rule

Agent/runtime logic must:

- read canonical JSON objects;
- never depend on Markdown parsing for routing, state, or identity.

### Review Rule

Markdown may still be opened:

- for operator review;
- for human-readable notes;
- for presentation or handoff.

But Markdown remains non-authoritative.

## Identity Model

Identity must be type-specific.

### ResearchDocument identity

Preferred primary identity:

- `document_id = hash(canonical_url)`

Fallback:

- `document_id = hash(content_hash + provider + fetched_at bucket)`

Use fallback only when no stable canonical URL exists.

### ResearchDocument update/version rule

In v1, `ResearchDocument` should be treated as the logical source identity, not every historical fetch snapshot.

That means:

- the same stable canonical URL normally resolves to the same `document_id`;
- `content_hash` and `fetched_at` record the observed version/state of that source;
- re-fetching a changed page should update or append document-associated artifacts, not silently create an unrelated logical document.

If exact historical versioning is needed later, it should be introduced as:

- document-version artifacts;
- or explicit version refs linked under the same logical `document_id`.

v1 does **not** require full source-version object modeling.

### ResearchThread identity

Preferred primary identity:

- `thread_id = hash(normalized_question + owner_context + started_at/date_bucket)`

The thread represents the research line, not a single document.

### ResearchRun identity

Preferred primary identity:

- `run_id = hash(thread_id + query + provider_set + run_started_at)`

Runs are append-only iterations under a thread.

### ResearchSynthesis identity

Preferred primary identity:

- `synthesis_id = hash(thread_id + run_set/version + synthesis_type)`

### Entity identity

Use existing POS/entity identities where possible:

- `person:*`
- `org:*`
- `project:*`
- `topic:*`
- `tool:*`

Do not invent parallel identity systems when an accepted entity namespace already exists.

## Secondary Indexes

The following secondary indexes should exist conceptually even if implementation arrives in phases:

- canonical URL;
- source URL aliases;
- content hash;
- provider/source;
- author/entity;
- topic/theme;
- project ID;
- thread ID;
- run ID;
- query;
- fetched_at;
- published_at;
- artifact role;
- confidence;
- review status.

These are lookup dimensions, not replacements for canonical object IDs.

## Multi-key Routing Model

Routing should distinguish three layers:

### 1. Primary identity

Stable ID of the logical object.

Examples:

- `document_id`
- `thread_id`
- `run_id`
- `synthesis_id`

### 2. Alias keys

Alternate lookup keys that resolve to the same canonical object.

Examples:

- original URL;
- redirected URL;
- mobile URL variant;
- provider-local URL;
- author alias;
- topic alias;
- project alias.

### 3. Role keys

Different artifacts/views for the same logical object.

Examples:

- `metadata`
- `normalized_text`
- `summary`
- `citation_bundle`

### Routing Rule

Lookup may start from aliases, but resolution must end in canonical object IDs.

The storage model must not treat each alias as a separate logical object.

## Multi-source Convergence

The same logical source may be seen through:

- direct fetch;
- Jina;
- visual OCR;
- Exa answer;
- transcript extraction;
- manual operator import.

This must not create fake duplicate logical resources by default.

The intended model is:

- **one logical resource**
- multiple artifacts/evidence layers
- provenance-tagged
- confidence/review-aware

Provider outputs may disagree. That disagreement should be surfaced via provenance and review semantics, not flattened into silent overwrite.

## Iterative Research Model

Some research tasks are one-shot. Many are not.

The correct default model is:

- append-only `ResearchThread`
- multiple `ResearchRun`s
- versioned `ResearchSynthesis`
- a pointer to `latest_synthesis`

### Canonical audit trail

Canonical audit trail is:

- thread history
- run history
- superseded syntheses

### Canonical current view

Canonical current view is:

- latest reviewed/accepted synthesis

Draft or unreviewed synthesis is not the same as accepted knowledge.

## Project vs Global Research

Research may be:

- globally reusable;
- project-scoped;
- or both.

### Global knowledge candidate

Treat as reusable/global when:

- useful outside one project;
- belongs to a domain/topic/entity;
- likely to be reused later.

### Project-scoped attachment

Treat as project-scoped when:

- research was done for one issue/client/repo/proposal;
- conclusions only make sense in that project context;
- actionability depends on the project.

### Both links may exist

One document may be globally useful and still have been used inside a specific project thread.

Therefore project association should be represented through links/edges, not folder ownership.

## Shared Research Index for Agent Navigation

Agents need a shared navigation layer so they can answer quickly:

- have we already researched X?
- is there an existing thread?
- what documents exist?
- is there a synthesis?
- what open questions remain?
- what projects used this?

### v1 index structure

`h2t-ops:research` should own local structured indexes such as:

- `threads.index.json`
- `documents.index.json`
- `syntheses.index.json`
- `links.index.json`
- `aliases.index.json`

These are **navigation caches**, not canonical truth.

Canonical truth remains in object JSON artifacts.

### Minimum index row contracts

The first implementation wave should keep index entries minimal but stable.

#### `documents.index.json`

Each row should contain at least:

- `document_id`
- `canonical_url` if present
- `provider`
- `title` if present
- `status`
- `review_status`
- `thread_ids`
- `entity_ids`
- `project_ids`
- `updated_at`

#### `threads.index.json`

Each row should contain at least:

- `thread_id`
- `question`
- `status`
- `owner_context`
- `topic_ids` or `topics`
- `latest_synthesis_id`
- `updated_at`

#### `syntheses.index.json`

Each row should contain at least:

- `synthesis_id`
- `thread_id`
- `status`
- `review_status` or synthesis status-equivalent
- `confidence_summary` if available
- `has_open_questions`
- `project_ids`
- `updated_at`

#### `links.index.json`

Each row should contain at least:

- `link_id`
- `link_type`
- `from_id`
- `to_id`
- `relation`
- `confidence` if available

#### `aliases.index.json`

Each row should contain at least:

- `alias_type`
- `alias_value`
- `target_object_type`
- `target_id`
- `confidence` if available

These row contracts are intentionally narrow. They exist to keep navigation consistent across implementation slices.

### Agent lookup order

Default agent lookup order should be:

1. query shared index;
2. resolve canonical object IDs;
3. read canonical object JSON;
4. open Markdown mirror only for human review.

### Rebuildability rule

Index entries must be rebuildable from canonical JSON artifacts.

If index and object disagree, object wins.

This is the same architectural rule as:

- Markdown mirror vs canonical JSON;
- local cache vs future POS registry.

## Retention Policy

Retention must follow artifact role.

### Persistent

Keep long-term:

- canonical object JSON;
- normalized metadata;
- normalized text when needed for evidence use;
- citation bundles/evidence locators;
- navigation index state;
- accepted/reviewed syntheses;
- superseded syntheses that are part of the canonical audit trail;
- thread/run references needed for auditability.

### Regenerable

May be recreated:

- Markdown mirrors;
- display-oriented summaries;
- some rendered views;
- convenience aggregations that do not hold unique truth.

### Ephemeral

May be dropped:

- transient OCR intermediates;
- provider debug traces;
- temp screenshots;
- raw search result pages when not needed for provenance;
- other non-canonical provider noise.

### Retention rule

Persistent artifacts must be sufficient to:

- reconstruct agent navigation;
- reconstruct accepted syntheses;
- reconstruct why a later accepted synthesis replaced an earlier one;
- preserve evidence traceability.

### Synthesis retention rule

Retention for syntheses must distinguish three classes:

- **draft synthesis**
  - may be persistent or short-lived depending on implementation choice;
  - not canonical current view;
  - not required to outlive all cleanup policies in v1.

- **reviewed/accepted synthesis**
  - persistent;
  - eligible to become canonical current view.

- **superseded synthesis**
  - persistent when it forms part of the canonical reasoning/audit trail;
  - must remain addressable even after a newer synthesis becomes current.

This keeps history reconstructable without requiring every transient draft to become long-term truth.

## Run Artifact Boundary

`ResearchRun` exists to capture one research iteration, but it must not become an unbounded duplicate of document storage.

### v1 rule

In v1:

- canonical content/evidence artifacts attach to documents;
- syntheses attach to synthesis objects;
- runs primarily own iteration metadata and optional run-level refs.

Run-level refs may include:

- query snapshot refs;
- provider result-set refs;
- ranking/output manifests;
- diagnostic notes refs.

Runs should not become the primary storage home for normalized document text or citation bundles.

That keeps the boundary clear:

- document = source/evidence object
- run = iteration/execution pass
- synthesis = derived conclusion

## POS Compatibility

This spec is local-first, but it must remain POS-compatible.

### v1

`h2t-ops:research` remains locally authoritative for:

- canonical JSON artifacts;
- local structured indexes;
- Markdown mirrors.

POS is not yet canonical.

### v1.5

POS may ingest:

- documents;
- threads;
- runs;
- syntheses;
- entity/project links.

### v2

POS may become the global registry/navigation layer, while:

- `h2t-ops` remains provider/runtime/tooling layer;
- local indexes become cache/working set;
- Markdown remains mirror.

### Compatibility rule

Stable local IDs, role names, and artifact boundaries should be chosen now so later POS ingestion is additive rather than migratory.

## Minimal Schema Sketch

The following sketches define the intended conceptual shape. Exact file layout may evolve in implementation.

### ResearchDocument

```json
{
  "schema": "research_document/v0.1",
  "document_id": "research-doc:sha256:...",
  "canonical_url": "https://...",
  "source_url": "https://...",
  "provider": "web|arxiv|github|hf|manual",
  "title": "...",
  "authors": [{"name": "...", "entity_id": null}],
  "published_at": null,
  "fetched_at": "...",
  "content_hash": "...",
  "status": "raw|normalized|indexed|rejected",
  "artifact_refs": {
    "metadata": "dor://lake/research/...",
    "normalized_text": "dor://lake/research/...",
    "citation_bundle": "dor://lake/research/...",
    "markdown_mirror": "dor://lake/research/..."
  },
  "privacy": "public|mixed|personal",
  "review_status": "unreviewed|reviewed|rejected"
}
```

### ResearchThread

```json
{
  "schema": "research_thread/v0.1",
  "thread_id": "research-thread:sha256:...",
  "question": "...",
  "created_at": "...",
  "status": "open|paused|resolved|superseded",
  "domain": "research|business|creative|infra",
  "topics": ["..."],
  "owner_context": {
    "context_type": "project|repo|global|client",
    "context_id": "project:ai-native"
  },
  "latest_synthesis_id": null
}
```

### ResearchRun

```json
{
  "schema": "research_run/v0.1",
  "run_id": "research-run:sha256:...",
  "thread_id": "research-thread:sha256:...",
  "created_at": "...",
  "status": "running|completed|failed|superseded",
  "query": "...",
  "provider_set": ["exa", "web", "youtube"],
  "document_ids": ["research-doc:sha256:..."],
  "artifact_refs": {
    "query_snapshot": null,
    "result_manifest": null
  },
  "notes_ref": null,
  "result_counts": {
    "documents": 0,
    "accepted_documents": 0
  }
}
```

### ResearchSynthesis

```json
{
  "schema": "research_synthesis/v0.1",
  "synthesis_id": "research-synthesis:sha256:...",
  "thread_id": "research-thread:sha256:...",
  "run_ids": ["research-run:sha256:..."],
  "created_at": "...",
  "status": "draft|reviewed|accepted|superseded",
  "summary": "...",
  "claims": [
    {
      "claim": "...",
      "confidence": "low|medium|high",
      "evidence_refs": ["research-doc:sha256:...#quote-1"]
    }
  ],
  "open_questions": [],
  "proposed_edges": []
}
```

### ResearchEntityLink

```json
{
  "schema": "research_entity_link/v0.1",
  "link_id": "research-entity-link:sha256:...",
  "from_document_id": "research-doc:sha256:...",
  "entity_id": "org:...",
  "entity_type": "person|org|topic|tool|project",
  "relation": "author|mentions|about|supports|criticizes",
  "confidence": "low|medium|high",
  "evidence_ref": "research-doc:sha256:...#locator"
}
```

### ProjectResearchLink

```json
{
  "schema": "project_research_link/v0.1",
  "link_id": "project-research-link:sha256:...",
  "project_id": "project:ai-native",
  "thread_id": "research-thread:sha256:...",
  "document_id": "research-doc:sha256:...",
  "synthesis_id": null,
  "relation": "informs|background|competitive_reference|source_for_decision",
  "created_at": "...",
  "evidence_ref": "research-doc:sha256:..."
}
```

## v1 Implementation Boundary

This spec does **not** require implementing the full POS object model immediately.

The first practical implementation wave should aim to establish:

- canonical JSON vs Markdown rule;
- role-tagged local artifacts;
- stable local IDs where feasible;
- shared structured navigation indexes;
- local routing semantics that distinguish document/thread/run/synthesis roles.

POS ingestion and cross-domain graph semantics remain later waves.

### v1 local storage stance

This spec intentionally constrains storage shape only lightly.

v1 should separate at least:

- canonical object JSON artifacts;
- shared index JSON files.

Whether that is implemented as:

- `objects/` + `indexes/`;
- or current artifact directories plus explicit object envelopes and index files;

is deferred to the implementation plan.

What is **not** deferred:

- object JSON and index JSON must be distinguishable as different layers;
- index files must be rebuildable from object JSON;
- routing must not depend on Markdown location/layout.

## Acceptance

This design is ready for implementation when the following are agreed:

1. Canonical local truth is JSON, not Markdown.
2. Document/thread/run/synthesis identities are distinct.
3. Multi-key routing resolves aliases into canonical object IDs.
4. Shared research indexes are caches, not truth.
5. Index entries are rebuildable from canonical JSON objects.
6. Iterative research uses thread/run/synthesis semantics rather than one mutable blob.
7. Project association is modeled by links, not folder ownership.
8. Retention classes are explicit.
9. The local model is chosen to be POS-compatible without requiring POS implementation now.

## Implementation Status

- Design only.
- No implementation is implied by this spec alone.
- A follow-up implementation plan should narrow the first wave to local artifact contracts, indexes, and routing updates.
