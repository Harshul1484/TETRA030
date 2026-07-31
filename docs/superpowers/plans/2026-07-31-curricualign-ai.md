# CurricuAlign AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a system that ingests university syllabi and live job market data, maps both onto a shared skill ontology in Neo4j, quantifies curriculum skill gaps, and generates targeted syllabus modifications with Claude.

**Architecture:** A six-stage pipeline (Ingest, Extract, Embed, Match, Score, Augment) where each stage has one responsibility and a stable interface. Neo4j is the source of truth for entities and relationships; ChromaDB owns only the mention-to-canonical-skill matching; Claude handles extraction and generation. Every external dependency has a deterministic fallback so the demo cannot break.

**Tech Stack:** FastAPI, Python 3.11, Neo4j 5.26, ChromaDB (embedded PersistentClient), sentence-transformers, Anthropic Claude API, Next.js 15, TypeScript, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-07-31-curricualign-ai-design.md`

---

## PRE-SPRINT: Do This Before Hour Zero

Verified on 2026-07-31: **Docker Desktop is installed but not running**, and **Python is not installed on the host**. Neither blocks the design (backend Python runs inside the container), but both block hour zero.

- [ ] **Start Docker Desktop and confirm the daemon responds**

```bash
docker ps
```
Expected: an empty container table, not a pipe connection error.

- [ ] **Pre-pull base images before the sprint starts**

These are several hundred megabytes. Downloading them at the starting gun wastes irreplaceable time.

```bash
docker pull python:3.11-slim
docker pull neo4j:5.26
docker pull node:22-alpine
```
Expected: `Status: Downloaded newer image` for each.

- [ ] **Confirm the Anthropic API key works**

```bash
curl -s https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-4-5","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}'
```
Expected: a JSON response containing `"type":"message"`. A 401 means the key is wrong; fix it now, not at hour 12.

**Host command note:** because Python is not on the host, every Python command in this plan runs inside the container via `docker compose exec backend <cmd>`. Do not try to run `pytest` directly on Windows.

---

## File Structure

```
TETRA030/
  docker-compose.yml
  .env.example
  backend/
    Dockerfile
    requirements.txt
    app/
      main.py                  FastAPI entrypoint, router registration
      config.py                env-driven settings, no hardcoded hosts
      contracts.py             Pydantic models for all six pipeline stages
      db/
        neo4j_client.py        driver lifecycle, session helper
        schema.py              constraints and indexes
      llm/
        claude_client.py       cached Claude wrapper with fallback chain
        cache.py               content-hash disk cache
      pipeline/
        ingest.py              PDF/DOCX to Document
        extract.py             Document to SkillMention via Claude
        embed.py               Chroma indexing
        match.py               similarity to ScoredPair
        score.py               GapReport and health score math
        augment.py             GapReport to AugmentProposal via Claude
      taxonomy/
        loader.py              canonical skill list into Neo4j
        data/skills.json       the curated 300-500 skill taxonomy
      api/
        courses.py             course and gap endpoints
        graph.py               visualization subgraph
        market.py              trends and refresh
        syllabi.py             upload
      seed.py                  pre-populate DB on boot
    tests/
      test_score.py            gap scoring math (real coverage)
      test_taxonomy.py         alias linking (real coverage)
      test_smoke.py            end-to-end pipeline
  frontend/
    (Next.js app - detailed in Phase 3)
  data/
    jobs_snapshot.json         committed job posting corpus
    syllabi/                   source PDFs
```

**Decomposition rationale:** each pipeline stage is its own module because the Match-to-Score seam is the designed swap point. `score.py` and `taxonomy/loader.py` are isolated because they are the only two modules carrying real unit tests, and they must be testable without Neo4j or Claude running.

---

## PHASE 0: Setup (Hours 0-3)

### Task 1: Repository scaffold and env-driven config

**Files:**
- Create: `.env.example`, `.gitignore`, `backend/requirements.txt`, `backend/Dockerfile`, `backend/app/config.py`, `backend/app/main.py`

- [ ] **Step 1: Create `.gitignore`**

```
__pycache__/
*.py[cod]
.env
.venv/
node_modules/
.next/
data/chroma/
data/llm_cache/
*.log
```

- [ ] **Step 2: Create `.env.example`**

Nothing may hardcode a hostname. This file is the contract for deployment later.

```
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=curricualign
ANTHROPIC_API_KEY=sk-ant-replace-me
CLAUDE_MODEL=claude-sonnet-4-5
CHROMA_PATH=/app/data/chroma
LLM_CACHE_PATH=/app/data/llm_cache
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CORS_ORIGINS=http://localhost:3000
```

- [ ] **Step 3: Create `backend/requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.7.0
neo4j==5.27.0
chromadb==0.6.3
sentence-transformers==3.3.1
anthropic==0.42.0
pdfplumber==0.11.4
python-docx==1.1.2
python-multipart==0.0.20
httpx==0.28.1
pytest==8.3.4
```

- [ ] **Step 4: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 5: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "curricualign"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5"
    chroma_path: str = "/app/data/chroma"
    llm_cache_path: str = "/app/data/llm_cache"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 6: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="CurricuAlign AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Commit**

```bash
git add .gitignore .env.example backend/
git commit -m "feat: scaffold backend with env-driven config"
```

---

### Task 2: Docker Compose brings the stack up

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

Chroma is embedded in the backend process, so it is deliberately not a service here. Two stateful services only.

```yaml
services:
  neo4j:
    image: neo4j:5.26
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/curricualign
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:7474"]
      interval: 5s
      timeout: 5s
      retries: 20

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./backend:/app
      - ./data:/app/data
    depends_on:
      neo4j:
        condition: service_healthy

volumes:
  neo4j_data:
```

- [ ] **Step 2: Copy env and bring the stack up**

```bash
cp .env.example .env
docker compose up -d --build
```
Expected: both services start; `neo4j` reports healthy.

- [ ] **Step 3: Verify the backend responds**

```bash
curl -s http://localhost:8000/api/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 4: Verify Neo4j accepts a query**

```bash
docker compose exec neo4j cypher-shell -u neo4j -p curricualign "RETURN 1 AS ok;"
```
Expected: a table containing `ok` and `1`.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker compose with neo4j and backend"
```

---

### Task 3: Pipeline contracts

These types are referenced by every later task. Defining them once here is the anti-drift measure from spec section 3.3.

**Files:**
- Create: `backend/app/contracts.py`

- [ ] **Step 1: Write `backend/app/contracts.py`**

```python
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DocumentKind(str, Enum):
    SYLLABUS = "syllabus"
    JOB_POSTING = "job_posting"


class Document(BaseModel):
    """Stage 1 output: a normalized source document."""
    doc_id: str
    kind: DocumentKind
    title: str
    raw_text: str
    source: str
    posted_date: date | None = None


class SkillMention(BaseModel):
    """Stage 2 output: a skill referenced in a document, before canonicalization."""
    mention_id: str
    doc_id: str
    surface_form: str
    context: str
    importance: float = Field(ge=0.0, le=1.0, default=0.5)


class ScoredPair(BaseModel):
    """Stage 4 output. This is the swap seam: any matcher emitting these works."""
    mention_id: str
    canonical_skill: str
    similarity: float = Field(ge=0.0, le=1.0)


class GapSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class SkillGap(BaseModel):
    """One missing or under-covered skill, with the evidence supporting it."""
    canonical_skill: str
    severity: GapSeverity
    market_demand: float = Field(ge=0.0, le=1.0)
    curriculum_coverage: float = Field(ge=0.0, le=1.0)
    prerequisite_distance: int
    trend_slope: float | None = None
    postings_requiring: int
    postings_total: int
    evidence: str


class GapReport(BaseModel):
    """Stage 5 output."""
    course_code: str
    course_title: str
    health_score: float = Field(ge=0.0, le=100.0)
    gaps: list[SkillGap]


class AugmentProposal(BaseModel):
    """Stage 6 output: modifications a professor can adopt without a redesign."""
    course_code: str
    added_outcomes: list[str]
    case_studies: list[str]
    toolsets: list[str]
    project_prompts: list[str]
    rationale: str


class TrendPoint(BaseModel):
    period: str
    frequency: int


class SkillTrend(BaseModel):
    """Slope is None until the forecaster ships. The contract never changes."""
    canonical_skill: str
    history: list[TrendPoint]
    slope: float | None = None
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
docker compose exec backend python -c "from app.contracts import GapReport; print(GapReport.model_json_schema()['title'])"
```
Expected: `GapReport`

- [ ] **Step 3: Commit**

```bash
git add backend/app/contracts.py
git commit -m "feat: define pipeline stage contracts"
```

---

### Task 4: Cached Claude client with fallback chain

Satisfies R3. A dead key or rate limit at judging time must still produce a working demo.

**Files:**
- Create: `backend/app/llm/cache.py`, `backend/app/llm/claude_client.py`
- Test: `backend/tests/test_llm_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_llm_cache.py
from app.llm.cache import DiskCache


def test_cache_roundtrip(tmp_path):
    cache = DiskCache(str(tmp_path))
    assert cache.get("prompt-a") is None
    cache.set("prompt-a", {"text": "result"})
    assert cache.get("prompt-a") == {"text": "result"}


def test_cache_key_is_content_addressed(tmp_path):
    cache = DiskCache(str(tmp_path))
    cache.set("prompt-a", {"text": "one"})
    cache.set("prompt-b", {"text": "two"})
    assert cache.get("prompt-a") == {"text": "one"}
    assert cache.get("prompt-b") == {"text": "two"}
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
docker compose exec backend pytest tests/test_llm_cache.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.llm.cache'`

- [ ] **Step 3: Implement `backend/app/llm/cache.py`**

```python
import hashlib
import json
from pathlib import Path
from typing import Any


class DiskCache:
    """Content-addressed cache. Same input always yields the same output."""

    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, key: str, value: Any) -> None:
        self._path(key).write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )
```

- [ ] **Step 4: Run the test and confirm it passes**

```bash
docker compose exec backend pytest tests/test_llm_cache.py -v
```
Expected: 2 passed

- [ ] **Step 5: Implement `backend/app/llm/claude_client.py`**

The fallback chain is the whole point: live call, then cache, then stub.

```python
import json
import logging
from typing import Any

import anthropic

from app.config import settings
from app.llm.cache import DiskCache

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Cached Claude wrapper. Never raises to callers; degrades instead."""

    def __init__(self) -> None:
        self.cache = DiskCache(settings.llm_cache_path)
        self._client = (
            anthropic.Anthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )

    def complete_json(
        self, prompt: str, system: str = "", fallback: Any = None
    ) -> Any:
        key = f"{settings.claude_model}|{system}|{prompt}"

        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if self._client is None:
            logger.warning("No API key configured; returning fallback")
            return fallback

        try:
            message = self._client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=system or anthropic.NOT_GIVEN,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text
            parsed = json.loads(_strip_fences(text))
            self.cache.set(key, parsed)
            return parsed
        except Exception as exc:
            logger.warning("Claude call failed (%s); returning fallback", exc)
            return fallback


def _strip_fences(text: str) -> str:
    """Claude sometimes wraps JSON in markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
    return cleaned
```

- [ ] **Step 6: Verify the fallback path works without a key**

```bash
docker compose exec backend python -c "
from app.llm.claude_client import ClaudeClient
c = ClaudeClient()
print(c.complete_json('test', fallback={'ok': True}))
"
```
Expected: `{'ok': True}` (or a real response if the key is set)

- [ ] **Step 7: Commit**

```bash
git add backend/app/llm/ backend/tests/test_llm_cache.py
git commit -m "feat: add cached claude client with fallback chain"
```

---

## PHASE 1: Data and Taxonomy (Hours 3-10)

### Task 5: Canonical skill taxonomy

**This is the highest-risk correctness item in the build.** Everything downstream is meaningless if aliases do not collapse.

**Files:**
- Create: `backend/app/taxonomy/data/skills.json`, `backend/app/taxonomy/loader.py`
- Test: `backend/tests/test_taxonomy.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_taxonomy.py
from app.taxonomy.loader import TaxonomyIndex


def test_exact_canonical_name_resolves():
    idx = TaxonomyIndex([
        {"canonical_name": "Machine Learning", "category": "ai",
         "aliases": ["ML", "machine-learning"], "prerequisites": []},
    ])
    assert idx.resolve("Machine Learning") == "Machine Learning"


def test_aliases_collapse_to_one_canonical_skill():
    idx = TaxonomyIndex([
        {"canonical_name": "Machine Learning", "category": "ai",
         "aliases": ["ML", "machine-learning"], "prerequisites": []},
    ])
    assert idx.resolve("ML") == "Machine Learning"
    assert idx.resolve("machine-learning") == "Machine Learning"
    assert idx.resolve("  MACHINE LEARNING  ") == "Machine Learning"


def test_unknown_surface_form_returns_none():
    idx = TaxonomyIndex([
        {"canonical_name": "Machine Learning", "category": "ai",
         "aliases": [], "prerequisites": []},
    ])
    assert idx.resolve("Underwater Basket Weaving") is None


def test_duplicate_alias_across_skills_raises():
    with_conflict = [
        {"canonical_name": "Machine Learning", "category": "ai",
         "aliases": ["ML"], "prerequisites": []},
        {"canonical_name": "Meta Learning", "category": "ai",
         "aliases": ["ML"], "prerequisites": []},
    ]
    try:
        TaxonomyIndex(with_conflict)
    except ValueError as exc:
        assert "ML" in str(exc)
    else:
        raise AssertionError("expected ValueError on ambiguous alias")
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
docker compose exec backend pytest tests/test_taxonomy.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.taxonomy.loader'`

- [ ] **Step 3: Implement `backend/app/taxonomy/loader.py`**

```python
import json
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).parent / "data" / "skills.json"


class TaxonomyIndex:
    """Resolves free-text skill mentions to canonical taxonomy names.

    Ambiguous aliases raise at construction time rather than silently
    resolving to whichever skill happened to load last.
    """

    def __init__(self, skills: list[dict[str, Any]]):
        self.skills = skills
        self._lookup: dict[str, str] = {}
        for skill in skills:
            canonical = skill["canonical_name"]
            for form in [canonical, *skill.get("aliases", [])]:
                normalized = self._normalize(form)
                existing = self._lookup.get(normalized)
                if existing and existing != canonical:
                    raise ValueError(
                        f"Ambiguous alias {form!r}: maps to both "
                        f"{existing!r} and {canonical!r}"
                    )
                self._lookup[normalized] = canonical

    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip().lower().replace("-", " ").replace("_", " ")

    def resolve(self, surface_form: str) -> str | None:
        return self._lookup.get(self._normalize(surface_form))

    def canonical_names(self) -> list[str]:
        return [s["canonical_name"] for s in self.skills]

    @classmethod
    def from_disk(cls) -> "TaxonomyIndex":
        return cls(json.loads(DATA_PATH.read_text(encoding="utf-8")))
```

- [ ] **Step 4: Run the tests and confirm they pass**

```bash
docker compose exec backend pytest tests/test_taxonomy.py -v
```
Expected: 4 passed

- [ ] **Step 5: Build `backend/app/taxonomy/data/skills.json`**

Target 300-500 entries across categories: programming languages, ML/AI, data engineering, cloud/devops, web, databases, security, soft skills. Every entry needs realistic aliases — that is the entire value of the file. Structure:

```json
[
  {
    "canonical_name": "Retrieval Augmented Generation",
    "category": "ai",
    "aliases": ["RAG", "retrieval-augmented generation", "retrieval augmented LLM"],
    "prerequisites": ["Vector Databases", "Large Language Models"]
  },
  {
    "canonical_name": "Vector Databases",
    "category": "data",
    "aliases": ["vector DB", "vector search", "embedding database"],
    "prerequisites": ["Databases"]
  }
]
```

Generate the bulk with Claude, then hand-check for alias collisions. The test in step 1 catches collisions at load time.

- [ ] **Step 6: Verify the real file loads without ambiguity**

```bash
docker compose exec backend python -c "
from app.taxonomy.loader import TaxonomyIndex
idx = TaxonomyIndex.from_disk()
print(f'{len(idx.canonical_names())} skills loaded')
print('RAG ->', idx.resolve('RAG'))
"
```
Expected: a count of at least 300, and `RAG -> Retrieval Augmented Generation`. A `ValueError` here means duplicate aliases; fix the JSON.

- [ ] **Step 7: Commit**

```bash
git add backend/app/taxonomy/ backend/tests/test_taxonomy.py
git commit -m "feat: add canonical skill taxonomy with alias resolution"
```

---

### Task 6: Neo4j schema and taxonomy load

**Files:**
- Create: `backend/app/db/neo4j_client.py`, `backend/app/db/schema.py`

- [ ] **Step 1: Implement `backend/app/db/neo4j_client.py`**

```python
from contextlib import contextmanager

from neo4j import GraphDatabase

from app.config import settings

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


@contextmanager
def session():
    with get_driver().session() as s:
        yield s
```

- [ ] **Step 2: Implement `backend/app/db/schema.py`**

```python
from app.db.neo4j_client import session
from app.taxonomy.loader import TaxonomyIndex

CONSTRAINTS = [
    "CREATE CONSTRAINT skill_name IF NOT EXISTS "
    "FOR (s:Skill) REQUIRE s.canonical_name IS UNIQUE",
    "CREATE CONSTRAINT course_code IF NOT EXISTS "
    "FOR (c:Course) REQUIRE c.code IS UNIQUE",
    "CREATE CONSTRAINT job_id IF NOT EXISTS "
    "FOR (j:JobPosting) REQUIRE j.doc_id IS UNIQUE",
    "CREATE CONSTRAINT outcome_id IF NOT EXISTS "
    "FOR (o:Outcome) REQUIRE o.outcome_id IS UNIQUE",
]


def apply_constraints() -> None:
    with session() as s:
        for statement in CONSTRAINTS:
            s.run(statement)


def load_taxonomy(index: TaxonomyIndex) -> int:
    """Idempotent. Safe to re-run on every boot."""
    with session() as s:
        for skill in index.skills:
            s.run(
                "MERGE (s:Skill {canonical_name: $name}) "
                "SET s.category = $category, s.aliases = $aliases",
                name=skill["canonical_name"],
                category=skill.get("category", "general"),
                aliases=skill.get("aliases", []),
            )
        for skill in index.skills:
            for prereq in skill.get("prerequisites", []):
                s.run(
                    "MATCH (a:Skill {canonical_name: $prereq}) "
                    "MATCH (b:Skill {canonical_name: $name}) "
                    "MERGE (a)-[:PREREQUISITE_OF]->(b)",
                    prereq=prereq,
                    name=skill["canonical_name"],
                )
    return len(index.skills)
```

- [ ] **Step 3: Apply schema and load the taxonomy**

```bash
docker compose exec backend python -c "
from app.db.schema import apply_constraints, load_taxonomy
from app.taxonomy.loader import TaxonomyIndex
apply_constraints()
print(load_taxonomy(TaxonomyIndex.from_disk()), 'skills loaded')
"
```
Expected: a count matching the taxonomy size.

- [ ] **Step 4: Verify in the graph**

```bash
docker compose exec neo4j cypher-shell -u neo4j -p curricualign \
  "MATCH (s:Skill) RETURN count(s) AS skills;"
```
Expected: the same count.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/
git commit -m "feat: add neo4j schema and idempotent taxonomy loader"
```

---

### Task 7: Job posting corpus

**Files:**
- Create: `data/jobs_snapshot.json`, `backend/app/pipeline/ingest.py`

- [ ] **Step 1: Assemble 1500-3000 real postings**

Source from a public dataset (Kaggle tech jobs, HuggingFace job postings) or a Remotive API sweep:

```bash
curl -s "https://remotive.com/api/remote-jobs?category=software-dev&limit=500" \
  -o data/remotive_raw.json
```

Normalize to this shape, one object per posting, saved as `data/jobs_snapshot.json`:

```json
[
  {
    "doc_id": "job-0001",
    "kind": "job_posting",
    "title": "Senior ML Engineer",
    "raw_text": "full job description text",
    "source": "remotive",
    "posted_date": "2026-05-14",
    "company": "Acme Corp"
  }
]
```

`posted_date` is mandatory — the trend forecaster depends on it. Discard any posting without one.

- [ ] **Step 2: Implement the loader in `backend/app/pipeline/ingest.py`**

```python
import json
from pathlib import Path

from app.contracts import Document, DocumentKind

SNAPSHOT_PATH = Path("/app/data/jobs_snapshot.json")


def load_job_snapshot() -> list[Document]:
    """Primary demo path: offline-safe, reproducible."""
    if not SNAPSHOT_PATH.exists():
        return []
    raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return [Document(**item) for item in raw]
```

- [ ] **Step 3: Verify the corpus parses**

```bash
docker compose exec backend python -c "
from app.pipeline.ingest import load_job_snapshot
docs = load_job_snapshot()
print(len(docs), 'postings')
print(docs[0].title if docs else 'EMPTY')
"
```
Expected: a count of at least 1500.

- [ ] **Step 4: Commit**

```bash
git add data/jobs_snapshot.json backend/app/pipeline/ingest.py
git commit -m "feat: add job posting corpus and snapshot loader"
```

---

### Task 8: Syllabus ingestion

**Timebox this hard.** PDF parsing is where ingestion time goes to die. A document that fails both paths is flagged and skipped, never crashing a batch.

**Files:**
- Modify: `backend/app/pipeline/ingest.py`

- [ ] **Step 1: Add PDF and DOCX parsing**

```python
import logging
import uuid

import pdfplumber
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)


def parse_syllabus(path: Path) -> Document | None:
    """Returns None on unparseable input. Never raises to the caller."""
    try:
        if path.suffix.lower() == ".pdf":
            text = _extract_pdf(path)
        elif path.suffix.lower() in {".docx", ".doc"}:
            text = _extract_docx(path)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", path.name, exc)
        return None

    if len(text.strip()) < 200:
        logger.warning("Text layer too thin in %s; flagged for skip", path.name)
        return None

    return Document(
        doc_id=f"syl-{uuid.uuid4().hex[:8]}",
        kind=DocumentKind.SYLLABUS,
        title=path.stem,
        raw_text=text,
        source=str(path.name),
    )


def _extract_pdf(path: Path) -> str:
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _extract_docx(path: Path) -> str:
    doc = DocxDocument(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def load_syllabi(directory: Path) -> list[Document]:
    docs = []
    for path in sorted(directory.glob("*")):
        if path.is_file():
            parsed = parse_syllabus(path)
            if parsed:
                docs.append(parsed)
    return docs
```

- [ ] **Step 2: Drop 5-10 real university syllabi into `data/syllabi/`**

Real institutional PDFs. This is what makes the demo land.

- [ ] **Step 3: Verify parsing**

```bash
docker compose exec backend python -c "
from pathlib import Path
from app.pipeline.ingest import load_syllabi
docs = load_syllabi(Path('/app/data/syllabi'))
print(len(docs), 'syllabi parsed')
for d in docs: print(' ', d.title, len(d.raw_text), 'chars')
"
```
Expected: every file parsed, or a logged warning naming the ones skipped.

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipeline/ingest.py data/syllabi/
git commit -m "feat: add syllabus pdf and docx ingestion"
```

---

## PHASE 2: Core Pipeline (Hours 10-20)

### Task 9: Skill extraction via Claude

**Files:**
- Create: `backend/app/pipeline/extract.py`

- [ ] **Step 1: Implement the extractor**

The prompt constrains Claude to the taxonomy. It may not invent skills.

```python
import json
import uuid

from app.contracts import Document, SkillMention
from app.llm.claude_client import ClaudeClient
from app.taxonomy.loader import TaxonomyIndex

SYSTEM = (
    "You extract technical skills from educational and job-market text. "
    "You only return JSON. You never invent skills outside the provided list."
)

TEMPLATE = """Extract every technical skill mentioned in the text below.

You MUST choose skill names only from this allowed list:
{allowed}

Return a JSON array. Each element:
  "surface_form": the exact allowed-list name
  "context": the sentence it came from, verbatim
  "importance": 0.0 to 1.0, how central it is to the document

Return [] if no listed skill appears. Return only JSON.

TEXT:
{text}"""


class SkillExtractor:
    def __init__(self, taxonomy: TaxonomyIndex, claude: ClaudeClient):
        self.taxonomy = taxonomy
        self.claude = claude

    def extract(self, doc: Document) -> list[SkillMention]:
        prompt = TEMPLATE.format(
            allowed=json.dumps(self.taxonomy.canonical_names()),
            text=doc.raw_text[:12000],
        )
        raw = self.claude.complete_json(prompt, system=SYSTEM, fallback=[])

        mentions = []
        for item in raw or []:
            surface = item.get("surface_form", "")
            if not self.taxonomy.resolve(surface):
                continue
            mentions.append(
                SkillMention(
                    mention_id=f"m-{uuid.uuid4().hex[:8]}",
                    doc_id=doc.doc_id,
                    surface_form=surface,
                    context=item.get("context", "")[:500],
                    importance=float(item.get("importance", 0.5)),
                )
            )
        return mentions
```

- [ ] **Step 2: Verify against one real syllabus**

```bash
docker compose exec backend python -c "
from pathlib import Path
from app.pipeline.ingest import load_syllabi
from app.pipeline.extract import SkillExtractor
from app.taxonomy.loader import TaxonomyIndex
from app.llm.claude_client import ClaudeClient
docs = load_syllabi(Path('/app/data/syllabi'))
ex = SkillExtractor(TaxonomyIndex.from_disk(), ClaudeClient())
ms = ex.extract(docs[0])
print(len(ms), 'mentions')
for m in ms[:10]: print(' ', m.surface_form, round(m.importance, 2))
"
```
Expected: a non-empty list of taxonomy-valid skill names.

- [ ] **Step 3: Commit**

```bash
git add backend/app/pipeline/extract.py
git commit -m "feat: add taxonomy-constrained skill extractor"
```

---

### Task 10: ChromaDB embedding and matching

**Files:**
- Create: `backend/app/pipeline/embed.py`, `backend/app/pipeline/match.py`

- [ ] **Step 1: Implement `backend/app/pipeline/embed.py`**

```python
import chromadb
from chromadb.utils import embedding_functions

from app.config import settings
from app.taxonomy.loader import TaxonomyIndex

COLLECTION = "canonical_skills"


class SkillIndex:
    """Embedded Chroma. No separate service required."""

    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path=settings.chroma_path)
        self.embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION, embedding_function=self.embedder
        )

    def index_taxonomy(self, taxonomy: TaxonomyIndex) -> int:
        documents, ids, metadatas = [], [], []
        for skill in taxonomy.skills:
            canonical = skill["canonical_name"]
            text = f"{canonical}. {' '.join(skill.get('aliases', []))}"
            documents.append(text)
            ids.append(canonical)
            metadatas.append({"category": skill.get("category", "general")})
        self.collection.upsert(
            documents=documents, ids=ids, metadatas=metadatas
        )
        return len(ids)

    def query(self, text: str, n: int = 3) -> list[tuple[str, float]]:
        result = self.collection.query(query_texts=[text], n_results=n)
        ids = result["ids"][0]
        distances = result["distances"][0]
        return [(i, 1.0 - float(d)) for i, d in zip(ids, distances)]
```

- [ ] **Step 2: Implement `backend/app/pipeline/match.py`**

This is the designed swap seam. Output is only `ScoredPair`, so the whole module can be replaced.

```python
from app.contracts import ScoredPair, SkillMention
from app.pipeline.embed import SkillIndex
from app.taxonomy.loader import TaxonomyIndex

MIN_SIMILARITY = 0.35


class VectorMatcher:
    def __init__(self, index: SkillIndex, taxonomy: TaxonomyIndex):
        self.index = index
        self.taxonomy = taxonomy

    def match(self, mentions: list[SkillMention]) -> list[ScoredPair]:
        pairs = []
        for mention in mentions:
            exact = self.taxonomy.resolve(mention.surface_form)
            if exact:
                pairs.append(
                    ScoredPair(
                        mention_id=mention.mention_id,
                        canonical_skill=exact,
                        similarity=1.0,
                    )
                )
                continue
            hits = self.index.query(mention.surface_form, n=1)
            if hits and hits[0][1] >= MIN_SIMILARITY:
                pairs.append(
                    ScoredPair(
                        mention_id=mention.mention_id,
                        canonical_skill=hits[0][0],
                        similarity=min(max(hits[0][1], 0.0), 1.0),
                    )
                )
        return pairs
```

- [ ] **Step 3: Index the taxonomy and verify semantic matching**

```bash
docker compose exec backend python -c "
from app.pipeline.embed import SkillIndex
from app.taxonomy.loader import TaxonomyIndex
idx = SkillIndex()
print(idx.index_taxonomy(TaxonomyIndex.from_disk()), 'skills indexed')
print(idx.query('building chatbots over company documents', n=3))
"
```
Expected: the RAG or LLM skills ranked highly. First run downloads the embedding model, which takes a minute.

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipeline/embed.py backend/app/pipeline/match.py
git commit -m "feat: add chroma skill index and vector matcher"
```

---

### Task 11: Write matched edges into Neo4j

**Files:**
- Create: `backend/app/db/writer.py`

- [ ] **Step 1: Implement the graph writer**

```python
from app.contracts import Document, DocumentKind, ScoredPair, SkillMention
from app.db.neo4j_client import session


def write_course(code: str, title: str, institution: str = "") -> None:
    with session() as s:
        s.run(
            "MERGE (c:Course {code: $code}) "
            "SET c.title = $title, c.institution = $institution",
            code=code, title=title, institution=institution,
        )


def write_outcome_skills(
    course_code: str,
    doc: Document,
    mentions: list[SkillMention],
    pairs: list[ScoredPair],
) -> None:
    by_mention = {m.mention_id: m for m in mentions}
    with session() as s:
        for pair in pairs:
            mention = by_mention.get(pair.mention_id)
            if not mention:
                continue
            s.run(
                "MATCH (c:Course {code: $code}) "
                "MERGE (o:Outcome {outcome_id: $oid}) "
                "SET o.text = $text "
                "MERGE (c)-[:HAS_OUTCOME]->(o) "
                "WITH o "
                "MATCH (sk:Skill {canonical_name: $skill}) "
                "MERGE (o)-[t:TEACHES]->(sk) "
                "SET t.confidence = $confidence",
                code=course_code,
                oid=pair.mention_id,
                text=mention.context,
                skill=pair.canonical_skill,
                confidence=pair.similarity * mention.importance,
            )


def write_job_skills(
    doc: Document, mentions: list[SkillMention], pairs: list[ScoredPair]
) -> None:
    by_mention = {m.mention_id: m for m in mentions}
    with session() as s:
        s.run(
            "MERGE (j:JobPosting {doc_id: $doc_id}) "
            "SET j.title = $title, j.source = $source, j.posted_date = $posted",
            doc_id=doc.doc_id,
            title=doc.title,
            source=doc.source,
            posted=str(doc.posted_date) if doc.posted_date else None,
        )
        for pair in pairs:
            mention = by_mention.get(pair.mention_id)
            if not mention:
                continue
            s.run(
                "MATCH (j:JobPosting {doc_id: $doc_id}) "
                "MATCH (sk:Skill {canonical_name: $skill}) "
                "MERGE (j)-[r:REQUIRES]->(sk) "
                "SET r.importance = $importance",
                doc_id=doc.doc_id,
                skill=pair.canonical_skill,
                importance=mention.importance,
            )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/db/writer.py
git commit -m "feat: add neo4j edge writer for courses and jobs"
```

---

### Task 12: Gap scoring engine

**This module carries real unit tests.** Silent wrongness here poisons every number in the demo and nobody would notice.

**Files:**
- Create: `backend/app/pipeline/score.py`
- Test: `backend/tests/test_score.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_score.py
from app.contracts import GapSeverity
from app.pipeline.score import (
    classify_severity,
    compute_gap_score,
    compute_health_score,
)


def test_high_demand_zero_coverage_is_critical():
    score = compute_gap_score(
        market_demand=0.9, curriculum_coverage=0.0,
        prerequisite_distance=1, trend_slope=None,
    )
    assert score > 0.7
    assert classify_severity(score) == GapSeverity.CRITICAL


def test_full_coverage_yields_no_meaningful_gap():
    score = compute_gap_score(
        market_demand=0.9, curriculum_coverage=1.0,
        prerequisite_distance=0, trend_slope=None,
    )
    assert score < 0.2


def test_unreachable_prerequisites_reduce_actionability():
    near = compute_gap_score(0.8, 0.0, prerequisite_distance=1, trend_slope=None)
    far = compute_gap_score(0.8, 0.0, prerequisite_distance=5, trend_slope=None)
    assert near > far


def test_rising_trend_increases_urgency():
    flat = compute_gap_score(0.5, 0.2, 1, trend_slope=0.0)
    rising = compute_gap_score(0.5, 0.2, 1, trend_slope=0.8)
    assert rising > flat


def test_absent_forecaster_does_not_change_score():
    """Trend slope None must behave exactly like zero, so cutting the
    forecaster never changes the numbers on screen."""
    assert compute_gap_score(0.5, 0.2, 1, None) == compute_gap_score(
        0.5, 0.2, 1, 0.0
    )


def test_health_score_is_bounded():
    assert compute_health_score([]) == 100.0
    assert 0.0 <= compute_health_score([0.9, 0.8, 0.7]) <= 100.0


def test_more_gaps_lower_health():
    assert compute_health_score([0.9, 0.9, 0.9]) < compute_health_score([0.1])
```

- [ ] **Step 2: Run and confirm failure**

```bash
docker compose exec backend pytest tests/test_score.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.score'`

- [ ] **Step 3: Implement `backend/app/pipeline/score.py`**

```python
from app.contracts import GapSeverity

W_DEMAND = 0.45
W_COVERAGE = 0.35
W_REACHABILITY = 0.10
W_TREND = 0.10


def compute_gap_score(
    market_demand: float,
    curriculum_coverage: float,
    prerequisite_distance: int,
    trend_slope: float | None,
) -> float:
    """Higher means a more urgent, more actionable gap.

    Reachability rewards skills close to what is already taught: adding a
    skill whose prerequisites are satisfied is cheap, one needing three
    missing prerequisites is not.
    """
    coverage_deficit = 1.0 - _clamp(curriculum_coverage)
    reachability = 1.0 / (1.0 + max(prerequisite_distance, 0))
    trend = _clamp(trend_slope if trend_slope is not None else 0.0)

    raw = (
        W_DEMAND * _clamp(market_demand)
        + W_COVERAGE * coverage_deficit
        + W_REACHABILITY * reachability
        + W_TREND * trend
    )
    # Coverage gates the whole score: a fully taught skill cannot register as
    # a large gap no matter how much the market wants it.
    return round(raw * (0.4 + 0.6 * coverage_deficit), 4)


def classify_severity(score: float) -> GapSeverity:
    if score >= 0.65:
        return GapSeverity.CRITICAL
    if score >= 0.45:
        return GapSeverity.HIGH
    if score >= 0.25:
        return GapSeverity.MODERATE
    return GapSeverity.LOW


def compute_health_score(gap_scores: list[float]) -> float:
    """100 means no gaps. Weighted toward the worst offenders so a few
    critical gaps cannot be averaged away by many trivial ones."""
    if not gap_scores:
        return 100.0
    ordered = sorted(gap_scores, reverse=True)
    weights = [1.0 / (i + 1) for i in range(len(ordered))]
    weighted = sum(s * w for s, w in zip(ordered, weights)) / sum(weights)
    return round(max(0.0, min(100.0, 100.0 * (1.0 - weighted))), 1)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
```

- [ ] **Step 4: Run the tests**

```bash
docker compose exec backend pytest tests/test_score.py -v
```
Expected: 7 passed. If `test_full_coverage_yields_no_meaningful_gap` fails, the coverage multiplier needs strengthening — tune the `0.4 + 0.6 * coverage_deficit` term, not the test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/score.py backend/tests/test_score.py
git commit -m "feat: add gap scoring engine with tested math"
```

---

### Task 13: The multi-hop gap query

This query is the answer to "why Neo4j" and goes verbatim into the technical writeup.

**Files:**
- Create: `backend/app/db/queries.py`

- [ ] **Step 1: Implement the query module**

```python
from app.db.neo4j_client import session

GAP_QUERY = """
// Skills the market demands, not covered by this course, ranked by
// demand and by how close they sit to what the course already teaches.
MATCH (c:Course {code: $course_code})
OPTIONAL MATCH (c)-[:HAS_OUTCOME]->(:Outcome)-[t:TEACHES]->(taught:Skill)
WITH c, collect(DISTINCT taught) AS taught_skills

MATCH (j:JobPosting)-[r:REQUIRES]->(demanded:Skill)
WITH c, taught_skills, demanded,
     count(DISTINCT j) AS postings_requiring,
     avg(r.importance) AS avg_importance
WHERE NOT demanded IN taught_skills

OPTIONAL MATCH path = shortestPath(
  (known:Skill)-[:PREREQUISITE_OF|RELATED_TO*1..2]-(demanded)
)
WHERE known IN taught_skills

WITH demanded, postings_requiring, avg_importance,
     CASE WHEN path IS NULL THEN 99 ELSE length(path) END AS distance
MATCH (total:JobPosting)
WITH demanded, postings_requiring, avg_importance, distance,
     count(DISTINCT total) AS postings_total
RETURN demanded.canonical_name AS skill,
       postings_requiring,
       postings_total,
       coalesce(avg_importance, 0.5) AS importance,
       min(distance) AS prerequisite_distance
ORDER BY postings_requiring DESC
LIMIT 40
"""


def fetch_course_gaps(course_code: str) -> list[dict]:
    with session() as s:
        return [dict(r) for r in s.run(GAP_QUERY, course_code=course_code)]


def fetch_courses() -> list[dict]:
    with session() as s:
        return [
            dict(r)
            for r in s.run(
                "MATCH (c:Course) RETURN c.code AS code, c.title AS title "
                "ORDER BY c.code"
            )
        ]


def fetch_subgraph(limit: int = 150) -> dict:
    """Nodes and edges for the graph explorer."""
    with session() as s:
        nodes = [
            dict(r)
            for r in s.run(
                "MATCH (n) WHERE n:Course OR n:Skill OR n:JobPosting "
                "RETURN id(n) AS id, labels(n)[0] AS label, "
                "coalesce(n.canonical_name, n.title, n.code) AS name "
                "LIMIT $limit",
                limit=limit,
            )
        ]
        node_ids = {n["id"] for n in nodes}
        edges = [
            dict(r)
            for r in s.run(
                "MATCH (a)-[r]->(b) "
                "WHERE id(a) IN $ids AND id(b) IN $ids "
                "RETURN id(a) AS source, id(b) AS target, type(r) AS type",
                ids=list(node_ids),
            )
        ]
    return {"nodes": nodes, "edges": edges}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/db/queries.py
git commit -m "feat: add multi-hop gap query and graph fetchers"
```

---

### Task 14: Syllabus augmenter

**Files:**
- Create: `backend/app/pipeline/augment.py`

- [ ] **Step 1: Implement the augmenter**

The constraint against wholesale redesign is explicit in the problem statement.

```python
import json

from app.contracts import AugmentProposal, GapReport
from app.llm.claude_client import ClaudeClient

SYSTEM = (
    "You are a curriculum design assistant advising a university professor. "
    "You propose targeted additions, never wholesale redesigns. "
    "You only return JSON."
)

TEMPLATE = """Course: {course_code} - {course_title}
Current curriculum health score: {health}/100

Identified skill gaps, most urgent first:
{gaps}

Propose modifications the professor can adopt WITHOUT redesigning the course.
Respect the existing structure. Be concrete and current.

Return JSON with exactly these keys:
  "added_outcomes": 2-4 new learning outcome statements
  "case_studies": 2-3 modern industry case studies
  "toolsets": 3-5 specific tools or libraries to introduce
  "project_prompts": 2-3 assignment briefs closing these gaps
  "rationale": one paragraph justifying the changes to a curriculum committee

Return only JSON."""


class SyllabusAugmenter:
    def __init__(self, claude: ClaudeClient):
        self.claude = claude

    def propose(self, report: GapReport) -> AugmentProposal:
        gap_lines = "\n".join(
            f"- {g.canonical_skill} ({g.severity.value}): {g.evidence}"
            for g in report.gaps[:12]
        )
        prompt = TEMPLATE.format(
            course_code=report.course_code,
            course_title=report.course_title,
            health=report.health_score,
            gaps=gap_lines,
        )
        fallback = {
            "added_outcomes": [],
            "case_studies": [],
            "toolsets": [],
            "project_prompts": [],
            "rationale": "Augmentation unavailable; showing gap analysis only.",
        }
        raw = self.claude.complete_json(prompt, system=SYSTEM, fallback=fallback)
        return AugmentProposal(course_code=report.course_code, **raw)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/pipeline/augment.py
git commit -m "feat: add syllabus augmenter"
```

---

### Task 15: Seed script and orchestration

Satisfies R1. A judge must never see an empty state.

**Files:**
- Create: `backend/app/seed.py`, `backend/app/pipeline/orchestrator.py`

- [ ] **Step 1: Implement `backend/app/pipeline/orchestrator.py`**

```python
import logging
from pathlib import Path

from app.contracts import GapReport, GapSeverity, SkillGap
from app.db import writer
from app.db.queries import fetch_course_gaps
from app.llm.claude_client import ClaudeClient
from app.pipeline.embed import SkillIndex
from app.pipeline.extract import SkillExtractor
from app.pipeline.ingest import load_job_snapshot, load_syllabi
from app.pipeline.match import VectorMatcher
from app.pipeline.score import (
    classify_severity,
    compute_gap_score,
    compute_health_score,
)
from app.taxonomy.loader import TaxonomyIndex

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self) -> None:
        self.taxonomy = TaxonomyIndex.from_disk()
        self.claude = ClaudeClient()
        self.index = SkillIndex()
        self.extractor = SkillExtractor(self.taxonomy, self.claude)
        self.matcher = VectorMatcher(self.index, self.taxonomy)

    def ingest_jobs(self, limit: int | None = None) -> int:
        docs = load_job_snapshot()
        if limit:
            docs = docs[:limit]
        for doc in docs:
            mentions = self.extractor.extract(doc)
            pairs = self.matcher.match(mentions)
            writer.write_job_skills(doc, mentions, pairs)
        return len(docs)

    def ingest_syllabi(self, directory: Path) -> int:
        docs = load_syllabi(directory)
        for doc in docs:
            code = doc.title[:32]
            writer.write_course(code=code, title=doc.title)
            mentions = self.extractor.extract(doc)
            pairs = self.matcher.match(mentions)
            writer.write_outcome_skills(code, doc, mentions, pairs)
        return len(docs)

    def build_report(self, course_code: str, course_title: str) -> GapReport:
        rows = fetch_course_gaps(course_code)
        gaps, scores = [], []
        for row in rows:
            total = max(row["postings_total"], 1)
            demand = row["postings_requiring"] / total
            distance = row["prerequisite_distance"]
            score = compute_gap_score(
                market_demand=demand,
                curriculum_coverage=0.0,
                prerequisite_distance=distance if distance < 99 else 6,
                trend_slope=None,
            )
            scores.append(score)
            gaps.append(
                SkillGap(
                    canonical_skill=row["skill"],
                    severity=classify_severity(score),
                    market_demand=round(demand, 4),
                    curriculum_coverage=0.0,
                    prerequisite_distance=distance,
                    trend_slope=None,
                    postings_requiring=row["postings_requiring"],
                    postings_total=total,
                    evidence=(
                        f"{row['postings_requiring']} of {total} postings "
                        f"require this; no outcome in this course covers it"
                    ),
                )
            )
        gaps.sort(key=lambda g: g.market_demand, reverse=True)
        return GapReport(
            course_code=course_code,
            course_title=course_title,
            health_score=compute_health_score(scores),
            gaps=gaps,
        )
```

- [ ] **Step 2: Implement `backend/app/seed.py`**

```python
import logging
from pathlib import Path

from app.db.schema import apply_constraints, load_taxonomy
from app.pipeline.orchestrator import Pipeline
from app.taxonomy.loader import TaxonomyIndex

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed(job_limit: int = 400) -> None:
    apply_constraints()
    taxonomy = TaxonomyIndex.from_disk()
    logger.info("Loaded %d skills", load_taxonomy(taxonomy))

    pipeline = Pipeline()
    logger.info("Indexed %d skills", pipeline.index.index_taxonomy(taxonomy))
    logger.info("Ingested %d syllabi", pipeline.ingest_syllabi(Path("/app/data/syllabi")))
    logger.info("Ingested %d job postings", pipeline.ingest_jobs(limit=job_limit))


if __name__ == "__main__":
    seed()
```

- [ ] **Step 3: Run the seed**

`job_limit` exists because extracting from 3000 postings costs real time and money. 400 is enough for credible statistics; raise it if the cache is warm.

```bash
docker compose exec backend python -m app.seed
```
Expected: log lines for each stage, ending with the job posting count.

- [ ] **Step 4: Verify the graph is populated**

```bash
docker compose exec neo4j cypher-shell -u neo4j -p curricualign \
  "MATCH (c:Course) RETURN count(c) AS courses;
   MATCH (j:JobPosting) RETURN count(j) AS jobs;
   MATCH ()-[r:REQUIRES]->() RETURN count(r) AS requires;"
```
Expected: non-zero on all three.

- [ ] **Step 5: Commit**

```bash
git add backend/app/seed.py backend/app/pipeline/orchestrator.py
git commit -m "feat: add pipeline orchestrator and seed script"
```

---

### Task 16: API endpoints

**Files:**
- Create: `backend/app/api/courses.py`, `backend/app/api/graph.py`, `backend/app/api/market.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implement `backend/app/api/courses.py`**

```python
from fastapi import APIRouter, HTTPException

from app.contracts import AugmentProposal, GapReport
from app.db.queries import fetch_courses
from app.llm.claude_client import ClaudeClient
from app.pipeline.augment import SyllabusAugmenter
from app.pipeline.orchestrator import Pipeline
from app.pipeline.score import compute_health_score

router = APIRouter(prefix="/api", tags=["courses"])
_pipeline: Pipeline | None = None


def pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline


@router.get("/courses")
def list_courses() -> list[dict]:
    courses = fetch_courses()
    out = []
    for course in courses:
        report = pipeline().build_report(course["code"], course["title"])
        out.append(
            {
                "code": course["code"],
                "title": course["title"],
                "health_score": report.health_score,
                "gap_count": len(report.gaps),
            }
        )
    return out


@router.get("/courses/{course_code}/gaps", response_model=GapReport)
def course_gaps(course_code: str) -> GapReport:
    courses = {c["code"]: c["title"] for c in fetch_courses()}
    if course_code not in courses:
        raise HTTPException(status_code=404, detail="Course not found")
    return pipeline().build_report(course_code, courses[course_code])


@router.post("/augment/{course_code}", response_model=AugmentProposal)
def augment(course_code: str) -> AugmentProposal:
    report = course_gaps(course_code)
    return SyllabusAugmenter(ClaudeClient()).propose(report)
```

- [ ] **Step 2: Implement `backend/app/api/graph.py`**

```python
from fastapi import APIRouter

from app.db.queries import fetch_subgraph

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph")
def graph(limit: int = 150) -> dict:
    return fetch_subgraph(limit=limit)
```

- [ ] **Step 3: Implement `backend/app/api/market.py`**

The contract holds whether or not the forecaster ships.

```python
from collections import defaultdict

from fastapi import APIRouter

from app.contracts import SkillTrend, TrendPoint
from app.db.neo4j_client import session

router = APIRouter(prefix="/api", tags=["market"])

TREND_QUERY = """
MATCH (j:JobPosting)-[:REQUIRES]->(s:Skill)
WHERE j.posted_date IS NOT NULL
RETURN s.canonical_name AS skill,
       substring(j.posted_date, 0, 7) AS period,
       count(*) AS frequency
ORDER BY period
"""


@router.get("/market/trends", response_model=list[SkillTrend])
def trends(limit: int = 20) -> list[SkillTrend]:
    """Slope is None until the forecaster ships. Shape never changes."""
    buckets: dict[str, list[TrendPoint]] = defaultdict(list)
    with session() as s:
        for row in s.run(TREND_QUERY):
            buckets[row["skill"]].append(
                TrendPoint(period=row["period"], frequency=row["frequency"])
            )
    ranked = sorted(
        buckets.items(),
        key=lambda kv: sum(p.frequency for p in kv[1]),
        reverse=True,
    )[:limit]
    return [
        SkillTrend(canonical_skill=name, history=points, slope=None)
        for name, points in ranked
    ]
```

- [ ] **Step 4: Register routers in `backend/app/main.py`**

```python
from app.api import courses, graph, market

app.include_router(courses.router)
app.include_router(graph.router)
app.include_router(market.router)
```

- [ ] **Step 5: Verify every endpoint responds**

```bash
curl -s http://localhost:8000/api/courses | head -c 400; echo
curl -s http://localhost:8000/api/graph?limit=20 | head -c 400; echo
curl -s http://localhost:8000/api/market/trends?limit=3 | head -c 400; echo
```
Expected: JSON from all three, none empty after seeding.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/ backend/app/main.py
git commit -m "feat: add course, graph, and market api endpoints"
```

---

### Task 17: End-to-end smoke test

**Files:**
- Create: `backend/tests/test_smoke.py`

- [ ] **Step 1: Write the smoke test**

```python
# backend/tests/test_smoke.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_courses_endpoint_returns_seeded_data():
    response = client.get("/api/courses")
    assert response.status_code == 200
    courses = response.json()
    assert len(courses) > 0, "seed did not run"
    assert all("health_score" in c for c in courses)


def test_gap_report_has_evidence():
    courses = client.get("/api/courses").json()
    code = courses[0]["code"]
    report = client.get(f"/api/courses/{code}/gaps").json()
    assert report["gaps"], "no gaps computed"
    assert all(g["evidence"] for g in report["gaps"])


def test_graph_endpoint_returns_nodes_and_edges():
    data = client.get("/api/graph?limit=50").json()
    assert data["nodes"]
    assert data["edges"]
```

- [ ] **Step 2: Run the full suite**

```bash
docker compose exec backend pytest tests/ -v
```
Expected: all pass. Failures in `test_courses_endpoint_returns_seeded_data` mean the seed did not run.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_smoke.py
git commit -m "test: add end-to-end smoke tests"
```

---

## HOUR 20 GATE

Stop and verify. This is pass/fail, not a judgement call. Run from a clean checkout:

```bash
docker compose down -v && docker compose up -d --build
docker compose exec backend python -m app.seed
```

- [ ] Dashboard shows a Curriculum Health Score computed from seeded data
- [ ] A course view shows at least five ranked gaps, each with evidence
- [ ] Graph explorer renders Course, Skill, and JobPosting nodes with gaps highlighted
- [ ] Augmenter returns Claude-generated modifications as a diff for one course

**If any criterion fails, cut scope. Phase 4 goes first. Do not extend the deadline.**

---

## PHASE 3: Frontend (Hours 14-26)

Runs in parallel with Phase 2 against seeded data. Task-level detail; UI work is iterative and the spec pins the requirements.

### Task 18: Next.js scaffold and generated API types

- [ ] Scaffold: `npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir`
- [ ] Add the frontend service to `docker-compose.yml` (image `node:22-alpine`, port 3000, `NEXT_PUBLIC_API_URL` from env, never hardcoded)
- [ ] Generate types from the live OpenAPI schema so frontend and backend cannot drift:
  `npx openapi-typescript http://localhost:8000/openapi.json -o frontend/lib/api-types.ts`
- [ ] Create `frontend/lib/api.ts` with a typed fetch wrapper reading `NEXT_PUBLIC_API_URL`
- [ ] Commit

### Task 19: Dashboard screen (demo peak 1)

- [ ] Program-level health score as the visual anchor
- [ ] Ranked top gaps across all courses, each showing its evidence string
- [ ] Course cards linking to detail views
- [ ] Trend highlights from `/api/market/trends`, rendering history without projection when `slope` is null
- [ ] Must be legible with no explanation - this is what an unattended judge sees first
- [ ] Commit

### Task 20: Course detail screen (demo peak 2)

- [ ] Per-course health score and ranked gap list
- [ ] Severity styling: critical, high, moderate, low
- [ ] Evidence line under every gap ("47 of 312 postings require this; no outcome covers it")
- [ ] Prerequisite distance shown as an actionability signal
- [ ] Button routing to the augmenter
- [ ] Commit

### Task 21: Graph explorer (demo peak 3)

- [ ] Force-directed rendering from `/api/graph` using `react-force-graph-2d`
- [ ] Node colour by label: Course, Skill, JobPosting
- [ ] Gap skills highlighted distinctly
- [ ] Click a node to filter its neighbourhood
- [ ] This screen is what makes the mandated Neo4j component visible rather than implied
- [ ] Commit

### Task 22: Augmenter screen (demo peak 4)

- [ ] Trigger `POST /api/augment/{code}`, with a loading state (Claude takes seconds)
- [ ] Render added outcomes, case studies, toolsets, and project prompts as a red/green diff against the original
- [ ] Show the rationale paragraph, written for a curriculum committee
- [ ] Export to PDF or Markdown
- [ ] Commit

### Task 23: Guided tour (satisfies R2)

- [ ] Persistent "Take the tour" control on every screen
- [ ] Steps through all four screens in order with short explanatory copy
- [ ] Auto-offer on first visit, dismissible
- [ ] This is the direct answer to unattended judging
- [ ] Commit

### Task 24: Upload flow

- [ ] Drag-and-drop PDF to `POST /api/syllabi`
- [ ] Live progress through the pipeline stages
- [ ] Proves the pipeline is real rather than fixture-backed
- [ ] Never the only path to results; seeded data always remains
- [ ] Commit

---

## PHASE 4: Differentiators (Hours 20-30)

**Cut these first if the hour-20 gate fails.** Both have deterministic fallbacks.

### Task 25: Fine-tuned skill embeddings

- [ ] Build training pairs from taxonomy aliases: (alias, canonical) positive, random cross-skill negative
- [ ] Fine-tune `all-MiniLM-L6-v2` with `MultipleNegativesRankingLoss`, 1-2 epochs
- [ ] Hold out 20 percent of aliases; measure top-1 retrieval accuracy before and after
- [ ] Save to `backend/models/skill-embeddings/`, point `EMBEDDING_MODEL` at it
- [ ] Record both numbers for the writeup
- [ ] **Fallback:** revert `EMBEDDING_MODEL` to the base model. One config change.
- [ ] Commit

### Task 26: Trend forecaster

- [ ] Bucket `REQUIRES` edges by `posted_date` month per skill
- [ ] Fit linear regression on frequency over time; normalize slope to -1..1
- [ ] Populate `SkillTrend.slope` and feed `compute_gap_score`
- [ ] Surface as "demand up N percent over M months; curriculum coverage zero"
- [ ] **Fallback:** slope stays None, which the tested math treats identically to zero
- [ ] Commit

---

## PHASE 5: Submission (Hours 26-36)

**Never cut. These are scored.**

### Task 27: README

- [ ] Problem-to-solution narrative
- [ ] Mermaid architecture diagram of the six-stage pipeline
- [ ] Screenshots or GIFs of all four screens
- [ ] One-command setup: `cp .env.example .env && docker compose up -d && docker compose exec backend python -m app.seed`
- [ ] No emojis
- [ ] Commit

### Task 28: Technical writeup

- [ ] Graph schema and the multi-hop Cypher query verbatim as the "why Neo4j" defence
- [ ] Embedding strategy with before/after retrieval numbers if Task 25 shipped
- [ ] The four-signal gap score with weights justified
- [ ] Honest limitations section - judges trust a system that states its own weaknesses
- [ ] Commit

### Task 29: Demo video

- [ ] Script first, then record. 3-5 minutes.
- [ ] Follow the four peaks: dashboard, gaps with evidence, graph, augmenter diff
- [ ] Insurance against anything breaking during judging

### Task 30: Deploy

- [ ] Neo4j to Aura Free; run schema and seed against it
- [ ] Backend to Render or Railway with env vars from `.env.example`
- [ ] Frontend to Vercel with `NEXT_PUBLIC_API_URL` pointed at the backend
- [ ] Verify the seeded demo works end to end on the public URL
- [ ] **Schedule no later than hour 30.** Online judging makes a local-only stack unreachable.

### Task 31: Final pass

- [ ] Walk the app cold, as a judge would: every screen loads from seeded state
- [ ] Guided tour completes without error
- [ ] Random clicking does not produce a crash or an empty state
- [ ] `grep -rP "[\x{1F300}-\x{1FAFF}]" --include="*.tsx" --include="*.py" --include="*.md" .` returns nothing
- [ ] Commit

---

## Self-Review Notes

**Spec coverage:** all thirteen spec sections map to tasks. Three mandated components: Neo4j (Tasks 6, 11, 13), ChromaDB (Task 10), LLM augmenter (Task 14). R1 seeding is Task 15, R2 tour is Task 23, R3 fallbacks are Tasks 4, 10, 25, 26.

**Type consistency:** every type used in Tasks 9-16 is defined in Task 3. `TaxonomyIndex.resolve` and `.canonical_names` are used consistently from Task 5 onward. `compute_gap_score` keeps the same four-parameter signature in the test, the implementation, and the orchestrator.

**Known rough edge:** the `compute_gap_score` weights in Task 12 are a first estimate and will need tuning against real seeded data — the coverage gate in particular. The tests define the required behaviour; tune the constants, not the tests.

**Environment blockers found during planning (2026-07-31):** Docker Desktop is installed but its daemon was not running, and Python is absent from the host. Neither breaks the design, but both block hour zero. See the PRE-SPRINT section.
