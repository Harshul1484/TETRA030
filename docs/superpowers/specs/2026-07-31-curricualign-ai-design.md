# CurricuAlign AI - Design Specification

**Project:** TETRA030
**Date:** 2026-07-31
**Event:** 36-hour hackathon, starting 2026-08-01
**Track:** D (EdTech), Problem Statement 1 - Dynamic Syllabus & Industry Skill-Gap Synchronizer
**Team size:** Solo
**Repository:** https://github.com/Harshul1484/TETRA030

---

## 1. Problem and Positioning

Higher education curricula lag 3-5 years behind market demand. Institutions have no automated
way to audit a syllabus against live job market data, so graduates earn top grades while
carrying severe skill gaps.

CurricuAlign AI ingests real syllabi and real job postings, maps both onto a shared skill
ontology in Neo4j, quantifies the gap, and generates targeted syllabus modifications that a
professor can adopt without redesigning a course from scratch.

**Target users:** university curriculum committees, deans of academics, accreditation bodies.

**Judging context:** the hackathon is online. Judges may open the application unattended, at
any hour, with no walkthrough and no opportunity to ask questions. This single constraint
drives three non-negotiable requirements:

- **R1 - Zero-setup.** The system ships pre-seeded. No empty states, no "upload a file first".
- **R2 - Self-explaining.** A guided tour and obvious next action on every screen.
- **R3 - Always-works.** Every external dependency has a fallback. Nothing in the demo path
  may fail because an API key expired or a rate limit was hit.

---

## 2. Locked Decisions

These were evaluated and settled during design. They are not to be re-litigated during the build.

| Decision | Choice | Rationale |
|---|---|---|
| Backend | FastAPI + Python | Native to the mandated AI stack; single runtime for a solo build |
| Frontend | Next.js + TypeScript | Fastest path to the graph and diff visualizations |
| Graph store | Neo4j | Mandated; load-bearing for multi-hop gap reasoning |
| Vector store | ChromaDB | Mandated by name; embedded mode needs no extra service |
| LLM | Claude API | Extraction and augmentation; strong structured output |
| Local orchestration | Docker Compose | Build first; deployment deferred |
| Relational store | None | Neo4j is the source of truth; avoids a third stateful service |

**Rejected alternatives.** NestJS was considered for developer velocity but would force either
dropping both ML differentiators or maintaining a second runtime solo. pgvector was considered
but is not named in the brief; substituting it risks a scored rubric line while making
infrastructure heavier (Postgres plus Neo4j, versus embedded Chroma plus Neo4j).

**Style constraint.** No emojis anywhere: UI, README, commit messages, code, or documentation.

---

## 3. Architecture

### 3.1 Pipeline

Six stages, each with one responsibility and a stable interface, so any stage can be swapped
or stubbed without touching its neighbours.

```
Ingest -> Extract -> Embed -> Match -> Score -> Augment
```

| Stage | Input | Output | Implementation |
|---|---|---|---|
| Ingest | PDF/DOCX/text syllabi, job postings | Normalized `Document` records | pdfplumber, python-docx |
| Extract | Raw document text | `SkillMention` list, taxonomy-linked | Claude, structured output |
| Embed | Skill mentions, canonical skills | Vectors in Chroma | sentence-transformers |
| Match | Vectors | Scored `(mention, canonical_skill)` pairs | Chroma similarity search |
| Score | Graph state | `GapReport` with per-skill severity | Cypher plus scoring module |
| Augment | GapReport plus course subgraph | Proposed syllabus modifications | Claude |

The seam between **Match** and **Score** is the critical insurance policy. Match emits nothing
but a list of scored pairs. If Chroma retrieval underperforms late in the build, it can be
replaced with fuzzy string matching against the taxonomy with no downstream change.

### 3.2 Why Neo4j is load-bearing

The graph answers questions that are genuinely painful in SQL. The canonical example, to be
reproduced verbatim in the technical writeup:

> Which skills are demanded by jobs our graduates target, reachable within two hops of
> outcomes our curriculum already teaches, but not directly covered by any course?

This is a multi-hop traversal over weighted edges. It is what separates an actionable
recommendation ("add these three skills to this course, in this order, because prerequisites
are already satisfied") from a naive list of forty missing keywords.

### 3.3 Contract-first development

Pydantic models for every inter-stage payload are defined in the first two hours. TypeScript
types are generated from the OpenAPI schema. Solo builds fail when frontend and backend drift;
generated types make that drift impossible.

### 3.4 Determinism

Every Claude call is cached to disk, keyed by a hash of its input. The same syllabus yields the
same result at zero cost and instant speed. This satisfies R3: a dead API key or rate limit at
judging time still produces a complete working demo from cache.

---

## 4. Skill Ontology Graph

### 4.1 Nodes

| Node | Key properties |
|---|---|
| `Course` | code, title, credits, department, institution |
| `Outcome` | text, bloom_level, source_course |
| `Skill` | canonical_name, category, aliases, esco_id |
| `JobPosting` | title, company, posted_date, source, seniority |
| `Employer` | name, sector |
| `Textbook` | title, chapter, isbn |

### 4.2 Relationships

```
(Course)-[:HAS_OUTCOME]->(Outcome)
(Outcome)-[:TEACHES {confidence}]->(Skill)
(JobPosting)-[:REQUIRES {importance, frequency}]->(Skill)
(JobPosting)-[:POSTED_BY]->(Employer)
(Skill)-[:PREREQUISITE_OF]->(Skill)
(Skill)-[:RELATED_TO {similarity}]->(Skill)
(Textbook)-[:COVERS]->(Skill)
(Course)-[:PRECEDES]->(Course)
```

`PREREQUISITE_OF` and `RELATED_TO` are what make this a graph problem rather than a join. They
distinguish a low-cost skill addition (adjacent to existing content, prerequisites satisfied)
from an expensive one (three missing prerequisites deep).

### 4.3 Taxonomy-first constraint

**This is the highest-risk correctness decision in the build.**

`Skill` nodes are drawn from a curated canonical taxonomy of roughly 300-500 tech skills, seeded
from ESCO or O*NET. Extraction *links to* this taxonomy; it never invents nodes. Without this
constraint, "ML", "Machine Learning", and "machine-learning" become three distinct nodes and
every downstream gap number is meaningless.

The taxonomy is built in hours 3-4, before anything depends on it.

### 4.4 Gap scoring

Per skill, combining four signals:

- **Market demand** - posting frequency, recency-weighted
- **Curriculum coverage** - whether any outcome teaches it, and at what confidence
- **Prerequisite reachability** - graph distance from what is already taught
- **Trend slope** - from the forecaster; defaults to zero when absent

Aggregated into a per-course and per-program **Curriculum Health Score**.

---

## 5. Data Strategy

### 5.1 Job market data (belt and braces)

- **Primary, demo path:** a snapshot of 1,500-3,000 real tech postings committed to the repo as
  JSON, sourced from a public dataset plus one early API sweep. Instant, offline-safe,
  reproducible.
- **Secondary, proof of life:** a "Refresh market data" action hitting a free API (Remotive or
  Adzuna). It genuinely works, proving the pipeline is real, but nothing in the demo depends on
  it. On failure it degrades to a message.

### 5.2 Syllabus data (corpus ladder)

- **MVP:** 5-10 real syllabi from the user's university, ingested as PDF. Institutional
  authenticity is what makes the demo land.
- **Full:** broadened to AICTE model curricula and published university syllabi through the same
  loader interface. Purely additive.

### 5.3 Parsing

`pdfplumber` first. Where the text layer is missing or garbled, fall back to passing raw text to
Claude for structure recovery. No OCR pipeline is built. Any document failing both paths is
flagged and skipped, never crashing a batch.

### 5.4 Seeding

The database ships pre-seeded with courses, postings, and computed gaps, satisfying R1.

---

## 6. API Surface

```
POST /api/syllabi              upload and ingest a syllabus
GET  /api/courses              list courses with health scores
GET  /api/courses/{id}/gaps    ranked gap report with evidence
GET  /api/graph                subgraph for visualization
POST /api/augment/{course_id}  Claude-generated syllabus modifications
GET  /api/market/trends        skill demand over time
POST /api/market/refresh       live API sweep
```

`/api/market/trends` is always present and always returns a valid payload. When the forecaster
of section 8.2 has not shipped, it serves historical frequency counts with a null slope, and the
frontend renders demand history without a projection. The endpoint contract does not change when
the model lands.

---

## 7. Frontend

Four screens, each independently a demo peak, so any entry point a judge chooses lands on
something compelling.

1. **Dashboard** - program health score, top gaps across all courses, trend highlights.
2. **Course detail** - gaps ranked by severity, each backed by evidence
   ("47 of 312 postings require this; no outcome covers it").
3. **Graph explorer** - force-directed Course to Skill to Job view with gaps highlighted. Makes
   the mandated Neo4j component visible rather than implied.
4. **Augmenter** - syllabus rewrite as a red/green diff, exportable.

A persistent **guided tour** walks an unattended judge through all four in order, satisfying R2.

---

## 8. Differentiating ML Components

Both are deliberately **off the critical path**, scheduled for hours 20-28, and both have
deterministic fallbacks.

### 8.1 Fine-tuned skill embeddings

A `sentence-transformers` model contrastively fine-tuned on skill-alias pairs, so that "RAG",
"retrieval augmented generation", and "vector search pipelines" occupy neighbouring space. Feeds
the mandated ChromaDB component and yields a measurable before/after retrieval-quality number.

**Fallback:** the base embedding model, via one config change.

### 8.2 Trend forecasting

Regression over skill frequency in job postings across time, producing statements of the form
"Kubernetes demand is up 40 percent in six months and your curriculum has zero coverage".

This is the strongest differentiator in the submission. Most teams will show what a syllabus
lacks today; almost none will show what it will lack in eighteen months.

**Fallback:** trend slope defaults to zero, and gap scoring proceeds on the other three signals.

### 8.3 Rejected: training the core extractor

Training a custom skill extractor was considered and rejected. It would consume 8-14 hours,
require hand-labelling a corpus that does not exist off the shelf, likely underperform zero-shot
Claude, and sit as a single point of failure upstream of the entire pipeline. Claude remains the
extractor on the critical path.

---

## 9. Error Handling

A floor beneath every layer:

| Failure | Fallback |
|---|---|
| Claude API unavailable | Disk cache, then deterministic stub |
| Chroma retrieval poor | Fuzzy string match against taxonomy |
| Trained models absent | Base embedding model; trend slope zero |
| Live job API dead | Committed snapshot |
| PDF unparseable | Claude structure recovery, then flag and skip |

---

## 10. Testing

Proportionate to a 36-hour build. Real unit tests on the **scoring math** and the **taxonomy
linker**, because silent wrongness there poisons every downstream number in a way no one would
notice during a demo. Smoke tests covering the pipeline end to end. No coverage chasing on UI glue.

---

## 11. Deliverables

- Working application, pre-seeded, with guided tour
- README with architecture diagram, screenshots, and one-command setup
- Recorded demo video, 3-5 minutes, scripted
- Technical writeup defending graph schema, embedding strategy, and gap-scoring math

---

## 12. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Taxonomy quality poisons all gap numbers | Critical | Curate in hours 3-4 before dependents exist |
| Scope creep past hour 20 | Critical | Core pipeline demoable by hour 20; all later work cuttable |
| PDF parsing consumes hours | High | Claude fallback, skip-on-fail, no OCR |
| Judges see Neo4j as decorative | Medium | Graph explorer screen plus the multi-hop query in the writeup |
| Deployment deferred too long | Medium | Env-driven config from hour 1; no hardcoded localhost |

**Hard schedule rule:** the core pipeline must be demoable by hour 20. Everything after that is
additive and individually cuttable without breaking the demo.

"Demoable" is defined concretely, and is pass/fail rather than a matter of judgement. At hour 20,
starting from `docker compose up` on a clean checkout, a person with no instructions must be able to:

1. Load the dashboard and see a Curriculum Health Score computed from seeded data
2. Open a course and see at least five ranked gaps, each showing its supporting evidence
3. Open the graph explorer and see Course, Skill, and JobPosting nodes with gap edges highlighted
4. Trigger the augmenter on one course and receive Claude-generated modifications as a diff

If any of the four fails at hour 20, the response is to cut remaining scope, not to extend the
deadline. Sections 8.1 and 8.2 are the first cuts.

---

## 13. Deferred

Deployment. The build comes first, per explicit user direction. Code stays deployment-ready
through env-driven configuration and no hardcoded hostnames, so migration to hosted
infrastructure remains cheap when it is scheduled.
