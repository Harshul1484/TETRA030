"""Populate the database so the application works with zero setup.

Anyone opening the app must land on a populated dashboard with real courses
and computed gaps, never an empty state asking them to upload something
first.

Every Claude call made here is cached to disk by content hash, so a second
run costs nothing and takes seconds. The cache directory is worth keeping
between runs for exactly that reason.

Usage:

    docker compose exec backend python -m app.seed
    docker compose exec backend python -m app.seed --jobs 100 --reset
"""

import argparse
import logging
from pathlib import Path

from app.db import writer
from app.db.schema import apply_constraints, graph_counts, load_taxonomy
from app.pipeline.orchestrator import Pipeline
from app.taxonomy.loader import TaxonomyIndex

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SYLLABUS_DIR = Path("/app/data/syllabi")
JOB_SNAPSHOT = Path("/app/data/jobs_snapshot.json")

# Extraction costs one Claude call per posting on a cold cache. The default
# balances a credible evidence denominator against that cost; raise it once
# the cache is warm, since repeats are free.
DEFAULT_JOB_LIMIT = 120


def seed(
    job_limit: int = DEFAULT_JOB_LIMIT,
    reset: bool = False,
    syllabus_dir: Path | None = None,
    snapshot: Path | None = None,
) -> dict:
    apply_constraints()

    taxonomy = TaxonomyIndex.from_disk()
    taxonomy_result = load_taxonomy(taxonomy)
    logger.info(
        "Taxonomy: %d skills, %d prerequisite edges",
        taxonomy_result["skills"],
        taxonomy_result["prerequisite_edges"],
    )

    if reset:
        logger.info("Reset: %s", writer.clear_ingested_data())

    pipeline = Pipeline()
    logger.info("Vector index: %d skills", pipeline.index_taxonomy())

    courses = pipeline.ingest_syllabi(syllabus_dir or SYLLABUS_DIR)
    logger.info("Courses: %d ingested %s", len(courses), courses)

    postings = pipeline.ingest_jobs(limit=job_limit, snapshot=snapshot or JOB_SNAPSHOT)
    logger.info("Job postings: %d ingested", postings)

    counts = graph_counts()
    logger.info("Graph: %s", counts)

    return {
        "courses": len(courses),
        "postings": postings,
        "skills": counts.get("skills", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the CurricuAlign database")
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOB_LIMIT,
        help="how many job postings to ingest",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="remove existing courses and postings, keeping the taxonomy",
    )
    args = parser.parse_args()

    result = seed(job_limit=args.jobs, reset=args.reset)

    if result["courses"] == 0:
        logger.warning("No courses ingested. The dashboard will be empty.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
