"""Natural-language investigations: intake, tool-calling loop, follow-ups."""

from __future__ import annotations

import base64

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from fastapi.responses import PlainTextResponse, Response

from ..analysis.loop import (
    MAX_FOLLOWUP_CALLS,
    MAX_TOOL_CALLS,
    affected_cause_titles,
    build_investigation_messages,
    HOST_MEASUREMENT_TOOLS,
    reference_excerpts_for,
    run_rounds,
)
from ..analysis.refresh import compare_readings
from ..config import load_settings
from ..diagnostics import fixtures as fx
from ..diagnostics.service_allowlist import InvalidServiceNameError, validate_service_name
from ..investigations import export as exporters
from ..investigations.store import store
from ..schemas import (
    FollowupRequest,
    HypothesisStatusRequest,
    InvestigationResponse,
    InvestigationSummary,
    NoteRequest,
    PlanStepImpossibleRequest,
    PlanStepOutcomeRequest,
    ProviderInfo,
    ProviderSwitchRequest,
    ReverifyRequest,
    TargetRequest,
    ToolInfo,
)
from ..tools.registry import (
    REGISTRY,
    ToolCallError,
    ToolContext,
    execute_prepared,
    prepare_call,
)

router = APIRouter(tags=["investigations"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PROBLEM_CHARS = 4000

# Extension + MIME + magic bytes must all agree.
ALLOWED_IMAGES: tuple[tuple[str, tuple[str, ...], bytes], ...] = (
    ("image/png", (".png",), b"\x89PNG\r\n\x1a\n"),
    ("image/jpeg", (".jpg", ".jpeg"), b"\xff\xd8\xff"),
)


class ImageValidationError(ValueError):
    pass


def validate_image_upload(
    filename: str | None, content_type: str | None, content: bytes
) -> str:
    """Return the verified MIME type or raise ImageValidationError."""
    if len(content) > MAX_IMAGE_BYTES:
        raise ImageValidationError(
            f"Screenshot exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)}MB size limit."
        )
    if not content:
        raise ImageValidationError("Screenshot is empty.")
    lowered_name = (filename or "").lower()
    lowered_type = (content_type or "").lower().split(";")[0].strip()
    for mime, extensions, magic in ALLOWED_IMAGES:
        if lowered_type == mime and lowered_name.endswith(extensions) and content.startswith(magic):
            return mime
    raise ImageValidationError(
        "Screenshot must be a PNG or JPEG file (extension, media type, and file signature must agree)."
    )


def _processing_location(settings: object, override: str | None) -> str:
    """Human-readable processing location for consent wording (never fails)."""
    try:
        from ..analysis.provider import select_provider

        provider, _ = select_provider(settings, override)  # type: ignore[arg-type]
        location = provider.capabilities().processing_location
    except Exception:  # noqa: BLE001 - consent wording must not fail
        return "provider unresolved"
    if location == "cloud":
        return "in the Meta cloud"
    if location == "local":
        return "on this computer by the local model"
    return "nowhere (withheld; simulated analysis cannot view images)"


@router.get("/api/tools")
def list_tools() -> list[ToolInfo]:
    from ..toolpacks.families import family_for_tool

    return [
        ToolInfo(
            name=spec.name,
            description=spec.description,
            category=spec.category,
            family=family_for_tool(spec.name),
        )
        for spec in REGISTRY.values()
    ]


@router.post("/api/investigations", response_model=InvestigationResponse)
async def start_investigation(
    problem: str = Form(min_length=1, max_length=MAX_PROBLEM_CHARS),
    service_name: str | None = Form(default=None),
    use_fixtures: bool | None = Form(default=None),
    share_consent: bool = Form(default=False),
    screenshot: UploadFile | None = File(default=None),
    target: str = Form(default="local"),
    provider: str = Form(default="auto"),
) -> InvestigationResponse:
    settings = load_settings()
    validated_service: str | None = None
    if service_name:
        try:
            validated_service = validate_service_name(service_name)
        except InvalidServiceNameError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    normalized_target = (target or "local").strip().lower()
    if normalized_target not in ("local", "remote", "unknown"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown diagnostic target {target!r}; use local, remote, or unknown.",
        )
    normalized_provider = (provider or "auto").strip().lower()
    if normalized_provider not in ("auto", "meta", "simulated", "local"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider {provider!r}; use auto, meta, simulated, or local.",
        )

    image_b64: str | None = None
    image_mime: str | None = None
    if screenshot is not None:
        if not share_consent:
            raise HTTPException(
                status_code=400,
                detail="A screenshot was attached but sharing consent was not given. "
                "Confirm authorization before the image is processed, or remove it.",
            )
        content = await screenshot.read(MAX_IMAGE_BYTES + 1)
        try:
            image_mime = validate_image_upload(screenshot.filename, screenshot.content_type, content)
        except ImageValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        image_b64 = base64.b64encode(content).decode("ascii")

    state = store.create(problem=problem.strip(), service_name=validated_service, has_image=image_b64 is not None)
    state.target = normalized_target
    state.provider_override = None if normalized_provider == "auto" else normalized_provider
    screenshot_evidence_id: str | None = None
    if image_b64 is not None and image_mime is not None:
        location = _processing_location(settings, state.provider_override)
        shot = state.add_evidence(
            category="screenshot",
            source="upload:screenshot",
            data={
                "filename": screenshot.filename if screenshot else None,
                "mime": image_mime,
                "bytes": len(content),
                "note": f"Image bytes sent for processing ({location}) with consent; FieldRook keeps only this metadata.",
            },
        )
        screenshot_evidence_id = shot.id
        state.add_activity("note", "Screenshot attached", f"Recorded as {shot.id}; processed {location} with consent, not stored.", evidence_ids=[shot.id])
        state.warnings.append(f"Screenshot shared with your consent ({location}); FieldRook does not store it.")
    # M022: initial turn carries fresh reference excerpts (quoted context).
    state.messages = build_investigation_messages(
        problem.strip(), validated_service, image_b64, image_mime,
        screenshot_evidence_id, normalized_target,
        evidence=[shot] if screenshot_evidence_id else None,
        knowledge_excerpts=reference_excerpts_for(problem.strip(), validated_service) or None,
    )
    await run_rounds(state, settings, use_fixtures)
    uses_fixtures = settings.fixtures_mode == "always" or use_fixtures is True or state.mode == "simulated"
    store.save(state)
    return state.to_response(uses_fixtures=uses_fixtures)


@router.get("/api/investigations", response_model=list[InvestigationSummary])
def list_investigations() -> list[InvestigationSummary]:
    return store.list_recent()


@router.get("/api/investigations/{investigation_id}", response_model=InvestigationResponse)
def get_investigation(investigation_id: str) -> InvestigationResponse:
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    settings = load_settings()
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    return state.to_response(uses_fixtures=uses_fixtures)


@router.post("/api/investigations/{investigation_id}/followup", response_model=InvestigationResponse)
async def followup_investigation(
    investigation_id: str, request: FollowupRequest
) -> InvestigationResponse:
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    settings = load_settings()
    message = request.message.strip()
    remaining = MAX_TOOL_CALLS - state.tool_calls_made
    grant = max(0, min(MAX_FOLLOWUP_CALLS, remaining))
    state.messages.append({"role": "user", "content": f"Technician follow-up: {message}"})
    state.add_activity("note", "Follow-up received", message[:500])
    if grant <= 0:
        state.warnings.append("Tool budget exhausted; follow-up answered from existing evidence only.")
    await run_rounds(state, settings, None, max_new_calls=grant, is_followup=True)
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    store.save(state)
    return state.to_response(uses_fixtures=uses_fixtures)


@router.post("/api/investigations/{investigation_id}/notes", response_model=InvestigationResponse)
async def add_investigation_note(investigation_id: str, request: NoteRequest) -> InvestigationResponse:
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    settings = load_settings()
    note = state.add_note(request.text)
    state.add_activity("note", "Technician note added", note.text[:500])
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    store.save(state)
    return state.to_response(uses_fixtures=uses_fixtures)


@router.post("/api/investigations/{investigation_id}/reverify", response_model=InvestigationResponse)
async def reverify_evidence(
    investigation_id: str, request: ReverifyRequest
) -> InvestigationResponse:
    """Re-run the exact read-only tool call behind one evidence item.

    The historical item is preserved untouched; the fresh reading becomes a
    new item linked via `refresh_of`, plus a comparison record with a
    `changed` / `unchanged` / `unavailable` verdict. Hypotheses that cited
    the old item are named as affected so the technician can review them.
    """
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    settings = load_settings()
    old = next((item for item in state.evidence if item.id == request.evidence_id), None)
    if old is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown evidence {request.evidence_id!r} in investigation {investigation_id!r}.",
        )
    if not old.tool_name or old.tool_args is None or old.tool_name not in REGISTRY:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Evidence {old.id} ({old.category}) has no re-runnable tool provenance "
                "(screenshots and legacy items cannot be re-collected)."
            ),
        )
    # M024.1: target isolation at the authorization boundary. Imported
    # collector evidence describes another computer: re-running its tool
    # refs on this host would silently substitute wrong-computer data.
    if (old.source or "").startswith("collector:"):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Evidence {old.id} was imported from a collector package and cannot be "
                "re-measured from this host. Import a fresh package from the affected "
                "computer to compare readings."
            ),
        )
    # Non-local cases must never trigger host measurements — including
    # historical local readings after the target changed. Static
    # computations outside HOST_MEASUREMENT_TOOLS stay available.
    if (state.target or "local") != "local" and old.tool_name in HOST_MEASUREMENT_TOOLS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Case target is {state.target!r}; host tool '{old.tool_name}' cannot be "
                "re-run for another computer. Collect on the affected machine instead."
            ),
        )
    if state.tool_calls_made >= MAX_TOOL_CALLS:
        raise HTTPException(
            status_code=409,
            detail=f"Tool budget exhausted ({MAX_TOOL_CALLS} calls per investigation); cannot re-verify.",
        )
    try:
        spec, args = prepare_call(old.tool_name, dict(old.tool_args))
    except ToolCallError as exc:
        raise HTTPException(status_code=422, detail=f"Stored tool call is no longer valid: {exc}") from exc

    state.add_activity(
        "tool_request",
        f"Reverify requested: {spec.name} (was {old.id})",
        "Re-running the identical read-only tool call; historical evidence is preserved.",
        tool_name=spec.name,
    )
    rerun_fixtures = True if state.mode == "simulated" else None
    output, duration_ms = await execute_prepared(
        spec, args, ToolContext(settings=settings, use_fixtures=rerun_fixtures)
    )
    state.tool_calls_made += 1
    item = state.add_evidence(
        category=spec.category,
        source=f"tool:{spec.name}:{output.source}",
        data={"summary": output.summary, "warnings": output.warnings, **output.data}
        if output.error is None
        else {"summary": output.summary, "warnings": output.warnings},
        error=output.error,
        tool_name=spec.name,
        tool_args=args.model_dump(mode="json"),
        refresh_of=old.id,
    )
    verdict, changes = compare_readings(
        old, None if output.error is not None else item.data, output.error
    )
    affected = affected_cause_titles(state, old.id)
    state.add_refresh(
        old_evidence_id=old.id,
        new_evidence_id=item.id,
        tool_name=spec.name,
        verdict=verdict,
        changes=changes,
        old_collected_at=old.collected_at,
        new_collected_at=item.collected_at,
        affected_causes=affected,
    )
    state.add_activity(
        "reverify",
        f"Re-check of {old.id} is {verdict.upper()} ({item.id})",
        "; ".join(changes[:3]) if changes else "Fresh reading matches the historical item.",
        tool_name=spec.name,
        duration_ms=duration_ms,
        evidence_ids=[old.id, item.id],
    )
    if state.mode == "simulated":
        state.assessment = fx.build_simulated_investigation_analysis(
            state.problem, state.evidence, state.target
        )
        state.add_activity(
            "note", "Assessment rebuilt after re-check",
            f"Simulated hypotheses recomputed over {len(state.evidence)} evidence items.",
        )
    if state.assessment is not None:
        from ..analysis.assist import refresh_assist

        try:
            refresh_assist(state, state.rounds_used)
        except Exception as exc:  # noqa: BLE001 - assist must never sink a re-check
            state.warnings.append(f"Assistance layer skipped after re-check ({exc}).")
    if verdict == "changed":
        state.warnings.append(
            f"Re-check {item.id} differs from historical {old.id} ({spec.name}). "
            + (
                f"Hypotheses built on {old.id} may need review: {', '.join(affected)}."
                if affected
                else f"No recorded hypothesis cited {old.id}."
            )
        )
    elif verdict == "unavailable":
        state.warnings.append(
            f"Re-check of {old.id} ({spec.name}) failed to collect; historical reading kept."
        )
    if any(p.status == "APPROVED" and not p.approval_used for p in state.proposals):
        state.warnings.append(
            "New evidence was collected after an approval was granted; that approval "
            "will require re-review before execution."
        )
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    store.save(state)
    return state.to_response(uses_fixtures=uses_fixtures)


@router.get("/api/providers")
def list_providers() -> list[dict]:
    """Available inference providers with capabilities (no network probing)."""
    from ..analysis.provider import (
        LocalEndpointProvider,
        MetaModelProvider,
        SimulatedProvider,
    )

    settings = load_settings()
    entries: list[dict] = []
    meta = MetaModelProvider(settings)
    meta_caps = meta.capabilities()
    meta_available = bool(settings.model_api_key) and not settings.offline_mode
    entries.append(
        {
            "name": "meta",
            "model": settings.model_name,
            "processing_location": meta_caps.processing_location,
            "vision": meta_caps.vision,
            "tool_calling": meta_caps.tool_calling,
            "available": meta_available,
            "reason": (
                "ready"
                if meta_available
                else (
                    "FIELDROOK_OFFLINE is enabled"
                    if settings.offline_mode
                    else "MODEL_API_KEY is not set"
                )
            ),
        }
    )
    simulated = SimulatedProvider(settings)
    sim_caps = simulated.capabilities()
    entries.append(
        {
            "name": "simulated",
            "model": simulated.model_label(),
            "processing_location": sim_caps.processing_location,
            "vision": sim_caps.vision,
            "tool_calling": sim_caps.tool_calling,
            "available": True,
            "reason": "ready (deterministic offline analysis)",
        }
    )
    from ..analysis.local_profiles import describe_profile, resolve_profile

    local = LocalEndpointProvider(settings)
    local_caps = local.capabilities()
    local_available = bool(settings.local_model_url.strip()) and bool(
        settings.local_model_name.strip()
    )
    entries.append(
        {
            "name": "local",
            "model": settings.local_model_name or "unconfigured",
            "processing_location": local_caps.processing_location,
            "vision": local_caps.vision,
            "tool_calling": local_caps.tool_calling,
            "available": local_available,
            "reason": (
                f"endpoint {settings.local_model_url}"
                if local_available
                else "FIELDROOK_LOCAL_MODEL_URL / FIELDROOK_LOCAL_MODEL_NAME not set"
            ),
            "profile": describe_profile(resolve_profile(settings.local_model_name)),
            "api_style": local.api_style() if local_available else "unresolved",
        }
    )
    return entries


TURN_LABELS = {
    "answer": "Technician answer",
    "observation": "Technician observation",
    "test_result": "Technician test result",
    "correction": "Technician correction",
    "question": "Technician question",
    "unable": "Technician unable",
}


@router.post("/api/investigations/{investigation_id}/turn", response_model=InvestigationResponse)
async def technician_turn(
    investigation_id: str,
    kind: str = Form(default="observation"),
    text: str = Form(min_length=1, max_length=2000),
    question_id: str | None = Form(default=None),
    share_consent: bool = Form(default=False),
    screenshot: UploadFile | None = File(default=None),
) -> InvestigationResponse:
    """One technician conversation turn: answer, observation, test result,
    correction, question, or unable, optionally with a follow-up screenshot.

    Technician-supplied content becomes labeled evidence
    (source `technician:<kind>`) that hypotheses and plans can cite, but it
    is never confused with independently measured facts. Answering a
    clarifying question closes it so it is never asked again; marking it
    unable records that the technician cannot answer it.
    """
    from ..knowledge.redact import redact_text

    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    settings = load_settings()
    normalized_kind = (kind or "observation").strip().lower()
    if normalized_kind not in TURN_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown turn kind {kind!r}; use answer, observation, test_result, correction, question, or unable.",
        )
    cleaned = redact_text(text.strip())
    if not cleaned:
        raise HTTPException(status_code=400, detail="Turn text is empty after redaction.")

    question = None
    if question_id:
        question = next((q for q in state.questions if q.question_id == question_id), None)
        if question is None:
            raise HTTPException(status_code=422, detail=f"Unknown question {question_id!r}.")
        if question.status != "open":
            raise HTTPException(status_code=409, detail=f"Question {question_id!r} is already {question.status}.")

    image_b64: str | None = None
    image_mime: str | None = None
    if screenshot is not None:
        if not share_consent:
            raise HTTPException(
                status_code=400,
                detail="A screenshot was attached but sharing consent was not given. "
                "Confirm authorization before the image is processed, or remove it.",
            )
        content = await screenshot.read(MAX_IMAGE_BYTES + 1)
        try:
            image_mime = validate_image_upload(screenshot.filename, screenshot.content_type, content)
        except ImageValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        image_b64 = base64.b64encode(content).decode("ascii")

    label = TURN_LABELS[normalized_kind]
    state.messages.append({"role": "user", "content": f"{label}: {cleaned}"})
    if image_b64 is not None and image_mime is not None:
        location = _processing_location(settings, state.provider_override)
        state.messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{label} includes a follow-up screenshot ({location})."},
                    {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}},
                ],
            }
        )
        state.has_image = True
        shot = state.add_evidence(
            category="screenshot",
            source="upload:screenshot",
            data={
                "filename": screenshot.filename if screenshot else None,
                "mime": image_mime,
                "bytes": len(content),
                "note": f"Follow-up image sent for processing ({location}) with consent; FieldRook keeps only this metadata.",
            },
        )
        state.add_activity(
            "note", "Follow-up screenshot attached",
            f"Recorded as {shot.id}; processed {location} with consent, not stored.",
            evidence_ids=[shot.id],
        )
        state.warnings.append(f"Follow-up screenshot shared with your consent ({location}); FieldRook does not store it.")

    evidence_ids: list[str] = []
    if normalized_kind in ("observation", "test_result"):
        item = state.add_evidence(
            category="technician_report",
            source=f"technician:{normalized_kind}",
            data={
                "kind": normalized_kind,
                "text": cleaned,
                "question_id": question_id,
                "note": "Technician-supplied; cited as reported, not independently measured.",
            },
        )
        evidence_ids.append(item.id)
    from ..analysis.assist import note_technician_answer

    note_technician_answer(state, cleaned)
    remaining = MAX_TOOL_CALLS - state.tool_calls_made
    grant = max(0, min(MAX_FOLLOWUP_CALLS, remaining))
    if grant <= 0:
        state.warnings.append("Tool budget exhausted; turn answered from existing evidence only.")
    await run_rounds(state, settings, None, max_new_calls=grant, is_followup=True)
    if question is not None:
        if normalized_kind == "unable":
            question.status = "blocked"
            question.answer = cleaned[:1000]
            state.add_activity(
                "question", f"Question {question.question_id} blocked", cleaned[:300],
                evidence_ids=evidence_ids,
            )
        else:
            question.status = "answered"
            question.answer = cleaned[:1000]
            state.add_activity(
                "question", f"Question {question.question_id} answered", cleaned[:300],
                evidence_ids=evidence_ids,
            )
    state.add_activity("turn", f"{label} processed", cleaned[:500], evidence_ids=evidence_ids)
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    store.save(state)
    return state.to_response(uses_fixtures=uses_fixtures)


@router.post(
    "/api/investigations/{investigation_id}/plan/steps/{step_id}/complete",
    response_model=InvestigationResponse,
)
async def complete_plan_step(
    investigation_id: str, step_id: str, request: PlanStepOutcomeRequest
) -> InvestigationResponse:
    """Record a technician-reported step outcome and advance the plan."""
    from ..analysis.assist import refresh_assist
    from ..knowledge.redact import redact_text

    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    if state.plan is None:
        raise HTTPException(status_code=404, detail="This investigation has no troubleshooting plan yet.")
    step = next((s for s in state.plan.steps if s.step_id == step_id), None)
    if step is None:
        raise HTTPException(status_code=404, detail=f"Unknown plan step {step_id!r}.")
    if step.status in ("done", "blocked", "skipped"):
        raise HTTPException(status_code=409, detail=f"Step {step_id!r} is already {step.status}.")
    step.status = "done"
    step.outcome = redact_text(request.outcome.strip())[:2000]
    state.add_activity(
        "troubleshoot_plan", f"Step {step_id} completed", step.outcome[:500],
        evidence_ids=list(step.evidence_ids),
    )
    refresh_assist(state, state.rounds_used)
    store.save(state)
    settings = load_settings()
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    return state.to_response(uses_fixtures=uses_fixtures)


@router.post(
    "/api/investigations/{investigation_id}/plan/steps/{step_id}/impossible",
    response_model=InvestigationResponse,
)
async def impossible_plan_step(
    investigation_id: str, step_id: str, request: PlanStepImpossibleRequest
) -> InvestigationResponse:
    """Mark a step impossible; replan around it or record why blocked."""
    from ..analysis.assist import refresh_assist
    from ..knowledge.redact import redact_text

    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    if state.plan is None:
        raise HTTPException(status_code=404, detail="This investigation has no troubleshooting plan yet.")
    step = next((s for s in state.plan.steps if s.step_id == step_id), None)
    if step is None:
        raise HTTPException(status_code=404, detail=f"Unknown plan step {step_id!r}.")
    if step.status in ("done", "blocked", "skipped"):
        raise HTTPException(status_code=409, detail=f"Step {step_id!r} is already {step.status}.")
    reason = redact_text(request.reason.strip())[:2000]
    step.status = "blocked"
    step.outcome = reason
    state.add_activity(
        "troubleshoot_plan", f"Step {step_id} impossible", reason[:500],
        evidence_ids=list(step.evidence_ids),
    )
    refresh_assist(state, state.rounds_used)
    open_steps = (
        [s for s in state.plan.steps if s.status in ("suggested", "current")]
        if state.plan is not None
        else []
    )
    if not open_steps:
        state.blocked_reason = (
            f"Step {step_id} cannot be performed ({reason}) and no alternative "
            "step is available from current evidence."
        )
        state.warnings.append(f"Investigation blocked: {state.blocked_reason}")
        state.add_activity("note", "Investigation blocked", state.blocked_reason)
    store.save(state)
    settings = load_settings()
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    return state.to_response(uses_fixtures=uses_fixtures)


@router.post(
    "/api/investigations/{investigation_id}/hypotheses/{hypothesis_id}/status",
    response_model=InvestigationResponse,
)
async def set_hypothesis_status(
    investigation_id: str, hypothesis_id: str, request: HypothesisStatusRequest
) -> InvestigationResponse:
    """Record an explicit technician judgment on one hypothesis.

    The judgment and its reason enter the hypothesis history and are never
    overridden by later model reassessments.
    """
    from ..analysis.assist import mark_hypothesis
    from ..knowledge.redact import redact_text

    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    reason = f"Technician judgment: {redact_text(request.reason.strip())}"[:1000]
    if not mark_hypothesis(state, hypothesis_id, request.status, reason, state.rounds_used):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown hypothesis {hypothesis_id!r} (or invalid status).",
        )
    hyp = next(h for h in state.hypotheses if h.hypothesis_id == hypothesis_id)
    state.add_activity(
        "hypothesis", f"Hypothesis {hypothesis_id} {request.status}",
        f"{hyp.title}: {reason}"[:500],
        evidence_ids=list(hyp.supporting_evidence_ids),
    )
    store.save(state)
    settings = load_settings()
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    return state.to_response(uses_fixtures=uses_fixtures)


@router.post("/api/investigations/{investigation_id}/provider", response_model=InvestigationResponse)
async def switch_provider(
    investigation_id: str, request: ProviderSwitchRequest
) -> InvestigationResponse:
    """Switch the inference provider for future rounds (evidence preserved).

    Switching TO a cloud provider while the investigation holds screenshots,
    evidence, or notes requires explicit `confirm_cloud`: that content would
    be transmitted on the next model round.
    """
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    settings = load_settings()
    wanted = request.provider
    if wanted == "meta":
        sensitive = bool(state.has_image or state.evidence or state.notes)
        if sensitive and not request.confirm_cloud:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Switching to the Meta cloud provider would transmit this "
                    "investigation's screenshots, evidence, and notes. Resend with "
                    "confirm_cloud=true to authorize that transmission."
                ),
            )
    state.provider_override = None if wanted == "auto" else wanted
    location = _processing_location(settings, state.provider_override)
    state.warnings.append(
        f"Inference provider switched to {wanted} ({location}); applies to the "
        "next round. Past assessments keep their original labels."
    )
    state.add_activity("provider", f"Provider switched to {wanted}", location)
    store.save(state)
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    return state.to_response(uses_fixtures=uses_fixtures)


@router.post("/api/investigations/{investigation_id}/cancel", response_model=InvestigationResponse)
async def cancel_round(investigation_id: str) -> InvestigationResponse:
    """Request cancellation of a running round (honored mid-flight).

    The in-flight model call is interrupted — streaming providers abort
    within a chunk; others stop waiting — then the round stops. Collected
    evidence is kept and the investigation stays resumable.
    """
    from ..investigations import persistence as persist

    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    persist.request_cancel(investigation_id, state.rounds_used)
    state.warnings.append("Cancellation requested; the current model call is interrupted, then the round stops.")
    settings = load_settings()
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    return state.to_response(uses_fixtures=uses_fixtures)


@router.post("/api/providers/local/test")
async def test_local_provider() -> dict:
    """User-triggered local connection test: one tiny capped completion.

    Reports reachability, API style, resolved profile, server-advertised
    capabilities, and measured latency. Never triggered automatically.
    """
    import time as _time

    from ..analysis.local_profiles import describe_profile, resolve_profile, vision_mismatch
    from ..analysis.provider import LocalEndpointProvider, cached_server_caps, validate_local_model_url
    from ..analysis.validate import ModelAnalysisError

    settings = load_settings()
    model = settings.local_model_name.strip()
    profile = resolve_profile(model)
    try:
        base = validate_local_model_url(settings.local_model_url)
    except ModelAnalysisError as exc:
        return {
            "ok": False, "error": str(exc), "model": model,
            "profile": describe_profile(profile), "server_caps": [],
        }
    if not model:
        return {
            "ok": False, "error": "FIELDROOK_LOCAL_MODEL_NAME is not set.",
            "model": model, "profile": describe_profile(profile), "server_caps": [],
        }
    provider = LocalEndpointProvider(settings)
    style = provider.api_style()
    server_caps = cached_server_caps(settings.local_model_url, model)
    started = _time.monotonic()
    try:
        if style == "ollama":
            reply = await provider._ollama_chat(
                base, model,
                [{"role": "user", "content": "Reply with exactly: OK"}],
                False, 16, 30.0,
            )
        else:
            from ..analysis.provider import _chat_completions

            reply = await _chat_completions(
                base + "/chat/completions", model,
                [{"role": "user", "content": "Reply with exactly: OK"}],
                None, False, 30.0, None, "Local model",
            )
        latency_s = round(_time.monotonic() - started, 1)
        text = str(reply.get("content") or "")
        return {
            "ok": True, "model": model, "api_style": style,
            "latency_s": latency_s, "reply": text[:120],
            "reply_ok": "OK" in text.upper(),
            "profile": describe_profile(profile), "server_caps": server_caps,
            "vision_warning": vision_mismatch(settings.local_model_vision, profile, server_caps),
            "stats": dict(provider.last_stats),
        }
    except ModelAnalysisError as exc:
        return {
            "ok": False, "error": str(exc)[:300], "model": model,
            "api_style": style, "latency_s": round(_time.monotonic() - started, 1),
            "profile": describe_profile(profile), "server_caps": server_caps,
        }


@router.post("/api/investigations/{investigation_id}/target", response_model=InvestigationResponse)
async def set_target(investigation_id: str, request: TargetRequest) -> InvestigationResponse:
    """Set the diagnostic target (which computer the evidence describes)."""
    from ..analysis.assist import refresh_assist

    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    if state.target == request.target:
        settings = load_settings()
        uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
        return state.to_response(uses_fixtures=uses_fixtures)
    previous = state.target
    state.target = request.target
    host_measured = [
        item.id for item in state.evidence
        if (item.source or "").startswith("tool:") and (item.tool_name or "") != "interpret_error_code"
    ]
    if previous == "local" and request.target != "local" and host_measured:
        state.warnings.append(
            "Diagnostic target changed to "
            f"{request.target}: existing host evidence ({', '.join(host_measured[:5])}"
            f"{', …' if len(host_measured) > 5 else ''}) may describe the wrong "
            "computer. Treat it as host-only until confirmed."
        )
    state.add_activity(
        "note", f"Diagnostic target: {previous} -> {request.target}",
        "Host measurements apply only when the target is the local host.",
    )
    refresh_assist(state, state.rounds_used)
    store.save(state)
    settings = load_settings()
    uses_fixtures = settings.fixtures_mode == "always" or state.mode == "simulated"
    return state.to_response(uses_fixtures=uses_fixtures)


@router.get("/api/investigations/{investigation_id}/export")
def export_investigation(investigation_id: str, format: str = "markdown") -> Response:
    state = store.get(investigation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown investigation {investigation_id!r}.")
    kind = (format or "").strip().lower()
    if kind == "json":
        return Response(
            content=exporters.build_json(state),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{investigation_id}.json"'},
        )
    if kind in ("markdown", "md"):
        return PlainTextResponse(
            content=exporters.build_markdown(state),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{investigation_id}.md"'},
        )
    raise HTTPException(status_code=400, detail="format must be 'markdown' or 'json'.")
