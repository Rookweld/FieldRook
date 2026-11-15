"use strict";

const state = { data: null, caseIndex: 0, view: "evidence", evidenceId: null };
const $ = (id) => document.getElementById(id);
const CASE_LABEL = {
  "task-phantom": "Suspected cause",
  "resolve-manual-worker": "Verified recovery",
  "resolve-still-failing": "Failed verification"
};

function node(tag, cls, value) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (value !== undefined && value !== null) n.textContent = String(value);
  return n;
}
function textLine(tag, cls, value, parent) {
  const element = node(tag, cls, value);
  parent.appendChild(element);
  return element;
}
function button(text, cls, onClick) {
  const n = node("button", cls, text);
  n.type = "button";
  n.addEventListener("click", onClick);
  return n;
}
function fmt(value) {
  if (value === null || value === undefined) return "n/a";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}
function current() {
  return state.data.cases[state.caseIndex];
}
function addHeading(parent, title, subtitle, count) {
  const box = node("div", "view-heading");
  const left = node("div");
  textLine("h4", "", title, left);
  textLine("p", "", subtitle, left);
  box.appendChild(left);
  if (count) textLine("span", "mono-note", count, box);
  parent.appendChild(box);
}
function refs(parent, ids) {
  if (!ids || !ids.length) return;
  const row = node("div", "refs");
  for (const id of ids) {
    const target = current().evidence.find(item => item.id === id);
    if (!target) continue;
    const jump = button(id + " ↗", "ref-button", () => {
      state.evidenceId = id;
      setView("evidence", true);
    });
    jump.setAttribute("aria-label", "Inspect evidence " + id);
    row.appendChild(jump);
  }
  parent.appendChild(row);
}
function buildSidebar() {
  const box = $("case-tabs");
  box.replaceChildren();
  state.data.cases.forEach((item, index) => {
    const n = node("button", "case-choice");
    n.type = "button";
    n.setAttribute("aria-pressed", String(index === state.caseIndex));
    n.setAttribute("aria-label", item.number + ": " + item.title + ", " + item.verdict);
    const head = node("span", "choice-meta");
    textLine("span", "", "TRIAL " + item.number, head);
    textLine("span", "choice-dot " + (item.tone || ""), "", head).setAttribute("aria-hidden", "true");
    n.appendChild(head);
    textLine("strong", "choice-title", item.title, n);
    textLine("small", "choice-sub", CASE_LABEL[item.case_id] || item.verdict, n);
    n.addEventListener("click", () => {
      if (index === state.caseIndex) return;
      state.caseIndex = index;
      state.evidenceId = null;
      state.view = "evidence";
      render();
    });
    box.appendChild(n);
  });
}
function setView(view, focus = false) {
  state.view = view;
  const tabs = Array.from($("detail-tabs").querySelectorAll("[role=tab]"));
  for (const tab of tabs) {
    const chosen = tab.dataset.view === state.view;
    tab.setAttribute("aria-selected", String(chosen));
    tab.tabIndex = chosen ? 0 : -1;
  }
  $("view-content").setAttribute("aria-labelledby", "tab-" + state.view);
  renderView();
  if (focus) {
    $("tab-" + view).focus({ preventScroll: true });
    $("view-content").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}
function render() {
  const c = current();
  buildSidebar();
  $("case-index").textContent = "CASE " + c.number + " // " + c.case_id;
  $("case-mode").textContent = "SIMULATED INFERENCE / OFFLINE FIXTURES";
  $("case-eyebrow").textContent = c.eyebrow;
  $("case-title").textContent = c.title;
  $("case-story").textContent = c.story;
  $("case-question").textContent = c.question;
  const verdict = $("case-verdict");
  verdict.className = "verdict " + c.tone;
  verdict.textContent = c.verdict;
  $("case-source-id").textContent = c.case_id;
  $("case-tool-count").textContent = c.tool_calls_used + " diagnostic tool calls";
  const commit = /^[0-9a-f]{40}$/.test(state.data.source_commit) ? state.data.source_commit : "master";
  $("case-source-link").href =
    "https://github.com/Rookweld/FieldRook/blob/" + commit + "/backend/eval/cases.py";
  setView(state.view);
}
function renderEvidence() {
  const c = current(), host = $("view-content");
  addHeading(host, "Source-backed observations", "Select a record to inspect the actual exported fixture response.", c.evidence.length + " records");
  const split = node("div", "evidence-split");
  const list = node("div", "evidence-list");
  const detail = node("div", "evidence-detail");
  const selected = c.evidence.find(e => e.id === state.evidenceId) || c.evidence[0];
  state.evidenceId = selected.id;
  c.evidence.forEach(e => {
    const b = node("button", "evidence-select");
    b.type = "button";
    b.setAttribute("aria-pressed", String(e.id === selected.id));
    textLine("span", "ev-id", e.id.toUpperCase() + "  /  " + e.category.replace(/_/g, " "), b);
    textLine("strong", "", e.tool_name, b);
    textLine("small", "", e.data.summary || e.source, b);
    b.addEventListener("click", () => {
      state.evidenceId = e.id;
      renderView();
    });
    list.appendChild(b);
  });
  const hd = node("div", "ev-header");
  textLine("strong", "", selected.id.toUpperCase() + " · " + selected.tool_name, hd);
  const cp = button("COPY RECORD", "", async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(selected, null, 2));
      cp.textContent = "COPIED";
    } catch {
      cp.textContent = "SELECT JSON BELOW";
    }
  });
  hd.appendChild(cp);
  detail.appendChild(hd);
  textLine("div", "ev-source", "PROVENANCE: " + selected.source, detail);
  const pre = node("pre");
  pre.tabIndex = 0;
  pre.textContent = JSON.stringify(selected, null, 2);
  detail.appendChild(pre);
  split.append(list, detail);
  host.appendChild(split);
  textLine("p", "muted-text", "Fixture records are intentionally curated to exclude machine identifiers and extraneous data. The selected values come from actual FieldRook tool results.", host);
}
function renderReasoning() {
  const c = current(), host = $("view-content");
  addHeading(host, "Facts vs. hypotheses", "Claims must stay attached to measurements and explicit uncertainty.");
  const list = node("div", "claim-list");
  for (const fact of c.facts) {
    const n = node("article", "claim observed");
    textLine("span", "claim-type", "● OBSERVED / TOOL-BACKED", n);
    textLine("p", "", fact.statement, n);
    refs(n, fact.evidence_ids);
    list.appendChild(n);
  }
  for (const cause of c.hypotheses) {
    const n = node("article", "claim inferred");
    textLine("span", "claim-type", "◇ INFERRED / " + cause.likelihood.toUpperCase() + " LIKELIHOOD", n);
    textLine("h5", "", cause.title, n);
    textLine("p", "", cause.description, n);
    refs(n, cause.evidence_ids);
    list.appendChild(n);
  }
  host.appendChild(list);
  if (c.uncertainties.length) {
    const uncertain = node("section", "uncertainty-box");
    textLine("h5", "", "What FieldRook cannot claim", uncertain);
    const ul = node("ul");
    c.uncertainties.forEach(v => textLine("li", "", v, ul));
    uncertain.appendChild(ul);
    host.appendChild(uncertain);
  }
  if (c.missing_evidence.length) {
    const missing = node("section", "missing-box");
    textLine("h5", "", "Missing evidence / follow-up needed", missing);
    const ul = node("ul");
    c.missing_evidence.forEach(v => textLine("li", "", v, ul));
    missing.appendChild(ul);
    host.appendChild(missing);
  }
}
function renderVerification() {
  const c = current(), host = $("view-content");
  addHeading(host, "Measure the outcome", "A technician-reported intervention is not an independently verified fix.");
  if (!c.verification) {
    const blank = node("div", "not-verified");
    textLine("h4", "", "CAUSE NOT VERIFIED", blank);
    textLine("p", "", "FieldRook found a suspicious task and matching cadence, but the fixture cannot establish that the task caused the visible windows. There was no corrective action, no approval, and no measured fix.", blank);
    textLine("p", "", c.takeaway, blank);
    host.appendChild(blank);
    return;
  }
  const v = c.verification;
  const lead = node("div", "verification-lead");
  textLine("strong", "", "Manual intervention claimed. New evidence required.", lead);
  textLine("p", "", "FieldRook recorded a technician's synthetic claim, captured a separate baseline, and re-ran the fixture measurement. No corrective execution occurred in this trial.", lead);
  host.appendChild(lead);
  const result = node("div", "result-banner " + c.tone);
  textLine("strong", "", v.intended_state, result);
  textLine("span", "result-tag", v.status, result);
  host.appendChild(result);
  const list = node("div", "criteria-list");
  for (const crit of v.criteria) {
    const card = node("section", "criterion");
    const h = node("div", "criterion-head");
    textLine("strong", "", crit.description, h);
    textLine("span", crit.outcome === "pass" ? "passed" : "failed", crit.outcome.toUpperCase(), h);
    card.appendChild(h);
    const measures = node("div", "criterion-values");
    const before = node("div", "measure");
    textLine("span", "", "BEFORE / BASELINE", before);
    textLine("strong", "", fmt(crit.baseline), before);
    const after = node("div", "measure");
    textLine("span", "", "AFTER / NEW READING", after);
    textLine("strong", "", fmt(crit.observed), after);
    measures.append(before, after);
    card.appendChild(measures);
    textLine("p", "", crit.detail, card);
    refs(card, [crit.before_evidence_id, crit.after_evidence_id]);
    list.appendChild(card);
  }
  host.appendChild(list);
  const note = node("div", "uncertainty-box");
  textLine("h5", "", "The verification boundary", note);
  const ul = node("ul");
  (v.uncertainties || []).forEach(s => textLine("li", "", s, ul));
  note.appendChild(ul);
  host.appendChild(note);
}
function renderTimeline() {
  const c = current(), host = $("view-content");
  addHeading(host, "The investigation ledger", "Actual activity entries emitted by the API. No steps have been invented for this page.", c.timeline.length + " events");
  const list = node("div", "timeline-list");
  for (const step of c.timeline) {
    const item = node("div", "timeline-item");
    textLine("span", "timeline-marker", step.seq.toString().padStart(2, "0"), item);
    const cell = node("div", "timeline-content");
    if (step.tool_name) textLine("small", "", step.tool_name.toUpperCase(), cell);
    textLine("strong", "", step.title, cell);
    if (step.detail) textLine("p", "", step.detail, cell);
    refs(cell, step.evidence_ids);
    item.appendChild(cell);
    list.appendChild(item);
  }
  host.appendChild(list);
}
function renderView() {
  const host = $("view-content");
  host.replaceChildren();
  if (state.view === "evidence") renderEvidence();
  else if (state.view === "reasoning") renderReasoning();
  else if (state.view === "verification") renderVerification();
  else renderTimeline();
}
function attachListeners() {
  const tabs = Array.from($("detail-tabs").querySelectorAll("[role=tab]"));
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => setView(tab.dataset.view));
    tab.addEventListener("keydown", event => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const step = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(i + step + tabs.length) % tabs.length];
      setView(next.dataset.view);
      next.focus();
    });
  });
  const cmd = $("copy-command");
  cmd.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText("cd backend && python -m eval.run");
      cmd.textContent = "COPIED";
    } catch {
      cmd.textContent = "COPY MANUALLY";
    }
  });
}
async function bootstrap() {
  attachListeners();
  try {
    const res = await fetch("./data/trials.json");
    if (!res.ok) throw Error("HTTP " + res.status);
    const data = await res.json();
    if (data.schema_version !== 1 || !Array.isArray(data.cases) || data.cases.length !== 3)
      throw Error("Unexpected trial data schema");
    if (!data.cases.every(c => c.fixture_only && c.analysis_mode === "simulated"))
      throw Error("Public trial data must be fixture-only");
    state.data = data;
    $("metric-evaluated").textContent = data.gauntlet.passed + "/" + data.gauntlet.evaluated;
    $("metric-cases").textContent = data.cases.length;
    $("metric-live").textContent = data.gauntlet.live_model_cases;
    $("run-utc").textContent = data.gauntlet.run_utc + " / FIXTURE GAUNTLET";
    $("commit-short").textContent = data.source_commit.substring(0, 8);
    $("workbench").hidden = false;
    render();
  } catch (error) {
    $("load-error").hidden = false;
    $("load-error").textContent = "Could not load the verified evidence file: " + error.message + ". Try reloading or inspect data/trials.json directly.";
  }
}
bootstrap();
