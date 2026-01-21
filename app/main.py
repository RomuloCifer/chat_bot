from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router
from app.repositories.db import init_db

def create_app() -> FastAPI:
    app = FastAPI(title="Barbershop Chatbot", version="0.1.0")

    @app.on_event("startup")
    def _startup():
        init_db()

    app.include_router(health_router, tags=["health"])
    app.include_router(chat_router, tags=["chat"])
    return app

app = create_app()
