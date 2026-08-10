from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..services import chat_service, intelligence

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    message: str


@router.post("")
def chat(req: ChatRequest, request: Request):
    result = chat_service.handle_message(
        session_id=req.session_id,
        user_message=req.message,
        visitor_ip=request.client.host if request.client else None,
    )
    # Premium BIPs can append a machine-readable [EIQ_INTEL] payload to the existing
    # capture_lead notes field. Process it after the normal chat/lead flow completes so
    # existing clients remain unchanged and vertical-specific attributes never pollute
    # the generic leads schema.
    try:
        intelligence.process_latest_lead_for_session(req.session_id)
    except Exception:
        # Intelligence enrichment must never break the visitor-facing chat path.
        pass
    return result
