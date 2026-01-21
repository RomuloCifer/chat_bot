from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.repositories.clients_repo import (
    upsert_client_by_key,
    get_client_state_and_ctx,
    set_client_state_and_ctx,
)
from app.services.conversation import handle_message

router = APIRouter(prefix="/chat")

class WebChatIn(BaseModel):
    client_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    state: str | None = "START"

class Button(BaseModel):
    id: str
    label: str

class WebChatOut(BaseModel):
    reply: str
    state: str
    buttons: list[Button] = []

@router.post("/web", response_model=WebChatOut)

def chat_web(payload: WebChatIn):
    upsert_client_by_key(client_key=payload.client_id)

    state, ctx = get_client_state_and_ctx(payload.client_id)

    reply, next_state, next_ctx, buttons = handle_message(
        current_state=state,
        ctx=ctx,
        message=payload.message,
    )

    set_client_state_and_ctx(payload.client_id, next_state, next_ctx)

    return WebChatOut(
        reply=reply,
        state=next_state,
        buttons=[Button(**b) for b in buttons],
    )