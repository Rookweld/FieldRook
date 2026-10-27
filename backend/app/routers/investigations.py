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
    InvestigationResponse,
    InvestigationSummary,
    NoteRequest,
    ReverifyRequest,
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


@router.get("/api/tools")
def list_tools() -> list[ToolInfo]:
    return [
        ToolInfo(name=spec.name, description=spec.description, category=spec.category)
        for spec in REGISTRY.values()
    ]


@router.post("/api/investigations", response_model=InvestigationResponse)
async def start_investigation(
    problem: str = Form(min_length=1, max_length=MAX_PROBLEM_CHARS),
    service_name: str | None = Form(default=None),
    use_fixtures: bool | None = Form(default=None),
    share_consent: bool = Form(default=False),
    screenshot: UploadFile | None = File(default=None),
) -> InvestigationResponse:
    settings = load_settings()
    validated_service: str | None = None
    if service_name:
        try:
            validated_service = validate_service_name(service_name)
        except InvalidServiceNameError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    image_b64: str | None = None
    image_mime: str | None = None
    if screenshot is not None:
        if not share_consent:
            raise HTTPException(
                status_code=400,
                detail="A screenshot was attached but sharing consent was not given. "
                "Confirm authorization before the image is sent to the Meta API, or remove it.",
            )
        content = await screenshot.read(MAX_IMAGE_BYTES + 1)
        try:
            image_mime = validate_image_upload(screenshot.filename, screenshot.content_type, content)
        except ImageValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        image_b64 = base64.b64encode(content).decode("ascii")

    state = store.create(problem=problem.strip(), service_name=validated_service, has_image=image_b64 is not None)
    screenshot_evidence_id: str | None = None
    if image_b64 is not None and image_mime is not None:
        shot = state.add_evidence(
            category="screenshot",
            source="upload:screenshot",
            data={
                "filename": screenshot.filename if screenshot else None,
                "mime": image_mime,
                "bytes": len(content),
                "note": "Image bytes sent to the model with consent; FieldRook keeps only this metadata.",
            },
        )
        screenshot_evidence_id = shot.id
        state.add_activity("note", "Screenshot attached", f"Recorded as {shot.id}; image sent to the model with consent, not stored.", evidence_ids=[shot.id])
        state.warnings.append("Screenshot shared with the Meta API with your consent; FieldRook does not store it.")
    state.messages = build_investigation_messages(problem.strip(), validated_service, image_b64, image_mime, screenshot_evidence_id)
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
        state.assessment = fx.build_simulated_investigation_analysis(state.problem, state.evidence)
        state.add_activity(
            "note", "Assessment rebuilt after re-check",
            f"Simulated hypotheses recomputed over {len(state.evidence)} evidence items.",
        )
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
