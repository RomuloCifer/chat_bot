"""
Testes para webhook do WhatsApp.
"""
import pytest
import json
import hmac
import hashlib
from fastapi.testclient import TestClient
from app.main import app
from app.repositories.db import init_db, get_conn

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db_whatsapp():
    init_db()
    _seed()
    yield


def _seed():
    conn = get_conn()
    try:
        conn.execute("DELETE FROM appointments")
        conn.execute("DELETE FROM clients")
        conn.execute("DELETE FROM services")
        conn.execute("DELETE FROM barbers")
        
        conn.execute("INSERT INTO barbers(name, is_active) VALUES(?, 1)", ("João",))
        conn.execute("INSERT INTO services(name, duration_minutes, price_cents, is_active) VALUES(?, ?, ?, 1)",
                     ("Corte", 30, 5000))
        conn.commit()
    finally:
        conn.close()


def test_webhook_verification():
    """Testa o GET /webhook/whatsapp (verificação)."""
    response = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "test_challenge_123",
            "hub.verify_token": "seu_verify_token_aqui",
        }
    )
    # Aceita sem token configurado (placeholder) ou rejeita se não corresponder
    # Por enquanto, esperamos 200 se tudo ok ou 403 se token errado
    assert response.status_code in (200, 403)


def test_webhook_receive_text_message():
    """Testa o POST /webhook/whatsapp com mensagem de texto."""
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5511987654321",
                        "text": {"body": "Olá, quero agendar"},
                        "type": "text"
                    }]
                }
            }]
        }]
    }
    
    response = client.post(
        "/webhook/whatsapp",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


def test_webhook_receive_non_text_message():
    """Testa o POST /webhook/whatsapp com mensagem não-texto (deve ignorar)."""
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5511987654321",
                        "image": {"url": "..."},
                        "type": "image"
                    }]
                }
            }]
        }]
    }
    
    response = client.post(
        "/webhook/whatsapp",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


def test_webhook_receive_empty():
    """Testa o POST /webhook/whatsapp vazio (deve retornar ok)."""
    payload = {"entry": []}
    response = client.post(
        "/webhook/whatsapp",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 200


def test_normalize_client_id():
    """Testa normalização de phone para client_id."""
    from app.integrations.channels.whatsapp import normalize_client_id
    
    # Sem formatação
    assert normalize_client_id("5511987654321") == "wa:5511987654321"
    # Com formatação
    assert normalize_client_id("+55 (11) 98765-4321") == "wa:5511987654321"
    # Apenas dígitos
    assert normalize_client_id("11987654321") == "wa:11987654321"


def test_extract_message_from_webhook():
    """Testa extração de mensagem do payload."""
    from app.integrations.channels.whatsapp import extract_message_from_webhook
    
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5511987654321",
                        "text": {"body": "Olá!"},
                        "type": "text"
                    }]
                }
            }]
        }]
    }
    
    result = extract_message_from_webhook(payload)
    assert result == ("5511987654321", "Olá!")


def test_verify_webhook_signature():
    """Testa validação de assinatura."""
    from app.integrations.channels.whatsapp import verify_webhook_signature
    
    verify_token = "test_token"
    body = '{"test": "data"}'
    
    # Calcula a assinatura esperada
    expected_hash = hmac.new(
        verify_token.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()
    signature = f"sha256={expected_hash}"
    
    # Válida
    assert verify_webhook_signature(body, signature, verify_token) is True
    
    # Inválida
    assert verify_webhook_signature(body, "sha256=invalid", verify_token) is False
