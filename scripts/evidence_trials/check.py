"""Strict publish gate for FieldRook's offline Evidence Trials."""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SITE=ROOT/"docs"/"evidence-trials"
data=json.loads((SITE/"data"/"trials.json").read_text(encoding="utf-8"))
assert data["schema_version"]==1
assert re.fullmatch(r"[0-9a-f]{40}",data["source_commit"])
assert data["gauntlet"]["live_model_cases"]==0
assert data["gauntlet"]["passed"]==data["gauntlet"]["evaluated"]
assert data["gauntlet"]["evaluated"]>=37
assert len(data["cases"])==3
assert {c["case_id"] for c in data["cases"]}=={"task-phantom","resolve-manual-worker","resolve-still-failing"}
for c in data["cases"]:
    assert c["fixture_only"] and c["analysis_mode"]=="simulated", c["case_id"]
    assert c["gauntlet"]["passed"] and c["gauntlet"]["case_id"]==c["case_id"]
    assert c["auto_executions"]==0
    assert c["evidence"],c["case_id"]
    all_ids={e["id"] for e in c["evidence"]}
    assert len(all_ids)==len(c["evidence"])
    for e in c["evidence"]:
        assert e["source"].startswith("tool:") and e["source"].endswith(":fixture")
        assert set(e["data"]).issubset({"summary","warnings","count","total_scanned","tasks","logs","worker_id","status","heartbeat_age_s","process_verified"})
    for fact in c["facts"]:assert set(fact["evidence_ids"]) <= all_ids
    for hypo in c["hypotheses"]:assert set(hypo["evidence_ids"]) <= all_ids
    for entry in c["timeline"]:assert set(entry["evidence_ids"]) <= all_ids
    if c["verification"]:
        v=c["verification"]
        assert v["kind"]=="manual_intervention_claim" and not v["intervention_proven"]
        assert len(v["criteria"])==2 and v["status"]==c["verdict"]
        for item in v["criteria"]:
            assert item["before_evidence_id"] in all_ids
            assert item["after_evidence_id"] in all_ids
            assert item["outcome"] in ("pass","fail")
    else:
        assert c["case_id"]=="task-phantom" and c["verdict"]=="CAUSE NOT VERIFIED"
assert data["cases"][1]["verification"]["status"]=="VERIFIED_RESOLVED"
assert all(x["outcome"]=="pass" for x in data["cases"][1]["verification"]["criteria"])
assert data["cases"][2]["verification"]["status"]=="NOT_RESOLVED"
assert any(x["outcome"]=="fail" for x in data["cases"][2]["verification"]["criteria"])
content=(SITE/"data"/"trials.json").read_text(encoding="utf-8")
for forbidden in ("PRIVATE KEY","OPENAI_API_KEY","MODEL_API_KEY=","Bearer ","gho_","sk-proj-"):
    assert forbidden not in content,forbidden
for file in ("index.html","app.js","style.css","favicon.svg","data/trials.json"):
    assert (SITE/file).is_file(),file
style=(SITE/"style.css").read_text(encoding="utf8")
assert "@import" not in style and "fonts.googleapis" not in style
assert "unsafe-inline" not in (SITE/"index.html").read_text(encoding="utf8")
print("EVIDENCE_TRIALS_CHECK_OK: 3 fixture cases, 37+ baseline checks, provenance/citations, statuses, no external runtime assets")
