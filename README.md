# 🤖 Chatbot para Barbearia

Um assistente conversacional para agendamento de horários em barbearias. Desenvolvido com **Python**, **FastAPI** e **SQLite**, com máquina de estados robusta e arquitetura preparada para **WhatsApp Cloud API** e **interpretação por IA (LLM)**.

## 🎯 Objetivo

Permitir que clientes marquem, remarquem ou cancelem horários de forma rápida e natural, conversando com o bot como se fosse uma pessoa — evitando dependência de palavras-chave fixas no futuro.

Exemplos de uso esperado:

- "Queria cortar o cabelo amanhã à tarde"
- "Tem horário com o barbeiro 2 na sexta?"

## Características

- ✅ **Agendamento de horários** - Interface conversacional intuitiva
- ✅ **Disponibilidade em tempo real** - Calcula slots livres considerando barbeiros, serviços e horário de almoço
- ✅ **Máquina de estados** - Fluxo conversacional estruturado e previsível
- ✅ **Múltiplos canais** - Web chat (pronto), WhatsApp (estrutura)
- ✅ **Persistência de estado** - Continua conversas de onde pararam
- ✅ **Validação de conflitos** - Impede duplo-agendamento
- ✅ **Logging estruturado** - Rastreabilidade completa
- ✅ **Testes automatizados** - Cobertura do fluxo principal

---

## 🧠 Interpretação de Mensagens (MVP e Futuro)

Hoje (MVP)
- Regras simples de intenção (detecção direta)
- Fluxo guiado e previsível (máquina de estados)
- Estados explícitos: `START`, `WAIT_BARBER`, `WAIT_SERVICE`, `WAIT_DATE`, `WAIT_TIME_PREF`, `WAIT_SLOT_PICK`, `WAIT_CONFIRMATION`, `CONFIRMED`

Futuro (planejado)
- Interpretação por IA (LLM): linguagem natural livre, frases incompletas ou fora de ordem, múltiplas intenções na mesma frase
- Extração automática de intenção (agendar, cancelar, remarcar, perguntar) e entidades (data, horário, barbeiro, serviço)
- Fallback automático para atendente humano quando necessário

Importante: a IA entrará apenas como substituta do módulo de NLU, mantendo a mesma interface com o orquestrador e regras de negócio. O restante do sistema não quebra.

---

## 🏗️ Arquitetura

```
app/
├── api/                 # Rotas FastAPI
│   ├── routes/
│   │   ├── chat.py     # Endpoint de chat web
│   │   └── health.py   # Health check
│   └── deps.py         # Dependências
├── domain/             # Modelos de dados
│   ├── models.py       # ConversationContext, Appointment
│   └── enums.py        # Estados (State)
├── repositories/       # Acesso a dados
│   ├── db.py           # Conexão e schema SQLite
│   ├── clients_repo.py # Clientes
│   ├── appointments_repo.py # Agendamentos
│   ├── barbers_repo.py # Barbeiros
│   └── services_repo.py # Serviços
├── services/           # Lógica de negócio
│   ├── conversation.py # Máquina de estados
│   ├── availability.py # Cálculo de slots livres
│   ├── nlu.py          # Detecção de intent
│   └── parsers.py      # Parse de data/hora em português
├── integrations/       # Canais de entrada/saída
│   ├── channels/
│   │   ├── web_chat.py  # Adaptador web (MVP)
│   │   └── whatsapp.py  # Estrutura para WhatsApp Cloud API
├── core/               # Configuração global
│   ├── config.py       # Horários de funcionamento
│   ├── logging.py      # Logger estruturado
│   └── timezone.py     # Timezone utilities
└── tests/              # Testes automatizados
    └── test_conversation_happy_path.py
```

---

## 🔄 Fluxo de Conversação

A máquina de estados segue este fluxo:

```
START
├─ (GREETING) → START
├─ (BOOK_APPOINTMENT) → WAIT_BARBER
│  └─ (seleciona barbeiro) → WAIT_SERVICE
│     └─ (seleciona serviço) → WAIT_DATE
│        └─ (informa data) → WAIT_TIME_PREF
│           └─ (informa hora aproximada) → WAIT_SLOT_PICK
│              └─ (escolhe horário sugerido) → WAIT_CONFIRMATION
│                 ├─ (SIM) → CONFIRMED ✅
│                 └─ (NÃO) → WAIT_BARBER
└─ (CANCEL | REMARK) → WAIT_CLARIFICATION
```

---

## 🧩 Camadas e Responsabilidades

- **Canal de entrada:** Web chat hoje; WhatsApp amanhã (via adapters em `app/integrations/channels/`)
- **Motor de conversa:** Máquina de estados em `services/conversation.py`
- **NLU / interpretação:** `services/nlu.py` (substituível por LLM mantendo a interface)
- **Regras de negócio:** Disponibilidade, conflitos, horários em `services/availability.py`
- **Persistência:** Repositórios SQLite em `app/repositories/*` (evolutivo para outros bancos)

---

## 🚀 Começando

### Instalação

```bash
cd chat_bot

# Criar virtual env
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

### Rodar a aplicação

```bash
uvicorn app.main:app --reload --port 8000
```

A API estará em `http://localhost:8000`

### Testar

```bash
# Testes do happy path
pytest app/tests/test_conversation_happy_path.py -v

# Com cobertura
pytest app/tests/ --cov=app --cov-report=html
```

---

## 📡 API

### POST `/chat/web`

Envia uma mensagem de chat e recebe a resposta do bot.

**Request:**
```json
{
  "client_id": "user_123",
  "message": "Oi, quero agendar um horário",
  "state": "START"
}
```

**Response:**
```json
{
  "reply": "Olá! 👋 Bem-vindo à barbearia! Posso te ajudar a agendar, remarcar ou cancelar um horário.",
  "state": "WAIT_BARBER",
  "buttons": [
    {"id": "BARBER_1", "label": "João"},
    {"id": "BARBER_2", "label": "Carlos"}
  ]
}
```

### GET `/health`

Health check da API.

---

## 🗄️ Banco de Dados

SQLite com seguinte schema:

### `clients`
```
id | client_key | name | conversation_state | conversation_ctx_json | ...
```

### `appointments`
```
id | client_id | barber_id | service_id | start_at | end_at | status | ...
```

### `barbers`
```
id | name | is_active
```

### `services`
```
id | name | duration_minutes | price_cents | is_active
```

---

## ⚙️ Configuração

Editar `app/core/config.py`:

```python
BUSINESS_START = "09:00"    # Abertura
BUSINESS_END = "19:00"      # Fechamento
LUNCH_START = "12:00"       # Almoço início
LUNCH_END = "13:00"         # Almoço fim
SLOT_STEP_MINUTES = 30      # Intervalo entre slots
```

---

## 📝 Boas Práticas Implementadas

✅ **Clean Code**
- Nomes explícitos e significativos
- Funções pequenas com responsabilidade única
- Sem lógica "mágica"

✅ **Arquitetura Limpa**
- Separação clara entre camadas (routes → services → repositories)
- Fácil de testar e estender

✅ **Tipos Estruturados**
- `ConversationContext` ao invés de dict solto
- Type hints em funções críticas

✅ **Segurança**
- Validação de `client_id` (SQL injection prevention)
- CORS configurado
- Constraint de conflitos no BD

✅ **Observabilidade**
- Logging estruturado em pontos críticos
- Estados de transição registrados
- Erros detalhados

✅ **Testes**
- Cobertura do fluxo completo de agendamento
- Casos de erro e validação

---

## 🔮 Próximas Funcionalidades

- [ ] Integração com WhatsApp
- [ ] Cancelamento de agendamentos via chat
- [ ] Remarcação de horários
- [ ] Notificações via SMS/email
- [ ] Histórico de agendamentos do cliente
- [ ] Rate limiting e autenticação
- [ ] Dashboard de administração

---

## 🧭 Princípios do Projeto

- **Conversa curta e objetiva:** resolver em poucos passos
- **Sem formatação rígida:** não travar o usuário
- **Evitar overengineering:** só o necessário para funcionar bem
- **Código legível e evolutivo:** interfaces estáveis entre camadas
- **Persistência de contexto:** independente do frontend
- **UX voltada ao WhatsApp:** desde o início

---

## 👨‍💼 Contribuindo

Este é um projeto em produção. Ao fazer mudanças:

1. ✅ Rodar testes: `pytest`
2. ✅ Testar fluxos manualmente
3. ✅ Atualizar esta documentação se necessário
4. ✅ Fazer commit com mensagem clara

---

## 📞 Suporte

Para problemas, verificar:
- `logs/` - Logs estruturados de cada módulo
- `data.sqlite3` - Estado atual do BD (abra com SQLite browser)
