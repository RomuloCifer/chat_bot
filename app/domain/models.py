from dataclasses import dataclass, asdict, field
from datetime import time
from typing import Optional


@dataclass
class ConversationContext:
    """Estrutura do contexto de conversação do cliente."""
    client_key: Optional[str] = None
    barber_id: Optional[int] = None
    barber_name: Optional[str] = None
    service_id: Optional[int] = None
    service_name: Optional[str] = None
    service_duration_minutes: Optional[int] = None
    date: Optional[str] = None  # ISO format: YYYY-MM-DD
    time_pref: Optional[str] = None  # HH:MM format
    selected_slot: Optional[str] = None  # HH:MM format (horário final escolhido)
    # Operações de cancelamento/remarcação
    operation: Optional[str] = None  # 'cancel' | 'remark'
    cancel_appt_id: Optional[int] = None
    remark_appt_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Converte para dict, removendo None values para JSON limpo."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @staticmethod
    def from_dict(data: dict) -> "ConversationContext":
        """Reconstrói a partir de dict."""
        return ConversationContext(**{k: v for k, v in data.items() if k in ConversationContext.__dataclass_fields__})

    def is_complete_for_booking(self) -> bool:
        """Verifica se contexto tem o mínimo para criar um agendamento."""
        return all([
            self.barber_id,
            self.service_id,
            self.date,
            self.selected_slot,
        ])


@dataclass
class Appointment:
    """Modelo de agendamento."""
    id: Optional[int] = None
    client_id: int = None
    barber_id: int = None
    service_id: int = None
    start_at: str = None  # ISO format: YYYY-MM-DDTHH:MM:SS+HH:MM
    end_at: str = None    # ISO format
    status: str = "scheduled"  # scheduled, completed, cancelled
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
