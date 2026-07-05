import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from services.database import init_db, get_preference
from services.scheduler import scheduler, reschedule_email_jobs

# Lifespan events for database and scheduler setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    print("🚀 Inizializzazione database...")
    init_db()
    
    print("📅 Avvio scheduler dei task in background...")
    scheduler.start()
    reschedule_email_jobs()
    
    yield
    
    # Shutdown actions
    print("🛑 Arresto dello scheduler...")
    scheduler.shutdown()

app = FastAPI(
    title="Secondo Cervello OS API",
    description="Backend Core REST API per il sistema LLM OS & Personal Wiki",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication dependency
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    expected_token = get_preference("BEARER_TOKEN", os.environ.get("API_BEARER_TOKEN", "secure_secret_token_12345"))
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token di autenticazione non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

# Import routers (to be created)
from src.api.routes.wiki import router as wiki_router
from src.api.routes.chat import router as chat_router
from src.api.routes.audio import router as audio_router
from src.api.routes.config import router as config_router

# Include routers, applying the authentication dependency globally to protect all endpoints
app.include_router(wiki_router, prefix="/api/wiki", tags=["Wiki"], dependencies=[Depends(get_current_user)])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat & Memory"], dependencies=[Depends(get_current_user)])
app.include_router(audio_router, prefix="/api/audio", tags=["Audio & Diario"], dependencies=[Depends(get_current_user)])
app.include_router(config_router, prefix="/api/config", tags=["Configuration & Scheduler"], dependencies=[Depends(get_current_user)])

@app.get("/")
def read_root(current_user: str = Depends(get_current_user)):
    return {
        "status": "online",
        "message": "Secondo Cervello OS API is running.",
        "version": "1.0.0"
    }

@app.post("/api/upload-asset", tags=["Wiki"], dependencies=[Depends(get_current_user)])
async def upload_asset_top_level(file: UploadFile = File(...)):
    """Alias di alto livello per il caricamento diretto di asset multimediali."""
    from src.api.routes.wiki import upload_asset
    return await upload_asset(file)
