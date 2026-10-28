"""M019 held-out challenge: 6 unseen IT support scenarios.

Same contract as scenarios.py (M018): each scenario defines ONLY what a
real technician would know — the opening report, answers to specific
questions, and scripted test outcomes. Hidden grading checks reference
behavior, never fixed question sequences. These cases were authored AFTER
the M019 prompt and pipeline changes, so they measure generalization
rather than fit to the original 20.
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


HELDOUT_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="cad-license-checkout",
        title="CAD app license checkout failure",
        target="remote",
        opening="SolidEdge fails to obtain a license on the engineer's laptop; she needs it for a client review this afternoon.",
        beats=(
            Beat("b-errortext", (("error",), ("message",), ("say",), ("dialog",), ("code",)),
                 "A dialog says 'License checkout failed: cannot connect to license server (error -15,570)'."),
            Beat("b-users", (("other", "user"), ("anyone", "else"), ("colleague",), ("same", "office")),
                 "Two other engineers in the same office get the same error."),
            Beat("b-vpn", (("vpn",), ("wifi",), ("office", "network")),
                 "She is on office wifi, not VPN. Browsing and email work fine."),
            Beat("b-server", (("server",), ("ping",), ("license", "server")),
                 "Pinging license-srv01 times out from her laptop; IT says the server itself is up.", kind="test_result"),
            Beat("b-yesterday", (("yesterday",), ("when",), ("start",), ("before",), ("worked",)),
                 "It worked yesterday morning; nothing on the laptop changed that she knows of."),
        ),
        checks=(
            Check("scoped", "scoped license-vs-app (users, network, or server)", "any_beat_used", {"ids": ["b-users", "b-vpn", "b-server"]}),
            Check("asked-errortext", "asked what the error says", "asked_or_proposed", {"any": ["error", "message", "dialog", "say", "code", "text"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="webcam-teams-calls",
        title="Camera black in Teams calls",
        target="remote",
        opening="The user's laptop camera shows a black screen in Teams calls.",
        beats=(
            Beat("b-otherapp", (("camera", "app"), ("other", "app"), ("zoom",), ("skype",)),
                 "The built-in Camera app shows the same black screen."),
            Beat("b-shutter", (("shutter",), ("cover",), ("privacy",), ("light",), ("led",)),
                 "There is a sliding privacy shutter and it is OPEN; no camera LED lights up."),
            Beat("b-update", (("update",), ("driver",), ("install",), ("change",)),
                 "Windows installed updates two nights ago; the camera worked last week."),
            Beat("b-device", (("device", "manager"), ("detect",), ("list",), ("imaging",)),
                 "Device Manager shows no imaging device at all, not even with an error icon.", kind="test_result"),
        ),
        checks=(
            Check("scoped-crossapp", "checked whether other apps see the camera", "any_beat_used", {"ids": ["b-otherapp"]}),
            Check("asked-physical", "asked about shutter, cover, privacy, or LED", "asked_or_proposed", {"any": ["shutter", "cover", "privacy", "led", "light"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="bsod-after-driver",
        title="Blue screens since a driver update",
        target="remote",
        opening="The user's laptop has blue-screened twice since yesterday.",
        beats=(
            Beat("b-code", (("code",), ("stop",), ("error",), ("screen",)),
                 "The stop code is DRIVER_IRQL_NOT_LESS_OR_EQUAL; no driver file is named."),
            Beat("b-what", (("driver",), ("update",), ("install",), ("change",)),
                 "Windows Update installed a new network adapter driver yesterday morning."),
            Beat("b-safe", (("safe", "mode"),),
                 "It stayed up for three hours in Safe Mode with Networking.", kind="test_result"),
            Beat("b-dump", (("dump",), ("minidump",), ("memory",)),
                 "There is a fresh MEMORY.DMP from this morning, about 900MB.", kind="test_result"),
        ),
        checks=(
            Check("asked-code", "asked for the stop code or screen text", "asked_or_proposed", {"any": ["code", "stop", "screen", "say", "error"]}),
            Check("asked-driver", "asked about drivers, updates, or recent changes", "asked_or_proposed", {"any": ["driver", "update", "install", "change"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="onedrive-sync-conflicts",
        title="OneDrive conflict copies of a shared sheet",
        target="remote",
        opening="OneDrive keeps creating conflict copies of the team's shared budget spreadsheet.",
        beats=(
            Beat("b-users", (("other", "user"), ("same", "time"), ("simultaneous",), ("colleague",), ("together",)),
                 "Three people edit it during month-end; conflicts appear when two save within minutes."),
            Beat("b-client", (("onedrive", "version"), ("client",), ("sync", "error")),
                 "The OneDrive sync client is up to date; it reports no errors."),
            Beat("b-demand", (("files", "demand"), ("on-demand",), ("offline",), ("available",)),
                 "Files On-Demand is on; the file is marked Always Available on her laptop."),
            Beat("b-coauthor", (("browser",), ("online",), ("co-author",), ("web",)),
                 "Editing in Excel for the web shows live co-authoring with no conflicts.", kind="test_result"),
        ),
        checks=(
            Check("scoped-multiuser", "scoped simultaneous editing", "any_beat_used", {"ids": ["b-users"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="monitor-resolution",
        title="New 4K monitor stuck at 1080p",
        target="remote",
        opening="A new 4K monitor on the designer's desk is stuck at 1080p.",
        beats=(
            Beat("b-cable", (("cable",), ("hdmi",), ("displayport",), ("adapter",), ("dock",)),
                 "It is connected through an old HDMI cable via a USB-C dock."),
            Beat("b-direct", (("direct",), ("bypass",), ("laptop", "port")),
                 "Plugged directly into the laptop's HDMI port it still offers 1080p max.", kind="test_result"),
            Beat("b-driver", (("driver",), ("gpu",), ("graphics",)),
                 "The Intel graphics driver is from 2022; Windows Update offers nothing newer."),
            Beat("b-detect", (("detect",), ("identify",), ("pnp",), ("generic",), ("recognize",)),
                 "Windows identifies it as 'Generic PnP Monitor', not by model name."),
        ),
        checks=(
            Check("asked-cable", "asked about cable, port, dock, or adapter", "asked_or_proposed", {"any": ["cable", "hdmi", "displayport", "dock", "adapter", "port"]}),
            Check("asked-driver", "asked about graphics driver", "asked_or_proposed", {"any": ["driver", "gpu", "graphics"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
    Scenario(
        id="shared-mailbox-permission",
        title="Shared mailbox won't open in Outlook",
        target="remote",
        opening="A user cannot open the shared info mailbox in Outlook.",
        beats=(
            Beat("b-owa", (("owa",), ("browser",), ("web",), ("outlook", "web")),
                 "The mailbox opens fine in Outlook on the web.", kind="test_result"),
            Beat("b-error", (("error",), ("message",), ("say",)),
                 "Outlook says 'Cannot expand the folder' with no error code."),
            Beat("b-other", (("other", "mailbox"), ("another", "shared"), ("second", "mailbox")),
                 "A second shared mailbox opens normally in the same Outlook profile."),
            Beat("b-recent", (("recent",), ("added",), ("when",), ("new",), ("granted",)),
                 "Access was granted last Friday; she has restarted Outlook since."),
        ),
        checks=(
            Check("scoped-owa", "compared against Outlook on the web", "any_beat_used", {"ids": ["b-owa"]}),
            Check("asked-error", "asked what the error says", "asked_or_proposed", {"any": ["error", "message", "say", "text"]}),
            *_remote_guards(), _citation(), _noprop(), _safe(),
            Check("questions-capped", "asked at most 8 questions", "questions_capped", {"n": 8}),
        ),
    ),
)
