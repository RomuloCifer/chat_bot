"""
Rota de webhook para WhatsApp Cloud API.

GET: Verificação do webhook (challenge)
POST: Recebimento de mensagens
"""
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
import os
from app.integrations.channels.whatsapp import (
    verify_webhook_signature,
    extract_message_from_webhook,
    normalize_client_id,
    send_message_via_graph_api,
)
from app.repositories.clients_repo import upsert_client_by_key, get_client_state_and_ctx, set_client_state_and_ctx
from app.services.conversation import handle_message
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook")

# Carrega config do .env
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None,
):
    """
    GET /webhook/whatsapp
    
    Endpoint de verificação do webhook. O WhatsApp envia uma requisição GET
    com hub.mode, hub.challenge e hub.verify_token.
    
    Se o token estiver correto, respondemos com o challenge.
    """
    logger.debug(f"Webhook verification request: mode={hub_mode}, token={hub_verify_token}")
    
    if not hub_mode or not hub_challenge or not hub_verify_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parâmetros faltando (hub.mode, hub.challenge, hub.verify_token)"
        )
    
    if hub_mode != "subscribe":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hub.mode deve ser 'subscribe'"
        )
    
    if hub_verify_token != WHATSAPP_VERIFY_TOKEN:
        logger.warning(f"Token de verificação inválido: {hub_verify_token}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token inválido"
        )
    
    logger.info("Webhook verificado com sucesso")
    return {"hub.challenge": hub_challenge}


@router.post("/whatsapp")
async def receive_message(request: Request):
    """
    POST /webhook/whatsapp
    
    Recebe mensagens do WhatsApp Cloud API.
    
    Body esperado:
    {
      "entry": [{
        "changes": [{
          "value": {
            "messages": [{
              "from": "<phone>",
              "text": { "body": "<msg>" },
              "type": "text"
            }]
          }
        }]
      }]
    }
    """
    try:
        # Lê e valida assinatura
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        
        if not signature:
            logger.warning("X-Hub-Signature-256 ausente")
            # Nota: em produção, rejeitar sem assinatura; por enquanto, permitir para testes
        elif WHATSAPP_VERIFY_TOKEN:
            if not verify_webhook_signature(body.decode(), signature, WHATSAPP_VERIFY_TOKEN):
                logger.warning("Assinatura do webhook inválida")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Assinatura inválida"
                )
        
        # Parseia payload
        payload = await request.json()
        logger.debug(f"Webhook payload: {payload}")
        
        # Extrai mensagem
        result = extract_message_from_webhook(payload)
        if not result:
            logger.info("Nenhuma mensagem de texto encontrada no webhook")
            return {"status": "ok"}  # Retorna OK mesmo sem mensagem
        
        phone, message_text = result
        client_id = normalize_client_id(phone)
        
        logger.info(f"Mensagem recebida de {phone}: {message_text}")
        
        # Garante que cliente existe
        upsert_client_by_key(client_key=client_id)
        
        # Recupera estado e contexto
        state, ctx = get_client_state_and_ctx(client_id)
        if isinstance(ctx, dict) and "client_key" not in ctx:
            ctx["client_key"] = client_id
        
        # Processa mensagem
        reply, next_state, next_ctx, buttons = handle_message(
            current_state=state,
            ctx=ctx,
            message=message_text,
        )
        
        # Persiste novo estado
        set_client_state_and_ctx(client_id, next_state, next_ctx)
        
        logger.info(f"Estado: {state} → {next_state}")
        
        # Envia resposta via WhatsApp
        success = await send_message_via_graph_api(
            phone=phone,
            text=reply,
            buttons=buttons,
            access_token=WHATSAPP_ACCESS_TOKEN,
            phone_id=WHATSAPP_PHONE_ID,
        )
        
        if not success:
            logger.error(f"Falha ao enviar resposta para {phone}")
            # Retorna OK mesmo se falhar (para não retentar o webhook)
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"Erro ao processar webhook: {str(e)}", exc_info=True)
        # Retorna OK para não causar retry
        return {"status": "error", "detail": str(e)}
