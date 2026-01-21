from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import re

from app.repositories.clients_repo import (
    upsert_client_by_key,
    get_client_state_and_ctx,
    set_client_state_and_ctx,
)
from app.services.conversation import handle_message
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat")


class WebChatIn(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=1000)
    state: str | None = "START"


class Button(BaseModel):
    id: str
    label: str


class WebChatOut(BaseModel):
    reply: str
    state: str
    buttons: list[Button] = []


def _validate_client_id(client_id: str) -> None:
    """
    Valida client_id para evitar SQL injection e valores inválidos.
    Aceita: alphanumerics, hífens, underscores, @
    """
    if not client_id or len(client_id) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id inválido (1-255 caracteres)"
        )
    
    # Permite: letras, números, hífens, underscores, @
    if not re.match(r"^[a-zA-Z0-9\-_@.]+$", client_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id contém caracteres inválidos"
        )


@router.post("/web", response_model=WebChatOut)
def chat_web(payload: WebChatIn):
    """
    Endpoint de chat para web.
    
    Args:
        payload: { client_id, message, state (opcional) }
    
    Returns:
        { reply, state, buttons }
    """
    try:
        # Valida client_id
        _validate_client_id(payload.client_id)
        
        logger.info(f"Chat request from client: {payload.client_id}")
        
        # Garante que o cliente existe no BD
        upsert_client_by_key(client_key=payload.client_id)

        # Recupera estado e contexto do cliente
        state, ctx = get_client_state_and_ctx(payload.client_id)
        
        logger.debug(f"Client state: {state}")

        # Processa mensagem
        reply, next_state, next_ctx, buttons = handle_message(
            current_state=state,
            ctx=ctx,
            message=payload.message,
        )

        # Persiste novo estado
        set_client_state_and_ctx(payload.client_id, next_state, next_ctx)
        
        logger.info(f"State transition: {state} -> {next_state}")

        return WebChatOut(
            reply=reply,
            state=next_state,
            buttons=[Button(**b) for b in buttons],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar chat: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar mensagem"
        )
