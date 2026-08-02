"""Detect curriculum drift by re-auditing against fresher market data.

The premise of this product is that curricula fall behind. A single scan
cannot demonstrate that: it shows a gap, not a trend. Re-auditing turns the
tool from a one-off audit into a monitor, which is what an institution would
actually subscribe to.

An audit snapshot records which skills the market demanded and how strongly,
at a point in time. Comparing two snapshots answers the question a dean asks
on the second visit: what changed since we last looked?
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.db.neo4j_client import session

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path("/app/data/audits")

# A skill must move by more than this share of postings before it counts as
# a change rather than sampling noise.
MIN_MOVEMENT = 0.02

DEMAND_QUERY = """
MATCH (total:JobPosting)
WITH count(DISTINCT total) AS postings_total
MATCH (j:JobPosting)-[:REQUIRES]->(s:Skill)
WITH postings_total, s.canonical_name AS skill, count(DISTINCT j) AS requiring
RETURN skill, requiring, postings_total
ORDER BY requiring DESC
"""


def capture_snapshot(directory: Path | None = None) -> dict:
    """Record what the market demands right now.

    Stored as a plain JSON file rather than in the graph: an audit history is
    an append-only log, and keeping it out of Neo4j means re-seeding the
    graph never destroys the record of what was true last month.
    """
    with session() as s:
        rows = [dict(r) for r in s.run(DEMAND_QUERY)]

    total = rows[0]["postings_total"] if rows else 0
    snapshot = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "postings_total": total,
        "demand": {r["skill"]: r["requiring"] for r in rows},
    }

    target = directory or SNAPSHOT_DIR
    target.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["captured_at"].replace(":", "").replace("-", "")
    (target / f"audit-{stamp}.json").write_text(
        json.dumps(snapshot, indent=1), encoding="utf-8"
    )
    return snapshot


def load_snapshots(directory: Path | None = None) -> list[dict]:
    target = directory or SNAPSHOT_DIR
    if not target.exists():
        return []

    snapshots = []
    for path in sorted(target.glob("audit-*.json")):
        try:
            snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Skipping unreadable snapshot %s: %s", path.name, exc)
    return sorted(snapshots, key=lambda s: s.get("captured_at", ""))


def compare(previous: dict, current: dict) -> dict:
    """What changed in market demand between two audits.

    Shares rather than raw counts, because two snapshots rarely contain the
    same number of postings and comparing counts across different corpus
    sizes would report movement that is purely an artifact of sampling.
    """
    prev_total = max(previous.get("postings_total", 0), 1)
    curr_total = max(current.get("postings_total", 0), 1)

    prev = {k: v / prev_total for k, v in previous.get("demand", {}).items()}
    curr = {k: v / curr_total for k, v in current.get("demand", {}).items()}

    emerged = []
    faded = []
    rising = []
    falling = []

    for skill, share in curr.items():
        if skill not in prev:
            if share >= MIN_MOVEMENT:
                emerged.append({"skill": skill, "share": round(share, 4)})
            continue
        delta = share - prev[skill]
        if delta >= MIN_MOVEMENT:
            rising.append(
                {
                    "skill": skill,
                    "from": round(prev[skill], 4),
                    "to": round(share, 4),
                    "delta": round(delta, 4),
                }
            )
        elif delta <= -MIN_MOVEMENT:
            falling.append(
                {
                    "skill": skill,
                    "from": round(prev[skill], 4),
                    "to": round(share, 4),
                    "delta": round(delta, 4),
                }
            )

    for skill, share in prev.items():
        if skill not in curr and share >= MIN_MOVEMENT:
            faded.append({"skill": skill, "share": round(share, 4)})

    rising.sort(key=lambda r: -r["delta"])
    falling.sort(key=lambda r: r["delta"])
    emerged.sort(key=lambda r: -r["share"])
    faded.sort(key=lambda r: -r["share"])

    return {
        "from": previous.get("captured_at"),
        "to": current.get("captured_at"),
        "postings_before": previous.get("postings_total", 0),
        "postings_after": current.get("postings_total", 0),
        "emerged": emerged[:10],
        "faded": faded[:10],
        "rising": rising[:10],
        "falling": falling[:10],
        "change_count": len(emerged) + len(rising),
    }


def latest_drift(directory: Path | None = None) -> dict | None:
    """Compare the two most recent audits.

    Returns None when there is only one, because a single snapshot cannot
    show drift and pretending otherwise would be inventing a trend.
    """
    snapshots = load_snapshots(directory)
    if len(snapshots) < 2:
        return None
    return compare(snapshots[-2], snapshots[-1])
