"""Natural-language investigations: intake, tool-calling loop, follow-ups."""

from __future__ import annotations

import base64

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from fastapi.responses import PlainTextResponse, Response

from ..analysis.loop import (
    MAX_FOLLOWUP_CALLS,
    MAX_TOOL_CALLS,
    build_investigation_messages,
    run_rounds,
)
from ..config import load_settings
from ..diagnostics.service_allowlist import InvalidServiceNameError, validate_service_name
from ..investigations import export as exporters
from ..investigations.store import store
from ..schemas import (
    FollowupRequest,
    InvestigationResponse,
    InvestigationSummary,
    NoteRequest,
    ToolInfo,
)
from ..tools.registry import REGISTRY

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
