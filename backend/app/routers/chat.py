from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    message: str


@router.post("")
def chat(req: ChatRequest, request: Request):
    return chat_service.handle_message(
        session_id=req.session_id,
        user_message=req.message,
        visitor_ip=request.client.host if request.client else None,
    )
