from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        description="Core API for Financial, Inventory and Payroll System (FIP) with Clean Architecture."
    )

    # Set all CORS enabled origins
    if settings.CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Routes métier activées après mise en place du contexte utilisateur et
    # de l'isolation multi-organisation.

    return application

app = create_application()

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.VERSION, "service": settings.PROJECT_NAME}
