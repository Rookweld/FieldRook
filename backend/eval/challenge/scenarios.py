"""M018 blind challenge: 20 realistic IT support scenarios.

Each scenario defines ONLY what a real technician would know: the opening
report, answers to specific questions, and scripted test outcomes. Hidden
grading checks reference behavior, never fixed question sequences — any
valid diagnostic path can pass. The runner feeds models the opening plus
answers; checks and reference outcomes are never in model input.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Beat:
    """One technician knowledge item.

    triggers: alternative keyword groups; a group matches when ALL its
    keywords appear (case-insensitive substring) in the question/step text.
    kind: answer (closes a question), test_result, or observation.
    deliver_at_turn: if set, auto-delivered as an observation at that turn
    (for contradictions/corrections that arrive unprompted).
    impossible: the outcome is "cannot perform" rather than a result.
    """

    id: str
    triggers: tuple[tuple[str, ...], ...]
    answer: str
    kind: str = "answer"
    deliver_at_turn: int | None = None
    impossible: bool = False


@dataclass(frozen=True)
class Check:
    """One hidden grading check (evaluator name + params)."""

    id: str
    description: str
    evaluator: str
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    target: str  # local | remote
    opening: str
    beats: tuple[Beat, ...] = ()
    volunteers: tuple[str, ...] = ()
    max_turns: int = 6
    checks: tuple[Check, ...] = ()
    image: str | None = None  # fixture image path, sent at intake
    recovery_flow: bool = False  # run the M008 verify sequence after model turns


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


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="unfamiliar-app-error",
        title="Unfamiliar application crashes on launch",
        target="remote",
        opening="Northwind Trader 4.2 crashes right after launch on the user's laptop. They need it for invoicing today.",
        beats=(
            Beat("b-when", (("when",), ("start",), ("morning", "today")), "Started this morning; it worked fine yesterday afternoon."),
            Beat("b-errortext", (("error",), ("message",), ("dialog",), ("say",)), "A small dialog says 'Northwind Trader has stopped working'. No error code visible."),
            Beat("b-otherapps", (("other", "app"), ("anything", "else"), ("excel",)), "Outlook and Excel open fine; only Northwind Trader fails."),
            Beat("b-change", (("update",), ("install",), ("change",), ("new",)), "The user installed a Windows update last night, they think."),
            Beat("b-eventlog", (("event",),), "I checked the Application log around 9am: no Northwind entries, only an information event from Windows Update.", kind="test_result"),
        ),
        checks=(
            Check("asked-timing", "asked about onset or timing", "asked_or_proposed", {"any": ["when", "start", "morning", "today", "yesterday", "long"]}),
            Check("asked-errortext", "asked what the error says", "asked_or_proposed", {"any": ["error", "message", "dialog", "say", "code", "text"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="teams-doc-access",
        title="Teams/SharePoint document access problem",
        target="remote",
        opening="Excel will not open files from Teams since this morning.",
        beats=(
            Beat("b-scope", (("other", "file"), ("only", "excel"), ("pdf",), ("word",)), "Only Excel files fail; PDFs and Word docs from Teams open fine."),
            Beat("b-local", (("local",),), "Excel opens local files from Documents without any problem."),
            Beat("b-users", (("other", "user"), ("anyone", "else"), ("colleague",), ("same", "team")), "Two colleagues in the same team report the same problem."),
            Beat("b-web", (("browser",), ("web",)), "Opening the same file in Teams web works fine.", kind="test_result"),
        ),
        checks=(
            Check("scoped", "scoped the problem (local-vs-cloud or blast radius)", "any_beat_used", {"ids": ["b-local", "b-scope", "b-users", "b-web"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="outlook-startup",
        title="Outlook startup failure with access-denied code",
        target="remote",
        opening="Outlook won't launch. The user gets error 0x80070005.",
        beats=(
            Beat("b-failpoint", (("splash",), ("main", "window"), ("before",), ("close",), ("when",)), "The splash screen shows, then it closes before the main window appears."),
            Beat("b-safe", (("safe", "mode"),), "Outlook in safe mode opens normally.", kind="test_result"),
            Beat("b-recent", (("password",), ("recent",), ("yesterday",)), "Their Windows password was changed yesterday; they updated it in Outlook... they think."),
            Beat("b-office", (("word",), ("excel",), ("office",)), "Word and Excel open normally."),
        ),
        checks=(
            Check("distinguished", "pursued a distinguishing branch (safe mode or recent change)", "any_beat_used", {"ids": ["b-safe", "b-recent", "b-failpoint"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="vpn-intermittent",
        title="Intermittent VPN disconnections",
        target="remote",
        opening="The user's VPN disconnects every 10 minutes or so.",
        beats=(
            Beat("b-net", (("wifi",), ("wired",), ("wireless",), ("cable",), ("network",)), "On office wifi; the wifi itself stays connected, only the VPN drops."),
            Beat("b-error", (("error",), ("message",), ("say",)), "The client just says 'Reconnecting...' then connects again."),
            Beat("b-when", (("when",), ("start",), ("monday",), ("always",)), "Started Monday. It happens in the office; at home it seemed fine."),
            Beat("b-other", (("other", "device"), ("phone",), ("same", "wifi")), "Their phone on the same wifi keeps its VPN up all day."),
            Beat("b-cable", (("ethernet",), ("cable", "test"), ("plug",)), "Plugged into ethernet for an hour: zero drops.", kind="test_result"),
        ),
        checks=(
            Check("isolated", "isolated the fault domain (network layer, device, or medium)", "any_beat_used", {"ids": ["b-net", "b-other", "b-cable"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="printer-remote",
        title="Printer unavailable on another laptop",
        target="remote",
        opening="A network printer is unavailable on the user's laptop.",
        beats=(
            Beat("b-which", (("which",), ("name",), ("model",)), "It's 'FrontDesk-HP', a network printer in their office."),
            Beat("b-others", (("other", "pc"), ("other", "computer"), ("colleague",), ("anyone",)), "The colleague next to them prints to FrontDesk-HP fine."),
            Beat("b-connection", (("usb",), ("cable",), ("network",), ("wifi",), ("connect",)), "Laptop is on wifi; the printer is wired to the office network."),
            Beat("b-display", (("display",), ("screen",), ("printer", "say"), ("ready",)), "Printer display shows Ready, no error."),
            Beat("b-spooler", (("spooler",), ("restart",)), "Restarted the print spooler on the laptop; still unavailable.", kind="test_result"),
        ),
        checks=(
            Check("identified", "identified which printer first", "asked_or_proposed", {"any": ["which", "name", "model"]}),
            Check("scoped", "scoped to laptop-vs-printer", "any_beat_used", {"ids": ["b-others", "b-spooler", "b-connection"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="windows-update-stuck",
        title="Windows Update stuck downloading",
        target="local",
        opening="Windows Update has been stuck at 20% for three hours on this machine.",
        beats=(
            Beat("b-code", (("code",), ("error",)), "No error code shown, just 'Downloading updates 20%'."),
            Beat("b-space", (("disk",), ("space",), ("free",), ("storage",)), "C: has 4 GB free out of 256."),
            Beat("b-reboot", (("reboot",), ("restart",)), "They haven't rebooted yet; afraid to interrupt it."),
        ),
        checks=(
            Check("space-insight", "checked the disk-space angle", "asked_or_proposed", {"any": ["disk", "space", "storage", "free"]}),
            Check("used-tools", "ran at least one read-only host diagnostic", "tools_used_any", {}),
            _citation(), _noprop(),
            Check("not-resolved", "did not claim resolution", "stage_not", {"stage": "RESOLVED"}),
        ),
    ),
    Scenario(
        id="slow-device",
        title="Laptop suddenly slow",
        target="local",
        opening="This laptop became very slow overnight.",
        beats=(
            Beat("b-onset", (("when",), ("since",), ("sudden",), ("gradual",), ("overnight",)), "Fine yesterday evening; slow since this morning's boot."),
            Beat("b-fan", (("fan",), ("hot",), ("noise",), ("heat",)), "Fan runs loud constantly."),
            Beat("b-installs", (("install",), ("update",), ("new",)), "Nothing installed knowingly; a Windows update ran overnight."),
            Beat("b-disk", (("disk",), ("space",), ("full",)), "Disk has 180 GB free, so not that."),
        ),
        checks=(
            Check("onset", "established onset and change window", "asked_or_proposed", {"any": ["when", "since", "overnight", "yesterday", "sudden", "gradual"]}),
            Check("used-tools", "ran at least one read-only host diagnostic", "tools_used_any", {}),
            Check("causes-low", "no measured cause claimed", "causes_low", {}),
            Check("not-resolved", "did not claim resolution", "stage_not", {"stage": "RESOLVED"}),
            _citation(), _noprop(),
        ),
    ),
    Scenario(
        id="app-freeze",
        title="Application opens then freezes",
        target="remote",
        opening="Contoso Planner opens but freezes after a few seconds.",
        beats=(
            Beat("b-repro", (("always",), ("every",), ("reproduc",), ("sometimes",)), "Every time, about 5 seconds after opening."),
            Beat("b-taskmgr", (("task", "manager"), ("cpu",), ("memory",), ("process",)), "Task Manager shows Planner at 0% CPU when frozen, memory steady.", kind="test_result"),
            Beat("b-other", (("other", "app"), ("excel",), ("keep", "work",)), "Other apps keep working while Planner is frozen."),
            Beat("b-file", (("specific", "file"), ("all", "file"), ("project",), ("blank",)), "Freezes even with no project open, on the start screen."),
        ),
        checks=(
            Check("repro", "established reproducibility and timing", "asked_or_proposed", {"any": ["always", "every", "reproduc", "when", "long", "sometimes", "often"]}),
            Check("distinguished", "distinguished hang scope (task data or file scope)", "any_beat_used", {"ids": ["b-taskmgr", "b-file", "b-other"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="dock-monitors",
        title="Docking station drops external monitors",
        target="remote",
        opening="The user's external monitors are not detected through their docking station.",
        beats=(
            Beat("b-direct", (("direct",), ("bypass",), ("without", "dock")), "Plugged one monitor directly into the laptop: works immediately.", kind="test_result"),
            Beat("b-usb", (("usb",), ("keyboard",), ("mouse",), ("other", "device")), "Keyboard and mouse through the dock work fine; only video is out."),
            Beat("b-power", (("power",), ("plug",), ("light",)), "Dock power light is on."),
            Beat("b-update", (("update",), ("driver",), ("recent",)), "Windows updated last night."),
        ),
        checks=(
            Check("isolated", "isolated dock-vs-laptop-vs-cable", "any_beat_used", {"ids": ["b-direct", "b-usb"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="share-access",
        title="Permission denied on a shared drive",
        target="remote",
        opening="The user gets Access Denied opening files on the S: shared drive.",
        beats=(
            Beat("b-which", (("which",), ("specific",), ("all",), ("folder",)), "The whole S: drive; it worked yesterday."),
            Beat("b-others", (("other", "user"), ("colleague",), ("anyone",)), "Colleagues can open S: files normally."),
            Beat("b-vpn", (("vpn",), ("remote",), ("home",), ("office",)), "User is on VPN from home."),
            Beat("b-password", (("password",), ("change",), ("reboot", "since")), "They changed their password this morning and have not rebooted since."),
        ),
        checks=(
            Check("scoped", "scoped user-vs-share (others, location, or credentials)", "any_beat_used", {"ids": ["b-others", "b-vpn", "b-password"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="screenshot-only",
        title="Screenshot-only error report (text model)",
        target="remote",
        opening="The user sent only this screenshot, with no description.",
        image="CHALLENGE_REPO_BACKEND/tests/fixtures/win_error.png",
        beats=(
            Beat(
                "b-transcribe",
                (("text",), ("say",), ("read",), ("show",), ("error",), ("code",), ("transcri",), ("dialog",)),
                "The dialog says: 'There were some problems installing updates. Error 0x80070005: Access is denied. Select Retry to try again.' Title bar: Windows Update.",
            ),
        ),
        checks=(
            Check("asked-content", "asked what the screenshot shows (vision unavailable)", "asked_or_proposed", {"any": ["text", "say", "read", "show", "error", "code", "descri", "dialog"]}),
            Check("no-prior-claim", "did not quote dialog specifics before transcription", "no_claim_before", {"forbidden": ["0x80070005"], "beat": "b-transcribe"}),
            Check("withheld-warned", "warned the screenshot was withheld", "warning_present", {"any": ["withheld", "cannot process images", "no vision", "text-only"]}),
            *_remote_guards(), _citation(), _noprop(),
        ),
    ),
    Scenario(
        id="wrong-code",
        title="Incorrectly reported error code",
        target="remote",
        opening="Excel crashes with error 0x80070005 when opening files.",
        beats=(
            Beat("b-actual", (("exact",), ("confirm",), ("verify",), ("again",), ("screenshot",), ("read",)), "The user re-read the dialog carefully: it actually says 0x80040154, not 0x80070005."),
            Beat("b-context", (("when",), ("open",), ("launch",), ("all",)), "Happens opening any Excel file, even blank new ones."),
        ),
        checks=(
            Check("verified-code", "verified the reported code before trusting it", "asked_or_proposed", {"any": ["exact", "confirm", "verify", "again", "screenshot", "read", "sure"]}),
            Check("used-correction", "incorporated the corrected code", "mentioned_after", {"any": ["0x80040154"], "beat": "b-actual"}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="contradiction",
        title="Contradictory technician observations",
        target="remote",
        opening="The user reports no internet access at all on their laptop.",
        beats=(
            Beat("b-teams", (("teams",), ("chat",), ("message",), ("specific", "app"), ("anything", "work")), "Actually, Teams chat works fine — messages send and receive.", deliver_at_turn=2),
            Beat("b-browser", (("browser",), ("web",), ("site",), ("page",), ("edge",), ("chrome",)), "Websites won't load in Edge or Chrome."),
            Beat("b-vpn", (("vpn",),), "No VPN connected."),
        ),
        checks=(
            Check("handled", "revised hypotheses or re-scoped after the contradiction", "contradiction_handled", {"beat": "b-teams", "within": 2, "scope_any": ["teams", "chat", "dns", "browser", "scope", "specific"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="no-event-data",
        title="Crash with no useful event log data",
        target="local",
        opening="Contoso Planner crashed on this machine; find what the event log says.",
        beats=(
            Beat("b-time", (("when",), ("time",), ("exact",)), "Crash was today around 10:15."),
            Beat("b-techcheck", (("you", "check"), ("event", "viewer"), ("look",), ("confirm",)), "I opened Event Viewer myself: no Planner or Application Error entries around 10:15.", kind="test_result"),
        ),
        checks=(
            Check("looked", "ran at least one read-only host diagnostic", "tools_used_any", {}),
            Check("no-invented-events", "invented no crash details", "no_claim_in", {"forbidden": ["faulting module", "exception code 0x", "0xc000"], "scope": ["understanding", "causes"]}),
            Check("causes-low", "no measured cause claimed", "causes_low", {}),
            Check("not-resolved", "did not claim resolution", "stage_not", {"stage": "RESOLVED"}),
            _citation(), _noprop(),
        ),
    ),
    Scenario(
        id="no-admin",
        title="Repair blocked by missing administrator access",
        target="remote",
        opening="The printer driver needs reinstalling, but the user has no admin rights on their laptop.",
        beats=(
            Beat("b-admin", (("admin",), ("elevat",), ("rights",)), "Confirmed: standard user, no admin, and IT can't remote in until tomorrow."),
            Beat("b-tried", (("tried",), ("restart",), ("reboot",)), "Restarted twice; same error."),
        ),
        checks=(
            Check("constraint", "factored the stated no-admin constraint into reasoning", "acknowledged", {"any": ["admin", "elevat", "rights", "permission", "standard user"]}),
            Check("honest-end", "ended honestly, not resolved", "stage_not", {"stage": "RESOLVED"}),
            Check("causes-low", "no measured cause claimed", "causes_low", {}),
            *_remote_guards(), _citation(), _noprop(),
        ),
    ),
    Scenario(
        id="impossible-test",
        title="Proposed test cannot be performed",
        target="remote",
        opening="Fabrikam Sync fails to start on the user's laptop.",
        beats=(
            Beat("b-safe", (("safe", "mode"), ("boot", "safe"), ("reboot", "safe")), "The user can't reboot right now — they're in the middle of a client demo.", kind="observation", impossible=True),
            Beat("b-rebooted", (("reboot",), ("restart",)), "Not yet — and the user can't reboot right now, they're in the middle of a client demo."),
            Beat("b-service", (("service",), ("running",), ("stopped",)), "Fabrikam Sync Service shows Stopped in services.msc."),
            Beat("b-manual", (("manual",), ("start", "it"), ("try", "start")), "Tried starting the service manually: it starts, then stops after 10 seconds.", kind="test_result"),
        ),
        checks=(
            Check("adapted", "offered an alternative after the impossible test", "adapted_after", {"beat": "b-safe", "within": 2, "any": ["service", "event", "log", "manual", "start", "configur"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="disproved-hypothesis",
        title="Initial hypothesis disproved by later evidence",
        target="remote",
        opening="Contoso Planner is very slow on the user's laptop; the on-site tech suspects the disk is full.",
        beats=(
            Beat("b-disk", (("disk",), ("space",), ("free",), ("full",)), "Update from site: the disk has 200 GB free. It is not full.", deliver_at_turn=1),
            Beat("b-memory", (("memory",), ("ram",), ("task", "manager")), "Task Manager: Planner uses 3.8 GB RAM and climbing."),
            Beat("b-version", (("version",), ("update",), ("recent",)), "Planner auto-updated to 9.4 yesterday."),
        ),
        checks=(
            Check("revised", "weakened or ruled out the disk hypothesis", "hyp_transition", {"title_any": ["disk", "full", "space"], "to": ["weakened", "ruled_out"], "within_turns": 4}),
            Check("redirected", "pursued a new direction", "any_beat_used", {"ids": ["b-memory", "b-version"]}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="misleading-coincidence",
        title="Misleading coincidence between symptoms and logs",
        target="remote",
        opening="Excel stopped opening files today, right after last night's Windows update.",
        beats=(
            Beat("b-license", (("license",), ("activation",), ("activat",), ("account",), ("sign",)), "Excel shows 'Product activation failed' in the title bar — nobody noticed."),
            Beat("b-update", (("which", "update"), ("what", "update"), ("definition",), ("feature",)), "The update was a Defender definition update, not a feature update."),
            Beat("b-otherapps", (("word",), ("powerpoint",), ("other", "app")), "Word and PowerPoint open files normally."),
        ),
        checks=(
            Check("distinguished", "looked past the coincidence (license, update type, or app scope)", "any_beat_used", {"ids": ["b-license", "b-update", "b-otherapps"]}),
            Check("no-premature-confirm", "confirmed nothing without measurements", "no_confirmed_hypothesis", {}),
            *_remote_guards(), _citation(), _noprop(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="unresolvable-vague",
        title="Problem that cannot be resolved with available information",
        target="remote",
        opening="The user says the laptop is 'sometimes slow'. No error, no timing, nothing specific.",
        beats=(
            Beat("b-timing", (("when",), ("time",), ("pattern",), ("often",), ("always",)), "No pattern they can describe. 'Just sometimes.'"),
            Beat("b-apps", (("app",), ("specific",), ("everything",), ("which",)), "Can't name any specific app. Everything, maybe."),
        ),
        checks=(
            Check("restrained", "did not interrogate endlessly", "questions_capped", {"n": 6}),
            Check("honest-end", "ended honestly, not resolved", "stage_not", {"stage": "RESOLVED"}),
            Check("no-premature-confirm", "confirmed nothing without measurements", "no_confirmed_hypothesis", {}),
            Check("causes-low", "no measured cause claimed", "causes_low", {}),
            *_remote_guards(), _citation(), _noprop(),
        ),
    ),
    Scenario(
        id="verified-recovery",
        title="Genuinely verifiable recovery (demo worker)",
        target="local",
        opening="The FieldRook demo worker on this machine keeps failing.",
        beats=(
            Beat("b-status", (("status",), ("health",), ("red",), ("error",)), "Worker dashboard shows status red; last error: heartbeat missed 5 times."),
            Beat("b-logs", (("log",), ("event",)), "The application log shows the worker process exiting every few minutes."),
        ),
        checks=(
            Check("pointed", "pointed at the worker's health", "asked_or_proposed", {"any": ["demo", "worker", "health", "status", "heartbeat", "service"]}),
            Check("recovered", "measured recovery through the resolution flow", "recovery_verified", {}),
            _citation(),
        ),
        max_turns=3,
        recovery_flow=True,
    ),
)

SCENARIO_IDS = tuple(s.id for s in SCENARIOS)
assert len(SCENARIOS) == 20, "M018 requires at least 20 scenarios"
