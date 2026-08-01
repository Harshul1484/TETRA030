"""Fetch a job posting snapshot from public job APIs.

The snapshot is committed to the repository and becomes the demo path:
instant, reproducible, and offline-safe. Live fetching exists to prove the
pipeline is real, not to serve the demo.

Two sources, for different reasons:

  Arbeitnow  paginated and large, supplies the volume needed for credible
             market statistics
  Remotive   smaller but tech-dense; their terms require attribution and ask
             that the API be called only a few times a day, so we call it
             once and store the source URL on every posting

Both are free and need no API key. Postings without a publication date are
discarded, since the trend forecaster depends on that field.

Usage, from the repository root:

    python scripts/fetch_jobs.py [--pages N]
"""

import argparse
import html
import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ARBEITNOW = "https://www.arbeitnow.com/api/job-board-api?page={page}"
REMOTIVE = "https://remotive.com/api/remote-jobs"

OUTPUT = Path("data/jobs_snapshot.json")
REQUEST_DELAY_SECONDS = 1.0
DEFAULT_PAGES = 20
MIN_DESCRIPTION_CHARS = 200

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

# Only postings that plausibly demand skills in our taxonomy are useful. A
# sales or landscaping role adds noise to the demand signal without adding
# anything a computing curriculum could act on.
#
# Matched against the TITLE only. Matching against tags proved far too loose:
# Arbeitnow attaches a "data" tag to sales roles, which pulled account
# executives and landscape architects into the corpus.
TECH_TITLE_SIGNALS = {
    "engineer", "developer", "software", "devops", "backend", "frontend",
    "full stack", "fullstack", "data scientist", "data analyst",
    "data engineer", "machine learning", "artificial intelligence",
    "programmer", "architect", "sre", "site reliability", "qa engineer",
    "test engineer", "android", "ios ", "web dev", "cto", "tech lead",
    "technical lead", "cloud", "platform engineer", "security engineer",
    "database", "sysadmin", "system administrator", "it consultant",
    "informatiker", "entwickler", "programmierer",
}

# Titles containing these are rejected outright even if a tech word appears,
# because the role is not a technical one.
NON_TECH_TITLE_SIGNALS = {
    "sales", "account executive", "recruiter", "hr ", "human resources",
    "marketing", "vertrieb", "buchhaltung", "landschaftsarchitekt",
    "pflege", "nurse", "teacher", "lehrer", "driver", "fahrer",
    "customer service", "kundenservice", "social media", "content writer",
    "copywriter", "graphic design", "vertragswesen", "einkauf",
}


def strip_html(raw: str) -> str:
    """Both APIs return HTML descriptions. The extractor wants prose.

    Arbeitnow's own data contains U+FFFD replacement characters, meaning
    the text was mangled upstream before we fetched it: "fuer" spelled with
    an umlaut arrives as "f�r". Verified by inspecting the raw response
    bytes, which contain no valid UTF-8 umlaut sequences at all. Nothing can
    recover the original character, so the marker is removed rather than
    left to be embedded as noise.
    """
    text = TAG_RE.sub(" ", raw or "")
    text = html.unescape(text)
    text = text.replace("�", "")
    return WHITESPACE_RE.sub(" ", text).strip()


def clean_title(raw: str) -> str:
    """Titles carry the same upstream mangling as descriptions."""
    return WHITESPACE_RE.sub(" ", (raw or "").replace("�", "")).strip()


def is_technical(title: str, tags: list) -> bool:
    """Title-only matching, with an explicit reject list.

    The `tags` parameter is accepted but deliberately unused: tag-based
    matching pulled in sales and landscaping roles whose tags happened to
    include "data".
    """
    lowered = title.lower()
    if any(signal in lowered for signal in NON_TECH_TITLE_SIGNALS):
        return False
    return any(signal in lowered for signal in TECH_TITLE_SIGNALS)


def infer_seniority(title: str) -> str:
    lowered = title.lower()
    if any(w in lowered for w in ("intern", "graduate", "junior", "entry", "trainee")):
        return "junior"
    if any(w in lowered for w in ("senior", "staff", "principal", "lead", "head of")):
        return "senior"
    return "mid"


def build_record(
    doc_id: str,
    title: str,
    description: str,
    tags: list,
    source: str,
    source_url: str,
    posted_date: str,
    company: str,
) -> dict | None:
    if not posted_date or len(description) < MIN_DESCRIPTION_CHARS:
        return None

    raw_text = f"{title}\n\n{description}"
    if tags:
        # Tag lists are high-signal: they read close to skill names, so
        # appending them gives the extractor a denser second pass.
        raw_text += "\n\nTags: " + ", ".join(str(t) for t in tags)

    return {
        "doc_id": doc_id,
        "kind": "job_posting",
        "title": title,
        "raw_text": raw_text,
        "source": source,
        "source_url": source_url,
        "posted_date": posted_date,
        "company": company,
        "seniority": infer_seniority(title),
    }


def fetch_json(url: str) -> dict:
    """Decode explicitly as UTF-8 rather than letting json infer it."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "Vedha-AI/0.1 (hackathon project)"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_arbeitnow(pages: int) -> list[dict]:
    records = []
    for page in range(1, pages + 1):
        try:
            payload = fetch_json(ARBEITNOW.format(page=page))
        except Exception as exc:
            print(f"  arbeitnow page {page}: FAILED ({type(exc).__name__})")
            break

        jobs = payload.get("data", [])
        if not jobs:
            break

        kept = 0
        for job in jobs:
            tags = job.get("tags") or []
            title = clean_title(job.get("title"))
            if not is_technical(title, tags):
                continue

            created = job.get("created_at")
            posted = (
                datetime.fromtimestamp(created).strftime("%Y-%m-%d")
                if isinstance(created, (int, float))
                else str(created or "")[:10]
            )

            record = build_record(
                doc_id=f"an-{job.get('slug', '')}"[:80],
                title=title,
                description=strip_html(job.get("description", "")),
                tags=tags,
                source="arbeitnow",
                source_url=job.get("url", ""),
                posted_date=posted,
                company=job.get("company_name", ""),
            )
            if record:
                records.append(record)
                kept += 1

        print(f"  arbeitnow page {page}: {len(jobs)} returned, {kept} technical")
        time.sleep(REQUEST_DELAY_SECONDS)

    return records


def fetch_remotive() -> list[dict]:
    """Single call. Remotive asks for at most a few requests per day."""
    try:
        payload = fetch_json(REMOTIVE)
    except Exception as exc:
        print(f"  remotive: FAILED ({type(exc).__name__})")
        return []

    jobs = payload.get("jobs", [])
    records = []
    for job in jobs:
        tags = job.get("tags") or []
        title = clean_title(job.get("title"))
        if not is_technical(title, tags):
            continue

        record = build_record(
            doc_id=f"rm-{job.get('id')}",
            title=title,
            description=strip_html(job.get("description", "")),
            tags=tags,
            source="remotive",
            source_url=job.get("url", ""),
            posted_date=str(job.get("publication_date", ""))[:10],
            company=job.get("company_name", ""),
        )
        if record:
            records.append(record)

    print(f"  remotive: {len(jobs)} returned, {len(records)} technical")
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=DEFAULT_PAGES)
    args = parser.parse_args()

    print("Fetching job postings")
    collected: dict[str, dict] = {}

    for record in fetch_arbeitnow(args.pages) + fetch_remotive():
        collected.setdefault(record["doc_id"], record)

    if not collected:
        print("\nNo postings collected. Snapshot not written.")
        return 1

    postings = sorted(
        collected.values(), key=lambda r: r["posted_date"], reverse=True
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(postings, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    dates = [r["posted_date"] for r in postings]
    by_source: dict[str, int] = {}
    for record in postings:
        by_source[record["source"]] = by_source.get(record["source"], 0) + 1

    print()
    print(f"wrote {len(postings)} postings to {OUTPUT}")
    print(f"by source: {by_source}")
    print(f"date range: {min(dates)} to {max(dates)}")
    print(f"fetched at: {datetime.now().isoformat(timespec='seconds')}")
    print()
    print("Sources: Arbeitnow (arbeitnow.com) and Remotive (remotive.com).")
    print("Remotive requires attribution under their API terms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
