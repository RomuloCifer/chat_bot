"""
Adaptador para WhatsApp Cloud API.

Responsabilidades:
- Normalizar payloads de entrada do webhook
- Validar assinatura X-Hub-Signature
- Formatar respostas para envio via Graph API
"""
import hmac
import hashlib
import json
from typing import Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


def verify_webhook_signature(body: str, signature: str, verify_token: str) -> bool:
    """
    Valida a assinatura X-Hub-Signature do webhook do WhatsApp.
    
    Args:
        body: Raw request body (string)
        signature: Header X-Hub-Signature (ex: "sha256=abc123...")
        verify_token: Token de verificação (da config)
    
    Returns:
        True se a assinatura é válida
    """
    try:
        hash_method, hash_value = signature.split("=")
        expected_hash = hmac.new(
            verify_token.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        return hash_value == expected_hash
    except Exception as e:
        logger.error(f"Erro ao validar assinatura: {e}")
        return False


def extract_message_from_webhook(payload: dict) -> Optional[tuple[str, str]]:
    """
    Extrai (phone_number, message_text) de um webhook do WhatsApp.
    
    Estrutura esperada:
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
    
    Returns:
        (phone_number, message) ou None se não encontrar mensagem de texto
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        messages = changes.get("value", {}).get("messages", [])
        
        if not messages:
            return None
        
        msg = messages[0]
        if msg.get("type") != "text":
            return None
        
        phone = msg.get("from")
        text = msg.get("text", {}).get("body", "").strip()
        
        if not phone or not text:
            return None
        
        return phone, text
    except Exception as e:
        logger.error(f"Erro ao extrair mensagem do webhook: {e}")
        return None


def normalize_client_id(phone: str) -> str:
    """
    Normaliza um número de telefone WhatsApp para client_id.
    
    Estratégia: `wa:<phone>` (ex: `wa:5511987654321`)
    
    Args:
        phone: Número do WhatsApp (pode vir com ou sem +55)
    
    Returns:
        client_id normalizado
    """
    # Remove caracteres não-numéricos
    clean_phone = "".join(c for c in phone if c.isdigit())
    return f"wa:{clean_phone}"


def build_text_message_response(phone: str, text: str) -> dict:
    """
    Constrói payload para enviar mensagem de texto via Graph API.
    
    Args:
        phone: Número do destinatário (sem +)
        text: Texto da mensagem
    
    Returns:
        Dict pronto para POST em /messages
    """
    return {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }


def build_button_message_response(phone: str, text: str, buttons: list[dict]) -> dict:
    """
    Constrói payload para enviar mensagem com botões via Graph API.
    
    Args:
        phone: Número do destinatário
        text: Corpo da mensagem
        buttons: Lista de {"id": str, "label": str}
    
    Returns:
        Dict pronto para POST em /messages (formato de Interactive Message)
    """
    # Formata botões para WhatsApp (limita a 3 e trunca labels)
    wa_buttons = []
    for btn in buttons[:3]:
        wa_buttons.append({
            "type": "reply",
            "reply": {
                "id": btn.get("id", "")[:256],
                "title": btn.get("label", "")[:20]  # WhatsApp limita a 20 chars
            }
        })
    
    return {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": wa_buttons
            }
        }
    }


async def send_message_via_graph_api(
    phone: str,
    text: str,
    buttons: list[dict],
    access_token: str,
    phone_id: str
) -> bool:
    """
    Envia mensagem via Graph API do WhatsApp (placeholder para integração real).
    
    Args:
        phone: Número do destinatário
        text: Corpo da mensagem
        buttons: Lista de botões (se vazia, envia só texto)
        access_token: Token de acesso
        phone_id: ID do número de telefone business
    
    Returns:
        True se enviado com sucesso
    
    Nota: Implementação real requer requests/httpx para fazer POST real.
    Por enquanto, apenas loga e retorna True (mock).
    """
    try:
        if buttons:
            payload = build_button_message_response(phone, text, buttons)
        else:
            payload = build_text_message_response(phone, text)
        
        logger.info(f"[MOCK] Enviando para {phone}: {payload}")
        # TODO: Implementar POST real em https://graph.instagram.com/v18.0/{phone_id}/messages
        # via requests.post(..., json=payload, headers={"Authorization": f"Bearer {access_token}"})
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        return False
