"""The roadmap turns a ranked gap list into a teaching sequence.

Its one hard guarantee is that a skill never appears before something it
depends on. A plan that schedules Amazon Web Services before Cloud Computing
is worse than no plan, because a committee might follow it.
"""

from unittest.mock import patch

from app.contracts import GapSeverity, SkillGap
from app.pipeline.roadmap import build_roadmap


def _gap(skill, category="cloud", requiring=40):
    return SkillGap(
        canonical_skill=skill,
        category=category,
        severity=GapSeverity.HIGH,
        market_demand=requiring / 100,
        curriculum_coverage=0.0,
        prerequisite_distance=2,
        postings_requiring=requiring,
        postings_total=100,
        evidence=f"{requiring} of 100 postings require this",
    )


def _build(gaps, prerequisites=None, taught=None, **kwargs):
    with patch(
        "app.pipeline.roadmap.fetch_prerequisites", return_value=prerequisites or {}
    ), patch("app.pipeline.roadmap.fetch_taught", return_value=set(taught or [])):
        return build_roadmap("CS101", gaps, **kwargs)


def _order(roadmap):
    """Flatten the plan into the order skills are taught."""
    return [
        entry["skill"] for stage in roadmap["stages"] for entry in stage["skills"]
    ]


def test_empty_gap_list_yields_an_empty_plan():
    plan = _build([])
    assert plan["stages"] == []


def test_independent_skills_all_land_in_the_first_stage():
    plan = _build([_gap("Docker"), _gap("Python"), _gap("SQL")])
    assert plan["stage_count"] == 1
    assert len(plan["stages"][0]["skills"]) == 3


def test_a_skill_never_precedes_its_prerequisite():
    """The core guarantee."""
    plan = _build(
        [_gap("Amazon Web Services"), _gap("Cloud Computing")],
        prerequisites={
            "Amazon Web Services": ["Cloud Computing"],
            "Cloud Computing": [],
        },
    )

    order = _order(plan)
    assert order.index("Cloud Computing") < order.index("Amazon Web Services")


def test_a_chain_produces_one_stage_per_link():
    plan = _build(
        [_gap("RAG"), _gap("Vector Databases"), _gap("Databases")],
        prerequisites={
            "RAG": ["Vector Databases"],
            "Vector Databases": ["Databases"],
            "Databases": [],
        },
    )

    assert _order(plan) == ["Databases", "Vector Databases", "RAG"]
    assert plan["stage_count"] == 3


def test_prerequisites_already_taught_do_not_block():
    """A course teaching Databases can take Vector Databases immediately."""
    plan = _build(
        [_gap("Vector Databases")],
        prerequisites={"Vector Databases": ["Databases"]},
        taught=["Databases"],
    )

    assert plan["stage_count"] == 1
    assert plan["stages"][0]["skills"][0]["already_taught"] == ["Databases"]


def test_prerequisites_outside_the_plan_are_named_not_hidden():
    """Groundwork the plan does not cover must be visible, or a committee
    would follow a sequence with a silent hole in it."""
    plan = _build(
        [_gap("Kubernetes")],
        prerequisites={"Kubernetes": ["Docker", "Distributed Systems"]},
    )

    entry = plan["stages"][0]["skills"][0]
    assert entry["outside_plan"] == ["Distributed Systems", "Docker"]


def test_prerequisites_covered_by_the_plan_are_distinguished():
    plan = _build(
        [_gap("Kubernetes"), _gap("Docker")],
        prerequisites={"Kubernetes": ["Docker"], "Docker": []},
    )

    kubernetes = [
        entry
        for stage in plan["stages"]
        for entry in stage["skills"]
        if entry["skill"] == "Kubernetes"
    ][0]
    assert kubernetes["covered_by_plan"] == ["Docker"]


def test_stages_respect_the_size_limit():
    """A committee can absorb a few additions per term, not fifteen."""
    plan = _build([_gap(f"Skill {i}") for i in range(10)], stage_size=3)
    assert all(len(stage["skills"]) <= 3 for stage in plan["stages"])


def test_horizon_caps_the_plan():
    plan = _build([_gap(f"Skill {i}") for i in range(30)], horizon=8)
    assert plan["total_skills"] == 8


def test_a_dependency_cycle_does_not_hang():
    """Bad taxonomy data must degrade, not loop forever."""
    plan = _build(
        [_gap("A"), _gap("B")],
        prerequisites={"A": ["B"], "B": ["A"]},
    )

    assert sorted(_order(plan)) == ["A", "B"]


def test_every_gap_reaches_the_plan():
    """No gap may be silently dropped, whatever its dependencies."""
    gaps = [_gap(f"Skill {i}") for i in range(9)]
    plan = _build(
        gaps,
        prerequisites={f"Skill {i}": [f"Skill {i - 1}"] for i in range(1, 9)},
    )

    assert len(_order(plan)) == 9


def test_graph_failure_degrades_to_demand_order():
    """If the graph is unreachable the plan is still useful, just unordered."""
    with patch(
        "app.pipeline.roadmap.fetch_prerequisites", side_effect=RuntimeError("down")
    ):
        plan = build_roadmap("CS101", [_gap("Docker"), _gap("Python")])

    assert len(_order(plan)) == 2
