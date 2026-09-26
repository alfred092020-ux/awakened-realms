from logres_superbrain import assert_evidence, retract_evidence, upsert_capability
from test_superbrain import db


def test_capability_profile_upsert():
    conn = db()
    row = upsert_capability(
        conn,
        member_id="devin-lead",
        capability="architecture-consult",
        provider="devin-mcp",
        model="normal",
        cost_class="paid",
        isolation_level="cloud",
        max_concurrency=1,
        health="HEALTHY",
    )
    assert row["capability"] == "architecture-consult"
    assert row["health"] == "HEALTHY"


def test_evidence_can_be_retracted_and_superseded():
    conn = db()
    first = assert_evidence(
        conn,
        subject="map:001",
        predicate="is_tutorial",
        value=True,
        provenance="inference",
        confidence=0.4,
        assertion_id="ev-first",
    )
    assert first["status"] == "ACTIVE"

    second = assert_evidence(
        conn,
        subject="map:001",
        predicate="is_tutorial",
        value=False,
        provenance="original-apk",
        confidence=0.95,
        supersedes_id="ev-first",
        assertion_id="ev-second",
    )
    assert second["status"] == "ACTIVE"
    old = conn.execute(
        "select status from evidence_assertions where assertion_id='ev-first'"
    ).fetchone()[0]
    assert old == "SUPERSEDED"

    retracted = retract_evidence(conn, "ev-second", reason="later canonical evidence")
    assert retracted["status"] == "RETRACTED"
