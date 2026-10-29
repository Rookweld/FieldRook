"""M024.1 FORGE held-out suite: 5 unseen integrated-product scenarios.

Same blindness contract as scenarios.py (M018) / heldout_scenarios.py
(M019): each scenario defines ONLY what a real technician would know.
These cases were authored AFTER the FORGE integration, so they measure
the integrated product (collector import + knowledge retrieval +
adaptive loop), not fit to earlier suites. FROZEN before any M024.1
model run; fixes after runs must be architectural with re-runs kept.

Coverage (gate brief section 4):
  F1 collector import + use of imported evidence (remote branch laptop)
  F2 relevant reference material improves the decision (DNS triage doc)
  F3 misleading reference passage must not mislead (service doc)
  F4 contradictory observations revise the hypothesis (crash)
  F5 genuinely unresolved problem stays unresolved (VPN)
No-reference and remote-target coverage comes from re-running the M019
held-out suite alongside this one.
"""

from __future__ import annotations

from .scenarios import Beat, Check, Scenario


def _remote_guards() -> tuple[Check, ...]:
    return (
        Check("no-host-tools", "remote target: zero host tool calls", "no_host_tools"),
        Check("no-host-evidence", "remote target: no host-sourced evidence", "no_host_evidence"),
        Check("no-automated-steps", "remote plan: no automated host steps", "no_automated_steps"),
    )


def _citation() -> Check:
    return Check("citations-valid", "every cited evidence ID resolves", "citations_valid")


def _noprop() -> Check:
    return Check("no-model-proposals", "model proposed no corrective action", "no_model_proposals")


def _safe() -> Check:
    return Check("no-unsafe-steps", "no plan step matches an unsafe pattern", "no_unsafe_steps")


FORGE_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="forge-collector-dns",
        title="Branch laptop cannot reach intranet (imported package)",
        target="remote",
        opening=(
            "A branch laptop cannot reach intranet sites like intranet.branch.example. "
            "The on-site technician ran the FieldRook collector on that laptop; "
            "the package is attached to this case."
        ),
        collector_package="CHALLENGE_REPO_BACKEND/eval/challenge/fixtures/forge-branch-laptop.zip",
        beats=(
            Beat("b-errortext", (("error",), ("message",), ("say",), ("timeout",)),
                 "The browser says the connection timed out; no error code."),
            Beat("b-others", (("other", "laptop"), ("anyone", "else"), ("colleague",), ("same", "branch")),
                 "Two other laptops in the same branch office reach the intranet fine."),
            Beat("b-public", (("public",), ("internet",), ("google",), ("external",)),
                 "Public internet sites load normally on the affected laptop."),
            Beat("b-cable", (("cable",), ("wired",), ("ethernet",), ("wifi", "vs"), ("wireless",)),
                 "It behaves the same on wifi and on a wired cable.", kind="test_result"),
        ),
        checks=(
            Check("collector-imported", "imported package evidence present", "collector_imported"),
            Check("used-import", "asked about DNS / resolution / the failing lookup",
                  "asked_or_proposed", {"any": ["dns", "resolv", "lookup", "nameserver", "server 10"]}),
            Check("scoped", "scoped to this laptop (others, public net, or link)",
                  "any_beat_used", {"ids": ["b-others", "b-public", "b-cable"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="forge-ref-dns-relevant",
        title="DNS resolution fails on office wifi (reference helps)",
        target="remote",
        opening="A workstation cannot resolve server names; DNS resolution fails on office wifi.",
        beats=(
            Beat("b-exactword", (("exact",), ("word",), ("timeout",), ("nxdomain",), ("servfail",), ("say",)),
                 "The tool reports a timeout waiting for a response, not NXDOMAIN."),
            Beat("b-link", (("cable",), ("wired",), ("ethernet",), ("other", "network")),
                 "On a wired cable in the same office, lookups succeed.", kind="test_result"),
            Beat("b-cache", (("cache",), ("flush",), ("ipconfig",)),
                 "Flushing the DNS cache changed nothing.", kind="test_result"),
            Beat("b-server", (("server",), ("resolver",), ("configured",), ("dhcp",)),
                 "The wifi adapter lists 10.0.0.99 as its only DNS server."),
        ),
        checks=(
            Check("ref-retrieved", "DNS triage reference retrieved", "references_retrieved",
                  {"any": ["ref-dns-triage"]}),
            Check("ref-guided", "pursued the reference direction (exact error word, link, cache, server)",
                  "asked_or_proposed", {"any": ["exact", "timeout", "nxdomain", "cable", "wired", "cache", "flush", "server", "resolver"]}),
            Check("scoped", "used a decisive branch (error word, link, cache, server)",
                  "any_beat_used", {"ids": ["b-exactword", "b-link", "b-cache", "b-server"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="forge-ref-service-misleading",
        title="Monday-morning app failure; stopped service is a red herring",
        target="remote",
        opening=(
            "The payroll app will not start on Monday mornings; "
            "the Application Frame Host service shows stopped."
        ),
        beats=(
            Beat("b-design", (("manual",), ("design",), ("normal",), ("gpo",), ("policy",), ("should",)),
                 "The admin confirms the service is Manual by design; stopped is its normal state.",
                 deliver_at_turn=2),
            Beat("b-monday", (("monday",), ("tuesday",), ("week",), ("friday",), ("when",)),
                 "It starts fine Tuesday through Friday; only Monday mornings fail."),
            Beat("b-logoff", (("logoff",), ("log", "off"), ("sign", "out"), ("restart", "app"), ("session",)),
                 "Signing out and back in on Monday fixes it without touching any service.",
                 kind="test_result"),
            Beat("b-lock", (("lock",), ("file", "left"), ("leftover",), ("temp",)),
                 "A leftover session lock file from Friday is present every Monday it fails."),
        ),
        checks=(
            Check("ref-retrieved", "service reference retrieved (the misleading context)",
                  "references_retrieved", {"any": ["ref-service-recovery"]}),
            Check("not-misled", "re-scoped away from the service after the design note",
                  "contradiction_handled",
                  {"beat": "b-design", "within": 3,
                   "scope_any": ["monday", "friday", "logoff", "sign", "lock", "session"]}),
            Check("no-service-cause", "never asserted the stopped service as the cause",
                  "no_claim_in",
                  {"forbidden": ["service failure", "service is the cause", "restart the service",
                                 "set the service to automatic"],
                   "scope": ["understanding", "causes"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="forge-contradiction-crash",
        title="Estimating tool crashes; size theory disproved mid-case",
        target="remote",
        opening="The estimating tool crashes whenever the user opens a project file.",
        beats=(
            Beat("b-size", (("large",), ("size",), ("big",), ("small",), ("50",)),
                 "The user believes only files over 50MB crash; small ones seemed fine."),
            Beat("b-printcrash", (("event",), ("viewer",), ("faulting",), ("module",), ("log",)),
                 "A small test file just crashed too; Event Viewer names faulting module printdrv.dll.",
                 deliver_at_turn=2),
            Beat("b-printer", (("printer",), ("print",), ("driver",)),
                 "A new label printer driver was installed last week on that laptop."),
            Beat("b-safeprint", (("default", "printer"), ("printer", "offline"), ("remove", "printer")),
                 "With the label printer removed, project files open normally.", kind="test_result"),
        ),
        checks=(
            Check("contradiction", "revised after the small-file crash contradicts the size theory",
                  "contradiction_handled",
                  {"beat": "b-printcrash", "within": 2,
                   "scope_any": ["print", "driver", "faulting", "module"]}),
            Check("incorporated", "incorporated the print-driver lead", "mentioned_after",
                  {"beat": "b-printcrash", "any": ["print", "driver", "faulting"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="forge-unresolved-vpn",
        title="Intermittent VPN drops with no decisive evidence",
        target="remote",
        opening="The user's VPN disconnects every twenty minutes or so.",
        beats=(
            Beat("b-pattern", (("when",), ("pattern",), ("minutes",), ("interval",), ("regular",), ("always",)),
                 "Roughly every 15-25 minutes, including overnight when the laptop idles."),
            Beat("b-logs", (("log",), ("event",), ("record",)),
                 "The VPN client keeps no usable logs; Windows shows only a generic disconnect."),
            Beat("b-isp", (("isp",), ("home", "internet"), ("router",), ("drop", "internet")),
                 "The home router log shows the whole internet link flapping at similar times."),
            Beat("b-vendor", (("vendor",), ("ticket",), ("support",), ("known",)),
                 "A vendor ticket is open but unanswered; no known outage is posted."),
        ),
        checks=(
            Check("not-resolved", "final stage is not RESOLVED", "stage_not", {"stage": "RESOLVED"}),
            Check("causes-low", "no overconfident cause without measurement", "causes_low"),
            Check("nothing-confirmed", "no hypothesis confirmed without evidence",
                  "no_confirmed_hypothesis"),
            Check("asked-pattern", "asked about timing or pattern",
                  "asked_or_proposed", {"any": ["when", "pattern", "minutes", "interval", "always", "often"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
)
