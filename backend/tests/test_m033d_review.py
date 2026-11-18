"""M033-D review regression tests: blinding, safety, human provenance."""

import json
from pathlib import Path

import pytest

from eval import m033d_review as review


def _fake_source(root: Path) -> Path:
    for folder, model in (("4b", "qwen3:4b"), ("8b", "qwen3:8b")):
        for version in ("m033c-control", "m033c-heldout"):
            path = root / version / folder
            path.mkdir(parents=True)
            results = []
            for i, case in enumerate(sorted(review.REFERENCES)):
                file = f"grade-{i+1:08x}.md"
                (path / file).write_text(
                    f"# {case}\nTECHNICIAN (opening): Test fault\n"
                    f"  information-gain: Selected primary next move; model question=8/10.\n"
                    f"  Q(open): Can the same test be repeated in the other application?\n"
                    f"--- turn 1 (1.3s) ---\n"
                    f"TECHNICIAN [answer]: It only fails in one application.\n"
                    f"  hyp[active]: Unknown cause\n"
                    f"turns=1 model_calls=2 wall=14s\n"
                    f"[PASS] some structural check\n"
                    f"Running qwen3:4b model\n", encoding="utf-8"
                )
                results.append({"id": case, "ok": True, "grade_file": file})
            (path / f"summary-{folder}.json").write_text(json.dumps({
                "model": model, "suite": "heldout", "results": results,
            }), encoding="utf-8")
    return root


def _grade_everything(out: Path) -> dict:
    path = out / "review" / "scores.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["ratings"].values():
        row.update({
            "discrimination": 2, "fidelity": 3,
            "actionability": 2, "calibration": 2,
            "rationale": "The technician has a clear and safe diagnostic branch.",
        })
    data["status"] = "HUMAN_RATED"
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def test_scrub_hides_grading_model_and_heuristic_but_preserves_questions():
    raw = (
        "# sample\n"
        "  information-gain: Selected alternate; model question=10/10\n"
        "  Q(open): Is Teams failing in a browser or just desktop?\n"
        "--- turn 1 (2.2s) ---\n"
        "  hyp[active]: App integration\n"
        "turns=1 model_calls=3 wall=5s\n"
        "[PASS] test\n"
        "Using qwen3-coder:30b for reasoning\n"
    )
    cleaned = review.scrub(raw)
    assert "information-gain" not in cleaned
    assert "[PASS]" not in cleaned
    assert "model_calls" not in cleaned
    assert "qwen3-coder" not in cleaned
    assert "(2.2s)" not in cleaned
    assert "Q(open)" in cleaned
    assert "hyp[active]" in cleaned


def test_realistic_review_pack_is_blinded_and_pair_matched(tmp_path):
    source = _fake_source(tmp_path / "source")
    out = tmp_path / "work"
    meta = review.prepare(source, out)
    assert meta["pairs"] == 6 and meta["blind_transcripts"] == 12
    packets = json.loads((out / "review" / "packets.json").read_text())
    key = json.loads((out / "private" / "answer_key.json").read_text())
    assert len(packets["pairs"]) == 6
    assert len(key["candidates"]) == 12
    public_files = list((out / "review").iterdir())
    assert not any("key" in p.name for p in public_files)
    content = (out / "review" / "BLIND_REVIEW.md").read_text()
    assert "qwen3:" not in content
    assert "baseline" not in content.lower()
    assert "experiment" not in content.lower()
    assert "information-gain" not in content.lower()
    assert "structural check" in content.lower()
    assert all(len(pair["candidates"]) == 2 for pair in packets["pairs"])
    assert all(len({c["id"] for c in p["candidates"]}) == 2 for p in packets["pairs"])


def test_prepare_refuses_unsafe_overwrite(tmp_path):
    src = _fake_source(tmp_path / "source")
    out = tmp_path / "output"
    review.prepare(src, out)
    with pytest.raises(FileExistsError):
        review.prepare(src, out)


def test_prepare_refuses_unequal_missing_runs(tmp_path):
    src = _fake_source(tmp_path / "source")
    p = src / "m033c-control" / "4b" / "summary-4b.json"
    data = json.loads(p.read_text())
    data["results"][0]["ok"] = False
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Missing or failed"):
        review.prepare(src, tmp_path / "output")


def test_prepare_refuses_model_mismatch(tmp_path):
    src = _fake_source(tmp_path / "source")
    p = src / "m033c-control" / "8b" / "summary-8b.json"
    data = json.loads(p.read_text())
    data["model"] = "qwen3:4b"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="same known model"):
        review.prepare(src, tmp_path / "output")


def test_unrated_reviews_never_unblind_or_write_results(tmp_path):
    review.prepare(_fake_source(tmp_path / "source"), tmp_path / "output")
    with pytest.raises(ValueError, match="Missing human rationale"):
        review.evaluate(tmp_path / "output")
    assert not (tmp_path / "output" / "private" / "HUMAN_RESULTS.json").exists()


def test_partial_review_never_unblinds(tmp_path):
    out = tmp_path / "output"
    review.prepare(_fake_source(tmp_path / "source"), out)
    grades = _grade_everything(out)
    one = next(iter(grades["ratings"]))
    grades["ratings"][one]["discrimination"] = None
    (out / "review" / "scores.json").write_text(json.dumps(grades))
    with pytest.raises(ValueError, match="Missing/out-of-range"):
        review.evaluate(out)
    assert not (out / "private" / "HUMAN_RESULTS.json").exists()


@pytest.mark.parametrize("bad", [True, 4, -1, 1.2, "3"])
def test_grades_are_bounded_int_not_bool(tmp_path, bad):
    out = tmp_path / "output"
    review.prepare(_fake_source(tmp_path / "source"), out)
    data = _grade_everything(out)
    first = next(iter(data["ratings"]))
    data["ratings"][first]["discrimination"] = bad
    (out / "review" / "scores.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Missing/out-of-range"):
        review.evaluate(out)


def test_transcript_tampering_refuses_unblind(tmp_path):
    out = tmp_path / "output"
    review.prepare(_fake_source(tmp_path / "source"), out)
    _grade_everything(out)
    p = out / "review" / "packets.json"
    data = json.loads(p.read_text())
    data["pairs"][0]["candidates"][0]["transcript"] += "\nextra text"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="tampered"):
        review.evaluate(out)


def test_full_human_rating_produces_provenance_report_no_auto_scores(tmp_path):
    out = tmp_path / "output"
    review.prepare(_fake_source(tmp_path / "source"), out)
    _grade_everything(out)
    result = review.evaluate(out)
    assert result["status"] == "HUMAN_RATED"
    assert len(result["means"]) == 4
    assert all(x["n"] == 3 for x in result["means"])
    assert all(x["mean_human_score"] == 9.0 for x in result["means"])
    assert (out / "private" / "HUMAN_RESULTS.json").is_file()
    with pytest.raises(FileExistsError):
        review.evaluate(out)


def test_html_reviewer_is_offline_and_anonymized(tmp_path):
    from eval.m033d_html import render_html
    packet = {
        "schema": "m033d.1",
        "pairs": [{
            "id": "PAIR-01", "case": "dummy",
            "counterfactuals": {
                "probe": "Compare A and B", "outcome_1": "A", "outcome_2": "B",
                "note": "Human grades", },
            "candidates": [{
                "id": "BLIND-abcd", "transcript": (
                    "Q(open): Test <script>alert('XSS')</script> qwen3:8b?"
                ),
            }],
        }],
    }
    # Scrubbing is performed before HTML rendering, so leaked model names in
    # this synthetic direct-input test intentionally remain data, never HTML.
    html = render_html(packet)
    assert "connect-src 'none'" in html
    assert "Export scores.json" in html
    assert "Import scores.json" in html
    assert "BLIND-abcd" in html
    assert "<script>alert" not in html
    assert "\\u003cscript" in html
    assert "innerHTML" not in html
    assert 'eval(' not in html


def test_prepared_html_contains_no_actual_model_or_answer_labels(tmp_path):
    out = tmp_path / "out"
    review.prepare(_fake_source(tmp_path / "source"), out)
    html = (out / "review" / "REVIEW_OFFLINE.html").read_text()
    assert "qwen3:" not in html
    assert "m033c-control" not in html
    assert "m033c-heldout" not in html
    assert "EXPERIMENT VERSION" not in html
    assert "<script id=" in html
    assert "scores.json" in html
