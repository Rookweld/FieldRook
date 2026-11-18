"""M033-D: offline blinded technician A/B review of frozen challenge transcripts.

No inference and no automated semantic-quality scores. Keys are kept outside
the reviewer folder; no unblinding until ALL 12 human ratings are submitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REFERENCES = {
    "cad-license-checkout": (
        "Compare second engineer with first or authorized license-server access.",
        "Several users fail: investigate shared license/network infrastructure.",
        "One user fails: investigate client settings or account authorization."),
    "webcam-teams-calls": (
        "Compare Teams video with Windows Camera app; check shutter/privacy.",
        "Both apps fail: inspect device, shutter, privacy, or driver.",
        "Only Teams fails: inspect Teams settings and application permissions."),
    "bsod-after-driver": (
        "Ask for stop code and recent changes; compare safe mode.",
        "Safe mode stable: investigate added driver/service.",
        "Safe mode also fails: investigate broader Windows/hardware faults."),
}
RUBRIC = {
    "discrimination": (3, "0=no useful branch; 1=generic scope; 2=relevant test; 3=alternative outcomes lead to DIFFERENT checks."),
    "fidelity": (3, "0=invents measurements; 1=major assumptions; 2=mostly accurate; 3=clear evidence/assumption boundary."),
    "actionability": (2, "0=unsafe/impossible; 1=partially useful; 2=safe, feasible, precise step."),
    "calibration": (2, "0=unfounded certainty; 1=ambiguous; 2=states uncertainty and does not weaken for no information."),
}
CODE = re.compile(r"^grade-[a-f0-9]{8}\.md$")
LEAK = re.compile(r"(?i)\b(qwen3(?:-coder|-vl)?|llama3(?:\.\d+)?|gemma\d*)(?::[\w.-]+)?\b")
MAX_BYTES = 120_000


def read_json(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Oversized review file")
    parsed = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(parsed, dict):
        raise ValueError("Expected object")
    return parsed


def scrub(text: str) -> str:
    """Remove outcome/score/model/latency disclosure, preserve technician turns."""
    clean = []
    for line in text.splitlines():
        if line.lstrip().startswith(("information-gain:", "turns=", "[PASS]", "[FAIL]")):
            continue
        line = re.sub(r"\s*\([\d.]+s\)(?=\s*-{3}|$)", "", line)
        clean.append(LEAK.sub("[hidden model]", line))
    return "\n".join(clean).strip()


def load(folder: Path, expected_model: str) -> dict[str, str]:
    summaries = list(folder.glob("summary-*.json"))
    if len(summaries) != 1:
        raise ValueError(f"Expected 1 benchmark summary in {folder}")
    summary = read_json(summaries[0])
    if summary.get("model") != expected_model or summary.get("suite") != "heldout":
        raise ValueError("Comparison must use same known model and heldout suite")
    records = {}
    for row in summary.get("results", []):
        if not isinstance(row, dict) or row.get("ok") is not True:
            continue
        name = row.get("grade_file")
        case = row.get("id")
        if case not in REFERENCES or not isinstance(name, str) or not CODE.fullmatch(name):
            continue
        path = folder / name
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Oversized transcript")
        if case in records:
            raise ValueError("Duplicate scenario")
        records[case] = scrub(path.read_text(encoding="utf-8-sig"))
    if set(records) != set(REFERENCES):
        raise ValueError("Missing or failed heldout scenario; cannot create matched pairs")
    return records


def prepare(source: Path, output: Path) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Review already exists: refuse to overwrite.")
    pairs = []
    identities = {}
    for slug, model in (("4b", "qwen3:4b"), ("8b", "qwen3:8b")):
        baseline = load(source / "m033c-control" / slug, model)
        experiment = load(source / "m033c-heldout" / slug, model)
        for case in sorted(REFERENCES):
            pair = "PAIR-%02d" % (len(pairs)+1)
            versions = [("baseline", baseline[case]), ("experiment", experiment[case])]
            if secrets.randbelow(2):
                versions.reverse()
            candidates = []
            for version, transcript in versions:
                code = "BLIND-" + secrets.token_hex(8)
                identities[code] = {
                    "model": model, "version": version, "case": case, "pair": pair,
                    "digest": hashlib.sha256(transcript.encode()).hexdigest(),
                }
                candidates.append({"id": code, "transcript": transcript})
            pairs.append({
                "id": pair, "case": case,
                "counterfactuals": {
                    "probe": REFERENCES[case][0],
                    "outcome_1": REFERENCES[case][1],
                    "outcome_2": REFERENCES[case][2],
                    "note": "Equivalent safe discriminating paths also count; examples are not mandatory.",
                },
                "candidates": candidates,
            })
    output.mkdir(parents=True, exist_ok=True)
    (output/"review").mkdir()
    (output/"private").mkdir()
    packet = {"schema": "m033d.1", "pairs": pairs}
    (output/"review"/"packets.json").write_text(json.dumps(packet, indent=2)+"\n", encoding="utf-8")
    (output/"private"/"answer_key.json").write_text(
        json.dumps({"schema": "m033d.1", "candidates": identities}, indent=2)+"\n",
        encoding="utf-8",
    )
    grades = {
        "schema": "m033d.1", "status": "UNRATED",
        "ratings": {code: {**{field: None for field in RUBRIC}, "rationale": ""}
                    for code in identities},
    }
    (output/"review"/"scores.json").write_text(
        json.dumps(grades, indent=2)+"\n", encoding="utf-8",
    )
    md = [
        "# M033-D — blinded human technician review", "",
        "Compare the two unidentified transcripts in each pair. No model or mode names.",
        "Do not open ../private/answer_key.json until ALL 12 transcripts are graded.",
        "Edit scores.json: provide integer rubric scores AND one factual rationale per item.",
        "Never treat the old automated structural checks as human quality scores.", "",
        "## Rubric", "",
    ]
    for name, (max_score, meaning) in RUBRIC.items():
        md.append("- %s (0-%d): %s" % (name, max_score, meaning))
    for pair in pairs:
        md.extend(["", "## "+pair["id"]+" — "+pair["case"], "",
                   "Possible useful comparison: "+pair["counterfactuals"]["probe"],
                   "Outcome 1: "+pair["counterfactuals"]["outcome_1"],
                   "Outcome 2: "+pair["counterfactuals"]["outcome_2"],
                   "Other valid diagnostic branches may score equally well."])
        for candidate in pair["candidates"]:
            md.extend(["", "### "+candidate["id"], "", "    " +
                candidate["transcript"].replace("\n", "\n    "), ""])
    (output/"review"/"BLIND_REVIEW.md").write_text("\n".join(md)+"\n", encoding="utf-8")
    from .m033d_html import render_html
    (output/"review"/"REVIEW_OFFLINE.html").write_text(
        render_html(packet), encoding="utf-8",
    )
    return {"pairs": len(pairs), "blind_transcripts": len(identities), "review": str(output/"review")}


def evaluate(output: Path) -> dict[str, Any]:
    """Refuse partial/invalid grades: no premature model unblinding."""
    private = output/"private"
    dest = private/"HUMAN_RESULTS.json"
    if dest.exists():
        raise FileExistsError("Human report already exists, refusing overwrite")
    scores = read_json(output/"review"/"scores.json")
    packet = read_json(output/"review"/"packets.json")
    key = read_json(private/"answer_key.json")
    if {scores.get("schema"), packet.get("schema"), key.get("schema")} != {"m033d.1"}:
        raise ValueError("Schema mismatch")
    expected = key["candidates"]
    ratings = scores["ratings"]
    if len(expected) != 12 or set(ratings) != set(expected):
        raise ValueError("Wrong number of ratings: need 12 matched blind transcripts")
    transcripts = {c["id"]: c["transcript"] for p in packet["pairs"] for c in p["candidates"]}
    if set(transcripts) != set(expected):
        raise ValueError("Packet/key ID mismatch")
    scored = defaultdict(list)
    details = []
    for ident, metadata in expected.items():
        raw = transcripts[ident]
        if hashlib.sha256(raw.encode()).hexdigest() != metadata["digest"]:
            raise ValueError("Packet transcript tampered")
        grade = ratings[ident]
        if not isinstance(grade, dict):
            raise ValueError("Missing grade: "+ident)
        rationale = grade.get("rationale")
        if not isinstance(rationale, str) or len(rationale.strip()) < 12:
            raise ValueError("Missing human rationale for "+ident)
        for name, (max_score, _) in RUBRIC.items():
            value = grade.get(name)
            if type(value) is not int or not (0 <= value <= max_score):
                raise ValueError("Missing/out-of-range human rating: "+ident+"."+name)
        total = sum(grade[name] for name in RUBRIC)
        scored[(metadata["model"], metadata["version"])].append(total)
        details.append({
            "case": metadata["case"], "model": metadata["model"],
            "version": metadata["version"], "human_score_out_of_10": total,
            "reason": rationale.strip(),
        })
    means = [
        {"model": model, "version": version, "n": len(values),
         "scores": values, "mean_human_score": round(sum(values)/len(values), 2)}
        for (model, version), values in sorted(scored.items())
    ]
    dest.write_text(
        json.dumps({"schema": "m033d.1", "means": means, "cases": details}, indent=2)+"\n",
        encoding="utf-8",
    )
    return {"status": "HUMAN_RATED", "results": str(dest), "means": means}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M033-D blind A/B technician review")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--source", type=Path, default=Path("eval/results"))
    prep.add_argument("--output", type=Path, default=Path("eval/results/m033d"))
    done = sub.add_parser("evaluate")
    done.add_argument("--output", type=Path, default=Path("eval/results/m033d"))
    args = parser.parse_args(argv)
    try:
        answer = prepare(args.source, args.output) if args.command == "prepare" else evaluate(args.output)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("M033-D %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 2
    print(json.dumps(answer, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
