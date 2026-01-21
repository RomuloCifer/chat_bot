from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router
from app.repositories.db import init_db
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Barbershop Chatbot", version="0.1.0")

    # CORS - permite requisições de fronts web (ajuste conforme necessário)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8080"],  # Fronts locais
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup():
        logger.info("Iniciando aplicação...")
        init_db()
        logger.info("Banco de dados inicializado")

    app.include_router(health_router, tags=["health"])
    app.include_router(chat_router, tags=["chat"])
    
    logger.info("Rotas registradas")
    return app


app = create_app()

