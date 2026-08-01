"""Ingestion must never crash a batch.

One malformed PDF in a folder of ten cannot be allowed to take down the
whole run, so every failure path here is expected to degrade to a skip.
"""

import json
from pathlib import Path

from app.contracts import DocumentKind
from app.pipeline.ingest import (
    load_job_metadata,
    load_job_snapshot,
    load_syllabi,
    parse_syllabus,
)

SNAPSHOT = Path(__file__).parent.parent.parent / "data" / "jobs_snapshot.json"


def test_missing_snapshot_returns_empty_not_error(tmp_path):
    assert load_job_snapshot(tmp_path / "nope.json") == []


def test_malformed_posting_is_skipped_not_fatal(tmp_path):
    """A single bad record must not lose the other 304."""
    snapshot = tmp_path / "jobs.json"
    snapshot.write_text(
        json.dumps(
            [
                {
                    "doc_id": "job-1",
                    "title": "Engineer",
                    "raw_text": "text",
                    "source": "test",
                    "posted_date": "2026-07-01",
                },
                {"doc_id": "job-2"},
                {
                    "doc_id": "job-3",
                    "title": "Developer",
                    "raw_text": "text",
                    "source": "test",
                    "posted_date": "2026-07-02",
                },
            ]
        ),
        encoding="utf-8",
    )

    documents = load_job_snapshot(snapshot)

    assert [d.doc_id for d in documents] == ["job-1", "job-3"]


def test_real_snapshot_loads_if_present():
    if not SNAPSHOT.exists():
        return

    documents = load_job_snapshot(SNAPSHOT)

    assert len(documents) >= 100, "corpus too small to produce credible statistics"
    assert all(d.kind == DocumentKind.JOB_POSTING for d in documents)
    assert all(d.posted_date is not None for d in documents), (
        "the trend forecaster depends on every posting having a date"
    )


def test_real_snapshot_has_no_replacement_characters():
    """Arbeitnow mangles some non-ASCII text upstream. The fetcher strips
    the resulting markers; this guards that it stays stripped."""
    if not SNAPSHOT.exists():
        return

    documents = load_job_snapshot(SNAPSHOT)
    corrupted = [d.doc_id for d in documents if "�" in d.raw_text]

    assert corrupted == [], f"replacement characters survived in {corrupted[:3]}"


def test_metadata_keeps_graph_fields_out_of_the_contract():
    """company and source_url belong on the JobPosting node, not on
    Document, so they travel separately."""
    if not SNAPSHOT.exists():
        return

    metadata = load_job_metadata(SNAPSHOT)

    assert metadata
    sample = next(iter(metadata.values()))
    assert set(sample) == {"company", "source_url", "seniority"}


def test_unparseable_file_returns_none(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"this is not a pdf at all")

    assert parse_syllabus(broken) is None


def test_file_with_thin_text_layer_is_skipped(tmp_path):
    """A scanned PDF yields almost no text. Better to flag it than to feed
    three words into the extractor and call the result a syllabus."""
    thin = tmp_path / "scanned.txt"
    thin.write_text("Course outline", encoding="utf-8")

    assert parse_syllabus(thin) is None


def test_plain_text_syllabus_parses(tmp_path):
    syllabus = tmp_path / "CS101_Intro_to_Databases.txt"
    syllabus.write_text(
        "Course outcomes: students will design relational schemas, "
        "write SQL queries, apply normalization, and reason about "
        "transaction isolation. " * 6,
        encoding="utf-8",
    )

    document = parse_syllabus(syllabus)

    assert document is not None
    assert document.kind == DocumentKind.SYLLABUS
    assert document.title == "CS101 Intro to Databases"


def test_load_syllabi_skips_failures_and_keeps_the_rest(tmp_path):
    good = tmp_path / "good_course.txt"
    good.write_text("Outcomes: build web applications with REST APIs. " * 12, encoding="utf-8")
    (tmp_path / "bad_course.pdf").write_bytes(b"not a pdf")
    (tmp_path / "thin.txt").write_text("too short", encoding="utf-8")

    documents = load_syllabi(tmp_path)

    assert len(documents) == 1
    assert documents[0].title == "good course"


def test_missing_syllabus_directory_returns_empty(tmp_path):
    assert load_syllabi(tmp_path / "does_not_exist") == []
